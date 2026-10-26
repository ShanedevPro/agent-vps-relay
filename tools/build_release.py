"""Build local review artifacts without leaking filesystem owners or build times."""
import gzip
import os
from pathlib import Path
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EPOCH = 946684800  # Fixed public epoch: 2000-01-01; no private session timestamps.


def normalize_sdist(path):
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output, tarfile.open(path) as source:
            with gzip.GzipFile(fileobj=output, filename="", mode="wb", mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as target:
                    for member in sorted(source.getmembers(), key=lambda m: m.name):
                        name = Path(member.name)
                        if name.is_absolute() or ".." in name.parts or not (member.isfile() or member.isdir()):
                            raise ValueError("Unexpected source archive member")
                        clean = tarfile.TarInfo(member.name)
                        clean.type = tarfile.DIRTYPE if member.isdir() else tarfile.REGTYPE
                        clean.size = member.size if member.isfile() else 0
                        clean.mode = 0o755 if member.isdir() else 0o644
                        clean.mtime = EPOCH
                        # New TarInfo defaults to uid/gid=0, blank names and no PAX metadata.
                        target.addfile(clean, source.extractfile(member) if member.isfile() else None)
        os.replace(temporary, path)
        path.chmod(0o644)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    os.chdir(ROOT)
    os.environ["SOURCE_DATE_EPOCH"] = str(EPOCH)
    from setuptools import build_meta
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    source = build_meta.build_sdist(str(destination))
    normalize_sdist(destination / source)
    build_meta.build_wheel(str(destination))
    print("Local artifacts built with normalized metadata. Run the privacy audit before sharing.")


if __name__ == "__main__":
    main()
