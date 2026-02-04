#!/usr/bin/env python3
"""
scrape.py - API endpoints for remote scraping pipeline triggering with Redis

Queue-based system (Redis):
- POST /api/scrape enqueues job to 'scrape:queue' (returns 202 immediately)
- Background worker thread processes queue from Redis
- Jobs metadata stored in Redis Hash 'scrape:jobs'
- Persistent across restarts

Endpoints:
- POST /api/scrape - Enqueue a scraping job
- GET /api/scrape/status/<job_id> - Get job status
- GET /api/scrape/jobs - List all jobs
- GET /api/scrape/queue - View pending queue
"""

import subprocess
import os
import json
import time
import signal
import threading
import redis
from pathlib import Path
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from app.models import db, Liga


scrape_bp = Blueprint('scrape', __name__, url_prefix='/api/scrape')

# Logging
from app.utils.logger import get_logger
logger = get_logger(__name__)

# Redis Configuration
REDIS_URL = os.getenv('REDIS_URL')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

# Initialize Redis
try:
    if REDIS_URL:
        logger.info(f"🔌 Connecting to Redis via REDIS_URL...")
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    else:
        logger.info(f"🔌 Connecting to Redis via {REDIS_HOST}:{REDIS_PORT}...")
        redis_client = redis.Redis(
            host=REDIS_HOST, 
            port=REDIS_PORT, 
            db=REDIS_DB, 
            decode_responses=True
        )
    # Ping to check connection
    redis_client.ping()
    logger.info(f"✅ Redis connected at {REDIS_HOST}:{REDIS_PORT}")
except Exception as e:
    logger.error(f"❌ Failed to connect to Redis: {e}")
    # We continue, but worker will fail loop if not connected

# Redis Keys
KEY_JOBS = "scrape:jobs"
KEY_QUEUE = "scrape:queue"

# Global worker thread control
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


def is_process_running(pid):
    """Check if process is still running"""
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def scrape_worker():
    """
    Background worker that processes scraping jobs from Redis queue.
    """
    global worker_running
    worker_running = True
    
    logger.info("🔧 Scraping worker thread started (Redis backed)")
    
    while worker_running:
        try:
            # BLPOP blocks until item is available or timeout
            # Returns tuple (key, value) or None
            item = redis_client.blpop(KEY_QUEUE, timeout=1)
            
            if not item:
                continue
                
            _, job_json = item
            job_data = json.loads(job_json)
            
            job_id = job_data['job_id']
            # Refresh job data from Hash to get latest status
            current_job = get_job(job_id)
            if current_job and current_job.get('status') == 'cancelled':
                logger.info("Skipping cancelled job", extra={"job_id": job_id})
                continue

            # If job not in Hash, use the one from queue (fallback)
            if not current_job:
                current_job = job_data

            league_slug = current_job['league']
            year = current_job['year']
            round_num = current_job['round']
            log_file = current_job['log_file']
            cmd = current_job['cmd']
            
            logger.info("🚀 Processing Job", extra={
                "job_id": job_id,
                "league": league_slug,
                "year": year,
                "round": round_num,
                "log_file": log_file,
                "cmd": cmd
            })
            
            # Update job status to running
            current_job['status'] = 'processing'
            current_job['processing_started_at'] = datetime.utcnow().isoformat() + 'Z'
            save_job(current_job)
            
            # Run scraping with live output to console
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=os.getcwd(),
                universal_newlines=True,
                bufsize=1
            )
            
            # Save PID to allow cancellation
            current_job['pid'] = process.pid
            save_job(current_job)
            
            # Stream logs to console in real-time
            for line in process.stdout:
                logger.info(line.strip(), extra={"job_id": job_id, "source": "subprocess"})
            
            process.wait()
            exit_code = process.returncode
            
            # Update job status
            current_job = get_job(job_id) or current_job # reload in case of updates
            
            current_job['status'] = 'completed' if exit_code == 0 else 'failed'
            current_job['completed_at'] = datetime.utcnow().isoformat() + 'Z'
            current_job['exit_code'] = exit_code
            
            if 'processing_started_at' in current_job and 'completed_at' in current_job:
                start = datetime.fromisoformat(current_job['processing_started_at'].replace('Z', ''))
                end = datetime.fromisoformat(current_job['completed_at'].replace('Z', ''))
                current_job['duration_seconds'] = int((end - start).total_seconds())
            
            save_job(current_job)
            
            logger.info(f"{'✅' if exit_code == 0 else '❌'} Job Completed", extra={
                "job_id": job_id,
                "exit_code": exit_code,
                "status": "success" if exit_code == 0 else "failed"
            })
            
        except redis.ConnectionError:
            logger.error("❌ Redis connection lost in worker. Retrying...")
            time.sleep(5)
        except Exception as e:
            logger.error("❌ Worker error", extra={"error": str(e)}, exc_info=True)
    
    logger.info("🛑 Scraping worker thread stopped")


def start_worker():
    """Start the background worker thread if not already running"""
    global worker_thread, worker_running
    
    if worker_thread is None or not worker_thread.is_alive():
        worker_running = True
        worker_thread = threading.Thread(target=scrape_worker, daemon=True, name="ScrapeWorker")
        worker_thread.start()
        logger.info("✅ Scraping worker thread initialized")


# Start worker on module import
start_worker()


@scrape_bp.route('', methods=['POST'])
def start_scrape():
    """Start a scraping job"""
    data = request.get_json()
    
    # Validate input
    league_slug = data.get('league')
    year = data.get('year')
    round_num = data.get('round')
    sync_mode = data.get('sync', False)
    
    if not league_slug:
        return jsonify({"error": "league is required"}), 400
    
    if not year:
        return jsonify({"error": "year is required"}), 400
    
    if not round_num:
        return jsonify({"error": "round is required"}), 400
    
    if not isinstance(round_num, int) or round_num < 1:
        return jsonify({"error": "round must be a positive integer"}), 400
    
    # Validate league exists
    league = Liga.query.filter_by(ogol_slug=league_slug).first()
    if not league:
        return jsonify({
            "error": f"League '{league_slug}' not found",
            "available_leagues": [l.ogol_slug for l in Liga.query.all()]
        }), 400
    
    # Validate round range
    if round_num > league.num_rodadas:
        return jsonify({
            "error": f"Round {round_num} exceeds maximum for {league.nome} ({league.num_rodadas} rounds)"
        }), 400
    
    # Check if already running (Redis)
    jobs = load_jobs()
    for existing_job in jobs.values():
        if (existing_job.get('league') == league_slug and 
            existing_job.get('year') == year and 
            existing_job.get('round') == round_num and 
            existing_job.get('status') in ['queued', 'processing']):
            
            # Verify if really processing (stale check) - logic simplified for phase 1 Redis
            current_app.logger.warning(f"Duplicate job detected: {existing_job.get('job_id')}")
            return jsonify({
                "message": "Job already exists in queue/processing",
                "job_id": existing_job.get('job_id'),
                "status": existing_job.get('status')
            }), 409
  
    # Create job ID
    timestamp = int(time.time())
    job_id = f"scrape_{league_slug}_{year}_{round_num}_{timestamp}"
    
    # Prepare log file
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"scrape_{league_slug}_{year}_r{round_num}.log"
    
    # Command
    cmd = [
        "python3", "scripts/run_batch.py",
        str(round_num),
        "--league", league_slug,
        "--year", str(year)
    ]
    
    current_app.logger.info(f"Enqueuing scrape job: {job_id}")
    
    try:
        job_data = {
            'job_id': job_id,
            'league': league_slug,
            'league_name': league.nome,
            'year': year,
            'round': round_num,
            'status': 'queued',
            'enqueued_at': datetime.utcnow().isoformat() + 'Z',
            'log_file': str(log_file),
            'cmd': cmd,
            'matches_scraped': 0,
            'matches_failed': 0
        }
        
        # Save to Redis Metadata
        save_job(job_data)
        
        # Push to Redis Queue
        redis_client.rpush(KEY_QUEUE, json.dumps(job_data))
        
        return jsonify({
            "status": "queued",
            "job_id": job_id,
            "message": "Job enqueued successfully (Redis).",
            "log_file": str(log_file)
        }), 202
        
    except Exception as e:
        current_app.logger.error(f"Failed to start scrape job: {e}")
        return jsonify({
            "error": "Failed to start scraping job",
            "details": str(e)
        }), 500


@scrape_bp.route('/status/<job_id>', methods=['GET'])
def get_status(job_id):
    """Get status of a scraping job from Redis"""
    job = get_job(job_id)
    
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    # Clean up stale jobs
    if job.get('status') == 'processing':
        pid = job.get('pid')
        if pid and not is_process_running(pid):
            # Process died? Mark completed/failed
            job['status'] = 'completed' # Assume success/finished logic for now
            job['completed_at'] = datetime.utcnow().isoformat() + 'Z'
            save_job(job)
    
    return jsonify(job)


@scrape_bp.route('/jobs', methods=['GET'])
def list_jobs():
    """List all scraping jobs from Redis"""
    jobs = load_jobs()
    
    # Filters
    status_filter = request.args.get('status')
    league_filter = request.args.get('league')
    limit = int(request.args.get('limit', 50))
    
    filtered_jobs = list(jobs.values())
    
    if status_filter:
        filtered_jobs = [j for j in filtered_jobs if j.get('status') == status_filter]
    
    if league_filter:
        filtered_jobs = [j for j in filtered_jobs if j.get('league') == league_filter]
    
    # Sort by enqueued_at desc (newest first)
    filtered_jobs.sort(key=lambda x: x.get('enqueued_at', ''), reverse=True)
    
    # Limit
    filtered_jobs = filtered_jobs[:limit]
    
    return jsonify({
        "total": len(filtered_jobs),
        "jobs": filtered_jobs
    })


@scrape_bp.route('/cancel/<job_id>', methods=['POST'])
def cancel_job(job_id):
    """Cancel a running scraping job"""
    job = get_job(job_id)
    
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    if job.get('status') not in ['running', 'processing']:
        return jsonify({"error": "Job is not running"}), 400
    
    pid = job.get('pid')
    if pid and is_process_running(pid):
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            current_app.logger.info(f"Sent SIGTERM to process group {pid}")
        except Exception as e:
            current_app.logger.warning(f"Failed to kill process {pid}: {e}")
    
    job['status'] = 'cancelled'
    job['cancelled_at'] = datetime.utcnow().isoformat() + 'Z'
    save_job(job)
    
    return jsonify({
        "status": "cancelled",
        "job_id": job_id,
        "message": "Job cancelled successfully"
    })


@scrape_bp.route('/queue', methods=['GET'])
def get_queue_status():
    """Get current queue status"""
    try:
        q_size = redis_client.llen(KEY_QUEUE)
    except:
        q_size = -1
        
    jobs = load_jobs()
    processing_job = next(
        (job for job in jobs.values() if job.get('status') == 'processing'),
        None
    )
    
    # Note: 'worker_alive' is local to this thread, works for single instance
    return jsonify({
        "queue_size": q_size,
        "processing_job": processing_job,
        "worker_running": worker_running,
        "worker_alive": worker_thread.is_alive() if worker_thread else False
    })


@scrape_bp.route('/flush', methods=['DELETE'])
def flush_queue():
    """Flush the scraping queue and job history (Admin utility)"""
    try:
        # Clear main queue and jobs hash
        redis_client.delete(KEY_QUEUE)
        redis_client.delete(KEY_JOBS)
        
        return jsonify({
            "message": "Redis queue and job history flushed successfully.",
            "keys_deleted": [KEY_QUEUE, KEY_JOBS]
        }), 200
    except Exception as e:
        return jsonify({
            "error": "Failed to flush Redis",
            "details": str(e)
        }), 500
