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
    from scripts.utils.state import get_last_processed_round, check_match_exists
except ImportError:
    # Fallback se rodar de dentro de scripts/
    sys.path.append(str(Path(__file__).parent.parent))
    from scripts.utils.normalization import normalize_match_data
    from scripts.db_importer import process_input
    from scripts.utils.state import get_last_processed_round, check_match_exists

# Configuração
SCRIPTS_DIR = Path(__file__).parent
OUTPUT_FILE = Path("rodada_atual_full.json")
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Structured logging setup
class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs JSON logs with context"""
    def format(self, record):
        log_obj = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        # Add extra fields if present
        if hasattr(record, 'job_context'):
            log_obj.update(record.job_context)
        return json.dumps(log_obj, ensure_ascii=False)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Human-readable for console
        logging.FileHandler(LOG_DIR / "batch_run.log")
    ]
)
logger = logging.getLogger(__name__)

# Add JSON handler for structured logs
json_handler = logging.FileHandler(LOG_DIR / "batch_structured.log")
json_handler.setFormatter(StructuredFormatter())
logger.addHandler(json_handler)

def log_with_context(level, message, **context):
    """Helper function to log with additional context (structured logging)"""
    # Map 'success' to 'info' since logger doesn't have success level
    if level == 'success':
        level = 'info'
        message = f"✅ {message}"  # Visual indicator for success
    
    # Create a log record with extra context
    extra_record = type('obj', (object,), {'job_context': context})()
    
    # Get logger level method
    log_method = getattr(logger, level.lower(), logger.info)
    log_method(message, extra=extra_record.__dict__)

def get_matches(force_round: int = None, league_slug: str = "brasileirao", year: int = 2026):
    """Calcula próxima rodada (ou usa forçada) e chama o crawler."""
    if force_round:
        next_round = force_round
        logger.info(f"MODO MANUAL: Forçando busca da rodada: {next_round}")
    else:
        last_round = get_last_processed_round()
        next_round = last_round + 1
        logger.info(f"Última rodada no banco: {last_round}. Buscando rodada: {next_round}")
    
    try:
        cmd = [
            sys.executable, str(SCRIPTS_DIR / "crawl_round.py"),
            "--round", str(next_round),
            "--league", league_slug
        ]
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
    """Executa o scraper para um único jogo (Resilience Layer: OgolScraper handles retries internally)."""
    logger.info(f"[{index}/{total}] Iniciando scraping: {url}")
    
    try:
        # Import local para evitar problemas de escopo/path se importado no topo
        from scripts.scraper import OgolScraper
        
        # Cria nova instância para cada thread
        scraper = OgolScraper(headless=True, detailed=True)
        # O método scrape agora possui @retry via tenacity
        data = scraper.scrape(url)
        return data

    except Exception as e:
        logger.error(f"❌ Falha fatal ao processar {url}: {e}")
        return None

def main():
    import argparse
    import socket
    
    parser = argparse.ArgumentParser(description="Batch Scraper Runner")
    parser.add_argument("round", nargs="?", type=int, help="Forçar execução de uma rodada específica (ignora estado do banco)")
    parser.add_argument("--league", default="brasileirao", help="League slug (default: brasileirao)")
    parser.add_argument("--year", type=int, default=2026, help="Season year (default: 2026)")
    args = parser.parse_args()
    
    start_time = datetime.now()
    job_id = f"{args.league}_{args.year}_r{args.round}_{int(time.time())}"
    
    # Log job start with full context
    log_with_context('info', 'Pipeline started',
        job_id=job_id,
        league=args.league,
        year=args.year,
        round=args.round if args.round else 'auto',
        round=args.round if args.round else 'auto',
        hostname=socket.gethostname(),
        timestamp=start_time.isoformat()
    )
    
    logger.info(f"🚀 Starting scrape: {args.league} {args.year} Round {args.round}")
    
    # 1. Obter lista de jogos
    urls = get_matches(force_round=args.round, league_slug=args.league, year=args.year)
    if not urls:
        log_with_context('warning', 'No matches found',
            job_id=job_id,
            league=args.league,
            round=args.round
        )
        logger.info("Pipeline encerrado: Nenhum jogo disponível para processar na próxima rodada.")
        sys.exit(0)
        
    # 2. Carregar progresso anterior (JSON local) - Backup Legacy
    results = {
        "metadata": {
            "crawled_at": start_time.isoformat(),
            "source": "ogol.com.br",
            "total_games": len(urls)
        },
        "games": []
    }
    
    processed_urls_json = set()
    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
                if "games" in saved_data:
                    results = saved_data
                    processed_urls_json = {g.get('url') for g in results["games"] if g.get('url')}
                    logger.info(f"JSON Cache: {len(processed_urls_json)} jogos encontrados.")
        except Exception as e:
            logger.warning(f"Não foi possível ler JSON incremental, ignorando: {e}")

    # 3. State Checkpoint no Banco (Single Source of Truth)
    urls_to_scrape = []
    skipped_count = 0
    
    logger.info("Verificando estado no banco de dados...")
    for url in urls:
        # Se já está no JSON local, não precisamos checar banco (otimização leve)
        # MAS a 'Zero Tolerance' prefere checar banco. 
        # Vamos checar banco sempre pra garantir atomicidade real.
        if check_match_exists(url):
            logger.info(f"⏭️  Skipping (DB Exists): {url}")
            skipped_count += 1
        elif url in processed_urls_json:
                # Está no JSON mas não no banco? Estranho, mas vamos reprocessar para garantir insert DB
                logger.warning(f"⚠️  URL no JSON mas não no DB (Reprocessando): {url}")
                urls_to_scrape.append(url)
        else:
            urls_to_scrape.append(url)

    urls = urls_to_scrape

    if not urls:
        logger.info("Todos os jogos já foram processados e salvos no banco!")
        sys.exit(0)

    # Adicionar path raiz ao pythonpath para imports funcionarem dentro das threads
    sys.path.append(str(Path.cwd()))
    
    total_urls = len(urls)
    success_count = 0
    
    log_with_context('info', 'Matches discovered',
        job_id=job_id,
        total_matches=total_urls,
        urls=urls[:3]  # Log first 3 for reference
    )
    logger.info(f"📊 Total de jogos a processar: {total_urls}")
    
    # 3. Executar scraping em paralelo (ThreadPool - Anti-Block)
    MAX_WORKERS = 3  # Respeitar servidor
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit tasks
        future_to_url = {
            executor.submit(scrape_match, url, i, total_urls): url
            for i, url in enumerate(urls, success_count + 1)
        }
        
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                if future.result():
                    data = future.result()
                    results["games"].append(data)
                    success_count += 1
                    
                    log_with_context('info', 'Match scraped',
                        job_id=job_id,
                        match_index=success_count,
                        total_matches=total_urls,
                        home_team=data.get('home_team'),
                        away_team=data.get('away_team'),
                        score=f"{data.get('home_score')}-{data.get('away_score')}",
                        url=url
                    )
                    logger.info(f"✅ Sucesso ({success_count}/{total_urls}): {url}")
                    
                    # 4. Normalização e Persistência no Banco
                    try:
                        normalized_data = normalize_match_data(data)
                        db_start = time.time()
                        db_success = process_input(normalized_data, league_slug=args.league, year=args.year)
                        db_duration = time.time() - db_start
                        
                        if db_success:
                            log_with_context('info', 'Match saved to database',
                                job_id=job_id,
                                url=url,
                                db_duration_ms=int(db_duration * 1000)
                            )
                            logger.info(f"💾 DB Insert OK: {url}")
                        else:
                            log_with_context('error', 'Failed to save match to database',
                                job_id=job_id,
                                url=url
                            )
                            logger.error(f"❌ DB Insert FALHOU: {url}")
                    except Exception as e:
                        log_with_context('error', 'Critical error saving to database',
                            job_id=job_id,
                            url=url,
                            error=str(e),
                            error_type=type(e).__name__
                        )
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
                    log_with_context('error', 'Failed to scrape match',
                        job_id=job_id,
                        url=url
                    )
                    logger.error(f"❌ Falha ao processar: {url}")
            except Exception as e:
                log_with_context('error', 'Unhandled exception in thread',
                    job_id=job_id,
                    url=url,
                    error=str(e),
                    error_type=type(e).__name__
                )
                logger.error(f"❌ Exceção não tratada na thread para {url}: {e}")

    duration = datetime.now() - start_time
    
    # Final summary log
    log_with_context('info', 'Pipeline completed',
        job_id=job_id,
        league=args.league,
        year=args.year,
        round=args.round,
        total_matches=total_urls,
        successful=success_count,
        failed=total_urls - success_count,
        duration_seconds=int(duration.total_seconds()),
        success_rate=f"{(success_count/total_urls*100):.1f}%" if total_urls > 0 else "0%"
    )
    
    logger.info(f"🏁 Processamento concluído em {duration}.")
    logger.info(f"Sucesso: {success_count}/{total_urls}")
    logger.info(f"Dados salvos em: {OUTPUT_FILE.absolute()}")

if __name__ == "__main__":
    main()
