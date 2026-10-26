# 维护与恢复 / Maintenance and recovery

保留私有的工作记录：协议与版本、节点导入位置、主用/备用选择、SSH指纹、Tailscale管理地址、控制台恢复步骤、证书期限及当前配置备份。
公开报告只保留白名单结果。不要为了“清理”删掉凭据、已验收配置、恢复卡或唯一可用的旧连接。

- **REALITY失败：** 分开检查公网TCP可达性、服务日志、UUID/flow/public-key/short-id、target/SNI与TLS兼容、客户端版本和直接出口。
  对同一服务器/客户端做单变量对照；不要把换target后成功解释成某网站是所有失败的唯一原因，也不要保证永不封锁。
- **Hysteria2失败：** 先区分UDP不可达、认证失败和证书pin不匹配。错pin必须失败；不能删掉pin或开启无验证连接作为修复。
- **证书/pin轮换：** 提前检查期限，在保留另一条已验收连接时准备新证书，独立计算pin，经已验证SSH传送到客户端。
  备份证书/密钥/配置，隔离验证新pin成功、旧/错误pin失败，再安排受保护切换；失败就恢复成对文件。
  不静默轮换密码或REALITY密钥。内置`apply`拒绝配置漂移；维护变更使用单独审阅的适配步骤。
- **版本升级：** 按官方发布说明重新评审身份、签名/摘要及互操作，不用普通resume当升级命令。保留旧二进制/配置并先在一次性环境验证。
- **SSH失联：** 新建Tailscale SSH连接与`tailscale ping`是不同检查；私网SSH失败时等待服务器独立回滚或使用服务商控制台。
  不为修复代理而关闭Tailscale、Wi-Fi或修改另一台设备的正常代理。
- **Agent退出：** 等待租约恢复，必要时按私有`RECOVER.txt`执行本地恢复命令；重开Agent后用`resume`读取checkpoint，不重复购买或初始化。

For the pinned Mihomo version, a certificate fingerprint installs a custom TLS verifier; the config's `skip-cert-verify: false`
does not mean a public CA will accept the self-signed certificate. Trust is the independently transported SHA-256 pin.
Leaf pin matching has different name/expiry semantics from normal CA validation; track expiry and test each intended native client separately.
See the pinned upstream [TLS configuration](https://github.com/MetaCubeX/mihomo/blob/v1.19.33/component/ca/config.go)
and [fingerprint verifier](https://github.com/MetaCubeX/mihomo/blob/v1.19.33/component/ca/fingerprint.go).

Retire only the exact completed recovery jobs. Cleanup skips checkpoint dependencies, modified files and files whose inactivity cannot be established.
Removing an old VPS also requires reviewing snapshots, volumes, IPs, local nodes, Tailscale membership and billing; retain a usable new connection throughout.
