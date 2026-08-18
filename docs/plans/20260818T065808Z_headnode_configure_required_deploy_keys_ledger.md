# Headnode configure required deploy-key references ledger

UTC opened: 2026-08-18T06:58:08Z
Owner: Codex
Scope: make both existing GitHub deploy-key secret references mandatory for the DYEC `headnode configure` command family. No secret value is read, created, changed, or committed.

## Gate 0 — baseline

- Worktree: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-headnode-config-require-deploy-keys` on `codex/headnode-config-require-deploy-keys`, created clean from annotated DYEC `18.0.31` at `48a5be59544b675f2949ebe836326bf29f28774f`.
- The live `pre-rel-18025` reconfigure initially failed at the DYEC repository Git-sync step (`SSM 5472bf6f-2a0d-4230-abc9-e80a6d17f64d`, `rc=128`) when no key references were supplied. The supported retry with the already-provisioned DYEC and DayOA deploy-key secret references succeeded under DYEC `18.0.31`.
- Current CLI source exposes both `--dyec-deploy-key-secret-arn` and `--dayoa-deploy-key-secret-arn` as optional on `headnode configure` and `headnode configure-dragen`.
- Boundary: make CLI arguments required and fail before any SSM command if absent; preserve the internal workflow API for cluster-creation callers that already supply explicit key references. No live retry, no secret mutation, no raw SSM, and no Slurm action are part of this implementation.

## Tracked rows

| ID | Area | Requirement | Status | Category | Gate | Evidence / terminal note |
|---|---|---|---|---|---|---|
| G0 | Baseline | Record source, live failure/success evidence, and boundary | SUCCESS | plan_amendment | Gate 0 | Baseline above; branch/worktree is clean. |
| K1 | CLI contract | Require both deploy-key ARN flags for `headnode configure` and `headnode configure-dragen` | SUCCESS | config_or_startup_contract | Gate 2 | Both Typer commands require the DYEC and DayOA key references; blank values fail before target resolution or SSM. The maintained `daylily_cfg_headnode` entry point matches the same contract. |
| K2 | Tests | Reject missing flags before SSM; prove supplied flags are forwarded for both command variants | SUCCESS | contract_test | Gate 2 | 2026-08-18T07:03:22Z: focused CLI/script suite passed: 14 passed. It covers missing and blank references, both command variants, and exact forwarding of both reference/region pairs. |
| K3 | Docs | State the mandatory key references in CLI reference/help-facing documentation | SUCCESS | feature_implementation | Gate 2 | Updated current CLI reference, operations, monitoring, and DRAGEN operator documentation; `--help` marks both arguments `[required]`. |
| K4 | Verification | Run targeted help/contract tests and check formatting | SUCCESS | contract_test | Gate 5 | 2026-08-18T07:03:22Z: `dyec headnode configure --help` and `configure-dragen --help` show both required flags; docs/no-PEM suite passed: 8 passed; `git diff --check` clean. No raw Snakemake or live workflow run. |
| K5 | Delivery | Commit the complete ledger, source, docs, and tests on the feature branch | SUCCESS | feature_implementation | Gate 5 | This complete implementation is committed on the local feature branch. Push/release remains outside this request unless separately authorized. |

## Acceptance

- Both configured headnode command variants reject a missing DYEC or DayOA deploy-key reference at CLI parsing time, before headnode discovery or SSM.
- Help and current docs make both requirements clear.
- Direct internal cluster-creation workflow calls remain explicit and unchanged.
- All rows are terminal before handoff.
