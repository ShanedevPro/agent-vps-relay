"""OS scheduler entry point copied to private storage before a trial."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from relay_agent.guard import restore, worker

if __name__ == "__main__":
    os.umask(0o077)
    directory = Path(sys.argv[1])
    if sys.argv[2:] == ["--restore"]:
        result = restore(directory)
        print("Restoration state: " + result)
        raise SystemExit(0 if result in {"rolled_back", "committed"} else 1)
    worker(directory)
