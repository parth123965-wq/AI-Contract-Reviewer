import logging
from typing import Optional
import redis.asyncio as redis
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

redis_client: Optional[Redis] = None


async def initialize_redis() -> Optional[Redis]:
    """
    Initialize the global Redis connection client using settings.REDIS_URL.
    Tests connection via ping.
    """
    global redis_client
    try:
        redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        await redis_client.ping()
        logger.info("Successfully connected to Redis.")
        return redis_client
    except Exception as e:
        logger.error(f"Failed to connect to Redis at {settings.REDIS_URL}: {e}")
        redis_client = None
        raise e


async def close_redis() -> None:
    """
    Close the global Redis client connection gracefully.
    """
    global redis_client
    if redis_client is not None:
        try:
            await redis_client.close()
            logger.info("Redis connection closed gracefully.")
        except Exception as e:
            logger.error(f"Error while closing Redis connection: {e}")
        finally:
            redis_client = None


def get_redis() -> Redis:
    """
    Dependency or getter function that returns the global Redis client instance.
    Raises RuntimeError if Redis client has not been initialized.
    """
    if redis_client is None:
        raise RuntimeError("Redis client is not initialized. Call initialize_redis() first.")
    return redis_client
