# Agent continuity / Agent 连续性

The agent may disappear as soon as its route changes. A server rollback cannot restore a laptop's VPN, and a client rollback cannot undo a remote firewall lockout.

## Client adapter contract

The private profile's `client` object contains four argument arrays, with absolute executable paths:

- `capture_argv`: return a JSON snapshot covering original profile/enabled state and persistent proxy/DNS settings relevant to this transition.
- `baseline_health_argv`: return `{"ok": true}` only when the original working connection is usable.
- `restore_argv`: restore that exact baseline without a network download, prompt, password or agent response.
- `switch_argv`: perform only the reviewed candidate transition, with a bounded runtime.
- `immutable_files`: static settings/scripts required by those actions; changed dependencies invalidate the proof.

These are trusted, reviewed local actions, not arbitrary commands taken from logs or third-party pages. The CLI never runs them through a shell.
The provided Mihomo adapter only switches an existing selector group. It records global state but intentionally cannot repair cross-app TUN/proxy/DNS changes.
For a broader transition, create and review a complete local restore adapter or use a manual handoff. Do not call a partial adapter sufficient.
Keep adapter scripts/settings and daily-use executables outside `temp/`. Do not rely on private state stored on a removable/unavailable code checkout.

## Protocol

1. `guard baseline`: save the healthy original snapshot, once. Do not replace it to conceal a failed trial.
2. `guard prove --approved`: an OS-managed job actually invokes restore and verifies baseline equality/health. Inspect status until proof passed; task registration alone is insufficient.
   Retire the completed proof job by its exact ID; retain the proof record for arming.
3. Prepare/review `RECOVER.txt` offline. Resolve all interactive permissions before the trial where safe.
4. `guard arm --approved`: default180 seconds; choose TTL before arming, never silently extend. Only one pending lease is allowed.
5. `guard switch --approved --lease ID`: perform the trial. The job lives outside the agent process and copied repository runtime.
6. Run real candidate checks with `verify --lease`. Direct-path evidence is a fresh attestation of actual observation, not generated success.
7. The agent must receive that result and make a fresh model/tool round trip before invoking `guard commit --agent-ack TOKEN` separately.
8. No commit, missing token, expired lease, failed checks or mismatched state means no verified completion. Allow the worker to restore, or explicitly request rollback.

The acknowledgement token is not cryptographic proof that a model had a conversation. The agent protocol supplies that assertion; never automate it inside a batch script.
Worker checks do not require Internet. Restoration may check Internet after restoring, but never wait for it before restoring.
Health/proxy requests and server egress checks alone cannot establish whether Codex's control channel is alive.

## OS and failure boundaries

- macOS: launchd user job. Its runtime is copied into private storage and needs no code checkout at recovery time.
- Linux: existing systemd user manager. Do not silently enable lingering, change user service policy or substitute nohup when unavailable.
- Windows: Task Scheduler with the current interactive token and least privilege, without saving a password.

Proof is specific to current permissions/session. A locked screen, sleep, logout, reboot or security prompt can invalidate assumptions; do not claim those scenarios tested unless they were.
Unattended restore must not depend on unlocking a GUI. A user-assisted operation is the required fallback when this cannot be demonstrated.
Unexpected worker failure is restartable by the OS; failed restoration is recorded as `recovery_failed`, with cleanup blocked for manual repair.
Local offline instructions remain necessary: no software can promise recovery when the OS, power, credentials or original upstream are unavailable.

After successful restoration, reopen the agent if needed and use `resume`. Do not create another profile, buy again, rotate credentials or erase evidence to restart.
After commit/rollback, cancel only the exact owned job. Never delete an armed job/runtime as “temporary cleanup”.

中文：独立恢复必须真执行过，不能依赖 Agent 下一句话。网站可用不代表 Agent 通道可用。
切换、验证、提交分成独立动作；不确定就不提交。恢复网络不保证重启已退出的 Codex。
