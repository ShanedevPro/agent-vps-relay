"""Stage private client files and optional node-only controller actions."""
from pathlib import Path
import re
import sys

from .core import require, write_private
from .guard import prepare_runtime


def mihomo_config(credentials, protocol, *, port=17890, interface=None):
    require(protocol in {"reality", "hysteria2"} and 1024 <= port <= 65535, "invalid_client", "Unsupported protocol or loopback port.")
    if protocol == "reality":
        r = credentials["reality"]
        proxy = {"name": "relay-candidate", "type": "vless", "server": credentials["address"], "port": 443,
                 "uuid": r["uuid"], "flow": "xtls-rprx-vision", "tls": True, "servername": r["sni"],
                 "client-fingerprint": "chrome", "skip-cert-verify": False, "network": "tcp", "udp": True,
                 "packet-encoding": "xudp", "smux": {"enabled": False},
                 "reality-opts": {"public-key": r["public_key"], "short-id": r["short_id"]}}
    else:
        h = credentials["hysteria2"]
        require(bool(h.get("password")) and bool(re.fullmatch(r"[0-9a-fA-F]{64}", h.get("pin_sha256", ""))),
                "invalid_client", "Hysteria2 requires a private password and a complete SHA-256 certificate pin.")
        proxy = {"name": "relay-candidate", "type": "hysteria2", "server": credentials["address"], "port": 443,
                 "password": h["password"], "sni": h["sni"], "fingerprint": h["pin_sha256"],
                 "skip-cert-verify": False}
    config = {"mixed-port": port, "bind-address": "127.0.0.1", "allow-lan": False,
              "mode": "rule", "log-level": "warning", "ipv6": True, "tun": {"enable": False},
              "dns": {"enable": False}, "proxies": [proxy], "rules": ["MATCH,relay-candidate"]}
    if interface:
        config["interface-name"] = interface
    return config


def stage(store, profile, credentials, protocol, *, port=17890, interface=None, temporary=False):
    store.assert_idle(profile)
    config = mihomo_config(credentials, protocol, port=port, interface=interface)
    folder = "temp" if temporary else "clients"
    path = store.profile(profile) / folder / (protocol + ".json")
    write_private(path, config)
    if temporary:
        store.record_temp(profile, path)
    store.update(profile, phase="staged")
    return {"phase": "staged", "artifact": folder + "/" + path.name,
            "networking_changed": False, "next": "Validate using the pinned test core. No TUN or system proxy activation."}


def prepare_controller(store, profile, settings):
    """Preserve the old group selection; caller supplies only a node-selection trial."""
    store.assert_idle(profile)
    require(not (store.profile(profile) / "baseline.json").exists(), "baseline_exists", "Do not replace a captured adapter.")
    secret = Path(settings.get("secret_file", "")).expanduser()
    require(secret.is_absolute() and secret.is_file() and not any(p.is_symlink() for p in (secret, *secret.parents)),
            "invalid_controller", "Use an existing absolute private controller-secret file.")
    settings = {**settings, "secret_file": str(secret)}
    from .clientctl import request
    actual = request(settings, "/proxies/" + __import__("urllib.parse", fromlist=["quote"]).quote(settings["group"], safe=""))
    require(actual.get("now") == settings["baseline_node"] and settings["candidate_node"] in actual.get("all", []),
            "client_not_ready", "Confirm the baseline selection and import the candidate without selecting it.")
    path = store.profile(profile) / "controller.json"
    write_private(path, settings)
    runtime = prepare_runtime(store.root)
    client = {key: [str(Path(sys.executable).resolve()), str(runtime / "relay_agent/clientctl.py"), operation, str(path)]
              for key, operation in [("capture_argv", "snapshot"), ("restore_argv", "restore"),
                                     ("switch_argv", "switch"), ("baseline_health_argv", "health")]}
    client["immutable_files"] = [str(path), str(Path(settings["secret_file"]).resolve())]
    config = store.load(profile)
    config["client"] = client
    write_private(store.profile(profile) / "profile.json", config)
    return {"phase": "staged", "scope": "Mihomo group selection only", "networking_changed": False}
