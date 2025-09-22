# app/core/cache.py

import redis
from app.config import settings
import logging

logger = logging.getLogger("cache_logger")
logging.basicConfig(level=logging.INFO)

class Cache:
    def __init__(self):
        self.client = None
        if settings.USE_REDIS:
            self.client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB
            )
            logger.info("Redis cache enabled")
        else:
            logger.info("Redis cache disabled")

    def get(self, key: str):
        if self.client:
            value = self.client.get(key)
            if value:
                return value.decode("utf-8")
        return None

    def set(self, key: str, value: str, ttl: int = 60*60*24):
        if self.client:
            self.client.set(key, value, ex=ttl)

# Global cache instance
cache = Cache()

def get_cache():
    """Get the global cache instance"""
    return cache