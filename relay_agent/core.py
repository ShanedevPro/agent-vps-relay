"""Private storage, typed errors, and shell-free subprocesses."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile


class RelayError(Exception):
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)


def require(condition, code, message):
    if not condition:
        raise RelayError(code, message)


def digest(value) -> str:
    data = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True).encode()
    return hashlib.sha256(data).hexdigest()


def private_dir(path: Path) -> Path:
    path = Path(path).expanduser()
    # Reject any existing symlink ancestor, not just the final component.
    for parent in (path, *path.parents):
        require(not parent.is_symlink(), "unsafe_path", "Private storage cannot traverse symlinks.")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        path.chmod(0o700)
    else:
        # chmod does not make Windows files private. Restrict directory inheritance.
        import csv
        try:
            raw = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True, text=True, check=True).stdout
            sid = next(csv.reader([raw.strip()]))[1]
            subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", "*" + sid + ":(OI)(CI)F",
                            "*S-1-5-18:(OI)(CI)F"], capture_output=True, check=True)
        except (OSError, ValueError, subprocess.SubprocessError, IndexError):
            raise RelayError("private_acl_failed", "Cannot establish a private Windows directory; stop before saving secrets.") from None
    return path


def write_private(path: Path, value, *, raw=False):
    private_dir(path.parent)
    require(not path.is_symlink(), "unsafe_path", "Refusing to replace a symlink.")
    fd, tmp = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            data = value if raw else (json.dumps(value, indent=2) + "\n").encode()
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
        if os.name != "nt":
            path.chmod(0o600)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_json(path: Path):
    path = Path(path).absolute()
    require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)),
            "missing_state", "Required private state is missing or unsafe.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError):
        raise RelayError("invalid_state", "Private JSON is invalid; inspect it locally.") from None


@contextmanager
def lock(path: Path):
    """OS locks release when a process dies; no stale PID-file deadlocks."""
    private_dir(path.parent)
    require(not path.is_symlink(), "unsafe_path", "Unsafe lock path.")
    with path.open("a+b") as f:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            if not f.read(1):
                f.write(b"0")
                f.flush()
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            os.chmod(path, 0o600)
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


def run(argv, *, stdin=None, timeout=30, check=True):
    require(isinstance(argv, list) and argv and all(isinstance(x, str) and "\x00" not in x for x in argv),
            "invalid_command", "Commands must be nonempty argument arrays.")
    try:
        result = subprocess.run(argv, input=stdin, capture_output=True, text=True,
                                timeout=timeout, shell=False)
    except (OSError, subprocess.TimeoutExpired):
        raise RelayError("command_unavailable", "A required command failed or timed out; inspect requirements locally.") from None
    if check:
        # Never propagate arbitrary stdout/stderr: installers and clients print secrets.
        require(result.returncode == 0, "command_failed", "A command failed; no raw command output was published.")
    return result


def file_in_use(path):
    """Unknown is protected. Cleanup must not delete a running core or open config."""
    executable = shutil.which("lsof")
    if not executable:
        return True
    try:
        result = run([executable, "-F", "p", "--", str(path)], check=False, timeout=5)
        # lsof uses 1 for no matching open file. Every other result is protected.
        return result.returncode != 1 or bool(result.stdout.strip()) or bool(result.stderr.strip())
    except RelayError:
        return True


def referenced_paths(value):
    if isinstance(value, dict):
        return set().union(*(referenced_paths(x) for x in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(referenced_paths(x) for x in value)) if value else set()
    if isinstance(value, str) and Path(value).is_absolute():
        return {Path(os.path.abspath(value))}
    return set()


class Store:
    def __init__(self, root=None):
        if root is None:
            root = (Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "AgentVpsRelay"
                    if os.name == "nt" else Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "agent-vps-relay")
        self.root = Path(os.path.abspath(Path(root).expanduser()))
        require(self.root not in {Path.home(), *Path.home().parents} and self.root.name not in {".ssh", ".codex", ".config"}
                and not any((p / ".git").exists() for p in (self.root, *self.root.parents)),
                "unsafe_state_root", "Use a dedicated private state directory, outside a Git repository.")

    def profile(self, name: str) -> Path:
        require(bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", name)), "invalid_profile", "Use a short lowercase profile identifier.")
        return self.root / "profiles" / name

    def load(self, name):
        return read_json(self.profile(name) / "profile.json")

    def init(self, name, config):
        path = self.profile(name)
        marker = self.root / ".store.json"
        require(not self.root.exists() or marker.exists() or not any(self.root.iterdir()),
                "unsafe_state_root", "An existing nonempty directory is not an owned private store; choose a new directory.")
        private_dir(self.root)
        with lock(self.root / ".store.lock"):
            if marker.exists():
                require(read_json(marker) == {"owner": "agent-vps-relay", "schema_version": 1},
                        "unsafe_state_root", "Private store ownership is invalid.")
            else:
                write_private(marker, {"owner": "agent-vps-relay", "schema_version": 1})
        private_dir(self.root / "profiles")
        private_dir(path)
        with lock(path / ".lock"):
            require(not (path / "profile.json").exists(), "profile_exists", "Use status/resume; initialization never rotates existing credentials.")
            write_private(path / "profile.json", config)
            write_private(path / "state.json", {"phase": "needs_user_action", "checks": {}})

    def state(self, name):
        return read_json(self.profile(name) / "state.json")

    def current_state(self, name):
        """Autonomous workers update their lease even if the CLI never runs again."""
        state = self.state(name)
        trials = [read_json(p) for p in (self.profile(name) / "leases").glob("*/lease.json")]
        trials = [j for j in trials if not j.get("proof")]
        if trials:
            latest = max(trials, key=lambda j: j.get("created", 0))
            if latest["phase"] == "rolled_back":
                state["phase"] = "rolled_back"
            elif latest["phase"] == "recovery_failed":
                state["phase"] = "needs_user_action"
            elif latest["phase"] in {"armed", "switching", "switched", "restoring"}:
                state["phase"] = "testing"
        return state

    def update(self, name, **values):
        path = self.profile(name)
        with lock(path / ".lock"):
            state = self.state(name)
            state.update(values)
            write_private(path / "state.json", state)
        return state

    def record_temp(self, name, path):
        """Only a dedicated run/temp subtree is eligible for cleanup."""
        base = self.profile(name)
        target = Path(path).absolute()
        temp = base / "temp"
        require(target.is_relative_to(temp) and target.is_file() and not target.is_symlink(),
                "unsafe_cleanup", "Only project-owned temporary regular files can be registered.")
        with lock(base / ".lock"):
            manifest = read_json(base / "owned.json") if (base / "owned.json").exists() else {}
            manifest[str(target.relative_to(base))] = digest(target.read_bytes())
            write_private(base / "owned.json", manifest)

    def assert_idle(self, name):
        base = self.profile(name)
        for lease in (base / "leases").glob("*/lease.json"):
            require(read_json(lease).get("phase") in {"committed", "rolled_back", "proof_passed", "proof_failed"},
                    "recovery_armed", "Resolve recovery before replacing or deleting its possible dependencies.")
        if (base / "management-lease.json").exists():
            require(read_json(base / "management-lease.json").get("phase") in {"committed", "rolled_back"},
                    "recovery_armed", "Resolve the server firewall lease before cleanup or staging changes.")

    def cleanup(self, name):
        base = self.profile(name)
        with lock(base / ".lock"):
            self.assert_idle(name)
            # Keep *all* cleanup blocked while proof or recovery may need artifacts.
            for lease in (base / "leases").glob("*/lease.json"):
                require(read_json(lease).get("phase") in {"committed", "rolled_back", "proof_passed", "proof_failed"},
                        "recovery_armed", "Cleanup is blocked while a recovery job is active.")
            manifest = read_json(base / "owned.json") if (base / "owned.json").exists() else {}
            protected = set()
            for checkpoint in base.rglob("*.json"):
                if checkpoint == base / "owned.json" or checkpoint.is_relative_to(base / "temp"):
                    continue
                protected.update(referenced_paths(read_json(checkpoint)))
            removed, skipped = 0, 0
            for rel, checksum in list(manifest.items()):
                target = base / rel
                safe = (not Path(rel).is_absolute() and ".." not in Path(rel).parts and target.is_relative_to(base / "temp")
                        and not any(p.is_symlink() for p in (target, *target.parents))
                        and target.is_file() and digest(target.read_bytes()) == checksum
                        and target not in protected and not file_in_use(target))
                if safe:
                    target.unlink()
                    removed += 1
                    del manifest[rel]
                else:
                    skipped += 1
            write_private(base / "owned.json", manifest)
            return {"removed": removed, "skipped_modified_or_unsafe": skipped}
