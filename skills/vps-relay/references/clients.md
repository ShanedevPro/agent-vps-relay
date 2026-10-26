# Client setup / 客户端

Check the actual device and OS/architecture. Reuse compatible installed software; do not assume the agent's host is the client.
Current official sources:

- [Clash Verge Rev releases](https://github.com/clash-verge-rev/clash-verge-rev/releases): free GUI option; follow the release's actual OS/architecture requirements.
- [Mihomo releases](https://github.com/MetaCubeX/mihomo/releases): portable core for loopback-only tests. Do not confuse similarly named game/API packages with this repository.
- [Shadowrocket App Store](https://apps.apple.com/app/shadowrocket/id932747118): optional paid client; inspect current availability/compatibility and let the user complete purchase/login.
- [Mihomo proxy ports](https://wiki.metacubex.one/en/config/inbound/port/): mixed HTTP/SOCKS listener for isolated checks.

Download only from the verified repository/vendor or official package registry. A lookalike download website is not an official source.
The CLI lock records reviewed core versions/digests. GUI installers are an agent-assisted path: record the verified release/asset and its integrity before execution.
Never bypass TLS/signature/Gatekeeper warnings or fetch an unknown binary just to make the plan continue.

For first-time users, explain what the application does and that a client does not include a proxy subscription/server.
Do not ask them to find their own tool without first inspecting what is missing and preparing a concrete installation step.
Do not install unnecessary browser automation, WSL, Node.js or an alternative client if the existing client works.

Before any network-affecting installation/first launch, preserve the current connection and meet the continuity gate.
Handle login, UAC/sudo, network extensions and VPN permission through the user's normal OS interface. Never ask for passwords in chat.
Do not let the new GUI auto-start a blank profile, enable system proxy/TUN, hijack DNS or register auto-connect as an installation side effect.
If the installer cannot be contained safely, download/stage it and use a user-assisted local step rather than risk the agent's connection.

For isolated tests, keep `allow-lan=false`, bind loopback, disable TUN and DNS takeover, and explicitly select a physical outer interface when needed.
The helper stages permanent import files under `clients/` by default. `--temporary` is only for short-lived tests.
If a native core is needed for daily use, download with `bootstrap --keep`; do not make a normal client depend on a disposable `temp/` file.

Import a separate profile, preserve rules/old nodes, and compare the actual imported UUID/flow/SNI/pin without printing secrets.
Check the UI and an actual browser if those tools are available. Otherwise give the user the exact test and distinguish their confirmation from automated evidence.
Wrong-pin and wrong-credential tests must fail. A latency number alone is not acceptance.

中文要点：有客户端先复用；没有再提供官方免费方案，付费软件只在用户选择后使用。
先准备、后导入、最后受保护试切换，不让安装程序提前抢占代理。
无法无人值守恢复时必须停在“已准备/需要用户操作”，不能标为完成。
