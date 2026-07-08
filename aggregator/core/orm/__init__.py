import os

# Fix for pipeline. See #10
# TODO See if this can be done in another way
if os.getenv("ENV") != "test":
    from ._init_runtime import _session
else:
    # Fix for pipline in #319
    _session = None
