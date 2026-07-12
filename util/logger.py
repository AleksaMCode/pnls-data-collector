import logging
import os
from datetime import datetime

import sentry_sdk
from dotenv import load_dotenv
from sentry_sdk.integrations.logging import LoggingIntegration
from tenacity import retry, stop_after_attempt, wait_random

load_dotenv()

# Base logs directory
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Log file with dynamic name based on date (shared by all components)
LOG_FILE = os.path.join(LOG_DIR, f"{datetime.now():%Y-%m-%d}.log")

# Configure global logging only once
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
    # Needed in order to be present when working with for example Celery tasks to override pre-existing handlers.
    # TODO: Make this configurable.
    force=True,
)

sentry_logging = LoggingIntegration(level=logging.INFO, event_level=logging.WARNING)


@retry(stop=stop_after_attempt(3), wait=wait_random(min=1, max=2))
def sentry_init():
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[sentry_logging],
        traces_sample_rate=1.0,
        enable_logs=True,
        attach_stacktrace=True,
        server_name=os.getenv("SENTRY_SERVER_NAME", "default-server-name"),
    )


sentry_init()


def get_logger(name: str):
    """Returns a namespaced logger for any module."""
    return logging.getLogger(name)
