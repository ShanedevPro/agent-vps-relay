import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from relay_agent.core import Store, RelayError, digest, read_json, write_private
from relay_agent.cli import main
from relay_agent.privacy import public_report


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve())
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "private")
        self.store.init("demo", {"credential": "SYNTHETIC_SECRET_MUST_NOT_ESCAPE"})

    def test_rerun_preserves_credentials(self):
        with self.assertRaises(RelayError):
            self.store.init("demo", {"credential": "replacement"})
        self.assertEqual(self.store.load("demo")["credential"], "SYNTHETIC_SECRET_MUST_NOT_ESCAPE")

    def test_profile_traversal_rejected(self):
        for value in ["../x", "", "/tmp/x", "a/b", "-x", "UPPER"]:
            with self.subTest(value=value), self.assertRaises(RelayError):
                self.store.profile(value)

    @unittest.skipIf(os.name == "nt", "POSIX modes")
    def test_private_permissions(self):
        p = self.store.profile("demo")
        self.assertEqual(p.stat().st_mode & 0o777, 0o700)
        self.assertEqual((p / "profile.json").stat().st_mode & 0o777, 0o600)

    def test_cleanup_only_unchanged_owned_files(self):
        base = self.store.profile("demo")
        a, b = base / "temp/a", base / "temp/b"
        write_private(a, {"x": 1}); write_private(b, {"x": 2})
        self.store.record_temp("demo", a); self.store.record_temp("demo", b)
        write_private(b, {"user_changed": True})
        with patch("relay_agent.core.file_in_use", return_value=False):
            result = self.store.cleanup("demo")
        self.assertEqual(result, {"removed": 1, "skipped_modified_or_unsafe": 1})
        self.assertFalse(a.exists()); self.assertTrue(b.exists())
        self.assertTrue((base / "profile.json").exists())

    def test_cleanup_protects_active_file_and_checkpoint_dependency(self):
        base = self.store.profile("demo")
        a, b = base / "temp/core", base / "temp/settings"
        write_private(a, "fixture"); write_private(b, "fixture")
        self.store.record_temp("demo", a); self.store.record_temp("demo", b)
        write_private(base / "baseline.json", {"restore_argv": [str(b)]})
        with patch("relay_agent.core.file_in_use", return_value=True):
            self.assertEqual(self.store.cleanup("demo")["removed"], 0)
        with patch("relay_agent.core.file_in_use", return_value=False):
            self.assertEqual(self.store.cleanup("demo")["removed"], 1)
        self.assertTrue(b.exists())

    def test_private_store_cannot_live_in_git_child(self):
        root = Path(self.tmp.name) / "public"
        (root / ".git").mkdir(parents=True)
        with self.assertRaises(RelayError):
            Store(root / "nested/private")

    def test_does_not_claim_nonempty_user_directory(self):
        root = Path(self.tmp.name) / "user"
        root.mkdir(); (root / "precious").write_text("keep")
        with self.assertRaises(RelayError):
            Store(root).init("demo", {})
        self.assertEqual((root / "precious").read_text(), "keep")

    def test_report_reflects_autonomous_rollback(self):
        self.store.update("demo", phase="verified")
        write_private(self.store.profile("demo") / "leases/trial/lease.json",
                      {"id": "trial", "proof": False, "phase": "rolled_back", "created": 1})
        write_private(self.store.profile("demo") / "leases/proof/lease.json",
                      {"id": "proof", "proof": True, "phase": "proof_passed", "created": 2})
        self.assertEqual(public_report(self.store.current_state("demo"))["phase"], "rolled_back")

    def test_cleanup_rejects_manifest_escape(self):
        base = self.store.profile("demo")
        outside = base / "precious"
        write_private(outside, "keep")
        write_private(base / "owned.json", {"temp/../precious": digest(outside.read_bytes())})
        self.assertEqual(self.store.cleanup("demo")["removed"], 0)
        self.assertTrue(outside.exists())

    def test_cleanup_refuses_active_and_failed_recovery(self):
        for phase in ["armed", "switched", "restoring", "recovery_failed", "proof_pending"]:
            write_private(self.store.profile("demo") / "leases/abc/lease.json", {"phase": phase})
            with self.subTest(phase=phase), self.assertRaises(RelayError):
                self.store.cleanup("demo")

    def test_registration_cannot_include_credentials(self):
        with self.assertRaises(RelayError):
            self.store.record_temp("demo", self.store.profile("demo") / "profile.json")

    @unittest.skipIf(os.name == "nt", "Symlink privilege varies")
    def test_symlink_not_deleted(self):
        base = self.store.profile("demo")
        other = Path(self.tmp.name) / "other"
        write_private(other, "keep")
        (base / "temp").mkdir()
        link = base / "temp/link"
        link.symlink_to(other)
        write_private(base / "owned.json", {"temp/link": digest(other.read_bytes())})
        self.assertEqual(self.store.cleanup("demo")["removed"], 0)
        self.assertTrue(other.exists())

    @unittest.skipIf(os.name == "nt", "Symlink privilege varies")
    def test_private_read_rejects_symlink_parent(self):
        root = Path(self.tmp.name)
        (root / "alias").symlink_to(self.store.root, target_is_directory=True)
        with self.assertRaises(RelayError):
            read_json(root / "alias/profiles/demo/profile.json")

    def test_export_drops_unknown_fields_and_nested_values(self):
        state = {"phase": "verified", "password": "SECRET", "endpoint": "192.0.2.8", "hostname": "person",
                 "checks": {"google": True, "github": {"secret": "SECRET"}, "exit": "SECRET", "freeform": "SECRET"}}
        report = public_report(state)
        self.assertEqual(report["checks"], {"google": True})
        self.assertNotIn("SECRET", json.dumps(report))
        self.assertNotIn("192.0.2.8", json.dumps(report))

    def test_cli_error_never_prints_raw_profile(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--state-dir", str(self.store.root), "apply", "--profile", "demo", "--approved-plan", "bad"])
        self.assertNotEqual(code, 0)
        self.assertNotIn("SYNTHETIC_SECRET_MUST_NOT_ESCAPE", output.getvalue())
        self.assertNotIn(str(self.store.root), output.getvalue())
