"""Check local Markdown references; do not crawl remote sites or publish data."""
from pathlib import Path
import re
import urllib.parse

root = Path(__file__).resolve().parents[1]
failures = []
for file in root.rglob("*.md"):
    if any(x in file.parts for x in [".git", ".venv", "build", "dist", ".test-work"]):
        continue
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", file.read_text(encoding="utf-8")):
        if "://" not in target and not target.startswith(("#", "mailto:")):
            path = urllib.parse.unquote(target.split("#")[0])
            if not (file.parent / path).is_file():
                failures.append((str(file.relative_to(root)), target))
for file, target in failures:
    print(file + ": broken local link " + target)
print("Documentation links: " + ("FAILED" if failures else "passed"))
raise SystemExit(bool(failures))
