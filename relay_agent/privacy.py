"""Public reports are constructed, never redacted from arbitrary private logs."""
from . import __version__

PHASES = {"needs_user_action", "staged", "testing", "rolled_back", "verified", "blocked"}
CHECKS = {"google", "github", "exit", "udp_dns", "direct_path", "tailscale_ssh", "public_ssh_blocked", "recovery"}


def public_report(state):
    phase = state.get("phase")
    checks = state.get("checks", {})
    return {
        "schema_version": 1,
        "tool_version": __version__,
        "phase": phase if phase in PHASES else "needs_user_action",
        "checks": {key: value for key, value in checks.items() if key in CHECKS and type(value) is bool},
        "live_pilot_validated": state.get("live_pilot_validated") is True,
    }
