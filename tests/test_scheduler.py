from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from relay_agent.core import RelayError
from relay_agent.scheduler import Scheduler


class SchedulerTests(unittest.TestCase):
    def test_unknown_os_has_no_detached_fallback(self):
        with tempfile.TemporaryDirectory() as t, patch("relay_agent.scheduler.run") as run:
            with self.assertRaises(RelayError):
                Scheduler("UnknownOS").launch("agent-vps-relay-example", Path(t), Path(t))
            run.assert_not_called()

    def test_cannot_cancel_an_unrelated_task(self):
        with patch("relay_agent.scheduler.run") as run:
            for system in ["Darwin", "Linux", "Windows"]:
                with self.subTest(system=system), self.assertRaises(RelayError):
                    Scheduler(system).cancel("other-network-worker")
            run.assert_not_called()

    def test_retirement_requires_readback(self):
        for system in ["Darwin", "Linux", "Windows"]:
            with self.subTest(system=system), patch("relay_agent.scheduler.os.getuid", return_value=123, create=True), \
                 patch("relay_agent.scheduler.run", return_value=subprocess.CompletedProcess([], 0, "", "")), self.assertRaises(RelayError):
                Scheduler(system).cancel("agent-vps-relay-example")

    def test_completed_owned_job_can_be_retired(self):
        for system in ["Darwin", "Linux", "Windows"]:
            codes = [0, 0, 1] if system == "Windows" else [0, 1]
            results = [subprocess.CompletedProcess([], code, "", "") for code in codes]
            with self.subTest(system=system), patch("relay_agent.scheduler.os.getuid", return_value=123, create=True), \
                 patch("relay_agent.scheduler.run", side_effect=results) as run:
                Scheduler(system).cancel("agent-vps-relay-example")
                self.assertTrue(all("agent-vps-relay-example" in " ".join(c.args[0]) for c in run.call_args_list))
