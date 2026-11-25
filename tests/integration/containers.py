"""Docker containers shared by all integration tests."""

import atexit
import os
import unittest
import uuid
from functools import cache
from urllib.parse import urlparse

try:
    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer
except ImportError:
    PostgresContainer = None
    RedisContainer = None

try:
    import redis
except ImportError:
    redis = None

# Keep in sync with the postgres and redis images in aggregator/docker-compose.yml.
POSTGRES_IMAGE = "postgres:16"
REDIS_IMAGE = "redis:8.8.0"

requires_postgres = unittest.skipUnless(
    PostgresContainer is not None,
    "testcontainers is required for Postgres integration tests",
)
requires_redis = unittest.skipUnless(
    redis is not None and RedisContainer is not None,
    "redis and testcontainers are required for Redis integration tests",
)


def _start(container):
    container.start()
    atexit.register(container.stop)
    return container


@cache
def postgres_container() -> "PostgresContainer":
    return _start(PostgresContainer(POSTGRES_IMAGE))


@cache
def redis_container() -> "RedisContainer":
    return _start(RedisContainer(REDIS_IMAGE))


def create_postgres_database(prefix: str) -> str:
    """Creates an empty database in the shared Postgres container and returns its URL."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    server_url = postgres_container().get_connection_url()
    database_name = f"{prefix}_{uuid.uuid4().hex[:8]}"

    # CREATE DATABASE cannot run inside a transaction.
    admin_engine = create_engine(server_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    finally:
        admin_engine.dispose()

    return (
        make_url(server_url)
        .set(database=database_name)
        .render_as_string(hide_password=False)
    )


def set_db_env(connection_url: str) -> None:
    """Points the services' settings (DB_* variables) at the given database."""
    parsed = urlparse(connection_url)
    os.environ["DB_USER"] = parsed.username or ""
    os.environ["DB_PASS"] = parsed.password or ""
    os.environ["DB_URL"] = parsed.hostname or ""
    os.environ["DB_PORT"] = str(parsed.port or "")
    os.environ["DB_NAME"] = parsed.path.lstrip("/")


def redis_client(db: int = 0) -> "redis.Redis":
    """Returns a client for one logical database of the shared Redis container."""
    container = redis_container()
    client = redis.Redis(
        host=container.get_container_host_ip(),
        port=int(container.get_exposed_port(6379)),
        db=db,
        decode_responses=True,
    )
    client.ping()
    return client
