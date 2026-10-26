import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from relay_agent.clients import mihomo_config
from relay_agent.core import RelayError, write_private
from relay_agent.downloads import catalog, download, unpack
from relay_agent.inspect import inspect_host
from relay_agent.probes import loopback_proxy


def credentials():
    return {"address": "2001:db8::10", "reality": {"uuid": "00000000-0000-4000-8000-000000000001",
            "sni": "www.example.com", "public_key": "EXAMPLE_PUBLIC_KEY", "short_id": "0123456789abcdef"},
            "hysteria2": {"password": "SYNTHETIC_ONLY", "sni": "relay.invalid", "pin_sha256": "ab" * 32}}


class ClientTests(unittest.TestCase):
    def test_isolated_configs_never_take_over_network(self):
        for protocol in ["reality", "hysteria2"]:
            config = mihomo_config(credentials(), protocol, interface="discovered-interface")
            self.assertEqual(config["bind-address"], "127.0.0.1")
            self.assertFalse(config["allow-lan"])
            self.assertFalse(config["tun"]["enable"])
            self.assertFalse(config["dns"]["enable"])
            self.assertNotIn("external-controller", config)

    def test_pin_is_mandatory_without_an_unchecked_tls_bypass(self):
        config = mihomo_config(credentials(), "hysteria2")
        self.assertEqual(config["proxies"][0]["fingerprint"], "ab" * 32)
        self.assertFalse(config["proxies"][0]["skip-cert-verify"])

    def test_missing_or_malformed_pin_cannot_be_staged(self):
        for pin in ["", "chrome", "ab" * 31]:
            c = credentials(); c["hysteria2"]["pin_sha256"] = pin
            with self.subTest(pin=pin), self.assertRaises(RelayError):
                mihomo_config(c, "hysteria2")

    def test_reality_no_multiplex(self):
        p = mihomo_config(credentials(), "reality")["proxies"][0]
        self.assertEqual(p["flow"], "xtls-rprx-vision")
        self.assertFalse(p["smux"]["enabled"])

    def test_test_proxy_must_be_loopback(self):
        for url in ["http://192.0.2.1:7890", "http://user:secret@127.0.0.1:7890", "https://127.0.0.1:7890"]:
            with self.subTest(url=url), self.assertRaises(RelayError):
                loopback_proxy(url)

    def test_inspection_when_nothing_installed(self):
        with patch("relay_agent.inspect.shutil.which", return_value=None):
            result = inspect_host()
        self.assertEqual(result["phase"], "needs_user_action")
        self.assertEqual(result["missing_tools"], ["ssh", "ssh-keygen", "curl"])
        self.assertFalse(result["client_device_confirmed"])

    def test_unlisted_architecture_needs_research(self):
        with patch("relay_agent.inspect.platform.machine", return_value="future-arch"):
            self.assertEqual(inspect_host()["architecture"], "unknown")
        with tempfile.TemporaryDirectory() as t, self.assertRaises(RelayError):
            download("mihomo", "unknown-future", Path(t) / "x")

    def test_download_lock_has_no_mutable_latest_urls(self):
        for platforms in catalog()["artifacts"].values():
            for entry in platforms.values():
                self.assertEqual(len(entry["sha256"]), 64)
                self.assertNotIn("/latest/", entry["url"])
                self.assertIn("/releases/download/", entry["url"])

    def test_bad_checksum_rejected_before_extraction(self):
        import io
        response = io.BytesIO(b"unexpected")
        response.url = "https://github.com/example/artifact"
        with tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve()) as t:
            with patch("relay_agent.downloads.urllib.request.urlopen", return_value=response):
                with self.assertRaises(RelayError):
                    download("mihomo", "linux-amd64", Path(t) / "x")
            self.assertFalse((Path(t) / "x").exists())

    def test_verified_cached_artifact_reused_without_download(self):
        raw = b"synthetic artifact"
        entry = {"repository": "example/project", "url": "https://github.com/example/project/releases/download/v1/core",
                 "sha256": hashlib.sha256(raw).hexdigest(), "format": "raw"}
        with tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve()) as t:
            archive = Path(t) / "archive"; write_private(archive, raw, raw=True)
            with patch("relay_agent.downloads.catalog", return_value={"artifacts": {"fixture": {"test": entry}}}), \
                 patch("relay_agent.downloads.urllib.request.urlopen") as fetch:
                self.assertEqual(download("fixture", "test", archive), entry)
                fetch.assert_not_called()

    def test_modified_archive_rejected_before_unpack(self):
        with tempfile.TemporaryDirectory() as t:
            archive = Path(t) / "archive"; archive.write_bytes(b"changed")
            with self.assertRaises(RelayError):
                unpack({"format": "raw", "sha256": "00" * 32}, archive, Path(t) / "core")
            self.assertFalse((Path(t) / "core").exists())

    def test_unpack_never_replaces_a_different_existing_runtime(self):
        raw = b"synthetic artifact"
        with tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve()) as t:
            archive, binary = Path(t) / "archive", Path(t) / "core"
            write_private(archive, raw, raw=True); write_private(binary, b"existing client", raw=True)
            with self.assertRaises(RelayError):
                unpack({"format": "raw", "sha256": hashlib.sha256(raw).hexdigest()}, archive, binary)
            self.assertEqual(binary.read_bytes(), b"existing client")
