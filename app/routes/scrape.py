#!/usr/bin/env python3
"""
scrape.py - API endpoints for remote scraping pipeline triggering

Queue-based system:
- POST /api/scrape enqueues job (returns 202 immediately)
- Background worker thread processes queue sequentially
- Logs appear in API console in real-time
- Prevents overwhelming the server with concurrent scrapes

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
import queue
from pathlib import Path
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from app.models import db, League

scrape_bp = Blueprint('scrape', __name__, url_prefix='/api/scrape')

JOBS_FILE = Path('data/scrape_jobs.json')
JOBS_FILE.parent.mkdir(exist_ok=True)

# Global task queue and worker thread
scrape_queue = queue.Queue()
worker_thread = None
worker_running = False


def load_jobs():
    """Load jobs from JSON file"""
    if JOBS_FILE.exists():
        try:
            with open(JOBS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            current_app.logger.warning("Invalid jobs file, starting fresh")
            return {}
    return {}


def save_jobs(jobs):
    """Save jobs to JSON file"""
    with open(JOBS_FILE, 'w') as f:
        json.dump(jobs, f, indent=2)


def is_process_running(pid):
    """Check if process is still running"""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def scrape_worker():
    """
    Background worker that processes scraping jobs from the queue.
    Jobs are processed sequentially (one at a time) with live logs.
    """
    global worker_running
    worker_running = True
    
    print("🔧 Scraping worker thread started")
    
    while worker_running:
        try:
            # Wait for job (blocks until available, timeout for clean shutdown)
            job_data = scrape_queue.get(timeout=1)
            
            job_id = job_data['job_id']
            league_slug = job_data['league']
            year = job_data['year']
            round_num = job_data['round']
            log_file = job_data['log_file']
            cmd = job_data['cmd']
            
            print(f"\n{'='*60}")
            print(f"🚀 PROCESSING JOB: {job_id}")
            print(f"📋 League: {league_slug} | Year: {year} | Round: {round_num}")
            print(f"📂 Log file: {log_file}")
            print(f"⚙️  Command: {' '.join(cmd)}")
            print(f"{'='*60}\n")
            
            # Update job status to running
            jobs = load_jobs()
            if job_id in jobs:
                jobs[job_id]['status'] = 'processing'
                jobs[job_id]['processing_started_at'] = datetime.utcnow().isoformat() + 'Z'
                save_jobs(jobs)
            
            # Run scraping with live output to console
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=os.getcwd(),
                universal_newlines=True,
                bufsize=1
            )
            
            # Stream logs to console in real-time
            for line in process.stdout:
                print(f"[SCRAPE] {line.rstrip()}")
            
            process.wait()
            exit_code = process.returncode
            
            # Update job status
            jobs = load_jobs()
            if job_id in jobs:
                jobs[job_id]['status'] = 'completed' if exit_code == 0 else 'failed'
                jobs[job_id]['completed_at'] = datetime.utcnow().isoformat() + 'Z'
                jobs[job_id]['exit_code'] = exit_code
                
                if 'processing_started_at' in jobs[job_id] and 'completed_at' in jobs[job_id]:
                    start = datetime.fromisoformat(jobs[job_id]['processing_started_at'].replace('Z', ''))
                    end = datetime.fromisoformat(jobs[job_id]['completed_at'].replace('Z', ''))
                    jobs[job_id]['duration_seconds'] = int((end - start).total_seconds())
                
                save_jobs(jobs)
            
            print(f"\n{'='*60}")
            print(f"{'✅' if exit_code == 0 else '❌'} JOB COMPLETED: {job_id}")
            print(f"Exit code: {exit_code}")
            print(f"{'='*60}\n")
            
            scrape_queue.task_done()
            
        except queue.Empty:
            # Timeout, continue loop (allows clean shutdown)
            continue
        except Exception as e:
            print(f"❌ Worker error: {e}")
            scrape_queue.task_done()
    
    print("🛑 Scraping worker thread stopped")


def start_worker():
    """Start the background worker thread if not already running"""
    global worker_thread, worker_running
    
    if worker_thread is None or not worker_thread.is_alive():
        worker_running = True
        worker_thread = threading.Thread(target=scrape_worker, daemon=True, name="ScrapeWorker")
        worker_thread.start()
        print("✅ Scraping worker thread initialized")


# Start worker on module import
start_worker()


@scrape_bp.route('', methods=['POST'])
def start_scrape():
    """
    Start a scraping job for league/round
    
    Request Body:
    {
        "league": "brasileirao",  // ogol_slug from leagues table
        "year": 2026,
        "round": 1,
        "sync": false  // NEW: if true, runs synchronously with live logs (blocks API)
    }
    
    Returns:
        202: Job started successfully (async mode)
        200: Job completed successfully (sync mode)
        400: Invalid parameters
        409: Job already running for this league/round
        429: Rate limit exceeded
    """
    data = request.get_json()
    
    # Validate input
    league_slug = data.get('league', 'brasileirao')
    year = data.get('year', 2026)
    round_num = data.get('round')
    sync_mode = data.get('sync', False)  # NEW: sync mode flag
    
    if not round_num:
        return jsonify({"error": "round is required"}), 400
    
    if not isinstance(round_num, int) or round_num < 1:
        return jsonify({"error": "round must be a positive integer"}), 400
    
    # Validate league exists
    league = League.query.filter_by(ogol_slug=league_slug).first()
    if not league:
        return jsonify({
            "error": f"League '{league_slug}' not found",
            "available_leagues": [l.ogol_slug for l in League.query.all()]
        }), 400
    
    # Validate round range
    if round_num > league.num_rounds:
        return jsonify({
            "error": f"Round {round_num} exceeds maximum for {league.name} ({league.num_rounds} rounds)"
        }), 400
    
    # Check if already running
    jobs = load_jobs()
    # Check for duplicate jobs (jobs is a list)
    for existing_job in jobs.values():
        if (existing_job.get('league') == league_slug and 
            existing_job.get('year') == year and 
            existing_job.get('round') == round_num and 
            existing_job.get('status') in ['queued', 'processing']):
            
            current_app.logger.warning(f"Duplicate job detected: {existing_job.get('job_id')}")
            return jsonify({
                "message": "Job already exists in queue",
                "job_id": existing_job.get('job_id'),
                "status": existing_job.get('status'),
                "queue_position": existing_job.get('queue_position')
            }), 409  # Conflict
  
    # Create job ID
    timestamp = int(time.time())
    job_id = f"scrape_{league_slug}_{year}_{round_num}_{timestamp}"
    
    # Prepare log file
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"scrape_{league_slug}_{year}_r{round_num}.log"
    
    # Start subprocess
    cmd = [
        "python3", "scripts/run_batch.py",
        str(round_num),
        "--league", league_slug,
        "--year", str(year)
    ]
    
    current_app.logger.info(f"Enqueuing scrape job: {job_id}")
    current_app.logger.info(f"Command: {' '.join(cmd)}")
    current_app.logger.info(f"Queue size: {scrape_queue.qsize()}")
    
    try:
        # Enqueue job (non-blocking)
        job_data = {
            'job_id': job_id,
            'league': league_slug,
            'year': year,
            'round': round_num,
            'log_file': str(log_file),
            'cmd': cmd
        }
        
        scrape_queue.put(job_data)
        
        # Save job metadata
        jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "league": league_slug,
            "league_name": league.name,
            "year": year,
            "round": round_num,
            "enqueued_at": datetime.utcnow().isoformat() + 'Z',
            "queue_position": scrape_queue.qsize(),
            "log_file": str(log_file),
            "matches_scraped": 0,
            "matches_failed": 0
        }
        save_jobs(jobs)
        
        return jsonify({
            "status": "queued",
            "job_id": job_id,
            "league": league_slug,
            "league_name": league.name,
            "year": year,
            "round": round_num,
            "message": "Job enqueued successfully. Worker will process it soon.",
            "queue_position": scrape_queue.qsize(),
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
    """
    Get status of a scraping job
    
    Returns:
        200: Job status
        404: Job not found
    """
    jobs = load_jobs()
    job = jobs.get(job_id)
    
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    # Update status if process finished
    if job['status'] == 'running':
        if not is_process_running(job.get('pid', 0)):
            job['status'] = 'completed'
            job['completed_at'] = datetime.utcnow().isoformat() + 'Z'
            
            # Calculate duration
            if 'started_at' in job and 'completed_at' in job:
                start = datetime.fromisoformat(job['started_at'].replace('Z', ''))
                end = datetime.fromisoformat(job['completed_at'].replace('Z', ''))
                job['duration_seconds'] = int((end - start).total_seconds())
            
            jobs[job_id] = job
            save_jobs(jobs)
    
    return jsonify(job)


@scrape_bp.route('/jobs', methods=['GET'])
def list_jobs():
    """
    List all scraping jobs
    
    Query params:
    - status: filter by status (running, completed, failed)
    - league: filter by league
    - limit: max results (default: 50)
    
    Returns:
        200: List of jobs
    """
    jobs = load_jobs()
    
    # Filters
    status_filter = request.args.get('status')
    league_filter = request.args.get('league')
    limit = int(request.args.get('limit', 50))
    
    # Update running jobs status
    for job_id, job in jobs.items():
        if job['status'] == 'running' and not is_process_running(job.get('pid', 0)):
            job['status'] = 'completed'
            job['completed_at'] = datetime.utcnow().isoformat() + 'Z'
    
    save_jobs(jobs)
    
    # Apply filters
    filtered_jobs = list(jobs.values())
    
    if status_filter:
        filtered_jobs = [j for j in filtered_jobs if j['status'] == status_filter]
    
    if league_filter:
        filtered_jobs = [j for j in filtered_jobs if j['league'] == league_filter]
    
    # Sort by started_at desc
    filtered_jobs.sort(key=lambda x: x.get('started_at', ''), reverse=True)
    
    # Limit
    filtered_jobs = filtered_jobs[:limit]
    
    return jsonify({
        "total": len(filtered_jobs),
        "jobs": filtered_jobs
    })


@scrape_bp.route('/cancel/<job_id>', methods=['POST'])
def cancel_job(job_id):
    """
    Cancel a running scraping job
    
    Returns:
        200: Job cancelled
        404: Job not found
        400: Job not running
    """
    jobs = load_jobs()
    job = jobs.get(job_id)
    
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    if job['status'] != 'running':
        return jsonify({"error": "Job is not running"}), 400
    
    pid = job.get('pid')
    if pid and is_process_running(pid):
        try:
            # Kill process group
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            
            job['status'] = 'cancelled'
            job['cancelled_at'] = datetime.utcnow().isoformat() + 'Z'
            jobs[job_id] = job
            save_jobs(jobs)
            
            current_app.logger.info(f"Cancelled job: {job_id}")
            
            return jsonify({
                "status": "cancelled",
                "job_id": job_id,
                "message": "Job cancelled successfully"
            })
        except Exception as e:
            current_app.logger.error(f"Failed to cancel job {job_id}: {e}")
            return jsonify({
                "error": "Failed to cancel job",
                "details": str(e)
            }), 500
    else:
        job['status'] = 'completed'
        jobs[job_id] = job
        save_jobs(jobs)
        
        return jsonify({
            "error": "Process already finished"
        }), 400


@scrape_bp.route('/queue', methods=['GET'])
def get_queue_status():
    """
    Get current queue status
    
    Returns:
        200: Queue information
    """
    jobs = load_jobs()
    
    queued_jobs = [
        {
            'job_id': job['job_id'],
            'league': job['league'],
            'year': job['year'],
            'round': job['round'],
            'enqueued_at': job.get('enqueued_at'),
            'queue_position': idx + 1
        }
        for idx, (job_id, job) in enumerate(jobs.items())
        if job.get('status') == 'queued'
    ]
    
    processing_job = next(
        (job for job in jobs.values() if job.get('status') == 'processing'),
        None
    )
    
    return jsonify({
        "queue_size": scrape_queue.qsize(),
        "queued_jobs": queued_jobs,
        "processing_job": processing_job,
        "worker_running": worker_running,
        "worker_alive": worker_thread.is_alive() if worker_thread else False
    })
