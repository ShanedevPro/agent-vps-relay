"""Mihomo REST node switching; no global proxy, DNS, TUN or installation changes."""
import argparse
import json
from pathlib import Path
import sys
import urllib.parse
import urllib.request

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from relay_agent.core import RelayError, read_json, require, run


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RelayError("unsafe_controller", "Controller redirects are refused; credentials stay on the original loopback endpoint.")


def request(settings, path, method="GET", data=None):
    url = urllib.parse.urlsplit(settings["controller"])
    require(url.scheme == "http" and url.hostname in {"127.0.0.1", "::1", "localhost"}
            and url.port and not url.username and not url.password and url.path in {"", "/"}
            and not url.query and not url.fragment,
            "unsafe_controller", "Controller must be a loopback HTTP endpoint.")
    secret = Path(settings["secret_file"]).expanduser().read_text().strip()
    require(bool(secret) and not any(c in secret for c in "\r\n"), "unsafe_controller", "A private controller secret is required.")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    req = urllib.request.Request(settings["controller"].rstrip("/") + path,
                                 data=json.dumps(data).encode() if data is not None else None,
                                 method=method, headers={"Authorization": "Bearer " + secret,
                                                       "Content-Type": "application/json"})
    with opener.open(req, timeout=6) as response:
        body = response.read(1024 * 1024)
    return json.loads(body) if body else {}


def system_snapshot():
    import os
    import platform
    if platform.system() == "Darwin":
        return {"proxy": run(["/usr/sbin/scutil", "--proxy"]).stdout,
                "dns": run(["/usr/sbin/scutil", "--dns"]).stdout}
    if os.name == "nt":
        # Fixed read-only script; no dynamic PowerShell interpolation or command-length limit.
        script = ("$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';"
                  "$p=Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings';"
                  "[pscustomobject]@{enabled=$p.ProxyEnable;server=$p.ProxyServer;pac=$p.AutoConfigURL;"
                  "dns=@(Get-DnsClientServerAddress|Sort-Object InterfaceIndex,AddressFamily|"
                  "Select-Object InterfaceIndex,AddressFamily,ServerAddresses)}|ConvertTo-Json -Depth 5 -Compress")
        return json.loads(run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script]).stdout)
    result = {"resolv_conf": Path("/etc/resolv.conf").read_text()}
    import shutil
    if shutil.which("gsettings"):
        result["gnome_proxy"] = run(["gsettings", "get", "org.gnome.system.proxy", "mode"], check=False).stdout
    return result


def execute(settings, operation):
    group = "/proxies/" + urllib.parse.quote(settings["group"], safe="")
    if operation == "snapshot":
        config = request(settings, "/configs")
        return {"selected": request(settings, group).get("now"), "mode": config.get("mode"),
                "tun": config.get("tun", {}).get("enable", False), "system": system_snapshot()}
    if operation in {"restore", "switch"}:
        node = settings["baseline_node" if operation == "restore" else "candidate_node"]
        request(settings, group, "PUT", {"name": node})
        require(request(settings, group).get("now") == node, "client_action_failed", "Node selection did not take effect.")
        return {"ok": True}
    if operation == "health":
        # This is baseline reachability only; cutover verification uses all protocol checks.
        proxy = settings["proxy"]
        from relay_agent.probes import loopback_proxy
        loopback_proxy(proxy)
        import os
        r = run(["curl", "-q", "-sS", "--head", "--proxy", proxy, "--noproxy", ".invalid", "--connect-timeout", "4",
                 "--max-time", "7", "-o", "NUL" if os.name == "nt" else "/dev/null", "-w", "%{http_code}",
                 "https://www.google.com/generate_204"], timeout=9, check=False)
        return {"ok": r.returncode == 0 and r.stdout == "204"}
    raise RelayError("invalid_action", "Unknown client action.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["snapshot", "restore", "switch", "health"])
    parser.add_argument("settings", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(execute(read_json(args.settings), args.operation)))
    except Exception:
        # REST errors may contain the controller token; fail without printing them.
        print(json.dumps({"ok": False, "error": "client_action_failed"}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
