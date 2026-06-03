# Interactive Shell Defaults Ledger

Created: 2026-05-28T01:09:32Z

## Objective

Record and apply the user's standing preference that shell work defaults to interactive sessions, that AWS EC2/headnode work defaults to an interactive `bash` login shell as `ubuntu`, and that `root` is not used unless the user gives explicit permission for that work.

## Gate 0 Inventory

- Current repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`.
- Relevant instruction surfaces inspected before edits:
  - `/Users/jmajor/.agents/AGENTS.md`
  - `/Users/jmajor/.agents/AGENTS.md~`
  - `/Users/jmajor/.codex/AGENTS.md`
  - `/Users/jmajor/.codex/config.toml`
  - `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`
  - `/Users/jmajor/.codex/memory.md`
  - `/Users/jmajor/.codex/memories/aws-destructive-changes.md`
  - `/Users/jmajor/.codex/memories/fallback_and_legacy_and_migration_support_for_code_changes_DO_NOT_UNLESS_TOLD_TO_PLEASE.md`
  - `./AGENTS.md`
- Initial AGENTS inventory under searched user/project scopes: 266 files.
- Memory updates must be made through an ad-hoc note under `/Users/jmajor/.codex/memories/extensions/ad_hoc/notes/`; existing memory registry files are not edited directly.

## Control Rows

| Row | Scope | Status | Evidence | Terminal Note |
|---|---|---|---|---|
| 1 | Add durable shell defaults to persistent user-level AGENTS files. | SUCCESS | Updated `/Users/jmajor/.agents/AGENTS.md`, `/Users/jmajor/.codex/AGENTS.md`, and `/Users/jmajor/.augment/AGENTS.md` with the Shell Session Defaults block. | Complete. |
| 2 | Add durable shell defaults to repo/worktree AGENTS files in searched Daylily/LSMC/Codex scopes. | SUCCESS | Initial pass updated 266 AGENTS files under `~/.agents`, `~/.codex`, `/Users/jmajor/projects/daylily`, and `/Users/jmajor/projects/lsmc`; wider project pass updated 181 more; home-level pass updated 147 more. | Complete. |
| 3 | Add allowed ad-hoc memory update note. | SUCCESS | Created `/Users/jmajor/.codex/memories/extensions/ad_hoc/notes/20260528T010932Z-interactive-shell-defaults.md`. | Complete. |
| 4 | Verify key instruction files and count updated AGENTS surfaces. | SUCCESS | Home-level verification under `/Users/jmajor` excluding macOS/system cache roots found 594 AGENTS files and 0 missing the marker `For AWS EC2, ParallelCluster, and other remote Linux hosts`. Key user/repo files were spot-checked. | Complete. |
