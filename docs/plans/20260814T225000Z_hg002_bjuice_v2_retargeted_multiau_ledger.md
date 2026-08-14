# HG002 Bjuice v2 retargeted multi-AU execution ledger

Controlling request: repair measured-coverage heatmaps, derive a second seven-AU matrix from the completed HG002 run, launch the same hg38 HIOMR2 kitchen-sink mega plus analytical Inflection package, and export successful results to S3 without FSx deletion.

Ledger path: `docs/plans/20260814T225000Z_hg002_bjuice_v2_retargeted_multiau_ledger.md`

## Gate 0 baseline

- DYEC worktree: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-hg002-bjuice-v2-retargeted-18001`, branch `codex/hg002-bjuice-v2-retargeted-multiau-20260814`, based on annotated release `18.0.1` (`da72fb47`), clean before this ledger.
- DayOA pin: `15.0.1`; no DayOA source change is expected for this manifest-only retarget.
- Cluster contract: profile `lsmc`, region `us-west-2`, cluster `prod-cand-1703`, headnode user `ubuntu`.
- Completed source analysis: `prod-cand-1703-hg002-bjuice-v2-multiau-20260814T114522Z`; its original S3 export succeeded and FSx was preserved.
- Measured coverage evidence was read after a DYEC analysis visit from the source analysis's Mosdepth `chrom=total` rows.
- Retarget rule: per-AU ILMN fraction is `old_fraction * requested_ILMN_target / measured_ILMN_coverage`, decimal ROUND_DOWN to 12 places. ONT end hour is the nearest positive integer endpoint under the fitted cumulative model `C(t)=24.533083079*(1-exp(-0.026241832*t))`.
- No existing released catalog-generator option accepts an explicit retarget plan. A strict, file-supplied plan option is therefore required; manual manifest edits are prohibited.

## Control rows

| ID | Area | Requirement | Status | Category | Approval gate | Owner | Evidence | Root cause / terminal note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G0-001 | Evidence | Record source analysis root, release pins, coverage source, and retarget formula. | SUCCESS | plan_amendment | Gate 0 | orchestrator | This ledger baseline; source `analysis_units.tsv` and Mosdepth summaries read through DYEC headnode run. | Baseline recorded. |
| PLOT-001 | Report | Collapse equal measured-coverage coordinates into shared heatmap cells and add ONT yield-vs-hours plot. | SUCCESS | feature_implementation | Gate 0 | orchestrator | `/Users/jmajor/Downloads/generate_hg002_bjuice_downsample_matrix.py`; `/Users/jmajor/Downloads/generate_hg002_bjuice_hard_vcf_classes.py`; inspected PNGs. | Plot artifacts are outside repo by explicit user destination. |
| DYEC-001 | DYEC | Add strict seven-row retarget-plan manifest generation with explicit values and no EUID generation. | SUCCESS | feature_implementation | Gate 0 | orchestrator | `daylily_ec/bjuice_v2_hg002_multi_au_config.py`; `daylily_ec/cli.py`; `250 passed` focused DYEC suite. | The plan must exactly prove each round-down correction; nullable live EUID fields remain blank. |
| DYEC-002 | DYEC | Document the plan format and add focused contract coverage. | SUCCESS | contract_test | Gate 0 | orchestrator | `docs/cli_reference.md`; `tests/test_bjuice_v2_hg002_multi_au_config.py`; `tests/test_cli_registry_v2.py`; `250 passed in 27.00s`. | Help, successful retarget, and invalid fraction behavior covered. |
| REL-001 | Release | Commit, push, PR/merge, annotate/push the next DYEC patch release if DYEC source changes. | OPEN | active_product_contract | Gate 5 | orchestrator | GitHub PR/release evidence. | Required because a new DYEC generator behavior is needed for the live launch. |
| RUN-001 | Operations | Generate the seven manifests, dry-run exactly seven AU roots with zero Slurm jobs, and launch a fresh controller with the release pins. | OPEN | active_product_contract | Gate 5 | orchestrator | DYEC catalog outputs and workflow session status. | User authorized live launch; no FSx deletion authority exists. |
| RUN-002 | Operations | Monitor controller to terminal, export the successful new analysis root to a fresh S3 prefix using DYEC, and preserve FSx. | OPEN | active_product_contract | Gate 5 | orchestrator | DYEC workflow/export receipts. | Export waits for controller `rc=0`; FSx deletion is explicitly out of scope. |

## Retarget matrix

| AU | ILMN target (x) | Prior measured ILMN (x) | Prior fraction | New fraction | ONT target (x) | New `[0,end)` | Model-predicted ONT (x) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| p5xp5 | 0.5 | 8.54 | 0.011433798307 | 0.000669426130 | 0.5 | `[0,1)` | 0.635419 |
| 1x1 | 1 | 9.85 | 0.022867596615 | 0.002321583412 | 1 | `[0,2)` | 1.254381 |
| 3x3 | 3 | 11.93 | 0.068602789846 | 0.017251330221 | 3 | `[0,5)` | 3.016727 |
| 5x5 | 5 | 12.71 | 0.114337983077 | 0.044979537009 | 5 | `[0,9)` | 5.160747 |
| 10x5 | 10 | 13.65 | 0.228675966155 | 0.167528180333 | 5 | `[0,9)` | 5.160747 |
| 15x5 | 15 | 14.01 | 0.343013949233 | 0.367252622305 | 5 | `[0,9)` | 5.160747 |
| 15x10 | 15 | 13.65 | 0.343013949233 | 0.376938405750 | 10 | `[0,20)` | 10.018035 |

## Operational stop conditions

- Any catalog/dry-run contract failure: stop and record the exact DYEC error; do not substitute raw DayOA/Snakemake or hand-edited manifests.
- Controller terminal nonzero: inspect only via DYEC workflow logs/status and report exact fault before any repair/relaunch.
- Controller `rc=0`: record an export visit, use DYEC no-delete export to the fresh S3 prefix, verify task success, and preserve the source FSx tree.
- No FSx deletion, DRA destructive cleanup, or Slurm intervention is authorized.
