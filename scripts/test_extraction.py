
from playwright.sync_api import sync_playwright
import sys
import os

# Put project root in path
sys.path.append(os.getcwd())

from scripts.extractors.match_info import extract_match_info

url = "https://www.ogol.com.br/jogo/2026-01-28-atletico-mineiro-palmeiras/11860784"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    print(f"Navegando: {url}")
    page.goto(url)
    
    info = extract_match_info(page)
    print("EXTRACTION RESULT:")
    print(info)
    
    # Debug: Imprimir texto da página para ver onde está a Rodada
    print("\n--- PAGE TEXT SNIPPET ---")
    text = page.evaluate("document.body.innerText")
    print(text[:2000])
    print("-------------------------")
    
    if not info.get('rodada'):
        print("❌ FALHA: Rodada não encontrada")
    else:
        print(f"✅ SUCESSO: Rodada = {info['rodada']}")
        
    browser.close()
