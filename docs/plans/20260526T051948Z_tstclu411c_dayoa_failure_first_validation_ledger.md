# tstClu-4-1-1c DayOA Failure-First Validation Ledger

Generated: 2026-05-26T05:19:48Z

## Control

Controlling plan: user request in current thread, "tstClu-4-1-1c Failure-First DayOA Validation And Release Plan".

Ledger path: `docs/plans/20260526T051948Z_tstclu411c_dayoa_failure_first_validation_ledger.md`

Cluster config path: `docs/plans/20260526T051948Z_tstclu411c_cluster_config.yaml`

Report path: `docs/tstclu411c_command_catalog_test_results.md`

No teardown, DRA deletion, cleanup, or destructive AWS action is in scope. Live creation, workflow execution, tag pushes, and DRA export are in scope.

## Gate 0 Baseline

| Item | Evidence |
|---|---|
| DAY-EC workspace | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| DAY-EC branch | `codex/analysis-id-export-catalog-validation` |
| DAY-EC HEAD/tag | `012a3b5b30d2e69a07aa80dd4c224ad1ee26d3a4`, exact tag `4.1.3` |
| DAY-EC installed version | `daylily-ephemeral-cluster 4.1.3.dev0+g6531a5307.d20260523` |
| DAY-EC dirty state | Modified: `config/day_cluster/post_install_ubuntu_combined.sh`, `config/daylily_available_repositories.yaml`, `daylily_ec/repositories.py`, packaged payload mirrors, `tests/test_headnode_init.py`, `tests/test_repository_catalog.py`; untracked prior docs/plans/reports and `tmp/`. Treat as pre-existing and do not revert. |
| DayOA workspace | `/Users/jmajor/projects/daylily/daylily-omics-analysis` |
| DayOA branch | `main` |
| DayOA HEAD/tag | `87e3b7bfded86d4fd4b5882df02d788295b72d77`, exact tag `1.0.22` |
| DayOA dirty state | Modified `docs/plans/20260523T124908Z_hg003_hiomr_ont_1021_cluster_validation_ledger.md`; several untracked prior ledgers and `hg003_hybrid_complete.md`. Treat as pre-existing and do not revert. |
| Ursa workspace | `/Users/jmajor/projects/daylily/daylily-ursa` |
| Ursa branch/HEAD | `codex/run-directory-mounts-ursa`, `039d13928692067c2500cbf69f3ab77ccd9fd439` |
| Ursa dirty state | Modified application/config/test files already present, including `pyproject.toml` and `config/ecosystem-versions.json` targets. Treat as pre-existing and do not revert. |
| AWS identity | `aws sts get-caller-identity --profile lsmc` -> account `108782052779`, ARN `arn:aws:iam::108782052779:root` |
| Existing clusters | `AWS_PROFILE=lsmc pcluster list-clusters --region us-west-2` -> `fork-fixer` and `hyb-hg003` are `CREATE_COMPLETE`; `tstVer4-1-1b` absent. |
| Prior result source | `docs/tstver411b_command_catalog_test_results.md` |
| Prior failures | `roche_snv_alignstats`, `hybrid_ultima_ont_snv`, `illumina_run_qc`, `illumina_bclconvert`, `ont_run_qc`, `ultima_run_qc` |
| Prior blocked | `complete_genomics_mgi_snv_concordance` |
| Prior successes to rerun after fixes | `illumina_snv_alignstats`, `illumina_snv_alignstats_relatedness_vep_multiqc`, `ultima_snv_alignstats`, `ont_snv_alignstats`, `pacbio_snv_alignstats`, `hybrid_ilmn_ont_snv` |
| New cluster settings | `PROFILE=lsmc`, `REGION=us-west-2`, `REGION_AZ=us-west-2d`, `CLUSTER=tstClu-4-1-1c`, `fsx_fs_size=12000`, `headnode_instance_type=r7i.4xlarge`, `max_count_8I=1`, `max_count_128I=1`, `max_count_192I=1`, budget/heartbeat `johnm@lsmc.com`. |
| Execution entity | `ubuntu`; outputs must land under `/fsx/analysis_results/ubuntu`. |
| Space gate | Before each analysis batch, require `/fsx` free space at least `3 TiB` and usage no more than `85%`. |
| DRA export target | `s3://lsmc-ssf-sequencing-data/derived/tstClu-4-1-1c/analysis_results/ubuntu/` |
| SSM discipline | Use `daylily_ec.aws.ssm.run_shell`/helpers with simple script bodies; no nested quote-heavy ad hoc `aws ssm send-command`. |

## Status Counts

| Status | Count |
|---|---:|
| `OPEN` | 0 |
| `IN_PROGRESS` | 0 |
| `ATTEMPTING_BUGFIX` | 0 |
| `SUCCESS` | 6 |
| `FAIL` | 0 |
| `BLOCKED` | 0 |
| `NO_LONGER_NEEDED` | 0 |
| `DUPLICATE` | 0 |
| `WontDo` | 22 |

## Control Ledger

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| `G0-001` | Orchestration | Record repo state, dirty files, active tags/commits, prior results, AWS identity, cluster settings, and no-teardown boundary. | `SUCCESS` | `feature_implementation` | Gate 0 | Orchestrator | Gate 0 baseline above. |  | Baseline recorded before implementation. |
| `CFG-001` | Cluster | Render `tstClu-4-1-1c` config from `tstVer4-1-1b` params. | `SUCCESS` | `config_or_startup_contract` | Gate 1 | Cluster Agent | Config path created: `docs/plans/20260526T051948Z_tstclu411c_cluster_config.yaml`; cluster name `tstClu-4-1-1c`, FSx `12000`, headnode `r7i.4xlarge`, max counts `1/1/1`. |  | Config rendered. |
| `PRE-001` | Cluster | Run DAY-EC preflight for `tstClu-4-1-1c`. | `SUCCESS` | `feature_implementation` | Gate 1 | Cluster Agent | `dyec preflight --profile lsmc --region-az us-west-2d --config docs/plans/20260526T051948Z_tstclu411c_cluster_config.yaml --non-interactive` -> 12 checks OK; log `docs/plans/20260526T051948Z_tstclu411c_logs/preflight.log`. |  | Preflight passed. |
| `CREATE-001` | Cluster | Create cluster and monitor to usable state. | `SUCCESS` | `feature_implementation` | Gate 2 | Cluster Agent | `dyec create --profile lsmc --region-az us-west-2d --config docs/plans/20260526T051948Z_tstclu411c_cluster_config.yaml --non-interactive` -> cluster created in 37m31s; headnode configured; state written `/Users/jmajor/.config/daylily/state_tstClu-4-1-1c_20260526052144.json`; log `docs/plans/20260526T051948Z_tstclu411c_logs/create.log`. |  | Cluster and headnode configuration completed. |
| `BOOT-001` | Headnode | Verify ubuntu SSM, `/fsx`, DRA, `day-clone`, `dyec`, Slurm partitions, and empty queue. | `SUCCESS` | `feature_implementation` | Gate 2 | Headnode Agent | `headnode_probe.py` via `daylily_ec.aws.ssm.run_shell` -> user `ubuntu`, host `ip-10-0-0-213`, `/fsx` mounted, `day-clone`, `dyec`, `sbatch`, `squeue`, `sinfo` present, partitions `i8`, `i128`, `i192`, `i192mem`, `i192bigmem`; initial `dyec headnode jobs` empty. CloudFormation resources: FSx `fs-000b2a8e8c15aae8b`, headnode `i-0b8a4dc693725a666`, DRA `dra-03e636ae2e0c6b0d7`; DRA `/data/` -> `s3://lsmc-dayoa-omics-analysis-us-west-2/data/` `AVAILABLE`. Logs: `headnode_probe.log`, `headnode_jobs_initial.log`. |  | Boot and initial queue verified. |
| `SPACE-001` | Space | Verify `/fsx` free space before each analysis batch. | `SUCCESS` | `legitimate_safety_handling` | Every run gate | Space Agent | Initial `df -h /fsx`: size `11T`, used `107M`, available `11T`, use `1%`; threshold met. Recheck before failure-first dry-runs at `2026-05-26T06:26:47Z`: `/fsx` size `11T`, used `107M`, available `11T`, use `1%`; queue empty. Logs: `space_check_failure_first_01.log`. This row must be rechecked before each analysis batch in progress notes. |  | Initial and failure-first dry-run space gates passed. |
| `DATA-001` | Data | Build fresh `tstClu-4-1-1c` low-coverage sample/run contexts; do not reuse old stage dirs. | `WontDo` | `feature_implementation` | Gate 3 | Data Agent | Fresh input manifests copied under `docs/plans/20260526T051948Z_tstclu411c_inputs/`. Sample staging completed for `hybrid_ultima_ont_snv` to `/fsx/data/staged_sample_data/remote_stage_20260526T062121Z` and `roche_snv_alignstats` to `/fsx/data/staged_sample_data/remote_stage_20260526T062157Z`; generated local TSVs under `docs/plans/20260526T051948Z_tstclu411c_inputs/generated/`. DRAs now available: `/data/` `dra-03e636ae2e0c6b0d7`, Illumina `/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/` `dra-0d6c4bb354c08ffd8`, and ONT `/run_dir_mounts/20260513_ONT_HG003/` `dra-024eaa89ab141a664`. Logs: `failure_first_stage_sample_analysis.log`, `run_mounts_create.log`, `run_mounts_create_remaining.log`, `illumina_mount_bcl_inventory.log`. | Ultima run DRA still needs creation/verification. | Closed as `WontDo` by user direction; no additional data staging work will be pursued under this ledger. |
| `FIX-001` | DayOA | Fix DayOA bugs needed by failed/blocked rows and test from pushed ref. | `WontDo` | `feature_implementation` | Gate 4 | DayOA Agent | Pushed branch `origin/codex/tstclu411c-hybrid-env-python`; latest cluster-test commit `f91a021` (`Skip WGS token gates for BCL bootstrap rows`). Fixes include hybrid rule-env Python lookup, mounted ONT run-QC/demux rules, nf-core/bclconvert 4.0.3 SampleSheet runtime normalization, demux-only BCL MultiQC, explicit logs/benchmarks for new rules, and BCL bootstrap parsing gates. Local tests: `pytest tests/test_snakemake_parser_contracts.py -q` -> 5 passed; `pytest tests/test_bclconvert_multiqc.py tests/test_run_qc_reports.py` -> 11 passed; `bash tests/test_bclconvert_bootstrap.sh` -> 11 passed. | Cluster live validation still in progress. | Closed as `WontDo` by user direction; no further DayOA fix/validation work will be tracked here. |
| `FIX-002` | DAY-EC | Fix catalog/run-context wiring to pass explicit `samples_table` and `units_table` paths. | `WontDo` | `feature_implementation` | Gate 4 | DAY-EC Agent | Local edits applied to catalog source/payload and `daylily_ec/repositories.py`; command catalog now describes pinned nf-core/bclconvert 4.0.3 for Illumina BCLConvert commands and states FastQC is not run. `pytest tests/test_repository_catalog.py -q` -> 8 passed. Cluster run-context live validations still pending. |  | Closed as `WontDo` by user direction; no further live catalog validation will be tracked here. |
| `FAIL-FIRST-001` | Workflow | Run/fix `hybrid_ultima_ont_snv` using only `sentdhuomr`. | `WontDo` | `feature_implementation` | Gate 5 | Workflow Agent | Prior failure: `ModuleNotFoundError: No module named 'sentieon_cli'` in `sentdhuomr_hybrid_select`. Dry-run `tcc_hybrid_ultima_ont_snv_5x5x_fix_dryrun` completed `exit_code=0`; live `tcc_hybrid_ultima_ont_snv_5x5x_fix` is running from stage dir `/fsx/data/staged_sample_data/remote_stage_20260526T062121Z`. Latest queue evidence: `sentdhuomr_stage1` running on `i192mem-dy-all-1`, 192 CPUs, 300000M. | Original root cause was bare base `python` resolving outside the rule env; dry-run validated the pushed fix. | Closed as `WontDo` by user direction; no terminal workflow evidence is claimed. |
| `FAIL-FIRST-002` | Workflow | Run/fix `illumina_run_qc`. | `WontDo` | `feature_implementation` | Gate 5 | Workflow Agent | Prior failure: missing `config/units.tsv`. Superseded by combined mounted run target `produce_illumina_run_qc_and_bclconvert` so run QC and BCLConvert execute in the same `/fsx/analysis_results/ubuntu/<analysis-id>/` output tree. Dry-run `tcc_illumina_run_qc_bclconvert_dryrun_v6` completed `exit_code=0`; live `tcc_illumina_run_qc_bclconvert` launched after `/fsx` space check. | Previous root cause was incomplete run-context catalog wiring. | Closed as `WontDo` by user direction; no terminal workflow evidence is claimed. |
| `FAIL-FIRST-003` | Workflow | Run/fix `illumina_bclconvert`. | `WontDo` | `feature_implementation` | Gate 5 | Workflow Agent | Prior failure: `No read pairs specified for analysis unit 20260514_LH01106_0009_B23TVLGLT4`. Dry-runs v4/v5 exposed two bootstrap parser gates; v6 completed `exit_code=0` and schedules `run_bclconvert` with `docker://nfcore/bclconvert:4.0.3`, normalized SampleSheet, generated units, demux metrics, demux-only MultiQC, logs, and benchmarks. Live `tcc_illumina_run_qc_bclconvert` launched. | Root cause was BCL bootstrap being routed through generic WGS read/token validation before nf-core BCLConvert could create FASTQs. | Closed as `WontDo` by user direction; no terminal workflow evidence is claimed. |
| `FAIL-FIRST-004` | Workflow | Run/fix `ont_run_qc`. | `WontDo` | `feature_implementation` | Gate 5 | Workflow Agent | Prior failure: missing `config/units.tsv`. |  | Closed as `WontDo` by user direction; live workflow not pursued here. |
| `FAIL-FIRST-005` | Workflow | Run/fix `ultima_run_qc`. | `WontDo` | `feature_implementation` | Gate 5 | Workflow Agent | Prior failure: missing `config/units.tsv`. |  | Closed as `WontDo` by user direction; live workflow not pursued here. |
| `FAIL-FIRST-006` | Workflow | Run/fix `roche_snv_alignstats`. | `WontDo` | `feature_implementation` | Gate 5 | Workflow Agent | Prior failure: missing Singularity image `.simg`. |  | Closed as `WontDo` by user direction; live workflow not pursued here. |
| `FAIL-FIRST-007` | Workflow | Resolve/run or keep blocked `complete_genomics_mgi_snv_concordance` with exact mate-pair evidence. | `WontDo` | `blocked_external_dependency` | Gate 5 | Workflow Agent | S3 inventory under `s3://lsmc-dayoa-omics-analysis-us-west-2/data/genomic_data/organism_reads/H_sapiens/giab/MGI/mgi_reads/` contains only `ML150002521_L01_UDB-386_1.fq.gz` (`90,600,002,744` bytes), `ML150002521_L01_UDB-386_2.fq.gz` (`10,794,018,984` bytes), and `ML150002521_L01_UDB-388_2.fq.gz` (`97,844,317,264` bytes). Logs: `cg_mgi_s3_inventory.log`, `cg_mgi_head_objects.jsonl`. | Exact `_386` mate pair is not credible due to a ~8.4x R1/R2 size mismatch; `_388_2` has credible size but is not an exact mate and cannot be substituted. | Closed as `WontDo` by user direction; no substitute mate-pair source will be used under this ledger. |
| `DAYOA-REL-001` | Release | Commit DayOA fixes, push, tag next non-`v` patch version after `1.0.22`, push tag. | `WontDo` | `feature_implementation` | Gate 6 | Release Agent |  |  | Closed as `WontDo` by user direction. |
| `DAYEC-REL-001` | Release | Update all DAY-EC DayOA pins to new DayOA tag, commit, push, tag next DAY-EC version after `4.1.3`, push tag. | `WontDo` | `feature_implementation` | Gate 6 | Release Agent |  |  | Closed as `WontDo` by user direction. |
| `PIN-001` | Release | Update `daylily-ursa` DAY-EC dependency pin and DAY-EC local self/version config pin; commit, push, tag, push tags. | `WontDo` | `feature_implementation` | Gate 6 | Release Agent |  |  | Closed as `WontDo` by user direction. |
| `SUCCESS-RERUN-001` | Workflow | Rerun `illumina_snv_alignstats` after releases. | `WontDo` | `feature_implementation` | Gate 7 | Workflow Agent |  |  | Closed as `WontDo` by user direction. |
| `SUCCESS-RERUN-002` | Workflow | Rerun `illumina_snv_alignstats_relatedness_vep_multiqc` after releases. | `WontDo` | `feature_implementation` | Gate 7 | Workflow Agent |  |  | Closed as `WontDo` by user direction. |
| `SUCCESS-RERUN-003` | Workflow | Rerun `ultima_snv_alignstats` after releases. | `WontDo` | `feature_implementation` | Gate 7 | Workflow Agent |  |  | Closed as `WontDo` by user direction. |
| `SUCCESS-RERUN-004` | Workflow | Rerun `ont_snv_alignstats` after releases. | `WontDo` | `feature_implementation` | Gate 7 | Workflow Agent |  |  | Closed as `WontDo` by user direction. |
| `SUCCESS-RERUN-005` | Workflow | Rerun `pacbio_snv_alignstats` after releases. | `WontDo` | `feature_implementation` | Gate 7 | Workflow Agent |  |  | Closed as `WontDo` by user direction. |
| `SUCCESS-RERUN-006` | Workflow | Rerun `hybrid_ilmn_ont_snv` with `sentdhiomr` family targets only where available. | `WontDo` | `feature_implementation` | Gate 7 | Workflow Agent |  |  | Closed as `WontDo` by user direction. |
| `EXPORT-001` | DRA | Export `/fsx/analysis_results/ubuntu/**` to requested S3 prefix via DRA and verify. | `WontDo` | `feature_implementation` | Gate 8 | DRA Agent |  |  | Closed as `WontDo` by user direction; no export was performed. |
| `REPORT-001` | Report | Write final matrix report with commands, inputs, versions, outputs, fixes, and export evidence. | `WontDo` | `feature_implementation` | Gate 8 | Report Agent |  |  | Closed as `WontDo` by user direction. |
| `FINAL-001` | Orchestration | Terminalize all rows and report objective completion. | `WontDo` | `feature_implementation` | Gate 8 | Orchestrator | User-directed closure of all non-success rows as `WontDo`. | Validation objective was abandoned before all rows completed. | Closed as `WontDo`; ledger is terminal by closure, not by completed validation. |

## Progress Notes

- 2026-05-26T05:19:48Z: Gate 0 recorded. New cluster config rendered from the `tstVer4-1-1b` config with only cluster name changed to `tstClu-4-1-1c`.
- 2026-05-26T05:22:00Z: Preflight passed with 12 checks OK.
- 2026-05-26T06:02:00Z: Cluster creation completed; headnode configured; budgets and heartbeat configured.
- 2026-05-26T06:03:00Z: Boot probe passed. Headnode reports `dyec version` as `4.1.4`; local checkout reports `4.1.3.dev0+g6531a5307.d20260523`, so release provenance must keep local and headnode versions separate.
- 2026-05-26T06:12:00Z: Local DayOA and DAY-EC focused tests passed for hybrid Python lookup and run-context catalog rendering fixes.
- 2026-05-26T06:16:00Z: DayOA working branch `codex/tstclu411c-hybrid-env-python` pushed at commit `bc27487` for cluster testing.
- 2026-05-26T06:22:00Z: Sample staging completed for failure-first sample workflows. Stage dirs: hybrid Ultima+ONT `/fsx/data/staged_sample_data/remote_stage_20260526T062121Z`; Roche `/fsx/data/staged_sample_data/remote_stage_20260526T062157Z`.
- 2026-05-26T06:24:00Z: Run-directory mount creation timed out waiting for Illumina DRA `dra-0d6c4bb354c08ffd8`; direct FSx describe still shows lifecycle `CREATING` and no failure details.
- 2026-05-26T06:25:00Z: CG/MGI was blocked at this point: S3 contains no credible exact mate pair. Exact `_386` R1/R2 sizes differ by ~8.4x; `_388_2` is not an exact mate and is not acceptable as a substitution.
- 2026-05-26T06:27:00Z: `hybrid_ultima_ont_snv` dry-run launched from pushed DayOA branch `codex/tstclu411c-hybrid-env-python`; current status is running with `exit_code=null`.
- 2026-05-26T06:29:12Z: `hybrid_ultima_ont_snv` dry-run `tcc_hybrid_ultima_ont_snv_5x5x_fix_dryrun` completed with `exit_code=0`; live run `tcc_hybrid_ultima_ont_snv_5x5x_fix` launched at 2026-05-26T06:30:38Z.
- 2026-05-26T06:40:00Z: User amended ILMN/ONT run-analysis scope: use mounted LSMC sequencing directories for Illumina BCLs, add run-QC on ONT and ILMN run data at first mount, run Illumina demux/demux reports, run ONT demux MultiQC, and spell these out in the command catalog.
- 2026-05-26T06:45:00Z: Illumina mount inventory found raw BCL content and existing reports under `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/`: `5152` `.cbcl` files, `RunInfo.xml`, `SampleSheet.csv`, and BCLConvert report CSVs. Evidence: `illumina_mount_bcl_inventory.log`.
- 2026-05-26T06:58:00Z: DayOA branch pushed through commit `fd79835` with pinned nf-core/bclconvert 4.0.3 SampleSheet runtime normalization, demux-only BCL MultiQC, and logs/benchmarks for new BCL/run-QC rules.
- 2026-05-26T07:00:31Z: Illumina combined dry-run v4 failed before BCLConvert with `No read pairs specified for analysis unit 20260514_LH01106_0009_B23TVLGLT4`; DayOA commit `12f5347` then allowed explicit BCL bootstrap synthetic units to parse without pre-existing reads.
- 2026-05-26T07:02:32Z: Illumina combined dry-run v5 failed at the next generic WGS gate: `SQ/RU/EX/LANE may not contain '.' or '_'`; DayOA commit `f91a021` then exempted only the synthetic BCL bootstrap row from that legacy token gate.
- 2026-05-26T07:04:49Z: Illumina combined dry-run v6 completed with `exit_code=0`, scheduling mounted Illumina run QC, `run_bclconvert` with `docker://nfcore/bclconvert:4.0.3`, generated units, demux metrics, and demux-only MultiQC with benchmark files.
- 2026-05-26T07:06:00Z: DRA status check shows all current DRAs `AVAILABLE`: `/data/`, Illumina run mount, and ONT run mount.
- 2026-05-26T07:07:00Z: `/fsx` space gate before live ILMN BCLConvert: size `11T`, used `39G`, available `11T`, use `1%`; `/fsx/analysis_results/ubuntu` is `4.8G`. Live `tcc_illumina_run_qc_bclconvert` launched.
- 2026-05-26T11:34:43Z: User directed all non-success rows to be cleared as `WontDo`. This closes the ledger as terminal by intentional abandonment, not by completed validation; no cleanup, export, teardown, or additional live workflow action was performed by this ledger update.
