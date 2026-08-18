# DYEC 18.0.47 documentation and agent CLI guidance release ledger

**Started:** 2026-08-18T16:07:25Z
**Release branch:** `codex/release-18.0.47-docs-agent-guidance`
**Baseline:** annotated DYEC `18.0.46` at `063b85e44b0bb8eb0c49cc381dafdb5457a40fc0`
**Preserved DayOA catalog pin:** `15.0.27`
**Scope:** documentation, release snapshot, and documentation-contract expectation only. No cloud, cluster, DayOA workflow, catalog-command, or infrastructure operation is in scope.

## Authority and release boundary

The user requested a documentation refresh that makes the DYEC CLI surface and
agent guidance obvious and comprehensive, followed by commit, push, annotated
tag, tag push, and a GitHub release. The user explicitly directed that no tests
be run for this documentation-only change.

The released `18.0.46` catalog remains the immutable baseline. `18.0.47` is a
new immutable catalog snapshot with identical command definitions and the same
DayOA `15.0.27` pin. No existing tag or catalog snapshot may be changed.

## Gate 0

| Row | Check | Evidence / result | State |
|---|---|---|---|
| G0.1 | Clean release worktree from `18.0.46` | `/Users/jmajor/.codex-worktrees/dyec-release-18.0.47-docs-agent-guidance`, branch created at `063b85e4` | COMPLETE |
| G0.2 | Correct remote release ceiling | Remote DYEC maximum was `18.0.46`; remote DayOA maximum was `15.0.27` | COMPLETE |
| G0.3 | New tag unused | `origin` had no `refs/tags/18.0.47` or peeled ref before release work | COMPLETE |
| G0.4 | User test instruction | No test command is authorized or run for this documentation-only release | COMPLETE |
| G0.5 | No operational side effect | No cluster, headnode, DRA, FSx, S3, DayOA controller, or Slurm mutation is authorized | COMPLETE |

## Documentation delivery rows

| Row | Deliverable | Acceptance evidence | State |
|---|---|---|---|
| D1 | Dedicated agent/operator CLI guide | `docs/agent_cli_guide.md` maps local setup, cluster/headnode inspection, catalog launch, DayOA tmux work, monitoring, export, and stop conditions | COMPLETE |
| D2 | Discoverable entry points | Root README, concise README, CLI reference, Quickest Start, Overview, Operations, and `AGENTS.md` link to or name the guide | COMPLETE |
| D3 | Correct launch/export contract | Docs state that controller auto-export options are rejected and export is a separate no-delete `analysis visit` + `dyec export` DRA sequence; export visit does not populate the empty destination prefix | COMPLETE |
| D4 | Correct DayOA agent contract | Docs state `dyec headnode connect`, interactive login tmux, separate `source dyoainit`, `dy-a`, `dy-r`, pinned-source immutability, and no raw Snakemake | COMPLETE |
| D5 | Current operator version | Current docs identify DYEC `18.0.47` and retain DayOA `15.0.27` | COMPLETE |
| D6 | Documentation contract expectation | `tests/test_cli_docs_contract.py` includes the new guide and expects `18.0.47`; it is edited but not executed by user direction | COMPLETE |

## Catalog and release rows

| Row | Deliverable | Acceptance evidence | State |
|---|---|---|---|
| R1 | Immutable catalog snapshot | `dyec_builds.18.0.47` is a byte-for-byte copy of `dyec_builds.current`; both resolve only `15.0.27` | COMPLETE |
| R2 | Source/package parity | Source and payload command-catalog bytes are identical | COMPLETE |
| R3 | Non-test static release review | `git diff --check` passed; source/package SHA-256 is `00bc22b7f0e195589f9c4bf35228734d2f406fc20a189ad13beff5f867391b10`; YAML parse confirms `18.0.47 == current`, 32 commands, pangenome command IDs present, and DayOA pin `15.0.27` | COMPLETE |
| R4 | Commit and branch push | Documentation release commit pushed to `origin/codex/release-18.0.47-docs-agent-guidance` | PENDING |
| R5 | Annotated tag and tag push | New immutable `18.0.47` tag created after commit and pushed without moving an existing tag | PENDING |
| R6 | GitHub release | Published GitHub release is attached to `18.0.47` | PENDING |
| R7 | Final ledger evidence | Post-release evidence commit pushed; tag remains attached to the clean release commit | PENDING |

## Explicit non-goals

- No unit, integration, CLI, catalog-render, or cloud tests are run.
- No existing tag, numeric catalog snapshot, validation evidence, or DayOA pin is rewritten.
- No DayOA source, environment YAML, workflow rule, controller, queue, DRA, FSx object, S3 result, or cluster state is changed.
- This release does not claim a workflow validation result; it is an operator-documentation release only.
