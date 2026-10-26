# 可选：独享静态 ISP 出口 / Optional static ISP exit

在已有、可正常使用的 VPS relay 上增加固定出口。供应商由用户选择，IPRoyal 只是示例；基础 VPS 路径继续保留。
本章是 `main` 上的文档扩展，不修改 v0.1.0 的程序、标签或发布包。

```text
客户端 → REALITY / Hysteria2 → VPS → 独享静态 ISP 代理 → 目标网站
```

VPS 负责中转；目标网站应看到 ISP 代理的出口 IP。固定地址有助于保持出口一致，但“纯净 IP”不是账号可用或免封的保证。

## 1. 选择和购买

先确认现有 VPS、客户端及恢复方式可用，再讨论是否需要这个附加出口。按固定地址选择独享静态 ISP 产品；
轮换住宅代理或有时限的 sticky session 不等于长期固定 IP。

例如，IPRoyal 的 [ISP 产品说明](https://iproyal.com/quick-start-guides/static-residential-proxies/) 提供独享静态 IPv4，支持 HTTP/HTTPS、SOCKS5 及不同认证方式。
购买时核对所在地、独享范围、协议、实际带宽/公平使用限制、并发设备限制、续费是否保留原地址及更换政策；价格和库存以当前页面为准。
供应商的风险评分只能作为一个参考信号。

Agent 准备具体产品、数量、期限与总费用，用户确认后在供应商页面完成登录和付款。
每位用户使用自己的代理；不要在仓库中分发公共代理账号。没有采购授权时，只准备方案。

## 2. 私有保存与认证

服务器地址、端口、协议、用户名/密码、订单和有效期都保存在 Git 外的私有目录，不放进聊天、命令参数、截图或公开报告。
按 [主流程](workflow.zh-CN.md) 保护文件权限，保存原配置和恢复动作。

用户名/密码认证与 IP 白名单按供应商实际支持选择。使用白名单时，应核实供应商看到的是 **VPS 的实际公网出口**，
不要误填 Tailscale 地址、本机地址或把面板访问者 IP 当成分配的代理 IP。

普通 SOCKS5 用户名/密码认证以明文传输密码，参见 [RFC 1929](https://www.rfc-editor.org/rfc/rfc1929.html#section-3)。
客户端到 VPS 的加密不覆盖 VPS 到 ISP 代理这一跳。需要加密代理连接时，先确认供应商确实支持 TLS-to-proxy，再按官方参数配置并验证证书。
“能代理 HTTPS 网站”与“连接代理服务器时使用 TLS”是两件事。网站本身的 HTTPS 证书验证保持开启。

## 3. 复用客户端建立链路

优先使用现有兼容客户端。Mihomo / Clash Verge Rev 可按官方 [dialer-proxy](https://wiki.metacubex.one/en/config/proxies/dialer-proxy/)
和 [SOCKS](https://wiki.metacubex.one/en/config/proxies/socks/) 文档配置。其他客户端先核实当前版本的链式代理功能，不猜测 UI 字段。

下面只是给**私有候选配置**合并的示例片段，不是完整配置，也不能直接覆盖正在使用的文件。
先在候选的 `proxies` 中保留已验收的 VPS 节点，将其名字设为 `relay-transit`，或把片段中的引用改成该节点的实际名字。
地址、端口和认证值都是虚构占位符，替换只能发生在私有文件中。

```json
{
  "proxies": [
    {
      "name": "isp-exit",
      "type": "socks5",
      "server": "isp-proxy.example.net",
      "port": 1080,
      "username": "REPLACE_IN_PRIVATE_FILE",
      "password": "REPLACE_IN_PRIVATE_FILE",
      "udp": false,
      "dialer-proxy": "relay-transit"
    }
  ]
}
```

`dialer-proxy` 写在 **ISP 节点**上，指向 VPS 节点；将请求交给 `isp-exit` 才是上图方向。
把方向反过来会让最终出口变成 VPS。引用不能形成循环；不要用已经弃用的 `relay` 分组代替。

先按 TCP 网页流量配置，供应商未明确支持 UDP 时保持 `udp: false`。
Hysteria2 的客户端到 VPS 传输使用 UDP，不代表 ISP 代理也必须转发 UDP；它仍可承载通向 ISP 代理的 TCP 连接。
VPS 的 REALITY target、证书、管理 SSH 和服务端配置不需要为这个客户端方案改变。

## 4. 隔离检查

1. 复制现有配置到独立私有候选文件，复用已核验的核心，先运行其配置检查。
2. 测试进程只监听新的回环端口，例如 `127.0.0.1:17990`；关闭 LAN、TUN、DNS 接管、系统代理和自动连接。
   在这个隔离配置中将测试请求明确路由到 `isp-exit`；保留原客户端的正常路径。
3. 通过该回环端口检查 HTTPS 与实际出口，把响应保存到私有文件。出口应与供应商分配的 ISP IP 相符，不能只是旧 VPS IP。
   同时核实外层确实到达自己的 VPS，检查实际浏览器、域名解析和适用的地址族。
4. 用另一份候选配置和全新测试进程验证错误代理密码会失败。测试路径不要自动回落到 `DIRECT` 或旧出口后还显示“ISP 成功”。
5. 确认重复连接的出口稳定后，再准备用户实际使用的规则。只让明确选择的流量走 ISP，其他流量沿用原策略。

无需把密码传给 curl。下面通过已配置好的本地测试核心发请求，原始响应留在私有文件；路径需按设备修改：

```sh
curl -q --fail --silent --show-error --proxy http://127.0.0.1:17990 --noproxy .invalid \
  --connect-timeout 5 --max-time 15 \
  --output /absolute/private/isp-trace.txt \
  https://www.cloudflare.com/cdn-cgi/trace
```

## 5. 切换、CLI 与恢复

保留手动选择原 VPS 的入口，不自动把所有流量切到新出口。导入、分组和规则变化要覆盖在 [连续性流程](continuity.md) 的快照与恢复动作中。
自动切换仍须实际证明无人值守恢复，并在切换后的独立 Agent 动作中提交。无法覆盖整个变化时，准备离线恢复卡，由用户辅助切换。

**v0.1.0 CLI 的 `verify` 面向基础 relay：它检查配置中的预期出口及 UDP DNS，`--lease` 失败会触发恢复。**
它没有 ISP 链路模式。TCP-only ISP 能正常浏览时，UDP DNS 仍可能失败；不要伪造成功、关掉检查或改写基础节点的验收记录来提交租约。
本章的链路检查单独记录在私有文件中；现有工具无法表达该切换的验收条件时，使用用户辅助切换。

ISP 失败时，用户可以撤销相关规则或选回原 VPS。保持服务商续费/换 IP 状态可见；地址或认证改变后重做隔离检查。
停止项目拥有的测试进程后，只清理临时副本，保留正在使用的客户端配置、认证文件与必要备份。

## 6. Claude：网络出口与订阅分别处理

IPRoyal 是出口供应商，不出售 Claude 订阅。使用者还需满足 Claude 的账户、实际所在地、验证与支付要求。
Claude 的 [Pro 官方说明](https://support.claude.com/en/articles/8325609-how-do-i-sign-up-for-the-pro-plan) 要求使用者实际位于支持地区；
购买该地区的代理 IP 不会改变这一条件。开通前读取最新要求，用户在官方界面完成自己的注册、验证与付款。
不要把固定出口、风险评分或一次能打开网页描述成必能订阅或免封。

## English

This optional chapter adds a dedicated static ISP exit to an already working relay. IPRoyal is one example; keep the VPS-only route available.
The chapter is maintained on `main`; the v0.1.0 tag, helpers and packages remain unchanged.

1. **Choose only when needed.** Review static/dedicated status, location, protocols, fair-use limits, device limits and renewal/IP retention.
   Rotating residential pools and temporary sticky sessions serve a different purpose. Prepare the exact cost; the user authorizes purchase and completes authentication/payment.
2. **Keep authentication private.** Store endpoints and secrets outside Git with restrictive permissions. For IP allowlisting, verify the VPS's actual public source address.
   Ordinary SOCKS password authentication is plaintext on the VPS-to-proxy hop; verify genuine TLS-to-proxy support if encryption there is required. Keep destination TLS verification enabled.
3. **Reuse a compatible client.** Merge the JSON fragment into a separate candidate that already contains the accepted `relay-transit` node.
   Put `dialer-proxy` on `isp-exit`, pointing at the VPS. Route test requests to `isp-exit`; reversing the relationship changes the final exit.
   The documented client-side approach needs no VPS service or SSH changes. Check other clients' actual chain support before adapting.
4. **Start with TCP.** Outer Hysteria2 UDP transport and the upstream proxy's UDP-forwarding support are separate capabilities.
   Validate the candidate config, bind a fresh loopback port and keep global networking off. Compare the observed ISP egress, test HTTPS/browser/DNS behavior and reject wrong credentials in a fresh process, with no silent fallback.
5. **Protect continuity.** Keep the original route, stage only selected traffic and apply the existing recovery protocol to the complete change.
   The v0.1.0 CLI requires expected egress and UDP DNS; it has no ISP-chain verification mode. Do not bypass that gate for a TCP-only proxy.
   Use separate private acceptance records and a user-assisted cutover when the current helpers cannot express the transition safely.
6. **Maintain and recover.** On upstream failure, let the user restore the original selection/rules. Recheck after IP/credential changes and preserve active configuration during cleanup.
   A fixed exit does not establish Claude subscription eligibility: check the linked official region, verification and payment requirements separately.
