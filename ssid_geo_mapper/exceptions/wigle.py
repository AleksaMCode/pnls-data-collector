class WigleError(Exception):
    """Base error for a failed WiGLE lookup, carrying the HTTP status and response body."""

    def __init__(
        self, message: str, status_code: int | None = None, body: str | None = None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class WigleAbortRunError(WigleError):
    """WiGLE refused the request in a way no other SSID can get past. The run must stop."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        body: str | None = None,
        retry_after: str | None = None,
    ):
        super().__init__(message, status_code=status_code, body=body)
        self.retry_after = retry_after


class WigleRateLimitError(WigleAbortRunError):
    """WiGLE answered 429. The daily quota is spent."""


class WigleAccessDeniedError(WigleAbortRunError):
    """WiGLE answered 401 or 403. The credentials are rejected or the client is blocked."""


class WigleLookupError(WigleError):
    """WiGLE rejected a single lookup (any other non-2xx status, or an unusable payload)."""
