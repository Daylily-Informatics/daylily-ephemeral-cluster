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
| `OPEN` | 20 |
| `IN_PROGRESS` | 2 |
| `ATTEMPTING_BUGFIX` | 0 |
| `SUCCESS` | 6 |
| `FAIL` | 0 |
| `BLOCKED` | 0 |
| `NO_LONGER_NEEDED` | 0 |
| `DUPLICATE` | 0 |

## Control Ledger

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| `G0-001` | Orchestration | Record repo state, dirty files, active tags/commits, prior results, AWS identity, cluster settings, and no-teardown boundary. | `SUCCESS` | `feature_implementation` | Gate 0 | Orchestrator | Gate 0 baseline above. |  | Baseline recorded before implementation. |
| `CFG-001` | Cluster | Render `tstClu-4-1-1c` config from `tstVer4-1-1b` params. | `SUCCESS` | `config_or_startup_contract` | Gate 1 | Cluster Agent | Config path created: `docs/plans/20260526T051948Z_tstclu411c_cluster_config.yaml`; cluster name `tstClu-4-1-1c`, FSx `12000`, headnode `r7i.4xlarge`, max counts `1/1/1`. |  | Config rendered. |
| `PRE-001` | Cluster | Run DAY-EC preflight for `tstClu-4-1-1c`. | `SUCCESS` | `feature_implementation` | Gate 1 | Cluster Agent | `dyec preflight --profile lsmc --region-az us-west-2d --config docs/plans/20260526T051948Z_tstclu411c_cluster_config.yaml --non-interactive` -> 12 checks OK; log `docs/plans/20260526T051948Z_tstclu411c_logs/preflight.log`. |  | Preflight passed. |
| `CREATE-001` | Cluster | Create cluster and monitor to usable state. | `SUCCESS` | `feature_implementation` | Gate 2 | Cluster Agent | `dyec create --profile lsmc --region-az us-west-2d --config docs/plans/20260526T051948Z_tstclu411c_cluster_config.yaml --non-interactive` -> cluster created in 37m31s; headnode configured; state written `/Users/jmajor/.config/daylily/state_tstClu-4-1-1c_20260526052144.json`; log `docs/plans/20260526T051948Z_tstclu411c_logs/create.log`. |  | Cluster and headnode configuration completed. |
| `BOOT-001` | Headnode | Verify ubuntu SSM, `/fsx`, DRA, `day-clone`, `dyec`, Slurm partitions, and empty queue. | `SUCCESS` | `feature_implementation` | Gate 2 | Headnode Agent | `headnode_probe.py` via `daylily_ec.aws.ssm.run_shell` -> user `ubuntu`, host `ip-10-0-0-213`, `/fsx` mounted, `day-clone`, `dyec`, `sbatch`, `squeue`, `sinfo` present, partitions `i8`, `i128`, `i192`, `i192mem`, `i192bigmem`; initial `dyec headnode jobs` empty. CloudFormation resources: FSx `fs-000b2a8e8c15aae8b`, headnode `i-0b8a4dc693725a666`, DRA `dra-03e636ae2e0c6b0d7`; DRA `/data/` -> `s3://lsmc-dayoa-omics-analysis-us-west-2/data/` `AVAILABLE`. Logs: `headnode_probe.log`, `headnode_jobs_initial.log`. |  | Boot and initial queue verified. |
| `SPACE-001` | Space | Verify `/fsx` free space before each analysis batch. | `SUCCESS` | `legitimate_safety_handling` | Every run gate | Space Agent | Initial `df -h /fsx`: size `11T`, used `107M`, available `11T`, use `1%`; threshold met. This row must be rechecked before each analysis batch in progress notes. |  | Initial space gate passed. |
| `DATA-001` | Data | Build fresh `tstClu-4-1-1c` low-coverage sample/run contexts; do not reuse old stage dirs. | `OPEN` | `feature_implementation` | Gate 3 | Data Agent |  |  |  |
| `FIX-001` | DayOA | Fix DayOA bugs needed by failed/blocked rows and test from pushed ref. | `IN_PROGRESS` | `feature_implementation` | Gate 4 | DayOA Agent | Local edits applied to active hybrid refactored rule files; `pytest tests/test_snakemake_parser_contracts.py -q` -> 5 passed; `rg` for active bare `python -c ... sentieon_cli.scripts` found no matches. Pushed branch `origin/codex/tstclu411c-hybrid-env-python`, commit `bc27487` (`Fix hybrid Sentieon CLI script resolution`). Cluster testing from pushed ref still pending. |  |  |
| `FIX-002` | DAY-EC | Fix catalog/run-context wiring to pass explicit `samples_table` and `units_table` paths. | `IN_PROGRESS` | `feature_implementation` | Gate 4 | DAY-EC Agent | Local edits applied to catalog source/payload and `daylily_ec/repositories.py`; `pytest tests/test_repository_catalog.py -q` -> 8 passed. Cluster run-context dry-runs still pending. |  |  |
| `FAIL-FIRST-001` | Workflow | Run/fix `hybrid_ultima_ont_snv` using only `sentdhuomr`. | `OPEN` | `feature_implementation` | Gate 5 | Workflow Agent | Prior failure: `ModuleNotFoundError: No module named 'sentieon_cli'` in `sentdhuomr_hybrid_select`. |  |  |
| `FAIL-FIRST-002` | Workflow | Run/fix `illumina_run_qc`. | `OPEN` | `feature_implementation` | Gate 5 | Workflow Agent | Prior failure: missing `config/units.tsv`. |  |  |
| `FAIL-FIRST-003` | Workflow | Run/fix `illumina_bclconvert`. | `OPEN` | `feature_implementation` | Gate 5 | Workflow Agent | Prior failure: `No read pairs specified for analysis unit 20260514_LH01106_0009_B23TVLGLT4`. |  |  |
| `FAIL-FIRST-004` | Workflow | Run/fix `ont_run_qc`. | `OPEN` | `feature_implementation` | Gate 5 | Workflow Agent | Prior failure: missing `config/units.tsv`. |  |  |
| `FAIL-FIRST-005` | Workflow | Run/fix `ultima_run_qc`. | `OPEN` | `feature_implementation` | Gate 5 | Workflow Agent | Prior failure: missing `config/units.tsv`. |  |  |
| `FAIL-FIRST-006` | Workflow | Run/fix `roche_snv_alignstats`. | `OPEN` | `feature_implementation` | Gate 5 | Workflow Agent | Prior failure: missing Singularity image `.simg`. |  |  |
| `FAIL-FIRST-007` | Workflow | Resolve/run or keep blocked `complete_genomics_mgi_snv_concordance` with exact mate-pair evidence. | `OPEN` | `feature_implementation` | Gate 5 | Workflow Agent | Prior blocker: candidate `_386_1` and `_386_2` sizes inconsistent. |  |  |
| `DAYOA-REL-001` | Release | Commit DayOA fixes, push, tag next non-`v` patch version after `1.0.22`, push tag. | `OPEN` | `feature_implementation` | Gate 6 | Release Agent |  |  |  |
| `DAYEC-REL-001` | Release | Update all DAY-EC DayOA pins to new DayOA tag, commit, push, tag next DAY-EC version after `4.1.3`, push tag. | `OPEN` | `feature_implementation` | Gate 6 | Release Agent |  |  |  |
| `PIN-001` | Release | Update `daylily-ursa` DAY-EC dependency pin and DAY-EC local self/version config pin; commit, push, tag, push tags. | `OPEN` | `feature_implementation` | Gate 6 | Release Agent |  |  |  |
| `SUCCESS-RERUN-001` | Workflow | Rerun `illumina_snv_alignstats` after releases. | `OPEN` | `feature_implementation` | Gate 7 | Workflow Agent |  |  |  |
| `SUCCESS-RERUN-002` | Workflow | Rerun `illumina_snv_alignstats_relatedness_vep_multiqc` after releases. | `OPEN` | `feature_implementation` | Gate 7 | Workflow Agent |  |  |  |
| `SUCCESS-RERUN-003` | Workflow | Rerun `ultima_snv_alignstats` after releases. | `OPEN` | `feature_implementation` | Gate 7 | Workflow Agent |  |  |  |
| `SUCCESS-RERUN-004` | Workflow | Rerun `ont_snv_alignstats` after releases. | `OPEN` | `feature_implementation` | Gate 7 | Workflow Agent |  |  |  |
| `SUCCESS-RERUN-005` | Workflow | Rerun `pacbio_snv_alignstats` after releases. | `OPEN` | `feature_implementation` | Gate 7 | Workflow Agent |  |  |  |
| `SUCCESS-RERUN-006` | Workflow | Rerun `hybrid_ilmn_ont_snv` with `sentdhiomr` family targets only where available. | `OPEN` | `feature_implementation` | Gate 7 | Workflow Agent |  |  |  |
| `EXPORT-001` | DRA | Export `/fsx/analysis_results/ubuntu/**` to requested S3 prefix via DRA and verify. | `OPEN` | `feature_implementation` | Gate 8 | DRA Agent |  |  |  |
| `REPORT-001` | Report | Write final matrix report with commands, inputs, versions, outputs, fixes, and export evidence. | `OPEN` | `feature_implementation` | Gate 8 | Report Agent |  |  |  |
| `FINAL-001` | Orchestration | Terminalize all rows and report objective completion. | `OPEN` | `feature_implementation` | Gate 8 | Orchestrator |  |  |  |

## Progress Notes

- 2026-05-26T05:19:48Z: Gate 0 recorded. New cluster config rendered from the `tstVer4-1-1b` config with only cluster name changed to `tstClu-4-1-1c`.
- 2026-05-26T05:22:00Z: Preflight passed with 12 checks OK.
- 2026-05-26T06:02:00Z: Cluster creation completed; headnode configured; budgets and heartbeat configured.
- 2026-05-26T06:03:00Z: Boot probe passed. Headnode reports `dyec version` as `4.1.4`; local checkout reports `4.1.3.dev0+g6531a5307.d20260523`, so release provenance must keep local and headnode versions separate.
- 2026-05-26T06:12:00Z: Local DayOA and DAY-EC focused tests passed for hybrid Python lookup and run-context catalog rendering fixes.
- 2026-05-26T06:16:00Z: DayOA working branch `codex/tstclu411c-hybrid-env-python` pushed at commit `bc27487` for cluster testing.
