# DYEC 10.0.65 Release Evidence Ledger

Date opened: 2026-06-19T20:35:09Z

## Control

Controlling request: export all current `/fsx/analysis_results/**` evidence from `tstpartition` to S3, prepare cleanup of exported FSx analysis results after verification, then finish the remaining DYEC command-catalog rows with at most two additional run-directory DRAs active at a time. Emit final PR evidence report at `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/dyec_release_evidence_10.0.65.md`.

Cluster: `tstpartition`

Region: `us-west-2`

AWS profile: `lsmc`

DYEC release under evidence: `10.0.65`

DayOA release under evidence: `10.0.35`

Evidence root: `/Users/jmajor/.config/daylily/dyec_10_0_53_release_evidence_20260619T203509Z/` for exports opened before the final self-pin; subsequent exports may use a `10.0.65` evidence root while preserving the same S3 destination pattern.

Hard boundaries:
- DayOA commands must run as `ubuntu` on the headnode inside persistent tmux/login shells with separate `source dyoainit`, `dy-a ...`, and `dy-r ...` commands. No raw `snakemake`.
- Run-directory validation may create at most two additional run DRAs at a time.
- `/fsx/analysis_results/**` deletion is destructive. The approved eight-directory slim cleanup is recorded below. Any further deletion requires a new exact path/count/byte set and a separate explicit cleanup approval in this thread.
- No S3 deletes are authorized.

## Release Train Adjustment

During run-directory catalog validation, DayOA `10.0.28` exposed a code bug in empty run-QC marker targets. The fix was released before continuing remaining evidence so subsequent catalog runs can use a real pinned release rather than a hidden headnode patch.

| Repo | Commit | Tag | Verification |
|---|---|---|---|
| `daylily-omics-analysis` | `facde18` | `10.0.29` | `pytest tests/test_run_qc_reports.py -q` -> `10 passed`; annotated tag verified with `git cat-file -t 10.0.29` -> `tag`; pushed to `origin/jem-dev` and `origin/10.0.29`. |
| `daylily-ephemeral-cluster` | `82854d42` | `10.0.50` | Pin surfaces updated to DayOA `10.0.29`; `pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py -q` -> `15 passed`; annotated tag verified with `git cat-file -t 10.0.50` -> `tag`; pushed to `origin/jem-dev` and `origin/10.0.50`. |
| `daylily-ephemeral-cluster` | `e772c99d` | `10.0.51` | DYEC self-pin updated to `10.0.50`; `pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py -q` -> `15 passed`; annotated tag verified with `git cat-file -t 10.0.51` -> `tag`; pushed to `origin/jem-dev` and `origin/10.0.51`. |
| `daylily-omics-analysis` | `fbae971` | `10.0.30` | BCL Slurm default changed to `shared_thread_odirect_output=false` after live `bcl-convert` DRAGEN watchdog failures with the previous `true` default. `pytest tests/test_bclconvert_multiqc.py -q` -> `13 passed`; `pytest tests/test_bclconvert_multiqc.py tests/test_run_qc_reports.py tests/test_multiqc_qc_targets.py -q` -> `51 passed`; `python -m pytest tests/test_dynamic_resource_helpers.py tests/test_slurm_caller_partitions.py tests/test_multiqc_qc_targets.py -q` -> `48 passed`; annotated tag verified with `git cat-file -t 10.0.30` -> `tag`; pushed to `origin/jem-dev` and `origin/10.0.30`. |
| `daylily-ephemeral-cluster` | `1f4e3868` | `10.0.52` | Pin surfaces updated to DayOA `10.0.30`; `pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py -q` -> `15 passed`; annotated tag verified with `git cat-file -t 10.0.52` -> `tag`; pushed to `origin/jem-dev` and `origin/10.0.52`. |
| `daylily-ephemeral-cluster` | `bb72436e` | `10.0.53` | DYEC self-pin updated to `10.0.52`; `pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py -q` -> `15 passed`; annotated tag verified with `git cat-file -t 10.0.53` -> `tag`; pushed to `origin/jem-dev` and `origin/10.0.53`. |
| `daylily-omics-analysis` | `f0c0d09` | `10.0.31` | BCL Convert scheduling moved to lane-level shards for the live Illumina run-directory catalog row; annotated tag verified and pushed. |
| `daylily-ephemeral-cluster` | `ddde7684` | `10.0.54` | Pin surfaces updated to DayOA `10.0.31`; focused DYEC catalog/pin tests passed before tag and push. |
| `daylily-ephemeral-cluster` | `fc39acb3` | `10.0.55` | DYEC self-pin updated to `10.0.54`; focused DYEC catalog/pin tests passed before tag and push. |
| `daylily-omics-analysis` | `cf8fed8` | `10.0.32` | BCL marker rules use local tmpdir to avoid cross-device scratch issues; annotated tag verified and pushed. |
| `daylily-ephemeral-cluster` | `11868a52` | `10.0.56` | Pin surfaces updated to DayOA `10.0.32`; focused DYEC catalog/pin tests passed before tag and push. |
| `daylily-ephemeral-cluster` | `0085f08e` | `10.0.57` | DYEC self-pin updated to `10.0.56`; focused DYEC catalog/pin tests passed before tag and push. |
| `daylily-omics-analysis` | `e9e584e` | `10.0.33` | BCL `fastq_list.csv` is rewritten after scratch copyback so downstream report-root paths match the final FSx output root; annotated tag verified and pushed. |
| `daylily-ephemeral-cluster` | `3bbaaf3e` | `10.0.58` | Pin surfaces updated to DayOA `10.0.33`; focused DYEC catalog/pin tests passed before tag and push. |
| `daylily-ephemeral-cluster` | `6b9030c7` | `10.0.59` | DYEC self-pin updated to `10.0.58`; focused DYEC catalog/pin tests passed before tag and push. |
| `daylily-omics-analysis` | `aa9af67` | `10.0.34` | BCL demux FastQC input symlinks now point correctly after moved output roots; annotated tag verified with `git cat-file -t 10.0.34` -> `tag`; pushed to `origin/jem-dev` and `origin/10.0.34`. |
| `daylily-ephemeral-cluster` | `272d89ce` | `10.0.60` | Pin surfaces updated to DayOA `10.0.34`; focused DYEC catalog/pin tests passed before tag and push. |
| `daylily-ephemeral-cluster` | `9b46aa67` | `10.0.61` | DYEC self-pin updated to `10.0.60`; focused DYEC catalog/pin tests passed before tag and push. |
| `daylily-ephemeral-cluster` | `774ade11` | `10.0.62` | Source-checkout version resolution fixed so local `daylily-ec --json version` reports the current checkout tag instead of stale installed metadata; `pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py tests/test_versioning.py -q` -> `22 passed`; annotated tag verified and pushed. |
| `daylily-ephemeral-cluster` | `4b336d41` | `10.0.63` | DYEC self-pin updated to `10.0.62`; local editable install then `daylily-ec --json version` -> `{"app":"Daylily Ephemeral Cluster","version":"10.0.63"}`; annotated tag verified and pushed. |
| `daylily-omics-analysis` | `01cf556` | `10.0.35` | ONT run-QC wrapper fixes for pycoQC read-only N50 arrays and nanoq stdin usage; `python -m pytest tests/test_run_qc_reports.py -q` -> `10 passed`; `python -m pytest tests/test_bclconvert_multiqc.py tests/test_run_qc_reports.py tests/test_multiqc_qc_targets.py -q` -> `54 passed`; `python -m pytest tests/test_dynamic_resource_helpers.py tests/test_slurm_caller_partitions.py tests/test_multiqc_qc_targets.py -q` -> `48 passed`; annotated tag verified and pushed. |
| `daylily-ephemeral-cluster` | `44cd4970` | `10.0.64` | Pin surfaces updated to DayOA `10.0.35`; `python -m pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py tests/test_versioning.py -q` -> `22 passed`; annotated tag verified with `git cat-file -t 10.0.64` -> `tag`; pushed to `origin/jem-dev` and `origin/10.0.64`. |
| `daylily-ephemeral-cluster` | `9f09d41e` | `10.0.65` | DYEC self-pin updated to `10.0.64`; `python -m pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py tests/test_versioning.py -q` -> `22 passed`; local editable install then `daylily-ec --json version` -> `{"app":"Daylily Ephemeral Cluster","version":"10.0.65"}`; annotated tag verified and pushed. |

The current DYEC release under evidence is therefore `10.0.65`, with DayOA command-catalog default/pinned refs at `10.0.35`.

## Gate 0 Baseline

- Instructions read: `/Users/jmajor/.codex/AGENTS-HOW-TO-RUN-DAYOA.md` and `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`.
- Local repo state at start:
  - `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`: `jem-dev...origin/jem-dev`, with pre-existing untracked AWS cost report docs.
  - `/Users/jmajor/projects/lsmc/daylily-omics-analysis`: `jem-dev...origin/jem-dev`, clean.
  - `/Users/jmajor/projects/lsmc`: `main...origin/main [behind 113]`, with pre-existing dirty/untracked workspace state. This task owns this ledger and the final DYEC evidence report.
- Cluster state: `tstpartition CREATE_COMPLETE`, public IP `16.144.178.120`.
- Queue baseline: `squeue -o '%i  %P  %C  %t  %N  %c  %T  %m  %M  %D  %j'` returned only the header on 2026-06-19T20:36Z.
- Workflow process baseline: `ps -fu ubuntu | awk '/dy-r|day_run|snakemake/ && !/awk/ {print}'` returned no active workflow processes.

## Current FSx Analysis Inventory

Read-only inventory from `tstpartition` as `ubuntu` on 2026-06-19T20:36Z. `df -h /fsx` showed `4.4T` size, `33G` used, `4.4T` available, `1%`.

| Path | Size | File Count |
|---|---:|---:|
| `/fsx/analysis_results/tstpartition/catalog_slim_cg_20260619_10028` | 596M | 1520 |
| `/fsx/analysis_results/tstpartition/catalog_slim_hybrid_20260619_10028` | 614M | 1526 |
| `/fsx/analysis_results/tstpartition/catalog_slim_ilmn_20260619_10028` | 598M | 1528 |
| `/fsx/analysis_results/tstpartition/catalog_slim_ont_20260619_10028` | 597M | 1523 |
| `/fsx/analysis_results/tstpartition/catalog_slim_pacbio_20260619_10028` | 596M | 1521 |
| `/fsx/analysis_results/tstpartition/catalog_slim_roche_20260619_10028` | 596M | 1521 |
| `/fsx/analysis_results/tstpartition/catalog_slim_ultima_20260619_10028` | 597M | 1525 |
| `/fsx/analysis_results/tstpartition/catalog_slim_utility_20260619_10028` | 597M | 1542 |

Current run mounts: none under `/fsx/run_dir_mounts`.

## Export Verification

All eight material analysis directories present at Gate 0 were exported serially on 2026-06-19 with `daylily-ec export --cluster tstpartition --region us-west-2 --profile lsmc`, using one temporary export DRA at a time. Each local receipt under `/Users/jmajor/.config/daylily/dyec_10_0_53_release_evidence_20260619T203509Z/exports/<analysis_id>/fsx_export.yaml` reported:

- `fsx_export.status: success`
- `fsx_export.phase: complete`
- `fsx_export.task_lifecycle: SUCCEEDED`
- `fsx_export.detached: true`
- `fsx_export.detach_lifecycle: DELETED`

Read-only FSx DRA verification after the export loop showed only `/references/` still attached:

| Association | Path | Lifecycle | S3 |
|---|---|---|---|
| `dra-0ffb27220d7fb2d63` | `/references/` | `AVAILABLE` | `s3://lsmc-dayoa-references-usw2` |

S3 verification used `AWS_PROFILE=lsmc aws s3api list-objects-v2` on each destination prefix:

| Analysis ID | Objects | Bytes | S3 Evidence URI |
|---|---:|---:|---|
| `catalog_slim_cg_20260619_10028` | 1786 | 590446901 | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_cg_20260619_10028/` |
| `catalog_slim_hybrid_20260619_10028` | 1799 | 608970129 | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_hybrid_20260619_10028/` |
| `catalog_slim_ilmn_20260619_10028` | 1812 | 591890671 | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_ilmn_20260619_10028/` |
| `catalog_slim_ont_20260619_10028` | 1792 | 591030651 | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_ont_20260619_10028/` |
| `catalog_slim_pacbio_20260619_10028` | 1790 | 590423422 | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_pacbio_20260619_10028/` |
| `catalog_slim_roche_20260619_10028` | 1790 | 590349524 | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_roche_20260619_10028/` |
| `catalog_slim_ultima_20260619_10028` | 1794 | 591042796 | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_ultima_20260619_10028/` |
| `catalog_slim_utility_20260619_10028` | 1809 | 591128030 | `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_slim_utility_20260619_10028/` |

## Post-Export Cleanup Approval Set

Read-only post-export inventory from `tstpartition` as `ubuntu` on 2026-06-19T21:13Z showed empty top-level placeholders `/fsx/analysis_results/cromwell_executions`, `/fsx/analysis_results/daylily`, and `/fsx/analysis_results/ubuntu` at `33K` and `0` files each. The material cleanup set pending explicit approval is:

| Path | Size | File Count |
|---|---:|---:|
| `/fsx/analysis_results/tstpartition/catalog_slim_cg_20260619_10028` | 596M | 1520 |
| `/fsx/analysis_results/tstpartition/catalog_slim_hybrid_20260619_10028` | 614M | 1526 |
| `/fsx/analysis_results/tstpartition/catalog_slim_ilmn_20260619_10028` | 599M | 1528 |
| `/fsx/analysis_results/tstpartition/catalog_slim_ont_20260619_10028` | 597M | 1523 |
| `/fsx/analysis_results/tstpartition/catalog_slim_pacbio_20260619_10028` | 596M | 1521 |
| `/fsx/analysis_results/tstpartition/catalog_slim_roche_20260619_10028` | 596M | 1521 |
| `/fsx/analysis_results/tstpartition/catalog_slim_ultima_20260619_10028` | 597M | 1525 |
| `/fsx/analysis_results/tstpartition/catalog_slim_utility_20260619_10028` | 597M | 1542 |

Aggregate material cleanup set: `4.7G`, `12207` files. Deletion remains blocked until the user gives a second explicit approval after reviewing this exact set.

## Cleanup Verification

User gave second explicit approval in-thread to delete exactly the eight material directories listed in the cleanup approval set. Cleanup ran on `tstpartition` as `ubuntu` on 2026-06-19T21:30:56Z with `rm -rf --` against only those eight paths and completed on 2026-06-19T21:31:05Z.

Post-delete verification:

- Each approved path returned `ABSENT`.
- `find /fsx/analysis_results -mindepth 1 -maxdepth 2 -type d -print | sort` returned only:
  - `/fsx/analysis_results/cromwell_executions`
  - `/fsx/analysis_results/daylily`
  - `/fsx/analysis_results/tstpartition`
  - `/fsx/analysis_results/ubuntu`
- `df -h /fsx` after deletion showed `4.4T` size, `33G` used, `4.4T` available, `1%`.

## Command Catalog Scope

Static catalog: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/config/daylily_pipeline_command_catalog.yaml`.

Total DayOA catalog commands: `21`.

Already validated without new mounts in the prior slim pass:
- `simple-test`
- `illumina_snv_alignstats`
- `illumina_snv_alignstats_relatedness_vep_multiqc`
- `illumina_hg002_kitchensink_multiqc`
- `illumina_pangenome_snv`
- `ultima_snv_alignstats`
- `ultima_snv_alignstats_kitchensink`
- `ultima_pangenome_snv`
- `ont_snv_alignstats`
- `ont_snv_alignstats_kitchensink`
- `pacbio_snv_alignstats`
- `roche_snv_alignstats`
- `hybrid_ilmn_ont_snv`
- `hybrid_ilmn_ont_snv_kitchensink`
- `inflection-bjuice-product-v0.1`
- `complete_genomics_mgi_snv_concordance`

Remaining command-catalog rows requiring run-directory DRAs:
- `illumina_run_qc` (`illumina_run_directory`)
- `illumina_bclconvert` (`bclconvert_0_mm`)
- `illumina_run_qc_bclconvert` (`bclconvert_0_mm`)
- `ont_run_qc` (`ont_run_directory`)
- `ultima_run_qc` (`ultima_run_directory`)

## Remaining Catalog Execution

### Illumina Run Directory Mount

Created the Illumina run-directory DRA for the three Illumina run-directory catalog rows:

| Field | Value |
|---|---|
| Mount ID | `20260514_LH01106_0009_B23TVLGLT4` |
| Association ID | `dra-0b4baef578b48f0a5` |
| Lifecycle | `AVAILABLE` |
| FSx path | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/` |
| Source S3 | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0009_B23TVLGLT4/` |
| Active additional run DRAs | `1` |

Readability probe confirmed `SampleSheet.csv`, `RunInfo.xml`, `RunParameters.xml`, and `Data/Intensities/BaseCalls/L001` through `L005` exist under the mounted path.

### Bugfix During Run-Mount Catalog Validation

`illumina_run_qc` initially generated the expected run-QC artifacts but returned `rc=1` in the top-level target. The failed local rule was `produce_illumina_run_qc`; its inputs existed, but it was an empty marker rule with `log:` and `benchmark:` directives and no `shell:` or `run:` body, so Snakemake could not complete the marker benchmark contract. The same empty-marker shape was present for the run-QC marker target family.

Local DayOA source patch:
- `workflow/rules/run_qc_reports.smk`: add explicit no-op shell bodies to the run-QC produce marker targets, creating `logs/benchmarks`, the rule log directory, and the empty marker log.
- `tests/test_run_qc_reports.py`: add a focused assertion that every run-QC produce marker has an executable shell action.

Validation:
- `pytest tests/test_run_qc_reports.py -q` -> `10 passed`.
- `pytest tests/test_run_qc_reports.py tests/test_rule_log_benchmark_contracts.py -q` -> `13 passed, 2 failed`; both failures are pre-existing unrelated `workflow/rules/gauchian.smk:73:produce_gauchian` log/benchmark contract violations.

The same rule-file patch was applied to the active headnode clone for `catalog_illumina_run_qc_20260619_10049`, then `dy-r --unlock` was run in the persistent tmux pane before retrying the catalog target. That hot-patched run passed and was exported as bugfix evidence, but the command-catalog disposition below uses the subsequent clean released-tag rerun from DayOA `10.0.29`.

### BCL Convert Watchdog Bugfix During Catalog Validation

`illumina_bclconvert` attempt `catalog_illumina_bclconvert_20260619_10051` was launched from DayOA `10.0.29` and failed in live Slurm shard jobs before producing any `bclconvert.done` markers. Multiple shard logs showed BCL Convert 4.0.3 entered conversion and then failed with DRAGEN watchdog diagnostics: `Hang detected - there has been no system activity for 600 seconds`, `No thread activity`, `No I/O activity`, followed by `WatchDogException` and exit `rc=134`. The command line in those logs used `--shared-thread-odirect-output true`.

To stop waste from `-k` continuing to schedule known-failing shards, the tmux controller was interrupted, orphaned Snakemake/day_run processes for only `catalog_illumina_bclconvert_20260619_10051` were killed, and only Slurm jobs whose `WorkDir` matched `/fsx/analysis_results/tstpartition/catalog_illumina_bclconvert_20260619_10051/daylily-omics-analysis` were canceled. Post-cancel verification showed an empty Slurm queue and no active `dy-r`/`day_run`/Snakemake processes.

Local DayOA source patch:
- `config/day_profiles/slurm/templates/rule_config.yaml`: change the Slurm BCL default `shared_thread_odirect_output` from `true` to `false`.
- `tests/test_bclconvert_multiqc.py`: update the profile-contract assertion to require the Slurm BCL default to remain `false`.

Validation:
- `pytest tests/test_bclconvert_multiqc.py -q` -> `13 passed`.
- `pytest tests/test_bclconvert_multiqc.py tests/test_run_qc_reports.py tests/test_multiqc_qc_targets.py -q` -> `51 passed`.
- `python -m pytest tests/test_dynamic_resource_helpers.py tests/test_slurm_caller_partitions.py tests/test_multiqc_qc_targets.py -q` -> `48 passed`.

The patch was released as DayOA `10.0.30`; DYEC `10.0.52` pins DayOA `10.0.30`, and final DYEC `10.0.53` self-pins `10.0.52`. Clean retry `catalog_illumina_bclconvert_20260619_10053` is running from DayOA `10.0.30`; both the active and template Slurm profile files show `shared_thread_odirect_output: false`, and submitted shard commands include the `false` argument in the BCL wrapper call.

### Command Results Added After Cleanup

| Command Catalog Row | Analysis ID | Command | Result | Evidence |
|---|---|---|---|---|
| `illumina_run_qc` | `catalog_illumina_run_qc_20260619_10051` | `AWS_REGION=us-west-2 dy-r produce_illumina_run_qc -p -j 5 -k --rerun-triggers mtime --config run_context_file=config/runs.tsv samples_table=config/samples.tsv units_table=config/units.tsv` | PASS, `rc=0`, DayOA tag `10.0.29` | `logs/benchmarks/produce_illumina_run_qc.bench.tsv` present at 230 bytes; `results/runs/20260514_LH01106_0009_B23TVLGLT4/run_qc/illumina/summary.html` present at 1.4K; `multiqc_report.html` present at 2.1M. Export receipt `/Users/jmajor/.config/daylily/dyec_10_0_53_release_evidence_20260619T203509Z/exports/catalog_illumina_run_qc_20260619_10051/fsx_export.yaml` reports `status=success`, `task_lifecycle=SUCCEEDED`, `detached=True`, `detach_lifecycle=DELETED`; S3 evidence `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_illumina_run_qc_20260619_10051/` has 1,869 objects and 593,196,094 bytes. |
| `ont_run_qc` | `catalog_ont_run_qc_20260620_10065` | `AWS_REGION=us-west-2 dy-r produce_ont_run_qc -p -j 5 -k --rerun-triggers mtime --config run_context_file=config/runs.tsv samples_table=config/samples.tsv units_table=config/units.tsv` | PASS, `rc=0`, DayOA tag `10.0.35` | `results/runs/20260513_ONT_HG003/run_qc/ont/summary.html`, `summary.tsv`, `multiqc_report.html`, `ont_demux_fastq.multiqc.html`, and `logs/benchmarks/produce_ont_run_qc.bench.tsv` verified present; FSx root `667M`, `2,324` files before export. Export receipt `/Users/jmajor/.config/daylily/dyec_10_0_65_release_evidence_20260619T203509Z/exports/catalog_ont_run_qc_20260620_10065/fsx_export.yaml` reports `status=success`, `task_lifecycle=SUCCEEDED`, `detached=True`, `detach_lifecycle=DELETED`; S3 evidence `s3://lsmc-ssf-sequencing-data/derived/tstpartition/tstpartition/catalog_ont_run_qc_20260620_10065/` has 2,666 objects and 651,316,855 bytes. |

## Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Baseline | Record repo state, cluster state, queue/process baseline, mounted-state baseline, destructive boundary, and evidence root. | SUCCESS | legitimate_safety_handling | Gate 0 | Codex | Sections above. |  | Completed before export or cleanup. |
| EXP-001 | Export | Export all current `/fsx/analysis_results/**` analysis directories to S3 with explicit FSx DRA export receipts. | SUCCESS | feature_implementation | Gate 1 | Codex | Export Verification table above and receipt files under `/Users/jmajor/.config/daylily/dyec_10_0_53_release_evidence_20260619T203509Z/exports/`. |  | All eight material Gate 0 directories exported to S3. |
| VER-001 | Export Verification | Verify export receipts, task status, S3 object/byte counts, and export DRA detach state for every current analysis directory. | SUCCESS | contract_test | Gate 2 | Codex | Export Verification table above. |  | All receipts terminal success; all prefixes nonempty; export DRAs detached. |
| DEL-001 | Cleanup | Delete exported `/fsx/analysis_results/**` only after the exact deletion set is restated and the user gives second explicit approval. | SUCCESS | destructive_operation | Gate 3 | User/Codex | Cleanup Verification section above. |  | User approved exact eight-path set; all eight paths deleted and verified absent. |
| MNT-001 | Run Mounts | Create and verify the minimal required run-directory DRAs, never more than two additional active run DRAs at a time. | OPEN | feature_implementation | Gate 4 | Codex | Catalog profiles above. |  |  |
| CAT-001 | Remaining Catalog | Run remaining run-mount command-catalog entries one at a time through `dy-r` only, in persistent headnode tmux/login shells. | OPEN | contract_test | Gate 5 | Codex | Pending cleanup approval and run mounts. |  |  |
| REP-001 | Final Report | Emit `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/dyec_release_evidence_10.0.65.md` with command dispositions and S3 evidence URIs. | OPEN | contract_test | Gate 5 | Codex | Pending Ultima catalog command and export. |  |  |
