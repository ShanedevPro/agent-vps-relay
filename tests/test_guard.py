import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from relay_agent import guard
from relay_agent.core import Store, RelayError, read_json, write_private

CHECKS = {x: True for x in ["google", "github", "exit", "udp_dns", "direct_path"]}


class FakeScheduler:
    def __init__(self):
        self.launched, self.cancelled = [], []
    def launch(self, *args, **kwargs):
        self.launched.append(args)
    def cancel(self, label):
        self.cancelled.append(label)


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve())
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.fake = root / "fixture.json"
        self.fake.write_text(json.dumps({"selected": "original", "proxy": "original", "dns": "original"}))
        self.store = Store(root / "private")
        script = Path(__file__).parent / "fixtures/client.py"
        self.client = {key: [str(Path(sys.executable).resolve()), str(script.resolve()), op, str(self.fake)]
                       for key, op in [("capture_argv", "capture"), ("restore_argv", "restore"),
                                       ("switch_argv", "switch"), ("baseline_health_argv", "health")]}
        self.store.init("demo", {"client": self.client})
        self.scheduler = FakeScheduler()
        guard.snapshot(self.store, "demo")

    def prove(self):
        proof = guard.new_job(self.store, "demo", proof=True, scheduler=self.scheduler)
        with patch("relay_agent.guard.os.getpid", return_value=os.getpid() + 1000):
            guard.worker(guard.lease_path(self.store, "demo", proof["lease"]))
        self.assertEqual(read_json(self.store.profile("demo") / "proof.json")["phase"], "proof_passed")

    def arm(self):
        self.prove()
        return guard.new_job(self.store, "demo", scheduler=self.scheduler)["lease"]

    def test_arm_requires_executed_proof(self):
        with self.assertRaises(RelayError):
            guard.new_job(self.store, "demo", scheduler=self.scheduler)

    def test_manual_restore_cannot_certify_unattended_proof(self):
        job = guard.new_job(self.store, "demo", proof=True, scheduler=self.scheduler)
        result = guard.restore(guard.lease_path(self.store, "demo", job["lease"]))
        self.assertEqual(result, "proof_failed")
        with self.assertRaises(RelayError):
            guard.new_job(self.store, "demo", scheduler=self.scheduler)

    def test_arming_does_not_switch(self):
        self.arm()
        self.assertEqual(json.loads(self.fake.read_text())["selected"], "original")

    def test_worker_restores_network_state_without_commit(self):
        ident = self.arm()
        guard.switch(self.store, "demo", ident)
        directory = guard.lease_path(self.store, "demo", ident)
        job = read_json(directory / "lease.json")
        job["deadline"] = time.time() - 1
        write_private(directory / "lease.json", job)
        guard.worker(directory)
        self.assertEqual(read_json(directory / "lease.json")["phase"], "rolled_back")
        self.assertEqual(json.loads(self.fake.read_text()), {"selected": "original", "proxy": "original", "dns": "original"})

    def test_google_success_without_agent_commit_still_rolls_back(self):
        ident = self.arm()
        guard.switch(self.store, "demo", ident)
        token = guard.verified_candidate(self.store, "demo", ident, CHECKS)["commit_token"]
        self.assertTrue(token)
        directory = guard.lease_path(self.store, "demo", ident)
        job = read_json(directory / "lease.json"); job["deadline"] = time.time() - 1
        write_private(directory / "lease.json", job)
        guard.worker(directory)
        self.assertEqual(read_json(directory / "lease.json")["phase"], "rolled_back")

    def test_wrong_or_missing_agent_ack_rejected(self):
        ident = self.arm(); guard.switch(self.store, "demo", ident)
        guard.verified_candidate(self.store, "demo", ident, CHECKS)
        for token in [None, "", "wrong"]:
            with self.subTest(token=token), self.assertRaises(RelayError):
                guard.commit(self.store, "demo", ident, token, self.scheduler)

    def test_commit_only_cancels_own_job(self):
        ident = self.arm(); guard.switch(self.store, "demo", ident)
        token = guard.verified_candidate(self.store, "demo", ident, CHECKS)["commit_token"]
        guard.commit(self.store, "demo", ident, token, self.scheduler)
        self.assertEqual(self.scheduler.cancelled, ["agent-vps-relay-" + ident])
        guard.worker(guard.lease_path(self.store, "demo", ident))
        self.assertEqual(json.loads(self.fake.read_text())["selected"], "broken-candidate")

    def test_reject_commit_before_switch_and_verification(self):
        ident = self.arm()
        with self.assertRaises(RelayError):
            guard.commit(self.store, "demo", ident, "anything", self.scheduler)

    def test_failed_pin_or_direct_path_cannot_verify(self):
        ident = self.arm(); guard.switch(self.store, "demo", ident)
        for key in CHECKS:
            checks = dict(CHECKS); checks[key] = False
            with self.subTest(key=key), self.assertRaises(RelayError):
                guard.verified_candidate(self.store, "demo", ident, checks)

    def test_changed_adapter_requires_new_proof(self):
        self.prove()
        config = self.store.load("demo")
        config["client"]["switch_argv"][-2] = "restore"
        write_private(self.store.profile("demo") / "profile.json", config)
        with self.assertRaises(RelayError):
            guard.new_job(self.store, "demo", scheduler=self.scheduler)

    def test_permission_failure_blocks_arm(self):
        config = self.store.load("demo")
        config["client"]["restore_argv"][-2] = "fail"
        write_private(self.store.profile("demo") / "profile.json", config)
        # Create a new baseline for the changed adapter in a separate profile.
        self.store.init("blocked", config)
        guard.snapshot(self.store, "blocked")
        proof = guard.new_job(self.store, "blocked", proof=True, scheduler=self.scheduler)
        with patch("relay_agent.guard.time.sleep"):
            guard.worker(guard.lease_path(self.store, "blocked", proof["lease"]))
        with self.assertRaises(RelayError):
            guard.new_job(self.store, "blocked", scheduler=self.scheduler)

    def test_nearly_expired_trial_cannot_start(self):
        ident = self.arm(); directory = guard.lease_path(self.store, "demo", ident)
        job = read_json(directory / "lease.json"); job["deadline"] = time.time() + 1
        write_private(directory / "lease.json", job)
        with self.assertRaises(RelayError):
            guard.switch(self.store, "demo", ident)

    def test_resume_does_not_rotate_or_reinitialize(self):
        ident = self.arm(); before = self.store.load("demo")
        from relay_agent.cli import status
        self.assertEqual(status(self.store, "demo")["leases"][-1]["lease"], ident)
        self.assertEqual(self.store.load("demo"), before)

    def test_guard_runtime_is_outside_repository(self):
        self.arm()
        runtime = self.scheduler.launched[-1][2]
        self.assertTrue(runtime.is_relative_to(self.store.root))
        self.assertTrue((runtime / "relay_agent/worker.py").is_file())
