import os

# Fix for pipeline. See #10
if os.getenv("ENV") != "test":
    from ._init_runtime import _session