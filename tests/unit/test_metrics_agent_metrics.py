"""Unit tests for the metrics the agent builds from the host readings."""

import unittest
from types import SimpleNamespace

from tests.support.metrics_agent_fakes import CPU, DISK, MEMORY, SWAP
from tests.support.metrics_agent_loader import import_metrics_agent_module

metrics = import_metrics_agent_module("collector_metrics_agent.metrics.helpers")

NOW = 1_750_000_000.0
DEVICE = "RPI-3"
HOST_TAG = f"host:{DEVICE}"


def by_name(built: list[dict]) -> dict[str, dict]:
    return {metric["metric"]: metric for metric in built}


def value_of(metric: dict):
    ((timestamp, value),) = metric["points"]
    return value


class TestBuildHeartbeatMetric(unittest.TestCase):
    def test_heartbeat_is_one_at_now(self):
        self.assertEqual(
            metrics.build_heartbeat_metric(NOW, DEVICE),
            [{"metric": "pnls.heartbeat", "points": [(NOW, 1)], "tags": [HOST_TAG]}],
        )


class TestBuildCpuMetrics(unittest.TestCase):
    def test_cpu_times_are_reported_as_given(self):
        built = by_name(metrics.build_cpu_metrics(NOW, CPU, DEVICE))

        self.assertEqual(
            {name: value_of(metric) for name, metric in built.items()},
            {
                "pnls.cpu.user": 12.5,
                "pnls.cpu.system": 3.0,
                "pnls.cpu.idle": 80.0,
                "pnls.cpu.iowait": 4.5,
            },
        )

    def test_iowait_is_zero_where_the_platform_has_none(self):
        # psutil only reports iowait on Linux.
        cpu = SimpleNamespace(user=1.0, system=2.0, idle=97.0)

        built = by_name(metrics.build_cpu_metrics(NOW, cpu, DEVICE))

        self.assertEqual(value_of(built["pnls.cpu.iowait"]), 0)


class TestBuildMemoryMetrics(unittest.TestCase):
    def test_memory_and_swap_values(self):
        built = by_name(metrics.build_memory_metrics(NOW, MEMORY, SWAP, DEVICE))

        self.assertEqual(
            {name: value_of(metric) for name, metric in built.items()},
            {
                "pnls.mem.used": 600,
                "pnls.mem.free": 200,
                "pnls.mem.total": 1_000,
                "pnls.mem.pct_usable": 0.4,
                "pnls.swap.used": 50,
            },
        )


class TestBuildDiskMetrics(unittest.TestCase):
    def test_disk_values(self):
        built = by_name(metrics.build_disk_metrics(NOW, DISK, DEVICE))

        self.assertEqual(
            {name: value_of(metric) for name, metric in built.items()},
            {"pnls.disk.in_use": 0.3, "pnls.disk.used": 30, "pnls.disk.free": 70},
        )

    def test_disk_metrics_are_tagged_with_the_root_device(self):
        for metric in metrics.build_disk_metrics(NOW, DISK, DEVICE):
            with self.subTest(metric=metric["metric"]):
                self.assertEqual(metric["tags"], [HOST_TAG, "device:/"])


class TestBuildIoMetrics(unittest.TestCase):
    def test_read_and_write_rates(self):
        built = by_name(metrics.build_io_metrics(NOW, 12.5, 7.0, DEVICE))

        self.assertEqual(value_of(built["pnls.io.r_s"]), 12.5)
        self.assertEqual(value_of(built["pnls.io.w_s"]), 7.0)


class TestBuildUptimeMetric(unittest.TestCase):
    def test_uptime_in_seconds(self):
        self.assertEqual(
            metrics.build_uptime_metric(NOW, 3_600.0, DEVICE),
            [{"metric": "pnls.uptime", "points": [(NOW, 3_600.0)], "tags": [HOST_TAG]}],
        )


class TestBuildAllMetrics(unittest.TestCase):
    def build(self):
        return metrics.build_all_metrics(
            now=NOW,
            device_name=DEVICE,
            cpu=CPU,
            mem=MEMORY,
            swap=SWAP,
            disk=DISK,
            reads_per_sec=12.5,
            writes_per_sec=7.0,
            uptime=3_600.0,
        )

    def test_every_metric_in_dashboard_order(self):
        self.assertEqual(
            [metric["metric"] for metric in self.build()],
            [
                "pnls.heartbeat",
                "pnls.cpu.user",
                "pnls.cpu.system",
                "pnls.cpu.idle",
                "pnls.cpu.iowait",
                "pnls.mem.used",
                "pnls.mem.free",
                "pnls.mem.total",
                "pnls.mem.pct_usable",
                "pnls.swap.used",
                "pnls.disk.in_use",
                "pnls.disk.used",
                "pnls.disk.free",
                "pnls.io.r_s",
                "pnls.io.w_s",
                "pnls.uptime",
            ],
        )

    def test_every_metric_is_one_point_at_now_tagged_with_the_host(self):
        for metric in self.build():
            with self.subTest(metric=metric["metric"]):
                self.assertEqual(len(metric["points"]), 1)
                self.assertEqual(metric["points"][0][0], NOW)
                self.assertIn(HOST_TAG, metric["tags"])


if __name__ == "__main__":
    unittest.main()
