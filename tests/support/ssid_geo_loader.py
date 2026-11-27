"""Imports ssid_geo_mapper modules without a database connection."""

import importlib
import os

# `core/orm/helpers.py` imports `_init_runtime` directly, which builds the engine from the DB_*
# variables on import (the ENV=test guard in `core/orm/__init__.py` does not apply). The values only
# make the URL valid: nothing connects until a session is used, and the tests bind their sessions to
# a test database or replace the helpers.
for _name, _value in (
    ("DB_USER", "test"),
    ("DB_PASS", "test"),
    ("DB_URL", "localhost"),
    ("DB_PORT", "5432"),
    ("DB_NAME", "test"),
):
    os.environ.setdefault(_name, _value)


def import_ssid_geo_module(name: str):
    """Imports an SSID GEO mapper module, e.g. `ssid_geo_mapper.main`."""
    return importlib.import_module(name)
