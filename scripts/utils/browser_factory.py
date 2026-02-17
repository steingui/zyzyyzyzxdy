"""
browser_factory.py - Centralized browser lifecycle for Playwright.

Single source of truth for launching browsers, creating contexts,
and handling Cloudflare challenges. Used by both crawl_round.py and scraper.py.
"""

import time
import logging
from typing import Optional, Tuple

from playwright.sync_api import Playwright, Browser, BrowserContext, Page

from scripts.config import BROWSER_ARGS, USER_AGENT, VIEWPORT, EXTRA_HEADERS
from scripts.exceptions import InvalidDOMError
from app.utils.logger import get_logger, slog, log_diagnostic

logger = get_logger(__name__)

COMPONENT = "browser"

# Strings that indicate a Cloudflare challenge page
_CF_INDICATORS = [
    "just a moment",
    "checking your browser",
    "cloudflare",
    "ray id",
]


def create_browser_context(
    playwright: Playwright,
    *,
    headless: bool = True,
    proxy: Optional[dict] = None,
) -> Tuple[Browser, BrowserContext, Page]:
    """
    Launch browser and return (browser, context, page) with full stealth config.

    Args:
        playwright: Playwright instance from sync_playwright()
        headless: Run headless (default True)
        proxy: Optional proxy config dict for playwright

    Returns:
        Tuple of (browser, context, page) ready to navigate
    """
    browser = playwright.chromium.launch(
        headless=headless,
        args=BROWSER_ARGS,
        proxy=proxy,
    )
    context = browser.new_context(
        user_agent=USER_AGENT,
        viewport=VIEWPORT,
        extra_http_headers=EXTRA_HEADERS,
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
    )
    page = context.new_page()
    return browser, context, page


# ---------------------------------------------------------------------------
# Cloudflare challenge handling
# ---------------------------------------------------------------------------

def _is_cloudflare_challenge(page: Page) -> bool:
    """Check if the current page is a Cloudflare challenge."""
    try:
        title = page.title().lower()
        if any(ind in title for ind in _CF_INDICATORS[:2]):
            return True
        body_text = page.evaluate(
            "document.body?.innerText?.substring(0, 500)?.toLowerCase() || ''"
        )
        return any(ind in body_text for ind in _CF_INDICATORS)
    except Exception:
        return False


def wait_for_cloudflare(page: Page, timeout: int = 30, poll_interval: float = 2.0) -> bool:
    """
    Wait for a Cloudflare JS challenge to resolve.

    Returns True if resolved (or no challenge detected), False if timed out.
    """
    if not _is_cloudflare_challenge(page):
        return True

    slog(logger, "info", "Cloudflare challenge detected, waiting",
         component=COMPONENT, operation="cf_wait",
         page_title=page.title(), timeout=timeout)

    start = time.time()
    while time.time() - start < timeout:
        time.sleep(poll_interval)
        if not _is_cloudflare_challenge(page):
            elapsed = round(time.time() - start, 1)
            slog(logger, "info", "Cloudflare challenge resolved",
                 component=COMPONENT, operation="cf_resolved",
                 elapsed_seconds=elapsed, page_title=page.title())
            return True

    elapsed = round(time.time() - start, 1)
    log_diagnostic(logger, "Cloudflare challenge did not resolve",
        component=COMPONENT, operation="cf_timeout",
        hint="CF JS challenge stuck. Consider: playwright-stealth, updated UA, or residential proxy.",
        expected="Page title changes from 'Just a moment...' to content",
        actual=f'Title still "{page.title()}" after {elapsed}s',
        timeout=timeout)
    return False


def navigate_with_cf_wait(page: Page, url: str, timeout: int = 60000) -> None:
    """
    Navigate to URL and wait for Cloudflare to resolve.

    Raises InvalidDOMError if challenge does not clear.
    """
    page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    if not wait_for_cloudflare(page, timeout=30):
        raise InvalidDOMError(f"Cloudflare challenge did not resolve for {url}")
