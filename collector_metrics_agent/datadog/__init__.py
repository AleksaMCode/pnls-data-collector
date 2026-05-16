import os

from datadog import initialize
from dotenv import load_dotenv

load_dotenv()


initialize(api_key=os.getenv("DATADOG_API_KEY"), api_host=os.getenv("DATADOG_API_HOST"))
