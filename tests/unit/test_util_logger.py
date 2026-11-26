"""Unit tests for the shared logger: its log file, its Sentry setup and `get_logger`."""

import importlib
import logging
import logging.handlers
import os
import unittest
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from unittest import mock

from tenacity import RetryError

import util.logger
from tests.support.aggregator_loader import no_retry_wait

REPO_ROOT = Path(__file__).resolve().parents[2]
STARTED = datetime(2026, 6, 14, 23, 59)
REAL_FILE_HANDLER = logging.FileHandler


class FixedClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return STARTED


@contextmanager
def reloaded_logger(env: dict | None = None):
    """Runs `util/logger.py` again, as on a service's start, and yields what it set up.

    The root logger and Sentry are not touched: `logging.basicConfig` and `sentry_sdk.init` are
    replaced, and the module is reloaded once more (with the real clock) when the context closes.
    """
    with (
        mock.patch("logging.basicConfig") as basic_config,
        mock.patch("sentry_sdk.init") as sentry,
        # A real handler, but the file is only created on the first record, which never comes.
        mock.patch(
            "logging.FileHandler",
            side_effect=lambda filename, encoding=None: REAL_FILE_HANDLER(
                filename, encoding=encoding, delay=True
            ),
        ),
        mock.patch.dict("os.environ", env or {}),
    ):
        with mock.patch("datetime.datetime", FixedClock):
            module = importlib.reload(util.logger)
        try:
            yield module, basic_config, sentry
        finally:
            importlib.reload(util.logger)
            # The reloads make handlers of their own; they are not the service's.
            for call in basic_config.call_args_list:
                for handler in call.kwargs.get("handlers", []):
                    handler.close()


class TestLogFile(unittest.TestCase):
    def test_logs_go_to_the_repository_logs_folder(self):
        with reloaded_logger() as (module, *_):
            self.assertEqual(Path(module.LOG_DIR).resolve(), REPO_ROOT / "logs")

    def test_file_is_named_after_the_start_day(self):
        with reloaded_logger() as (module, *_):
            self.assertEqual(Path(module.LOG_FILE).name, "2026-06-14.log")

    def test_records_go_to_the_file_and_the_console(self):
        with reloaded_logger() as (module, basic_config, _):
            handlers = basic_config.call_args.kwargs["handlers"]

            self.assertEqual(
                [type(handler) for handler in handlers],
                [REAL_FILE_HANDLER, logging.StreamHandler],
            )
            self.assertEqual(
                Path(handlers[0].baseFilename).resolve(),
                Path(module.LOG_FILE).resolve(),
            )

    def test_root_logger_is_reconfigured_at_info_level(self):
        with reloaded_logger() as (_, basic_config, __):
            kwargs = basic_config.call_args.kwargs

        self.assertEqual(kwargs["level"], logging.INFO)
        # Replaces handlers set up before, e.g. by Celery.
        self.assertTrue(kwargs["force"])
        self.assertEqual(
            kwargs["format"], "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )

    @unittest.expectedFailure
    def test_file_rolls_over_at_midnight(self):
        """Known issue: the file name is fixed when the module is imported, so a service started
        on June 14 writes to 2026-06-14.log forever, and the file is never rotated. Remove the
        decorator once a handler that rolls over at midnight is used.
        """
        with reloaded_logger() as (_, basic_config, __):
            file_handler = basic_config.call_args.kwargs["handlers"][0]

            self.assertIsInstance(
                file_handler, logging.handlers.TimedRotatingFileHandler
            )
            self.assertEqual(file_handler.when, "MIDNIGHT")


class TestSentry(unittest.TestCase):
    def test_sentry_is_set_up_on_import_from_the_environment(self):
        env = {
            "SENTRY_DSN": "https://key@sentry.example/1",
            "SENTRY_SERVER_NAME": "aggregator",
        }

        with reloaded_logger(env) as (module, _, sentry):
            sentry.assert_called_once()
            kwargs = sentry.call_args.kwargs
            integration = module.sentry_logging

        self.assertEqual(kwargs["dsn"], "https://key@sentry.example/1")
        self.assertEqual(kwargs["server_name"], "aggregator")
        self.assertEqual(kwargs["integrations"], [integration])

    def test_server_name_has_a_default(self):
        with mock.patch.dict("os.environ"), mock.patch("sentry_sdk.init") as sentry:
            os.environ.pop("SENTRY_SERVER_NAME", None)
            util.logger.sentry_init()

        self.assertEqual(sentry.call_args.kwargs["server_name"], "default-server-name")

    def test_warnings_and_errors_become_sentry_events(self):
        integration = util.logger.sentry_logging

        self.assertEqual(integration._handler.level, logging.WARNING)
        self.assertEqual(integration._breadcrumb_handler.level, logging.INFO)

    def test_failed_setup_is_retried(self):
        with (
            mock.patch("sentry_sdk.init", side_effect=[OSError("DNS"), None]) as sentry,
            no_retry_wait(util.logger.sentry_init),
        ):
            util.logger.sentry_init()

        self.assertEqual(sentry.call_count, 2)

    def test_setup_gives_up_after_three_attempts(self):
        with (
            mock.patch("sentry_sdk.init", side_effect=OSError("DNS")) as sentry,
            no_retry_wait(util.logger.sentry_init),
            self.assertRaises(RetryError),
        ):
            util.logger.sentry_init()

        self.assertEqual(sentry.call_count, 3)


class TestGetLogger(unittest.TestCase):
    def test_named_logger_under_the_root_configuration(self):
        logger = util.logger.get_logger("aggregator.background.tasks")

        self.assertIs(logger, logging.getLogger("aggregator.background.tasks"))
        self.assertTrue(logger.propagate)


if __name__ == "__main__":
    unittest.main()
