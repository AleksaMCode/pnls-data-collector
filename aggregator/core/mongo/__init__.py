import os

# Pipeline fix. See #45
if os.getenv("ENV") != "test":
    from ._init_runtime import get_collection, get_bucket_for_write, get_bucket_for_read
