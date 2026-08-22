# Slim 5x+5x Bjuice and HIOMR2 execution ledger

Created: `2026-08-17T06:43:28Z`

## Objective

Run two fresh, independent catalog-controlled HG002 slim-data analyses in
parallel on a verified idle live cluster, then no-delete export each successful
analysis root through DYEC's DRA path:

1. `inflection-bjuice-product-v0.2` — HIOMR2 slim kitchen-sink mega plus
   analytical Inflection packaging.
2. `hiomr2_slim_kitchensink_mega` — the same slim HIOMR2 kitchen-sink mega
   without an Inflection packaging target.

Both commands must use the activated DYEC current catalog and explicit DayOA
tag `15.0.11`, even if a historical catalog validation record references an
older DayOA tag. The catalog's exact receipt-bound fixture is
`hg002_bjuice_verified_5x5x_fastq` on `hg38`; its default numeric scope
`19-20` is retained because no `1-25` override was requested.

## Gate 0 baseline

- Local checkout: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` on
  `codex/dyec-18.0.22-dayoa-15.0.11`.
- Activated CLI: DYEC `18.0.22`; `dyec info` reports pinned DayOA `15.0.11`.
- Pre-existing user worktree state includes one modified ledger and untracked
  `TrusSV/`, cache receipts, plans, release notes, and temporary proof files.
  This execution will not modify, stage, remove, or assume ownership of them.
- Live inventory at `2026-08-17T06:43:28Z`: `pcand-18022` and
  `prod-cand-1703` both report `UPDATE_COMPLETE` in `us-west-2` under profile
  `lsmc`. Cluster and mount/controller readiness must be proven before either
  is selected.
- `prod-cand-1703` has an unrelated in-flight four-AU HIOMR2 controller. It is
  excluded unless a later inspection proves no collision and the user directs
  its use.
- Selected cluster: `pcand-18022`, headnode `i-07c38ac3548d7f4c4` as `ubuntu`.
  It reports zero controllers, zero tmux panes, and zero Slurm jobs; FSx is
  1% used with 12,016,301,824 KiB available. Its installed DYEC version is
  `18.0.22`, matching the local activated CLI, and `day-clone` is available.
- The exact three read-only fixture FASTQs are readable on the selected
  headnode at the packaged `/fsx/references/.../bjuice_preval_2026/HG002/`
  ILMN R1/R2 and ONT paths. No full-coverage substitute or input rewrite is
  authorized.
- Explicit launch accounting identity: project `pcand-18022`, cost center
  `pcand-18022-ccenter`; the cost center is active, allows `ubuntu`, and has a
  monthly cap of 1234 USD. No budget/cost-center mutation was made.
- Catalog launch is the controller authority: DYEC owns its persistent
  `ubuntu` tmux session, analysis-root visit/lock lifecycle, `dyoainit`,
  `dy-a slurm hg38`, and `dy-r` invocation. Raw `snakemake` is prohibited.
- No recurring monitor, scheduled task, Slurm intervention, budget mutation,
  cluster mutation, or source checkout modification is in scope.

## Export and cleanup boundary

The user authorized post-`rc=0` FSx-to-S3 export. Each export must first
record a `dyec analysis visit --mode export`, use a fresh explicit destination
prefix, retain FSx data, and verify `status=success`, `phase=complete`,
`task_lifecycle=SUCCEEDED`, `detached=true`, and expected S3 objects.

FSx deletion remains a separate destructive approval gate. The user later gave
an exact second approval for the HIOMR2 root only; the Bjuice root remains
retained pending its successful export and a separately scoped cleanup
approval.

## Control ledger

| ID | Requirement | Status | Category | Approval gate | Evidence / terminal note |
|---|---|---|---|---|---|
| G0-001 | Verify active cluster, exact slim fixture provenance, mounts, and no controller collision. | SUCCESS | legitimate_safety_handling | Gate 0 | `pcand-18022` is empty/current and all three packaged slim fixture FASTQs are readable as `ubuntu`; `prod-cand-1703` remains excluded as busy. |
| CAT-001 | Freeze exact pair, input profile, DayOA `15.0.11`, `hg38`, and no-Inflection distinction. | SUCCESS | active_product_contract | Gate 0 | `dyec --json catalog show` verified both command shapes. |
| CAT-002 | Add verified Bjuice and HIOMR2 result S3 URIs to the DYEC command catalog as concordance evidence. | SUCCESS | feature_implementation | Successful export receipts | Both records now point to their dedicated `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/.../DAY_final_multiqc_data/multiqc_giab_concordance.txt` objects: Bjuice `pcand18022-hg002-slim5x5x-bjuice-ifx-20260817t0648z` and no-Inflection HIOMR2 `pcand18022-hg002-slim5x5x-hiomr2-20260817t0648z`. Each record preserves the historical DayOA `15.0.11` context and states that it does not clear the current `15.0.12` validation-pending state. |
| DRY-001 | Render and run independent dry controllers in parallel; require attributable `rc=0` and zero Slurm submission for each. | SUCCESS | contract_test | Gate 1 | The initial parallel lanes failed only in concurrent DayOA-environment bootstrap; fresh Bjuice and no-Inflection HIOMR2 dry2 controllers each reached attributable `rc=0` with zero Slurm submissions. |
| ENV-001 | Establish the shared DayOA `15.0.11` environment through a fresh catalog-owned dry controller before concurrent workflow work. | SUCCESS | legitimate_safety_handling | Gate 1 | Bjuice dry2 created the `DAYOA` environment, established Mermaid readiness, and reached `rc=0` without manual cache deletion, source modification, or Slurm work. |
| LIVE-001 | Render and launch fresh live Bjuice controller only after its dry controller succeeds. | SUCCESS | feature_implementation | Gate 1 | Catalog v6 controller `pcand18022-hg002-slim5x5x-bjuice-ifx-20260817t0648z` reached attributable terminal `rc=0` with no failure marker; it retains the analytical Inflection package/batch binding. |
| LIVE-002 | Render and launch fresh live no-Inflection HIOMR2 controller only after its dry controller succeeds. | SUCCESS | feature_implementation | Gate 1 | Catalog v6 controller `pcand18022-hg002-slim5x5x-hiomr2-20260817t0648z` reached attributable terminal `rc=0` with no failure marker; it contains no package target or delivery-batch setting. |
| MON-001 | Monitor both attributed controllers until terminal status. | SUCCESS | legitimate_safety_handling | Gate 5 | Both controllers reached attributable `rc=0` with no failure marker. The user then stopped and deleted the task-owned 15-minute monitor; no Slurm intervention occurred. |
| EXP-001 | No-delete DRA export for each root that reaches attributable `rc=0`; verify receipt and objects. | SUCCESS | feature_implementation | One Bjuice retry explicitly authorized | HIOMR2 DRA `dra-099bf60af970a4503` task `task-07042d644f5dfb3fb` and the one authorized Bjuice-retry DRA `dra-065329a4fceb729fd` task `task-0a96f7581ba6ddc90` both reached `status=success`, `phase=complete`, `task_lifecycle=SUCCEEDED`, and `detached=true`, with `delete_data_in_file_system=false`. Both dedicated S3 prefixes and their 82,088-byte GIAB concordance objects were verified. The retained first Bjuice receipt documents the initial `dra-0288dfcfcdb10e7e0` FSx `HttpTimeoutException`; no additional retry occurred. |
| DEL-001 | Delete only the verified-export HIOMR2 FSx root after an exact second approval. | SUCCESS (observed) | destructive_operation | User second approval received | At `2026-08-17T09:10Z`, `/fsx/analysis_results/pcand-18022/pcand18022-hg002-slim5x5x-hiomr2-20260817t0648z` was confirmed absent while its dedicated S3 prefix still listed objects. The root disappeared after the delete visit/lock acquisition but before the guarded removal could execute; the failed guard invocation did not run `rm`, so the deletion cannot be attributed to this agent. |
| DEL-002 | Retain the Bjuice FSx root unless and until its retry export succeeds and the user gives a separate exact cleanup approval. | BLOCKED | destructive_operation | Bjuice export receipt plus user second approval | No Bjuice FSx deletion is authorized or attempted. |
| DOC-001 | Maintain the requested DYEC-versioned command runbook and commit/push only run-owned documentation. | IN_PROGRESS | historical_docs_only | Gate 5 | Dedicated record is `docs/runbooks/18.0.22/runbooka2.md`; final evidence and an explicit documentation-only commit/push remain pending. |

## Completion boundary

The objective is complete only when both controllers have attributable
successful terminal receipts and both no-delete exports have passed their
receipt and S3-object checks. The HIOMR2 local root is already absent with its
S3 delivery retained; the Bjuice root remains explicitly retained.
