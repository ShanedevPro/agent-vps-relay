# CLI reference

Use Python3.11+ from this reviewed checkout, or install the package locally. No runtime dependencies.
Never run examples unchanged: all endpoint/account/fingerprint values are fictional. Keep completed profiles outside Git.

Default private state: Linux/macOS `$XDG_CONFIG_HOME/agent-vps-relay` (or `~/.config/agent-vps-relay`), Windows `%LOCALAPPDATA%/AgentVpsRelay`.
POSIX directories/files use700/600; Windows directory inheritance is restricted to the current SID and SYSTEM.
`--state-dir` must precede the subcommand; use it only for a dedicated private directory.

```sh
python3 -m relay_agent inspect
python3 -m relay_agent bootstrap
python3 -m relay_agent init --profile demo --config /absolute/private/profile.json
python3 -m relay_agent status --profile demo
python3 -m relay_agent resume --profile demo
```

`inspect` is read-only. `bootstrap` without a component is read-only. `init` creates private state and never overwrites an existing profile.
Inspection reports only detected clients; unknown/custom installations require agent discovery, not duplicate installation.

## Downloads and server

```sh
python3 -m relay_agent bootstrap --profile demo --component mihomo
python3 -m relay_agent plan --profile demo
python3 -m relay_agent apply --profile demo --approved-plan PLAN_DIGEST
```

Bootstrap verifies pinned artifacts and writes to `temp/`; `--keep` retains a daily-use runtime under `tools/` instead.
`--platform` is for explicit cross-platform preparation, never permission to execute the wrong architecture.
Downloads do not start/install the client. GUI installation and missing interpreter installation are agent/user-assisted operations.
Verified cached artifacts are reused. A changed archive or different existing native runtime is rejected instead of overwritten; upgrades need explicit review.
Pinned artifact digests are from GitHub's official release metadata, not a separately signed trust channel. Review upstream identity and release notes.

Supply a dedicated independently verified known-hosts file with exactly one key. Existing SSH config can be supplied as `ssh.config_file`, but strict checking and the pinned alias remain enforced.
The server must already support key-based SSH/sudo, Python3, `ss` and `ip`. Provision nonroot administration and console recovery through the agent workflow first.
Plan inspects the server, records a stable target/state and gives a digest. Apply rechecks it, installs owned services and preserves credentials through pending/server receipts.
Public management is preserved at deployment. Existing services/owned deployments are not silently adopted. Explicit upgrades/target repairs require a separately reviewed adaptation; they are not automatic reruns.
An inactive UFW is left inactive during deployment; only its rules are staged. Enabling it belongs to the guarded management step.
Deployment errors may leave an owned pending receipt for repair. Inspect the root-only `last-error.txt` privately; do not publish its contents.

## Stage and verify clients

```sh
python3 -m relay_agent client stage --profile demo --protocol reality --port 17890 --interface DISCOVERED_INTERFACE
python3 -m relay_agent client stage --profile demo --protocol hysteria2 --port 17891 --interface DISCOVERED_INTERFACE
```

Files are under private `clients/` and are retained. Add `--temporary` only for disposable isolated-test copies.
They bind127.0.0.1 and do not enable TUN/DNS/system proxy. Run a verified core against the file in an isolated process; the agent owns the process and stops it after testing.
Use the actual core's config validator before starting it. Do not mark protocol success based on a listening loopback port.

```sh
python3 -m relay_agent verify --profile demo --protocol reality --proxy http://127.0.0.1:17890 --direct-evidence /absolute/private/evidence.json
```

The private evidence object has `profile_digest` from status, `observed_at` (Unix seconds), `family` (`IPv4`/`IPv6`),
`method` (`physical-interface-and-source-check`/`paired-server-capture`), and `standalone_path_verified: true`.
It must reflect actual fresh observations. The helper validates its binding/freshness, not the truth of arbitrary attestations.
Missing evidence leaves `direct_path=false`; it cannot commit a trial. Expected exits come from the private profile, never from a public report.
Verify includes Google/GitHub HTTP, expected egress, SOCKS UDP DNS. Browser behavior, transfer/restart, negative authentication/pin and sustained checks remain separately required agent acceptance work.

## Client recovery and trial

For existing Mihomo selector switching, prepare private controller settings from the example without exposing its secret:

```sh
python3 -m relay_agent client prepare-controller --profile demo --settings /absolute/private/controller.json
python3 -m relay_agent guard baseline --profile demo
python3 -m relay_agent guard prove --profile demo --approved
python3 -m relay_agent guard status --profile demo
python3 -m relay_agent guard arm --profile demo --approved
python3 -m relay_agent guard switch --profile demo --lease LEASE_ID --approved
```

Wait for `proof_passed` before arming; prove/arm are OS-owned jobs, not background shells. The proof expires after30 minutes and changes invalidate it.
Retire the completed proof job with `guard retire --profile demo --lease PROOF_ID`; keep its proof record.
After switching, call verify with `--lease LEASE_ID`. Receive the result and make a fresh agent round trip, then separately:

```sh
python3 -m relay_agent guard commit --profile demo --lease LEASE_ID --agent-ack FRESH_TOKEN
```

Never batch switch/verify/commit. Default TTL180s, configurable30–900s before arming, no extension. Too little remaining time blocks switching.
Omitting commit restores the original. Manual recovery is `guard rollback --profile demo --lease LEASE_ID`; an offline recovery card is saved privately.
Arbitrary/cross-app transitions need a reviewed complete adapter, not the supplied node-selection adapter. See the continuity reference.

## Server firewall recovery

```sh
python3 -m relay_agent management plan --profile demo
python3 -m relay_agent management apply --profile demo --approved-plan PLAN_DIGEST
python3 -m relay_agent management status --profile demo
```

Only after fresh private SSH/sudo and console recovery. Root-owned proof then10-minute rollback; no client-lease cancellation.
The reference recipe removes only its own bootstrap SSH rule. Pre-existing/foreign SSH allowances require a reviewed adaptation, not deletion by guesswork.
Verify both proxy protocols after restriction. Direct public denial evidence contains `profile_digest`, `observed_at`,
and `public_ipv4_ssh_blocked: true` and/or `public_ipv6_ssh_blocked: true` for the server's assigned public families, from actual direct-interface probes.
The helper discovers assigned addresses over private SSH and includes the configured relay endpoint. Declare provider NAT/floating addresses under
`management.public_addresses`. An IPv4-only server needs only the IPv4 result; an IPv6-only server needs only IPv6. Assigned IPv6 still needs a check even when the chosen proxy endpoint is IPv4.

```sh
python3 -m relay_agent management commit --profile demo --evidence /absolute/private/public-ssh-checks.json
python3 -m relay_agent management rollback --profile demo
```

If private access fails, wait for server rollback or use the provider console; never count inability to SSH as proof the firewall is correct.

## Cleanup and reports

`cleanup --profile demo` removes only unchanged files in the recorded `temp/` manifest. Armed/failed recovery blocks cleanup.
Checkpoint dependencies and open files are protected. If `lsof` is absent or inspection fails, cleanup conservatively skips files.
Do not install tools solely for cleanup or run daily-use clients from temp files; Windows currently retains these files for manual inspection.
`report --profile demo` emits a strict public allowlist of phase/boolean checks, not endpoints, filenames or raw logs. Preview before sharing.
JSON errors are typed and intentionally suppress raw command output. Exit2 means a known blocked condition; exit3 is an unexpected failure.
