import hashlib
import hmac
import re

MAC_COLON_RE = re.compile(r"^[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}$")


def _canonicalize_mac(mac: str) -> str:
    if mac is None:
        raise ValueError("MAC is None")

    normalized = mac.strip()
    if not MAC_COLON_RE.fullmatch(normalized):
        raise ValueError(f"Invalid MAC format: {mac!r}")

    return normalized.lower().replace(":", "")


def hash_mac_hmac_sha256(mac: str, pepper: str) -> str:
    canonical_mac = _canonicalize_mac(mac)
    return hmac.new(
        pepper.encode("utf-8"),
        canonical_mac.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
