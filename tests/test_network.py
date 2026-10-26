import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from relay_agent import clientctl
from relay_agent.clients import prepare_controller
from relay_agent.core import RelayError, Store, write_private
from relay_agent.probes import verify_network


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve())
        self.addCleanup(self.tmp.cleanup)
        self.selected = "original"
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path == "/redirect":
                    self.send_response(302)
                    self.send_header("Location", "/configs")
                    self.end_headers()
                    return
                if self.headers.get("Authorization") != "Bearer SYNTHETIC_CONTROLLER_SECRET":
                    self.send_response(401); self.end_headers(); return
                body = ({"now": owner.selected, "all": ["original", "candidate"]}
                        if self.path == "/proxies/relay" else {"mode": "rule", "tun": {"enable": False}})
                self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(body).encode())

            def do_PUT(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.selected = body["name"]
                self.send_response(204); self.end_headers()

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        secret = Path(self.tmp.name) / "secret"
        write_private(secret, b"SYNTHETIC_CONTROLLER_SECRET", raw=True)
        self.settings = {"controller": "http://127.0.0.1:" + str(server.server_port), "secret_file": str(secret),
                         "group": "relay", "baseline_node": "original", "candidate_node": "candidate",
                         "proxy": "http://127.0.0.1:17890"}

    def test_real_loopback_controller_switch_and_restore(self):
        with patch("relay_agent.clientctl.system_snapshot", return_value={"proxy": "original", "dns": "original"}):
            baseline = clientctl.execute(self.settings, "snapshot")
            clientctl.execute(self.settings, "switch")
            self.assertEqual(clientctl.execute(self.settings, "snapshot")["selected"], "candidate")
            clientctl.execute(self.settings, "restore")
            self.assertEqual(clientctl.execute(self.settings, "snapshot"), baseline)

    def test_controller_redirect_cannot_forward_credentials(self):
        with self.assertRaises(RelayError):
            clientctl.request(self.settings, "/redirect")

    def test_preparation_does_not_switch_and_preserves_captured_adapter(self):
        store = Store(Path(self.tmp.name) / "private"); store.init("demo", {})
        result = prepare_controller(store, "demo", self.settings)
        self.assertFalse(result["networking_changed"])
        self.assertEqual(self.selected, "original")
        before = (store.profile("demo") / "controller.json").read_bytes()
        write_private(store.profile("demo") / "baseline.json", {})
        with self.assertRaises(RelayError):
            prepare_controller(store, "demo", {**self.settings, "group": "other"})
        self.assertEqual((store.profile("demo") / "controller.json").read_bytes(), before)


class ProbeTests(unittest.TestCase):
    def probe(self, *, address="192.0.2.10", fail_http=False, udp=True, direct=True):
        def curl(argv, **kwargs):
            self.assertEqual(argv[:2], ["curl", "-q"])
            self.assertIn("--proxy", argv)
            self.assertIn("--noproxy", argv)
            if "https://www.cloudflare.com/cdn-cgi/trace" in argv:
                Path(argv[argv.index("-o") + 1]).write_text("ip=" + address + "\n")
                return subprocess.CompletedProcess(argv, 0, "", "")
            return subprocess.CompletedProcess(argv, 1 if fail_http else 0,
                                               "204" if "https://www.google.com/generate_204" in argv else "200", "")
        with patch("relay_agent.probes.run", side_effect=curl), patch("relay_agent.probes.udp_dns", return_value=udp):
            return verify_network("http://127.0.0.1:17890", ["192.0.2.10", "2001:db8::10"], direct_evidence=direct)

    def test_expected_ipv4_and_ipv6_egress(self):
        for address in ["192.0.2.10", "2001:db8::10"]:
            self.assertTrue(all(self.probe(address=address).values()))

    def test_old_proxy_egress_and_missing_direct_evidence_rejected(self):
        self.assertFalse(self.probe(address="192.0.2.99")["exit"])
        self.assertFalse(self.probe(direct=False)["direct_path"])

    def test_blocked_udp_and_http_or_dns_failure_remain_failures(self):
        self.assertFalse(self.probe(udp=False)["udp_dns"])
        self.assertFalse(self.probe(fail_http=True)["google"])
