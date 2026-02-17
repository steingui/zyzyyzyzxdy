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
import os
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ensure project root is in path for scripts.* imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.config import OGOL_BASE_URL
from scripts.utils.normalization import normalize_match_data
from scripts.db_importer import process_input
from scripts.utils.state import get_last_processed_round, check_match_exists
from scripts.utils.throttle import AdaptiveThrottle

# Configuração
SCRIPTS_DIR = Path(__file__).parent
OUTPUT_FILE = Path("rodada_atual_full.json")
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Shared Resources
global_throttle = AdaptiveThrottle()

# Configuração de Logs (RFC 005)
from app.utils.logger import get_logger, slog, log_diagnostic
logger = get_logger(__name__)

COMPONENT = "pipeline"

def get_matches(league_slug: str, year: int, force_round: int = None):
    """Calcula próxima rodada (ou usa forçada) e chama o crawler diretamente."""
    from scripts.crawl_round import get_round_matches
    
    if force_round:
        next_round = force_round
        slog(logger, 'info', 'Forced round mode', component=COMPONENT,
             operation='discover_round', round=next_round, league=league_slug)
    else:
        last_round = get_last_processed_round()
        next_round = last_round + 1
        slog(logger, 'info', 'Auto-detected next round', component=COMPONENT,
             operation='discover_round', last_round_in_db=last_round, next_round=next_round)
    
    try:
        urls = get_round_matches(league_slug=league_slug, round_num=next_round)
        
        if not urls:
            slog(logger, 'warning', 'No matches available for round', component=COMPONENT,
                 operation='discover_round', round=next_round, league=league_slug)
            return []
            
        slog(logger, 'info', 'Crawler found matches', component=COMPONENT,
             operation='discover_round', round=next_round, matches_found=len(urls))
        return urls
    except Exception as e:
        log_diagnostic(logger, 'Failed to fetch round matches',
            component=COMPONENT, operation='discover_round', error=e,
            hint='get_round_matches raised an exception. Check crawler diagnostic logs above.',
            round=next_round, league=league_slug)
        return []

def scrape_match(url, index, total):
    """Executa o scraper para um único jogo (Resilience Layer: OgolScraper handles retries internally)."""
    slog(logger, 'info', 'Starting match scrape', component=COMPONENT,
         operation='scrape_match', url=url, match_index=index, total_matches=total)
    
    try:
        # Import local para evitar problemas de escopo/path se importado no topo
        from scripts.scraper import OgolScraper
        
        # Cria nova instância para cada thread
        # Usamos o global_throttle para compartilhar o rate limiting entre threads
        scraper = OgolScraper(headless=True, detailed=True, throttle=global_throttle)
        # O método scrape agora possui @retry via tenacity
        data = scraper.scrape(url)
        return data

    except Exception as e:
        # Import exception locally to avoid top-level import issues if not in pythonpath
        try:
             from scripts.exceptions import InvalidDOMError
             if isinstance(e, InvalidDOMError):
                 log_diagnostic(logger, 'Invalid DOM detected - anti-garbage filter',
                      component=COMPONENT, operation='dom_validation',
                      error=e,
                      hint='Page loaded but DOM structure is invalid. Anti-bot or layout change.',
                      url=url)
                 return None
        except ImportError:
             pass

        log_diagnostic(logger, 'Fatal error processing match',
            component=COMPONENT, operation='scrape_match',
            error=e,
            hint='Unrecoverable error during scraping. Check scraper logs for DOM/network details.',
            url=url)
        return None

def main():
    import argparse
    import socket
    
    parser = argparse.ArgumentParser(description="Batch Scraper Runner")
    parser.add_argument("round", nargs="?", type=int, help="Forçar execução de uma rodada específica (ignora estado do banco)")
    parser.add_argument("--league", required=True, help="League slug (e.g., brasileirao)")
    parser.add_argument("--year", type=int, required=True, help="Season year (e.g., 2026)")
    args = parser.parse_args()
    
    run_batch_pipeline(args.league, args.year, args.round)

def run_batch_pipeline(league_slug, year, round_num=None, job_id=None):
    """
    Main pipeline logic extracted for direct calling (e.g. from Celery).
    """
    import socket
    start_time = datetime.now()
    if not job_id:
        job_id = f"{league_slug}_{year}_r{round_num}_{int(time.time())}"
    
    # Log job start with full context
    slog(logger, 'info', 'Pipeline started', component=COMPONENT,
         operation='pipeline_start', job_id=job_id,
         league=league_slug, year=year,
         round=round_num if round_num else 'auto',
         hostname=socket.gethostname())
    
    # Adicionar path raiz ao pythonpath para imports funcionarem dentro das threads
    sys.path.append(str(Path.cwd()))

    # 1. Obter lista de jogos
    urls = get_matches(force_round=round_num, league_slug=league_slug, year=year)
    if not urls:
        log_diagnostic(logger, 'No matches found for round',
            component=COMPONENT, operation='discover_matches',
            hint='Crawler returned empty list. Either the round has not started or the page structure changed. Check crawler diagnostic logs above.',
            job_id=job_id, league=league_slug, round=round_num)
        return {"status": "completed", "matches_scraped": 0, "total_matches": 0}
        
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
        if check_match_exists(url):
            logger.info(f"⏭️  Skipping (DB Exists): {url}")
            skipped_count += 1
        elif url in processed_urls_json:
                logger.warning(f"⚠️  URL no JSON mas não no DB (Reprocessando): {url}")
                urls_to_scrape.append(url)
        else:
            urls_to_scrape.append(url)

    urls = urls_to_scrape

    if not urls:
        logger.info("Todos os jogos já foram processados e salvos no banco!")
        return {"status": "completed", "matches_scraped": success_count if 'success_count' in locals() else 0, "total_matches": total_urls if 'total_urls' in locals() else 0}

    total_urls = len(urls)
    success_count = 0
    
    slog(logger, 'info', 'Matches discovered, starting parallel scrape', component=COMPONENT,
         operation='scrape_batch', job_id=job_id,
         total_matches=total_urls, skipped_db=skipped_count,
         max_workers=int(os.environ.get('SCRAPE_MAX_WORKERS', '1')),
         sample_urls=urls[:3])
    
    # 3. Executar scraping em paralelo (ThreadPool - Anti-Block)
    MAX_WORKERS = int(os.environ.get('SCRAPE_MAX_WORKERS', '1'))  # Default 1 for memory-constrained environments
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit tasks
        future_to_url = {
            executor.submit(scrape_match, url, i, total_urls): url
            for i, url in enumerate(urls, 1)
        }
        
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                res = future.result()
                if res:
                    data = res
                    results["games"].append(data)
                    success_count += 1
                    
                    slog(logger, 'info', 'Match scraped successfully', component=COMPONENT,
                         operation='match_complete', job_id=job_id,
                         match_index=success_count, total_matches=total_urls,
                         home_team=data.get('home_team'),
                         away_team=data.get('away_team'),
                         score=f"{data.get('home_score')}-{data.get('away_score')}",
                         url=url)
                    
                    # 4. Normalização e Persistência no Banco
                    try:
                        normalized_data = normalize_match_data(data)
                        db_start = time.time()
                        db_success = process_input(normalized_data, league_slug=league_slug, year=year)
                        db_duration = time.time() - db_start
                        
                        if db_success:
                            slog(logger, 'info', 'Match saved to database', component=COMPONENT,
                                 operation='db_insert', job_id=job_id, url=url,
                                 db_duration_ms=int(db_duration * 1000))
                        else:
                            log_diagnostic(logger, 'Failed to save match to database',
                                component=COMPONENT, operation='db_insert',
                                hint='process_input returned False. Check db_importer logs above for SQL error details.',
                                job_id=job_id, url=url,
                                home_team=data.get('home_team'), away_team=data.get('away_team'))
                    except Exception as e:
                        log_diagnostic(logger, 'Critical error saving to database',
                            component=COMPONENT, operation='db_insert',
                            error=e,
                            hint='Unexpected exception during DB persistence. The match was scraped successfully but not saved.',
                            job_id=job_id, url=url)

                    # Salvamento Incremental (Thread-safe aqui na main thread)
                    try:
                        # logger.info(f"Salvando progresso ({success_count}/{total_urls})...")
                        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                            json.dump(results, f, ensure_ascii=False, indent=2)
                    except Exception as e:
                        logger.error(f"Erro ao salvar arquivo incrementalmente: {e}")
                else:
                    log_diagnostic(logger, 'Scraper returned empty data for match',
                        component=COMPONENT, operation='scrape_match',
                        hint='OgolScraper.scrape() returned None/empty. Check scraper diagnostic logs above.',
                        job_id=job_id, url=url)
            except Exception as e:
                log_diagnostic(logger, 'Unhandled exception in scrape thread',
                    component=COMPONENT, operation='thread_result',
                    error=e,
                    hint='ThreadPoolExecutor future raised. This is an infrastructure-level error, not a scraping error.',
                    job_id=job_id, url=url)

    duration = datetime.now() - start_time
    
    # Final summary log
    slog(logger, 'info', 'Pipeline completed', component=COMPONENT,
         operation='pipeline_complete', job_id=job_id,
         league=league_slug, year=year, round=round_num,
         total_matches=total_urls, successful=success_count,
         failed=total_urls - success_count,
         duration_seconds=int(duration.total_seconds()),
         success_rate=f"{(success_count/total_urls*100):.1f}%" if total_urls > 0 else "0%")
    
    return {
        "status": "completed",
        "matches_scraped": success_count,
        "total_matches": total_urls,
        "duration_seconds": int(duration.total_seconds())
    }

if __name__ == "__main__":
    main()
