#!/usr/bin/env python3
"""
scraper.py - Scraper flexível de estatísticas do Brasileirão

Extrai dados de partidas do site ogol.com.br e retorna JSON estruturado.
Campos não encontrados são retornados como null (flexibilidade).

Uso:
    python3 scripts/scraper.py "https://www.ogol.com.br/jogo/..."
    python3 scripts/scraper.py "https://www.ogol.com.br/jogo/..." > data/jogo.json
"""

import json
import os
import re
import sys
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout

# Configuração de logging com timestamp ISO
LOG_TIMESTAMP = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(f'logs/scraper_{LOG_TIMESTAMP}.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)


class OgolScraper:
    """Scraper flexível para ogol.com.br - extrai o máximo possível sem quebrar."""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.data: Dict[str, Any] = {}
    
    def _safe_eval(self, page: Page, js_code: str, default=None):
        """Executa JavaScript de forma segura, retornando default em caso de erro."""
        try:
            return page.evaluate(js_code)
        except Exception as e:
            logger.debug(f"JS eval error: {e}")
            return default
    
    def _remove_ads(self, page: Page):
        """Remove overlays e ads que interferem na extração."""
        self._safe_eval(page, """
            (() => {
                const selectors = [
                    '.up-floating', '.clever-core-ads', '[id*="google_ads"]',
                    '.modal-overlay', '[id*="Offerwall"]', 'iframe[title*="ad"]'
                ];
                selectors.forEach(sel => {
                    document.querySelectorAll(sel).forEach(el => el.remove());
                });
                document.querySelectorAll('div').forEach(div => {
                    const style = window.getComputedStyle(div);
                    if ((style.position === 'fixed' || style.position === 'absolute') && 
                        parseInt(style.zIndex) > 100 && div.offsetWidth > window.innerWidth * 0.5) {
                        div.remove();
                    }
                });
            })()
        """)
    
    def extract_match_info(self, page: Page) -> Dict[str, Any]:
        """Extrai informações básicas da partida de forma flexível."""
        info = {}
        
        # Times via JavaScript (mais robusto)
        teams = self._safe_eval(page, """
            (() => {
                const home = document.querySelector('.match-header-team.left .match-header-team-name a');
                const away = document.querySelector('.match-header-team.right .match-header-team-name a');
                if (home && away) return { home: home.textContent.trim(), away: away.textContent.trim() };
                
                // Fallback: links de equipa
                const teamLinks = Array.from(document.querySelectorAll('a[href*="/equipa/"]'));
                if (teamLinks.length >= 2) {
                    return { home: teamLinks[0].textContent.trim(), away: teamLinks[1].textContent.trim() };
                }
                return null;
            })()
        """)
        
        if teams:
            info['home_team'] = teams.get('home')
            info['away_team'] = teams.get('away')
        
        # Placar
        score = self._safe_eval(page, """
            (() => {
                const scoreEl = document.querySelector('.match-header-vs a');
                if (scoreEl) {
                    const match = scoreEl.textContent.match(/(\\d+)\\s*[-–]\\s*(\\d+)/);
                    if (match) return { home: parseInt(match[1]), away: parseInt(match[2]) };
                }
                return null;
            })()
        """)
        
        if score:
            info['home_score'] = score.get('home')
            info['away_score'] = score.get('away')
        
        # Rodada
        rodada = self._safe_eval(page, """
            (() => {
                const text = document.body.innerText;
                const match = text.match(/[Rr]odada\\s*(\\d+)/);
                return match ? parseInt(match[1]) : null;
            })()
        """)
        info['rodada'] = rodada
        
        # Data e hora
        info['data_hora'] = self._safe_eval(page, """
            document.querySelector('.dateauthor')?.textContent?.trim() || null
        """)
        
        # Estádio
        estadio = self._safe_eval(page, """
            document.querySelector('a[href*="/estadio/"]')?.textContent?.trim() || null
        """)
        if estadio:
            info['estadio'] = {'nome': estadio}
        
        # Árbitro (limpar texto extra)
        arbitro = self._safe_eval(page, """
            (() => {
                const el = document.querySelector('a[href*="/arbitro/"]');
                if (!el) return null;
                // Pegar apenas o texto do link, não dos filhos
                return el.innerText.replace(/\\s+/g, ' ').trim();
            })()
        """)
        if arbitro:
            info['arbitro'] = {'nome': arbitro}
        
        # Público
        publico = self._safe_eval(page, """
            (() => {
                const text = document.body.innerText;
                const match = text.match(/[Ll]otação[:\\s]*([\\d\\.\\s]+)/);
                return match ? parseInt(match[1].replace(/\\D/g, '')) : null;
            })()
        """)
        if publico:
            info['publico'] = publico
        
        return info
    
    def extract_statistics(self, page: Page) -> Dict[str, Dict[str, Any]]:
        """Extrai estatísticas incluindo xG de forma flexível."""
        
        result = self._safe_eval(page, """
            (() => {
                const stats = { home: {}, away: {} };
                const seen = new Set();
                
                // Mapear nomes EXATOS para campos
                const exactMapping = {
                    'gols esperados': 'xg',
                    'expected goals': 'xg',
                    'gols esperados no alvo': 'xgot',
                    'chutes': 'chutes',
                    'chutes a gol': 'chutes_gol',
                    'chutes bloqueados': 'chutes_bloqueados',
                    'chutes fora': 'chutes_fora',
                    'escanteios': 'escanteios',
                    'faltas': 'faltas',
                    'impedimentos': 'impedimentos',
                    'defesas': 'defesas_goleiro',
                    'posse de bola': 'posse',
                    'total passes': 'passes_total',
                    'passes certos': 'passes',
                    'total cortes': 'cortes',
                    'divididas ganhas': 'duelos_ganhos'
                };
                
                document.querySelectorAll('.graph-bar').forEach(bar => {
                    const titleEl = bar.querySelector('.bars-title');
                    const values = bar.querySelectorAll('.bar-header .num');
                    
                    if (titleEl && values.length >= 2) {
                        const name = titleEl.textContent.trim().toLowerCase();
                        
                        // Match EXATO (não subcategorias como "gols esperados de faltas")
                        const field = exactMapping[name];
                        
                        if (field && !seen.has(field)) {
                            seen.add(field);
                            stats.home[field] = values[0].textContent.trim();
                            stats.away[field] = values[values.length - 1].textContent.trim();
                        }
                    }
                });
                
                return stats;
            })()
        """, {'home': {}, 'away': {}})
        
        # Converter valores para números
        stats_home = {}
        stats_away = {}
        
        for field, val in result.get('home', {}).items():
            parsed = self._parse_value(val)
            if parsed is not None:
                stats_home[field] = parsed
                
        for field, val in result.get('away', {}).items():
            parsed = self._parse_value(val)
            if parsed is not None:
                stats_away[field] = parsed
        
        return {'stats_home': stats_home, 'stats_away': stats_away}
    
    def extract_events(self, page: Page) -> List[Dict[str, Any]]:
        """Extrai eventos (gols e cartões) de forma flexível."""
        events = []
        
        # Gols - buscar nos scorers do header
        goals = self._safe_eval(page, """
            (() => {
                const goals = [];
                const scorers = document.querySelector('.match-header-scorers');
                if (scorers) {
                    const text = scorers.innerText;
                    // Padrão: "Jogador 45'" ou "Jogador 45+2'"
                    const matches = text.matchAll(/([A-ZÀ-Úa-zà-ú]+(?:\\s+[A-ZÀ-Úa-zà-ú]+)*)\\s*(\\d+)'(?:\\+(\\d+))?/g);
                    for (const m of matches) {
                        goals.push({
                            tipo: 'gol',
                            jogador: m[1],
                            minuto: parseInt(m[2]),
                            minuto_adicional: m[3] ? parseInt(m[3]) : 0
                        });
                    }
                }
                return goals;
            })()
        """, [])
        
        events.extend(goals)
        
        # Cartões - buscar por ícones específicos do ogol
        cards = self._safe_eval(page, """
            (() => {
                const cards = [];
                const seen = new Set();
                
                // Buscar todos os ícones de cartão
                document.querySelectorAll('.zz-icn-yellow_card, .zz-icn-red_card').forEach(icon => {
                    const row = icon.closest('tr');
                    if (!row) return;
                    
                    const playerLink = row.querySelector('a[href*="/jogador/"]');
                    if (!playerLink) return;
                    
                    const playerName = playerLink.textContent.trim();
                    const tipo = icon.className.includes('yellow') ? 'cartao_amarelo' : 'cartao_vermelho';
                    
                    // Extrair minuto do título do ícone ou do texto da linha
                    const title = icon.getAttribute('title') || '';
                    let minuto = null;
                    
                    const titleMatch = title.match(/(\\d+)/);
                    if (titleMatch) {
                        minuto = parseInt(titleMatch[1]);
                    } else {
                        // Buscar no texto da linha
                        const rowText = row.innerText;
                        const minuteMatch = rowText.match(/(\\d+)'/);
                        if (minuteMatch) {
                            minuto = parseInt(minuteMatch[1]);
                        }
                    }
                    
                    // Evitar duplicatas
                    const key = `${playerName}-${tipo}-${minuto}`;
                    if (!seen.has(key)) {
                        seen.add(key);
                        cards.push({
                            tipo: tipo,
                            jogador: playerName,
                            minuto: minuto
                        });
                    }
                });
                
                return cards;
            })()
        """, [])
        
        events.extend(cards)
        events.sort(key=lambda x: x.get('minuto') or 0)
        
        return events
    
    def extract_lineups(self, page: Page) -> Dict[str, Dict[str, List]]:
        """Extrai escalações completas identificando times pelos headers."""
        
        result = self._safe_eval(page, """
            (() => {
                const lineups = {
                    home: { titulares: [], reservas: [], tecnico: null },
                    away: { titulares: [], reservas: [], tecnico: null }
                };
                
                // Encontrar os nomes dos times no header
                const homeTeamEl = document.querySelector('.match-header-team.left .match-header-team-name a');
                const awayTeamEl = document.querySelector('.match-header-team.right .match-header-team-name a');
                const homeTeam = homeTeamEl?.textContent?.trim()?.toUpperCase() || '';
                const awayTeam = awayTeamEl?.textContent?.trim()?.toUpperCase() || '';
                
                // Encontrar módulos de escalação por nome do time
                const modules = document.querySelectorAll('.zz-module');
                
                modules.forEach(module => {
                    const title = module.querySelector('.zz-module-title')?.textContent?.toUpperCase() || '';
                    const players = [];
                    let isHome = null;
                    
                    // Determinar se é time casa ou fora
                    if (homeTeam && title.includes(homeTeam.substring(0, 8))) {
                        isHome = true;
                    } else if (awayTeam && title.includes(awayTeam.substring(0, 8))) {
                        isHome = false;
                    } else if (title.includes('ATLÉTICO') || title.includes('ATLETICO')) {
                        // Fallback para times conhecidos
                        isHome = homeTeam.includes('ATLÉTICO') || homeTeam.includes('ATLETICO');
                        if (!isHome) isHome = !awayTeam.includes('ATLÉTICO');
                    }
                    
                    if (isHome === null) return;
                    
                    // Extrair jogadores
                    module.querySelectorAll('tr, .zz-player-row').forEach(row => {
                        const playerLink = row.querySelector('a[href*="/jogador/"]');
                        if (!playerLink) return;
                        
                        const name = playerLink.textContent.trim();
                        if (!name) return;
                        
                        // Número da camisa
                        const firstCell = row.querySelector('td:first-child');
                        let number = null;
                        if (firstCell) {
                            const numMatch = firstCell.textContent.match(/^\\s*(\\d+)\\s*$/);
                            if (numMatch) number = parseInt(numMatch[1]);
                        }
                        
                        // Evitar duplicatas
                        if (!players.find(p => p.nome === name)) {
                            players.push({ nome: name, numero: number });
                        }
                    });
                    
                    // Técnico
                    const coachLink = module.querySelector('a[href*="/treinador/"]');
                    const coach = coachLink?.textContent?.trim();
                    
                    // Atribuir ao time
                    if (players.length > 0) {
                        const target = isHome ? lineups.home : lineups.away;
                        if (target.titulares.length === 0) {
                            target.titulares = players.slice(0, 11);
                            target.reservas = players.slice(11);
                            if (coach) target.tecnico = coach;
                        }
                    }
                });
                
                // Fallback: pegar das tabelas se módulos não funcionaram
                if (lineups.home.titulares.length === 0 || lineups.away.titulares.length === 0) {
                    const tables = document.querySelectorAll('table.zztable.game_matchups');
                    tables.forEach((table, idx) => {
                        const players = [];
                        table.querySelectorAll('tr').forEach(row => {
                            const playerLink = row.querySelector('a[href*="/jogador/"]');
                            if (!playerLink) return;
                            
                            const name = playerLink.textContent.trim();
                            const firstCell = row.querySelector('td:first-child');
                            let number = null;
                            if (firstCell) {
                                const numMatch = firstCell.textContent.match(/^\\s*(\\d+)\\s*$/);
                                if (numMatch) number = parseInt(numMatch[1]);
                            }
                            
                            if (!players.find(p => p.nome === name)) {
                                players.push({ nome: name, numero: number });
                            }
                        });
                        
                        if (players.length >= 5) {
                            const target = idx === 0 ? lineups.home : lineups.away;
                            if (target.titulares.length === 0) {
                                target.titulares = players.slice(0, 11);
                                target.reservas = players.slice(11);
                            }
                        }
                    });
                }
                
                return lineups;
            })()
        """, {'home': {'titulares': [], 'reservas': []}, 'away': {'titulares': [], 'reservas': []}})
        
        return {
            'escalacao_casa': {
                'titulares': result.get('home', {}).get('titulares', []),
                'reservas': result.get('home', {}).get('reservas', []),
                'tecnico': result.get('home', {}).get('tecnico')
            },
            'escalacao_fora': {
                'titulares': result.get('away', {}).get('titulares', []),
                'reservas': result.get('away', {}).get('reservas', []),
                'tecnico': result.get('away', {}).get('tecnico')
            }
        }
    
    def _parse_value(self, text, field_name='') -> Optional[float]:
        """Converte texto para valor numérico de forma flexível."""
        if text is None:
            return None
            
        if isinstance(text, (int, float)):
            return text
            
        text = str(text).strip()
        
        # Remover % 
        has_percent = '%' in text
        text_clean = text.replace('%', '').strip()
        
        # Se tem vírgula como decimal (padrão BR)
        if ',' in text_clean and '.' not in text_clean:
            text_clean = text_clean.replace(',', '.')
        
        try:
            # Se é claramente decimal (xG, por exemplo)
            if '.' in text_clean:
                return float(text_clean)
            # Inteiro
            return int(text_clean)
        except ValueError:
            # Fallback: extrair primeiro número
            match = re.search(r'(\d+)', text)
            if match:
                return int(match.group(1))
        
        return None
    
    def scrape(self, url: str) -> Dict[str, Any]:
        """Executa o scraping completo de forma flexível."""
        logger.info(f"Iniciando scraping: {url}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1280, 'height': 900}
            )
            page = context.new_page()
            
            try:
                # Carregar página e aguardar conteúdo inicial
                page.goto(url, wait_until='domcontentloaded', timeout=60000)
                page.wait_for_timeout(3000)  # Mais tempo para JS inicial
                
                self._remove_ads(page)
                
                # Scroll agressivo para forçar lazy loading
                for scroll in [500, 1000, 2000, 3000, 4000]:
                    page.evaluate(f'window.scrollTo(0, {scroll})')
                    page.wait_for_timeout(800)
                    self._remove_ads(page)
                
                # Voltar ao topo e esperar estabilizar
                page.evaluate('window.scrollTo(0, 0)')
                page.wait_for_timeout(1000)
                
                # Tentar esperar por elementos específicos (flexível)
                try:
                    page.wait_for_selector('.graph-bar', timeout=5000)
                except:
                    pass
                
                # Extrair dados em ordem de prioridade
                # 1. Info básica (sempre funciona)
                self.data = self.extract_match_info(page)
                self.data['url_fonte'] = url
                
                # 2. Estatísticas (funcionam bem)
                stats = self.extract_statistics(page)
                self.data.update(stats)
                
                # 3. Scroll para seção de escalações e eventos
                page.evaluate('window.scrollTo(0, 2500)')
                page.wait_for_timeout(1500)
                self._remove_ads(page)
                
                # 4. Eventos (gols + cartões)
                events = self.extract_events(page)
                if events:
                    self.data['eventos'] = events
                
                # 5. Escalações
                lineups = self.extract_lineups(page)
                self.data.update(lineups)
                
                logger.info(f"Scraping concluído: {self.data.get('home_team', '?')} x {self.data.get('away_team', '?')}")
                
            except PlaywrightTimeout as e:
                logger.error(f"Timeout ao acessar {url}: {e}")
                
            except Exception as e:
                logger.error(f"Erro no scraping: {e}")
                
            finally:
                browser.close()
        
        return self.data


def main():
    """Ponto de entrada principal."""
    if len(sys.argv) < 2:
        print("Uso: python3 scraper.py <URL>", file=sys.stderr)
        print("Exemplo: python3 scraper.py 'https://www.ogol.com.br/jogo/...'", file=sys.stderr)
        sys.exit(1)
    
    url = sys.argv[1]
    headless = '--no-headless' not in sys.argv
    
    scraper = OgolScraper(headless=headless)
    data = scraper.scrape(url)
    
    # Validação mínima flexível
    if not data.get('home_team') or not data.get('away_team'):
        logger.error("Não foi possível extrair informações básicas da partida")
        sys.exit(1)
    
    # Output JSON
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
