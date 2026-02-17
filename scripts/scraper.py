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
    EXTRA_HEADERS,
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
from scripts.utils import remove_ads, scroll_to_top
from scripts.utils.merger import merge_player_data
from scripts.utils.proxy import ProxyManager
from scripts.utils.throttle import AdaptiveThrottle
from scripts.exceptions import InvalidDOMError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
import time

# Garantir que diretório de logs existe
LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOG_TIMESTAMP = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')

# Configuração de Logs (RFC 005)
from app.utils.logger import get_logger, slog, log_diagnostic
logger = get_logger(__name__)

COMPONENT = "scraper"


class OgolScraper:
    """Scraper para ogol.com.br - extrai estatísticas de partidas do Brasileirão."""
    
    def __init__(self, headless: bool = True, detailed: bool = False, throttle: AdaptiveThrottle = None) -> None:
        """
        Inicializa o scraper.
        
        Args:
            headless: Se True, roda o browser sem interface gráfica
            detailed: Se True, extrai stats detalhadas de cada jogador (mais lento)
            throttle: Instância opcional de AdaptiveThrottle (compartilhada)
        """
        self.headless = headless
        self.detailed = detailed
        self.strict_mode = True # Always strict by default for now
        self.data: Dict[str, Any] = {}
        self.proxy_manager = ProxyManager()
        self.throttle = throttle or AdaptiveThrottle()
    
    def _validate_page_structure(self, page):
        """
        Validates if the page has the expected DOM structure.
        Raises InvalidDOMError if critical elements are missing.
        """
        try:
            # 1. Check for Match Header or Game Report (Basic Identity)
            has_identity = page.evaluate('''() => {
                return !!(
                    document.querySelector('.zz-container #game_report') || 
                    document.querySelector('.match-header') ||
                    document.querySelector('.match-header-team')
                );
            }''')
            
            if not has_identity:
                raise InvalidDOMError("Page missing match identity (header/game_report)")

            # 2. Check for Score (Critical)
            has_score = page.evaluate('''() => {
                return !!document.querySelector('.match-header-vs .result') || 
                       !!document.querySelector('.match-header-vs a');
            }''')
            
            if not has_score:
                 # Check if it's a future match (no score yet)? 
                 # For now, we assume we only scrape past matches or live matches with score.
                 # But if we are scraping 'fixtures', this might fail.
                 # Given the user wants "100% efficiency" to avoid garbage, we enforce score presence.
                 raise InvalidDOMError("Page missing score element")

            # 3. Check for Stats Containment (Critical context for statistics)
            if self.strict_mode:
                has_stats_container = page.evaluate('''() => {
                    // Check for either the new layout container or old graph bars
                    return !!(
                        document.querySelector('.zz-container table') || 
                        document.querySelector('.graph-bar')
                    );
                }''')
                
                if not has_stats_container:
                     raise InvalidDOMError("Page missing statistics container (table or graph-bar)")

        except Exception as e:
            if isinstance(e, InvalidDOMError):
                raise e
            # If evaluate fails (page closed?), wrap it
            raise InvalidDOMError(f"DOM Validation failed unexpectedly: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((PlaywrightTimeout, Exception)), # Will retry InvalidDOMError too? Maybe not desired?
        # Actually, if DOM is wrong, retrying might fix it if it was a partial load. 
        # So yes, retry InvalidDOMError is acceptable.
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def _execute_scrape_logic(self, page, url: str):
        """Core logic with retry support"""
        from scripts.utils.cloudflare import wait_for_cloudflare
        
        # Carregar página e aguardar conteúdo inicial
        start_time = time.time()
        page.goto(url, wait_until='domcontentloaded', timeout=NAVIGATION_TIMEOUT)
        
        # Wait for Cloudflare challenge to resolve (if present)
        cf_resolved = wait_for_cloudflare(page, timeout=30)
        if not cf_resolved:
            raise InvalidDOMError(f"Cloudflare challenge did not resolve for {url}")
        
        # Adaptive Throttle: sleep proportional to server response time
        response_time = time.time() - start_time
        self.throttle.wait(response_time)

        page.wait_for_timeout(JS_INITIAL_WAIT)
        
        remove_ads(page)
        
        # Validation Step
        try:
            self._validate_page_structure(page)
        except InvalidDOMError as e:
            slog(logger, 'warning', 'DOM validation failed on first load, attempting scrolls',
                 component=COMPONENT, operation='validate_dom',
                 url=url, error_message=str(e))
            # Maybe it needs scrolling to load? Continue to scrolls logic and validate again?
            # Or fail fast?
            # User wants "100% efficient", so maybe fail explicitly?
            # But let's try the scrolls -> validate pattern to be robust.
            pass

        # Scroll agressivo para forçar lazy loading
        for scroll in INITIAL_SCROLL_POSITIONS:
            page.evaluate(f'window.scrollTo(0, {scroll})')
            page.wait_for_timeout(SCROLL_DELAY)
            remove_ads(page)
        
        # Voltar ao topo e esperar estabilizar
        scroll_to_top(page, STABILIZATION_WAIT)
        
        # Final Strong Validation
        self._validate_page_structure(page)
        
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
        
        # 3. Smart Scroll para seções críticas (Lineups e Eventos)
        target_selectors = [
            '.zz-container #game_report',  # Escalações (Layout Novo)
            '.zz-module.game_matchup',     # Escalações (Layout Antigo)
            '.match-header-scorers',       # Gols
            '#event_summary'               # Eventos gerais
        ]
        
        logger.info("Executando Smart Scroll para carregar seções...")
        for selector in target_selectors:
            try:
                # Tenta localizar mas não falha se não existir (layout dinâmico)
                loc = page.locator(selector).first
                if loc.is_visible():
                    loc.scroll_into_view_if_needed()
                    page.wait_for_timeout(SCROLL_DELAY)
            except Exception:
                pass
        
        # Scroll final para o fundo para garantir footer/ads/scripts finais
        page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        page.wait_for_timeout(STABILIZATION_WAIT)
        remove_ads(page)

        # Voltar um pouco para garantir que lineups não ficaram "acima" do view se footer for grande
        page.evaluate('window.scrollBy(0, -500)')
        page.wait_for_timeout(500)
        
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
        
        slog(logger, 'info', 'Scraping completed for match', component=COMPONENT,
             operation='extract_complete', url=url,
             home_team=self.data.get('home_team'),
             away_team=self.data.get('away_team'),
             home_score=self.data.get('home_score'),
             away_score=self.data.get('away_score'),
             has_stats='stats_home' in self.data,
             has_lineups='escalacao_casa' in self.data,
             has_events='eventos' in self.data)
        
        # Unificar dados de jogadores para evitar redundância
        self.data = merge_player_data(self.data)
        
        return self.data

    def scrape(self, url: str) -> Dict[str, Any]:
        """
        Executa o scraping completo de forma flexível.
        
        Args:
            url: URL do jogo no ogol.com.br
            
        Returns:
            Dicionário com todos os dados extraídos
        """
        slog(logger, 'info', 'Starting match scrape', component=COMPONENT,
             operation='scrape_start', url=url,
             headless=self.headless, detailed=self.detailed)
        
        # [NEW] Get proxy
        proxy_config = self.proxy_manager.get_proxy()
        
        with sync_playwright() as p:
            # [NEW] Pass proxy to launch
            browser = p.chromium.launch(
                headless=self.headless,
                args=BROWSER_ARGS,
                proxy=proxy_config  # Inject proxy if available
            )
            # Contexto com anti-detecção e headers extras
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport=VIEWPORT,
                extra_http_headers=EXTRA_HEADERS,
                locale='pt-BR',
                timezone_id='America/Sao_Paulo'
            )
            page = context.new_page()
            
            try:
                # Chama a lógica com retry
                self._execute_scrape_logic(page, url)
                
            except Exception as e:
                log_diagnostic(logger, 'Fatal scraping error after retries',
                    component=COMPONENT, operation='scrape_fatal',
                    error=e,
                    hint='All retry attempts failed. Possible causes: (1) anti-bot detection, (2) page structure changed, (3) network issues on Render',
                    url=url)
                
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
        log_diagnostic(logger, 'Failed to extract basic match info',
            component=COMPONENT, operation='validate_output',
            expected='home_team and away_team present in scraped data',
            actual=f'home_team={data.get("home_team")}, away_team={data.get("away_team")}',
            hint='Scraper returned data but critical fields are missing. The page DOM may have changed.',
            url=url if len(sys.argv) > 1 else 'N/A')
        sys.exit(1)
    
    # Output JSON
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
