import math
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx
from tenacity import wait_exponential


class RetryableWigleError(httpx.HTTPError):
    """HTTPError carrying optional server-suggested retry delay."""

    MAX_RETRY_DELAY_SECONDS = 60.0

    def __init__(self, message: str, retry_after: str | int | float | None = None):
        super().__init__(message)
        self.retry_after = self._parse_retry_after(retry_after)

    @classmethod
    def _parse_retry_after(cls, retry_after: str | int | float | None) -> float | None:
        if retry_after is None:
            return None

        value = str(retry_after).strip()

        # Retry-After: <delay-seconds>
        try:
            seconds = float(value)
            if math.isfinite(seconds):
                return min(max(seconds, 0.0), cls.MAX_RETRY_DELAY_SECONDS)
        except (TypeError, ValueError):
            pass

        # Retry-After: <http-date>
        try:
            retry_dt = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None

        if retry_dt is None:
            return None

        if retry_dt.tzinfo is None:
            retry_dt = retry_dt.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        seconds = (retry_dt - now).total_seconds()
        return min(max(seconds, 0.0), cls.MAX_RETRY_DELAY_SECONDS)


def wait_retry_after_or_exponential(retry_state):
    # If exception has retry_after, prefer that; else fallback exponential.
    ex = retry_state.outcome.exception()
    if isinstance(ex, RetryableWigleError) and ex.retry_after is not None:
        return ex.retry_after
    # Same shape as wait_exponential(multiplier=1, min=1, max=60)
    return wait_exponential(multiplier=1, min=1, max=60)(retry_state)
