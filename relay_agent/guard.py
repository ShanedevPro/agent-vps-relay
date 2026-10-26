"""A fail-closed cutover lease; the OS worker never needs the agent's network."""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import sys
import time

from .core import RelayError, digest, lock, private_dir, read_json, require, run, write_private
from .scheduler import Scheduler

TERMINAL = {"committed", "rolled_back", "recovery_failed", "proof_passed", "proof_failed"}


def action(argv):
    require(isinstance(argv, list) and argv and Path(argv[0]).is_absolute(),
            "invalid_adapter", "Client actions require absolute executable paths and argument arrays.")
    return run(argv, timeout=12)


def capture(client):
    try:
        result = json.loads(action(client["capture_argv"]).stdout)
        require(isinstance(result, dict), "invalid_adapter", "Client snapshots must be JSON objects covering the full transition.")
        return result
    except (KeyError, ValueError):
        raise RelayError("invalid_adapter", "The client snapshot adapter must return JSON.") from None


def health(client):
    try:
        obj = json.loads(action(client["baseline_health_argv"]).stdout)
        return obj.get("ok") is True
    except (RelayError, KeyError, ValueError, AttributeError):
        return False


def binding(client):
    files = {}
    for key in ["capture_argv", "restore_argv", "switch_argv", "baseline_health_argv"]:
        argv = client.get(key)
        require(isinstance(argv, list) and argv and all(isinstance(x, str) and "\x00" not in x for x in argv),
                "invalid_adapter", "Supply the complete client adapter contract.")
        require(Path(argv[0]).is_absolute(), "invalid_adapter", "Adapter executable paths must be absolute.")
        for arg in argv:
            p = Path(arg)
            if p.is_file() and (arg == argv[0] or p.suffix in {".py", ".sh", ".ps1"}):
                require(not p.is_symlink(), "invalid_adapter", "Resolve executable/script symlinks before recording the adapter.")
                files[str(p)] = digest(p.read_bytes())
    for name in client.get("immutable_files", []):
        p = Path(name)
        require(p.is_absolute() and p.is_file() and not p.is_symlink(), "invalid_adapter", "An immutable adapter dependency is missing.")
        files[str(p)] = digest(p.read_bytes())
    return digest({"client": client, "executables": files})


def prepare_runtime(root):
    source = Path(__file__).parent
    files = [p for p in source.iterdir() if p.suffix in {".py", ".json"}]
    version = digest({p.name: digest(p.read_bytes()) for p in files})[:20]
    destination = root / "runtime" / version
    private_dir(destination / "relay_agent")
    for p in files:
        out = destination / "relay_agent" / p.name
        if not out.exists():
            write_private(out, p.read_bytes(), raw=True)
        require(digest(out.read_bytes()) == digest(p.read_bytes()), "runtime_changed", "Private recovery runtime is inconsistent.")
    return destination


def snapshot(store, profile):
    client = store.load(profile).get("client", {})
    client_binding = binding(client)
    require(health(client), "baseline_unhealthy", "The original connection is not healthy; do not stage a takeover.")
    state = capture(client)
    path = store.profile(profile) / "baseline.json"
    require(not path.exists(), "baseline_exists", "An existing baseline must not be overwritten; use status/resume.")
    write_private(path, {"client": client, "binding": client_binding, "snapshot": state, "created": time.time()})
    return {"phase": "staged", "baseline_saved": True}


def new_job(store, profile, *, proof=False, ttl=180, scheduler=None):
    base = store.profile(profile)
    client = store.load(profile).get("client", {})
    baseline = read_json(base / "baseline.json")
    require(binding(client) == baseline["binding"], "baseline_changed", "Adapter changed; review and capture a new baseline in a new profile.")
    require(health(client) and capture(client) == baseline["snapshot"],
            "baseline_changed", "Current connection differs from the verified baseline.")
    if not proof:
        p = read_json(base / "proof.json")
        require(p.get("binding") == baseline["binding"] and p.get("phase") == "proof_passed"
                and p.get("worker_pid") and p.get("worker_pid") != p.get("launcher_pid")
                and 0 <= time.time() - p.get("finished", 0) < 1800,
                "recovery_unproven", "A fresh unattended recovery proof is required.")
        require(30 <= ttl <= 900, "invalid_ttl", "A live cutover lease must be between 30 and 900 seconds.")
    for existing in (base / "leases").glob("*/lease.json"):
        require(read_json(existing).get("phase") in TERMINAL - {"recovery_failed"},
                "recovery_armed", "Resolve the existing recovery job before creating another.")
    ident = secrets.token_hex(12)
    directory = base / "leases" / ident
    private_dir(directory)
    now = time.time()
    job = {"id": ident, "label": "agent-vps-relay-" + ident, "phase": "proof_pending" if proof else "armed",
           "proof": proof, "deadline": now + ttl, "monotonic_deadline": time.monotonic() + ttl,
           "client": client, "binding": baseline["binding"], "baseline": baseline["snapshot"],
           "profile_path": str(base), "created": now, "launcher_pid": os.getpid()}
    write_private(directory / "lease.json", job)
    runtime = prepare_runtime(store.root)
    offline = [sys.executable, str(runtime / "relay_agent/worker.py"), str(directory), "--restore"]
    command_text = __import__("subprocess").list2cmdline(offline) if os.name == "nt" else shlex.join(offline)
    # Offline instructions contain no passwords or import URIs.
    write_private(base / "RECOVER.txt", (
        "If the agent disappears, leave this computer running. The OS worker will restore the original connection.\n"
        "If automatic recovery fails, open the original client and restore its profile, proxy and DNS settings.\n"
        "Recorded original settings: " + str(base / "baseline.json") + "\n"
        "Local checkpoint: " + str(directory) + "\n"
        "Manual recovery (run locally, no Internet required):\n" +
        command_text + "\n"
    ).encode(), raw=True)
    scheduler = scheduler or Scheduler()
    try:
        scheduler.launch(job["label"], directory, runtime)
    except RelayError:
        job["phase"] = "proof_failed" if proof else "blocked"
        write_private(directory / "lease.json", job)
        raise
    return {"lease": ident, "phase": job["phase"], "ttl_seconds": ttl}


def lease_path(store, profile, ident):
    require(isinstance(ident, str) and len(ident) == 24 and all(c in "0123456789abcdef" for c in ident),
            "invalid_lease", "Invalid lease identifier.")
    return store.profile(profile) / "leases" / ident


def switch(store, profile, ident):
    directory = lease_path(store, profile, ident)
    with lock(directory / ".lock"):
        job = read_json(directory / "lease.json")
        require(not job["proof"] and job["phase"] == "armed" and job["deadline"] - time.time() > 25,
                "invalid_lease", "Only an armed, unexpired lease can switch the client.")
        require(binding(store.load(profile)["client"]) == job["binding"], "adapter_changed", "The client adapter changed.")
        require(capture(job["client"]) == job["baseline"], "baseline_changed", "Current state changed outside this trial.")
        job["phase"] = "switching"
        write_private(directory / "lease.json", job)
    # Never hold the worker's lock during a slow external command.
    try:
        action(job["client"]["switch_argv"])
    except RelayError:
        restore(directory)
        raise
    with lock(directory / ".lock"):
        current = read_json(directory / "lease.json")
        require(current["phase"] == "switching" and time.time() < current["deadline"],
                "lease_expired", "The trial expired; recovery owns the connection now.")
        candidate = capture(job["client"])
        require(candidate != job["baseline"], "candidate_not_selected", "The candidate did not change the captured client state; recovery stays armed.")
        current.update(phase="switched", candidate_snapshot=candidate)
        write_private(directory / "lease.json", current)
    return {"phase": "testing", "lease": ident, "commit_requires_fresh_agent_response": True}


def verified_candidate(store, profile, ident, checks):
    require(checks and all(type(v) is bool and v for v in checks.values()) and
            {"google", "github", "exit", "udp_dns", "direct_path"} <= checks.keys(),
            "verification_failed", "Candidate checks failed or direct-path evidence is missing; do not commit.")
    directory = lease_path(store, profile, ident)
    with lock(directory / ".lock"):
        job = read_json(directory / "lease.json")
        require(job["phase"] == "switched" and time.time() < job["deadline"], "invalid_lease", "No active switched trial.")
        require(capture(job["client"]) == job["candidate_snapshot"], "candidate_changed", "Candidate changed outside the trial.")
        token = secrets.token_hex(16)
        job.update(checks=checks, verified_at=time.time(), commit_token=token)
        write_private(directory / "lease.json", job)
    return {"phase": "testing", "lease": ident, "commit_token": token,
            "next": "After a fresh agent response, explicitly commit in a separate action; otherwise leave recovery armed."}


def commit(store, profile, ident, token, scheduler=None):
    directory = lease_path(store, profile, ident)
    with lock(directory / ".lock"):
        job = read_json(directory / "lease.json")
        require(job["phase"] == "switched" and time.time() < job["deadline"] and
                time.time() - job.get("verified_at", 0) <= 60 and
                secrets.compare_digest(str(token), str(job.get("commit_token", ""))) and bool(token),
                "commit_rejected", "A fresh verification token and separate agent acknowledgement are required.")
        require(binding(store.load(profile)["client"]) == job["binding"] and capture(job["client"]) == job["candidate_snapshot"],
                "candidate_changed", "Client state or adapter changed; do not commit.")
        require(time.time() < job["deadline"] and time.monotonic() < job["monotonic_deadline"],
                "lease_expired", "The lease expired during final verification.")
        job.update(phase="committed", finished=time.time())
        job.pop("commit_token", None)
        write_private(directory / "lease.json", job)
    store.update(profile, phase="verified", checks=job["checks"])
    (scheduler or Scheduler()).cancel(job["label"])
    return {"phase": "verified", "lease": ident}


def restore(directory, *, unattended=False):
    """Bounded restoration, using only locally available recorded actions."""
    with lock(directory / ".lock"):
        job = read_json(directory / "lease.json")
        if job["phase"] in TERMINAL:
            return job["phase"]
        job["phase"] = "restoring"
        write_private(directory / "lease.json", job)
    ok = False
    for _ in range(3):
        try:
            action(job["client"]["restore_argv"])
            ok = health(job["client"]) and capture(job["client"]) == job["baseline"]
            if ok:
                break
        except (RelayError, OSError, ValueError):
            pass
        time.sleep(1)
    with lock(directory / ".lock"):
        current = read_json(directory / "lease.json")
        # A successful commit never races a rollback, since commit is rejected in restoring state.
        proof_ok = ok and unattended and current.get("worker_pid") != current.get("launcher_pid")
        current.update(phase=("proof_passed" if proof_ok else "proof_failed") if job["proof"] else
                       ("rolled_back" if ok else "recovery_failed"), finished=time.time())
        write_private(directory / "lease.json", current)
        if job["proof"]:
            write_private(Path(job["profile_path"]) / "proof.json", {
                "phase": current["phase"], "binding": job["binding"], "finished": current["finished"],
                "launcher_pid": current.get("launcher_pid"),
                "worker_pid": current.get("worker_pid"), "worker_ppid": current.get("worker_ppid")})
    return current["phase"]


def worker(directory):
    directory = Path(directory)
    with lock(directory / ".lock"):
        job = read_json(directory / "lease.json")
        job.update(worker_pid=os.getpid(), worker_ppid=os.getppid())
        write_private(directory / "lease.json", job)
    if job["proof"]:
        restore(directory, unattended=True)
        return
    while True:
        with lock(directory / ".lock"):
            job = read_json(directory / "lease.json")
            if job["phase"] in TERMINAL:
                return
            expired = time.time() >= job["deadline"] or time.monotonic() >= job["monotonic_deadline"]
        if expired:
            restore(directory, unattended=True)
            return
        time.sleep(0.25)
