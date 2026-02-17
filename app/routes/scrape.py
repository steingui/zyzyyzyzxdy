#!/usr/bin/env python3
"""
scrape.py - API endpoints for remote scraping pipeline triggering with Redis

Queue-based system (Redis):
- POST /api/scrape enqueues job to 'scrape:queue' (returns 202 immediately)
- Background worker thread processes queue from Redis
- Jobs metadata stored in Redis Hash 'scrape:jobs'
- Persistent across restarts
"""

import os
import json
import time
import threading
import redis
import logging
from pathlib import Path
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from app.models import db, Liga
from scripts.run_batch import run_batch_pipeline

scrape_bp = Blueprint('scrape', __name__, url_prefix='/api/scrape')

# Logging
from app.utils.logger import get_logger, slog, log_diagnostic
logger = get_logger(__name__)

COMPONENT = "worker"

# Redis Configuration
from app.database.redis import redis_client

# Redis Keys
KEY_QUEUE = "scrape:queue"
KEY_JOBS = "scrape:jobs"

# Constants
MAX_RETRIES = 3
RETRY_DELAY = 10 # Seconds
MAX_RECOVERY_ATTEMPTS = 3  # Circuit breaker: stop recovering jobs that OOM repeatedly
WORKER_LOCK_KEY = "scrape:worker_lock"
WORKER_LOCK_TTL = 300  # seconds

# Worker controls (In-process thread)
worker_thread = None
worker_running = False

def get_job(job_id):
    """Get single job from Redis"""
    try:
        data = redis_client.hget(KEY_JOBS, job_id)
        return json.loads(data) if data else None
    except Exception as e:
        slog(logger, 'error', 'Redis error in get_job', component=COMPONENT,
             operation='redis_read', error_type=type(e).__name__, error_message=str(e))
        return None

def save_job(job_data):
    """Save/Update single job in Redis"""
    try:
        job_id = job_data['job_id']
        redis_client.hset(KEY_JOBS, job_id, json.dumps(job_data))
    except Exception as e:
        slog(logger, 'error', 'Redis error in save_job', component=COMPONENT,
             operation='redis_write', job_id=job_data.get('job_id'), error_message=str(e))

def load_jobs():
    """Load all jobs from Redis"""
    try:
        raw = redis_client.hgetall(KEY_JOBS)
        return {k: json.loads(v) for k, v in raw.items()}
    except Exception as e:
        slog(logger, 'error', 'Redis error in load_jobs', component=COMPONENT,
             operation='redis_read', error_message=str(e))
        return {}

def recover_stuck_jobs():
    """
    On startup, find jobs that were in 'processing' or 'queued' but 
    never finished (app crash) and put them back in the queue.
    
    Circuit breaker: if a job has been recovered too many times
    (MAX_RECOVERY_ATTEMPTS), it means it consistently OOMs or fails.
    Mark it as 'failed' instead of re-queuing to break the crash loop.
    """
    slog(logger, 'info', 'Checking for stuck jobs on startup', component=COMPONENT,
         operation='recover_stuck_jobs')
    jobs = load_jobs()
    recovered_count = 0
    failed_count = 0
    
    # Get current queue content to avoid duplicates
    try:
        current_queue = redis_client.lrange(KEY_QUEUE, 0, -1)
        enqueued_job_ids = {json.loads(j)['job_id'] for j in current_queue}
    except:
        enqueued_job_ids = set()

    for job_id, job_data in jobs.items():
        status = job_data.get('status')
        if status in ['processing', 'queued']:
            if job_id not in enqueued_job_ids:
                recovery_count = job_data.get('recovery_count', 0) + 1
                
                # Circuit breaker: too many recoveries = permanent failure
                if recovery_count > MAX_RECOVERY_ATTEMPTS:
                    log_diagnostic(logger, 'Job exceeded max recovery attempts - circuit breaker triggered',
                        component=COMPONENT, operation='circuit_breaker',
                        hint='This job has been recovered too many times. Likely cause: the scrape consistently OOMs or crashes. Check memory usage and reduce SCRAPE_MAX_WORKERS.',
                        job_id=job_id, recovery_count=recovery_count,
                        max_attempts=MAX_RECOVERY_ATTEMPTS, last_status=status)
                    job_data['status'] = 'failed'
                    job_data['error'] = f'Exceeded max recovery attempts ({MAX_RECOVERY_ATTEMPTS}). Likely OOM.'
                    job_data['completed_at'] = datetime.utcnow().isoformat() + 'Z'
                    save_job(job_data)
                    failed_count += 1
                    continue
                
                slog(logger, 'warning', 'Recovering stuck job', component=COMPONENT,
                     operation='recover_job', job_id=job_id, previous_status=status,
                     recovery_count=recovery_count, max_attempts=MAX_RECOVERY_ATTEMPTS)
                job_data['status'] = 'queued'
                job_data['recovery_count'] = recovery_count
                job_data['recovered_at'] = datetime.utcnow().isoformat() + 'Z'
                save_job(job_data)
                redis_client.lpush(KEY_QUEUE, json.dumps(job_data))
                recovered_count += 1
    
    slog(logger, 'info', 'Stuck job recovery complete', component=COMPONENT,
         operation='recover_stuck_jobs', recovered=recovered_count,
         failed_circuit_breaker=failed_count, total_inspected=len(jobs))

def scrape_worker():
    """
    Background worker that consumes a Redis list queue.
    Runs one job at a time in-process with Retry logic.
    """
    global worker_running
    slog(logger, 'info', 'Scraping worker thread started', component=COMPONENT,
         operation='thread_start', pid=os.getpid(), thread_name='ScrapeWorker')
    
    scraper_logger = logging.getLogger('scripts.run_batch')
    
    while worker_running:
        try:
            # Block until a job is available
            result = redis_client.blpop(KEY_QUEUE, timeout=5)
            if not result:
                continue
            
            _, job_json = result
            job_data = json.loads(job_json)
            job_id = job_data['job_id']
            league_slug = job_data['league']
            year = job_data['year']
            round_num = job_data['round']
            log_file = job_data.get('log_file')
            retry_count = job_data.get('retry_count', 0)
            
            slog(logger, 'info', 'Processing job', component=COMPONENT,
                 operation='job_start', job_id=job_id, attempt=retry_count + 1,
                 league=league_slug, year=year, round=round_num)
            
            # Setup dynamic log file handler
            handler = None
            if log_file:
                log_path = Path(log_file)
                log_path.parent.mkdir(exist_ok=True)
                handler = logging.FileHandler(log_path)
                handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
                scraper_logger.addHandler(handler)
            
            # Update status to processing
            job_data['status'] = 'processing'
            job_data['processing_started_at'] = datetime.utcnow().isoformat() + 'Z'
            save_job(job_data)
            
            # Run the function directly
            try:
                result_data = run_batch_pipeline(
                    league_slug=league_slug,
                    year=year,
                    round_num=round_num,
                    job_id=job_id
                )
                
                # Update completion status
                job_data['status'] = result_data.get('status', 'completed')
                job_data['matches_scraped'] = result_data.get('matches_scraped', 0)
                job_data['total_matches'] = result_data.get('total_matches', 0)
                job_data['duration_seconds'] = result_data.get('duration_seconds', 0)
                job_data['completed_at'] = datetime.utcnow().isoformat() + 'Z'
                
            except Exception as inner_e:
                log_diagnostic(logger, 'Scraper function failed for job',
                    component=COMPONENT, operation='job_execute',
                    error=inner_e,
                    hint='The run_batch_pipeline raised an exception. Check crawler/scraper logs above for root cause.',
                    job_id=job_id, attempt=retry_count + 1, league=league_slug, round=round_num)
                
                if retry_count < MAX_RETRIES:
                    slog(logger, 'warning', 'Retrying failed job after delay', component=COMPONENT,
                         operation='job_retry', job_id=job_id, retry_count=retry_count + 1,
                         max_retries=MAX_RETRIES, delay_seconds=RETRY_DELAY)
                    job_data['status'] = 'queued'
                    job_data['retry_count'] = retry_count + 1
                    job_data['last_error'] = str(inner_e)
                    save_job(job_data)
                    
                    # Backoff sleep before re-queueing to avoid infinite rapid failure loops
                    time.sleep(RETRY_DELAY)
                    redis_client.rpush(KEY_QUEUE, json.dumps(job_data))
                    continue # Skip the rest of loop to not close handler yet? No, better close and reopen.
                else:
                    log_diagnostic(logger, 'Job permanently failed after all retries',
                        component=COMPONENT, operation='job_final_failure',
                        hint='All retry attempts exhausted. Review crawler and scraper diagnostic logs above for root cause.',
                        job_id=job_id, max_retries=MAX_RETRIES, last_error=str(inner_e))
                    job_data['status'] = 'failed'
                    job_data['error'] = str(inner_e)
                    job_data['completed_at'] = datetime.utcnow().isoformat() + 'Z'
            
            # Cleanup handler
            if handler:
                scraper_logger.removeHandler(handler)
                handler.close()
            
            save_job(job_data)
            slog(logger, 'info', 'Job finished', component=COMPONENT,
                 operation='job_complete', job_id=job_id, final_status=job_data['status'],
                 matches_scraped=job_data.get('matches_scraped'),
                 duration_seconds=job_data.get('duration_seconds'))
            
        except redis.ConnectionError:
            log_diagnostic(logger, 'Redis connection lost in worker',
                component=COMPONENT, operation='redis_connection',
                hint='Redis became unreachable. Worker will retry in 5s. If persistent, check REDIS_URL env var and Redis service health.')
            time.sleep(5)
        except Exception as e:
            log_diagnostic(logger, 'Unexpected worker loop error',
                component=COMPONENT, operation='worker_loop', error=e,
                hint='Unhandled exception in the main worker loop. This should not happen.')
    
    slog(logger, 'info', 'Scraping worker thread stopped', component=COMPONENT,
         operation='thread_stop')

def start_worker():
    """Start the background worker thread if not already running.
    Uses a Redis lock to ensure only ONE process (gunicorn worker) starts the thread.
    """
    global worker_thread, worker_running
    
    if worker_thread is not None and worker_thread.is_alive():
        return  # Already running in this process
    
    # Redis-based singleton: only one gunicorn worker should run the scrape thread
    try:
        acquired = redis_client.set(WORKER_LOCK_KEY, os.getpid(), nx=True, ex=WORKER_LOCK_TTL)
        if not acquired:
            slog(logger, 'info', 'Another worker process owns the scrape thread lock, skipping',
                 component=COMPONENT, operation='singleton_check')
            return
    except Exception as e:
        log_diagnostic(logger, 'Redis lock error, starting worker anyway as fallback',
            component=COMPONENT, operation='singleton_lock', error=e,
            hint='Could not acquire Redis lock. Starting worker regardless. Risk: duplicate workers if another process is also running.')
    
    # 1. Recovery first
    try:
        recover_stuck_jobs()
    except Exception as e:
        log_diagnostic(logger, 'Failed to recover stuck jobs on startup',
            component=COMPONENT, operation='recover_stuck_jobs', error=e,
            hint='Recovery failed but worker will still start. Stuck jobs may remain in processing state.')

    # 2. Start thread
    worker_running = True
    worker_thread = threading.Thread(target=scrape_worker, daemon=True, name="ScrapeWorker")
    worker_thread.start()
    slog(logger, 'info', 'Scraping worker thread initialized', component=COMPONENT,
         operation='thread_init', pid=os.getpid())


_worker_init_done = False

@scrape_bp.before_app_request
def _ensure_worker_started():
    """Lazily start the worker on first request instead of on module import."""
    global _worker_init_done
    if _worker_init_done:
        return
    _worker_init_done = True
    start_worker()

@scrape_bp.route('', methods=['POST'])
def start_scrape():
    """Start a scraping job (In-Process Reliable)"""
    data = request.get_json()
    
    league_slug = data.get('league')
    year = data.get('year')
    round_num = data.get('round')
    
    if not all([league_slug, year, round_num]):
        return jsonify({"error": "league, year, and round are required"}), 400
    
    # Validate league
    league = Liga.query.filter_by(ogol_slug=league_slug).first()
    if not league:
        return jsonify({"error": f"League '{league_slug}' not found"}), 400
    
    # Create job ID
    timestamp = int(time.time())
    job_id = f"scrape_{league_slug}_{year}_{round_num}_{timestamp}"
    
    # Log file
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"scrape_{league_slug}_{year}_r{round_num}.log"
    
    job_data = {
        'job_id': job_id,
        'league': league_slug,
        'league_name': league.nome,
        'year': year,
        'round': round_num,
        'status': 'queued',
        'enqueued_at': datetime.utcnow().isoformat() + 'Z',
        'log_file': str(log_file),
        'retry_count': 0
    }
    
    save_job(job_data)
    redis_client.rpush(KEY_QUEUE, json.dumps(job_data))
    
    return jsonify({
        "status": "queued",
        "job_id": job_id,
        "message": "Job enqueued (Reliable In-Process).",
        "log_file": str(log_file)
    }), 202

@scrape_bp.route('/status/<job_id>', methods=['GET'])
def get_status(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)

@scrape_bp.route('/jobs', methods=['GET'])
def list_jobs():
    jobs = load_jobs()
    job_list = list(jobs.values())
    job_list.sort(key=lambda x: x.get('enqueued_at', ''), reverse=True)
    return jsonify({"jobs": job_list, "total": len(job_list)})

@scrape_bp.route('/cancel/<job_id>', methods=['POST'])
def cancel_job(job_id):
    """Note: Termination of thread-based jobs is not supported safely in Python."""
    return jsonify({"error": "Cancellation not supported for in-process jobs"}), 400

@scrape_bp.route('/queue', methods=['GET'])
def get_queue_status():
    try:
        q_size = redis_client.llen(KEY_QUEUE)
    except:
        q_size = 0
    return jsonify({
        "queue_size": q_size,
        "worker_running": worker_running,
        "worker_active": worker_thread.is_alive() if worker_thread else False
    })

@scrape_bp.route('/flush', methods=['DELETE'])
def flush_queue():
    redis_client.delete(KEY_QUEUE)
    redis_client.delete(KEY_JOBS)
    return jsonify({"message": "Queue flushed"})
