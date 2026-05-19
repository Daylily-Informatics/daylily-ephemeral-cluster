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
- `daylily-ec headnode connect` must preserve interactive TUI/editor key chords, especially Emacs `Ctrl-S` and `Ctrl-X Ctrl-S`. Keep both layers of XON/XOFF protection: the remote ubuntu login shell must disable flow control, and the local `daylily_ec.aws.ssm.start_session` path must keep a local `/dev/tty` flow-control guard running while Session Manager owns the terminal. A one-time local `stty -ixon -ixoff` is not sufficient because the AWS Session Manager/plugin startup path can leave the live local TTY with flow control enabled again.
- Do not remove or bypass the `tests/test_ssm.py` guardrail coverage for the local flow-control guard. Regression evidence should include a real `daylily-ec headnode connect` session where `cat -v` receives bare `Ctrl-S` as `^S`; for editor validation, `emacs -Q` should enter `I-search` on `Ctrl-S` and write the file on `Ctrl-X Ctrl-S`.

# Local Environment

- Use the repo activation flow before running Daylily commands. If the `DAY-EC` Conda environment is not present or dependencies are missing, run `source ./activate` from the repo root to create/activate it, then use the `DAY-EC` environment for tests and CLI commands.

# Working Docs And Plan Ledgers

- Every repo should have a `docs/plans/` directory. Create it when it is missing.
- Store plans, ledger plans, execution ledgers, and AI working documents used to carry out repo work under `docs/plans/`.
- Treat these files as durable repo artifacts: check them in and preserve them with the repo unless the user explicitly asks to remove or archive one.
- Name plan and ledger files with a datetime in the filename, such as `YYYYMMDDTHHMMSSZ_<short_slug>_ledger.md` or `YYYYMMDD_<short_slug>.md`.
- Do not keep the authoritative plan or execution ledger only in chat, temporary directories, or agent-local scratch space.

# ParallelCluster CLI

- `pcluster` is not an `aws` CLI subcommand. Do not pass AWS CLI-only flags such as `--json` to `pcluster`; ParallelCluster commands emit JSON by default.

# Version Tags

- Daylily version tags should not use a leading `v`. When determining the next version, use non-`v` semver tags as the source of truth.
