#!/usr/bin/env python3
"""
crawl_round.py - Coleta URLs dos jogos da rodada atual do Brasileirão

Uso:
    python3 scripts/crawl_round.py [--url URL_DA_COMPETICAO]

Retorno:
    Lista de URLs JSON no stdout
"""

import argparse
import json
import logging
import sys
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
load_dotenv()

# Configuração de Logs
import os
sys.path.append(os.getcwd()) # Ensure root is in path
from app.utils.logger import get_logger, slog, log_diagnostic
from scripts.config import OGOL_BASE_URL

logger = get_logger(__name__)

COMPONENT = "crawler"

def get_round_matches(league_slug: str, round_num: int = None):
    """
    Fetch match URLs for a specific round of a league.
    
    Args:
        round_num: Round/Rodada number (optional)
        league_slug: League slug on ogol.com.br (default: brasileirao)
    """
    url = f"{OGOL_BASE_URL}/competicao/{league_slug}"
    if round_num:
        url = f"{url}?jornada_in={round_num}"
        
    slog(logger, 'info', 'Starting round crawl', component=COMPONENT,
         operation='navigate', url=url, league=league_slug, round=round_num)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            
            # Get page title for diagnostics
            page_title = page.title()
            
            # Esperar tabela
            try:
                page.wait_for_selector("#fixture_games", timeout=10000)
                fixture_table_exists = True
            except:
                fixture_table_exists = False
                log_diagnostic(logger, "Fixture table not found on page",
                    component=COMPONENT, operation="wait_for_table",
                    expected="#fixture_games element present",
                    actual="Element not found within 10s timeout",
                    hint="The page might have changed structure, be blocked by anti-bot, or the round/league slug is invalid",
                    url=url, league=league_slug, round=round_num,
                    page_title=page_title,
                    selector="#fixture_games")
                return []
            
            # Validação de Prontidão: Verificar se existe algum jogo com placar final
            result_check = page.evaluate("""() => {
                const table = document.getElementById('fixture_games');
                const results = document.querySelectorAll('#fixture_games td.result a');
                const allRows = table ? table.querySelectorAll('tr') : [];
                return {
                    has_results: results.length > 0,
                    result_count: results.length,
                    total_rows: allRows.length,
                    page_title: document.title,
                    page_url: window.location.href
                };
            }""")
            
            if not result_check['has_results']:
                log_diagnostic(logger, "No finished matches found in round",
                    component=COMPONENT, operation="check_results",
                    expected="td.result a elements > 0",
                    actual=f"{result_check['result_count']} result links, {result_check['total_rows']} table rows",
                    hint="Page loaded and fixture table exists, but no result links found. Possible causes: (1) round has not started yet, (2) CSS selector 'td.result a' changed on ogol.com.br, (3) anti-bot served empty/different page",
                    url=url, league=league_slug, round=round_num,
                    page_title=result_check['page_title'],
                    final_url=result_check['page_url'],
                    selector_checked="#fixture_games td.result a",
                    fixture_table_exists=True)
                return []

            # Extrair links
            links = page.evaluate("""() => {
                const results = [];
                const tables = document.querySelectorAll('#fixture_games table');
                
                if (tables.length > 0) {
                    const targetTable = tables[0];
                    const cells = targetTable.querySelectorAll('td.result a[href*="/jogo/"]');
                    cells.forEach(a => results.push(a.href));
                } else {
                    const cells = document.querySelectorAll('#fixture_games td.result a[href*="/jogo/"]');
                    cells.forEach(a => results.push(a.href));
                }
                
                return [...new Set(results)];
            }""")
            
            slog(logger, 'info', 'Matches discovered successfully', component=COMPONENT,
                 operation='extract_links', url=url, league=league_slug, round=round_num,
                 matches_found=len(links),
                 result_elements=result_check['result_count'],
                 sample_urls=links[:3] if links else [])
            
            return links
            
        except Exception as e:
            log_diagnostic(logger, "Failed to crawl round page",
                component=COMPONENT, operation="page_load",
                error=e,
                hint="Playwright failed to load or process the page. Possible causes: (1) network timeout on Render free tier, (2) anti-bot redirect, (3) ogol.com.br is down",
                url=url, league=league_slug, round=round_num)
            return []
        finally:
            browser.close()

def main():
    parser = argparse.ArgumentParser(description="Crawler de jogos da rodada")
    parser.add_argument("--round", type=int, help="Número da rodada (opcional)")
    parser.add_argument("--league", required=True, help="League slug (e.g., brasileirao)")
    args = parser.parse_args()
    
    matches = get_round_matches(league_slug=args.league, round_num=args.round)
    
    if matches:
        slog(logger, 'info', 'Crawl completed', component=COMPONENT,
             operation='complete', matches=len(matches))
        print(json.dumps(matches, indent=2))
    else:
        slog(logger, 'warning', 'No matches available', component=COMPONENT,
             operation='complete', league=args.league, round=args.round)
        print("[]")

if __name__ == "__main__":
    main()
