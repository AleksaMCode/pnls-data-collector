"""Imports the stats API the way its Docker image runs it, next to the repository's own packages."""

import importlib
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

STATS_API_DIR = Path(__file__).resolve().parents[2] / "stats_api"
# Never connected to: tests that need Supabase bind the helpers to a test database.
PLACEHOLDER_SUPABASE = "postgresql://test:test@localhost:5432/test"
# Read by routers/stats.py on import. Pinned, so the local `.env` cannot change the cache expiry.
TEST_CACHE_TTL_SECONDS = 600

_app_util_modules: dict = {}


def _is_util(name: str) -> bool:
    return name == "util" or name.startswith("util.")


@contextmanager
def _app_root(env: dict | None = None):
    """Runs imports with `stats_api/` as the root, as in the Docker image (`from core…`, `from util…`).

    The stats API's `util` package has the same name as the repository's shared `util`. While the
    context is open, `sys.modules` holds the stats API's one; the repository's is put back after.
    Observability is turned off: no Sentry or Logfire events are sent from tests.
    """
    saved = {
        name: sys.modules.pop(name) for name in list(sys.modules) if _is_util(name)
    }
    sys.modules.update(_app_util_modules)
    sys.path.insert(0, str(STATS_API_DIR))
    try:
        with mock.patch.dict(
            os.environ,
            {
                "SUPABASE_CONNECTION": PLACEHOLDER_SUPABASE,
                "REDIS_TTL": str(TEST_CACHE_TTL_SECONDS),
                "LOGFIRE_SEND_TO_LOGFIRE": "false",
                "LOGFIRE_IGNORE_NO_CONFIG": "1",
                **(env or {}),
            },
        ):
            logger = importlib.import_module("util.logger")
            # Skips sentry_sdk.init() and logfire.configure() in main.py.
            logger._observability_initialized = True
            yield
    finally:
        sys.path.remove(str(STATS_API_DIR))
        for name in list(sys.modules):
            if _is_util(name):
                _app_util_modules[name] = sys.modules.pop(name)
        sys.modules.update(saved)


def _not_connected(*args, **kwargs):
    raise RuntimeError(
        "A test used the Supabase session without replacing it with a test database."
    )


def load_app_modules() -> dict:
    """Imports the stats API once and returns its modules by name (`main`, `routers.stats`, …).

    The Supabase session is replaced with one that refuses to connect: unit tests replace the
    helpers, integration tests bind `_session` to a test database.
    """
    if "routers.stats" not in sys.modules:
        with _app_root():
            importlib.import_module("main")
        sys.modules["core.supabase.helpers"]._session = _not_connected
    names = (
        "main",
        "routers.stats",
        "middleware.auth",
        "core.redis.helpers",
        "core.supabase",
        "core.supabase.helpers",
    )
    modules = {name: sys.modules[name] for name in names}
    modules["util.util"] = _app_util_modules["util.util"]
    return modules


def build_app(env: dict | None = None):
    """Builds a fresh `main` module (and its FastAPI app) with the given environment.

    `main.py` reads SERVER_ENV and ALLOWED_ORIGINS when it is imported. Variables not in `env` are
    removed while it runs, so the local `.env` cannot decide the setup under test.
    """
    load_app_modules()
    overrides = {"SERVER_ENV": None, "ALLOWED_ORIGINS": None, **(env or {})}
    with _app_root({k: v for k, v in overrides.items() if v is not None}):
        for name, value in overrides.items():
            if value is None:
                os.environ.pop(name, None)
        # Not load_dotenv(): the variables under test must not come back from `.env`.
        with mock.patch("dotenv.load_dotenv"):
            return importlib.reload(sys.modules["main"])
