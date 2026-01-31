"""
events.py - Extrai eventos da partida (gols, cartões)
"""

import logging
from typing import Any, Dict, List
from playwright.sync_api import Page

from ..utils.browser import safe_eval

logger = logging.getLogger(__name__)


def extract_events(page: Page) -> List[Dict[str, Any]]:
    """
    Extrai eventos (gols e cartões) e identifica o time.
    
    Args:
        page: Página do Playwright com o jogo carregado
        
    Returns:
        Lista de dicionários com os eventos
    """
    events: List[Dict[str, Any]] = []
    
    # Gols - identificar time mandante (left) e visitante (right)
    goals = safe_eval(page, r'''
        (() => {
            const goals = [];
            
            const processScorers = (selector, side) => {
                const container = document.querySelector(selector);
                if (container) {
                    const text = container.innerText;
                    const matches = text.matchAll(/([A-ZÀ-Úa-zà-ú]+(?:\s+[A-ZÀ-Úa-zà-ú]+)*)\s*(\d+)'(?:\+(\d+))?/g);
                    for (const m of matches) {
                        goals.push({
                            tipo: 'gol',
                            jogador: m[1],
                            minuto: parseInt(m[2]),
                            minuto_adicional: m[3] ? parseInt(m[3]) : 0,
                            time: side
                        });
                    }
                }
            };
            
            processScorers('.match-header-scorers.left', 'home');
            processScorers('.match-header-scorers.right', 'away');
            
            return goals;
        })()
    ''', [])
    
    events.extend(goals)
    
    # Cartões
    cards = safe_eval(page, r'''
        (() => {
            const cards = [];
            const processCards = (type) => {
                document.querySelectorAll(`.${type}`).forEach(card => {
                    const playerEl = card.closest('.player')?.querySelector('a[href*="/jogador/"]');
                    const minuteMatch = card.closest('.event, .player')?.textContent?.match(/(\d+)'/);
                    if (playerEl) {
                        cards.push({
                            tipo: type === 'yellow-card' ? 'cartao_amarelo' : 'cartao_vermelho',
                            jogador: playerEl.textContent.trim(),
                            minuto: minuteMatch ? parseInt(minuteMatch[1]) : null
                        });
                    }
                });
            };
            processCards('yellow-card');
            processCards('red-card');
            return cards;
        })()
    ''', [])
    
    events.extend(cards)
    
    return events
