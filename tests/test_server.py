import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from relay_agent import server_payload as server


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve())
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        for name in ["ROOT", "ETC", "BIN"]:
            p = patch.object(server, name, root / name.lower()); p.start(); self.addCleanup(p.stop)
        self.config = {"deployment_id": "fixture-deployment", "ssh": {"port": 22},
                       "server": {"address": "192.0.2.10", "reality_target": "www.example.com:443",
                                  "reality_sni": "www.example.com", "target_validated": True}}
        self.artifacts = {"xray": {"version": "fixture"}, "hysteria2": {"version": "fixture"}}
        self.request = {"config": self.config, "artifacts": self.artifacts}
        self.observed = {"os_id": "debian", "os_version": "13", "machine": "amd64", "port_conflict": False,
                         "managed_id": self.config["deployment_id"]}

    def test_interrupted_dependency_install_keeps_bound_pending_receipt(self):
        with patch.object(server, "inspect", return_value=self.observed), patch.object(server.os, "geteuid", return_value=0, create=True), \
             patch.object(server.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")), \
             patch.object(server, "command", side_effect=RuntimeError("synthetic dependency failure")):
            with self.assertRaises(RuntimeError):
                server.deploy(self.request)
        pending = json.loads((server.ROOT / "pending.json").read_text())
        self.assertEqual(pending["settings"], server.deployment_settings(self.config, self.artifacts))

    def test_pending_settings_cannot_silently_change(self):
        server.save(server.ROOT / "pending.json", {"deployment_id": self.config["deployment_id"], "settings": {"different": True}})
        with patch.object(server, "inspect", return_value=self.observed), patch.object(server.os, "geteuid", return_value=0, create=True), \
             patch.object(server, "command") as command:
            with self.assertRaises(ValueError):
                server.deploy(self.request)
            command.assert_not_called()

    def test_resume_preserves_credentials_and_refuses_file_drift(self):
        binary = server.BIN / "fixture"; binary.parent.mkdir(); binary.write_bytes(b"synthetic binary")
        receipt = {"versions": {k: v["version"] for k, v in self.artifacts.items()},
                   "settings": server.deployment_settings(self.config, self.artifacts),
                   "credentials": {"fixture_password": "SYNTHETIC_ONLY"},
                   "files": {str(binary): hashlib.sha256(binary.read_bytes()).hexdigest()}}
        server.save(server.ROOT / "receipt.json", receipt)
        with patch.object(server, "inspect", return_value=self.observed), patch.object(server.os, "geteuid", return_value=0, create=True), \
             patch.object(server, "command", return_value="active"), patch.object(server, "fetch") as fetch:
            first = server.deploy(self.request); second = server.deploy(self.request)
            self.assertEqual(first["credentials"], second["credentials"])
            fetch.assert_not_called()
            binary.write_bytes(b"changed")
            with self.assertRaises(ValueError):
                server.deploy(self.request)

    def test_firewall_staging_never_enables_or_broadens_active_ssh(self):
        for active in [True, False]:
            with patch.object(server.shutil, "copytree"), patch.object(server, "command", return_value="Status: active" if active else "Status: inactive") as command:
                server.stage_firewall(self.config)
                calls = [c.args[0] for c in command.call_args_list]
                self.assertFalse(any("enable" in argv or "disable" in argv for argv in calls))
                self.assertEqual(any("22/tcp" in argv for argv in calls), not active)
                self.assertTrue(any("443/tcp" in argv for argv in calls))
                self.assertTrue(any("443/udp" in argv for argv in calls))
