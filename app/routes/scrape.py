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
    if REDIS_URL:
        # Hide password in logs if present
        safe_url = REDIS_URL.split('@')[-1] if '@' in REDIS_URL else REDIS_URL
        logger.info(f"✅ Redis connected via REDIS_URL ({safe_url})")
    else:
        logger.info(f"✅ Redis connected at {REDIS_HOST}:{REDIS_PORT}")
except Exception as e:
    logger.error(f"❌ Failed to connect to Redis: {e}")
    # We continue, but worker will fail loop if not connected

# Redis Keys
KEY_JOBS = "scrape:jobs"

# Import Celery task
from app.tasks import scrape_job


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


@scrape_bp.route('', methods=['POST'])
def start_scrape():
    """Start a scraping job via Celery"""
    data = request.get_json()
    
    # Validate input
    league_slug = data.get('league')
    year = data.get('year')
    round_num = data.get('round')
    
    if not all([league_slug, year, round_num]):
        return jsonify({"error": "league, year, and round are required"}), 400
    
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
            
            return jsonify({
                "message": "Job already exists in queue/processing",
                "job_id": existing_job.get('job_id'),
                "status": existing_job.get('status')
            }), 409
  
    # Create job ID
    timestamp = int(time.time())
    job_id = f"scrape_{league_slug}_{year}_{round_num}_{timestamp}"
    
    # Prepare log file path
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"scrape_{league_slug}_{year}_r{round_num}.log"
    
    current_app.logger.info(f"Triggering Celery scrape job: {job_id}")
    
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
            'matches_scraped': 0,
            'total_matches': 0
        }
        
        # Save to Redis Metadata
        save_job(job_data)
        
        # Trigger Celery Task
        task = scrape_job.delay(league_slug, year, round_num, job_id)
        
        # Update metadata with Celery task ID
        job_data['celery_task_id'] = task.id
        save_job(job_data)
        
        return jsonify({
            "status": "queued",
            "job_id": job_id,
            "celery_task_id": task.id,
            "message": "Job enqueued successfully (Celery).",
            "log_file": str(log_file)
        }), 202
        
    except Exception as e:
        current_app.logger.error(f"Failed to trigger Celery job: {e}")
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
    """Cancel a running scraping job via Celery"""
    job = get_job(job_id)
    
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    if job.get('status') not in ['queued', 'processing']:
        return jsonify({"error": "Job is not running or queued"}), 400
    
    task_id = job.get('celery_task_id')
    if task_id:
        from app.celery_app import celery_app
        celery_app.control.revoke(task_id, terminate=True, signal='SIGTERM')
        logger.info(f"Revoked Celery task {task_id}")
    
    job['status'] = 'cancelled'
    job['cancelled_at'] = datetime.utcnow().isoformat() + 'Z'
    save_job(job)
    
    return jsonify({
        "status": "cancelled",
        "job_id": job_id,
        "message": "Job cancellation request sent to Celery"
    })


@scrape_bp.route('/queue', methods=['GET'])
def get_queue_status():
    """Get current queue status (simplified for Celery)"""
    jobs = load_jobs()
    processing_job = next(
        (job for job in jobs.values() if job.get('status') == 'processing'),
        None
    )
    
    return jsonify({
        "processing_job": processing_job,
        "celery_active": True # Assumption if the API is up and using Celery
    })


@scrape_bp.route('/flush', methods=['DELETE'])
def flush_queue():
    """Flush the job history hash from Redis (Admin utility)"""
    try:
        # Clear jobs hash
        redis_client.delete(KEY_JOBS)
        
        return jsonify({
            "message": "Redis job history flushed successfully.",
            "keys_deleted": [KEY_JOBS]
        }), 200
    except Exception as e:
        return jsonify({
            "error": "Failed to flush Redis",
            "details": str(e)
        }), 500
