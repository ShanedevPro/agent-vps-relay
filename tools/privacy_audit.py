"""Audit the proposed public tree, Git blobs and built archives; print rule names only."""
import argparse
import ipaddress
from pathlib import Path
import re
import subprocess
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIRS = {"relay_agent", "tests", "tools", "skills", "examples", "docs", ".github"}
PUBLIC_FILES = {"README.md", "README.en.md", "AGENT.md", "AGENTS.md", "LICENSE", ".gitignore", "pyproject.toml", "MANIFEST.in", "validation.json"}
PRIVATE_FILENAMES = {"profile.json", "credentials.json", "controller.json", "known_hosts", "state.json"}
EXCLUDED = {".git", ".venv", "__pycache__", ".test-work", "build", "dist"}
DOC_NETWORKS = [ipaddress.ip_network(x) for x in ["192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24"]]
RULES = {
    "private_key": re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    "personal_home": re.compile(r"(?:/Users/|/home/)[a-zA-Z][^/\s\"']+/"),
    "github_token": re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
    "credential_uri": re.compile(r"(?:vless|hy2|hysteria2?|trojan)://[^\s\"'<>]{12,}"),
}


def issues(text):
    found = [name for name, regex in RULES.items() if regex.search(text)]
    for value in re.findall(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])", text):
        try:
            ip = ipaddress.ip_address(value)
        except ValueError:
            continue
        if not (ip.is_loopback or ip.is_unspecified or value in {"1.1.1.1", "100.64.0.0"} or any(ip in n for n in DOC_NETWORKS)):
            found.append("nonexample_ipv4")
    for email in re.findall(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text):
        if not email.endswith(("@example.com", "@example.org", "@example.net", "@users.noreply.github.com")):
            found.append("personal_email")
    for value in re.findall(r"(?<![\w:])(?:[0-9a-fA-F]{0,4}:){2,}[0-9a-fA-F:.]*(?![\w:])", text):
        try:
            ip = ipaddress.ip_address(value)
        except ValueError:
            continue
        if ip.version == 6 and not (ip.is_loopback or ip.is_unspecified or ip in ipaddress.ip_network("2001:db8::/32")
                                    or value == "fd7a:115c:a1e0::"):
            found.append("nonexample_ipv6")
    return sorted(set(found))


def scan_bytes(name, data, problems):
    if len(data) > 2 * 1024 * 1024:
        problems.append((name, "oversized_public_file"))
        return
    try:
        text = data.decode("utf-8")
    except UnicodeError:
        problems.append((name, "unexpected_binary"))
        return
    for rule in issues(text):
        problems.append((name, rule))


def scan_artifacts(path, problems):
    candidates = [path] if path.is_file() else list(path.glob("*"))
    if not candidates:
        problems.append(("artifacts", "no_artifacts_found"))
    for item in candidates:
        if item.suffix == ".whl":
            with zipfile.ZipFile(item) as archive:
                if archive.comment:
                    problems.append((item.name, "archive_metadata"))
                for member in archive.infolist():
                    if member.extra or member.comment:
                        problems.append((item.name, "archive_metadata"))
                    if Path(member.filename).name in PRIVATE_FILENAMES:
                        problems.append((item.name, "private_filename"))
                    if member.file_size > 2 * 1024 * 1024:
                        problems.append((item.name, "oversized_public_file"))
                    elif not member.is_dir():
                        scan_bytes(item.name + ":" + member.filename, archive.read(member), problems)
        elif item.name.endswith(".tar.gz"):
            header = item.read_bytes()[:10]
            if len(header) < 10 or header[3] & 24 or header[4:8] != b"\0\0\0\0":
                problems.append((item.name, "archive_metadata"))
            with tarfile.open(item) as archive:
                for member in archive.getmembers():
                    if member.uid or member.gid or member.uname not in {"", "root"} or member.gname not in {"", "root"} or member.pax_headers:
                        problems.append((item.name, "archive_metadata"))
                    if Path(member.name).name in PRIVATE_FILENAMES:
                        problems.append((item.name, "private_filename"))
                    if member.size > 2 * 1024 * 1024:
                        problems.append((item.name, "oversized_public_file"))
                    elif member.isfile():
                        scan_bytes(item.name + ":" + member.name, archive.extractfile(member).read(), problems)
        else:
            problems.append((item.name, "unrecognized_artifact"))


def audit(root=ROOT, artifacts=None):
    problems = []
    result = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True)
    tracked = {x.decode() for x in result.stdout.split(b"\0") if x} if result.returncode == 0 else set()
    candidates = set(tracked)
    for p in root.rglob("*"):
        rel = p.relative_to(root)
        if p.is_file() and not any(x in EXCLUDED or x.endswith(".egg-info") for x in rel.parts):
            candidates.add(str(rel).replace("\\", "/"))
    for rel in sorted(candidates):
        path = root / rel
        parts = Path(rel).parts
        if parts[0] not in PUBLIC_DIRS and rel not in PUBLIC_FILES:
            problems.append((rel, "not_in_public_allowlist"))
            continue
        if not path.is_file() or path.is_symlink():
            problems.append((rel, "missing_or_symlink"))
            continue
        if path.name in PRIVATE_FILENAMES:
            problems.append((rel, "private_filename"))
        scan_bytes(rel, path.read_bytes(), problems)
    # The index can differ from the working tree. Scan the actual proposed blobs too.
    index = subprocess.run(["git", "ls-files", "--stage", "-z"], cwd=root, capture_output=True)
    for entry in index.stdout.split(b"\0") if index.returncode == 0 else []:
        if not entry:
            continue
        metadata, _, name = entry.partition(b"\t")
        mode, sha, stage = metadata.decode().split()
        rel = name.decode()
        if mode != "100644" and mode != "100755":
            problems.append(("index:" + rel, "unreviewed_file_type"))
            continue
        size = subprocess.run(["git", "cat-file", "-s", sha], cwd=root, capture_output=True, text=True)
        if size.returncode or int(size.stdout) > 2 * 1024 * 1024:
            problems.append(("index:" + rel, "oversized_public_file"))
            continue
        blob = subprocess.run(["git", "cat-file", "-p", sha], cwd=root, capture_output=True)
        scan_bytes("index:" + rel, blob.stdout, problems)
    history = subprocess.run(["git", "rev-list", "--objects", "--all"], cwd=root, capture_output=True, text=True)
    if history.returncode == 0:
        for line in history.stdout.splitlines():
            sha, _, name = line.partition(" ")
            kind = subprocess.run(["git", "cat-file", "-t", sha], cwd=root, capture_output=True, text=True)
            if kind.stdout.strip() in {"blob", "commit"}:
                size = subprocess.run(["git", "cat-file", "-s", sha], cwd=root, capture_output=True, text=True)
                if size.returncode or int(size.stdout) > 2 * 1024 * 1024:
                    problems.append(("history:" + (name or sha[:10]), "oversized_public_file"))
                    continue
                blob = subprocess.run(["git", "cat-file", "-p", sha], cwd=root, capture_output=True)
                scan_bytes("history:" + (name or sha[:10]), blob.stdout, problems)
    if artifacts:
        scan_artifacts(artifacts, problems)
    return problems


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path)
    args = parser.parse_args()
    failures = audit(artifacts=args.artifact)
    for filename, rule in failures:
        print(filename + ": " + rule)
    print("Privacy audit: " + ("FAILED" if failures else "passed"))
    raise SystemExit(bool(failures))
