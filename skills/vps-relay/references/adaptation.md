# Unlisted environments / 未列系统

The automatic server adapter is deliberately limited to Debian13/amd64. Other platforms are not forbidden, but not silently supported.

1. Inspect the actual OS/version, architecture, package manager, service manager, firewall, current proxies and permissions.
2. Read the current official OS, client/core and provider documentation. Record the relevant source/version in the private plan.
3. Explain differences from the reference recipe and propose the smallest adaptation. Preserve the same approval/recovery gates.
4. Prefer a disposable environment or isolated local test. Do not disable SELinux, certificate verification, host-key checks, firewall protection or approval mechanisms to fit a script.
5. Validate syntax, credentials, certificate behavior, address-family routing, cleanup ownership and unattended restoration on the actual platform.
6. Mark the path experimental and report what was not tested. Offer a synthetic, privacy-reviewed contribution only if the user asks.

The helper returning `needs_research` is a handoff to the agent's research step, not permission to skip validation or a claim the task is impossible.
If no safe automatic restore exists, prepare the client and offline recovery steps for a user-assisted switch.
If downloaded releases are unreachable, use an existing trusted connection or an offline transfer with independently verified digest; never disable TLS verification.

中文：不写死路径、网卡名和发行版命令。先发现能力、查官方资料、提出适配，再证明安全与可用性。
没有证据就保持实验性或“需要用户操作”，不要把一个成功样例升级成对所有系统的保证。
