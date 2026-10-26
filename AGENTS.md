# Contributor guidance

`AGENT.md` is the deployment-user entry point; this file governs repository maintenance.

- Keep code dependency-free on Python 3.11+, with no import-time side effects.
- Never use production VPNs, personal configurations or paid infrastructure in default tests.
- Fail closed on unproven recovery. There must be no thread/nohup fallback for client takeover.
- Never print raw subprocess errors, configurations, import URIs or private snapshots.
- Use synthetic examples and documentation IP ranges. Do not import real case records or commit private state.
- Preserve credential identity and unrelated resources on reruns/cleanup.
- Run `python -m unittest discover -v` and `python tools/privacy_audit.py` after meaningful changes.
- Publish the guide and helpers using `docs/RELEASING.md`; paid pilots and platform labs are optional maintainer work.
- Keep per-user connectivity and unattended-recovery checks in the deployment workflow.
