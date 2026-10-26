"""Download only reviewed, pinned upstream artifacts. Never execute during bootstrap."""
import gzip
import hashlib
import importlib.resources
import json
from pathlib import Path
import urllib.parse
import urllib.request
import zipfile

from .core import RelayError, require, private_dir, write_private


def catalog():
    return json.loads(importlib.resources.files("relay_agent").joinpath("versions.lock.json").read_text())


def download(component, platform_id, destination: Path):
    try:
        entry = catalog()["artifacts"][component][platform_id]
    except KeyError:
        raise RelayError("needs_research", "No reviewed artifact for this platform; research upstream compatibility first.") from None
    url = entry["url"]
    parsed = urllib.parse.urlsplit(url)
    require(parsed.scheme == "https" and parsed.hostname == "github.com" and
            parsed.path.startswith("/" + entry["repository"] + "/releases/download/") and
            len(entry["sha256"]) == 64, "invalid_lock", "Artifact identity is not pinned.")
    private_dir(destination.parent)
    if destination.exists():
        require(destination.is_file() and not destination.is_symlink() and
                hashlib.sha256(destination.read_bytes()).hexdigest() == entry["sha256"],
                "artifact_changed", "Existing artifact differs; review an upgrade or choose a new owned location without overwriting it.")
        return entry
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            require(urllib.parse.urlsplit(response.url).scheme == "https", "unsafe_redirect", "Download redirected away from HTTPS.")
            raw = response.read(160 * 1024 * 1024 + 1)
    except (OSError, ValueError):
        raise RelayError("download_unavailable", "Official download unavailable; preserve the working connection and use a verified offline transfer.") from None
    require(len(raw) <= 160 * 1024 * 1024 and hashlib.sha256(raw).hexdigest() == entry["sha256"],
            "checksum_mismatch", "Downloaded artifact did not match its reviewed digest.")
    write_private(destination, raw, raw=True)
    return entry


def unpack(entry, archive: Path, destination: Path):
    """Extract one known member, never arbitrary archive paths or symlinks."""
    raw = archive.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == entry["sha256"], "checksum_mismatch", "Archive changed after download or offline transfer.")
    require(entry["format"] in {"raw", "zip", "gzip"}, "invalid_archive", "Unsupported artifact format.")
    if entry["format"] == "zip":
        with zipfile.ZipFile(archive) as z:
            member = z.getinfo(entry["member"])
            require(member.file_size <= 160 * 1024 * 1024, "invalid_archive", "Unexpected executable size.")
            raw = z.read(member)
    elif entry["format"] == "gzip":
        with gzip.open(archive, "rb") as f:
            raw = f.read(160 * 1024 * 1024 + 1)
    require(len(raw) <= 160 * 1024 * 1024, "invalid_archive", "Unexpected executable size.")
    if destination.exists():
        require(destination.is_file() and not destination.is_symlink() and destination.read_bytes() == raw,
                "artifact_changed", "Existing native runtime differs; do not overwrite a possible active client.")
        return
    write_private(destination, raw, raw=True)
    destination.chmod(0o700)
