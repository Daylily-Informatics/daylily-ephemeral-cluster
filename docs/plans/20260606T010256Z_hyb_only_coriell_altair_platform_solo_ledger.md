# Hyb-Only Coriell/Altair Platform-Solo Kitchen-Sink Ledger

Created: 2026-06-06T01:02:56Z

## Control Paths

- Controlling ledger: `docs/plans/20260606T010256Z_hyb_only_coriell_altair_platform_solo_ledger.md`
- Evidence logs: `docs/plans/20260606T010256Z_hyb_only_coriell_altair_platform_solo_logs/`
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- Cluster: `hyb-only`
- AWS profile: `lsmc`
- Region: `us-west-2`

## Locked Decisions

- Treat `NA00023` as a typo for `NA00232`.
- Run platform-solo cohorts, not hybrid and not per-sample analyses.
- Analyze all staged samples: ONT four Coriells; ILMN four Coriells plus HG001-HG007 from the same ILMN run.
- Do not invoke raw `snakemake`; DayOA launch and recovery commands use `dy-r` through DYEC/headnode workflow helpers.
- Do not cancel, requeue, drain, resume, or otherwise intervene in Slurm jobs/nodes without explicit approval.
- Do not delete FSx analysis outputs after export unless explicitly approved.

## Gate 0 Baseline

Completed 2026-06-06T01:28Z. Evidence is recorded in `20260606T010256Z_hyb_only_coriell_altair_platform_solo_logs/`.

| Check | Evidence |
|---|---|
| DYEC repo | `gate0_dyec_git_status.txt`, `gate0_dyec_head.txt`, `gate0_dyec_remotes.txt`: clean `jem-dev`, HEAD `da6b44e97a5648b63319c5ffd36c662164557cd8`, origin `git@github.com:lsmc-bio/daylily-ephemeral-cluster.git`. |
| DayOA repo | `gate0_dayoa_git_status.txt`, `gate0_dayoa_head.txt`, `gate0_dayoa_remotes.txt`: clean `jem-dev`, HEAD `d02a1bd825c8c13bac3751d26854b9834c5c3a53`, origin `git@github.com:lsmc-bio/daylily-omics-analysis.git`. |
| AWS identity | `gate0_aws_identity.json`. |
| Cluster | `gate0_pcluster_describe_hyb_only.json`: `hyb-only` `CREATE_COMPLETE`, compute fleet `RUNNING`, headnode `i-05374380b57fad901`. |
| Headnode FSx/Slurm | `gate0_headnode_fsx_squeue.stdout.txt`: user `ubuntu`, `squeue` present, `/fsx` 8.8T available, queue empty. |
| Existing mounts | `gate0_mounts_list.json`: no existing DYEC mounts before this run. |
| Source inventory | `gate0_source_summary.tsv`, `gate0_source_objects.tsv`: ONT 4 samples total 277.36 GiB; ILMN requested files total about 1.83 TiB. |
| Space gate | PASS: planned staged bytes plus 20% headroom fit under `/fsx` available space. |

## Source Roots

### ONT

| Chip | S3 root |
|---|---|
| chip1 | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260522_ONT_4Coriells_chip1/20260522_ONT_4Coriells_chip1/20260522_2252_2B_PBM13545_f3392d36/` |
| chip2 | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260522_ONT_4Coriells_chip2/20260522_ONT_4Coriells_chip2/20260523_0038_1C_PBM14931_9bbdbb3f/` |
| chip3 | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260522_ONT_4Coriells_chip3/20260522_ONT_4Coriells_chip3/20260523_0038_1F_PBK89072_e28a4508/` |
| chip4 | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260522_ONT_4Coriells_chip4/20260522_ONT_4Coriells_chip4/20260523_0039_3E_PBM13048_8867cb21/` |

### ILMN

`s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/lh01121/2026/20260526_LH01121_0004_B23WW2NLT4/Analysis/1/Data/BCLConvert/fastq/`

## Control Ledger

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| GATE0-001 | Inventory | Record repo state, AWS identity, cluster/headnode state, Slurm queue, `/fsx` free space, current mounts, source byte counts. | SUCCESS | feature_implementation | Gate 0 | Orchestrator | `gate0_*`, `gate0_source_*`; `/fsx` 8.8T available; queue empty. |  | Baseline complete; source mounts may proceed. |
| SRC-001 | Mounts | Verify or create read-only mount for ONT chip1 source. | SUCCESS | feature_implementation | Gate 1 | Mount/Data Agent | `src001_mount_chip1.stdout.json`, `verify_ont_mount_paths.stdout.txt`, `mounts_status_20260606T0224Z.json`: `ont-4coriells-chip1` AVAILABLE. |  | Read-only DRA mount ready at `/fsx/run_dir_mounts/ont-4coriells-chip1/`. |
| SRC-002 | Mounts | Verify or create read-only mount for ONT chip2 source. | SUCCESS | feature_implementation | Gate 1 | Mount/Data Agent | `src002_mount_chip2.stdout.json`, `verify_ont_mount_paths.stdout.txt`, `mounts_status_20260606T0224Z.json`: `ont-4coriells-chip2` AVAILABLE. |  | Read-only DRA mount ready at `/fsx/run_dir_mounts/ont-4coriells-chip2/`. |
| SRC-003 | Mounts | Verify or create read-only mount for ONT chip3 source. | SUCCESS | feature_implementation | Gate 1 | Mount/Data Agent | `src003_mount_chip3.stdout.json`, `verify_ont_mount_paths.stdout.txt`, current mount list: `ont-4coriells-chip3` AVAILABLE. |  | Read-only DRA mount ready at `/fsx/run_dir_mounts/ont-4coriells-chip3/`. |
| SRC-004 | Mounts | Verify or create read-only mount for ONT chip4 source. | SUCCESS | feature_implementation | Gate 1 | Mount/Data Agent | `src004_mount_chip4.stdout.json`, `verify_ont_mount_paths.stdout.txt`, current mount list: `ont-4coriells-chip4` AVAILABLE. |  | Read-only DRA mount ready at `/fsx/run_dir_mounts/ont-4coriells-chip4/`. |
| SRC-005 | Mounts | Verify or create read-only mount for ILMN BCLConvert FASTQ source. | SUCCESS | feature_implementation | Gate 1 | Mount/Data Agent | `src005_mount_ilmn_fastq.stderr.txt`: initial waiter timed out while CREATING; `mounts_status_20260606T0250c.json`: lifecycle AVAILABLE; `verify_ilmn_mount_paths.stdout.txt`: headnode path exists with 100 FASTQs. | Large DRA metadata association exceeded the first long waiter but completed without retry. | Read-only DRA mount ready at `/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/`. |
| ONT-001 | ONT | Build `/fsx/scratch/ONT/NA00232_SMN_R1_all.fastq.gz` from barcode18 chip1, chip2, chip4. | SUCCESS | feature_implementation | Gate 2 | ONT Agent | `ont_stage_status_20260606T0256c.stdout.txt`: `DONE 2026-06-06T02:55:16Z NA00232 /fsx/scratch/ONT/NA00232_SMN_R1_all.fastq.gz 51444000878`; source manifest under `/fsx/scratch/ONT/manifests/NA00232.sources.tsv`. |  | Concatenation and `gzip -t` passed. |
| ONT-002 | ONT | Build `/fsx/scratch/ONT/NA09677_SMN_R1_all.fastq.gz` from barcode19 chip1, chip2, chip3, chip4. | IN_PROGRESS | feature_implementation | Gate 2 | ONT Agent | `headnode_stage_ont_data.sh`, `launch_ont_stage.stdout.txt`. |  | Covered by active ONT staging tmux after ONT-001. |
| ONT-003 | ONT | Build `/fsx/scratch/ONT/NA03986_DMPK_R1_all.fastq.gz` from barcode20 chip1, chip2, chip4. | IN_PROGRESS | feature_implementation | Gate 2 | ONT Agent | `headnode_stage_ont_data.sh`, `launch_ont_stage.stdout.txt`. |  | Covered by active ONT staging tmux after ONT-002. |
| ONT-004 | ONT | Build `/fsx/scratch/ONT/NA05164_DMPK_R1_all.fastq.gz` from barcode21 chip1, chip2, chip4. | IN_PROGRESS | feature_implementation | Gate 2 | ONT Agent | `headnode_stage_ont_data.sh`, `launch_ont_stage.stdout.txt`. |  | Covered by active ONT staging tmux after ONT-003. |
| ILMN-001 | ILMN | Stage Coriell ILMN FASTQs for NA00232, NA09677, NA03986, and NA05164 to `/fsx/scratch/ILMN/`. | IN_PROGRESS | feature_implementation | Gate 2 | ILMN Agent | `headnode_stage_ilmn_data.sh`, `launch_ilmn_stage.stdout.txt`; `install_ilmn_parallel_stage.stdout.txt`: serial staging replaced with `hybonly_stage_ilmn_parallel_20260606T010256Z`; `ilmn_parallel_stage_status_20260606T0311Z.stdout.txt`: parallel tmux active. | Serial ILMN staging was correct but too slow because it ran 50 large `gzip -t` checks one at a time. | Covered by active parallel ILMN staging tmux; no Slurm jobs/nodes touched. |
| ILMN-002 | ILMN | Stage HG001-HG007 Altair `{a,b,c}` R1/R2 FASTQs from the same ILMN run only to `/fsx/scratch/ILMN/`. | IN_PROGRESS | feature_implementation | Gate 2 | ILMN Agent | `headnode_stage_ilmn_data.sh`, `launch_ilmn_stage.stdout.txt`; `install_ilmn_parallel_stage.stdout.txt`: serial staging replaced with `hybonly_stage_ilmn_parallel_20260606T010256Z`; `ilmn_parallel_stage_status_20260606T0311Z.stdout.txt`: 4 parallel workers active. | Serial ILMN staging was correct but too slow because it ran 50 large `gzip -t` checks one at a time. | Covered by active parallel ILMN staging tmux; no Slurm jobs/nodes touched. |
| CFG-001 | Config | Generate ONT `analysis_samples.tsv`, `samples.tsv`, and `units.tsv` with pass-through `/fsx/scratch/ONT` paths only. | SUCCESS | contract_test | Gate 3 | Manifest Agent | `analysis_inputs/ont_analysis_samples.tsv`, `ont_samples_stage_precheck_retry.stdout.txt`, `ont_samples_stage_config_only.stdout.txt`, `generated_configs/ont/20260606T024346Z_1e7a4d91_{samples,units}.tsv`; path audit found 0 bad paths and ONT_R2_PATH=`na`. |  | Config-only generation passed after DYEC scratch/single-end ONT fixes. |
| CFG-002 | Config | Generate ILMN `analysis_samples.tsv`, `samples.tsv`, and `units.tsv` with pass-through `/fsx/scratch/ILMN` paths only. | SUCCESS | contract_test | Gate 3 | Manifest Agent | `analysis_inputs/ilmn_analysis_samples.tsv`, `ilmn_samples_stage_precheck.stdout.txt`, `ilmn_samples_stage_config_only.stdout.txt`, `generated_configs/ilmn/20260606T024346Z_bb867783_{samples,units}.tsv`; path audit found 0 bad paths. |  | Config-only generation passed for 25 ILMN units. |
| WF-001 | Workflow | ONT platform-solo dry-run succeeds with ONT SNV/alignstats, relatedness, VEP, global contamination, and MultiQC targets. | OPEN | contract_test | Gate 4 | Workflow Agent |  |  |  |
| WF-002 | Workflow | ONT platform-solo live workflow reaches terminal success. | OPEN | feature_implementation | Gate 4 | Workflow Agent |  |  |  |
| WF-003 | Workflow | ILMN platform-solo dry-run succeeds with catalog-equivalent kitchen-sink targets. | OPEN | contract_test | Gate 4 | Workflow Agent |  |  |  |
| WF-004 | Workflow | ILMN platform-solo live workflow reaches terminal success. | OPEN | feature_implementation | Gate 4 | Workflow Agent |  |  |  |
| EXP-001 | Export | Export successful ONT analysis results to `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/<analysis-id>/daylily-omics-analysis/`. | OPEN | feature_implementation | Gate 5 | Export Agent |  |  |  |
| EXP-002 | Export | Export successful ILMN analysis results to `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/<analysis-id>/daylily-omics-analysis/`. | OPEN | feature_implementation | Gate 5 | Export Agent |  |  |  |
| ACCEPT-001 | Acceptance | All rows terminal; staged FASTQs pass `gzip -t`; exports have object counts and byte counts. | OPEN | contract_test | Gate 5 | Orchestrator |  |  |  |

## Status Summary

| Status | Count |
|---|---:|
| OPEN | 7 |
| IN_PROGRESS | 5 |
| ATTEMPTING_BUGFIX | 0 |
| SUCCESS | 9 |
| BLOCKED | 0 |
| FAIL | 0 |
| NO_LONGER_NEEDED | 0 |
| DUPLICATE | 0 |

## Code Changes During Execution

| Time UTC | Repo | Change | Test Evidence |
|---|---|---|---|
| 2026-06-06T02:45Z | DYEC | Added strict `/fsx/scratch` pass-through support in `daylily_ec/stage_samples.py`; scratch paths are accepted as headnode-visible only when manifest rows use `STAGE_DIRECTIVE=pass_through`; non-pass-through scratch rows fail precheck. | `python -m pytest tests/test_stage_samples_from_local_to_headnode.py -q`: 49 passed before ONT extension, 51 passed after ONT extension. |
| 2026-06-06T02:48Z | DYEC | Added single-end ONT raw FASTQ support for pass-through manifests; generated units emit `ONT_R2_PATH=na`, matching DayOA's ONT FASTQ contract. | `python -m pytest tests/test_stage_samples_from_local_to_headnode.py -q`: 51 passed; `ont_samples_stage_precheck_retry.stdout.txt` passed. |
