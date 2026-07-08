# jul8itelx4 Intel Catalog Plus BJuice DYEC 10.0.118 Ledger

Created: 2026-07-08T14:20:32Z

Controlling request: run the DYEC 10.0.118 Intel command catalog on cluster
`jul8itelx4` in `us-west-2d`, using DayOA 10.0.70, 16 coordinated lanes,
`-j 300 -p -k`, all prod `daywgs` commands plus BJuice, then export verified
successful analysis directories and clean them from FSx.

## Control Paths

- Work root: `/Users/jmajor/projects/lsmc`
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- Ledger path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260708T142032Z_intel_catalog_bjuice_jul8itelx4_dyec_10_0_118_ledger.md`
- Runbook path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/PR_runbook_dyec_10.0.118.md`
- Command plan JSON: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260708T142032Z_intel_catalog_bjuice_selected_commands.json`
- Command plan TSV: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260708T142032Z_intel_catalog_bjuice_selected_commands.tsv`
- Evidence root: `s3://lsmc-ssf-sequencing-data/derived/jul8itelx4/command_catalog_results/10.0.70-20260708T142032Z/`

## Gate 0 Baseline

- Required instruction files read:
  - `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`
  - `/Users/jmajor/.codex/AGENTS-HOW-TO-RUN-DAYOA.md`
  - `/Users/jmajor/.agents/AGENTS.md`
  - `/Users/jmajor/.agents/AGENTS-HOW-TO-RUN-DAYOA.md`
  - `/Users/jmajor/.codex/AGENTS.md`
  - `/Users/jmajor/projects/lsmc/AGENTS.md`
  - `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/AGENTS.md`
  - `/Users/jmajor/projects/lsmc/daylily-omics-analysis/AGENTS.md`
- AWS profile/account: `AWS_PROFILE=lsmc`, `aws sts get-caller-identity -> 108782052779`.
- DYEC version: `dyec version -> Daylily Ephemeral Cluster 10.0.118`.
- DYEC checkout: `3621b79b6b75625d209d840256f94cdce387e991`, `jem-dev`, tag `10.0.118`, tracking `origin/jem-dev`.
- DayOA checkout: `e2d7793f6faf8d30524548ac693bf66c82e723e4`, `jem-dev`, tags `10.0.70` and `10.0.69`, tracking `origin/jem-dev`.
- DYEC dirty baseline: existing untracked prior ledger `docs/plans/20260708T140150Z_dyec_10_0_118_headnode_update_ledger.md`; new run artifacts are owned by this ledger.
- DayOA dirty baseline: clean.
- Catalog pin check: source and packaged payload catalog pin DayOA `10.0.70`; selected command tags are exactly `10.0.70`.
- Cluster check: `pcluster describe-cluster --cluster-name jul8itelx4 --region us-west-2` with profile `lsmc` reported `clusterStatus=CREATE_COMPLETE`, `computeFleetStatus=RUNNING`, headnode `i-02946c880916d6dbc`, `r7i.4xlarge`, public IP `44.229.238.123`.
- Cluster support files present:
  - `/Users/jmajor/.config/daylily/jul8itelx4_cluster_20260708114632.yaml`
  - `/Users/jmajor/.config/daylily/jul8itelx4_cluster_20260708114632.yaml.init`
  - `/Users/jmajor/.config/daylily/jul8itelx4_next_run_20260708114632.yaml`
  - `/Users/jmajor/.config/daylily/state_jul8itelx4_20260708114632.json`
  - `/Users/jmajor/.config/daylily/preflight_jul8itelx4_20260708114632.json`
  - `/Users/jmajor/.config/daylily/jul8itelx4_spot_price_summary_20260708114632.json`

## Status Legend

- `OPEN`: not started
- `IN_PROGRESS`: active
- `ATTEMPTING_BUGFIX`: concrete repair underway after a failed attempt
- `SUCCESS`: completed and verified
- `FAIL`: bugfix attempted but not completed
- `BLOCKED`: waiting on approval, credential, live system, or external state

## Execution Ledger

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| GATE-000 | Inventory | Gate 0 baseline captured before live launch | SUCCESS | plan_amendment | Gate 0 | Agent 00 | Baseline section above; command plan JSON/TSV generated with 15 rows |  | Gate 0 complete |
| GATE-001 | Headnode | Refresh `jul8itelx4` headnode from DYEC 10.0.118 and verify DayOA 10.0.70 catalog | OPEN | config_or_startup_contract | Gate 0 | Agent 00 |  |  |  |
| GATE-002 | FSx/Slurm | Record initial `df -h /fsx`, Slurm queue, tool presence, and headnode catalog state | OPEN | contract_test | Gate 0 | Agent 00 |  |  |  |
| MOUNT-001 | Run mounts | Resolve or create Illumina run DRA for `illumina_run_qc` without blocking sample-analysis launch | SUCCESS | feature_implementation | Gate 1 | Agent 13 | mount_id=`20260514_LH01106_0009_B23TVLGLT4`, association=`dra-0e31c89df77176d37`, lifecycle=`AVAILABLE`; `dyec mounts verify --platform ILMN -> Mount verified` |  | ILMN run mount available and verified |
| MOUNT-002 | Run mounts | Resolve or create ONT run DRA for `ont_run_qc` without blocking sample-analysis launch | SUCCESS | feature_implementation | Gate 1 | Agent 14 | mount_id=`20260513_ONT_HG003`, association=`dra-0a60db320f05c1eb1`, lifecycle=`AVAILABLE`; `dyec mounts verify --platform ONT -> Mount verified` |  | ONT run mount available and verified |
| MOUNT-003 | Run mounts | Resolve or create Ultima run DRA for `ultima_run_qc` without blocking sample-analysis launch | SUCCESS | feature_implementation | Gate 1 | Agent 15 | mount_id=`602221-20260417_2346`, association=`dra-03ebcc27fecb99c6f`, lifecycle=`AVAILABLE`; `dyec mounts verify --platform ULTIMA -> Mount verified` |  | ULTIMA run mount available and verified |
| CMD-001 | Sample command | Launch, monitor, export, verify, and cleanup `illumina_snv_alignstats` | OPEN | feature_implementation | Gate 2 | Agent 01 | analysis_id=`ccv_live_illumina_snv_alignstats_20260708T142032Z` |  |  |
| CMD-002 | Sample command | Launch, monitor, export, verify, and cleanup `illumina_snv_alignstats_relatedness_vep_multiqc` | OPEN | feature_implementation | Gate 2 | Agent 02 | analysis_id=`ccv_live_illumina_snv_alignstats_relatedness_vep_multiqc_20260708T142032Z` |  |  |
| CMD-003 | Sample command | Launch, monitor, export, verify, and cleanup `illumina_hg002_kitchensink_multiqc` | OPEN | feature_implementation | Gate 2 | Agent 03 | analysis_id=`ccv_live_illumina_hg002_kitchensink_multiqc_20260708T142032Z` |  |  |
| CMD-004 | Sample command | Launch, monitor, export, verify, and cleanup `ultima_snv_alignstats` | OPEN | feature_implementation | Gate 2 | Agent 04 | analysis_id=`ccv_live_ultima_snv_alignstats_20260708T142032Z` |  |  |
| CMD-005 | Sample command | Launch, monitor, export, verify, and cleanup `ultima_snv_alignstats_kitchensink` | OPEN | feature_implementation | Gate 2 | Agent 05 | analysis_id=`ccv_live_ultima_snv_alignstats_kitchensink_20260708T142032Z` |  |  |
| CMD-006 | Sample command | Launch, monitor, export, verify, and cleanup `ont_snv_alignstats` | OPEN | feature_implementation | Gate 2 | Agent 06 | analysis_id=`ccv_live_ont_snv_alignstats_20260708T142032Z` |  |  |
| CMD-007 | Sample command | Launch, monitor, export, verify, and cleanup `ont_snv_alignstats_kitchensink` | OPEN | feature_implementation | Gate 2 | Agent 07 | analysis_id=`ccv_live_ont_snv_alignstats_kitchensink_20260708T142032Z` |  |  |
| CMD-008 | Sample command | Launch, monitor, export, verify, and cleanup `pacbio_snv_alignstats` | OPEN | feature_implementation | Gate 2 | Agent 08 | analysis_id=`ccv_live_pacbio_snv_alignstats_20260708T142032Z` |  |  |
| CMD-009 | Sample command | Launch, monitor, export, verify, and cleanup `roche_snv_alignstats` | OPEN | feature_implementation | Gate 2 | Agent 09 | analysis_id=`ccv_live_roche_snv_alignstats_20260708T142032Z` |  |  |
| CMD-010 | Sample command | Launch, monitor, export, verify, and cleanup `hybrid_ilmn_ont_snv` | OPEN | feature_implementation | Gate 2 | Agent 10 | analysis_id=`ccv_live_hybrid_ilmn_ont_snv_20260708T142032Z` |  |  |
| CMD-011 | Sample command | Launch, monitor, export, verify, and cleanup `hybrid_ilmn_ont_snv_kitchensink` | OPEN | feature_implementation | Gate 2 | Agent 11 | analysis_id=`ccv_live_hybrid_ilmn_ont_snv_kitchensink_20260708T142032Z` |  |  |
| CMD-012 | BJuice command | Launch, monitor, export, verify, and cleanup `inflection-bjuice-product-v0.1` | OPEN | feature_implementation | Gate 2 | Agent 12 | analysis_id=`ccv_live_inflection_bjuice_product_v0_1_20260708T142032Z` |  |  |
| CMD-013 | Run-QC command | Launch, monitor, export, verify, and cleanup `illumina_run_qc` | IN_PROGRESS | feature_implementation | Gate 2 | Agent 13 | analysis_id=`ccv_live_illumina_run_qc_20260708T152112Z`; workflow `exit_code=0`, completed `2026-07-08T18:55:36Z`; summary.html/summary.tsv/done present |  | Workflow succeeded; export and cleanup still pending |
| CMD-014 | Run-QC command | Launch, monitor, export, verify, and cleanup `ont_run_qc` | IN_PROGRESS | feature_implementation | Gate 2 | Agent 14 | analysis_id=`ccv_live_ont_run_qc_20260708T152112Z`; workflow `exit_code=0`, completed `2026-07-08T17:18:52Z`; summary.html/summary.tsv/done present |  | Workflow succeeded; export and cleanup still pending |
| CMD-015 | Run-QC command | Launch, monitor, export, verify, and cleanup `ultima_run_qc` | IN_PROGRESS | feature_implementation | Gate 2 | Agent 15 | analysis_id=`ccv_live_ultima_run_qc_20260708T163200Z`; DayOA log `WORKFLOW SUCCESS`/`RETURN CODE: 0`; summary.html/summary.tsv/done present |  | Workflow succeeded; export and cleanup still pending |
| MON-001 | Monitoring | Poll `df -h /fsx`, Slurm queue, tmux status, workflow status files, and command logs during execution | OPEN | contract_test | Gate 3 | Agent 15 |  |  |  |
| EXP-001 | Export | Upload support bundle and successful analysis outputs to S3 with object and byte parity checks | OPEN | feature_implementation | Gate 4 | Agent 15 |  |  |  |
| CLEAN-001 | Cleanup | Cleanup only verified-successful FSx analysis directories through `dyec analysis guard` | OPEN | legitimate_safety_handling | Gate 4 | Agent 15 | Requires export parity per command; no unverified delete permitted |  |  |
| FINAL-001 | Acceptance | No ambiguous rows remain; final report separates success, fail, and blocked rows | OPEN | contract_test | Gate 5 | Agent 00 |  |  |  |

## Command Notes

- The selected commands were generated from the active DYEC catalog with:
  - condition `(type == "prod" and "daywgs" in compatible_cluster_types) or command_id == "inflection-bjuice-product-v0.1"`
  - normalized live command replacement `bin/day_run -> dy-r`
  - normalized execution flags `-j 300 -p -k -T 0`
- Run-QC DRAs must use explicit wait timeouts above 40 minutes if they need creation.
- Cleanup is per-analysis only after export object/byte parity is recorded.

## 2026-07-08T15:48Z DRA Mount Prep

- `dyec mounts list --profile lsmc --region us-west-2 --cluster jul8itelx4` returned `No mounts found`; no DRA mounts were already present or running before mount creation.
- Starting read-only run-directory DRAs in parallel with active sample-analysis jobs:
  - ILMN `20260514_LH01106_0009_B23TVLGLT4`: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0009_B23TVLGLT4/`
  - ONT `20260513_ONT_HG003`: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260513_ONT_HG003/`
  - ULTIMA `602221-20260417_2346`: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/RUN602221/2026/602221-20260417_2346/`
- Each mount create uses `--wait --timeout-seconds 3600` per run-mount SOP so DRA metadata import is not prematurely treated as failed.

## 2026-07-08T15:52Z DRA Mount Create Evidence

- Three local wait sessions are running in parallel for ILMN, ONT, and ULTIMA `dyec mounts create`.
- `dyec mounts list --profile lsmc --region us-west-2 --cluster jul8itelx4` reported:
  - ONT `20260513_ONT_HG003`: `dra-0a60db320f05c1eb1`, lifecycle `CREATING`, headnode path `/fsx/run_dir_mounts/20260513_ONT_HG003/`, created `2026-07-08T15:51:44Z`.
  - ILMN `20260514_LH01106_0009_B23TVLGLT4`: `dra-0e31c89df77176d37`, lifecycle `CREATING`, headnode path `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/`, created `2026-07-08T15:51:45Z`.
  - ULTIMA `602221-20260417_2346`: `dra-03ebcc27fecb99c6f`, lifecycle `CREATING`, headnode path `/fsx/run_dir_mounts/602221-20260417_2346/`, created `2026-07-08T15:51:44Z`.
- Slurm work is active in parallel; `dyec headnode jobs` showed running jobs including `pre_prep_ont_cram`, `relatedness_batch_somalier_relate`, `rtg_vcfeval_roi`, `calc_coverage_evenness`, and `relatedness_batch_somalier_extract`, with additional submitted jobs pending.
- Added run-QC support to `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260708T142032Z_jul8itelx4_catalog_ops.py`:
  - `prepare-run-contexts` writes `runs.tsv` only from `AVAILABLE` DRA records.
  - `launch-run-qc-commands` launches the three run-context catalog commands through `dyec workflow launch --run-context-file`.
  - `python -m py_compile docs/plans/20260708T142032Z_jul8itelx4_catalog_ops.py` passed.

## 2026-07-08T18:58Z DRA And Run-QC Status Refresh

- `dyec mounts list --profile lsmc --region us-west-2 --cluster jul8itelx4` reported all three run mounts `AVAILABLE`.
- `dyec mounts verify --mount-id 20260514_LH01106_0009_B23TVLGLT4 --platform ILMN --timeout-seconds 600` passed.
- Run-QC one-at-a-time release status:
  - `ultima_run_qc`: successful analysis `ccv_live_ultima_run_qc_20260708T163200Z`; output evidence present under `/fsx/analysis_results/ubuntu/ccv_live_ultima_run_qc_20260708T163200Z/daylily-omics-analysis/results/runs/602221-20260417_2346/run_qc/ultima/`.
  - `ont_run_qc`: successful analysis `ccv_live_ont_run_qc_20260708T152112Z`; `dyec workflow status` exit code `0`, completed `2026-07-08T17:18:52Z`; `summary.html`, `summary.tsv`, and `logs/ont_run_qc_report.done` present.
  - `illumina_run_qc`: successful analysis `ccv_live_illumina_run_qc_20260708T152112Z`; `dyec workflow status` exit code `0`, completed `2026-07-08T18:55:36Z`; `summary.html`, `summary.tsv`, and `logs/illumina_run_qc_report.done` present.
- FSx status from headnode: `/fsx` size `6.6T`, used `552G`, available `6.0T`, use `9%`.
- Export and cleanup for the three successful run-QC analysis roots remain pending; no FSx deletion was performed.
