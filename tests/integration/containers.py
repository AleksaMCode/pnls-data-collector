"""Docker containers shared by all integration tests."""

import atexit
import os
import unittest
import uuid
from functools import cache
from pathlib import Path
from urllib.parse import urlparse

try:
    from testcontainers.core.container import DockerContainer
    from testcontainers.core.waiting_utils import wait_for_logs
    from testcontainers.mongodb import MongoDbContainer
    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer
except ImportError:
    DockerContainer = None
    MongoDbContainer = None
    PostgresContainer = None
    RedisContainer = None

try:
    import redis
except ImportError:
    redis = None

try:
    import pymongo
except ImportError:
    pymongo = None

try:
    import firebase_admin
except ImportError:
    firebase_admin = None

REPO_ROOT = Path(__file__).resolve().parents[2]
AGGREGATOR_MIGRATIONS = REPO_ROOT / "aggregator" / "migrations"
SUPABASE_MIGRATIONS = REPO_ROOT / "stats" / "supabase" / "migrations"

# Keep in sync with the postgres and redis images in aggregator/docker-compose.yml.
POSTGRES_IMAGE = "postgres:16"
REDIS_IMAGE = "redis:8.8.0"
# The stats service publishes to Supabase, which runs Postgres 17.6 (see stats/supabase/config.toml).
SUPABASE_POSTGRES_IMAGE = "postgres:17.6"
# Keep in sync with the mongodb image in firebase_housekeeping/docker-compose.yml.
MONGO_IMAGE = "mongo:8.2.3"

FIREBASE_EMULATOR_DIR = Path(__file__).resolve().parent / "firebase_emulator"
FIREBASE_EMULATOR_IMAGE = "pnls-firebase-database-emulator:test"
FIREBASE_EMULATOR_PORT = 9000
FIREBASE_AUTH_EMULATOR_PORT = 9099
FIREBASE_TEST_PROJECT_ID = "demo-pnls"
# Matches the `demo-` project the emulator starts with (see firebase_emulator/Dockerfile).
FIREBASE_TEST_DATABASE_URL = "https://demo-pnls-default-rtdb.firebaseio.com"

# Logical Redis databases, one per use, so that tests sharing the container never clash.
REDIS_DB_REDIS_HELPERS = 1
REDIS_DB_ORM_CACHE = 2
REDIS_DB_WORKFLOW_CACHE = 3
REDIS_DB_CELERY_BROKER = 4
REDIS_DB_CELERY_BACKEND = 5
REDIS_DB_PIPELINE_CACHE = 6
REDIS_DB_STATS_API_CACHE = 7

requires_postgres = unittest.skipUnless(
    PostgresContainer is not None,
    "testcontainers is required for Postgres integration tests",
)
requires_redis = unittest.skipUnless(
    redis is not None and RedisContainer is not None,
    "redis and testcontainers are required for Redis integration tests",
)
requires_mongo = unittest.skipUnless(
    pymongo is not None and MongoDbContainer is not None,
    "pymongo and testcontainers are required for MongoDB integration tests",
)
requires_firebase = unittest.skipUnless(
    firebase_admin is not None and DockerContainer is not None,
    "firebase-admin and testcontainers are required for Firebase integration tests",
)


def _start(container):
    container.start()
    atexit.register(container.stop)
    return container


@cache
def postgres_container() -> "PostgresContainer":
    return _start(PostgresContainer(POSTGRES_IMAGE))


@cache
def supabase_postgres_container() -> "PostgresContainer":
    """A second Postgres server, on Supabase's version, only started by the tests that need it."""
    return _start(PostgresContainer(SUPABASE_POSTGRES_IMAGE))


@cache
def redis_container() -> "RedisContainer":
    return _start(RedisContainer(REDIS_IMAGE))


@cache
def mongo_container() -> "MongoDbContainer":
    # Explicit credentials: the defaults come from MONGO_* variables, which a local .env may set.
    return _start(
        MongoDbContainer(MONGO_IMAGE, username="test", password="test", dbname="test")
    )


@cache
def mongo_client() -> "pymongo.MongoClient":
    """Returns the one client of the shared MongoDB container, closed when the test run ends."""
    client = mongo_container().get_connection_client()
    # Registered after the container, so it is closed before the container stops.
    atexit.register(client.close)
    return client


def create_mongo_database(prefix: str) -> "pymongo.database.Database":
    """Returns a new, empty database in the shared MongoDB container (created on first write)."""
    return mongo_client()[f"{prefix}_{uuid.uuid4().hex[:8]}"]


def create_postgres_database(prefix: str, container=None) -> str:
    """Creates an empty database in a shared Postgres container (the default one if not given)."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    server_url = (container or postgres_container()).get_connection_url()
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


def apply_migrations(
    connection_url: str, migrations_dir: Path, pattern: str = "*.up.sql"
) -> None:
    """Runs every migration file of a service in name order, as the production database got them."""
    from sqlalchemy import create_engine

    engine = create_engine(connection_url)
    try:
        connection = engine.raw_connection()
        try:
            with connection.cursor() as cursor:
                for migration in sorted(migrations_dir.glob(pattern)):
                    cursor.execute(migration.read_text(encoding="utf-8"))
            connection.commit()
        finally:
            connection.close()
    finally:
        engine.dispose()


def create_aggregator_database(prefix: str) -> str:
    """Creates a database with the full aggregator schema (tables, views and seed data)."""
    from sqlalchemy import create_engine, text

    connection_url = create_postgres_database(prefix)
    apply_migrations(connection_url, AGGREGATOR_MIGRATIONS)

    # The OUI view is created WITH NO DATA, and an unpopulated materialized view cannot be read.
    engine = create_engine(connection_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("REFRESH MATERIALIZED VIEW ieee_mac_oui_with_country")
            )
    finally:
        engine.dispose()

    return connection_url


def create_supabase_database(prefix: str) -> str:
    """Creates a database with the stats service's Supabase schema, on Supabase's Postgres version."""
    connection_url = create_postgres_database(
        prefix, container=supabase_postgres_container()
    )
    # Supabase CLI migrations are plain `<timestamp>_<name>.sql` files.
    apply_migrations(connection_url, SUPABASE_MIGRATIONS, pattern="*.sql")
    return connection_url


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


def redis_url(db: int) -> str:
    """Returns a redis:// URL for one logical database of the shared Redis container."""
    container = redis_container()
    host = container.get_container_host_ip()
    port = container.get_exposed_port(6379)
    return f"redis://{host}:{port}/{db}"


@cache
def firebase_emulator_container() -> "DockerContainer":
    """Builds the emulator image (cached by Docker after the first build) and starts it once."""
    import docker

    docker.from_env().images.build(
        path=str(FIREBASE_EMULATOR_DIR), tag=FIREBASE_EMULATOR_IMAGE, rm=True
    )
    container = DockerContainer(FIREBASE_EMULATOR_IMAGE).with_exposed_ports(
        FIREBASE_EMULATOR_PORT, FIREBASE_AUTH_EMULATOR_PORT
    )
    _start(container)
    wait_for_logs(container, "All emulators ready", timeout=180)
    return container


def connect_firebase_emulator() -> None:
    """Points firebase-admin's default app at the emulator, replacing any app set up before.

    The Admin SDK sends every `db.reference()` call to the host in FIREBASE_DATABASE_EMULATOR_HOST
    and signs in with a fixed emulator token, so no real credentials are used. With
    FIREBASE_AUTH_EMULATOR_HOST set, `auth.verify_id_token()` accepts the Authentication emulator's
    tokens: it checks their claims (project, expiry), but not their signature.
    """
    container = firebase_emulator_container()
    host = container.get_container_host_ip()
    port = container.get_exposed_port(FIREBASE_EMULATOR_PORT)
    os.environ["FIREBASE_DATABASE_EMULATOR_HOST"] = f"{host}:{port}"
    os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = firebase_auth_emulator_host()

    try:
        firebase_admin.delete_app(firebase_admin.get_app())
    except ValueError:
        pass  # No default app yet.

    firebase_admin.initialize_app(
        credential=_EmulatorCredential(),
        options={
            "databaseURL": FIREBASE_TEST_DATABASE_URL,
            # ID tokens are checked against the project they were issued for.
            "projectId": FIREBASE_TEST_PROJECT_ID,
        },
    )
    assert_firebase_is_emulator()


def firebase_auth_emulator_host() -> str:
    """Returns `host:port` of the Authentication emulator, in the shared emulator container."""
    container = firebase_emulator_container()
    host = container.get_container_host_ip()
    return f"{host}:{container.get_exposed_port(FIREBASE_AUTH_EMULATOR_PORT)}"


def create_firebase_test_user(email: str, password: str) -> str:
    """Signs up a user in the Authentication emulator and returns their ID token."""
    import httpx

    response = httpx.post(
        f"http://{firebase_auth_emulator_host()}"
        "/identitytoolkit.googleapis.com/v1/accounts:signUp",
        # The emulator accepts any API key.
        params={"key": "test-api-key"},
        json={"email": email, "password": password, "returnSecureToken": True},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["idToken"]


def assert_firebase_is_emulator() -> None:
    """Stops a test before it can write to, or delete, a real Firebase database."""
    emulator_host = os.environ.get("FIREBASE_DATABASE_EMULATOR_HOST", "")
    database_url = firebase_admin.get_app().options.get("databaseURL")
    if not emulator_host or database_url != FIREBASE_TEST_DATABASE_URL:
        raise RuntimeError(
            "Firebase integration tests must run against the emulator, "
            f"got emulator host '{emulator_host}' and database URL '{database_url}'."
        )


if firebase_admin is not None:
    from firebase_admin import credentials

    class _EmulatorCredential(credentials.Base):
        """A placeholder credential; with an emulator host set, the SDK never asks it for a token."""

        def get_credential(self):
            raise RuntimeError(
                "Firebase integration tests must not use real credentials."
            )
