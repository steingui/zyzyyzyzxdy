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
    "um momento",
    "verificando",
    "attention required",
    "security check",
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
    
    # Randomize viewport slightly to avoid fingerprinting
    import random
    width = VIEWPORT['width'] + random.randint(-50, 50)
    height = VIEWPORT['height'] + random.randint(-50, 50)
    
    context = browser.new_context(
        user_agent=USER_AGENT,
        viewport={'width': width, 'height': height},
        extra_http_headers=EXTRA_HEADERS,
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
        permissions=['geolocation'],
    )
    
    # Try to apply stealth
    try:
        from playwright_stealth import stealth_sync
        page = context.new_page()
        stealth_sync(page)
        logger.info("Playwright-Stealth applied successfully")
    except ImportError:
        logger.warning("playwright-stealth not installed, running without it")
        page = context.new_page()

    return browser, context, page


# ---------------------------------------------------------------------------
# Cloudflare challenge handling
# ---------------------------------------------------------------------------

def _is_cloudflare_challenge(page: Page) -> bool:
    """Check if the current page is a Cloudflare challenge."""
    try:
        # If page is closed/crashed, this might raise
        title = page.title().lower()
        
        # Check all indicators against title
        for ind in _CF_INDICATORS:
            if ind in title:
                logger.debug(f"CF Challenge detected by title: '{title}' (indicator: '{ind}')")
                return True
        
        # Check body text - if this fails (e.g. context destroyed), we should probably 
        # assume we are still loading/transitioning, hence NOT strictly "resolved" yet.
        # But for this boolean check, if we can't read body, we can't confirm challenge.
        # Let's rely on title mostly.
        
        body_text = page.evaluate(
            "document.body?.innerText?.substring(0, 500)?.toLowerCase() || ''"
        )
        
        for ind in _CF_INDICATORS:
            if ind in body_text:
                logger.debug(f"CF Challenge detected by body text: '{ind}' found in first 500 chars.")
                return True
                
        return False
    except Exception as e:
        # If we can't interact with the page, assume it's unstable/loading.
        # We should NOT return False (== Resolved) because that breaks the wait loop.
        # We'll log and return True to keep waiting.
        logger.debug(f"Error checking CF state: {e}")
        return True


def simulate_human_side_effects(page: Page):
    """Perform random mouse movements, scrolls, and clicks to look human."""
    import random
    try:
        # Random mouse move
        x = random.randint(100, 800)
        y = random.randint(100, 600)
        logger.debug(f"Human Sim: Moving mouse to ({x}, {y})")
        page.mouse.move(x, y, steps=10)
        
        # Occasional scroll
        if random.random() < 0.4:
            dy = random.randint(100, 500)
            logger.debug(f"Human Sim: Scrolling by {dy}")
            page.mouse.wheel(0, dy)
        
        # Random small pauses
        if random.random() < 0.1:
            delay = random.uniform(0.1, 0.5)
            logger.debug(f"Human Sim: Pausing for {delay:.2f}s")
            time.sleep(delay)
            
    except Exception as e:
        logger.debug(f"Human Sim Error: {e}")


def attempt_click_cf_checkbox(page: Page):
    """
    Aggressively search for and click the Cloudflare/Turnstile 'Verify' checkbox.
    Checks main page, iframes, and shadow roots.
    """
    try:
        # Common selectors for the checkbox
        selectors = [
            "input[type='checkbox']",
            ".ctp-checkbox-label",
            "#turnstile-wrapper iframe",
            "iframe[src*='cloudflare']",
            "iframe[src*='turnstile']",
            ".big-button",
            "div.cb-b", # sometimes used
            "#challenge-stage input"
        ]
        
        frames = page.frames
        logger.debug(f"Active Solver: Checking {len(frames)} frames for CF/Turnstile widgets...")

        # 1. Check main page
        for sel in selectors:
            try:
                # If it's an iframe, we might need to verify inside it
                if "iframe" in sel:
                    for i, frame in enumerate(frames):
                        if "cloudflare" in frame.url or "turnstile" in frame.url:
                            logger.debug(f"Active Solver: Found potential CF frame [{i}]: {frame.url}")
                            # Try clicking body or checkbox inside frame
                            try:
                                checkbox = frame.locator("input[type='checkbox']").first
                                if checkbox.is_visible():
                                    logger.info(f"Clicking CF checkbox in iframe: {frame.url}")
                                    checkbox.click()
                                    return
                                
                                # Sometimes just clicking the body of the challenge frame works
                                logger.debug(f"Active Solver: Clicking body of CF frame [{i}]")
                                frame.locator("body").click(timeout=500)
                                return
                            except Exception as frame_err:
                                logger.debug(f"Active Solver: Failed interaction in frame [{i}]: {frame_err}")
                else:
                    # Regular element on main page
                    # logger.debug(f"Active Solver: Checking selector '{sel}' on main page...")
                    element = page.locator(sel).first
                    if element.is_visible():
                        logger.info(f"Active Solver: Clicking found element '{sel}'")
                        element.click()
                        return
            except:
                continue

    except Exception as e:
        logger.debug(f"Error trying to click CF checkbox: {e}")


def wait_for_cloudflare(page: Page, timeout: int = 30, poll_interval: float = 2.0) -> bool:
    """
    Wait for a Cloudflare JS challenge to resolve.

    Returns True if resolved (or no challenge detected), False if timed out.
    """
    # Initial check
    if not _is_cloudflare_challenge(page):
        return True

    slog(logger, "info", "Cloudflare challenge detected, waiting",
         component=COMPONENT, operation="cf_wait",
         page_title=page.title(), timeout=timeout)

    start = time.time()
    while time.time() - start < timeout:
        
        # ACT LIKE A HUMAN while waiting
        simulate_human_side_effects(page)
        
        # ACTIVELY TRY TO SOLVE IT
        attempt_click_cf_checkbox(page)
        
        time.sleep(poll_interval)
        
        # Debug log for waiting
        elapsed = round(time.time() - start, 1)
        if int(elapsed) % 5 == 0:
             logger.debug(f"Waiting for CF... ({elapsed}s/{timeout}s) - Title: {page.title()}")

        # If is_cloudflare_challenge returns False, it means we are CLEAR.
        if not _is_cloudflare_challenge(page):
            # Double check to ensure we didn't just hit a transient error state
            # (though _is_cloudflare_challenge now returns True on error)
            
            # Dismiss "AVANÇAR" / Ads modal if present (seen in production/debug)
            try:
                # Naive click on typical ad overlay buttons if they exist
                page.evaluate("""(() => {
                    const buttons = Array.from(document.querySelectorAll('button, a, div'));
                    const avanzar = buttons.find(b => b.innerText && b.innerText.includes('AVANÇAR'));
                    if (avanzar) {
                         console.log("Clicking AVANÇAR button");
                         avanzar.click();
                    }
                })()""")
            except:
                pass

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
    # Increased timeout for production (Render can be slow)
    if not wait_for_cloudflare(page, timeout=60):
        # Final check: maybe it resolved but page title is weird?
        # If we have the fixture table, we are good.
        if page.locator("#fixture_games").count() > 0:
            return
        raise InvalidDOMError(f"Cloudflare challenge did not resolve for {url}")
