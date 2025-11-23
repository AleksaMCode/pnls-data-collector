import os

# Fix for pipeline. See #10
# TODO See if this can be done in another way
if os.getenv("ENV") != "test":
    from ._init_runtime import _session
