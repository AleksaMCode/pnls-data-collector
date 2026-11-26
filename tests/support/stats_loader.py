"""Imports stats service modules without a connection to the local database or Supabase."""

import importlib
import os

# The engines are built from these on import. The values only make the URLs valid, and they win
# over the local `.env`, which `load_dotenv()` does not let override variables that are already set.
for _name, _value in (
    ("DB_USER", "test"),
    ("DB_PASS", "test"),
    ("DB_URL", "localhost"),
    ("DB_PORT", "5432"),
    ("DB_NAME", "test"),
    ("SUPABASE_USER", "test"),
    ("SUPABASE_PASS", "test"),
    ("SUPABASE_URL", "localhost"),
    ("SUPABASE_PORT", "5432"),
    ("SUPABASE_NAME", "test"),
):
    os.environ.setdefault(_name, _value)

ORM_HELPERS = "stats.core.orm.helpers"
SUPABASE_HELPERS = "stats.core.supabase.helpers"


def _not_connected(database: str):
    def fail(*args, **kwargs):
        raise RuntimeError(
            f"A test used the {database} session without replacing it with a test database."
        )

    return fail


def _load_helpers():
    """Imports both helper modules once, with sessions that refuse to connect.

    Under `ENV=test`, `core/supabase/__init__.py` defines no `_session`, so its helpers (and
    `main.py`) cannot be imported. Outside it, the sessions would use the databases from the local
    `.env`, one of them the production Supabase. Both are replaced either way: tests that need a
    database patch `_session` with one bound to a test container.
    """
    for package, database in (
        ("stats.core.orm", "local database"),
        ("stats.core.supabase", "Supabase"),
    ):
        module = importlib.import_module(package)
        if getattr(module, "_session", None) is None:
            module._session = _not_connected(database)

    orm_helpers = importlib.import_module(ORM_HELPERS)
    orm_helpers._session = _not_connected("local database")
    supabase_helpers = importlib.import_module(SUPABASE_HELPERS)
    supabase_helpers._session = _not_connected("Supabase")


def import_stats_module(name: str):
    """Imports a stats module, e.g. `stats.main`."""
    import sys

    if SUPABASE_HELPERS not in sys.modules:
        _load_helpers()
    return importlib.import_module(name)
