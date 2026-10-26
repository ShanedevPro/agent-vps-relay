"""Read-only local capability discovery. Do not mistake this host for the user's device."""
import os
from pathlib import Path
import platform
import shutil
import ssl
import sys


def inspect_host():
    system, machine = platform.system(), platform.machine().lower()
    arch = {"aarch64": "arm64", "arm64": "arm64", "x86_64": "amd64", "amd64": "amd64"}.get(machine, "unknown")
    tools = {name: shutil.which(name) is not None for name in
             ["ssh", "ssh-keygen", "curl", "systemctl", "systemd-run", "launchctl", "schtasks", "winget", "brew", "apt-get"]}
    clients = []
    if system == "Darwin":
        for name in ["Shadowrocket", "Clash Verge", "Clash Verge Rev"]:
            if any((p / (name + ".app")).exists() for p in [Path("/Applications"), Path.home() / "Applications"]):
                clients.append(name)
    if shutil.which("mihomo"):
        clients.append("mihomo")
    if system == "Windows":
        # An installed GUI can live anywhere. These are hints, never an absence claim.
        for parent in [os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles", "")]:
            if parent and any((Path(parent) / name).exists() for name in ["Clash Verge", "Clash Verge Rev"]):
                clients.append("Clash Verge Rev")
    missing = [name for name in ["ssh", "ssh-keygen", "curl"] if not tools[name]]
    try:
        trust_available = ssl.create_default_context().cert_store_stats().get("x509_ca", 0) > 0
    except (OSError, ssl.SSLError):
        trust_available = False
    version = platform.mac_ver()[0] if system == "Darwin" else platform.release()
    return {"role": "agent_execution_host", "client_device_confirmed": False,
            "os": system, "os_version": version, "architecture": arch,
            "python_supported": sys.version_info >= (3, 11), "certificate_trust_available": trust_available,
            "tools": tools, "clients_detected": clients, "client_discovery_complete": False,
            "admin": os.geteuid() == 0 if hasattr(os, "geteuid") else None,
            "free_gib": round(shutil.disk_usage(Path.home()).free / 2**30, 1),
            "proxy_environment_present": any(os.environ.get(k) for k in ["HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"]),
            "missing_tools": missing, "phase": "needs_user_action" if missing or arch == "unknown" or not trust_available or sys.version_info < (3, 11) else "staged",
            "next": "Confirm the actual client device and working connection; do not enable proxy/TUN during installation."}
