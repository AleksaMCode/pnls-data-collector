from util.logger import get_logger

from . import client

logger = get_logger(__name__)
LOOKUP_CACHE_TTL_SECONDS = 60 * 60


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


def ssid_cache_key(ssid: str) -> str:
    return f"ssid:id:{ssid}"


def mac_cache_key(mac: str) -> str:
    return f"mac:id:{mac.lower()}"


def get_cached_ssid_id(ssid: str) -> int | None:
    cached_value = get_key_value(ssid_cache_key(ssid))
    if cached_value is None:
        return None
    try:
        return int(cached_value)
    except (TypeError, ValueError):
        logger.warning(f"Invalid cached SSID id '{cached_value}' for '{ssid}'.")
        return None


def set_cached_ssid_id(ssid: str, ssid_id: int) -> bool:
    return set_key_value(
        ssid_cache_key(ssid),
        str(ssid_id),
        ttl=LOOKUP_CACHE_TTL_SECONDS,
    )


def get_cached_mac_id(mac: str) -> int | None:
    cached_value = get_key_value(mac_cache_key(mac))
    if cached_value is None:
        return None
    try:
        return int(cached_value)
    except (TypeError, ValueError):
        logger.warning(f"Invalid cached MAC id '{cached_value}' for '{mac}'.")
        return None


def set_cached_mac_id(mac: str, mac_id: int) -> bool:
    return set_key_value(
        mac_cache_key(mac),
        str(mac_id),
        ttl=LOOKUP_CACHE_TTL_SECONDS,
    )
