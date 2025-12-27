import logging
import os
from datetime import datetime

import sentry_sdk
from dotenv import load_dotenv
from sentry_sdk.integrations.logging import LoggingIntegrations

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
)

sentry_logging = LoggingIntegration(level=logging.INFO, event_level=logging.WARNING)

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[sentry_logging],
    traces_sample_rate=1.0,
    enable_logs=True,
    attach_stacktrace=True,
)


def get_logger(name: str):
    """Returns a namespaced logger for any module."""
    return logging.getLogger(name)
