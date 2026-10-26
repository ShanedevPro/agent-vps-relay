"""Bounded probes. Proxy success does not prove the outer path was direct."""
from pathlib import Path
import ipaddress
import json
import socket
import struct
import tempfile
import urllib.parse

from .core import RelayError, require, run


def loopback_proxy(url):
    p = urllib.parse.urlsplit(url)
    require(p.scheme in {"http", "socks5h"} and p.hostname in {"127.0.0.1", "::1", "localhost"}
            and p.port is not None and not p.username and not p.password,
            "unsafe_proxy", "Test proxy must be an unauthenticated loopback endpoint.")
    return p


def receive(sock, count):
    data = b""
    while len(data) < count:
        part = sock.recv(count - len(data))
        require(bool(part), "probe_failed", "SOCKS connection ended early.")
        data += part
    return data


def udp_dns(host, port):
    require(host == "127.0.0.1", "unsupported_probe", "UDP reference probe requires an IPv4 loopback SOCKS listener.")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp, socket.create_connection((host, port), 5) as tcp:
        udp.bind(("127.0.0.1", 0))
        udp.settimeout(6)
        tcp.settimeout(6)
        tcp.sendall(b"\x05\x01\x00")
        require(receive(tcp, 2) == b"\x05\x00", "probe_failed", "SOCKS authentication failed.")
        tcp.sendall(b"\x05\x03\x00\x01" + socket.inet_aton(host) + struct.pack("!H", udp.getsockname()[1]))
        head = receive(tcp, 4)
        require(head[:2] == b"\x05\x00" and head[3] == 1, "probe_failed", "UDP association unavailable.")
        relay = socket.inet_ntoa(receive(tcp, 4))
        relay_port = struct.unpack("!H", receive(tcp, 2))[0]
        require(relay in {"0.0.0.0", "127.0.0.1"}, "unsafe_probe", "Unexpected SOCKS UDP relay address.")
        import secrets
        ident = secrets.randbits(16)
        query = struct.pack("!6H", ident, 0x100, 1, 0, 0, 0) + b"\x07example\x03com\x00" + struct.pack("!2H", 1, 1)
        udp.sendto(b"\x00\x00\x00\x01" + socket.inet_aton("1.1.1.1") + struct.pack("!H", 53) + query, (host, relay_port))
        data, source = udp.recvfrom(4096)
        require(source[1] == relay_port and data[:3] == b"\0\0\0" and data[3] in {1, 4}, "probe_failed", "Invalid UDP response.")
        offset = 10 if data[3] == 1 else 22
        h = struct.unpack("!6H", data[offset:offset + 12])
        return h[0] == ident and h[1] & 15 == 0 and h[3] > 0


def verify_network(proxy, expected_exits, *, direct_evidence=False, include_udp=True):
    parsed = loopback_proxy(proxy)
    require(bool(expected_exits) and all(ipaddress.ip_address(x) for x in expected_exits),
            "invalid_exits", "Provide expected server egress addresses in the private profile.")
    common = ["curl", "-q", "-sS", "--proxy", proxy, "--noproxy", ".invalid",
              "--connect-timeout", "5", "--max-time", "12"]
    checks = {}
    for key, url, expected in [("google", "https://www.google.com/generate_204", "204"),
                               ("github", "https://github.com/", "200")]:
        r = run(common + ["--head", "-o", "NUL" if __import__("os").name == "nt" else "/dev/null", "-w", "%{http_code}", url], timeout=15, check=False)
        checks[key] = r.returncode == 0 and r.stdout == expected
    # Keep response bodies out of command output and reports.
    with tempfile.TemporaryDirectory(prefix="relay-probe-") as temp:
        body = Path(temp) / "trace"
        r = run(common + ["--max-filesize", "4096", "-o", str(body), "https://www.cloudflare.com/cdn-cgi/trace"], timeout=15, check=False)
        ips = [line[3:] for line in body.read_text().splitlines() if line.startswith("ip=")] if body.exists() else []
        checks["exit"] = r.returncode == 0 and len(ips) == 1 and ips[0] in expected_exits
    if include_udp:
        try:
            checks["udp_dns"] = udp_dns(parsed.hostname, parsed.port)
        except (RelayError, OSError, ValueError, struct.error):
            checks["udp_dns"] = False
    checks["direct_path"] = direct_evidence is True
    return checks
