import os

from dotenv import load_dotenv

load_dotenv()

SERVICE_NAME = "SSID GEO Mapper"

SERVICE_DESCRIPTION = "SSID GEO Mapper microservice"

SERVICE_VERSION = "v1"

# Max. allotted limit for research. Hard cap on HTTP requests sent to WiGLE per run.
WIGLE_API_LIMIT = 250
# SSIDs fetched per run. Kept below the limit to leave headroom for requests
# WiGLE may count differently than we do (timeouts, window boundaries).
WIGLE_BATCH_SIZE = min(int(os.getenv("WIGLE_BATCH_SIZE", "240")), WIGLE_API_LIMIT)
WIGLE_BASE_DELAY_SECONDS = float(os.getenv("WIGLE_BASE_DELAY_SECONDS", "2.0"))
WIGLE_DELAY_JITTER_SECONDS = float(os.getenv("WIGLE_DELAY_JITTER_SECONDS", "0.7"))

# Project uses CERN's Mattermost
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
