import os

from dotenv import load_dotenv

# Fix for pipeline. See #10
if os.getenv("ENV") != "test":
    from datadog import initialize

    load_dotenv()
    initialize(
        api_key=os.getenv("DATADOG_API_KEY"), api_host=os.getenv("DATADOG_API_HOST")
    )
