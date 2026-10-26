"""Trusted-host OpenSSH transport and reviewable deployment plans."""
import base64
import ipaddress
import json
from pathlib import Path
import re
import secrets

from .core import RelayError, digest, read_json, require, run, write_private
from .downloads import catalog


def validate_ssh(config):
    s = config.get("ssh", {})
    require(bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", s.get("host", ""))) and
            bool(re.fullmatch(r"[a-z_][a-z0-9_-]*", s.get("user", ""))) and
            type(s.get("port", 22)) is int and 1 <= s.get("port", 22) <= 65535,
            "invalid_ssh", "Supply a valid SSH host, account, and port.")
    for key in ["identity_file", "known_hosts_file"]:
        path = Path(s.get(key, "")).expanduser()
        require(path.is_absolute() and path.is_file() and not any(c in str(path) for c in ['"', '\n', '\r']),
                "invalid_ssh", "SSH key and dedicated known-hosts files must exist locally.")
    keys = run(["ssh-keygen", "-lf", str(Path(s["known_hosts_file"]).expanduser())]).stdout.splitlines()
    require(len(keys) == 1 and len(keys[0].split()) >= 2 and keys[0].split()[1] == s.get("fingerprint")
            and s.get("identity_verified") is True,
            "identity_unverified", "Pin one independently verified host key; ssh-keyscan alone is not verification.")
    return s


def ssh(config, program, *, host_override=None, timeout=60):
    s = validate_ssh(config)
    host = host_override or s["host"]
    require(bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", host)), "invalid_ssh", "Invalid management address.")
    argv = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "GlobalKnownHostsFile=none",
            "-o", 'UserKnownHostsFile="' + str(Path(s["known_hosts_file"]).expanduser()) + '"',
            "-o", "HostKeyAlias=" + s["host"], "-o", "ControlMaster=no", "-o", "ControlPath=none",
            "-o", "ConnectTimeout=8", "-o", "IdentitiesOnly=yes", "-i", str(Path(s["identity_file"]).expanduser()),
            "-p", str(s.get("port", 22)), "-l", s["user"]]
    argv += ["-F", str(Path(s["config_file"]).expanduser()) if s.get("config_file") else "none"]
    argv += [host, "python3 -" if s["user"] == "root" else "sudo -n python3 -"]
    result = run(argv, stdin=program, timeout=timeout)
    try:
        obj = json.loads(result.stdout)
    except ValueError:
        raise RelayError("remote_failed", "The server did not return a valid private result.") from None
    require(obj.get("ok") is True, "remote_failed", "Remote operation failed; preserve the current route and inspect the server privately.")
    return obj


def call(config, operation, extras=None, *, host_override=None, timeout=60):
    payload = {"operation": operation, "config": config, **(extras or {})}
    source = Path(__file__).with_name("server_payload.py").read_text()
    # Source is sent over SSH stdin. Credentials are neither command-line arguments nor public output.
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    program = "import base64,json\nREQUEST=json.loads(base64.b64decode(" + repr(encoded) + "))\n" + source
    return ssh(config, program, host_override=host_override, timeout=timeout)


def plan(store, name):
    config = store.load(name)
    server = config.get("server", {})
    require(bool(re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]*:443", server.get("reality_target", ""))) and
            bool(re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]*", server.get("reality_sni", ""))),
            "needs_target_review", "Choose and validate a REALITY TLS target and matching SNI before deployment.")
    require(server["reality_target"] == server["reality_sni"] + ":443", "invalid_target", "Reference recipe requires target/SNI to match.")
    require(server.get("target_validated") is True, "needs_target_review", "Record server-side TLS compatibility; actual-network protocol tests follow deployment. No universal target is assumed.")
    address = server.get("address", "")
    try:
        ipaddress.ip_address(address)
    except ValueError:
        raise RelayError("invalid_address", "Reference recipe requires an explicit public IPv4 or IPv6 endpoint.") from None
    require(config["ssh"].get("port", 22) != 443, "port_conflict", "SSH and the proxy must not share TCP443.")
    if not config.get("deployment_id"):
        config["deployment_id"] = secrets.token_hex(16)
        write_private(store.profile(name) / "profile.json", config)
    observed = call(config, "inspect")
    require(observed["os_id"] == "debian" and observed["os_version"] == "13" and observed["machine"] in {"x86_64", "amd64"},
            "needs_research", "No automated server adapter for this OS/architecture; use the adaptation guide.")
    require(not observed["port_conflict"], "port_conflict", "An unrelated service already uses a required port.")
    require(observed["managed_id"] in {None, config["deployment_id"]}, "foreign_deployment", "This server belongs to another deployment profile.")
    value = {"schema_version": 1, "profile_digest": digest(config), "observed": observed,
             "artifacts": {key: catalog()["artifacts"][key]["linux-amd64"] for key in ["xray", "hysteria2"]},
             "changes": ["Install missing dependencies and pinned official binaries", "Create isolated service accounts and owned systemd units",
                         "Generate/reuse private credentials", "Allow proxy ports while preserving SSH and existing firewall rules"],
             "network_takeover": False, "management_restriction": False}
    write_private(store.profile(name) / "plan.json", value)
    return {"phase": "needs_user_action", "plan_digest": digest(value), "changes": value["changes"],
            "next": "Review the private plan and exact server before applying. Purchases and local-client takeover are separate."}


def apply(store, name, approved_digest):
    config = store.load(name)
    value = read_json(store.profile(name) / "plan.json")
    require(digest(value) == approved_digest and value["profile_digest"] == digest(config),
            "stale_plan", "The approved plan or private profile changed; generate a new plan.")
    now = call(config, "inspect")
    require(now == value["observed"], "server_changed", "Server identity/state changed since planning; review a new plan.")
    result = call(config, "deploy", {"artifacts": value["artifacts"]}, timeout=300)
    write_private(store.profile(name) / "credentials.json", result["credentials"])
    store.update(name, phase="staged", server_deployed=True)
    return {"phase": "staged", "credentials_saved_privately": True, "network_takeover": False,
            "next": "Run isolated protocol tests; verify provider-console recovery and Tailscale before management hardening."}
