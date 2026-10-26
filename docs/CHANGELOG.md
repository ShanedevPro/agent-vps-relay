# Guide updates on main

- Added an optional bilingual Static ISP Exit chapter with an IPRoyal example, private credentials, Mihomo chaining and separate Claude eligibility guidance.
- Linked it from onboarding, agent/skill entries and workflows. The v0.1.0 tag, helper code and release packages are unchanged.

# v0.1.0

首次发布：给 Agent 一句话，按实际环境配置自建 VPS relay。

- 中文优先的双语指南、简短 Agent 入口与可选 skill。
- 首次使用检查、官方来源补齐依赖、现有客户端复用。
- Debian13/amd64 双协议参考配置：REALITY/Vision TCP443 与 Hysteria2 UDP443。
- 隔离测试、OS托管恢复租约、离线恢复卡、独立提交与断线回滚。
- Tailscale 管理 SSH、公网代理流量保留、按实际分配地址族检查。
- 私有运行状态、凭据复用、限定所有权的清理、无遥测与白名单报告。
- 可选 Python3.11+ CLI、合成示例与维护者工具。

Read the [agent guide](../AGENT.md) to begin. Each setup follows its own connectivity and recovery checks.
Maintainer platform labs and paid VPS pilots are optional; the guide does not require buying a test server before use.
