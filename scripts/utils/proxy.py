import os
import random
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class ProxyManager:
    """
    Manages a list of proxies for rotation.
    Proxies are loaded from the PROXY_LIST environment variable (comma-separated).
    Format: scheme://username:password@ip:port or scheme://ip:port
    """

    def __init__(self):
        self.proxies: List[str] = self._load_proxies()
        self.current_index = 0

    def _load_proxies(self) -> List[str]:
        """Loads proxies from environment variable."""
        proxy_str = os.getenv("PROXY_LIST", "")
        if not proxy_str:
            logger.warning("No proxies found in PROXY_LIST environment variable. Using direct connection.")
            return []
        
        proxies = [p.strip() for p in proxy_str.split(",") if p.strip()]
        logger.info(f"Loaded {len(proxies)} proxies.")
        return proxies

    def get_proxy(self) -> Optional[Dict[str, str]]:
        """
        Returns a proxy configuration dictionary for Playwright.
        Rotates simply by random choice for now, or round-robin if needed.
        """
        if not self.proxies:
            return None

        # Random rotation strategy
        proxy_url = random.choice(self.proxies)
        
        # Playwright expects a dictionary with 'server' key.
        # Credentials should be embedded in the URL or separated.
        # Playwright format: {'server': 'http://myproxy.com:3128', 'username': 'user', 'password': 'pass'}
        
        # Basic parsing for scheme://user:pass@host:port vs scheme://host:port
        # Note: Playwright's 'server' argument accepts the full URL including auth 
        # for many proxy types, but splitting is safer if detailed config is needed.
        # For simplicity, we pass the full URL string to 'server' which Playwright supports.
        
        logger.info(f"Using proxy: {self._mask_proxy(proxy_url)}")
        return {"server": proxy_url}

    def _mask_proxy(self, proxy_err: str) -> str:
        """Masks credentials in proxy string for logging."""
        if "@" in proxy_err:
            scheme_part, rest = proxy_err.split("://", 1)
            creds, address = rest.split("@", 1)
            return f"{scheme_part}://*****:*****@{address}"
        return proxy_err
