import ipaddress
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from relay_agent.core import Store, RelayError, digest, read_json, write_private, run
from relay_agent import remote, management

TAILSCALE_FIXTURE = str(ipaddress.ip_address("100.64.0.0") + 10)


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve())
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "private")
        self.config = {"ssh": {"host": "192.0.2.10", "user": "relayadmin", "port": 22,
                               "identity_file": str(Path(self.tmp.name) / "key"),
                               "known_hosts_file": str(Path(self.tmp.name) / "known"),
                               "fingerprint": "SHA256:EXAMPLE", "identity_verified": True},
                       "server": {"address": "192.0.2.10", "reality_target": "www.example.com:443",
                                  "reality_sni": "www.example.com", "target_validated": True}}
        Path(self.config["ssh"]["identity_file"]).write_text("SYNTHETIC_ONLY")
        Path(self.config["ssh"]["known_hosts_file"]).write_text("SYNTHETIC_ONLY")
        self.store.init("demo", self.config)
        self.observed = {"ok": True, "os_id": "debian", "os_version": "13", "machine": "x86_64",
                         "managed_id": None, "port_conflict": False}

    def test_independently_pinned_key_required(self):
        self.config["ssh"]["identity_verified"] = False
        with patch("relay_agent.remote.run", return_value=subprocess.CompletedProcess([], 0, "256 SHA256:EXAMPLE host (ED25519)\n", "")):
            with self.assertRaises(RelayError):
                remote.validate_ssh(self.config)

    def test_wrong_known_key_rejected(self):
        with patch("relay_agent.remote.run", return_value=subprocess.CompletedProcess([], 0, "256 SHA256:WRONG host (ED25519)\n", "")):
            with self.assertRaises(RelayError):
                remote.validate_ssh(self.config)

    def test_ssh_options_cannot_be_injected(self):
        for host in ["-oProxyCommand=bad", "192.0.2.10; bad", "x\nbad"]:
            self.config["ssh"]["host"] = host
            with self.assertRaises(RelayError):
                remote.validate_ssh(self.config)

    def test_plan_cannot_overwrite_foreign_service(self):
        with patch("relay_agent.remote.call", return_value={**self.observed, "port_conflict": True}):
            with self.assertRaises(RelayError):
                remote.plan(self.store, "demo")

    def test_unlisted_server_os_stops_for_research(self):
        with patch("relay_agent.remote.call", return_value={**self.observed, "os_id": "other"}):
            with self.assertRaises(RelayError) as cm:
                remote.plan(self.store, "demo")
        self.assertEqual(cm.exception.code, "needs_research")

    def test_stale_plan_does_not_apply(self):
        with patch("relay_agent.remote.call", return_value=self.observed):
            result = remote.plan(self.store, "demo")
        c = self.store.load("demo"); c["server"]["address"] = "192.0.2.11"
        write_private(self.store.profile("demo") / "profile.json", c)
        with patch("relay_agent.remote.call") as call, self.assertRaises(RelayError):
            remote.apply(self.store, "demo", result["plan_digest"])
        call.assert_not_called()

    def test_server_changed_since_review_not_applied(self):
        with patch("relay_agent.remote.call", return_value=self.observed):
            result = remote.plan(self.store, "demo")
        with patch("relay_agent.remote.call", return_value={**self.observed, "managed_id": "other"}) as call:
            with self.assertRaises(RelayError):
                remote.apply(self.store, "demo", result["plan_digest"])
            self.assertEqual(call.call_count, 1)

    def test_server_credentials_only_saved_privately(self):
        with patch("relay_agent.remote.call", return_value=self.observed):
            result = remote.plan(self.store, "demo")
        with patch("relay_agent.remote.call", side_effect=[self.observed, {"ok": True, "credentials": {"password": "SYNTHETIC_ONLY"}}]):
            public = remote.apply(self.store, "demo", result["plan_digest"])
        self.assertNotIn("SYNTHETIC_ONLY", json.dumps(public))
        self.assertEqual(read_json(self.store.profile("demo") / "credentials.json")["password"], "SYNTHETIC_ONLY")

    def test_missing_console_or_root_account_blocks_hardening(self):
        for config in [self.config, {**self.config, "ssh": {**self.config["ssh"], "user": "root"},
                                    "management": {"console_recovery_verified": True, "addresses": [TAILSCALE_FIXTURE]}}]:
            with self.assertRaises(RelayError):
                management.private_access(config)

    def test_hardening_requires_real_tailscale_range(self):
        config = {**self.config, "management": {"console_recovery_verified": True, "addresses": ["192.0.2.10"]}}
        with self.assertRaises(RelayError):
            management.private_access(config)

    def test_server_commit_requires_both_fresh_protocol_checks(self):
        config = self.store.load("demo")
        config["management"] = {"console_recovery_verified": True, "addresses": [TAILSCALE_FIXTURE]}
        write_private(self.store.profile("demo") / "profile.json", config)
        lease = {"id": "example", "deadline": time.time() + 500}
        write_private(self.store.profile("demo") / "management-lease.json", lease)
        evidence = self.store.profile("demo") / "evidence.json"
        write_private(evidence, {"profile_digest": digest(config), "observed_at": time.time(),
                                 "public_ipv4_ssh_blocked": True, "public_ipv6_ssh_blocked": True})
        with patch("relay_agent.management.call", return_value={"ok": True, "public_addresses": ["192.0.2.10"]}) as call:
            with self.assertRaises(RelayError):
                management.finish(self.store, "demo", commit=True, evidence=evidence)
            self.assertEqual(call.call_count, 1)  # Fresh private SSH only, no commit.

    def prepare_management_commit(self, address, public_addresses, checks):
        config = self.store.load("demo")
        config["server"]["address"] = address
        config["management"] = {"console_recovery_verified": True, "addresses": [TAILSCALE_FIXTURE]}
        write_private(self.store.profile("demo") / "profile.json", config)
        lease = {"id": "example", "deadline": time.time() + 500}
        write_private(self.store.profile("demo") / "management-lease.json", lease)
        evidence = self.store.profile("demo") / "evidence.json"
        write_private(evidence, {"profile_digest": digest(config), "observed_at": time.time(), **checks})
        result = {key: True for key in ["google", "github", "exit", "udp_dns", "direct_path"]}
        self.store.update("demo", protocol_checks={protocol: {"checks": result, "observed_at": time.time()}
                                                  for protocol in ["reality", "hysteria2"]})
        return evidence, {"ok": True, "public_addresses": public_addresses}

    def test_ipv4_only_management_commit_does_not_require_ipv6(self):
        evidence, observed = self.prepare_management_commit("192.0.2.10", ["192.0.2.10"], {"public_ipv4_ssh_blocked": True})
        with patch("relay_agent.management.call", side_effect=[observed, {"phase": "committed"}]) as call:
            self.assertEqual(management.finish(self.store, "demo", commit=True, evidence=evidence)["phase"], "committed")
            self.assertEqual(call.call_args.args[1], "harden_commit")

    def test_ipv6_only_management_commit_does_not_require_ipv4(self):
        evidence, observed = self.prepare_management_commit("2001:db8::10", ["2001:db8::10"], {"public_ipv6_ssh_blocked": True})
        with patch("relay_agent.management.call", side_effect=[observed, {"phase": "committed"}]):
            self.assertEqual(management.finish(self.store, "demo", commit=True, evidence=evidence)["phase"], "committed")

    def test_assigned_ipv6_is_required_even_with_ipv4_node(self):
        evidence, observed = self.prepare_management_commit("192.0.2.10", ["192.0.2.10", "2001:db8::10"], {"public_ipv4_ssh_blocked": True})
        with patch("relay_agent.management.call", return_value=observed) as call, self.assertRaises(RelayError):
            management.finish(self.store, "demo", commit=True, evidence=evidence)
        self.assertEqual(call.call_count, 1)

    def test_nat_endpoint_and_extra_provider_addresses_are_included(self):
        config = {"server": {"address": "192.0.2.10"}, "management": {"public_addresses": ["2001:db8::10"]}}
        self.assertEqual(management.public_families(config, {"public_addresses": []}), {4, 6})

    def test_missing_server_address_inventory_cannot_skip_checks(self):
        with self.assertRaises(RelayError):
            management.public_families(self.config, {"ok": True})

    def test_raw_process_errors_not_forwarded(self):
        with patch("relay_agent.core.subprocess.run", return_value=subprocess.CompletedProcess([], 1, "SYNTHETIC_ONLY", "SYNTHETIC_ONLY")):
            with self.assertRaises(RelayError) as cm:
                run(["example"])
        self.assertNotIn("SYNTHETIC_ONLY", str(cm.exception))
