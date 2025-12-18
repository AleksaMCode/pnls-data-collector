import re


def extract_device_name(node_key: str) -> str:
    """
    Extracts device name from a Firebase node key by stripping the trailing date.
    Example: "RPI-1-2025-10-31" → "RPI-1"
    """
    match = re.match(r"^(.*)-\d{4}-\d{2}-\d{2}$", node_key)
    if not match:
        raise AttributeError(f"Node key '{node_key}' is not a valid Firebase node key.")
    return match.group(1)


def clean_string(s: str) -> str:
    # Remove NULL and control characters, but keep UTF-8 characters
    return re.sub(r"[\x00-\x1F\x7F-\x9F]", "", s).strip()
