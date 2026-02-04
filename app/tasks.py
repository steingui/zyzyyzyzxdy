import os
import json
import redis
from datetime import datetime
from app.celery_app import celery_app
from scripts.run_batch import run_batch_pipeline

# Redis Configuration (to stay in sync with custom tracking)
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
KEY_JOBS = "scrape:jobs"

@celery_app.task(bind=True)
def scrape_job(self, league_slug, year, round_num, job_id):
    """
    Celery task that executes the scraping pipeline.
    Updates the custom Redis Hash to keep compatibility with existing API.
    """
    # 1. Update status to processing
    try:
        job_data_raw = redis_client.hget(KEY_JOBS, job_id)
        if job_data_raw:
            job_data = json.loads(job_data_raw)
            job_data['status'] = 'processing'
            job_data['processing_started_at'] = datetime.utcnow().isoformat() + 'Z'
            job_data['celery_task_id'] = self.request.id
            redis_client.hset(KEY_JOBS, job_id, json.dumps(job_data))
    except Exception as e:
        print(f"Error updating job status: {e}")

    # 2. Run the actual pipeline
    try:
        result = run_batch_pipeline(
            league_slug=league_slug, 
            year=year, 
            round_num=round_num, 
            job_id=job_id
        )
        
        # 3. Update status to completed
        job_data_raw = redis_client.hget(KEY_JOBS, job_id)
        if job_data_raw:
            job_data = json.loads(job_data_raw)
            job_data['status'] = result.get('status', 'completed')
            job_data['completed_at'] = datetime.utcnow().isoformat() + 'Z'
            job_data['matches_scraped'] = result.get('matches_scraped', 0)
            job_data['total_matches'] = result.get('total_matches', 0)
            job_data['duration_seconds'] = result.get('duration_seconds', 0)
            redis_client.hset(KEY_JOBS, job_id, json.dumps(job_data))
            
        return result
        
    except Exception as e:
        # 4. Handle failure
        job_data_raw = redis_client.hget(KEY_JOBS, job_id)
        if job_data_raw:
            job_data = json.loads(job_data_raw)
            job_data['status'] = 'failed'
            job_data['error'] = str(e)
            job_data['completed_at'] = datetime.utcnow().isoformat() + 'Z'
            redis_client.hset(KEY_JOBS, job_id, json.dumps(job_data))
        raise e
