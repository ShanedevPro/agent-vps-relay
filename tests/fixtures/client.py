"""Synthetic client: changes a private JSON file, never networking."""
import json
from pathlib import Path
import sys

operation, filename = sys.argv[1:3]
path = Path(filename)
if operation == "capture":
    print(path.read_text())
elif operation == "restore":
    path.write_text(json.dumps({"selected": "original", "proxy": "original", "dns": "original"}))
elif operation == "switch":
    path.write_text(json.dumps({"selected": "broken-candidate", "proxy": "candidate", "dns": "candidate"}))
elif operation == "health":
    print(json.dumps({"ok": json.loads(path.read_text())["selected"] == "original"}))
elif operation == "fail":
    print("SYNTHETIC_SECRET_MUST_NOT_ESCAPE", file=sys.stderr)
    raise SystemExit(1)
