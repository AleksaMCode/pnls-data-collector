import os

from dotenv import load_dotenv

load_dotenv()

SERVICE_NAME = "SSID GEO Mapper"

SERVICE_DESCRIPTION = "SSID GEO Mapper microservice"

SERVICE_VERSION = "v1"

# Max. allotted limit for research
WIGLE_API_LIMIT = 250

# Project uses CERN's Mattermost
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
