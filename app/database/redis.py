import os
import redis
import logging

logger = logging.getLogger(__name__)

def get_redis_client():
    """
    Returns a configured Redis client instance.
    Uses generic REDIS_URL or CACHE_REDIS_URL.
    """
    redis_url = os.getenv('REDIS_URL', os.getenv('CACHE_REDIS_URL', 'redis://localhost:6379/0'))
    try:
        return redis.from_url(redis_url, decode_responses=True)
    except Exception as e:
        logger.error(f"Failed to create Redis client at {redis_url}: {e}")
        return None

import json
from typing import Optional, Any

# Singleton-like usage
redis_client = get_redis_client()

class RedisCache:
    def __init__(self, client=None):
        self.client = client or redis_client

    def get(self, key: str) -> Optional[Any]:
        """Retrieve and deserialize JSON data from Redis"""
        if not self.client:
            return None
        try:
            data = self.client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Redis GET error key={key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Serialize and store data in Redis with TTL"""
        if not self.client:
            return False
        try:
            serialized = json.dumps(value)
            return self.client.set(key, serialized, ex=ttl)
        except Exception as e:
            logger.error(f"Redis SET error key={key}: {e}")
            return False

# Global cache instance
cache = RedisCache()
