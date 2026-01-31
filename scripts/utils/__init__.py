"""
Utils package - Funções utilitárias para o scraper
"""

from .browser import safe_eval, remove_ads
from .parsing import parse_value, normalize_name

__all__ = ['safe_eval', 'remove_ads', 'parse_value', 'normalize_name']
