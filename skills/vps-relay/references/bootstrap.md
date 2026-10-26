# 首次安装 / First-time bootstrap

先完成只读检查，再选择最少的安装动作。Agent 运行在 Linux 容器中，不代表用户的 Mac/Windows 已经安装客户端。
没有可用的起始联网路径时，先安排用户提供可信连接或离线安装包；不能靠切换一个未验证节点来下载救援工具。

| 检查结果 | 下一步 / Required action |
| --- | --- |
| 无 Python 或低于3.11 | 从 [Python 官方下载](https://www.python.org/downloads/) 或已有系统包管理器获取受支持版本；验证发行者、平台、签名/摘要，安装后重新检查解释器。CLI不能安装尚不存在的自身解释器。 |
| 无 OpenSSH | 先核实系统内置工具；Windows按 [Microsoft说明](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse) 安装 **Client** 组件。只管理VPS无需打开用户电脑的SSH Server。Linux按当前发行版官方仓库安装客户端。 |
| 无 curl / CA信任异常 | 优先系统受支持包；核对 [curl官方来源](https://curl.se/download.html) 与平台提供者。先修复系统时间/证书信任，不能使用`-k`绕过验证。 |
| 无 GUI客户端 | 先提供 [官方 Clash Verge Rev](https://github.com/clash-verge-rev/clash-verge-rev/releases) 的适配版本；隔离测试可只下载便携 Mihomo。 |
| 已有兼容客户端 | 检查实际版本、REALITY/Vision与Hysteria2支持、当前配置/启动状态，复用并导入独立候选；不另装替代软件。 |
| Shadowrocket未购买/不可用 | 不要求Apple账号或付费；回到兼容免费方案。已拥有或明确选择时再使用。 |
| 架构不匹配 / 空间不足 | 停止执行安装包；重新选择官方适配构建或按适配流程研究。检查下载、解压、日志及回滚运行时所需空间，不猜测兼容性。 |
| 需要管理员 / VPN权限 | 准备具体操作并解释原因，用户在OS界面确认；不索要密码。没有授权就保持已准备状态。 |
| GitHub/下载不可达 | 保留旧网络；检查当前代理与TLS，再用可信离线传输和独立摘要。不得使用陌生镜像、关闭证书验证或先切换候选网络。 |
| 安装/首次启动试图开启代理/TUN | 中止接管并恢复原设置。此步骤同样需要已证明的无人值守恢复；无法证明则由用户本地协助操作。 |

Record installation evidence privately: component, repository/vendor identity, version, OS/architecture, release asset, digest/signature result,
required permission and observed post-install network state. Do not copy account details, machine paths or installer logs into the public repository.

Re-run tool/version discovery after installation. Verify the original agent path, profile, enabled state, proxy, DNS and interfaces still match the baseline.
Detecting an application directory is only a hint, not a compatibility check. Never launch a downloaded binary merely to learn whether its architecture is correct.

The helper automates pinned portable-core downloads. GUI, interpreter, package-manager and permission operations are agent-assisted:
prepare the exact vendor/platform step, let the user complete unavoidable authentication/OS prompts, then independently verify the outcome.
