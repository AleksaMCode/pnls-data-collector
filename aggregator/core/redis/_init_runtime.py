import os

import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_DB = 1

client = redis.Redis(
    host=os.getenv("REDIS_URL"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    password=os.getenv("REDIS_PASSWORD"),
    db=REDIS_DB,
    decode_responses=True,
)
