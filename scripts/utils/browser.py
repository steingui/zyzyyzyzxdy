"""
browser.py - Utilitários para interação com o browser (Playwright)
"""

import logging
from typing import Any, Optional
from playwright.sync_api import Page

from ..config import SELECTORS

logger = logging.getLogger(__name__)


def safe_eval(page: Page, js_code: str, default: Optional[Any] = None) -> Any:
    """
    Executa JavaScript de forma segura, retornando default em caso de erro.
    
    Args:
        page: Página do Playwright
        js_code: Código JavaScript a executar
        default: Valor padrão em caso de erro
        
    Returns:
        Resultado da execução ou valor default
    """
    try:
        return page.evaluate(js_code)
    except Exception as e:
        logger.debug(f"Erro ao executar JS: {e}")
        return default


def remove_ads(page: Page) -> None:
    """
    Remove overlays e ads que interferem na extração.
    
    Args:
        page: Página do Playwright
    """
    try:
        page.evaluate(f'''
            (() => {{
                const selectors = '{SELECTORS["ads_overlay"]}';
                document.querySelectorAll(selectors).forEach(el => el.remove());
                
                // Remover modais e overlays genéricos
                document.querySelectorAll('[style*="position: fixed"]').forEach(el => {{
                    if (el.offsetHeight > window.innerHeight * 0.3) el.remove();
                }});
                
                // Garantir scroll
                document.body.style.overflow = 'auto';
                document.documentElement.style.overflow = 'auto';
            }})()
        ''')
    except Exception as e:
        logger.debug(f"Erro ao remover ads: {e}")


def scroll_page(page: Page, positions: list[int], delay_ms: int = 800) -> None:
    """
    Faz scroll progressivo na página para forçar lazy loading.
    
    Args:
        page: Página do Playwright
        positions: Lista de posições Y para scroll
        delay_ms: Delay entre cada scroll em milissegundos
    """
    for y in positions:
        page.evaluate(f'window.scrollTo(0, {y})')
        page.wait_for_timeout(delay_ms)
        remove_ads(page)


def scroll_to_top(page: Page, wait_ms: int = 1000) -> None:
    """
    Volta ao topo da página e aguarda estabilização.
    
    Args:
        page: Página do Playwright
        wait_ms: Tempo de espera após scroll
    """
    page.evaluate('window.scrollTo(0, 0)')
    page.wait_for_timeout(wait_ms)
