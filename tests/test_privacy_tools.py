import contextlib
import io
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

from relay_agent.cli import main
from tools.privacy_audit import issues, audit
from tools.build_release import normalize_sdist


class PrivacyTests(unittest.TestCase):
    def test_synthetic_examples_allowed(self):
        self.assertEqual(issues("192.0.2.10 2001:db8::10 https://www.example.com"), [])

    def test_nonexample_network_identity_rejected(self):
        ipv4 = ".".join(["198", "18", "1", "9"])
        ipv6 = ":".join(["2001", "abcd", "abcd", "abcd", "1", "2", "3", "4"])
        self.assertIn("nonexample_ipv4", issues(ipv4))
        self.assertIn("nonexample_ipv6", issues(ipv6))

    def test_unknown_arguments_never_echo_secrets(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            main(["--password", "SYNTHETIC_SECRET_MUST_NOT_ESCAPE"])
        self.assertNotIn("SYNTHETIC_SECRET_MUST_NOT_ESCAPE", output.getvalue())

    def test_arbitrary_file_excluded_from_public_tree(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); (root / "unknown.txt").write_text("example")
            self.assertIn(("unknown.txt", "not_in_public_allowlist"), audit(root))

    def test_staged_secret_is_detected_even_with_clean_working_copy(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
            readme = root / "README.md"
            readme.write_text("-----BEGIN " + "PRIVATE KEY-----")
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True, capture_output=True)
            readme.write_text("Safe synthetic documentation")
            self.assertIn(("index:README.md", "private_key"), audit(root))

    def test_source_archive_owner_metadata_is_detected_and_removed(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); archive = root / "fixture.tar.gz"
            with tarfile.open(archive, "w:gz") as out:
                member = tarfile.TarInfo("fixture/README.md")
                member.uname = "SYNTHETIC_PERSON"; member.uid = 12345
                member.size = 7; out.addfile(member, io.BytesIO(b"example"))
            self.assertIn((archive.name, "archive_metadata"), audit(root, artifacts=archive))
            normalize_sdist(archive)
            self.assertFalse(any(rule == "archive_metadata" for _, rule in audit(root, artifacts=archive)))
