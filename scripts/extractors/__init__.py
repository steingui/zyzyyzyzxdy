"""
Extractors package - Módulos de extração de dados específicos
"""

from .match_info import extract_match_info
from .statistics import extract_statistics
from .events import extract_events
from .lineups import extract_lineups
from .player_ratings import extract_player_ratings
from .player_detailed_stats import extract_player_detailed_stats

__all__ = [
    'extract_match_info', 
    'extract_statistics', 
    'extract_events', 
    'extract_lineups',
    'extract_player_ratings',
    'extract_player_detailed_stats',
]
