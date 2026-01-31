"""
config.py - Configurações centralizadas do scraper

Todas as constantes, timeouts e seletores ficam aqui para facilitar manutenção.
"""

from typing import Dict, List

# =============================================================================
# TIMEOUTS (em milissegundos)
# =============================================================================
NAVIGATION_TIMEOUT = 60000  # Timeout para carregamento de página
ELEMENT_WAIT_TIMEOUT = 5000  # Timeout para esperar elementos específicos
SCROLL_DELAY = 800  # Delay entre scrolls para lazy loading
JS_INITIAL_WAIT = 3000  # Tempo para JS inicial carregar
STABILIZATION_WAIT = 1000  # Tempo para página estabilizar

# =============================================================================
# BROWSER CONFIG
# =============================================================================
USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
VIEWPORT = {'width': 1920, 'height': 1080}
BROWSER_ARGS = [
    '--disable-blink-features=AutomationControlled',
    '--no-sandbox',
    '--disable-dev-shm-usage'
]

# =============================================================================
# SELETORES CSS
# =============================================================================
SELECTORS = {
    # Container principal
    'main_container': '.zz-container',
    'game_report': '.zz-container #game_report',
    
    # Times
    'team_left': '.match-header-team.left .match-header-team-name a',
    'team_right': '.match-header-team.right .match-header-team-name a',
    'team_subtitle': '.subtitle',
    'team_links': 'a[href*="/equipa/"]',
    
    # Placar
    'score': '.match-header-vs a',
    
    # Escalações
    'game_matchup': '.zz-module.game_matchup, .game_matchup',
    'player': '.player',
    'player_name': 'a[href*="/jogador/"]',
    'player_number': '.number',
    'coach': 'a[href*="/treinador/"]',
    
    # Eventos
    'scorers_left': '.match-header-scorers.left',
    'scorers_right': '.match-header-scorers.right',
    
    # Estatísticas
    'stats_bar': '.graph-bar',
    'stats_title': '.bars-title',
    'stats_value': '.bar-header .num',
    
    # Outros
    'stadium': 'a[href*="/estadio/"]',
    'referee': 'a[href*="/arbitro/"]',
    'date_author': '.dateauthor',
    
    # Ads para remover
    'ads_overlay': '.ads-overlay, #onesignal-slidedown-container, .cookie-banner, [class*="ad-"], [id*="google_ads"]'
}

# =============================================================================
# MAPEAMENTO DE ESTATÍSTICAS
# =============================================================================
STATS_FIELD_MAPPING: Dict[str, str] = {
    'posse de bola': 'posse',
    'chutes': 'chutes',
    'chutes (a gol)': 'chutes',
    'escanteios': 'escanteios',
    'gols esperados': 'xg',
    'expected goals': 'xg',
    'gols esperados no alvo': 'xgot',
    'chutes a gol': 'chutes_gol',
    'chutes bloqueados': 'chutes_bloqueados',
    'chutes fora': 'chutes_fora',
    'faltas': 'faltas',
    'impedimentos': 'impedimentos',
    'defesas': 'defesas_goleiro',
    'total passes': 'passes_total',
    'passes certos': 'passes',
    'total cortes': 'cortes',
    'divididas ganhas': 'duelos_ganhos'
}

# =============================================================================
# SCROLL POSITIONS
# =============================================================================
INITIAL_SCROLL_POSITIONS: List[int] = [500, 1000, 2000, 3000, 4000]
LINEUP_SCROLL_RANGE = range(2000, 6000, 1000)
