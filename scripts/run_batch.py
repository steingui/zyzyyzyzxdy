#!/usr/bin/env python3
"""
run_batch.py - Executa o scraper para toda a rodada (Paralelo + Incremental)

1. Descobre URLs dos jogos (via crawl_round.py)
2. Carrega progresso anterior (se houver)
3. Executa scraper.py para cada jogo pendente em PARALELO
4. Consolida resultados e salva incrementalmente
"""

import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Imports locais (assumindo execução da raiz ou pythonpath configurado)
try:
    from scripts.utils.normalization import normalize_match_data
    from scripts.db_importer import process_input
    from scripts.utils.state import get_last_processed_round
except ImportError:
    # Fallback se rodar de dentro de scripts/
    sys.path.append(str(Path(__file__).parent.parent))
    from scripts.utils.normalization import normalize_match_data
    from scripts.db_importer import process_input
    from scripts.utils.state import get_last_processed_round

# Configuração
SCRIPTS_DIR = Path(__file__).parent
OUTPUT_FILE = Path("rodada_atual_full.json")
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "batch_run.log")
    ]
)
logger = logging.getLogger(__name__)

def get_matches(force_round: int = None):
    """Calcula próxima rodada (ou usa forçada) e chama o crawler."""
    if force_round:
        next_round = force_round
        logger.info(f"MODO MANUAL: Forçando busca da rodada: {next_round}")
    else:
        last_round = get_last_processed_round()
        next_round = last_round + 1
        logger.info(f"Última rodada no banco: {last_round}. Buscando rodada: {next_round}")
    
    try:
        cmd = [sys.executable, str(SCRIPTS_DIR / "crawl_round.py"), "--round", str(next_round)]
        result = subprocess.run(
            cmd,
            capture_output=True, text=True, check=True
        )
        # O crawler imprime logs no stderr e JSON no stdout
        urls = json.loads(result.stdout)
        
        if not urls:
            logger.warning(f"Rodada {next_round} não tem jogos disponíveis ou prontos.")
            return []
            
        return urls
    except subprocess.CalledProcessError as e:
        logger.error(f"Falha ao buscar jogos: {e.stderr}")
        return []
    except json.JSONDecodeError:
        logger.error(f"Saída inválida do crawler: {result.stdout}")
        return []

def scrape_match(url, index, total):
    """Executa o scraper para um único jogo com Retry."""
    max_retries = 3
    
    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            logger.info(f"[{index}/{total}] Retentando {url} (Tentativa {attempt}/{max_retries})...")
        else:
            logger.info(f"[{index}/{total}] Iniciando scraping: {url}")
        
        try:
            # Import local para evitar problemas de escopo/path se importado no topo
            from scripts.scraper import OgolScraper
            
            # Cria nova instância para cada thread
            # ANTI-BLOCK: Headless=True (Usuario pediu para voltar) - Mantendo headers para segurança
            scraper = OgolScraper(headless=True, detailed=True)
            data = scraper.scrape(url)
            return data

        except Exception as e:
            logger.warning(f"Erro na tentativa {attempt} para {url}: {e}")
            if attempt < max_retries:
                # ANTI-BLOCK: Aumentar backoff
                wait_time = 10 * attempt
                time.sleep(wait_time)
            else:
                logger.error(f"Falha definitiva após {max_retries} tentativas: {url}")
                return None

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Batch Scraper Runner")
    parser.add_argument("round", nargs="?", type=int, help="Forçar execução de uma rodada específica (ignora estado do banco)")
    args = parser.parse_args()
    
    start_time = datetime.now()
    
    # 1. Obter lista de jogos
    urls = get_matches(force_round=args.round)
    if not urls:
        logger.info("Pipeline encerrado: Nenhum jogo disponível para processar na próxima rodada.")
        sys.exit(0)
        
    # 2. Carregar progresso anterior se existir
    results = {
        "metadata": {
            "crawled_at": start_time.isoformat(),
            "source": "ogol.com.br",
            "total_games": len(urls)
        },
        "games": []
    }
    
    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
                if "games" in saved_data:
                    results = saved_data
                    processed_urls = {g.get('url') for g in results["games"] if g.get('url')}
                    logger.info(f"Encontrados {len(processed_urls)} jogos já processados. Retomando...")
                    
                    # Filtra URLs
                    urls = [u for u in urls if u not in processed_urls]
        except Exception as e:
            logger.warning(f"Não foi possível ler arquivo existente, iniciando do zero: {e}")

    if not urls:
        logger.info("Todos os jogos já foram processados!")
        sys.exit(0)

    # Adicionar path raiz ao pythonpath para imports funcionarem dentro das threads
    sys.path.append(str(Path.cwd()))
    
    success_count = len(results["games"])
    total_urls = success_count + len(urls)
    
    # ANTI-BLOCK: Execução sequencial para evitar detecção
    logger.info(f"Iniciando processamento SEQUENCIAL de {len(urls)} jogos restantes...")

    # 3. Processar (workers=1 efetivamente sequencial)
    with ThreadPoolExecutor(max_workers=2) as executor:
        # Submit tasks
        future_to_url = {
            executor.submit(scrape_match, url, i, total_urls): url
            for i, url in enumerate(urls, success_count + 1)
        }
        
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                data = future.result()
                if data:
                    results["games"].append(data)
                    success_count += 1
                    logger.info(f"Sucesso: {url}")
                    
                    # 4. Normalização e Persistência no Banco
                    try:
                        logger.info(f"Normalizando e salvando no Banco de Dados: {url}")
                        normalized_data = normalize_match_data(data)
                        db_success = process_input(normalized_data)
                        if db_success:
                            logger.info(f"✅ DB Insert OK: {url}")
                        else:
                            logger.error(f"❌ DB Insert FALHOU: {url}")
                    except Exception as e:
                        logger.error(f"❌ Erro crítico ao salvar no banco (continuando batch): {e}")

                    # Salvamento Incremental (JSON Backup)
                    
                    # Salvamento Incremental (Thread-safe aqui na main thread)
                    try:
                        logger.info(f"Salvando progresso ({success_count}/{total_urls})...")
                        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                            json.dump(results, f, ensure_ascii=False, indent=2)
                    except Exception as e:
                        logger.error(f"Erro ao salvar arquivo incrementalmente: {e}")
                else:
                    logger.error(f"Falha ao processar: {url}")
            except Exception as e:
                logger.error(f"Exceção não tratada na thread para {url}: {e}")

    duration = datetime.now() - start_time
    logger.info(f"Processamento concluído em {duration}.")
    logger.info(f"Sucesso: {success_count}/{total_urls}")
    logger.info(f"Dados salvos em: {OUTPUT_FILE.absolute()}")

if __name__ == "__main__":
    main()
