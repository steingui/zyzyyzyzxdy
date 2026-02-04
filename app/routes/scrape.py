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
from app.utils.logger import get_logger
logger = get_logger(__name__)

# Redis Configuration
REDIS_URL = os.getenv('REDIS_URL', os.getenv('CACHE_REDIS_URL', 'redis://localhost:6379/0'))
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# Redis Keys
KEY_QUEUE = "scrape:queue"
KEY_JOBS = "scrape:jobs"

# Constants
MAX_RETRIES = 3
RETRY_DELAY = 10 # Seconds

# Worker controls (In-process thread)
worker_thread = None
worker_running = False

def get_job(job_id):
    """Get single job from Redis"""
    try:
        data = redis_client.hget(KEY_JOBS, job_id)
        return json.loads(data) if data else None
    except Exception as e:
        logger.error("Redis error in get_job", extra={"error": str(e)})
        return None

def save_job(job_data):
    """Save/Update single job in Redis"""
    try:
        job_id = job_data['job_id']
        redis_client.hset(KEY_JOBS, job_id, json.dumps(job_data))
    except Exception as e:
        logger.error("Redis error in save_job", extra={"error": str(e)})

def load_jobs():
    """Load all jobs from Redis"""
    try:
        raw = redis_client.hgetall(KEY_JOBS)
        return {k: json.loads(v) for k, v in raw.items()}
    except Exception as e:
        logger.error("Redis error in load_jobs", extra={"error": str(e)})
        return {}

def recover_stuck_jobs():
    """
    On startup, find jobs that were in 'processing' or 'queued' but 
    never finished (app crash) and put them back in the queue.
    """
    logger.info("🔍 Checking for stuck jobs...")
    jobs = load_jobs()
    recovered_count = 0
    
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
                logger.warning(f"🔄 Recovering stuck job: {job_id} (Status: {status})")
                job_data['status'] = 'queued'
                job_data['recovered_at'] = datetime.utcnow().isoformat() + 'Z'
                save_job(job_data)
                redis_client.lpush(KEY_QUEUE, json.dumps(job_data))
                recovered_count += 1
    
    if recovered_count > 0:
        logger.info(f"✅ Recovered {recovered_count} stuck jobs.")
    else:
        logger.info("✨ No stuck jobs found.")

def scrape_worker():
    """
    Background worker that consumes a Redis list queue.
    Runs one job at a time in-process with Retry logic.
    """
    global worker_running
    logger.info("🚀 Scraping worker thread started (In-Process Reliable)")
    
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
            
            logger.info(f"👷 processing job {job_id} (Attempt {retry_count + 1})")
            
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
                logger.error(f"❌ Scraper function failed for {job_id}: {inner_e}")
                
                if retry_count < MAX_RETRIES:
                    logger.warning(f"🔄 Retrying job {job_id} in {RETRY_DELAY}s... ({retry_count + 1}/{MAX_RETRIES})")
                    job_data['status'] = 'queued'
                    job_data['retry_count'] = retry_count + 1
                    job_data['last_error'] = str(inner_e)
                    save_job(job_data)
                    
                    # Backoff sleep before re-queueing to avoid infinite rapid failure loops
                    time.sleep(RETRY_DELAY)
                    redis_client.rpush(KEY_QUEUE, json.dumps(job_data))
                    continue # Skip the rest of loop to not close handler yet? No, better close and reopen.
                else:
                    logger.error(f"💀 Job {job_id} failed after {MAX_RETRIES} retries.")
                    job_data['status'] = 'failed'
                    job_data['error'] = str(inner_e)
                    job_data['completed_at'] = datetime.utcnow().isoformat() + 'Z'
            
            # Cleanup handler
            if handler:
                scraper_logger.removeHandler(handler)
                handler.close()
            
            save_job(job_data)
            logger.info(f"✅ Job {job_id} finished with status {job_data['status']}")
            
        except redis.ConnectionError:
            logger.error("❌ Redis connection lost in worker. Retrying...")
            time.sleep(5)
        except Exception as e:
            logger.error("❌ Worker loop error", extra={"error": str(e)}, exc_info=True)
    
    logger.info("🛑 Scraping worker thread stopped")

def start_worker():
    """Start the background worker thread if not already running"""
    global worker_thread, worker_running
    
    if worker_thread is None or not worker_thread.is_alive():
        # 1. Recovery first
        try:
            recover_stuck_jobs()
        except Exception as e:
            logger.error(f"Failed to recover stuck jobs: {e}")

        # 2. Start thread
        worker_running = True
        worker_thread = threading.Thread(target=scrape_worker, daemon=True, name="ScrapeWorker")
        worker_thread.start()
        logger.info("✅ Scraping worker thread initialized")

# Start worker on module import
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
