# Agent VPS Relay

**给 Agent 一句话，从检查环境到配置自建节点，同时保留你的正常联网。**

[English](README.en.md) · [Agent 入口](AGENT.md) · [命令说明](docs/CLI.md) · [发布说明](https://github.com/ShanedevPro/agent-vps-relay/releases/tag/v0.1.0)

这是「操作指南 + 小型 Python CLI」，不需要 MCP 服务，也不提供节点、订阅或账号。
默认配置 **VLESS + REALITY + XTLS Vision/TCP443** 和 **Hysteria2/UDP443**，在实际网络测试后选择主用协议。

从检查环境、补齐软件到配置服务器、保护联网和日常维护，按实际设备逐步执行。CLI 是可选辅助工具。

## 一句话开始

已在本地获得项目时，告诉 Agent：

```text
阅读这个项目的 AGENT.md，按流程帮我配置自建 VPS 代理。
先检查我的设备和现有连接；缺少必要软件时再下载、安装。
保留我现在的正常联网。没有验证新连接和独立回滚前，不要切换系统代理或 VPN。
```

直接把下面这段话发给 Agent：

```text
Read https://raw.githubusercontent.com/ShanedevPro/agent-vps-relay/v0.1.0/AGENT.md
and help me configure a VPS relay. Inspect my environment and install missing
requirements when necessary. Preserve my current Internet connection.
Do not switch it until the new connection and independent recovery are verified.
```

可选技能安装：`npx skills add ShanedevPro/agent-vps-relay --skill vps-relay`。
不支持 skills 的 Agent 直接读取 AGENT.md 即可；不能因此要求用户安装 Node.js。

## 第一次使用也可以

不要求提前安装 Shadowrocket、Clash、Tailscale 或 SSH 工具。
Agent 先区分自己的运行环境、你的客户端设备和 VPS，再检查系统、架构、权限、软件、IPv4/IPv6 及当前联网方式。

- 有兼容客户端就优先复用，不随意更新或替换现有配置。
- 没有客户端，可从官方渠道选择免费 Clash Verge Rev。Shadowrocket 是用户自选的付费选项。
- 先用便携核心、临时配置和本地代理端口测试，不抢占系统代理、TUN 或 DNS。
- 下载核验来源、架构、版本和摘要。安装、首次启动可能改变网络时，按切换风险处理。
- 登录、付款、管理员授权和操作系统权限由用户在对应界面完成，不把密码或验证码发给 Agent。

CLI 需要 **Python 3.11+**；网络与服务器操作还需要 OpenSSH 和 curl。
Python 尚未安装时，由 Agent 按官方渠道补齐；不要先运行一个依赖 Python 的“安装检查”。

```sh
python3 -m relay_agent inspect
python3 -m relay_agent bootstrap
```

CLI 无第三方运行依赖，也不会在 import、inspect 或 bootstrap 检查时接管网络。
`bootstrap --component ...` 只下载、校验和解包受控测试程序，不自动启动或安装 GUI。
GUI 安装及操作由 Agent 根据当前平台执行或引导用户完成，不假装已获得管理员权限。

## 防止 Agent 断网后无法自救

流程是：**原连接快照 → 隔离测试 → 实际执行无人值守恢复证明 → 离线恢复卡 → OS 托管的 180 秒租约 → 试切换 → 验证 → Agent 下一次独立动作提交**。

macOS 使用 launchd，Linux 使用 systemd 用户服务，Windows 使用任务计划程序。
没有 `nohup` 兜底。创建任务、看到进程或网站可访问都不等于完成恢复验证。

如果 Agent 消失或没有提交，worker 到期恢复原连接。提交必须在切换后的独立 Agent 动作中进行；
不要把切换、验证和提交塞进同一脚本。系统回滚不能保证自动重启已退出的 Codex。
若当前平台无法证明无弹窗、无新密码的自动恢复，就保留配置，改为用户辅助切换。

本项目提供现有 Mihomo 分组节点切换适配器；跨客户端接管、首次开启系统代理等变化需要额外的可验证恢复适配器，不能直接套用节点选择适配器。

## 支持边界与工作顺序

Debian 13/amd64 是自动化服务器参考路径；macOS/Windows 是客户端参考路径。
其他系统先查官方资料、提出适配方案、保留验证关卡，并标记为实验性，而不是强行执行 Debian 命令。

检查 → 补齐依赖 → 购买或接入 VPS → SSH 身份和控制台恢复 → 部署双协议 → 隔离测试 → 导入客户端 → 受保护切换 → Tailscale 管理限制 → 文档与清理。

IPv6 按实际需要使用；IPv4-only 或 IPv6-only VPS 都不必为了流程再购买另一种地址。
SSH 管理与代理流量分开：检查服务器实际分配的公网地址后，只允许经 Tailscale 管理 SSH，TCP443/UDP443 保持公网可达。
Tailscale 自身仍有传输流量；不要声称“除了443所有端口都关闭了”。
服务器防火墙的回滚与本机 VPN 切换的回滚是两个独立机制。

## 可选：独享静态 ISP 出口

需要固定出口时，阅读 [Static ISP Exit 章节](skills/vps-relay/references/static-isp-exit.md)：
客户端 → VPS → 独享 ISP 代理 → 网站。IPRoyal 是示例供应商，现有 VPS-only 路径继续保留。
章节包括选择与购买、私有凭据、Mihomo 链路片段、隔离检查、恢复及 Claude 订阅要求。

这是 `main` 上的文档扩展。需要 Agent 配置此选项时，在基础流程后补充这段提示：

```text
Read https://raw.githubusercontent.com/ShanedevPro/agent-vps-relay/main/skills/vps-relay/references/static-isp-exit.md
and help me add an optional dedicated ISP exit. Preserve my working relay
and current Internet connection. Ask before any purchase.
```

## 隐私

本仓库只有新写的代码和虚构示例，没有从真实会话导入配置、日志、截图、工单、订单或 Git 历史。
凭据、导入文件和运行状态放在仓库外的私有目录。不要把 `credentials.json`、原始异常输出或节点二维码发到 issue。
`report` 使用字段白名单导出，不对原始日志做一次字符串替换后假装安全。
无遥测、无托管控制平面、无自动上传。购买、发布和删除旧服务器都需要具体授权。

查看 [隐私说明](docs/PRIVACY.md)、[匿名经验总结](docs/RETROSPECTIVE.md) 和 [维护/发布流程](docs/RELEASING.md)。

## 贡献与许可

本项目原始代码使用 MIT。上游程序保留各自许可；不把 GPL/AGPL 安装脚本复制进本项目。
请使用合成数据测试，禁止用正在工作的主机或生产节点测试断网、错误防火墙或凭据轮换。
维护者可查阅 [测试记录](docs/VALIDATION.md) 和 [测试方法](docs/TESTING.md)；用户无需先运行维护者测试才能按指南配置。
