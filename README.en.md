# Agent VPS Relay

**One prompt for an agent: inspect, configure and verify a self-hosted relay without abandoning the working connection.**

[简体中文](README.md) · [Agent entry](AGENT.md) · [CLI](docs/CLI.md) · [Release](https://github.com/ShanedevPro/agent-vps-relay/releases/tag/v0.1.0)

A guide and dependency-free Python CLI, not a VPN subscription or MCP service.
Default protocols: VLESS + REALITY + XTLS Vision/TCP443 and Hysteria2/UDP443. Test both before choosing a primary.

Follow the workflow for your actual devices, from missing requirements to server setup, protected cutover and maintenance.
The CLI is an optional aid.

## Start

With a local checkout, ask your agent to read `AGENT.md` and help configure a relay, preserving the current connection.
Give your agent this prompt:

```text
Read https://raw.githubusercontent.com/ShanedevPro/agent-vps-relay/v0.1.0/AGENT.md
and help me configure a VPS relay.
Check my environment and install missing requirements when necessary.
Preserve my current Internet connection. Do not switch it until the new
connection and independent recovery have been verified.
```

Optional skill installation: `npx skills add ShanedevPro/agent-vps-relay --skill vps-relay`.
Agents without skills support can read the guide directly; installing Node.js is not required for that path.

## First-time users

No preinstalled client or VPS is assumed. Inspect the agent host, actual client device and server separately.
Reuse a compatible client; otherwise offer official free Clash Verge Rev. Shadowrocket is optional and paid.
Download only missing requirements, checking official identity, version, architecture and digest.
Keep TUN, system proxy takeover, DNS hijacking and auto-connect off while staging.
Network-affecting installers and first launches require the same recovery protection as cutover.
Users complete payment, login and OS authorization in the relevant application, without sending passwords to the agent.

The CLI needs Python 3.11+. Network/server operations also require OpenSSH and curl.
If Python is missing, the agent first follows the platform's official installation path; the CLI cannot bootstrap its own absent interpreter.

```sh
python3 -m relay_agent inspect
python3 -m relay_agent bootstrap
```

Bootstrap downloads verified portable test cores; it does not start them, install a GUI or enable a VPN.
The agent handles GUI installation using available platform tools or an explicit user handoff.

## Keep the agent reachable

Save the working baseline, test the candidate through loopback-only ports, prove unattended restoration, save offline recovery instructions,
then arm an OS-owned 180-second lease. A fresh agent action must commit after verification; websites working alone never commit it.
Without commit, the worker restores the original connection even if the agent disappears.

Recovery uses launchd, systemd user services or Windows Task Scheduler, with no detached-shell fallback.
It cannot promise to restart a terminated agent. When unattended recovery cannot be proven, leave configuration staged and use user-assisted cutover.
The supplied Mihomo adapter switches an existing group only; it cannot restore a different VPN application's global takeover.

## Scope

Debian 13/amd64 is the automated server reference. macOS/Windows are client reference paths.
Unlisted environments require official-source research, a proposed adaptation and unchanged safety gates; label them experimental.
Preserve credentials on reruns and unrelated applications/profiles throughout.
After verification, ordinary SSH can be restricted to Tailscale while TCP443/UDP443 stay public.
IPv6 is optional. Public SSH checks cover the server's actual assigned address families, including provider NAT/floating addresses you declare.
Client recovery and server firewall recovery are independent.

## Privacy and release

Private credentials and checkpoints live outside the repository. Public reports use an allowlist and contain no endpoints or arbitrary logs.
No telemetry, control plane or automatic uploads. Examples are fictional; publication and paid infrastructure are separate approvals.
See [privacy](docs/PRIVACY.md), [retrospective](docs/RETROSPECTIVE.md) and [release gates](docs/RELEASING.md).
Original code: MIT. Upstream components retain their licenses.
Maintainers can use the [test records](docs/VALIDATION.md) and [test procedures](docs/TESTING.md); users do not need a maintainer test run before following the guide.
