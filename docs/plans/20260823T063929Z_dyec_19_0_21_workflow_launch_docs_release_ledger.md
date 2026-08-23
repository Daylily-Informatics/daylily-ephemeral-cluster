# DYEC 19.0.21 workflow-launch documentation release ledger

**Opened:** 2026-08-23T06:39:29Z  
**Release branch:** `codex/release-19.0.21-workflow-launch-docs-20260823`  
**Baseline:** annotated `19.0.20`, peeled commit `69e7a4cf101a19571be9c4367dde3b8f037dc21a`

## Objective

Publish documentation and CLI-help coverage for the DYEC 19.0.20 workflow
launch controls: public `--dry-run` adds `-n` to the effective command,
including a supplied `--dy-command`; public `--rerun-triggers` is repeatable
and must not duplicate a trigger embedded in that command. Cut the next
annotated DYEC release as `19.0.21`.

## Gate 0

| Item | Status | Evidence |
| --- | --- | --- |
| Private release worktree | complete | `/Users/jmajor/.codex-worktrees/dyec-release-19.0.21-workflow-launch-docs-20260823` |
| Exact baseline | complete | `19.0.20` annotated tag peels to `69e7a4cf101a19571be9c4367dde3b8f037dc21a` |
| Next tag availability | complete | `git ls-remote --tags origin 19.0.21` returned no tag before work began |
| Scope | complete | README, operator docs, agent guidance/help text, immutable catalog snapshot, and release ledger only |

## Release rows

| Row | Status | Evidence |
| --- | --- | --- |
| Explain direct workflow dry-run and rerun-trigger controls | complete | README, concise README, agent guide, quick start, and AGENTS describe the public option contract and same-root continuation |
| Update CLI help and compact agent guidance | complete | `dyec workflow launch --help` shows the enforced `-n` and duplicate-trigger guidance; `dyec agent guidance` reports the direct-launch rule |
| Advance immutable release snapshot and verify source/payload parity | complete | `CURRENT_DYEC_BUILD=19.0.21`; the source/payload `dyec_builds.19.0.21` snapshots match and preserve 19.0.20 |
| Verify candidate | complete | Release snapshot tests: 3 passed; `py_compile`, catalog source/payload `cmp -s`, `git diff --check`, and `dyec catalog list --dyec-version 19.0.21` passed |
| Commit, push, annotate, and verify `19.0.21` | pending | pending |

## Non-goals

This release does not launch, inspect, stop, or otherwise alter any headnode
controller, DayOA workflow, Slurm job, FSx root, DRA, S3 evidence, or cluster.
