"""
player_detailed_stats.py - Extrai estatísticas detalhadas de cada jogador

Abre o modal de cada jogador no campo tático para extrair:
- Estatísticas de Defesa (duelos, desarmes, interceptações, etc)
- Estatísticas de Passe (precisão, oportunidades criadas, etc)
- Estatísticas de Ataque (xG, chutes, dribles, etc)

IMPORTANTE: Este extrator é mais lento pois clica em cada jogador (22 por partida).
Use apenas quando precisar dos dados detalhados.
"""

import logging
import time
from typing import Any, Dict, List, Optional
from playwright.sync_api import Page

from ..utils.browser import safe_eval

logger = logging.getLogger(__name__)

# Tempo de espera para o modal abrir (ms)
MODAL_WAIT_MS = 800
# Tempo de espera após fechar modal
CLOSE_WAIT_MS = 300


def extract_player_detailed_stats(page: Page) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extrai estatísticas detalhadas de todos os jogadores.
    
    Fluxo:
    1. Navega para /ao-vivo onde o campo tático está disponível
    2. Identifica todos os blocos de jogadores no campo tático
    3. Para cada jogador: clica -> espera modal -> extrai -> fecha
    4. Retorna listas separadas por time (home/away)
    
    Args:
        page: Página do Playwright com o jogo carregado
        
    Returns:
        Dicionário com:
        - stats_detalhadas_home: Lista de jogadores do mandante
        - stats_detalhadas_away: Lista de jogadores do visitante
    """
    logger.info("Iniciando extração de estatísticas detalhadas dos jogadores...")
    
    # Navegar para a página /ao-vivo onde o campo tático está
    current_url = page.url
    ao_vivo_url = _get_ao_vivo_url(current_url)
    
    if ao_vivo_url and ao_vivo_url != current_url:
        logger.info(f"Navegando para: {ao_vivo_url}")
        try:
            page.goto(ao_vivo_url, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(2000)  # Aguardar carregamento
            
            # Scroll para encontrar o campo tático
            for scroll_y in [1000, 2000, 3000]:
                page.evaluate(f'window.scrollTo(0, {scroll_y})')
                page.wait_for_timeout(500)
                
                # Verificar se campo tático apareceu
                has_pitch = safe_eval(page, r'''
                    document.querySelector('.pitch_eleven_horizontal') !== null
                ''', False)
                
                if has_pitch:
                    logger.info("Campo tático encontrado!")
                    break
                    
        except Exception as e:
            logger.error(f"Erro ao navegar para /ao-vivo: {e}")
    
    # Obter lista de player_ids de cada time
    player_info = safe_eval(page, r'''
        (() => {
            const result = { home: [], away: [] };
            
            const pitch = document.querySelector('.pitch_eleven_horizontal');
            if (!pitch) return result;
            
            const teamTables = pitch.querySelectorAll('table.team');
            if (teamTables.length < 2) return result;
            
            // Home team (primeira tabela)
            teamTables[0].querySelectorAll('.campo_onze_bloco_jogador').forEach(block => {
                const playerId = block.getAttribute('data-player-id');
                const nameSpan = block.querySelector('.player_name .player span');
                if (playerId) {
                    result.home.push({
                        player_id: playerId,
                        nome: nameSpan ? nameSpan.textContent.trim() : null
                    });
                }
            });
            
            // Away team (segunda tabela)
            teamTables[1].querySelectorAll('.campo_onze_bloco_jogador').forEach(block => {
                const playerId = block.getAttribute('data-player-id');
                const nameSpan = block.querySelector('.player_name .player span');
                if (playerId) {
                    result.away.push({
                        player_id: playerId,
                        nome: nameSpan ? nameSpan.textContent.trim() : null
                    });
                }
            });
            
            return result;
        })()
    ''', {'home': [], 'away': []})
    
    home_players = player_info.get('home', [])
    away_players = player_info.get('away', [])
    
    logger.info(f"Encontrados: {len(home_players)} home, {len(away_players)} away")
    
    if not home_players and not away_players:
        logger.warning("Campo tático não encontrado. Stats detalhadas não disponíveis.")
        return {}
    
    # Extrair stats de cada jogador
    stats_home = []
    stats_away = []
    
    for player in home_players:
        stats = _extract_single_player_stats(page, player['player_id'], player.get('nome'))
        if stats:
            stats_home.append(stats)
    
    for player in away_players:
        stats = _extract_single_player_stats(page, player['player_id'], player.get('nome'))
        if stats:
            stats_away.append(stats)
    
    logger.info(f"Stats extraídas: {len(stats_home)} home, {len(stats_away)} away")
    
    result = {}
    if stats_home:
        result['stats_detalhadas_home'] = stats_home
    if stats_away:
        result['stats_detalhadas_away'] = stats_away
        
    return result


def _get_ao_vivo_url(current_url: str) -> Optional[str]:
    """
    Converte URL do jogo para URL da página /ao-vivo.
    
    Ex: .../jogo/.../12345 -> .../jogo/.../12345/ao-vivo
    """
    if not current_url:
        return None
        
    # Remover trailing slash
    url = current_url.rstrip('/')
    
    # Se já está em /ao-vivo, retornar como está
    if url.endswith('/ao-vivo'):
        return url
        
    # Se está em outra sub-página, substituir
    import re
    url = re.sub(r'/(performance|escalacao|estatisticas|cronica)$', '', url)
    
    return f"{url}/ao-vivo"


def _extract_single_player_stats(page: Page, player_id: str, player_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Extrai estatísticas de um único jogador.
    
    Args:
        page: Página do Playwright
        player_id: ID do jogador (data-player-id)
        player_name: Nome do jogador (opcional, para logging)
        
    Returns:
        Dicionário com todas as estatísticas ou None se falhar
    """
    log_name = player_name or player_id
    
    try:
        # 1. Clicar no jogador para abrir modal
        clicked = safe_eval(page, f'''
            (() => {{
                const block = document.querySelector('.campo_onze_bloco_jogador[data-player-id="{player_id}"]');
                if (block) {{
                    block.click();
                    return true;
                }}
                return false;
            }})()
        ''', False)
        
        if not clicked:
            logger.warning(f"Não encontrou jogador: {log_name}")
            return None
        
        # 2. Aguardar modal abrir
        page.wait_for_timeout(MODAL_WAIT_MS)
        
        # 3. Extrair dados do modal usando texto (mais robusto)
        stats_data = safe_eval(page, r'''
            (() => {
                const popup = document.getElementById('match-player-stats-popup');
                if (!popup) return null;
                
                const result = {
                    defesa: {},
                    passe: {},
                    ataque: {},
                    _raw: {},
                    rating: null
                };
                
                // Extrair rating do header
                const ratingBadge = popup.querySelector('span[style*="background-color"]');
                if (ratingBadge) {
                    const ratingText = ratingBadge.textContent.trim();
                    const rating = parseFloat(ratingText);
                    if (!isNaN(rating)) result.rating = rating;
                }
                
                // Pegar todo o texto do popup e parsear por linhas
                const popupText = popup.innerText;
                const lines = popupText.split('\n').map(l => l.trim()).filter(l => l.length > 0);
                
                let currentCategory = 'outros';
                
                // Estatísticas conhecidas por categoria
                const defesaStats = ['duelos ganhos', 'duelos aéreos', 'desarmes', 'interceptações', 
                                    'chutes bloqueados', 'recuperações', 'total cortes', 'cortes',
                                    'faltas', 'dribles sofridos', 'pênaltis cometidos', 'foras de jogo'];
                const passeStats = ['passes certos', 'passes', 'oportunidades criadas', 'passes longos',
                                    'passes para trás', 'passes no último', 'cruzamentos', 'passes chave',
                                    'passes de ruptura', 'grandes chances criadas'];
                const ataqueStats = ['gols esperados', 'xg', 'xgot', 'chutes', 'chutes a gol', 
                                    'chutes para fora', 'chutes na trave', 'toques', 'dribles conseguidos',
                                    'perdas de posse', 'perdas de bola', 'impedimentos', 'faltas sofridas',
                                    'grandes chances perdidas', 'pênaltis a favor'];
                
                for (let i = 0; i < lines.length; i++) {
                    const line = lines[i];
                    const lineLower = line.toLowerCase();
                    
                    // Detectar headers de categoria
                    if (lineLower === 'defesa') { currentCategory = 'defesa'; continue; }
                    if (lineLower === 'passe') { currentCategory = 'passe'; continue; }
                    if (lineLower === 'ataque') { currentCategory = 'ataque'; continue; }
                    
                    // Verificar se a próxima linha é um valor
                    if (i + 1 < lines.length) {
                        const nextLine = lines[i + 1];
                        
                        // Verificar se nextLine parece um valor (número, -, ou formato X/Y)
                        const isValue = /^[\d\-\/\.\(\)%]+$/.test(nextLine.replace(/\s/g, ''));
                        
                        if (isValue) {
                            const label = line;
                            const value = nextLine;
                            
                            // Determinar categoria se ainda não definida
                            if (currentCategory === 'outros') {
                                const labelLower = label.toLowerCase();
                                if (defesaStats.some(s => labelLower.includes(s))) currentCategory = 'defesa';
                                else if (passeStats.some(s => labelLower.includes(s))) currentCategory = 'passe';
                                else if (ataqueStats.some(s => labelLower.includes(s))) currentCategory = 'ataque';
                            }
                            
                            result._raw[label] = value;
                            if (['defesa', 'passe', 'ataque'].includes(currentCategory)) {
                                result[currentCategory][label] = value;
                            }
                            
                            i++; // Pular a linha do valor
                        }
                    }
                }
                
                return result;
            })()
        ''', None)
        
        # 4. Fechar modal
        safe_eval(page, r'''
            (() => {
                const closeBtn = document.querySelector('.zz-popup-close, #match-player-stats-popup .close');
                if (closeBtn) {
                    closeBtn.click();
                    return true;
                }
                // Fallback: clicar fora do modal
                const overlay = document.querySelector('.zz-popup-overlay, .modal-overlay');
                if (overlay) {
                    overlay.click();
                    return true;
                }
                return false;
            })()
        ''', False)
        
        page.wait_for_timeout(CLOSE_WAIT_MS)
        
        if not stats_data:
            logger.warning(f"Modal vazio para: {log_name}")
            return None
        
        # 5. Processar e estruturar os dados
        processed = _process_player_stats(stats_data, player_id, player_name)
        
        return processed
        
    except Exception as e:
        logger.error(f"Erro ao extrair stats de {log_name}: {e}")
        return None


def _process_player_stats(raw_stats: Dict, player_id: str, player_name: Optional[str]) -> Dict[str, Any]:
    """
    Processa e normaliza as estatísticas brutas.
    
    Converte strings como "4/10 (40%)" em estruturas mais úteis.
    """
    result: Dict[str, Any] = {
        'player_id': int(player_id) if player_id else None,
        'nome': player_name,
    }
    
    # Processar cada categoria
    for category in ['defesa', 'passe', 'ataque']:
        cat_data = raw_stats.get(category, {})
        if cat_data:
            result[category] = {}
            for key, value in cat_data.items():
                normalized_key = _normalize_stat_key(key)
                parsed_value = _parse_stat_value(value)
                result[category][normalized_key] = parsed_value
    
    # Adicionar rating se disponível
    if 'rating' in raw_stats:
        result['rating'] = raw_stats['rating']
    
    return result


def _normalize_stat_key(key: str) -> str:
    """
    Normaliza nomes de estatísticas para snake_case.
    
    Ex: "Duelos Ganhos" -> "duelos_ganhos"
    """
    import re
    import unicodedata
    
    # Remover acentos
    key = unicodedata.normalize('NFKD', key).encode('ASCII', 'ignore').decode('utf-8')
    
    # Converter para minúsculas e substituir espaços por underscore
    key = key.lower().strip()
    key = re.sub(r'\s+', '_', key)
    key = re.sub(r'[^\w]', '', key)
    
    return key


def _parse_stat_value(value: str) -> Any:
    """
    Converte valor de estatística para tipo adequado.
    
    Exemplos:
    - "4/10 (40%)" -> {"total": 4, "tentativas": 10, "percentual": 40}
    - "6.5" -> 6.5
    - "3" -> 3
    - "-" -> None
    """
    if not value or value == '-':
        return None
    
    import re
    
    # Padrão: "X/Y (Z%)"
    match = re.match(r'(\d+)/(\d+)\s*\((\d+(?:\.\d+)?)%\)', value)
    if match:
        return {
            'total': int(match.group(1)),
            'tentativas': int(match.group(2)),
            'percentual': float(match.group(3))
        }
    
    # Padrão: "X/Y" (sem percentual)
    match = re.match(r'(\d+)/(\d+)', value)
    if match:
        total = int(match.group(1))
        tentativas = int(match.group(2))
        percentual = round((total / tentativas) * 100, 1) if tentativas > 0 else 0
        return {
            'total': total,
            'tentativas': tentativas,
            'percentual': percentual
        }
    
    # Número decimal
    try:
        if '.' in value or ',' in value:
            return float(value.replace(',', '.'))
        return int(value)
    except ValueError:
        return value  # Retorna string se não conseguir parsear
