# Tests / 测试与验收

Default tests use synthetic data, loopback HTTP fixtures and mocked server commands. They do not require a VPS or change routing.

```sh
python3 -m unittest discover -v
python3 tools/privacy_audit.py
python3 tools/check_docs.py
```

The opt-in native scheduler lab creates a dedicated private fixture store. It restores JSON-file settings only, kills its launcher,
waits for the OS-owned worker and retires only its own jobs. Do not replace its fixture adapter with a real VPN to run this test.

```sh
python3 tools/guard_smoke.py
```

Use `--root` only for a new, private, internal-disk directory outside Git. The lab preserves its result/checkpoints for local review.
The worker needs an available OS session/service manager and a local interpreter. An unavailable scheduler must fail without a shell fallback.

## Coverage and optional follow-ups

| Case | Current evidence | Optional maintainer follow-up |
| --- | --- | --- |
| Missing tools/no discovered client, unknown architecture | Synthetic discovery/download refusal tests | Actual clean-device installation and version checks |
| Missing Python, paid client unavailable, low privileges | Explicit bootstrap/handoff workflow | Clean-device manual/agent-assisted acceptance; no paid-client requirement |
| Existing compatible client | Real loopback controller fixture, preserved baseline/settings | Actual installed GUI, imported nodes, browser and routing acceptance |
| First launch activates proxy/TUN, download/GitHub unavailable | Fail-closed workflow and integrity errors | Disposable device/VM injection; verify original connection survives |
| Expected IPv4/IPv6 egress, blocked UDP, HTTP/DNS failure, old-proxy path | Mocked probe results, direct-evidence binding | Independent paths for each family; physical source or paired captures |
| Wrong password, wrong pin | Pin format/config validation and rejection-state tests | Real server/core negative handshake tests; parser success is insufficient |
| Agent disappears; websites work without commit | Unit state transitions plus native macOS launcher-death fixture | Native Linux/Windows labs; actual guarded client pilot |
| Interactive recovery prompt | Failed-proof blocks arm | Actual UAC/sudo/locked-session boundary tests per supported platform |
| Resume, credential preservation, foreign state/modified files | Private-store and mocked remote deployment tests | Fresh/interrupted/repeat disposable server deployment |
| Correct job cancellation and cleanup | Ownership, active-lease, references/open-file protection | Platform job/readback and native client-use acceptance |
| Firewall activation / private SSH | Owned rollback implementation and mocked firewall staging tests | Fresh nonroot Tailscale SSH/sudo, provider-console recovery, paired public denial |

CI is configured for multiple OS/Python versions; consult its actual run results on GitHub.
Docker/VM-backed server integration and paid VPS pilots are optional additional coverage, recorded separately from mocks.

## Disposable server/pilot procedure

1. Identify a throwaway Debian13/amd64 environment. For a paid VPS, obtain approval of provider, location, total budget,
   expected duration and destruction rules before purchase. Keep all identifiers and costs in private state.
2. Verify console recovery, independently pinned SSH identity, key access and noninteractive sudo. Install/join management-only Tailscale.
   Prepare the private synthetic-template profile with actual values; no production credentials may be reused.
3. Run `plan`, review the exact target, then `apply` with that digest. Verify services/permissions/443 listeners.
   Repeat apply after a fresh plan: credentials and ownership must stay unchanged. Interrupt package/download/service phases and resume.
4. Stage each client on a distinct loopback port. Validate the pinned core config, then test direct transport, DNS/UDP, expected exit,
   wrong password/pin, IPv4/IPv6, blocked UDP, restart, bounded transfer and a short sustained session. Record actual results privately.
5. Stage a real client on a disposable secondary device. Validate GUI/browser/rules and baseline restoration; prove OS recovery.
   Trial a deliberately unusable candidate and terminate the launcher. Also let generic websites pass while omitting the agent commit.
   In both cases the original profile, proxy and DNS must return without a new prompt.
6. Run a successful guarded trial. Receive fresh agent output and commit in a separate action. Confirm only that lease's job stops.
   Test resume after rollback and commit without purchase, duplicate service or credential regeneration.
7. Restrict management with its separate server lease. Test every assigned public family directly, fresh Tailscale SSH/sudo and both protocols.
   Exercise server rollback before committing. An untestable family stays pending rather than receiving an invented success.
8. Review cleanup against active configs, backups and workers, export the allowlisted report, inspect it, and retire the exact disposable resources
   under the approved destruction rules. Check provider inventory/billing and Tailscale independently. Preserve private evidence.

Publication follows [the publishing checklist](RELEASING.md); these experiments are not required to publish the guide.
中文：维护者按需要选择实验，不要求用户先跑实验，也不要求发布前购买VPS。默认测试不碰现用网络；收费实验须先明确费用和回收范围。
