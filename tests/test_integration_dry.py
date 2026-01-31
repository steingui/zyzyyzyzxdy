
import sys
import os
import logging
from pathlib import Path

# Setup path
sys.path.append(os.getcwd())

from scripts.utils.normalization import normalize_match_data
from scripts.db_importer import process_input

logging.basicConfig(level=logging.INFO)

mock_data = {
    "url_fonte": "http://teste.com/jogo/1",
    "home_team": "Time Teste Casa",
    "away_team": "Time Teste Fora",
    "rodada": 1,
    "home_score": 2,
    "away_score": 1,
    "data_hora": "13 Abr 2024 16:00",
    "estadio": {"nome": "ESTÁDIO: Monumental de Teste", "cidade": "Cidade X"},
    "arbitro": {"nome": "ÁRBITRO: Juiz Teste"},
    "publico": "45.000",
    "stats_home": {
        "posse": "60%",
        "chutes": "12",
        "xg": "1.45"
    },
    "stats_away": {
        "posse": "40%",
        "chutes": "8",
        "xg": "0.75"
    }
}

print("--- Iniciando Teste de Integração (Dry Run) ---")
try:
    print("1. Normalizando...")
    norm = normalize_match_data(mock_data)
    print(f"   Data normalizada: {norm['data_hora']}")
    print(f"   Posse normalizada: {norm['stats_home']['posse']} (Tipo: {type(norm['stats_home']['posse'])})")
    
    assert norm['data_hora'] == "2024-04-13 16:00:00"
    assert norm['stats_home']['posse'] == 60
    assert norm['arbitro']['nome'] == "Juiz Teste"
    
    print("2. Persistindo no Banco...")
    success = process_input(norm)
    
    if success:
        print("✅ SUCESSO: Dados inseridos no banco via pipeline.")
        sys.exit(0)
    else:
        print("❌ FALHA: db_importer retornou False.")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ ERRO CRÍTICO: {e}")
    sys.exit(1)
