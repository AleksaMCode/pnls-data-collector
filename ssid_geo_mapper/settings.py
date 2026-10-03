import os

from dotenv import load_dotenv

load_dotenv()

SERVICE_NAME = "SSID GEO Mapper"

SERVICE_DESCRIPTION = "SSID GEO Mapper microservice"

SERVICE_VERSION = "v1"

# Max. allotted limit for research
WIGLE_API_LIMIT = 250
WIGLE_BASE_DELAY_SECONDS = float(os.getenv("WIGLE_BASE_DELAY_SECONDS", "2.0"))
WIGLE_DELAY_JITTER_SECONDS = float(os.getenv("WIGLE_DELAY_JITTER_SECONDS", "0.7"))

# Project uses CERN's Mattermost
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
