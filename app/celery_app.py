import os
from celery import Celery

def create_celery_app(app=None):
    """
    Creates and configures a Celery instance.
    If a Flask app is provided, it configures Celery to match the app's config.
    """
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    celery = Celery(
        'br_stats_hub',
        broker=redis_url,
        backend=redis_url,
        include=['app.tasks']
    )
    
    # Optional: Update celery config from Flask app config if needed
    if app:
        celery.conf.update(app.config)
        
    class ContextTask(celery.Task):
        """Ensure tasks run within the Flask app context"""
        def __call__(self, *args, **kwargs):
            if app:
                with app.app_context():
                    return self.run(*args, **kwargs)
            return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

# Global celery instance for the worker to find
# This is what's used in the command line: celery -A app.celery_app worker
celery_app = create_celery_app()
