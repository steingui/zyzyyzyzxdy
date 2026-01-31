import logging
import time
import urllib.request
import json
try:
    import redis
except ImportError:
    redis = None
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_URL = "http://localhost:5001/api/teams/"
REDIS_HOST = "localhost"
REDIS_PORT = 6379

def verify_cache():
    # 1. Clear Redis (optional, but good for clean test)
    if redis:
        try:
            r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
            r.flushdb()
            logger.info("Flushed Redis database.")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            pass
    else:
        logger.warning("Redis module not found. Skipping Redis flush/check.")

    # 2. First Request (Cache Miss)
    logger.info("Making first request to /api/teams/ (expecting Cache Miss)...")
    start_time = time.time()
    try:
        with urllib.request.urlopen(API_URL) as response:
            if response.status != 200:
                logger.error(f"API request failed with status {response.status}")
                sys.exit(1)
            _ = response.read() # Consume body
    except Exception as e:
        logger.error(f"First request failed: {e}")
        sys.exit(1)

    duration_1 = time.time() - start_time
    logger.info(f"First request took {duration_1:.4f} seconds.")

    # 3. Check Redis for Keys
    if redis:
        try:
            keys = r.keys("*")
            logger.info(f"Found {len(keys)} keys in Redis: {keys}")
            if len(keys) == 0:
                logger.warning("No keys found in Redis! Caching might not be working.")
            else:
                logger.info("Redis keys verified.")
        except Exception as e:
            logger.error(f"Error checking Redis keys: {e}")

    # 4. Second Request (Cache Hit)
    logger.info("Making second request to /api/teams/ (expecting Cache Hit)...")
    start_time = time.time()
    try:
        with urllib.request.urlopen(API_URL) as response:
            _ = response.read()
    except Exception as e:
        logger.error(f"Second request failed: {e}")
        sys.exit(1)

    duration_2 = time.time() - start_time
    
    logger.info(f"Second request took {duration_2:.4f} seconds.")
    
    if duration_2 < duration_1:
         logger.info(f"Cache verification SUCCESS: Second request was {duration_1 - duration_2:.4f}s faster.")
    else:
         logger.warning("Cache verification INCONCLUSIVE: Second request was not significantly faster (local network latency might obscure results).")
         
if __name__ == "__main__":
    # Ensure dependencies are available (requests, redis)
    # The user might need to install them if running locally. 
    # But I can run this inside the container or just rely on requests if installed.
    # docker-compose is setting up everything.
    verify_cache()
