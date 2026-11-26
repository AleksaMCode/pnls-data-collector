"""Imports firebase_housekeeping modules without real Firebase credentials or a MongoDB connection."""

import importlib
import sys
import types
from unittest import mock

# Imported first, so the folders these create on import exist (the logs folder and tqdm's lock).
import firebase_admin.db  # noqa: F401
import tqdm

import util.logger  # noqa: F401

FIREBASE_HELPERS = "firebase_housekeeping.core.firebase.helpers"
MONGO_RUNTIME = "firebase_housekeeping.core.mongo._init_runtime"
MONGO_FUNCTIONS = ("get_bucket_for_read", "get_bucket_for_write", "get_collection")


def _not_connected(name: str):
    def fail(*args, **kwargs):
        raise RuntimeError(
            f"{name}() would use the MongoDB from the local .env: tests must replace it."
        )

    return fail


def _install_mongo_placeholders() -> None:
    """Replaces the MongoDB client module before anything imports it.

    `core/mongo/_init_runtime.py` builds a client from the local `.env` on import, which could be
    the production MongoDB. Under `ENV=test`, `core/mongo/__init__.py` skips it and defines none of
    its functions, so `core/mongo/helpers.py` cannot be imported at all. Placeholders that raise are
    used in both cases: unit tests replace them with mocks, integration tests with the test MongoDB.
    """
    if MONGO_RUNTIME in sys.modules:
        return
    runtime = types.ModuleType(MONGO_RUNTIME)
    for name in MONGO_FUNCTIONS:
        setattr(runtime, name, _not_connected(name))
    sys.modules[MONGO_RUNTIME] = runtime

    package = importlib.import_module("firebase_housekeeping.core.mongo")
    for name in MONGO_FUNCTIONS:
        if not hasattr(package, name):
            setattr(package, name, getattr(runtime, name))


def import_housekeeping_module(name: str):
    """Imports a housekeeping module, e.g. `firebase_housekeeping.main`.

    - `core.firebase.helpers` starts firebase-admin with the service-account file: no app is
      started here. Integration tests call `connect_firebase_emulator()`.
    - `core.mongo` connects to the MongoDB from `.env`: see `_install_mongo_placeholders`.
    - Under `ENV=test`, `core.firebase.helpers` does not import `tqdm`, which the batched delete
      fallback needs: it is added back.
    """
    _install_mongo_placeholders()
    with (
        mock.patch("firebase_admin.credentials.Certificate"),
        mock.patch("firebase_admin.initialize_app"),
    ):
        module = importlib.import_module(name)

    helpers = sys.modules.get(FIREBASE_HELPERS)
    if helpers is not None and not hasattr(helpers, "tqdm"):
        helpers.tqdm = tqdm.tqdm
    return module
