#!/usr/bin/env python3
"""
db_importer.py - Ingestão de dados estatísticos para PostgreSQL.

Este script processa dados estruturados e semi-estruturados (JSON) e os persiste no RDS,
garantindo integridade via operações atômicas (ON CONFLICT).

Exemplo de uso:
    python3 scripts/run_batch.py --rodada 1 | python3 scripts/db_importer.py
"""

import json
import sys
import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler('logs/db_importer.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)


def get_or_create_season(cursor, league_slug: str, year: int) -> int:
    """
    Get or create season for league+year.
    
    Args:
        cursor: database cursor
        league_slug: ogol.com.br league slug (e.g., 'brasileirao', 'premier-league')
        year: season year (e.g., 2026)
    
    Returns:
        season_id
    """
    # Get league ID from ogol_slug
    cursor.execute("SELECT id FROM leagues WHERE ogol_slug = %s", (league_slug,))
    league_row = cursor.fetchone()
    
    if not league_row:
        raise ValueError(f"League with ogol_slug '{league_slug}' not found in database")
    
    league_id = league_row['id']
    
    # Get or create season
    cursor.execute("""
        SELECT id FROM seasons 
        WHERE league_id = %s AND year = %s
    """, (league_id, year))
    
    season_row = cursor.fetchone()
    
    if season_row:
        return season_row['id']
    
    # Create new season
    logger.info(f"Creating new season: {league_slug} {year}")
    cursor.execute("""
        INSERT INTO seasons (league_id, year, is_current)
        VALUES (%s, %s, TRUE)
        RETURNING id
    """, (league_id, year))
    
    return cursor.fetchone()['id']



def get_connection():
    """
    Cria conexão com o banco de dados PostgreSQL.
    Regra S01: Credenciais via ENV VAR.
    """
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        logger.error("DATABASE_URL não definida. Configure a variável de ambiente.")
        sys.exit(1)
    
    try:
        conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        return conn
    except psycopg2.Error as e:
        logger.error(f"Erro ao conectar ao PostgreSQL: {e}")
        sys.exit(1)


def get_or_create_time(cursor, nome: str) -> int:
    """Busca ou cria um time pelo nome usando ON CONFLICT para segurança paralela."""
    cursor.execute("""
        INSERT INTO times (nome) VALUES (%s)
        ON CONFLICT (nome) DO UPDATE SET nome = EXCLUDED.nome
        RETURNING id
    """, (nome,))
    return cursor.fetchone()['id']


def get_or_create_jogador(cursor, nome: str, time_id: Optional[int] = None) -> int:
    """Busca ou cria um jogador pelo nome."""
    # Como jogadores podem ter nomes iguais, idealmente teríamos um identificador único do Ogol.
    # Por ora, mantemos busca por nome. Se quisermos evitar duplicatas em paralelo:
    cursor.execute("SELECT id FROM jogadores WHERE nome = %s", (nome,))
    result = cursor.fetchone()
    if result: return result['id']

    cursor.execute("""
        INSERT INTO jogadores (nome, time_atual_id) VALUES (%s, %s)
        RETURNING id
    """, (nome, time_id))
    return cursor.fetchone()['id']


def get_or_create_arbitro(cursor, nome: str, estado: Optional[str] = None) -> int:
    """Busca ou cria um árbitro pelo nome."""
    cursor.execute("""
        INSERT INTO arbitros (nome) VALUES (%s)
        ON CONFLICT (nome) DO UPDATE SET nome = EXCLUDED.nome
        RETURNING id
    """, (nome,))
    return cursor.fetchone()['id']


def get_or_create_estadio(cursor, nome: str, cidade: Optional[str] = None, 
                           estado: Optional[str] = None, capacidade: Optional[int] = None) -> int:
    """Busca ou cria um estádio pelo nome."""
    cursor.execute("""
        INSERT INTO estadios (nome) VALUES (%s)
        ON CONFLICT (nome) DO UPDATE SET nome = EXCLUDED.nome
        RETURNING id
    """, (nome,))
    return cursor.fetchone()['id']


def validate_json(data: dict) -> bool:
    """Valida se o JSON possui os campos obrigatórios."""
    required_fields = ['home_team', 'away_team', 'rodada']
    
    for field in required_fields:
        if field not in data:
            logger.error(f"Campo obrigatório ausente: {field}")
            return False
    
    return True


def check_idempotency(cursor, rodada: int, time_casa_id: int, time_fora_id: int) -> Optional[int]:
    """
    Regra S03: Verifica se a partida já existe no banco.
    Retorna o ID da partida se existir, None caso contrário.
    """
    cursor.execute("""
        SELECT id FROM partidas 
        WHERE rodada = %s AND time_casa_id = %s AND time_fora_id = %s
    """, (rodada, time_casa_id, time_fora_id))
    
    result = cursor.fetchone()
    return result['id'] if result else None


def insert_partida(cursor, data: dict, time_casa_id: int, time_fora_id: int,
                   estadio_id: Optional[int], arbitro_id: Optional[int], season_id: int) -> int:
    """
    Insere a partida ou atualiza se já existir.
    Salva dados extras na coluna JSONB metadata.
    """
    # Preparar metadata (remover campos grandes para economizar espaço)
    metadata = data.copy()
    for key in ['escalacao_casa', 'escalacao_fora', 'eventos', 'stats_home', 'stats_away']:
        metadata.pop(key, None)
    
    cursor.execute("""
        INSERT INTO partidas (
            season_id, rodada, time_casa_id, time_fora_id, 
            gols_casa, gols_fora,
            gols_casa_intervalo, gols_fora_intervalo,
            data_hora, estadio_id, arbitro_id, publico, url_fonte, status,
            metadata
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'finished', %s)
        ON CONFLICT (season_id, rodada, time_casa_id, time_fora_id) 
        DO UPDATE SET
            gols_casa = EXCLUDED.gols_casa,
            gols_fora = EXCLUDED.gols_fora,
            metadata = partidas.metadata || EXCLUDED.metadata,
            updated_at = CURRENT_TIMESTAMP
        RETURNING id
    """, (
        season_id,
        data['rodada'],
        time_casa_id,
        time_fora_id,
        data.get('home_score', 0),
        data.get('away_score', 0),
        data.get('home_score_halftime'),
        data.get('away_score_halftime'),
        data.get('data_hora'),
        estadio_id,
        arbitro_id,
        data.get('publico'),
        data.get('url_fonte'),
        json.dumps(metadata)
    ))
    
    return cursor.fetchone()['id']


def insert_estatisticas(cursor, partida_id: int, data: dict):
    """Insere ou atualiza as estatísticas da partida com flexibilidade JSONB."""
    stats_home = data.get('stats_home', {})
    stats_away = data.get('stats_away', {})
    
    # Capturar TUDO o que vier no stats_home/away como metadata
    metadata = {
        'home_raw': stats_home,
        'away_raw': stats_away
    }
    
    cursor.execute("""
        INSERT INTO estatisticas_partida (
            partida_id,
            posse_casa, posse_fora,
            chutes_casa, chutes_fora,
            chutes_gol_casa, chutes_gol_fora,
            chutes_bloqueados_casa, chutes_bloqueados_fora,
            escanteios_casa, escanteios_fora,
            xg_casa, xg_fora,
            xgot_casa, xgot_fora,
            passes_casa, passes_fora,
            passes_precisao_casa, passes_precisao_fora,
            faltas_casa, faltas_fora,
            impedimentos_casa, impedimentos_fora,
            defesas_goleiro_casa, defesas_goleiro_fora,
            cortes_casa, cortes_fora,
            amarelos_casa, amarelos_fora,
            vermelhos_casa, vermelhos_fora,
            metadata
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (partida_id) 
        DO UPDATE SET
            posse_casa = EXCLUDED.posse_casa,
            posse_fora = EXCLUDED.posse_fora,
            chutes_casa = EXCLUDED.chutes_casa,
            chutes_fora = EXCLUDED.chutes_fora,
            chutes_gol_casa = EXCLUDED.chutes_gol_casa,
            chutes_gol_fora = EXCLUDED.chutes_gol_fora,
            xg_casa = EXCLUDED.xg_casa,
            xg_fora = EXCLUDED.xg_fora,
            passes_casa = EXCLUDED.passes_casa,
            passes_fora = EXCLUDED.passes_fora,
            metadata = estatisticas_partida.metadata || EXCLUDED.metadata,
            updated_at = CURRENT_TIMESTAMP
    """, (
        partida_id,
        stats_home.get('posse'), stats_away.get('posse'),
        stats_home.get('chutes'), stats_away.get('chutes'),
        stats_home.get('chutes_gol'), stats_away.get('chutes_gol'),
        stats_home.get('chutes_bloqueados'), stats_away.get('chutes_bloqueados'),
        stats_home.get('escanteios'), stats_away.get('escanteios'),
        stats_home.get('xg'), stats_away.get('xg'),
        stats_home.get('xgot'), stats_away.get('xgot'),
        stats_home.get('passes'), stats_away.get('passes'),
        stats_home.get('passes_precisao'), stats_away.get('passes_precisao'),
        stats_home.get('faltas'), stats_away.get('faltas'),
        stats_home.get('impedimentos'), stats_away.get('impedimentos'),
        stats_home.get('defesas_goleiro'), stats_away.get('defesas_goleiro'),
        stats_home.get('cortes'), stats_away.get('cortes'),
        stats_home.get('amarelos'), stats_away.get('amarelos'),
        stats_home.get('vermelhos'), stats_away.get('vermelhos'),
        json.dumps(metadata)
    ))


def insert_eventos(cursor, partida_id: int, eventos: list, time_casa_id: int, time_fora_id: int):
    """Insere os eventos da partida (gols, cartões, substituições)."""
    tipo_map = {
        'gol': 'GOL',
        'gol_contra': 'GOL_CONTRA',
        'gol_penalti': 'GOL_PENALTI',
        'cartao_amarelo': 'CARTAO_AMARELO',
        'cartao_vermelho': 'CARTAO_VERMELHO',
        'segundo_amarelo': 'SEGUNDO_AMARELO',
        'substituicao': 'SUBSTITUICAO'
    }
    
    for evento in eventos:
        tipo = tipo_map.get(evento.get('tipo', '').lower())
        if not tipo:
            continue
        
        # Determinar time do evento
        time_id = time_casa_id if evento.get('time') == 'home' else time_fora_id
        
        # Buscar/criar jogadores
        jogador_id = None
        jogador_sec_id = None
        
        if evento.get('jogador'):
            jogador_id = get_or_create_jogador(cursor, evento['jogador'], time_id)
        
        if evento.get('jogador_secundario'):
            jogador_sec_id = get_or_create_jogador(cursor, evento['jogador_secundario'], time_id)
        
        cursor.execute("""
            INSERT INTO eventos (
                partida_id, minuto, minuto_adicional, periodo,
                tipo, jogador_id, jogador_secundario_id, time_id, descricao
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            partida_id,
            evento.get('minuto', 0),
            evento.get('minuto_adicional', 0),
            evento.get('periodo', 1),
            tipo,
            jogador_id,
            jogador_sec_id,
            time_id,
            evento.get('descricao')
        ))



def insert_escalacoes(cursor, partida_id: int, escalacao: dict, time_id: int):
    """
    Insere escalação.
    Assume que o JSON já vem fundido com stats e rating (via scraper/merger).
    """
    # Processar titulares e reservas
    for category, is_titular in [('titulares', True), ('reservas', False)]:
        for player in escalacao.get(category, []):
            nome = player['nome']
            numero = player.get('numero')
            
            # Buscar ou criar jogador
            jogador_id_db = get_or_create_jogador(cursor, nome, time_id)
            
            # Extrair valores já presentes no objeto (merge feito no scraper)
            nota = player.get('rating')
            qualidade = player.get('rating_qualidade')
            
            # JSON stats (include rating_qualidade here since column doesn't exist in table)
            detailed_stats = {}
            for key in ['defesa', 'passe', 'ataque']:
                if key in player:
                    detailed_stats[key] = player[key]
            
            # Add rating_qualidade to stats JSON
            if qualidade:
                detailed_stats['rating_qualidade'] = qualidade
            
            stats_json = json.dumps(detailed_stats) if detailed_stats else '{}'
            
            cursor.execute("""
                INSERT INTO escalacoes (
                    partida_id, jogador_id, time_id, titular, numero_camisa,
                    nota, stats
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (partida_id, jogador_id) 
                DO UPDATE SET
                    nota = EXCLUDED.nota,
                    stats = EXCLUDED.stats
            """, (
                partida_id, 
                jogador_id_db, 
                time_id, 
                is_titular, 
                numero,
                nota,
                stats_json
            ))
            
            logger.info(f"✅ Escalação inserida: {player.get('nome')} (Partida {partida_id}, Rating: {nota})")


def process_input(data: dict, league_slug: str = "brasileirao", year: int = 2026) -> bool:
    """
    Processa o JSON de entrada e persiste no banco.
    Regra S02: COMMIT apenas após validação completa.
    """
    if not validate_json(data):
        return False
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get or create season
        season_id = get_or_create_season(cursor, league_slug, year)
        logger.info(f"Using season_id={season_id} for {league_slug} {year}")
    except Exception as e:
        logger.error(f"Failed to get/create season: {e}")
        conn.close()
        return False
    
    try:
        # Buscar/criar entidades relacionadas
        time_casa_id = get_or_create_time(cursor, data['home_team'])
        time_fora_id = get_or_create_time(cursor, data['away_team'])
        
        # Criar entidades opcionais
        estadio_id = None
        if data.get('estadio'):
            estadio_id = get_or_create_estadio(
                cursor, 
                data['estadio'].get('nome'),
                data['estadio'].get('cidade'),
                data['estadio'].get('estado'),
                data['estadio'].get('capacidade')
            )
        
        arbitro_id = None
        if data.get('arbitro'):
            arbitro_id = get_or_create_arbitro(
                cursor,
                data['arbitro'].get('nome'),
                data['arbitro'].get('estado')
            )

        # Tenta inserir/atualizar partida (ON CONFLICT garante atomicidade)
        partida_id = insert_partida(cursor, data, time_casa_id, time_fora_id, estadio_id, arbitro_id, season_id)
        
        # Inserir estatísticas (ON CONFLICT DO UPDATE)
        if 'stats_home' in data or 'stats_away' in data:
            insert_estatisticas(cursor, partida_id, data)
            logger.info(f"Estatísticas processadas para partida {partida_id}")

        # Inserir eventos (Limpamos antes para evitar duplicação em re-runs)
        if 'eventos' in data:
            cursor.execute("DELETE FROM eventos WHERE partida_id = %s", (partida_id,))
            insert_eventos(cursor, partida_id, data['eventos'], time_casa_id, time_fora_id)
            logger.info(f"Eventos processados: {len(data['eventos'])}")
        
        # Inserir escalações
        if 'escalacao_casa' in data:
            insert_escalacoes(cursor, partida_id, data['escalacao_casa'], time_casa_id)
        if 'escalacao_fora' in data:
            insert_escalacoes(cursor, partida_id, data['escalacao_fora'], time_fora_id)
        
        # Regra S02: COMMIT apenas após sucesso total
        conn.commit()
        logger.info(
            f"✅ Dados salvos: {data['home_team']} {data.get('home_score', '?')}-{data.get('away_score', '?')} {data['away_team']} (Rodada {data['rodada']})"
        )
        return True
        
    except psycopg2.Error as e:
        conn.rollback()
        logger.error(f"Erro PostgreSQL: {e}")
        return False
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro inesperado: {e}")
        return False
        
    finally:
        cursor.close()
        conn.close()


def main():
    """Ponto de entrada principal."""
    # Garantir que diretório de logs existe
    os.makedirs('logs', exist_ok=True)
    
    # Ler JSON da stdin
    try:
        raw_input = sys.stdin.read().strip()
        
        if not raw_input:
            logger.error("Nenhum dado recebido via stdin")
            sys.exit(1)
        
        data = json.loads(raw_input)
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON inválido: {e}")
        sys.exit(1)
    
    # Processar e salvar
    success = process_input(data)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
