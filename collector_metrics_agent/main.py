import time

import psutil

from collector_metrics_agent.datadog.helpers import send_metrics
from collector_metrics_agent.metrics.helpers import build_all_metrics
from collector_metrics_agent.settings import DATADOG_TIMEOUT, DEVICE_NAME
from util.logger import get_logger

logger = get_logger(__name__)

# HOST = socket.gethostname()

# Track previous disk I/O for rate calculation
prev_disk_io = psutil.disk_io_counters()
prev_time = time.time()


def start():
    global prev_disk_io, prev_time
    while True:
        now = time.time()

        cpu = psutil.cpu_times_percent(interval=1)
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        disk = psutil.disk_usage("/")

        curr_disk_io = psutil.disk_io_counters()
        elapsed = now - prev_time
        if elapsed > 0.0:
            reads_per_sec = (
                curr_disk_io.read_count - prev_disk_io.read_count
            ) / elapsed
            writes_per_sec = (
                curr_disk_io.write_count - prev_disk_io.write_count
            ) / elapsed
        else:
            reads_per_sec = 0
            writes_per_sec = 0
        prev_disk_io = curr_disk_io
        prev_time = now

        uptime = now - psutil.boot_time()

        metrics = build_all_metrics(
            now=now,
            device_name=DEVICE_NAME,
            cpu=cpu,
            mem=mem,
            swap=swap,
            disk=disk,
            reads_per_sec=reads_per_sec,
            writes_per_sec=writes_per_sec,
            uptime=uptime,
        )
        ok = send_metrics(metrics)
        if ok:
            logger.info(f"Sent {len(metrics)} metrics from {DEVICE_NAME}.")
        else:
            logger.info(f"Failed to send {len(metrics)} metrics from {DEVICE_NAME}.")
        time.sleep(DATADOG_TIMEOUT)


if __name__ == "__main__":
    start()
