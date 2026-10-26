"""Small JSON CLI. Human intent remains with the agent; mechanics fail closed."""
import argparse
import json
import os
from pathlib import Path
import platform
import sys
import time

from . import __version__
from .core import RelayError, Store, digest, read_json, require, write_private
from .inspect import inspect_host


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's ordinary error echoes arbitrary unrecognized input, including pasted secrets.
        print(json.dumps({"phase": "blocked", "error": "invalid_arguments", "message": "Invalid arguments; use --help. Input values were not echoed."}))
        raise SystemExit(2)


def parser():
    p = SafeParser(description="Agent VPS Relay: inspect, stage, verify, then guard a connection trial.")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--state-dir", type=Path)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("inspect")
    init = sub.add_parser("init")
    init.add_argument("--profile", required=True)
    init.add_argument("--config", type=Path, required=True)
    for verb in ["status", "resume", "plan", "cleanup", "report"]:
        s = sub.add_parser(verb)
        s.add_argument("--profile", required=True)
    boot = sub.add_parser("bootstrap")
    boot.add_argument("--profile")
    boot.add_argument("--component", choices=["mihomo", "xray", "hysteria2"])
    boot.add_argument("--platform")
    boot.add_argument("--keep", action="store_true", help="Keep a required native runtime outside disposable temp files")
    apply = sub.add_parser("apply")
    apply.add_argument("--profile", required=True)
    apply.add_argument("--approved-plan", required=True)
    client = sub.add_parser("client")
    client.add_argument("operation", choices=["stage", "prepare-controller"])
    client.add_argument("--profile", required=True)
    client.add_argument("--protocol", choices=["reality", "hysteria2"], default="reality")
    client.add_argument("--port", type=int, default=17890)
    client.add_argument("--interface")
    client.add_argument("--settings", type=Path)
    client.add_argument("--temporary", action="store_true")
    verify = sub.add_parser("verify")
    verify.add_argument("--profile", required=True)
    verify.add_argument("--protocol", choices=["reality", "hysteria2"], required=True)
    verify.add_argument("--proxy", required=True)
    verify.add_argument("--direct-evidence", type=Path)
    verify.add_argument("--lease")
    guard = sub.add_parser("guard")
    guard.add_argument("operation", choices=["baseline", "prove", "arm", "switch", "commit", "rollback", "status", "retire"])
    guard.add_argument("--profile", required=True)
    guard.add_argument("--lease")
    guard.add_argument("--ttl", type=int, default=180)
    guard.add_argument("--agent-ack")
    guard.add_argument("--approved", action="store_true")
    management = sub.add_parser("management")
    management.add_argument("operation", choices=["plan", "apply", "status", "commit", "rollback"])
    management.add_argument("--profile", required=True)
    management.add_argument("--approved-plan")
    management.add_argument("--evidence", type=Path)
    return p


def status(store, profile):
    state = store.current_state(profile)
    leases = []
    jobs = [read_json(file) for file in (store.profile(profile) / "leases").glob("*/lease.json")]
    for job in sorted(jobs, key=lambda j: j.get("created", 0)):
        leases.append({"lease": job["id"], "phase": job["phase"], "proof": job["proof"]})
    return {"phase": state["phase"], "profile_digest": digest(store.load(profile)),
            "checks": {k: v for k, v in state.get("checks", {}).items() if type(v) is bool},
            "leases": leases, "next": "Read the private checkpoint; never reinitialize to resume."}


def direct_evidence(args, config):
    if not args.direct_evidence:
        return False
    value = read_json(args.direct_evidence)
    return (value.get("profile_digest") == digest(config) and value.get("standalone_path_verified") is True and
            value.get("method") in {"physical-interface-and-source-check", "paired-server-capture"} and
            value.get("family") in {"IPv4", "IPv6"} and 0 <= time.time() - value.get("observed_at", 0) < 300)


def execute(args):
    store = Store(args.state_dir)
    if args.command == "inspect":
        return inspect_host()
    if args.command == "init":
        config = read_json(args.config)
        require(isinstance(config, dict), "invalid_profile", "Private profile must be a JSON object.")
        store.init(args.profile, config)
        return {"phase": "needs_user_action", "initialized": True}
    if args.command in {"status", "resume"}:
        return status(store, args.profile)
    if args.command == "bootstrap":
        if not args.component:
            result = inspect_host()
            result["client_installation"] = "Reuse an existing compatible client. Otherwise verify the official Clash Verge Rev release; paid clients are optional."
            result["install_safety"] = "This command does not install or activate GUI clients, TUN drivers, or a system proxy."
            return result
        require(bool(args.profile), "missing_profile", "Downloads require a private profile.")
        store.load(args.profile)
        store.assert_idle(args.profile)
        from .downloads import download, unpack
        identity = args.platform or (platform.system().lower() + "-" + inspect_host()["architecture"])
        folder = "tools" if args.keep else "temp"
        root = store.profile(args.profile) / folder
        archive = root / (args.component + ".download")
        entry = download(args.component, identity, archive)
        if not args.keep:
            store.record_temp(args.profile, archive)
        binary = root / (args.component + (".exe" if identity.startswith("windows-") else ""))
        unpack(entry, archive, binary)
        if not args.keep:
            store.record_temp(args.profile, binary)
        return {"phase": "staged", "download_verified": True, "executed": False,
                "artifact": folder + "/" + binary.name, "version": entry["version"]}
    if args.command == "plan":
        from .remote import plan
        return plan(store, args.profile)
    if args.command == "apply":
        from .remote import apply
        return apply(store, args.profile, args.approved_plan)
    if args.command == "client":
        from .clients import stage, prepare_controller
        if args.operation == "prepare-controller":
            require(args.settings is not None, "missing_settings", "Supply private controller settings.")
            return prepare_controller(store, args.profile, read_json(args.settings))
        credentials = read_json(store.profile(args.profile) / "credentials.json")
        return stage(store, args.profile, credentials, args.protocol, port=args.port, interface=args.interface, temporary=args.temporary)
    if args.command == "verify":
        from .probes import verify_network
        from . import guard
        config = store.load(args.profile)
        expected = config.get("verification", {}).get("expected_exits", [])
        checks = verify_network(args.proxy, expected, direct_evidence=direct_evidence(args, config))
        state = store.state(args.profile)
        by_protocol = state.get("protocol_checks", {})
        by_protocol[args.protocol] = {"checks": checks, "observed_at": time.time()}
        store.update(args.profile, checks=checks, protocol_checks=by_protocol)
        if args.lease:
            if not all(checks.values()):
                directory = guard.lease_path(store, args.profile, args.lease)
                phase = guard.restore(directory)
                return {"phase": phase, "checks": checks, "committed": False}
            return guard.verified_candidate(store, args.profile, args.lease, checks)
        return {"phase": "staged" if all(checks.values()) else "needs_user_action", "checks": checks,
                "next": "Protocol probes do not prove browser use or long-term stability. Stage the real client before a guarded trial."}
    if args.command == "guard":
        from . import guard
        if args.operation == "baseline":
            return guard.snapshot(store, args.profile)
        if args.operation in {"prove", "arm", "switch"}:
            require(args.approved, "approval_required", "Confirm the exact recovery/trial action with the user before setting --approved.")
        if args.operation in {"prove", "arm"}:
            return guard.new_job(store, args.profile, proof=args.operation == "prove", ttl=args.ttl)
        if args.operation == "status":
            return status(store, args.profile)
        require(bool(args.lease), "missing_lease", "Supply the exact owned lease ID.")
        if args.operation == "switch":
            return guard.switch(store, args.profile, args.lease)
        if args.operation == "commit":
            return guard.commit(store, args.profile, args.lease, args.agent_ack)
        directory = guard.lease_path(store, args.profile, args.lease)
        if args.operation == "retire":
            job = read_json(directory / "lease.json")
            require(job["phase"] in {"committed", "rolled_back", "proof_passed", "proof_failed"},
                    "recovery_armed", "Cannot retire an armed or failed recovery job.")
            from .scheduler import Scheduler
            Scheduler().cancel(job["label"])
            return {"phase": job["phase"], "owned_job_retired": True}
        phase = guard.restore(directory)
        from .scheduler import Scheduler
        Scheduler().cancel(read_json(directory / "lease.json")["label"])
        return {"phase": phase}
    if args.command == "cleanup":
        return store.cleanup(args.profile)
    if args.command == "management":
        from . import management
        if args.operation == "plan":
            return management.plan(store, args.profile)
        if args.operation == "apply":
            return management.apply(store, args.profile, args.approved_plan)
        if args.operation == "status":
            from .remote import call
            config = store.load(args.profile)
            addresses = management.private_access(config)
            result = call(config, "harden_status", host_override=addresses[0])
            write_private(store.profile(args.profile) / "management-lease.json", result)
            return {"phase": result["phase"], "scope": "server firewall only"}
        return management.finish(store, args.profile, commit=args.operation == "commit", evidence=args.evidence)
    if args.command == "report":
        from .privacy import public_report
        return public_report(store.current_state(args.profile))
    raise RelayError("invalid_command", "Unknown operation.")


def main(argv=None):
    os.umask(0o077)
    args = parser().parse_args(argv)
    try:
        result = execute(args)
        print(json.dumps(result, ensure_ascii=False))
        if args.command == "verify" and not all(result.get("checks", {"verified": True}).values()):
            return 2
        if result.get("phase") in {"recovery_failed", "proof_failed"}:
            return 2
        return 0
    except RelayError as exc:
        print(json.dumps({"phase": "blocked", "error": exc.code, "message": exc.message}))
        return 2
    except Exception:
        # No traceback/raw subprocess arguments: they may include credentials or local identities.
        print(json.dumps({"phase": "blocked", "error": "internal_error", "message": "Operation failed safely; preserve private state for local diagnosis."}))
        return 3
