import os

import logfire
from dotenv import load_dotenv
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis.asyncio import Redis

load_dotenv()


async def init_redis_cache(prefix: str = "stats-api-cache") -> Redis:
    redis_url = os.getenv("REDIS_CONNECTION")

    if redis_url:
        client = Redis.from_url(redis_url)
    else:
        client = Redis(
            host=os.getenv("REDIS_URL"),
            port=int(os.getenv("REDIS_PORT")),
            username=os.getenv("REDIS_USERNAME"),
            password=os.getenv("REDIS_PASSWORD"),
            decode_responses=False,
        )
    logfire.instrument_redis()
    FastAPICache.init(RedisBackend(client), prefix=prefix)
    return client
