#!/usr/bin/env python3
"""
main.py - Orquestrador principal do pipeline de scraping

Descobre automaticamente os links de jogos de cada rodada do Brasileirão
e processa cada partida salvando no banco de dados.

Uso:
    python3 scripts/main.py                    # Processa todas as rodadas pendentes
    python3 scripts/main.py --rodada 1         # Processa apenas a rodada 1
    python3 scripts/main.py --rodada 1-5       # Processa rodadas 1 a 5
    python3 scripts/main.py --descobrir        # Apenas lista os links (não processa)
"""

import argparse
import json
import sys
import os
import logging
import time
from datetime import datetime
from typing import List, Dict, Optional, Set
from pathlib import Path

from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout

# Importar módulos locais
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.scraper import OgolScraper
from scripts.db_importer import process_input, get_connection
from scripts.config import USER_AGENT, VIEWPORT

# Configuração de logging com timestamp ISO
LOG_TIMESTAMP = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(f'logs/main_{LOG_TIMESTAMP}.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# URLs base
BASE_URL = "https://www.ogol.com.br"
COMPETITION_URL = f"{BASE_URL}/edicao/brasileirao-serie-a-2026/210277"


class BrasileiraoLinkDiscovery:
    """Descobre links de jogos do Brasileirão por rodada."""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.links_by_round: Dict[int, List[str]] = {}
    
    def _close_overlay(self, page: Page):
        """Fecha overlays de publicidade se presentes."""
        try:
            # Tentar clicar em "AVANÇAR" ou botão de fechar
            page.evaluate("""
                (() => {
                    const buttons = Array.from(document.querySelectorAll('div, a, span, button'));
                    const avanzar = buttons.find(b => b.innerText && 
                        (b.innerText.includes('AVANÇAR') || b.innerText.includes('PULAR') || b.innerText.includes('FECHAR')));
                    if (avanzar) avanzar.click();
                })()
            """)
            page.wait_for_timeout(500)
        except:
            pass
    
    def _extract_links_from_page(self, page: Page) -> List[str]:
        """Extrai todos os links de jogos visíveis na página."""
        try:
            links = page.evaluate("""
                Array.from(document.querySelectorAll('a[href^="/jogo/"]'))
                    .map(a => a.href)
                    .filter((v, i, arr) => arr.indexOf(v) === i)
            """)
            return links
        except Exception as e:
            logger.warning(f"Erro ao extrair links: {e}")
            return []
    
    def discover_round(self, rodada: int) -> List[str]:
        """Descobre os links de jogos de uma rodada específica."""
        logger.info(f"Descobrindo links da Rodada {rodada}...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1280, 'height': 800}
            )
            page = context.new_page()
            
            try:
                # Acessar página da competição com parâmetro de rodada
                url = f"{COMPETITION_URL}?fase=230406&rodada={rodada}"
                page.goto(url, wait_until='networkidle', timeout=30000)
                
                # Fechar overlays
                self._close_overlay(page)
                page.wait_for_timeout(1500)
                
                # Scroll para carregar conteúdo
                page.evaluate('window.scrollBy(0, 500)')
                page.wait_for_timeout(1000)
                
                # Extrair links
                links = self._extract_links_from_page(page)
                
                # Filtrar apenas links relevantes (ignorar jogos de outras competições)
                filtered = [l for l in links if '/jogo/2026' in l]
                
                logger.info(f"Rodada {rodada}: {len(filtered)} jogos encontrados")
                self.links_by_round[rodada] = filtered
                
                return filtered
                
            except Exception as e:
                logger.error(f"Erro ao descobrir rodada {rodada}: {e}")
                return []
                
            finally:
                browser.close()
    
    def discover_all_rounds(self, start: int = 1, end: int = 38) -> Dict[int, List[str]]:
        """Descobre links de todas as rodadas (ou intervalo específico)."""
        logger.info(f"Descobrindo rodadas {start} a {end}...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1280, 'height': 800}
            )
            page = context.new_page()
            
            try:
                for rodada in range(start, end + 1):
                    url = f"{COMPETITION_URL}?fase=230406&rodada={rodada}"
                    page.goto(url, wait_until='networkidle', timeout=30000)
                    
                    self._close_overlay(page)
                    page.wait_for_timeout(1000)
                    page.evaluate('window.scrollBy(0, 500)')
                    page.wait_for_timeout(800)
                    
                    links = self._extract_links_from_page(page)
                    filtered = [l for l in links if '/jogo/2026' in l]
                    
                    self.links_by_round[rodada] = filtered
                    logger.info(f"Rodada {rodada}: {len(filtered)} jogos")
                    
                    # Delay entre rodadas
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Erro durante descoberta: {e}")
                
            finally:
                browser.close()
        
        return self.links_by_round


def get_processed_urls() -> Set[str]:
    """Retorna URLs já processadas no banco de dados."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT url_fonte FROM partidas WHERE url_fonte IS NOT NULL")
        urls = {row['url_fonte'] for row in cursor.fetchall()}
        cursor.close()
        conn.close()
        return urls
    except:
        return set()


def process_round(rodada: int, links: List[str], skip_existing: bool = True):
    """Processa todos os jogos de uma rodada."""
    logger.info(f"Processando Rodada {rodada} ({len(links)} jogos)...")
    
    # Verificar URLs já processadas
    processed_urls = get_processed_urls() if skip_existing else set()
    
    scraper = OgolScraper(headless=True)
    success = 0
    skipped = 0
    failed = 0
    
    for i, url in enumerate(links, 1):
        # Pular se já processado
        if url in processed_urls:
            logger.info(f"[{i}/{len(links)}] Pulando (já existe): {url}")
            skipped += 1
            continue
        
        logger.info(f"[{i}/{len(links)}] Processando: {url}")
        
        try:
            # Extrair dados
            data = scraper.scrape(url)
            
            # Garantir rodada correta
            if not data.get('rodada'):
                data['rodada'] = rodada
            
            # Salvar no banco
            if process_input(data):
                success += 1
                logger.info(f"✅ Salvo: {data.get('home_team', '?')} x {data.get('away_team', '?')}")
            else:
                failed += 1
                
        except Exception as e:
            logger.error(f"❌ Erro: {e}")
            failed += 1
        
        # Delay entre jogos
        time.sleep(2)
    
    logger.info(f"Rodada {rodada} concluída: {success} salvos, {skipped} existentes, {failed} falhas")
    return success, skipped, failed


def main():
    """Ponto de entrada principal."""
    parser = argparse.ArgumentParser(description='Pipeline de scraping do Brasileirão 2026')
    parser.add_argument('--rodada', '-r', type=str, help='Rodada(s) para processar (ex: 1, 1-5)')
    parser.add_argument('--descobrir', '-d', action='store_true', help='Apenas descobrir links (não processar)')
    parser.add_argument('--no-headless', action='store_true', help='Mostrar navegador')
    parser.add_argument('--force', '-f', action='store_true', help='Reprocessar jogos existentes')
    args = parser.parse_args()
    
    # Garantir diretório de logs
    os.makedirs('logs', exist_ok=True)
    
    # Determinar rodadas
    if args.rodada:
        if '-' in args.rodada:
            start, end = map(int, args.rodada.split('-'))
        else:
            start = end = int(args.rodada)
    else:
        start, end = 1, 38
    
    headless = not args.no_headless
    
    # Descobrir links
    discovery = BrasileiraoLinkDiscovery(headless=headless)
    all_links = discovery.discover_all_rounds(start, end)
    
    # Mostrar resumo
    total_games = sum(len(links) for links in all_links.values())
    logger.info(f"\n📊 Total: {total_games} jogos encontrados em {len(all_links)} rodadas")
    
    if args.descobrir:
        # Apenas mostrar os links
        for rodada, links in sorted(all_links.items()):
            print(f"\n=== Rodada {rodada} ===")
            for link in links:
                print(link)
        return
    
    # Processar cada rodada
    total_success = 0
    total_skipped = 0
    total_failed = 0
    
    for rodada, links in sorted(all_links.items()):
        if links:
            s, k, f = process_round(rodada, links, skip_existing=not args.force)
            total_success += s
            total_skipped += k
            total_failed += f
    
    # Resumo final
    print("\n" + "=" * 50)
    print("📊 RESUMO FINAL")
    print("=" * 50)
    print(f"✅ Salvos: {total_success}")
    print(f"⏭️  Existentes: {total_skipped}")
    print(f"❌ Falhas: {total_failed}")
    print("=" * 50)


if __name__ == "__main__":
    main()
