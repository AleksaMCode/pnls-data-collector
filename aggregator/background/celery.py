import os
from datetime import timedelta

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

def _redis_auth() -> str:
    password = os.getenv("REDIS_PASSWORD")
    if not password:
        return ""
    return f":{password}@"


def _redis_connection_url(db: int) -> str:
    host = os.getenv("REDIS_URL", "redis")
    port = os.getenv("REDIS_PORT", "6379")
    return f"redis://{_redis_auth()}{host}:{port}/{db}"


celery = Celery(
    "aggregator",
    broker=_redis_connection_url(0),
    backend=_redis_connection_url(1),
    include=["aggregator.background.tasks"],
)

celery.conf.result_expires = timedelta(days=10)
