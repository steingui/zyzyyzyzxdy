"""
match_info.py - Extrai informações básicas da partida
"""

import logging
from typing import Any, Dict
from playwright.sync_api import Page

from ..utils.browser import safe_eval

logger = logging.getLogger(__name__)


def extract_match_info(page: Page) -> Dict[str, Any]:
    """
    Extrai informações básicas da partida usando o layout visual do site.
    
    O site SEMPRE exibe o mandante à esquerda e visitante à direita.
    Prioridade: escalações (#game_report) > match-header > links de equipa
    
    Args:
        page: Página do Playwright com o jogo carregado
        
    Returns:
        Dicionário com home_team, away_team, placar, rodada, etc.
    """
    info: Dict[str, Any] = {}
    
    # Extrair times
    teams = safe_eval(page, '''
        (() => {
            // 1. PRIORIDADE: Usar .zz-container #game_report (escalações)
            const gameReport = document.querySelector('.zz-container #game_report');
            if (gameReport) {
                const cols = gameReport.querySelectorAll('.zz-tpl-col');
                if (cols.length >= 2) {
                    const homeTeam = cols[0].querySelector('.subtitle');
                    const awayTeam = cols[1].querySelector('.subtitle');
                    if (homeTeam && awayTeam) {
                        return {
                            home: homeTeam.textContent.trim(),
                            away: awayTeam.textContent.trim(),
                            source: 'game-report'
                        };
                    }
                }
            }
            
            // 2. Fallback: seletores do match header
            const leftTeam = document.querySelector('.match-header-team.left .match-header-team-name a');
            const rightTeam = document.querySelector('.match-header-team.right .match-header-team-name a');
            if (leftTeam && rightTeam) {
                return { 
                    home: leftTeam.textContent.trim(), 
                    away: rightTeam.textContent.trim(),
                    source: 'match-header'
                };
            }
            
            // 3. Fallback: Links de equipa ordenados por posição no DOM
            const container = document.querySelector('.zz-container, .match-header');
            if (container) {
                const teamLinks = container.querySelectorAll('a[href*="/equipa/"]');
                const uniqueTeams = [...new Set(Array.from(teamLinks).map(a => a.textContent.trim()))];
                if (uniqueTeams.length >= 2) {
                    return {
                        home: uniqueTeams[0],
                        away: uniqueTeams[1],
                        source: 'team-links'
                    };
                }
            }
            
            return null;
        })()
    ''')
    
    if teams:
        info['home_team'] = teams.get('home')
        info['away_team'] = teams.get('away')
        info['_teams_source'] = teams.get('source')
    
    # Extrair placar
    score = safe_eval(page, r'''
        (() => {
            const scoreEl = document.querySelector('.match-header-vs a');
            if (scoreEl) {
                const match = scoreEl.textContent.match(/(\d+)\s*[-–]\s*(\d+)/);
                if (match) return { home: parseInt(match[1]), away: parseInt(match[2]) };
            }
            return null;
        })()
    ''')
    
    if score:
        info['home_score'] = score.get('home')
        info['away_score'] = score.get('away')
    
    # Extrair rodada
    rodada = safe_eval(page, r'''
        (() => {
            const text = document.body.innerText;
            const match = text.match(/[Rr]odada\s*(\d+)/);
            return match ? parseInt(match[1]) : null;
        })()
    ''')
    info['rodada'] = rodada
    
    # Data e hora
    info['data_hora'] = safe_eval(page, '''
        document.querySelector('.dateauthor')?.textContent?.trim() || null
    ''')
    
    # Estádio
    estadio = safe_eval(page, '''
        document.querySelector('a[href*="/estadio/"]')?.textContent?.trim() || null
    ''')
    if estadio:
        info['estadio'] = {'nome': estadio}
    
    # Árbitro
    arbitro = safe_eval(page, r'''
        (() => {
            const el = document.querySelector('a[href*="/arbitro/"]');
            if (!el) return null;
            return el.innerText.replace(/\s+/g, ' ').trim();
        })()
    ''')
    if arbitro:
        info['arbitro'] = {'nome': arbitro}
    
    # Público
    publico = safe_eval(page, r'''
        (() => {
            const text = document.body.innerText;
            const match = text.match(/[Ll]otação[:\s]*([\d\.\s]+)/);
            return match ? parseInt(match[1].replace(/\D/g, '')) : null;
        })()
    ''')
    if publico:
        info['publico'] = publico
    
    return info
