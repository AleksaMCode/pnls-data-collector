import json
import os

# Base data directory
DATA_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "captured_data"
)
os.makedirs(DATA_DIR, exist_ok=True)


def publish_captured_data_locally(data, timestamp):
    with open(
        os.path.join(DATA_DIR, f"{timestamp}-data.json"),
        "a",
        encoding="utf-8",
    ) as f:
        f.write(json.dumps(data) + "\n")
