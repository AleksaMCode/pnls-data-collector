import os

if os.getenv("ENV") != "test":
    from ._init_runtime import _session
