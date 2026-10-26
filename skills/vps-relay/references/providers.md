# Providers / 服务商

Start with an existing suitable VPS. Ask about budget, region, transfer needs and intended client network only when missing.
Use current official information; this project has no affiliate links or permanently recommended price/offer.

- [Vultr](https://www.vultr.com/) / [documentation](https://docs.vultr.com/)
- [RackNerd](https://www.racknerd.com/) / [customer portal](https://my.racknerd.com/)
- [Tailscale installation](https://tailscale.com/download) / [SSH over Tailscale](https://tailscale.com/docs/reference/ssh-over-tailscale)

Compare actual cost, region, memory, architecture, transfer allowance, IPv4/IPv6 availability and billing model.
Do not treat a datacenter IP as a residential/ISP exit, promise access to every website, or guarantee immunity from blocking/account restrictions.
Prefer a small reversible trial when the network path is uncertain; do not buy extra addresses merely because a protocol request failed.

Prepare the concrete cart/choice and total commitment before requesting approval. Users complete payment and legally binding account steps.
Do not invent billing details, phone numbers or addresses. Ask only for genuinely required information or hand off the sensitive form.
Use an already authenticated portal when available. Authentication in one browser is not authentication in another.
Check actual provisioning, service identity and assigned addresses after purchase. A payment page or welcome email is not a working relay.

IPv6 is conditional: confirm availability, region policy, client reachability and any cost. If needed, prepare a support request with the user's actual service data privately and obtain authorization before sending it.
Do not publish ticket URLs, access codes, service IDs or billing screenshots. A request submitted through another proxy may display that proxy's IP; it is not necessarily the allocated VPS address.

Use the provider recovery console to verify server identity/fingerprint and a usable recovery login. Opening a console login prompt is not completing the test.
Generate a dedicated local SSH key, pin the independently verified host key, establish a nonroot administrator and verify fresh sudo.
If only a password login is initially available, the user completes the sensitive local bootstrap; never paste the password into chat or command arguments.

For management-only Tailscale, preserve DNS and default routes; do not enable an exit node, subnet routes or built-in Tailscale SSH merely as a side effect.
Only close public SSH after the server's private address, ordinary OpenSSH/sudo and recovery have been verified. Keep proxy data traffic public.

Retirement is separate from initial setup. Before final approval, show the exact instance and associated billable storage/backups/reserved IPs.
Verify destruction, not power-off. Explain already-accrued charges, then remove only matching client nodes, Tailscale device and obsolete tunnel jobs.

中文要点：先查现有资源，再决定是否购买；价格、流量和 IPv6 以当前官方信息为准。
用户完成付款/验证，Agent 负责准备清楚的选择并核验结果。不能把支付、在线、能 SSH 和代理验收混成一个“已完成”。
