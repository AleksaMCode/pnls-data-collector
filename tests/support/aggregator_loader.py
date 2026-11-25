"""Imports aggregator modules that have side effects on import, without real keys or services."""

import importlib
import os
import sys
from contextlib import ExitStack, contextmanager
from functools import cache
from unittest import mock

FIREBASE_HELPERS = "aggregator.core.firebase.helpers"

# Only used to make the database URL valid; tests bind their sessions to a test database.
for _name, _value in (
    ("DB_USER", "test"),
    ("DB_PASS", "test"),
    ("DB_URL", "localhost"),
    ("DB_PORT", "5432"),
    ("DB_NAME", "test"),
):
    os.environ.setdefault(_name, _value)


@cache
def test_rsa_key():
    """A throwaway RSA key pair, generated once per test run. Never committed to the repo."""
    from Crypto.PublicKey import RSA

    return RSA.generate(2048)


def import_firebase_helpers():
    """Returns `aggregator.core.firebase.helpers`, imported without credentials or a key file.

    No Firebase app is started. Unit tests replace `db`; integration tests call
    `tests.integration.containers.connect_firebase_emulator()`.
    """
    if FIREBASE_HELPERS in sys.modules:
        return sys.modules[FIREBASE_HELPERS]

    with (
        mock.patch("util.util.load_rsa_key_from_file", return_value=test_rsa_key()),
        mock.patch("firebase_admin.credentials.Certificate"),
        mock.patch("firebase_admin.initialize_app"),
    ):
        return importlib.import_module(FIREBASE_HELPERS)


def import_aggregator_module(name: str):
    """Imports an aggregator module that imports the Firebase helpers, e.g. `aggregator.main`."""
    import_firebase_helpers()
    return importlib.import_module(name)


@contextmanager
def no_retry_wait(*functions):
    """Removes the tenacity wait between attempts, so error paths do not wait minutes.

    From the tenacity maintainer: https://github.com/jd/tenacity/issues/106
    """
    from tenacity import wait_none

    with ExitStack() as stack:
        for function in functions:
            stack.enter_context(mock.patch.object(function.retry, "wait", wait_none()))
        yield
