import json
import sys

if sys.version_info < (3, 11):
    print(json.dumps({"phase": "needs_user_action", "error": "python_too_old", "message": "Install Python 3.11+ through the official platform path first."}))
    raise SystemExit(2)

from .cli import main

raise SystemExit(main())
