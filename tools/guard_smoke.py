"""Real OS scheduler acceptance using file fixtures only. Never touches networking."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from relay_agent import guard
from relay_agent.core import Store, read_json, write_private
from relay_agent.scheduler import Scheduler


def wait_phase(path, phases, limit=40):
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        state = read_json(path)
        if state["phase"] in phases:
            return state
        time.sleep(0.2)
    raise RuntimeError("OS worker did not reach the expected fixture state")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    root = args.root or (Path.home() / ".config/agent-vps-relay-lab" / uuid.uuid4().hex)
    store = Store(root)
    # Claim the dedicated empty store before creating private fixtures in it.
    store.init("lab", {})
    fixture = root / "fixture.json"
    write_private(fixture, {"selected": "original", "proxy": "original", "dns": "original"})
    script = root / "fixture_client.py"
    write_private(script, (Path(__file__).parent.parent / "tests/fixtures/client.py").read_bytes(), raw=True)
    client = {key: [str(Path(sys.executable).resolve()), str(script), operation, str(fixture)]
              for key, operation in [("capture_argv", "capture"), ("restore_argv", "restore"),
                                     ("switch_argv", "switch"), ("baseline_health_argv", "health")]}
    write_private(store.profile("lab") / "profile.json", {"client": client})
    guard.snapshot(store, "lab")
    labels = []
    try:
        proof = guard.new_job(store, "lab", proof=True)
        proof_path = guard.lease_path(store, "lab", proof["lease"]) / "lease.json"
        labels.append(read_json(proof_path)["label"])
        result = wait_phase(proof_path, {"proof_passed", "proof_failed"})
        assert result["phase"] == "proof_passed"
        assert result["worker_pid"] != os.getpid()
        Scheduler().cancel(labels[-1])
        # The launcher dies after a simulated switch. The native OS worker must survive it.
        program = '''import json,os,signal,sys
from pathlib import Path
from relay_agent.core import Store
from relay_agent import guard
s=Store(Path(sys.argv[1]))
j=guard.new_job(s,'lab',ttl=30)
guard.switch(s,'lab',j['lease'])
print(json.dumps({**j,'launcher_pid':os.getpid()}),flush=True)
os.kill(os.getpid(),signal.SIGTERM)
'''
        child = subprocess.run([sys.executable, "-c", program, str(root)], capture_output=True, text=True)
        assert child.returncode != 0
        trial = json.loads(child.stdout)
        trial_path = guard.lease_path(store, "lab", trial["lease"]) / "lease.json"
        labels.append(read_json(trial_path)["label"])
        state = wait_phase(trial_path, {"rolled_back", "recovery_failed"}, 50)
        assert state["phase"] == "rolled_back"
        assert state["worker_pid"] != trial["launcher_pid"]
        assert read_json(fixture) == {"selected": "original", "proxy": "original", "dns": "original"}
        output = {"os": __import__("platform").system(), "proof_executed": True,
                  "launcher_terminated": True, "os_worker_restored_fixture": True, "real_network_changed": False}
        write_private(root / "result.json", output)
        print(json.dumps(output))
    finally:
        for path in (store.profile("lab") / "leases").glob("*/lease.json"):
            job = read_json(path)
            labels.append(job["label"])
            if job["phase"] not in guard.TERMINAL:
                guard.restore(path.parent)
        for label in set(labels):
            Scheduler().cancel(label)


if __name__ == "__main__":
    main()
