# Maintainer check records / 维护检查记录

The local release record is maintained in `validation.json`; it records checks actually performed.
See [optional maintainer procedures](TESTING.md) for reproducible commands and future follow-ups.
Users follow the agent workflow and check their own environment; running this maintainer suite is not an onboarding requirement.

Local v0.1.0 checks: **78 tests passed**, real macOS launchd fixture recovery passed after launcher termination,
and checksum-verified Mihomo v1.19.33 parsed both synthetic client configurations. Skill, local documentation links,
source/index privacy and distribution-archive audits passed. These checks did not deploy or change a working VPN.

| Layer | Meaning |
| --- | --- |
| Unit tests | Synthetic profiles, malformed inputs, secrets, checksums, resume/ownership and state-machine behavior |
| Native scheduler lab | A real OS-owned worker restores a JSON-file fixture after its launcher terminates; no real VPN change |
| Core configuration check | Reviewed downloaded binaries parse synthetic client configurations; no live proxy acceptance implied |
| Disposable server integration | Actual package/service/firewall/deployment behavior in an owned throwaway environment |
| Live VPS pilot | End-to-end provider/native network/client/agent continuity; requires separate cost approval |

The Python CLI is designed for macOS/Linux/Windows. The server adapter is Debian13/amd64 only.
Additional platform labs are recorded when performed; current CI results are available on [GitHub Actions](https://github.com/ShanedevPro/agent-vps-relay/actions).
Installed-client discovery is intentionally incomplete: a custom installation is not evidence the client is absent.
The reference Mihomo adapter only switches a selector group. It does not prove safe cross-app or system-wide takeover.

Package installation, server-core interoperability, Tailscale/firewall behavior, GUI side effects and recovery during
lock/logout/sleep/reboot depend on the actual environment. The agent checks the relevant behavior during each setup.
The direct-path file is an agent attestation; the CLI verifies freshness/binding, not whether someone fabricated an observation.
The commit token records explicit acknowledgement; it does not cryptographically prove a model round trip.

中文：这里是维护记录，不是用户安装前要完成的额外任务。单测、OS文件夹具、核心解析和公网实测分别记录，
每次实际配置仍按用户自己的环境验证连接与恢复。
