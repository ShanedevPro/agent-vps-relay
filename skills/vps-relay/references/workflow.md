# Workflow

## Inspect and agree

Confirm the goal, client devices, existing VPS, budget and desired provider only where not discoverable.
Inspect the agent host, user client and server separately. Record OS/architecture, privileges, available tools and actual connectivity.
Identify the working path for the agent: direct Internet, router, system VPN, application proxy or environment proxy.
Never infer that path from a Google request alone. An initially working agent connection is needed; there is no promise of autonomous offline bootstrap.

Explain the proposed changes and gain alignment. Preserve current profiles and settings; do not replace another provider as a side effect.
Default to both REALITY/Vision/TCP443 and Hysteria2/UDP443, comparing real results rather than claiming a universally best protocol.

## Bootstrap without takeover

Inspect Python, OpenSSH, curl, certificate trust and client software. Reuse compatible installed tools.
Load [first-time bootstrap](bootstrap.md) when any requirement is missing or a first launch is needed.
If a tool is missing, use official platform documentation and an official registry/vendor release. Confirm platform, architecture and integrity.
Do not install WSL, Node.js, browser automation, a package manager or a paid client just because one old example used it.
Python missing: install it through the official platform path before invoking this project's CLI.

Read [clients.md](clients.md) when selecting/installing a client. Use a verified portable core for isolated testing where possible.
Do not enable system proxy, TUN, DNS hijacking, auto-connect or startup takeover during staging.
An installer/first launch that can change networking is subject to the same recovery gate as a profile switch.
If permissions or safe unattended recovery are unavailable, prepare the exact local user step and verify it afterward; do not falsely mark it done.

## Obtain a server and establish access

Read [providers.md](providers.md) only if purchase/provider work is needed.
Use the user's existing server when suitable. Inspect current offers/availability before recommending a new purchase.
The user completes authentication, payment, CAPTCHAs and required privileges in the actual service/app. Never ask for a password/code in chat.
Verify server identity through an independent provider-console/host-key source. A keyscan is not proof of identity.
Establish dedicated key access, nonroot sudo and recovery-console access. Install/join Tailscale using current official instructions when chosen.
Do not make it an exit node or change DNS/subnet routing for a management-only deployment.

## Deploy and isolate

Use a private profile outside Git. `plan` is for review; `apply` requires its exact digest and rechecks server state.
The automated reference adapter is Debian 13/amd64. Read [adaptation.md](adaptation.md) for other environments; never force Debian commands.
Review and pin current upstream releases, not mutable latest URLs. Do not upgrade an accepted deployment silently.
Generate credentials once. A pending/server receipt must survive interrupted deployment; resume it instead of rotating credentials.
Stage REALITY and Hysteria2 separately; do not mix fields or disable TLS verification to fix a mismatch.
Self-signed Hysteria requires an actually enforced pin or trusted CA. Include a wrong-pin rejection test.

Run isolated clients bound to loopback, with TUN and DNS takeover disabled. Bind their outer transport to a discovered physical interface when needed.
Check each available address family separately; IPv6 is optional. Verify the test did not silently chain through the working VPN; use physical source checks or paired server capture.
Record fresh direct-path evidence privately; the CLI consumes an attestation, not an automatic proof of an arbitrary network path.
Use actual target/SNI compatibility tests; a protocol failure does not establish that an entire IP is blocked.

Verify repeated HTTP/egress requests, UDP DNS, invalid credentials/pin rejection, a restart, bounded transfer and a short sustained session.
Read actual-client/browser behavior separately. Curl success is not browser acceptance or a long-term guarantee.
If only one protocol works, describe the partial result and user options; do not label both verified.

## Stage the user client and protect the agent

Import a separate candidate without overwriting or selecting the original profile. Complete required permissions before the actual trial where safe.
Capture the original profile/enabled state and system proxy/DNS settings with a concrete local restoration action.
The provided Mihomo controller adapter supports existing group node selection only. Cross-app takeover needs a broader, reviewed adapter.
Snapshot/health/restore commands must be locally available, bounded, noninteractive and use absolute executable paths.
Declare immutable scripts/settings dependencies. Read [continuity.md](continuity.md) before any takeover.

Prove restoration by an OS-owned job. Creating a task or running restore from the agent's own terminal is insufficient.
Save offline recovery instructions. Arm a 180-second lease immediately before an explicitly approved trial; never extend it automatically.
The worker must survive the agent/launcher dying. No fresh password, unlock dialog, network download or model response may be needed to restore.
If proof fails, **do not automate takeover**. Leave the setup staged for a user-assisted switch.

After switching, verify the real client and obtain a fresh agent response. `verify --lease` returns a short-lived commit token.
Commit in a separate agent action. Do not combine switch, verify and commit in a single tool call/script.
When uncertain, omit commit: the worker restores the original. Restoring Internet does not guarantee restarting an exited agent.
Resume from the checkpoint after reconnection, without repeating initialization, purchasing or credential generation.

## Restrict management, then finish

Server firewall recovery is separate from client recovery. Keep public SSH until fresh Tailscale SSH/sudo and provider-console recovery pass.
Use a server-owned rollback before changing the firewall. Probe public SSH directly for the server's assigned address families; do not test it through the server's own proxy.
Discover the server's assigned public addresses, and declare additional provider NAT/floating addresses in `management.public_addresses`.
Recheck both public proxy protocols and fresh private SSH before committing management restriction. Keep TCP443/UDP443 and Tailscale transport usable.
Do not require a family the server does not have. For an assigned family that cannot be tested, obtain a suitable independent path; do not fabricate evidence to commit.

Document the working route, [maintenance](maintenance.md), certificate/pin renewal and recovery method.
Cancel exact recovery jobs only after their acceptance gates. Cleanup only owned temporary files; keep active profiles, credentials, backups and useful evidence.
Old-resource retirement is optional and separately approved: inspect exact resource identity, snapshots/storage/IPs, local nodes and Tailscale membership.
Stopping a VPS is not releasing it, and accrued charges are not erased by deletion.

Export only an allowlisted report after preview. Never upload private state, raw command output, packet captures, screenshots or credentials automatically.
