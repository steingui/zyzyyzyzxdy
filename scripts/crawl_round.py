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

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DEFAULT_URL_BASE = "https://www.ogol.com.br/competicao"

def get_round_matches(round_num: int = None, league_slug: str = "brasileirao"):
    """
    Fetch match URLs for a specific round of a league.
    
    Args:
        round_num: Round/Rodada number (optional)
        league_slug: League slug on ogol.com.br (default: brasileirao)
    """
    url = f"{DEFAULT_URL_BASE}/{league_slug}"
    if round_num:
        url = f"{url}?jornada_in={round_num}"
        
    logger.info(f"Target URL: {url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            
            # Esperar tabela
            try:
                page.wait_for_selector("#fixture_games", timeout=10000)
            except:
                logger.warning("Tabela de jogos não encontrada (rodada vazia ou inválida?)")
                return []
            
            # Validação de Prontidão: Verificar se existe algum jogo com placar final
            # Buscamos por links de jogo que tenham resultado (formato comum no site)
            has_results = page.evaluate("""() => {
                const results = document.querySelectorAll('#fixture_games td.result a');
                // Se houver algum link na coluna de resultado, assumimos que há jogos (mesmo que ao vivo)
                return results.length > 0;
            }""")
            
            if not has_results:
                logger.warning(f"Rodada {round_num} parece não ter jogos iniciados/terminados.")
                return []

            # Extrair links (Apenas da primeira tabela para evitar rodadas futuras/duplicatas)
            links = page.evaluate("""() => {
                const results = [];
                // Selecionar tabelas dentro do container
                const tables = document.querySelectorAll('#fixture_games table');
                
                if (tables.length > 0) {
                    // Assume que a primeira tabela é a rodada solicitada (padrão do filtro jornada_in)
                    const targetTable = tables[0];
                    const cells = targetTable.querySelectorAll('td.result a[href*="/jogo/"]');
                    cells.forEach(a => results.push(a.href));
                } else {
                    // Fallback para comportamento antigo se não achar tabelas específicas (estrutura plana?)
                    const cells = document.querySelectorAll('#fixture_games td.result a[href*="/jogo/"]');
                    cells.forEach(a => results.push(a.href));
                }
                
                return [...new Set(results)];
            }""")
            
            return links
            
        except Exception as e:
            logger.error(f"Erro ao extrair jogos: {e}")
            return []
        finally:
            browser.close()

def main():
    parser = argparse.ArgumentParser(description="Crawler de jogos da rod ada")
    parser.add_argument("--round", type=int, help="Número da rodada (opcional)")
    parser.add_argument("--league", default="brasileirao", help="League slug (default: brasileirao)")
    args = parser.parse_args()
    
    matches = get_round_matches(args.round, args.league)
    
    if matches:
        logger.info(f"Encontrados {len(matches)} jogos.")
        print(json.dumps(matches, indent=2))
    else:
        # Exit code 0 mas lista vazia = nada para fazer (rodada futura ou vazia)
        logger.warning("Nenhum jogo disponível.")
        print("[]")

if __name__ == "__main__":
    main()
