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
        """Extrai informações básicas da partida usando o layout visual do site."""
        info = {}
        
        # FONTE PRINCIPAL: Layout visual do site
        # O site SEMPRE exibe o mandante à esquerda e visitante à direita
        teams = self._safe_eval(page, """
            (() => {
                // 1. PRIORIDADE: Usar .zz-container #game_report (escalações)
                // Este é o mais confiável pois mostra os nomes exatamente como na seção de escalações
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
        """)
        
        if teams:
            info['home_team'] = teams.get('home')
            info['away_team'] = teams.get('away')
            info['_teams_source'] = teams.get('source')  # Para debug
        
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
        
        # Estádio (útil para validar mando)
        estadio = self._safe_eval(page, """
            document.querySelector('a[href*=\"/estadio/\"]')?.textContent?.trim() || null
        """)
        if estadio:
            info['estadio'] = {'nome': estadio}
        
        # Árbitro (limpar texto extra)
        arbitro = self._safe_eval(page, """
            (() => {
                const el = document.querySelector('a[href*=\"/arbitro/\"]');
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
        """Extrai estatísticas usando .zz-container como fonte primária."""
        
        result = self._safe_eval(page, """
            (() => {
                const stats = { home: {}, away: {} };
                const seen = new Set();
                
                // Mapear nomes para campos normalizados
                const fieldMapping = {
                    'posse de bola': 'posse',
                    'chutes': 'chutes',
                    'chutes (a gol)': 'chutes',
                    'escanteios': 'escanteios',
                    'gols esperados': 'xg',
                    'expected goals': 'xg',
                    'gols esperados no alvo': 'xgot',
                    'chutes a gol': 'chutes_gol',
                    'chutes bloqueados': 'chutes_bloqueados',
                    'chutes fora': 'chutes_fora',
                    'faltas': 'faltas',
                    'impedimentos': 'impedimentos',
                    'defesas': 'defesas_goleiro',
                    'total passes': 'passes_total',
                    'passes certos': 'passes',
                    'total cortes': 'cortes',
                    'divididas ganhas': 'duelos_ganhos'
                };
                
                // PRIORIDADE 1: Tabela inline dentro de .zz-container
                const container = document.querySelector('.zz-container');
                if (container) {
                    const table = container.querySelector('table');
                    if (table) {
                        const rows = table.querySelectorAll('tr');
                        if (rows.length >= 2) {
                            const headerCells = rows[0].querySelectorAll('td, th');
                            const valueCells = rows[1].querySelectorAll('td, th');
                            
                            headerCells.forEach((cell, idx) => {
                                const label = cell.textContent.trim().toLowerCase();
                                const field = fieldMapping[label];
                                
                                if (field && !seen.has(field) && valueCells[idx]) {
                                    seen.add(field);
                                    // Valor formato: "41% [bolinha] 59%" ou "(4) 10 [bolinha] 15 (5)"
                                    const valueText = valueCells[idx].textContent.trim();
                                    
                                    // Regex para extrair números/percentuais separados
                                    // Formato: valor_home ... valor_away
                                    const parts = valueText.split(/[●○]|\\s{2,}/).map(s => s.trim()).filter(s => s);
                                    
                                    if (parts.length >= 2) {
                                        stats.home[field] = parts[0];
                                        stats.away[field] = parts[parts.length - 1];
                                    } else {
                                        // Fallback: usar regex para números
                                        const nums = valueText.match(/[\d.,]+%?/g);
                                        if (nums && nums.length >= 2) {
                                            stats.home[field] = nums[0];
                                            stats.away[field] = nums[nums.length - 1];
                                        }
                                    }
                                }
                            });
                        }
                    }
                }
                
                // PRIORIDADE 2: Fallback para .graph-bar (layout antigo)
                if (Object.keys(stats.home).length === 0) {
                    document.querySelectorAll('.graph-bar').forEach(bar => {
                        const titleEl = bar.querySelector('.bars-title');
                        const values = bar.querySelectorAll('.bar-header .num');
                        
                        if (titleEl && values.length >= 2) {
                            const name = titleEl.textContent.trim().toLowerCase();
                            const field = fieldMapping[name];
                            
                            if (field && !seen.has(field)) {
                                seen.add(field);
                                stats.home[field] = values[0].textContent.trim();
                                stats.away[field] = values[values.length - 1].textContent.trim();
                            }
                        }
                    });
                }
                
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
        """Extrai eventos e identifica o time se possível."""
        events = []
        
        # Gols - identificar time mandante (left) e visitante (right)
        goals = self._safe_eval(page, """
            (() => {
                const goals = [];
                
                const processScorers = (selector, side) => {
                    const container = document.querySelector(selector);
                    if (container) {
                        const text = container.innerText;
                        const matches = text.matchAll(/([A-ZÀ-Úa-zà-ú]+(?:\\s+[A-ZÀ-Úa-zà-ú]+)*)\\s*(\\d+)'(?:\\+(\\d+))?/g);
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
        """, [])
        
        events.extend(goals)
        
        # Cartões (mantido lógica anterior, adicionando time se trivial)
        # ... (código de cartões permanece, mas simplificado para o exemplo, mantendo o existente se não editar essa parte)
        # Vou reinscrever a parte de cartões para manter integridade
        
        cards = self._safe_eval(page, """
             (() => {
                const cards = [];
                const seen = new Set();
                document.querySelectorAll('.zz-icn-yellow_card, .zz-icn-red_card').forEach(icon => {
                    const row = icon.closest('tr');
                    if (!row) return;
                    const playerLink = row.querySelector('a[href*="/jogador/"]');
                    if (!playerLink) return;
                    const playerName = playerLink.textContent.trim();
                    const tipo = icon.className.includes('yellow') ? 'cartao_amarelo' : 'cartao_vermelho';
                    const title = icon.getAttribute('title') || '';
                    let minuto = null;
                    const titleMatch = title.match(/(\\d+)/);
                    if (titleMatch) minuto = parseInt(titleMatch[1]);
                    else {
                        const rowText = row.innerText;
                        const m = rowText.match(/(\\d+)'/);
                        if (m) minuto = parseInt(m[1]);
                    }
                    
                    const key = `${playerName}-${tipo}-${minuto}`;
                    if (!seen.has(key)) {
                        seen.add(key);
                        cards.push({ tipo, jogador: playerName, minuto });
                    }
                });
                return cards;
            })()
        """, [])
        
        for c in cards:
            c['time'] = None # Não sabemos facilmente o time nos cartões da tabela geral ainda
            events.append(c)

        events.sort(key=lambda x: x.get('minuto') or 0)
        return events
    
    def extract_lineups(self, page: Page) -> Dict[str, Dict[str, List]]:
        """Extrai escalações usando .zz-container como fonte primária."""
        
        result = self._safe_eval(page, """
            (() => {
                const result = { home: { starters: [], bench: [], coach: null, teamName: null }, away: { starters: [], bench: [], coach: null, teamName: null } };
                const parsePlayer = (el, numberEl = null) => ({
                    nome: el.textContent.trim(),
                    numero: numberEl ? parseInt(numberEl.textContent.trim()) || null : null
                });
                
                // PRIORIDADE 1: .zz-container > #game_report
                const zzContainer = document.querySelector('.zz-container');
                if (zzContainer) {
                    const gameReport = zzContainer.querySelector('#game_report');
                    if (gameReport) {
                        // Colunas do game_report: primeiro = home, segundo = away
                        const cols = gameReport.querySelectorAll('.zz-tpl-col');
                        const sides = ['home', 'away'];
                        
                        cols.forEach((col, idx) => {
                            if (idx >= 2) return; // Máximo 2 times
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
        """, {'home': {'starters': [], 'bench': []}, 'away': {'starters': [], 'bench': []}})
        
        # 2. Usar teamName do container para popular o campo 'time' nas escalações
        home_team_from_lineups = result.get('home', {}).get('teamName')
        away_team_from_lineups = result.get('away', {}).get('teamName')
        
        # Armazenar para uso em validações futuras se necessário
        if home_team_from_lineups:
            self._lineup_home_team = home_team_from_lineups
        if away_team_from_lineups:
            self._lineup_away_team = away_team_from_lineups
        
        # NOTA: O layout visual do site é confiável:
        # - Esquerda (.left, primeira coluna) = Home (mandante)
        # - Direita (.right, segunda coluna) = Away (visitante)
        # NÃO fazemos inversão baseada em eventos pois os gols são exibidos
        # do lado do time que SOFREU o gol, não do que marcou.

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
    
    def _normalize_name(self, name: str) -> str:
        """Normaliza nome para comparação (remove acentos, minúsculas)."""
        import unicodedata
        nfkd_form = unicodedata.normalize('NFKD', name)
        return u"".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()

    def _fix_teams_by_url(self, url: str):
        """
        Verifica se a ordem dos times na URL (mandante-visitante) contradiz a extração.
        Se necessário, inverte TUDO (times, placar, stats, eventos, escalações).
        """
        if not self.data.get('home_team') or not self.data.get('away_team'):
            return

        # Extrair slugs da URL
        # Padrão: /jogo/YYYY-MM-DD-time-casa-time-fora/id
        match = re.search(r'/jogo/\d{4}-\d{2}-\d{2}-(.+?)-(.+?)/\d+', url)
        if not match:
            return

        slug_home = match.group(1).replace('-', ' ')
        slug_away = match.group(2).replace('-', ' ')
        
        name_home = self._normalize_name(self.data['home_team'])
        name_away = self._normalize_name(self.data['away_team'])
        
        # Função simples de similaridade (contém)
        def is_similar(slug, name):
            # Tokenizar
            slug_tokens = set(slug.split())
            name_tokens = set(name.split())
            # Se houver interseção significativa
            return len(slug_tokens.intersection(name_tokens)) > 0
            
        home_matches_slug_home = is_similar(slug_home, name_home)
        home_matches_slug_away = is_similar(slug_away, name_home)
        
        away_matches_slug_home = is_similar(slug_home, name_away)
        away_matches_slug_away = is_similar(slug_away, name_away)
        
        # Cenário de Inversão: 
        # Extraído Home bate com Slug Away  E  Extraído Away bate com Slug Home
        # E o contrário não é verdadeiro (para evitar nomes parecidos nos dois times)
        if (home_matches_slug_away and away_matches_slug_home and 
            not home_matches_slug_home and not away_matches_slug_away):
            
            logger.warning(f"Inversão de mando detectada via URL ({slug_home} x {slug_away}). Corrigindo dados...")
            
            d = self.data
            
            # 1. Info Básica
            d['home_team'], d['away_team'] = d['away_team'], d['home_team']
            d['home_score'], d['away_score'] = d.get('away_score', 0), d.get('home_score', 0)
            
            # Stats Halftime se existirem
            if 'home_score_halftime' in d:
                d['home_score_halftime'], d['away_score_halftime'] = d.get('away_score_halftime'), d.get('home_score_halftime')

            # 2. Estatísticas
            if 'stats_home' in d and 'stats_away' in d:
                d['stats_home'], d['stats_away'] = d['stats_away'], d['stats_home']
                
            # 3. Escalações
            if 'escalacao_casa' in d and 'escalacao_fora' in d:
                 d['escalacao_casa'], d['escalacao_fora'] = d['escalacao_fora'], d['escalacao_casa']
                 
            # 4. Eventos
            if 'eventos' in d:
                for ev in d['eventos']:
                    if ev.get('time') == 'home':
                        ev['time'] = 'away'
                    elif ev.get('time') == 'away':
                        ev['time'] = 'home'

    def scrape(self, url: str) -> Dict[str, Any]:
        """Executa o scraping completo de forma flexível."""
        logger.info(f"Iniciando scraping: {url}")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage'
                ]
            )
            context = browser.new_context(
                user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080}
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
                # Scroll progressivo para forçar lazy loading
                for y in range(2000, 6000, 1000):
                    page.evaluate(f'window.scrollTo(0, {y})')
                    page.wait_for_timeout(800)
                    self._remove_ads(page)
                
                # Tentar esperar pelo container de escalações
                try:
                    page.wait_for_selector('.zz-module.game_matchup, .game_matchup', timeout=5000)
                except:
                    pass
                
                page.wait_for_timeout(1000)
                
                # 4. Eventos (gols + cartões)
                events = self.extract_events(page)
                if events:
                    self.data['eventos'] = events
                
                # 5. Escalações
                lineups = self.extract_lineups(page)
                self.data.update(lineups)
                
                # 6. Validação final de mando de campo pela URL
                self._fix_teams_by_url(url)
                
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
