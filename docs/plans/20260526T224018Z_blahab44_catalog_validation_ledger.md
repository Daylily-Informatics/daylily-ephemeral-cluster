# blahab44 DayOA/DAY-EC Catalog Validation Ledger

Date opened: 2026-05-26T22:40:18Z

Controlling request: after a 30 minute wait, commit and push DayOA and DAY-EC checkins, create a new cluster named `blahab44` using those checkins, and run all DayOA command catalog commands.

Ledger path: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/plans/20260526T224018Z_blahab44_catalog_validation_ledger.md`

## Gate 0 Inventory

- Instructions read: `/Users/jmajor/.agents/AGENTS.md`, `/Users/jmajor/.codex/AGENTS.md`, `/Users/jmajor/.augment/AGENTS.md`, `/Users/jmajor/.augment/rules/*.md`, repo `AGENTS.md`, DayOA `AGENTS.md`, `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`, DayEC `README.md`, and DayOA `README.md`.
- DayEC repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`, branch `main`, HEAD `5966aabad77e76a65cbc7fd87b2770496f52100d`, remote `git@github.com:Daylily-Informatics/daylily-ephemeral-cluster.git`, fetched `origin/main`.
- DayEC dirty state at Gate 0: untracked `docs/plans/20260526T213400Z_jem_bucktst3_ilmn_0p1x_kitchensink/dryrun/`; this ledger is newly created by this run.
- DayOA repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`, branch `main`, HEAD `a6b4dd4918c9d2473bb52ec69f3aba12b7fb7f32`, tag `2.0.1`, remote `git@github.com:Daylily-Informatics/daylily-omics-analysis.git`, fetched `origin/main`.
- DayOA dirty state at Gate 0: modified runtime asset path files `config/day_profiles/local/templates/rule_config.yaml`, `config/day_profiles/slurm/templates/rule_config.yaml`, `config/supporting_files/b37_supporting_files.yaml`, `config/supporting_files/hg38_broad_supporting_files.yaml`, `config/supporting_files/hg38_supporting_files.yaml`, `docs/catalog_of_tools.md`, `docs/ops/multiqc_qc_targets.md`, `tests/test_giab_qc_contracts.py`, and `tests/test_tool_catalog_docs.py`.
- Activation evidence: `source ./activate` resolved `CONDA_DEFAULT_ENV=DAY-EC`, `dyec=/Users/jmajor/miniconda3/envs/DAY-EC/bin/dyec`, `dyec version -> Daylily Ephemeral Cluster 4.1.13.dev0+g46ef5f7a6.d20260526`.
- AWS identity evidence: `AWS_PROFILE=lsmc aws sts get-caller-identity --output json` returned account `108782052779`, ARN `arn:aws:iam::108782052779:root`.
- Existing cluster baseline: `AWS_PROFILE=lsmc pcluster list-clusters --region us-west-2` listed `jem-bucktst3` `CREATE_COMPLETE`, plus failed rollback stacks `jem-bucktst2` and `jem-bucktst1`; no `blahab44` existed at Gate 0.
- Catalog inventory: `config/daylily_available_repositories.yaml` contains 17 DayOA commands, all currently pinned to `git_tag: 2.0.1` and repository `default_ref: 2.0.1`.
- Baseline DayOA focused tests: `eval "$(conda shell.zsh hook)" && conda activate DAY-EC && python -m pytest -q tests/test_giab_qc_contracts.py tests/test_tool_catalog_docs.py tests/test_multiqc_qc_targets.py -> 44 passed`.
- Baseline DAY-EC focused tests: `source ./activate >/dev/null && python -m pytest tests/test_repository_catalog.py tests/test_cli_registry_v2.py tests/test_packaged_defaults.py tests/test_resources_extraction.py tests/test_workflow.py tests/test_run_mounts.py tests/test_stage_samples_from_local_to_headnode.py -q -> 234 passed`.
- Earlier command attempts corrected: `dyec --version` is invalid because version is a subcommand; `tests/test_config_packaging.py` and `tests/test_resource_parity.py` do not exist in this checkout.
- Non-destructive boundary: live cluster creation is authorized by the controlling request; no destructive AWS action is authorized in this thread.

## Planned Release Pins

- Next DayOA non-`v` semver tag selected from fetched tags: `2.0.2` because the highest fetched non-`v` semver tag is `2.0.1`.
- DAY-EC catalog must be updated from `2.0.1` to `2.0.2`; otherwise catalog-driven workflows would clone old DayOA tag `2.0.1` rather than the new DayOA checkin.
- Next DAY-EC non-`v` semver tag selected from fetched tags: `5.0.2` because the highest fetched non-`v` semver tag is `5.0.1`.
- DAY-EC source and packaged `daylily_cli_global.yaml` must point `git_ephemeral_cluster_repo_tag` at `5.0.2`; otherwise the headnode configure step would clone DAY-EC `5.0.1`.

## Post-Pin Validation

- DayOA published commit: `1b103c7c66a8f04d94c1feab7f8e591f5a3dd4b8`.
- DayOA published tag: `2.0.2`.
- DAY-EC source and packaged catalog parity: `cmp -s config/daylily_available_repositories.yaml daylily_ec/resources/payload/config/daylily_available_repositories.yaml -> catalog_parity_ok`.
- DAY-EC catalog readback: `dyec repositories commands --repository daylily-omics-analysis` shows repository `default_ref: "2.0.2"` and command `git_tag: "2.0.2"` for the catalog command profiles.
- DAY-EC focused tests after pinning: `234 passed`.
- No user-level `/Users/jmajor/.config/daylily/daylily_cli_global.yaml` was present, so cluster create will use the repo or packaged DAY-EC global config.

## Post-Create Evidence

- Pre-create target readback: `AWS_PROFILE=lsmc pcluster list-clusters --region us-west-2` showed no `blahab44`; `us-west-2d` was `available` with ZoneId `usw2-az4`.
- Preflight command: `dyec preflight --profile lsmc --region-az us-west-2d --config docs/plans/20260526T224018Z_blahab44_cluster_request.yaml --non-interactive` passed 12 checks.
- Create command: `dyec create --profile lsmc --region-az us-west-2d --config docs/plans/20260526T224018Z_blahab44_cluster_request.yaml --non-interactive`.
- Create result: `blahab44` completed in `21m 6s`; headnode configured; state written to `/Users/jmajor/.config/daylily/state_blahab44_20260526224612.json`.
- ParallelCluster readback: `clusterStatus=CREATE_COMPLETE`, `computeFleetStatus=RUNNING`, headnode `i-0bc04c4642b1c4b8d`, headnode type `r7i.2xlarge`, region `us-west-2`.
- Headnode readiness via `daylily_ec.aws.ssm.run_shell` as `ubuntu`: `/fsx` mounted with about `4.4T` available, `/fsx/references/runtime_assets` present, `/fsx/references/genomic_data/organism_reads_slim` present, `/fsx/runtime_assets` absent, `/fsx/data` absent, `day-clone` present, `dyec version -> Daylily Ephemeral Cluster 5.0.2`, partitions `i8`, `i128`, `i192`, `i192mem`, and `i192bigmem` present, and `squeue -h` empty.
- Catalog execution helper: `docs/plans/20260526T224018Z_blahab44_catalog_driver.py`; copied current one-DRA/reference-slim manifests into `docs/plans/20260526T224018Z_blahab44_inputs/`.

## Catalog Commands

| # | Command ID | Class | Catalog Pin | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | `illumina_snv_alignstats` | sample_analysis | `2.0.2` | OPEN |  |
| 2 | `illumina_snv_alignstats_relatedness_vep_multiqc` | sample_analysis | `2.0.2` | OPEN |  |
| 3 | `ultima_snv_alignstats` | sample_analysis | `2.0.2` | OPEN |  |
| 4 | `ultima_snv_alignstats_kitchensink` | sample_analysis | `2.0.2` | OPEN |  |
| 5 | `ont_snv_alignstats` | sample_analysis | `2.0.2` | OPEN |  |
| 6 | `ont_snv_alignstats_kitchensink` | sample_analysis | `2.0.2` | OPEN |  |
| 7 | `pacbio_snv_alignstats` | sample_analysis | `2.0.2` | OPEN |  |
| 8 | `roche_snv_alignstats` | sample_analysis | `2.0.2` | OPEN |  |
| 9 | `hybrid_ilmn_ont_snv` | sample_analysis | `2.0.2` | OPEN |  |
| 10 | `hybrid_ilmn_ont_snv_kitchensink` | sample_analysis | `2.0.2` | OPEN |  |
| 11 | `hybrid_ultima_ont_snv` | sample_analysis | `2.0.2` | OPEN |  |
| 12 | `complete_genomics_mgi_snv_concordance` | sample_analysis | `2.0.2` | BLOCKED | Candidate CG/MGI mate-pair contract remains unverified; no substitution authorized. |
| 13 | `illumina_run_qc` | run_analysis | `2.0.2` | OPEN |  |
| 14 | `illumina_bclconvert` | run_analysis | `2.0.2` | OPEN |  |
| 15 | `illumina_run_qc_bclconvert` | run_analysis | `2.0.2` | OPEN |  |
| 16 | `ont_run_qc` | run_analysis | `2.0.2` | OPEN |  |
| 17 | `ultima_run_qc` | run_analysis | `2.0.2` | OPEN |  |

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REL-001 | DayOA release | Commit and push the runtime asset path changes; create and push non-`v` tag `2.0.2` so the catalog can address the new checkin. | SUCCESS | config_or_startup_contract | Gate 1 | orchestrator | Commit `1b103c7c66a8f04d94c1feab7f8e591f5a3dd4b8` (`Pin runtime assets under references`) pushed to `origin/main`; annotated tag `2.0.2` pushed; remote readback showed `refs/heads/main` at `1b103c7c66a8f04d94c1feab7f8e591f5a3dd4b8` and `refs/tags/2.0.2` present. Baseline DayOA focused tests passed: `44 passed`. |  | DayOA runtime-asset path update is published and addressable by tag `2.0.2`. |
| REL-002 | DAY-EC catalog | Pin source and packaged DayOA catalog refs from `2.0.1` to `2.0.2`, update tests/docs, commit and push. | SUCCESS | config_or_startup_contract | Gate 1 | orchestrator | Source and packaged catalogs, README, docs, and catalog tests changed to `2.0.2`; source/package catalog parity passed; focused DAY-EC tests passed: `234 passed`. |  | DAY-EC catalog now resolves DayOA command clones to tag `2.0.2`. |
| REL-003 | DAY-EC self pin | Pin source and packaged `daylily_cli_global.yaml` from `5.0.1` to `5.0.2`, then tag/push `5.0.2` so the headnode configure step clones the new checkin. | SUCCESS | config_or_startup_contract | Gate 1 | orchestrator | No user-level global config exists; source and packaged global config changed to `5.0.2`; source/package global-config parity passed; focused DAY-EC tests passed: `234 passed`. |  | DAY-EC headnode configure will clone the `5.0.2` release tag after publication. |
| CLU-001 | Cluster create | Create new DAY-EC cluster `blahab44` in `us-west-2` using profile `lsmc`, after release pins are pushed. | SUCCESS | feature_implementation | Gate 2 | orchestrator | Preflight passed 12 checks; create completed in `21m 6s`; state `/Users/jmajor/.config/daylily/state_blahab44_20260526224612.json`; pcluster readback `CREATE_COMPLETE`, compute fleet `RUNNING`, headnode `i-0bc04c4642b1c4b8d`; headnode readiness confirmed DAY-EC `5.0.2`, runtime assets under `/fsx/references/runtime_assets`, no `/fsx/runtime_assets` or `/fsx/data`, empty Slurm queue. |  | `blahab44` is live and ready for catalog dry-runs. |
| CAT-001 | Catalog launch | Run all 17 DayOA command catalog commands against `blahab44`; each command row must reach `SUCCESS`, `FAIL`, or `BLOCKED` with exact dry-run/live evidence. | IN_PROGRESS | contract_test | Gate 3 | orchestrator | Catalog command inventory above; durable driver `docs/plans/20260526T224018Z_blahab44_catalog_driver.py`; event stream target `docs/plans/20260526T224018Z_blahab44_catalog_runs.jsonl`; logs target `docs/plans/20260526T224018Z_blahab44_logs/`. |  | Dry-run phase starting. |
| FINAL-001 | Final report | Record final row counts, cluster state, output/export paths, residual blockers, and destructive-action boundary. | OPEN | contract_test | Gate 4 | orchestrator |  |  |  |
