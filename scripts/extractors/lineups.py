"""
lineups.py - Extrai escalações das equipes
"""

import logging
from typing import Any, Dict, List, Optional
from playwright.sync_api import Page

from ..utils.browser import safe_eval

logger = logging.getLogger(__name__)


def extract_lineups(page: Page) -> Dict[str, Dict[str, Any]]:
    """
    Extrai escalações usando .zz-container como fonte primária.
    
    Prioridade:
    1. .zz-container > #game_report
    2. .zz-module.game_matchup
    3. Lista linear de jogadores
    
    O layout visual é confiável:
    - Esquerda (.left, primeira coluna) = Home (mandante)
    - Direita (.right, segunda coluna) = Away (visitante)
    
    Args:
        page: Página do Playwright com o jogo carregado
        
    Returns:
        Dicionário com escalacao_casa e escalacao_fora
    """
    result = safe_eval(page, '''
        (() => {
            const result = { 
                home: { starters: [], bench: [], coach: null, teamName: null }, 
                away: { starters: [], bench: [], coach: null, teamName: null } 
            };
            
            const parsePlayer = (el, numberEl = null) => ({
                nome: el.textContent.trim(),
                numero: numberEl ? parseInt(numberEl.textContent.trim()) || null : null
            });
            
            // PRIORIDADE 1: .zz-container > #game_report
            const zzContainer = document.querySelector('.zz-container');
            if (zzContainer) {
                const gameReport = zzContainer.querySelector('#game_report');
                if (gameReport) {
                    const cols = gameReport.querySelectorAll('.zz-tpl-col');
                    const sides = ['home', 'away'];
                    
                    cols.forEach((col, idx) => {
                        if (idx >= 2) return;
                        const side = sides[idx];
                        
                        // Nome do time (subtitle)
                        const subtitle = col.querySelector('.subtitle');
                        if (subtitle) result[side].teamName = subtitle.textContent.trim();
                        
                        // Jogadores - procurar links de jogador
                        col.querySelectorAll('.player').forEach(playerDiv => {
                            const nameEl = playerDiv.querySelector('a[href*="/jogador/"]');
                            const numEl = playerDiv.querySelector('.number');
                            
                            if (nameEl) {
                                result[side].starters.push(parsePlayer(nameEl, numEl));
                            }
                        });
                        
                        // Técnico
                        const coachEl = col.querySelector('a[href*="/treinador/"]');
                        if (coachEl) result[side].coach = coachEl.textContent.trim();
                    });
                }
            }
            
            // PRIORIDADE 2: Fallback .zz-module.game_matchup
            if (result.home.starters.length === 0) {
                const container = document.querySelector(".zz-module.game_matchup");
                if (container) {
                    ['home', 'away'].forEach(side => {
                        const sideDiv = container.querySelector('.' + side);
                        if (sideDiv) {
                            sideDiv.querySelectorAll('.lineup .player .name a').forEach(a => 
                                result[side].starters.push(parsePlayer(a, a.closest('.player')?.querySelector('.number'))));
                            sideDiv.querySelectorAll('.bench .player .name a').forEach(a => 
                                result[side].bench.push(parsePlayer(a, a.closest('.player')?.querySelector('.number'))));
                            const c = sideDiv.querySelector('a[href*="/treinador/"]');
                            if (c) result[side].coach = c.textContent.trim();
                        }
                    });
                }
            }
            
            // PRIORIDADE 3: Fallback Linear (Home -> Away)
            if (result.home.starters.length === 0) {
                const allPlayers = [];
                document.querySelectorAll('.player').forEach(p => {
                    const nameEl = p.querySelector('a[href*="/jogador/"]');
                    const numEl = p.querySelector('.number');
                    if (nameEl && numEl && !isNaN(parseInt(numEl.textContent))) {
                         allPlayers.push(parsePlayer(nameEl, numEl));
                    }
                });

                const uniquePlayers = [];
                const seen = new Set();
                allPlayers.forEach(p => {
                    const key = `${p.nome}-${p.numero}`;
                    if (!seen.has(key)) { seen.add(key); uniquePlayers.push(p); }
                });
                
                if (uniquePlayers.length >= 22) {
                    result.home.starters = uniquePlayers.slice(0, 11);
                    result.away.starters = uniquePlayers.slice(11, 22);
                    const bench = uniquePlayers.slice(22);
                    const mid = Math.ceil(bench.length / 2);
                    result.home.bench = bench.slice(0, mid);
                    result.away.bench = bench.slice(mid);
                }
            }
            
            // Técnicos (fallback final)
            if (!result.home.coach) {
                const coaches = document.querySelectorAll('a[href*="/treinador/"]');
                const c = Array.from(coaches).map(i => i.textContent.trim());
                const u = [...new Set(c)];
                if (u.length >= 1) result.home.coach = u[0];
                if (u.length >= 2) result.away.coach = u[1];
            }
            
            return result;
        })()
    ''', {'home': {'starters': [], 'bench': []}, 'away': {'starters': [], 'bench': []}})

    return {
        'escalacao_casa': {
            'titulares': result.get('home', {}).get('starters', []),
            'reservas': result.get('home', {}).get('bench', []),
            'tecnico': result.get('home', {}).get('coach'),
            'time': result.get('home', {}).get('teamName')
        },
        'escalacao_fora': {
            'titulares': result.get('away', {}).get('starters', []),
            'reservas': result.get('away', {}).get('bench', []),
            'tecnico': result.get('away', {}).get('coach'),
            'time': result.get('away', {}).get('teamName')
        }
    }
