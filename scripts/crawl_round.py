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

DEFAULT_URL = "https://www.ogol.com.br/competicao/brasileirao"

def get_round_matches(url: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Usar user agent comum para evitar bloqueios simples
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        page = context.new_page()
        
        logger.info(f"Acessando: {url}")
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            
            # Esperar a tabela de jogos renderizar
            page.wait_for_selector("#fixture_games", timeout=10000)
            
            # Extrair links dos jogos da rodada atual
            # O seletor baseia-se na estrutura fornecida: td.result a[href*='/jogo/']
            links = page.evaluate("""() => {
                const results = [];
                // Seleciona todas as células de resultado na tabela de jogos
                const cells = document.querySelectorAll('#fixture_games td.result a[href*="/jogo/"]');
                
                cells.forEach(a => {
                    if (a.href) {
                        results.push(a.href);
                    }
                });
                
                // Remover duplicatas (links podem aparecer repetidos como texto vazio e placar)
                return [...new Set(results)];
            }""")
            
            return links
            
        except Exception as e:
            logger.error(f"Erro ao extrair jogos: {e}")
            return []
        finally:
            browser.close()

def main():
    parser = argparse.ArgumentParser(description="Crawler de jogos da rodada")
    parser.add_argument("--url", default=DEFAULT_URL, help="URL da página da competição")
    args = parser.parse_args()
    
    matches = get_round_matches(args.url)
    
    if matches:
        logger.info(f"Encontrados {len(matches)} jogos.")
        print(json.dumps(matches, indent=2))
    else:
        logger.warning("Nenhum jogo encontrado.")
        sys.exit(1)

if __name__ == "__main__":
    main()
