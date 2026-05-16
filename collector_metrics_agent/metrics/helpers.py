def build_heartbeat_metric(now: float, device_name: str) -> list[dict]:
    return [
        {
            "metric": "pnls.heartbeat",
            "points": [(now, 1)],
            "tags": [f"host:{device_name}"],
        }
    ]


def build_cpu_metrics(now: float, cpu, device_name: str) -> list[dict]:
    cpu_iowait = getattr(cpu, "iowait", 0)  # Linux only
    return [
        {
            "metric": "pnls.cpu.user",
            "points": [(now, cpu.user)],
            "tags": [f"host:{device_name}"],
        },
        {
            "metric": "pnls.cpu.system",
            "points": [(now, cpu.system)],
            "tags": [f"host:{device_name}"],
        },
        {
            "metric": "pnls.cpu.idle",
            "points": [(now, cpu.idle)],
            "tags": [f"host:{device_name}"],
        },
        {
            "metric": "pnls.cpu.iowait",
            "points": [(now, cpu_iowait)],
            "tags": [f"host:{device_name}"],
        },
    ]


def build_memory_metrics(now: float, mem, swap, device_name: str) -> list[dict]:
    return [
        {
            "metric": "pnls.mem.used",
            "points": [(now, mem.used)],
            "tags": [f"host:{device_name}"],
        },
        {
            "metric": "pnls.mem.free",
            "points": [(now, mem.free)],
            "tags": [f"host:{device_name}"],
        },
        {
            "metric": "pnls.mem.total",
            "points": [(now, mem.total)],
            "tags": [f"host:{device_name}"],
        },
        {
            "metric": "pnls.mem.pct_usable",
            "points": [(now, mem.available / mem.total)],
            "tags": [f"host:{device_name}"],
        },
        {
            "metric": "pnls.swap.used",
            "points": [(now, swap.used)],
            "tags": [f"host:{device_name}"],
        },
    ]


def build_disk_metrics(now: float, disk, device_name: str) -> list[dict]:
    base_tags = [f"host:{device_name}", "device:/"]
    return [
        {
            "metric": "pnls.disk.in_use",
            "points": [(now, disk.used / disk.total)],
            "tags": base_tags,
        },
        {"metric": "pnls.disk.used", "points": [(now, disk.used)], "tags": base_tags},
        {"metric": "pnls.disk.free", "points": [(now, disk.free)], "tags": base_tags},
    ]


def build_io_metrics(
    now: float, reads_per_sec: float, writes_per_sec: float, device_name: str
) -> list[dict]:
    return [
        {
            "metric": "pnls.io.r_s",
            "points": [(now, reads_per_sec)],
            "tags": [f"host:{device_name}"],
        },
        {
            "metric": "pnls.io.w_s",
            "points": [(now, writes_per_sec)],
            "tags": [f"host:{device_name}"],
        },
    ]


def build_uptime_metric(now: float, uptime: float, device_name: str) -> list[dict]:
    return [
        {
            "metric": "pnls.uptime",
            "points": [(now, uptime)],
            "tags": [f"host:{device_name}"],
        }
    ]


def build_all_metrics(
    now: float,
    device_name: str,
    cpu,
    mem,
    swap,
    disk,
    reads_per_sec: float,
    writes_per_sec: float,
    uptime: float,
) -> list[dict]:
    metrics = []
    metrics.extend(build_heartbeat_metric(now, device_name))
    metrics.extend(build_cpu_metrics(now, cpu, device_name))
    metrics.extend(build_memory_metrics(now, mem, swap, device_name))
    metrics.extend(build_disk_metrics(now, disk, device_name))
    metrics.extend(build_io_metrics(now, reads_per_sec, writes_per_sec, device_name))
    metrics.extend(build_uptime_metric(now, uptime, device_name))

    return metrics
