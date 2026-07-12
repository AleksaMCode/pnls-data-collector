import logging
import os

import sentry_sdk
from dotenv import load_dotenv
from sentry_sdk.integrations.logging import LoggingIntegration
from tenacity import retry, stop_after_attempt, wait_random

load_dotenv()

# Configure global logging only once
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
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
