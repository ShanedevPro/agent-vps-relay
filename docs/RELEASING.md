# Publishing / 发布

This project publishes an agent guide and optional helper tools. A paid VPS pilot or an exhaustive platform lab is not required to share the guide.

1. Review the user workflow, first-time setup, reference platform scope and recovery steps. Keep maintainer test commands outside user onboarding.
2. Confirm the repository owner, public visibility, version and authorization. Set matching repository, tag and raw-guide URLs.
3. Review the exact proposed files, Git index/history, commit/tag author metadata and release notes for private information.
   Use synthetic examples and a project identity for commit/tag metadata; never import private infrastructure history.
4. If distributing packages, build with `python tools/build_release.py` (setuptools68+), then run `python tools/privacy_audit.py --artifact dist`.
   The build removes source ownership/PAX/gzip metadata and normalizes wheel timestamps. Also check documentation links.
5. Push only the reviewed history, create the version tag and publish the release. Verify the public repository, tag, raw guide and any uploaded asset hashes.

Maintainers may run focused tests for code changes and keep [test records](VALIDATION.md) factual.
Broader platform labs and disposable-server experiments in [TESTING.md](TESTING.md) are optional follow-up work, not a publication gate.
Any paid experiment still needs cost approval; the working relay is never a destructive test environment.

Each user's actual setup still needs the workflow's connectivity checks, independent recovery before automated cutover,
and private SSH/console recovery before management restriction. Publishing a guide does not replace those local steps.

No release workflow publishes automatically. CI has no provider credentials or purchasing abilities.
Review official upstream release notes, identity, checksums and licensing before changing `versions.lock.json`; normal reruns preserve accepted versions and credentials.

中文：流程合理、入口清楚、发布内容与历史不含隐私后即可发布指南；不把付费试点或全平台实验作为发布前置条件。
每位用户真正配置时仍须检查自己的线路与恢复能力。构建包也要审查所有者、时间和元数据，发布后核实真实链接与版本。
