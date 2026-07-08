import os

import redis
from dotenv import load_dotenv

from aggregator.settings import REDIS_CACHE_DB

load_dotenv()


client = redis.Redis(
    host=os.getenv("REDIS_URL"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    password=os.getenv("REDIS_PASSWORD"),
    db=REDIS_CACHE_DB,
    decode_responses=True,
)
