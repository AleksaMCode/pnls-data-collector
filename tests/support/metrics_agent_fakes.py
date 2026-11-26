"""Fake host readings and a fake clock for running the metrics agent loop in tests."""

from types import SimpleNamespace

READS_PER_SECOND = 100
WRITES_PER_SECOND = 40
BOOT_TIME = 1_000.0

CPU = SimpleNamespace(user=12.5, system=3.0, idle=80.0, iowait=4.5)
MEMORY = SimpleNamespace(used=600, free=200, total=1_000, available=400)
SWAP = SimpleNamespace(used=50)
DISK = SimpleNamespace(used=30, free=70, total=100)


class StopLoop(Exception):
    """Raised by the fake `time.sleep` to end `start()` after a number of iterations."""


class FakeHost:
    """A host whose clock only moves when the agent waits, with steady disk I/O.

    `wall_offset` is added to the wall clock only (`time.time()`), as when NTP steps the clock;
    `time.monotonic()` is not affected.
    """

    def __init__(self, start: float = 2_000.0, iterations: int = 1):
        self.monotonic_now = start
        self.wall_offset = 0.0
        self.iterations_left = iterations
        self.sleeps = []
        self.cpu_intervals = []
        self.disk_paths = []
        self.time = SimpleNamespace(
            time=self.wall_time, monotonic=self.monotonic, sleep=self.sleep
        )
        self.psutil = SimpleNamespace(
            cpu_times_percent=self.cpu_times_percent,
            virtual_memory=lambda: MEMORY,
            swap_memory=lambda: SWAP,
            disk_usage=self.disk_usage,
            disk_io_counters=self.disk_io_counters,
            boot_time=lambda: BOOT_TIME,
        )

    def advance(self, seconds: float):
        self.monotonic_now += seconds

    def wall_time(self) -> float:
        return self.monotonic_now + self.wall_offset

    def monotonic(self) -> float:
        return self.monotonic_now

    def sleep(self, seconds: float):
        self.sleeps.append(seconds)
        self.iterations_left -= 1
        if self.iterations_left <= 0:
            raise StopLoop
        self.advance(seconds)

    def cpu_times_percent(self, interval):
        self.cpu_intervals.append(interval)
        self.advance(interval)
        return CPU

    def disk_usage(self, path):
        self.disk_paths.append(path)
        return DISK

    def disk_io_counters(self):
        return SimpleNamespace(
            read_count=READS_PER_SECOND * self.monotonic_now,
            write_count=WRITES_PER_SECOND * self.monotonic_now,
        )
