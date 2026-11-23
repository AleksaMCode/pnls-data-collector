from collections import Counter
from dataclasses import dataclass, field


@dataclass
class MappingRunStats:
    """Outcome counters for one SSID GEO mapping run."""

    request_budget: int
    attempted: int = 0
    requests_sent: int = 0
    with_locations: int = 0
    no_results: int = 0
    failures: Counter = field(default_factory=Counter)
    # Set when the run was cut short.
    aborted_status: int | None = None
    aborted_at_request: int | None = None
    abort_body: str | None = None
    abort_retry_after: str | None = None
    budget_exhausted: bool = False

    @property
    def failed(self) -> int:
        return sum(self.failures.values())


def format_duration(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def build_summary(stats: MappingRunStats, duration_seconds: float) -> str:
    duration = format_duration(duration_seconds)

    if stats.aborted_at_request is not None:
        headline = (
            f"SSID GEO mapping ABORTED after {duration}: {stats.aborted_status} "
            f"from WiGLE at request "
            f"{stats.aborted_at_request}/{stats.request_budget}."
        )
    elif stats.budget_exhausted:
        headline = (
            f"SSID GEO mapping STOPPED after {duration}: request budget of "
            f"{stats.request_budget} reached."
        )
    else:
        headline = f"SSID GEO mapping completed in {duration}."

    lines = [
        headline,
        f"Attempted: {stats.attempted} | Requests sent: "
        f"{stats.requests_sent}/{stats.request_budget}",
        f"With locations: {stats.with_locations} | No results: {stats.no_results} "
        f"| Failed: {stats.failed}",
    ]

    if stats.failures:
        breakdown = ", ".join(
            f"{reason} x{count}" for reason, count in stats.failures.most_common()
        )
        lines.append(f"Failures: {breakdown}")

    if stats.aborted_at_request is not None:
        if stats.abort_retry_after:
            lines.append(f"Retry-After: {stats.abort_retry_after}")
        if stats.abort_body:
            # Bodies can be multi-line HTML (e.g. a proxy error page); keep it on one line.
            lines.append(f"WiGLE said: {' '.join(stats.abort_body.split())}")

    return "\n".join(lines)
