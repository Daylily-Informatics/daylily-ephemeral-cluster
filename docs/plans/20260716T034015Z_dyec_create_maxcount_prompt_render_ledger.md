# DYEC create MaxCount prompt and render repair ledger

Created: `2026-07-16T03:40:15Z`

## Objective

Make every public Intel `dyec create` max-count input control the corresponding
`Scheduling.SlurmQueues[].ComputeResources[].MaxCount` values. Remove hidden
subtype `1` precedence and prove the exact rendered Intel YAML before proposing
the refreshed branch to `main`.

## Gate 0 inventory

- Worktree: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-coverage-plus10-20260716`
- Branch: `codex/coverage-plus10-20260716`
- `origin/main` and branch HEAD were both
  `2329bccb6a443490cde3b11423623b3b1fc0ab56` after the requested refresh;
  there were no newer remote-main additions at inventory time.
- Preserved active checkout has 51 tracked and 75 untracked status entries and
  is outside this ledger's write scope.
- Current known-good evidence: exact-tag `10.3.18` request values 8/12 rendered
  20 Intel compute resources with `MaxCount` 8/12. The defect is conditional,
  not a universal substitution failure.
- Root-cause inventory:
  - fourteen subtype max-count config keys are labeled `PROMPTUSER` but create
    never prompts them;
  - any non-empty subtype `set_value`, commonly a generated stale `1`, wins
    over a newly supplied broad family count;
  - generated next-run configs persist derived subtype values as explicit
    `USESETVALUE` entries, preserving the hidden override;
  - active DRAGEN/RHEL F2 resources contain literal `MaxCount: 1`/`2`, and the
    active `sentieon-single` template contains five literal `MaxCount: 12`
    values; these are specialized fixed-topology contracts with no public
    max-count prompt and are not redefined by this Intel-family repair.
- No live cluster update, AWS mutation, Slurm intervention, budget change,
  release, or destructive action is authorized by this ledger.

## Control ledger

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| MAX-001 | Remote integration | Pull current `origin/main` into the clean branch before implementation and repeat before final tests. | SUCCESS | feature_implementation | Gate 0 | orchestrator | Initial and final fetches were no-ops at common `2329bccb6a443490cde3b11423623b3b1fc0ab56`; divergence `0/0`. |  | Final tests ran against current maintained main. |
| MAX-002 | Config resolution | Ensure user-supplied family values override hidden/stale subtype `1` values and stop generating hidden subtype overrides. | SUCCESS | config_or_startup_contract | Gate 1 | orchestrator | Fourteen private subtype keys removed from source/package create templates and required keys; resolver expands only the five public family inputs; next-run writer drops private keys; legacy configs receive one explicit ignored-key warning. | Hidden subtype values were never prompted but could override the public value. | The public family value is authoritative and legacy overrides are not ignored silently. |
| MAX-003 | Active templates | Prove every active Intel MaxCount remains an explicit create-time substitution and keep source/package trees identical. | SUCCESS | config_or_startup_contract | Gate 1 | orchestrator | Active Intel literal-quota regression and existing source/package parity contract. | Specialized DRAGEN/Sentieon limits were initially conflated with the Intel public-input defect. | Scope amended: specialized fixed topologies remain unchanged. |
| MAX-004 | Regression tests | Prove prompt/value precedence, next-run output, all selected Intel templates, and final rendered MaxCount values. | SUCCESS | contract_test | Gate 2 | orchestrator | `296 passed` focused suite plus dedicated interactive regression: stale subtype precedence, warning, exactly five public prompts, 8/9/12/19/38 answer propagation, next-run omission, active-template substitution-only contract, and unique rendered values across every supported Intel AZ. |  | Prompt- and render-level proof passed. |
| MAX-005 | Final verification | Rebase/merge latest remote additions, run focused/full/coverage/format/lint/diff checks, and propose normal PR. | IN_PROGRESS | contract_test | Gate 3 | orchestrator | Full suite and quality gates pass; normal commit/push/draft PR pending. |  |  |

## Final report

All rows terminal: `no`

Objective complete: `no`
