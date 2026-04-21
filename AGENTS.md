# Safety Preferences

- Do not execute destructive AWS resource changes unless the user gives a second explicit approval after being told the action is destructive.
- Do not answer interactive confirmation prompts for destructive AWS changes unless that second explicit approval has already been given in the current thread.
- Treat an initial request to "teardown", "destroy", "delete", or similar as permission to inspect, prepare, or dry-run only. Before any live destructive action, restate the exact effect and wait for a separate explicit confirmation.
- Always read `.md` and other instruction files in `~/.agents/*`, `~/.codex/*`, `./.agents`, `./.codex`, `./AGENTS.md`, and `./CLAUDE.md`.
- Unless the user explicitly asks for fallback behavior in the current thread, do not add, preserve, or rely on fallback behavior. Prefer direct fixes and hard failures over silent fallback paths.

# Headnode SSM Access

- All SSM interactive sessions and command payloads that interact with headnodes must run as `ubuntu` in a bash login shell.
- Do not use `root` for headnode work. The `ubuntu` user is in sudoers; use targeted `sudo` from `ubuntu` only when escalation is required.
- Interactive sessions must use `SSM-SessionManagerRunShell` configured with `runAsDefaultUser=ubuntu` and bash login-shell behavior.
- Command payloads must go through the central `daylily_ec.aws.ssm.run_shell` and `daylily_ec.aws.ssm.write_remote_text` helpers rather than ad hoc `aws ssm send-command` calls.

# ParallelCluster CLI

- `pcluster` is not an `aws` CLI subcommand. Do not pass AWS CLI-only flags such as `--json` to `pcluster`; ParallelCluster commands emit JSON by default.

# Version Tags

- Daylily version tags should not use a leading `v`. When determining the next version, use non-`v` semver tags as the source of truth.
