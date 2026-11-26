"""Unit tests for the agent loop, on a fake host and clock."""

import unittest
from unittest import mock

from tests.support.metrics_agent_fakes import (
    BOOT_TIME,
    READS_PER_SECOND,
    WRITES_PER_SECOND,
    FakeHost,
    StopLoop,
)
from tests.support.metrics_agent_loader import import_metrics_agent_module

main = import_metrics_agent_module("collector_metrics_agent.main")

DEVICE = "RPI-3"
INTERVAL = 10
# Time between the import of `main` (which takes the first disk reading) and `start()`.
IMPORT_LEAD_SECONDS = 0.001


class AgentLoopTestCase(unittest.TestCase):
    def setUp(self):
        self.send = self.patch("send_metrics", return_value=True)
        self.patch("DEVICE_NAME", DEVICE)
        self.patch("DATADOG_TIMEOUT", INTERVAL)

    def patch(self, name, value=mock.DEFAULT, **kwargs):
        patcher = mock.patch.object(main, name, value, **kwargs)
        patched = patcher.start()
        self.addCleanup(patcher.stop)
        return patched

    def run_agent(self, iterations: int, between=None, configure=None) -> FakeHost:
        """Runs `start()` for a number of iterations.

        `configure(host)` runs before `start()`, and `between(host)` after each sleep.
        """
        host = FakeHost(iterations=iterations)
        if configure is not None:
            configure(host)
        self.patch("psutil", host.psutil)
        self.patch("time", host.time)
        # As on import of `main`, just before `start()` is called.
        self.patch("prev_disk_io", host.disk_io_counters())
        self.patch("prev_time", host.wall_time())
        host.advance(IMPORT_LEAD_SECONDS)

        if between is not None:
            sleep = host.sleep

            def sleep_then(seconds):
                sleep(seconds)
                between(host)

            host.time.sleep = sleep_then

        with self.assertRaises(StopLoop):
            main.start()
        return host

    def sent(self, iteration: int) -> dict[str, float]:
        metrics = self.send.call_args_list[iteration].args[0]
        return {metric["metric"]: metric["points"][0][1] for metric in metrics}


class TestAgentLoop(AgentLoopTestCase):
    def test_each_iteration_sends_every_metric(self):
        self.run_agent(iterations=2)

        self.assertEqual(self.send.call_count, 2)
        for iteration in range(2):
            with self.subTest(iteration=iteration):
                self.assertEqual(len(self.sent(iteration)), 16)

    def test_metrics_are_tagged_with_the_configured_device(self):
        self.run_agent(iterations=1)

        for metric in self.send.call_args.args[0]:
            self.assertIn(f"host:{DEVICE}", metric["tags"])

    def test_cpu_is_sampled_over_one_second_and_disk_usage_is_for_root(self):
        host = self.run_agent(iterations=2)

        self.assertEqual(host.cpu_intervals, [1, 1])
        self.assertEqual(host.disk_paths, ["/", "/"])

    def test_waits_the_configured_interval_between_sends(self):
        host = self.run_agent(iterations=2)

        self.assertEqual(host.sleeps, [INTERVAL, INTERVAL])

    def test_uptime_is_the_time_since_boot(self):
        host = FakeHost()
        start = host.wall_time() + IMPORT_LEAD_SECONDS

        self.run_agent(iterations=1)

        self.assertAlmostEqual(self.sent(0)["pnls.uptime"], start - BOOT_TIME)

    def test_disk_rates_after_the_first_iteration(self):
        self.run_agent(iterations=2)

        self.assertAlmostEqual(self.sent(1)["pnls.io.r_s"], READS_PER_SECOND)
        self.assertAlmostEqual(self.sent(1)["pnls.io.w_s"], WRITES_PER_SECOND)

    def test_a_failed_send_does_not_stop_the_agent(self):
        self.send.return_value = False

        self.run_agent(iterations=3)

        self.assertEqual(self.send.call_count, 3)

    def test_the_last_reading_is_kept_for_the_next_rate(self):
        host = self.run_agent(iterations=1)

        self.assertEqual(main.prev_disk_io, host.disk_io_counters())


class TestAgentLoopKnownBugs(AgentLoopTestCase):
    @unittest.expectedFailure
    def test_first_disk_rates_match_the_real_rate(self):
        """Known bug: the first rate divides a second of disk I/O by the time since import (about
        a millisecond), so it is about 1000 times too high. Remove the decorator once the first
        sample is measured over the right interval, or skipped.
        """
        self.run_agent(iterations=1)

        # A fix may also skip the first rates; only rates that are sent must be right.
        first = self.sent(0)
        for name, rate in (
            ("pnls.io.r_s", READS_PER_SECOND),
            ("pnls.io.w_s", WRITES_PER_SECOND),
        ):
            with self.subTest(metric=name):
                self.assertLess(abs(first.get(name, rate) - rate), rate * 0.1)

    @unittest.expectedFailure
    def test_disk_rates_ignore_a_forward_wall_clock_step(self):
        """Known bug: the rates divide by wall clock time, so an NTP step (a Raspberry Pi has no
        hardware clock) makes them almost zero. Remove the decorator once `time.monotonic()` is used.
        """

        def ntp_step(host):
            host.wall_offset += 3_600

        self.run_agent(iterations=2, between=ntp_step)

        self.assertAlmostEqual(self.sent(1)["pnls.io.r_s"], READS_PER_SECOND)

    @unittest.expectedFailure
    def test_disk_rates_ignore_a_backward_wall_clock_step(self):
        """Known bug: a backward step makes the elapsed time negative, so the rates are sent as 0.
        Remove the decorator once `time.monotonic()` is used.
        """

        def ntp_step(host):
            host.wall_offset -= 3_600

        self.run_agent(iterations=2, between=ntp_step)

        self.assertAlmostEqual(self.sent(1)["pnls.io.r_s"], READS_PER_SECOND)

    @unittest.expectedFailure
    def test_a_failed_reading_does_not_stop_the_agent(self):
        """Known issue: an exception from psutil ends `start()`, which also stops the heartbeat.
        Remove the decorator once each iteration catches and logs its errors.
        """

        def fail_first_memory_reading(host):
            memory = host.psutil.virtual_memory
            readings = iter([OSError("Cannot read /proc/meminfo")])

            def virtual_memory():
                error = next(readings, None)
                if error is not None:
                    raise error
                return memory()

            host.psutil.virtual_memory = virtual_memory

        self.run_agent(iterations=2, configure=fail_first_memory_reading)

        self.assertEqual(self.send.call_count, 1)


if __name__ == "__main__":
    unittest.main()
