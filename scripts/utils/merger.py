"""
merger.py - Utilitário para unificar dados de jogadores

Combina dados dispersos (escalações, ratings, stats detalhadas) em uma única estrutura
dentro da escalação, eliminando redundâncias no JSON final.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def merge_player_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Unifica dados de jogadores espalhados em múltiplas chaves.
    
    Combina:
    - escalacao_casa/fora (titulares e reservas)
    - ratings_home/away
    - stats_detalhadas_home/away
    
    Args:
        data: Dicionário completo extraído pelo scraper
        
    Returns:
        Dicionário limpo, com dados fundidos em 'escalacao_*' e 
        chaves redundantes removidas.
    """
    # Processar Casa
    _merge_team_data(
        data.get('escalacao_casa', {}),
        data.get('ratings_home', []),
        data.get('stats_detalhadas_home', [])
    )
    
    # Processar Fora
    _merge_team_data(
        data.get('escalacao_fora', {}),
        data.get('ratings_away', []),
        data.get('stats_detalhadas_away', [])
    )
    
    # Remover chaves redundantes
    keys_to_remove = [
        'ratings_home', 'ratings_away',
        'stats_detalhadas_home', 'stats_detalhadas_away'
    ]
    
    for key in keys_to_remove:
        if key in data:
            del data[key]
            
    return data


def _merge_team_data(escalacao: Dict, ratings: List[Dict], stats: List[Dict]) -> None:
    """
    Funde ratings e stats dentro da estrutura de escalação (in-place).
    """
    if not escalacao:
        return

    # Criar mapas de busca por nome e ID
    ratings_map = _create_player_map(ratings)
    stats_map = _create_player_map(stats)
    
    # Função auxiliar para enriquecer lista de jogadores
    def enrich_players(players_list: List[Dict]):
        for player in players_list:
            
            # Tentar encontrar via Map
            # Prioridade: ID > Nome exato > Nome similar
            
            # --- MERGE RATINGS ---
            rating_data = _find_match(player, ratings_map)
            if rating_data:
                # Merge seguro
                if 'rating' not in player and 'rating' in rating_data:
                    player['rating'] = rating_data['rating']
                if 'rating_qualidade' not in player and 'rating_qualidade' in rating_data:
                    player['rating_qualidade'] = rating_data['rating_qualidade']
                # Se não tínhamos ID, pegamos do rating
                if not player.get('player_id') and rating_data.get('player_id'):
                    player['player_id'] = rating_data['player_id']

            # --- MERGE DETAILED STATS ---
            stat_data = _find_match(player, stats_map)
            if stat_data:
                # Stats detalhadas (defesa, passe, ataque)
                for cat in ['defesa', 'passe', 'ataque']:
                    if cat in stat_data and cat not in player:
                        player[cat] = stat_data[cat]
                
                # Aproveitar ID se ainda não tiver
                if not player.get('player_id') and stat_data.get('player_id'):
                    player['player_id'] = stat_data['player_id']
                    
                # Aproveitar rating se veio das stats detalhadas e não tínhamos
                if 'rating' not in player and 'rating' in stat_data:
                    player['rating'] = stat_data['rating']

    # Aplicar em titulares e reservas
    enrich_players(escalacao.get('titulares', []))
    enrich_players(escalacao.get('reservas', []))


def _create_player_map(player_list: List[Dict]) -> Dict[str, Dict]:
    """Cria mapa hash para busca rápida por nome normalizado e ID."""
    mapping = {}
    for p in player_list:
        # Chave por ID (string)
        if p.get('player_id'):
            mapping[f"id:{p['player_id']}"] = p
            
        # Chave por nome (normalizado)
        if p.get('nome'):
            norm_name = _normalize_name(p['nome'])
            mapping[f"name:{norm_name}"] = p
            
    return mapping


def _find_match(target: Dict, source_map: Dict) -> Optional[Dict]:
    """Tenta encontrar o jogador correspondente no mapa."""
    # 1. Tentar por ID
    if target.get('player_id'):
        key = f"id:{target['player_id']}"
        if key in source_map:
            return source_map[key]
            
    # 2. Tentar por Nome
    if target.get('nome'):
        key = f"name:{_normalize_name(target['nome'])}"
        if key in source_map:
            return source_map[key]
            
    return None


def _normalize_name(name: str) -> str:
    """Normaliza nome para chave de busca (lowercase, sem acentos, sem espaços extras)."""
    import unicodedata
    if not name:
        return ""
    
    # Remover acentos e converter para minúsculas
    normalized = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('utf-8')
    return normalized.lower().strip().replace(' ', '')
