"""
cloudflare.py - Utility to handle Cloudflare JS challenges.

Detects and waits for Cloudflare's "Just a moment..." challenge to resolve
before proceeding with page scraping.
"""

import time
import logging
from playwright.sync_api import Page

from app.utils.logger import get_logger, slog, log_diagnostic

logger = get_logger(__name__)

COMPONENT = "cloudflare"

# Strings that indicate a Cloudflare challenge page
CF_INDICATORS = [
    "just a moment",
    "checking your browser",
    "cloudflare",
    "ray id",
]


def is_cloudflare_challenge(page: Page) -> bool:
    """Check if the current page is a Cloudflare challenge."""
    try:
        title = page.title().lower()
        if any(indicator in title for indicator in CF_INDICATORS[:2]):
            return True
        # Also check body text for edge cases
        body_text = page.evaluate("document.body?.innerText?.substring(0, 500)?.toLowerCase() || ''")
        if any(indicator in body_text for indicator in CF_INDICATORS):
            return True
    except Exception:
        pass
    return False


def wait_for_cloudflare(page: Page, timeout: int = 30, poll_interval: float = 2.0) -> bool:
    """
    Wait for a Cloudflare JS challenge to resolve.
    
    Args:
        page: Playwright Page object
        timeout: Maximum seconds to wait for challenge resolution
        poll_interval: Seconds between checks
        
    Returns:
        True if challenge resolved (or no challenge detected), False if timed out
    """
    if not is_cloudflare_challenge(page):
        return True
    
    slog(logger, 'info', 'Cloudflare challenge detected, waiting for resolution',
         component=COMPONENT, operation='cf_wait',
         page_title=page.title(),
         timeout=timeout)
    
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(poll_interval)
        
        if not is_cloudflare_challenge(page):
            elapsed = round(time.time() - start, 1)
            slog(logger, 'info', 'Cloudflare challenge resolved',
                 component=COMPONENT, operation='cf_resolved',
                 elapsed_seconds=elapsed,
                 page_title=page.title())
            return True
    
    # Timed out
    elapsed = round(time.time() - start, 1)
    log_diagnostic(logger, 'Cloudflare challenge did not resolve',
        component=COMPONENT, operation='cf_timeout',
        hint='The Cloudflare JS challenge did not clear within the timeout. Playwright on Render may be fingerprinted as a bot. Consider: (1) updating Chrome version in user-agent, (2) using playwright-stealth, (3) adding a residential proxy.',
        expected='Page title changes from "Just a moment..." to actual content',
        actual=f'Title still "{page.title()}" after {elapsed}s',
        timeout=timeout)
    return False
