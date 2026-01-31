#!/usr/bin/env python3
"""
scraper.py - Scraper de estatísticas do Brasileirão

Extrai dados de partidas do site ogol.com.br e retorna JSON estruturado.
Campos não encontrados são retornados como null (flexibilidade).

Uso:
    python3 scraper.py <URL>
    python3 scraper.py <URL> --no-headless    # Para debug visual
    python3 scraper.py <URL> --detailed       # Inclui stats detalhadas de cada jogador

Exemplo:
    python3 scraper.py "https://www.ogol.com.br/jogo/2024-04-13-palmeiras-sao-paulo/12345"
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Configurar path para imports relativos funcionarem quando executado diretamente
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.config import (
    NAVIGATION_TIMEOUT,
    ELEMENT_WAIT_TIMEOUT,
    SCROLL_DELAY,
    JS_INITIAL_WAIT,
    STABILIZATION_WAIT,
    USER_AGENT,
    VIEWPORT,
    BROWSER_ARGS,
    INITIAL_SCROLL_POSITIONS,
    LINEUP_SCROLL_RANGE,
)
from scripts.extractors import (
    extract_match_info,
    extract_statistics,
    extract_events,
    extract_lineups,
    extract_player_ratings,
    extract_player_detailed_stats,
)
from scripts.utils import remove_ads, scroll_to_top, merge_player_data

# Garantir que diretório de logs existe
LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOG_TIMESTAMP = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(LOG_DIR / f'scraper_{LOG_TIMESTAMP}.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)


class OgolScraper:
    """Scraper para ogol.com.br - extrai estatísticas de partidas do Brasileirão."""
    
    def __init__(self, headless: bool = True, detailed: bool = False) -> None:
        """
        Inicializa o scraper.
        
        Args:
            headless: Se True, roda o browser sem interface gráfica
            detailed: Se True, extrai stats detalhadas de cada jogador (mais lento)
        """
        self.headless = headless
        self.detailed = detailed
        self.data: Dict[str, Any] = {}
    
    def scrape(self, url: str) -> Dict[str, Any]:
        """
        Executa o scraping completo de forma flexível.
        
        Args:
            url: URL do jogo no ogol.com.br
            
        Returns:
            Dicionário com todos os dados extraídos
        """
        logger.info(f"Iniciando scraping: {url}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=BROWSER_ARGS
            )
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport=VIEWPORT
            )
            page = context.new_page()
            
            try:
                # Carregar página e aguardar conteúdo inicial
                page.goto(url, wait_until='domcontentloaded', timeout=NAVIGATION_TIMEOUT)
                page.wait_for_timeout(JS_INITIAL_WAIT)
                
                remove_ads(page)
                
                # Scroll agressivo para forçar lazy loading
                for scroll in INITIAL_SCROLL_POSITIONS:
                    page.evaluate(f'window.scrollTo(0, {scroll})')
                    page.wait_for_timeout(SCROLL_DELAY)
                    remove_ads(page)
                
                # Voltar ao topo e esperar estabilizar
                scroll_to_top(page, STABILIZATION_WAIT)
                
                # Tentar esperar por elementos específicos (flexível)
                try:
                    page.wait_for_selector('.graph-bar', timeout=ELEMENT_WAIT_TIMEOUT)
                except Exception:
                    pass
                
                # === EXTRAÇÃO DE DADOS ===
                
                # 1. Info básica (sempre funciona)
                self.data = extract_match_info(page)
                self.data['url_fonte'] = url
                
                # 2. Estatísticas
                stats = extract_statistics(page)
                self.data.update(stats)
                
                # 3. Scroll para seção de escalações e eventos
                for y in LINEUP_SCROLL_RANGE:
                    page.evaluate(f'window.scrollTo(0, {y})')
                    page.wait_for_timeout(SCROLL_DELAY)
                    remove_ads(page)
                
                # Tentar esperar pelo container de escalações
                try:
                    page.wait_for_selector('.zz-module.game_matchup, .game_matchup', timeout=ELEMENT_WAIT_TIMEOUT)
                except Exception:
                    pass
                
                page.wait_for_timeout(STABILIZATION_WAIT)
                
                # 4. Eventos (gols + cartões)
                events = extract_events(page)
                if events:
                    self.data['eventos'] = events
                
                # 5. Escalações
                lineups = extract_lineups(page)
                self.data.update(lineups)
                
                # 6. Ratings dos jogadores (campo tático visual)
                ratings = extract_player_ratings(page)
                if ratings:
                    self.data.update(ratings)
                
                # 7. Stats detalhadas de cada jogador (opcional, lento)
                if self.detailed:
                    logger.info("Extraindo stats detalhadas de jogadores (22 modais)...")
                    detailed_stats = extract_player_detailed_stats(page)
                    if detailed_stats:
                        self.data.update(detailed_stats)
                
                logger.info(f"Scraping concluído: {self.data.get('home_team', '?')} x {self.data.get('away_team', '?')}")
                
                # Unificar dados de jogadores para evitar redundância
                self.data = merge_player_data(self.data)
                
            except PlaywrightTimeout as e:
                logger.error(f"Timeout ao acessar {url}: {e}")
                
            except Exception as e:
                logger.error(f"Erro no scraping: {e}")
                
            finally:
                browser.close()
        
        return self.data


def main() -> None:
    """Ponto de entrada principal."""
    if len(sys.argv) < 2:
        print("Uso: python3 scraper.py <URL> [opções]", file=sys.stderr)
        print("Opções:", file=sys.stderr)
        print("  --no-headless  Mostra o browser (debug)", file=sys.stderr)
        print("  --detailed     Extrai stats detalhadas de cada jogador (lento)", file=sys.stderr)
        print("Exemplo: python3 scraper.py 'https://www.ogol.com.br/jogo/...'", file=sys.stderr)
        sys.exit(1)
    
    url = sys.argv[1]
    headless = '--no-headless' not in sys.argv
    detailed = '--detailed' in sys.argv
    
    scraper = OgolScraper(headless=headless, detailed=detailed)
    data = scraper.scrape(url)
    
    # Validação mínima flexível
    if not data.get('home_team') or not data.get('away_team'):
        logger.error("Não foi possível extrair informações básicas da partida")
        sys.exit(1)
    
    # Output JSON
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
