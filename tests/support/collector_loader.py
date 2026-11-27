"""Imports collector modules that have side effects on import, without real keys or services."""

import importlib
from unittest import mock

# Imported first, so the folders these create on import exist before `os.makedirs` is replaced
# below: the logs folder (util.logger) and scapy's cache.
import firebase_admin.db  # noqa: F401
import scapy.layers.dot11  # noqa: F401
import scapy.sendrecv  # noqa: F401

import util.logger  # noqa: F401
from tests.support.keys import test_rsa_key


def import_collector_module(name: str):
    """Imports a collector module, e.g. `collector.wlan.parser`.

    - `collector.core.firebase.helpers` starts firebase-admin with the service-account file:
      no app is started here. Integration tests call `connect_firebase_emulator()`.
    - `collector.wlan.parser` loads the public key file: the throwaway test key is used.
    - `collector.util.util` creates `collector/captured_data`: the folder is not created, and
      tests point `DATA_DIR` at a temporary folder.
    """
    with (
        mock.patch(
            "util.util.load_rsa_key_from_file",
            return_value=test_rsa_key().publickey(),
        ),
        mock.patch("firebase_admin.credentials.Certificate"),
        mock.patch("firebase_admin.initialize_app"),
        mock.patch("os.makedirs"),
    ):
        return importlib.import_module(name)
