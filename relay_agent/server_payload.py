"""SSH-stdin program. REQUEST is supplied by the private controller.

This program never runs on import; main is gated on an injected REQUEST.
Only the Debian 13 reference adapter is automated.
"""
import hashlib
import io
import ipaddress
import json
import os
from pathlib import Path
import platform
import secrets
import shutil
import subprocess
import tempfile
import urllib.request
import uuid
import zipfile


ROOT = Path("/var/lib/agent-vps-relay")
ETC = Path("/etc/agent-vps-relay")
BIN = Path("/usr/local/lib/agent-vps-relay")


def ensure(condition):
    if not condition:
        raise ValueError("Reference recipe precondition failed")


def deployment_settings(config, artifacts):
    return {"server": config["server"], "ssh_port": config["ssh"].get("port", 22),
            "artifacts": artifacts}


def command(argv, timeout=60):
    return subprocess.run(argv, capture_output=True, text=True, check=True, timeout=timeout,
                          env={**os.environ, "LC_ALL": "C"}).stdout


def save(path, value, mode=0o600):
    data = json.dumps(value, indent=2) + "\n" if not isinstance(value, str) else value
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(dir=path.parent)
    with os.fdopen(fd, "w") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(name, mode)
    os.replace(name, path)


def inspect():
    values = {}
    for line in Path("/etc/os-release").read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            values[k] = v.strip('"')
    receipt = json.loads((ROOT / "receipt.json").read_text()) if (ROOT / "receipt.json").exists() else None
    pending = json.loads((ROOT / "pending.json").read_text()) if (ROOT / "pending.json").exists() else None
    listeners = command(["ss", "-H", "-lnut"])
    occupied = any(line.split()[4].rsplit(":", 1)[-1] == "443" for line in listeners.splitlines() if len(line.split()) > 4)
    managed = receipt or pending
    interfaces = json.loads(command(["ip", "-j", "address", "show", "scope", "global"]))
    public_addresses = sorted({item["local"] for interface in interfaces for item in interface.get("addr_info", [])
                               if ipaddress.ip_address(item["local"]).is_global})
    return {"ok": True, "os_id": values.get("ID"), "os_version": values.get("VERSION_ID"),
            "machine": platform.machine(), "machine_id": Path("/etc/machine-id").read_text().strip(),
            "managed_id": managed.get("deployment_id") if managed else None,
            "installed_versions": receipt.get("versions") if receipt else None,
            "target": receipt.get("target") if receipt else None,
            "port_conflict": occupied and managed is None, "public_addresses": public_addresses}


def fetch(entry, destination):
    ensure(entry["url"].startswith("https://github.com/" + entry["repository"] + "/releases/download/"))
    with urllib.request.urlopen(entry["url"], timeout=45) as r:
        ensure(r.url.startswith("https://"))
        raw = r.read(160 * 1024 * 1024 + 1)
    ensure(len(raw) <= 160 * 1024 * 1024)
    ensure(hashlib.sha256(raw).hexdigest() == entry["sha256"])
    if entry["format"] == "zip":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            ensure(z.getinfo(entry["member"]).file_size <= 160 * 1024 * 1024)
            raw = z.read(entry["member"])
    ensure(entry["format"] in {"raw", "zip"})
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=destination.parent)
    with os.fdopen(fd, "wb") as f:
        f.write(raw)
    os.chmod(name, 0o755)
    os.replace(name, destination)


def unit(name, account, binary, args):
    # Fixed owned paths; no config values interpolated into unit directives.
    text = f'''[Unit]
Description=Agent VPS Relay {name}
After=network-online.target
Wants=network-online.target
[Service]
User={account}
Group={account}
ExecStart={binary} {args}
Restart=on-failure
RestartSec=2
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
AmbientCapabilities=CAP_NET_BIND_SERVICE
ReadOnlyPaths=/etc/agent-vps-relay
[Install]
WantedBy=multi-user.target
'''
    save(Path("/etc/systemd/system") / ("agent-vps-relay-" + name + ".service"), text, 0o644)


def deploy(request):
    config, artifacts = request["config"], request["artifacts"]
    observed = inspect()
    ensure(os.geteuid() == 0 and observed["os_id"] == "debian" and observed["os_version"] == "13")
    ensure(observed["machine"] in {"x86_64", "amd64"} and not observed["port_conflict"])
    ensure(observed["managed_id"] in {None, config["deployment_id"]})
    settings = deployment_settings(config, artifacts)
    versions = {k: v["version"] for k, v in artifacts.items()}
    if (ROOT / "receipt.json").exists():
        receipt = json.loads((ROOT / "receipt.json").read_text())
        ensure(receipt["versions"] == versions)  # Explicit upgrade workflow required; no silent replacement.
        ensure(receipt["settings"] == settings)
        for name, checksum in receipt["files"].items():
            ensure(hashlib.sha256(Path(name).read_bytes()).hexdigest() == checksum)
        for name in ["xray", "hysteria2"]:
            command(["systemctl", "is-active", "agent-vps-relay-" + name])
        return {"ok": True, "credentials": receipt["credentials"], "resumed": True}
    # Never take ownership of pre-existing unrecorded files.
    if observed["managed_id"] is None:
        ensure(not ETC.exists() and not BIN.exists())
        ensure(not ROOT.exists() or not any(ROOT.iterdir()))
        import pwd
        for account in ["relay-xray", "relay-hy2"]:
            try:
                pwd.getpwnam(account)
            except KeyError:
                continue
            raise ValueError("Unowned service account exists")
        for name in ["xray", "hysteria2"]:
            ensure(not (Path("/etc/systemd/system") / ("agent-vps-relay-" + name + ".service")).exists())
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(ROOT, 0o700)
    if (ROOT / "pending.json").exists():
        ensure(json.loads((ROOT / "pending.json").read_text())["settings"] == settings)
    else:
        save(ROOT / "pending.json", {"deployment_id": config["deployment_id"], "settings": settings})
    missing = [p for p in ["ca-certificates", "openssl", "ufw"] if subprocess.run(
        ["dpkg-query", "-W", "-f=${Status}", p], capture_output=True, text=True).stdout != "install ok installed"]
    if missing:
        command(["apt-get", "update"], 120)
        command(["apt-get", "install", "-y", "--no-install-recommends", *missing], 150)
    fetch(artifacts["xray"], BIN / "xray")
    fetch(artifacts["hysteria2"], BIN / "hysteria2")
    for account in ["relay-xray", "relay-hy2"]:
        if subprocess.run(["id", account], capture_output=True).returncode:
            command(["useradd", "--system", "--user-group", "--no-create-home", "--shell", "/usr/sbin/nologin", account])
    ETC.mkdir(parents=True, exist_ok=True, mode=0o755)
    os.chmod(ETC, 0o755)
    if (ROOT / "credentials.json").exists():
        credentials = json.loads((ROOT / "credentials.json").read_text())
    else:
        output = command([str(BIN / "xray"), "x25519"])
        pair = dict(line.split(":", 1) for line in output.splitlines() if ":" in line)
        private = pair["PrivateKey"].strip()
        public = (pair.get("Password") or pair.get("PublicKey") or "").strip()
        ensure(public and private)
        credentials = {"address": config["server"]["address"],
                       "reality": {"uuid": str(uuid.uuid4()), "short_id": secrets.token_hex(8),
                                   "private_key": private, "public_key": public, "sni": config["server"]["reality_sni"]},
                       "hysteria2": {"password": secrets.token_urlsafe(32), "sni": "relay.invalid"}}
        save(ROOT / "credentials.json", credentials)
    if not (ETC / "server.crt").exists():
        command(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes",
                 "-days", "365", "-subj", "/CN=relay.invalid", "-addext", "subjectAltName=DNS:relay.invalid",
                 "-keyout", str(ETC / "server.key"), "-out", str(ETC / "server.crt")])
    fingerprint = command(["openssl", "x509", "-noout", "-fingerprint", "-sha256", "-in", str(ETC / "server.crt")])
    credentials["hysteria2"]["pin_sha256"] = fingerprint.split("=", 1)[1].strip().replace(":", "").lower()
    save(ROOT / "credentials.json", credentials)
    r = credentials["reality"]
    xray = {"log": {"loglevel": "warning"}, "inbounds": [{"listen": "::", "port": 443, "protocol": "vless",
        "settings": {"clients": [{"id": r["uuid"], "flow": "xtls-rprx-vision"}], "decryption": "none"},
        "streamSettings": {"network": "tcp", "security": "reality", "realitySettings": {"show": False,
        "target": config["server"]["reality_target"], "serverNames": [r["sni"]], "privateKey": r["private_key"],
        "shortIds": [r["short_id"]]}}, "sniffing": {"enabled": True, "destOverride": ["http", "tls"], "routeOnly": False}}],
        "outbounds": [{"protocol": "freedom"}]}
    hy2 = {"listen": ":443", "tls": {"cert": str(ETC / "server.crt"), "key": str(ETC / "server.key")},
           "auth": {"type": "password", "password": credentials["hysteria2"]["password"]}}
    save(ETC / "xray.json", xray, 0o640)
    save(ETC / "hysteria2.json", hy2, 0o640)
    import grp
    for filename, account in [("xray.json", "relay-xray"), ("hysteria2.json", "relay-hy2"),
                              ("server.key", "relay-hy2"), ("server.crt", "relay-hy2")]:
        os.chown(ETC / filename, 0, grp.getgrnam(account).gr_gid)
        os.chmod(ETC / filename, 0o640)
    command([str(BIN / "xray"), "run", "-test", "-config", str(ETC / "xray.json")])
    unit("xray", "relay-xray", BIN / "xray", "run -config /etc/agent-vps-relay/xray.json")
    unit("hysteria2", "relay-hy2", BIN / "hysteria2", "server -c /etc/agent-vps-relay/hysteria2.json")
    command(["systemctl", "daemon-reload"])
    stage_firewall(config)
    try:
        for name in ["xray", "hysteria2"]:
            command(["systemctl", "enable", "--now", "agent-vps-relay-" + name])
            command(["systemctl", "is-active", "agent-vps-relay-" + name])
    except Exception:
        for name in ["xray", "hysteria2"]:
            subprocess.run(["systemctl", "stop", "agent-vps-relay-" + name], capture_output=True)
        # Pending receipt and credentials deliberately survive for repair/resume.
        raise
    files = [BIN / "xray", BIN / "hysteria2", ETC / "xray.json", ETC / "hysteria2.json", ETC / "server.crt", ETC / "server.key"]
    save(ROOT / "receipt.json", {"deployment_id": config["deployment_id"], "versions": versions, "settings": settings,
                                "files": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                                "target": config["server"]["reality_target"], "credentials": credentials})
    return {"ok": True, "credentials": credentials}


def stage_firewall(config):
    # Stage on an inactive firewall; enabling belongs to the independently guarded step.
    backup = ROOT / "firewall-before"
    if not backup.exists():
        shutil.copytree("/etc/ufw", backup, symlinks=True)
    if not command(["ufw", "status"]).startswith("Status: active"):
        command(["ufw", "allow", str(config["ssh"].get("port", 22)) + "/tcp", "comment", "agent-vps-relay-bootstrap"])
    command(["ufw", "allow", "443/tcp", "comment", "agent-vps-relay-reality"])
    command(["ufw", "allow", "443/udp", "comment", "agent-vps-relay-hysteria2"])


def main(request):
    if request["operation"] == "inspect":
        return inspect()
    if request["operation"] == "deploy":
        return deploy(request)
    if request["operation"] in {"harden", "harden_status", "harden_commit", "harden_rollback"}:
        return management(request)
    raise ValueError("Unknown operation")


def management(request):
    import fcntl
    import time
    state_file = ROOT / "management.json"
    receipt = json.loads((ROOT / "receipt.json").read_text())
    ensure(receipt["deployment_id"] == request["config"]["deployment_id"])
    op = request["operation"]
    if op == "harden_status":
        state = json.loads(state_file.read_text())
        return {"ok": True, **state}
    if op == "harden":
        if state_file.exists():
            previous = json.loads(state_file.read_text())
            ensure(previous["phase"] in {"committed", "rolled_back"})
        ensure(command(["systemctl", "is-active", "tailscaled"]).strip() == "active")
        observed = command(["tailscale", "ip"]).splitlines()
        ensure(all(ip in observed for ip in request["config"]["management"]["addresses"]))
        ident = secrets.token_hex(12)
        directory = ROOT / ("management-" + ident)
        directory.mkdir(mode=0o700)
        for name in ["user.rules", "user6.rules", "ufw.conf"]:
            shutil.copy2(Path("/etc/ufw") / name, directory / name)
        state = {"id": ident, "phase": "proof_pending", "deadline": time.time() + 600,
                 "baseline_active": command(["ufw", "status"]).startswith("Status: active"),
                 "label": "agent-vps-relay-server-" + ident}
        save(state_file, state)
        # The timer executes the same local recovery path in proof and cutover modes.
        script = '''#!/usr/bin/env python3
import fcntl,json,pathlib,shutil,subprocess,sys,time
root=pathlib.Path('/var/lib/agent-vps-relay')
with (root/'management.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 state=json.loads((root/'management.json').read_text())
 if state['id'] != sys.argv[1] or state['phase']=='committed':sys.exit(0)
 d=root/('management-'+state['id'])
 for n in ['user.rules','user6.rules','ufw.conf']:shutil.copy2(d/n,pathlib.Path('/etc/ufw')/n)
 action=['ufw','reload'] if state['baseline_active'] else ['ufw','--force','disable']
 subprocess.run(action,check=True,stdout=subprocess.DEVNULL)
 if sys.argv[2]=='proof':(d/'proof.ok').write_text(str(time.time()))
 else:
  state.update(phase='rolled_back',finished=time.time())
  t=root/'management.next';t.write_text(json.dumps(state));t.chmod(0o600);t.replace(root/'management.json')
'''
        script_path = directory / "restore.py"
        save(script_path, script, 0o700)
        proof = state["label"] + "-proof"
        command(["systemd-run", "--unit=" + proof, "--on-active=2s", "--timer-property=AccuracySec=1s",
                 "--property=RemainAfterExit=yes", "/usr/bin/python3", str(script_path), ident, "proof"])
        for _ in range(40):
            if (directory / "proof.ok").exists():
                break
            time.sleep(0.25)
        ensure((directory / "proof.ok").exists())
        command(["systemctl", "stop", proof + ".timer", proof + ".service"])
        state.update(phase="armed", deadline=time.time() + 600)
        save(state_file, state)
        command(["systemd-run", "--unit=" + state["label"], "--on-active=600s", "--timer-property=AccuracySec=1s",
                 "/usr/bin/python3", str(script_path), ident, "cutover"])
        port = request["config"]["ssh"].get("port", 22)
        command(["ufw", "insert", "1", "allow", "in", "on", "tailscale0", "to", "any", "port", str(port),
                 "proto", "tcp", "comment", "agent-vps-relay-private-management"])
        command(["ufw", "--force", "delete", "allow", str(port) + "/tcp", "comment", "agent-vps-relay-bootstrap"])
        command(["ufw", "--force", "enable"])
        return {"ok": True, **state}
    state = json.loads(state_file.read_text())
    ensure(state["id"] == request["lease"])
    if op == "harden_rollback":
        command(["/usr/bin/python3", str(ROOT / ("management-" + state["id"]) / "restore.py"), state["id"], "cutover"])
    if op == "harden_commit":
        with (ROOT / "management.lock").open("a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            state = json.loads(state_file.read_text())
            ensure(state["id"] == request["lease"] and state["phase"] == "armed" and time.time() < state["deadline"])
            state.update(phase="committed", finished=time.time())
            save(state_file, state)
    command(["systemctl", "stop", state["label"] + ".timer"])
    # Stopping a timer may unload its never-started transient service; do not treat that as failure.
    ensure(subprocess.run(["systemctl", "is-active", "--quiet", state["label"] + ".timer"]).returncode != 0)
    return {"ok": True, **json.loads(state_file.read_text())}


if "REQUEST" in globals():
    try:
        print(json.dumps(main(REQUEST)))
    except Exception:
        if REQUEST.get("operation") != "inspect" and ROOT.exists():
            import traceback
            save(ROOT / "last-error.txt", traceback.format_exc())
        print(json.dumps({"ok": False, "error": "remote_operation_failed"}))
        raise SystemExit(1)
