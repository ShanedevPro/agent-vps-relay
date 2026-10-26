# Privacy / 隐私

The public source is written fresh from general lessons. Real accounts, endpoints, hostnames, people, device IDs, timestamps of private sessions,
billing/support records, screenshots, capture files and configuration histories are not publication inputs.
Examples use documentation IP ranges, reserved example domains and synthetic placeholders.

Private runtime state is separate from Git. POSIX modes are700/600; Windows ACL inheritance is restricted.
The SSH key is referenced, not copied into a public checkout. Credentials/import files are not command-line flags or normal output.
Server credentials remain in root-only receipts and a private local manifest; repeated operations do not rotate them.

`report` constructs a small allowlist: schema/tool version, an enumerated phase, known boolean checks and an explicit live-pilot flag.
It discards endpoints, labels, tokens, arbitrary nested objects, errors, paths, bodies and screenshots. It does not upload anything.
Raw installer/client errors are intentionally suppressed from ordinary CLI output; private diagnostics must not be pasted into public issues.

No telemetry, hosted control plane, automatic report submission or hidden subscription is provided.
The user's chosen AI agent/service has its own data handling; this project cannot promise to change that service's policies.
Prefer local import/config generation so secrets need not be pasted into the model conversation.

Before publishing, scan the exact Git index/history and packaged wheel/source archive. `.gitignore` alone is not a privacy review.
Do not “sanitize” a copy of a whole private infrastructure repository. Build a clean allowlisted source tree instead.
Review documentation, tests, artifacts, screenshots, metadata, commit author email and Git remote URLs as well as code.
Use the release build helper: ordinary source archives may contain the builder's filesystem account name/UID even when their file contents are clean.
Normalized archives remove that ownership metadata and private file times; the artifact audit checks for unexpected metadata too.
An issue template should request the allowlisted report, never full configurations or support-ticket links.

中文：不复制真实项目再做模糊替换；私有配置、截图和工单不进公开仓库。
默认不上传，公开报告按字段白名单生成；发布前审查实际文件、构建包和 Git 历史。
