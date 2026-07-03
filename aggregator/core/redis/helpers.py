from util.logger import get_logger

from . import client

logger = get_logger(__name__)


def set_key_value(key: str, value: str, ttl: int | None = None) -> bool:
    """
    Store key-value data in Redis Cache.
    """
    try:
        if ttl is None:
            return bool(client.set(key, value))
        return bool(client.set(key, value, ex=ttl))
    except Exception as e:
        logger.error(f"Failed to store key '{key}' in Redis - {str(e)}")
        return False


def get_key_value(key: str) -> str | None:
    """
    Read key value from Redis Cache.
    """
    try:
        return client.get(key)
    except Exception as e:
        logger.error(f"Failed to read key '{key}' from Redis - {str(e)}")
        return None
