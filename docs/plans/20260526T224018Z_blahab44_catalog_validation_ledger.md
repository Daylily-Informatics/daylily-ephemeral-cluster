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

## Post-Create Release Correction

- Initial live attempts under DayOA `2.0.3` failed immediately with `PermissionError` because Snakemake attempted to create conda envs under read-only `/fsx/references/runtime_assets/cached_envs/conda/...`.
- DayOA fix published: commit `2398d4a` (`Restore writable Snakemake conda cache`), tag `2.0.5`, pushed to `origin/main`; focused validation `pytest tests/test_multiqc_sample_identifiers.py -q -> 26 passed`.
- DAY-EC catalog fix published: commit `104fadf3` (`Pin DayOA 2.0.5 in command catalog`), tag `5.0.6`, pushed to `origin/main`; focused validation `pytest tests/test_repository_catalog.py tests/test_cli_registry_v2.py -q -> 99 passed` and `pytest tests/test_packaged_defaults.py tests/test_resources_extraction.py -q -> 7 passed`.
- Cluster `blahab44` headnode was created by DAY-EC `5.0.2`; post-fix catalog launches were made from the local DAY-EC `5.0.6` checkin and launch logs confirm `--git-tag 2.0.5` for forced retry dry-runs/lives.
- Rechecked AWS identity before post-fix live work: profile `lsmc`, region `us-west-2`, account `108782052779`, ARN `arn:aws:iam::108782052779:root`; `pcluster describe-cluster` read back `blahab44` as `CREATE_COMPLETE` with compute fleet `RUNNING`.

## Heartbeat 2026-05-27T02:43Z Monitoring

- Re-read repo instructions, plan-ledger SOP, current ledger, and git state. Repo branch remains `main` at `59fb294ac6c93c389f3bec418de433c84736abb3`; unrelated user/GoodOle3/cluster-config changes remain unstaged and were not touched.
- Workflow status/log sweep appended to `docs/plans/20260526T224018Z_blahab44_catalog_runs.jsonl` and wrote:
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ultima_snv_alignstats_kitchensink_retry2_live_status_20260527T024340Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ultima_snv_alignstats_kitchensink_retry2_live_tmux_tail_20260527T024340Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ont_snv_alignstats_kitchensink_live_status_20260527T024340Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ont_snv_alignstats_kitchensink_live_tmux_tail_20260527T024340Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_hybrid_ilmn_ont_snv_kitchensink_live_status_20260527T024340Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_hybrid_ilmn_ont_snv_kitchensink_live_tmux_tail_20260527T024340Z.log`
- All three remaining kitchensink sessions were still non-terminal: `exit_code=null`, `completed_at=null`.
- Headnode Slurm evidence via `daylily_ec.aws.ssm.run_shell` as `ubuntu` on `ip-10-0-0-224`: job `33` `verifybamid2_contam-TVBUG5X-HG003-5x-1-D0-PF-UG-ULTIMA` running `34:56`; job `48` `verifybamid2_contam-TVBONT5X-HG003-5x-1-D0-PF-ONT-PROMETHION` running `30:56`; job `80` `verifybamid2_contam-TVBHIO5X5X-HG003-ILMN5x-ONT5x-1-D0-PF-ILMN-NOVASEQ` running `23:56`.

## Heartbeat 2026-05-27T03:13Z Monitoring

- Re-read repo instructions, plan-ledger SOP, current ledger, and git state. Repo branch remains `main` at `61cef3d2ece315024f9fc1bef56c88c48d765244`; unrelated GoodOle3 files remain dirty/untracked and were not touched.
- Workflow status/log sweep appended to `docs/plans/20260526T224018Z_blahab44_catalog_runs.jsonl` and wrote:
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ultima_snv_alignstats_kitchensink_retry2_live_status_20260527T031340Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ultima_snv_alignstats_kitchensink_retry2_live_tmux_tail_20260527T031340Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ont_snv_alignstats_kitchensink_live_status_20260527T031340Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ont_snv_alignstats_kitchensink_live_tmux_tail_20260527T031340Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_hybrid_ilmn_ont_snv_kitchensink_live_status_20260527T031340Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_hybrid_ilmn_ont_snv_kitchensink_live_tmux_tail_20260527T031340Z.log`
- All three remaining kitchensink sessions were still non-terminal: `exit_code=null`, `completed_at=null`.
- Headnode Slurm evidence via `daylily_ec.aws.ssm.run_shell` as `ubuntu` on `ip-10-0-0-224`: `RUNNING=3`, `CONFIGURING=0`, `PENDING=0`, `TOTAL=3`; job `33` `verifybamid2_contam-TVBUG5X-HG003-5x-1-D0-PF-UG-ULTIMA` running `1:04:51`; job `48` `verifybamid2_contam-TVBONT5X-HG003-5x-1-D0-PF-ONT-PROMETHION` running `1:00:51`; job `80` `verifybamid2_contam-TVBHIO5X5X-HG003-ILMN5x-ONT5x-1-D0-PF-ILMN-NOVASEQ` running `53:51`.

## Heartbeat 2026-05-27T03:43Z Monitoring

- Re-read repo instructions, plan-ledger SOP, current ledger, and git state. Repo branch remains `main` at `67f81c70139de0964733182fe14c9f99cac41154`; unrelated GoodOle3 files remain dirty/untracked and were not touched.
- Workflow status/log sweep appended to `docs/plans/20260526T224018Z_blahab44_catalog_runs.jsonl` and wrote:
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ultima_snv_alignstats_kitchensink_retry2_live_status_20260527T034340Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ultima_snv_alignstats_kitchensink_retry2_live_tmux_tail_20260527T034340Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ultima_snv_alignstats_kitchensink_retry2_result_paths_20260527T034340Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ont_snv_alignstats_kitchensink_live_status_20260527T034340Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ont_snv_alignstats_kitchensink_live_tmux_tail_20260527T034340Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_hybrid_ilmn_ont_snv_kitchensink_live_status_20260527T034340Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_hybrid_ilmn_ont_snv_kitchensink_live_tmux_tail_20260527T034340Z.log`
- `bb44_ultima_snv_alignstats_kitchensink_retry2` completed successfully: `exit_code=0`, `completed_at=2026-05-27T03:18:30Z`.
- Completed Ultima kitchensink result root: `/fsx/analysis_results/ubuntu/bb44_ultima_snv_alignstats_kitchensink_retry2/daylily-omics-analysis/results`; key report paths include `results/day/hg38_broad/reports/DAY_final_multiqc.html`, `results/day/hg38_broad/reports/DAY_final_multiqc_data/`, `results/day/hg38_broad/other_reports/giab_concordance_mqc.tsv`, and `results/day/hg38_broad/other_reports/vep_annotation_mqc.tsv`; `find results/day/hg38_broad -type f -name '*.done'` counted `13`.
- Remaining non-terminal sessions: `bb44_ont_snv_alignstats_kitchensink` and `bb44_hybrid_ilmn_ont_snv_kitchensink` with `exit_code=null`, `completed_at=null`.
- Headnode Slurm evidence via `daylily_ec.aws.ssm.run_shell` as `ubuntu` on `ip-10-0-0-224`: `RUNNING=2`, `CONFIGURING=0`, `PENDING=0`, `TOTAL=2`; job `48` `verifybamid2_contam-TVBONT5X-HG003-5x-1-D0-PF-ONT-PROMETHION` running `1:31:04`; job `80` `verifybamid2_contam-TVBHIO5X5X-HG003-ILMN5x-ONT5x-1-D0-PF-ILMN-NOVASEQ` running `1:24:04`.

## Heartbeat 2026-05-27T05:07Z Monitoring

- Workflow status/log sweep appended to `docs/plans/20260526T224018Z_blahab44_catalog_runs.jsonl` and wrote:
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ont_snv_alignstats_kitchensink_live_status_20260527T050711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ont_snv_alignstats_kitchensink_live_tmux_tail_20260527T050711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_hybrid_ilmn_ont_snv_kitchensink_live_status_20260527T050711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_hybrid_ilmn_ont_snv_kitchensink_live_tmux_tail_20260527T050711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/blahab44_slurm_20260527T050711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/blahab44_slurm_detail_20260527T050711Z.log`
- Remaining non-terminal sessions: `bb44_ont_snv_alignstats_kitchensink` and `bb44_hybrid_ilmn_ont_snv_kitchensink` with `exit_code=null`, `completed_at=null`.
- ONT tmux tail included `Error in rule sent_snv_ont` and progress at `14 of 106 steps (13%) done`; Hybrid tmux tail included `Error in rule verifybamid2_contam` and progress at `37 of 848 steps (4%) done`.
- Headnode Slurm evidence via `daylily_ec.aws.ssm.run_shell` as `ubuntu` on `ip-10-0-0-224`: `RUNNING=0`, `CONFIGURING=2`, `PENDING=0`, `TOTAL=2`; jobs `48` and `185` were both `verifybamid2_contam` jobs in `CONFIGURING` on `i192mem-dy-all-1`.

## Heartbeat 2026-05-27T05:37Z Monitoring

- Re-read repo instructions, plan-ledger SOP, current ledger, and git state. Repo branch remains `main` at `1f834ea2`; unrelated GoodOle3/cache/Kahlo/Sarek/Dewey files remain dirty or untracked and were not touched.
- AWS identity evidence before the live status check: `AWS_PROFILE=lsmc`, region `us-west-2`, account `108782052779`, ARN `arn:aws:iam::108782052779:root`.
- Workflow status/log sweep appended to `docs/plans/20260526T224018Z_blahab44_catalog_runs.jsonl` and wrote:
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ont_snv_alignstats_kitchensink_live_status_20260527T053711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ont_snv_alignstats_kitchensink_live_tmux_tail_20260527T053711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_hybrid_ilmn_ont_snv_kitchensink_live_status_20260527T053711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_hybrid_ilmn_ont_snv_kitchensink_live_tmux_tail_20260527T053711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/blahab44_slurm_20260527T053711Z.log`
- Remaining non-terminal sessions: `bb44_ont_snv_alignstats_kitchensink` and `bb44_hybrid_ilmn_ont_snv_kitchensink` with `exit_code=null`, `completed_at=null`.
- ONT tmux tail still included `Error in rule sent_snv_ont` and progress at `13 of 106 steps (12%) done`; Hybrid tmux tail showed progress through `36 of 848 steps (4%) done`.
- Headnode Slurm evidence via `daylily_ec.aws.ssm.run_shell` as `ubuntu` on `ip-10-0-0-224`: `RUNNING=2`, `CONFIGURING=0`, `PENDING=0`, `TOTAL=2`; job `48` `verifybamid2_contam-TVBONT5X-HG003-5x-1-D0-PF-ONT-PROMETHION` and job `185` `verifybamid2_contam-TVBHIO5X5X-HG003-ILMN5x-ONT5x-1-D0-PF-ILMN-NOVASEQ` were both running on `i192mem-dy-all-1`.

## Heartbeat 2026-05-27T06:07Z Monitoring

- Re-read repo instructions, plan-ledger SOP, current ledger, and git state. Repo branch remains `main` at `1f834ea2`; unrelated GoodOle3/cache/Kahlo/Sarek/Dewey files remain dirty or untracked and were not touched.
- AWS identity evidence before the live status check: `AWS_PROFILE=lsmc`, region `us-west-2`, account `108782052779`, ARN `arn:aws:iam::108782052779:root`.
- Workflow status/log sweep appended to `docs/plans/20260526T224018Z_blahab44_catalog_runs.jsonl` and wrote:
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ont_snv_alignstats_kitchensink_live_status_20260527T060711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ont_snv_alignstats_kitchensink_live_tmux_tail_20260527T060711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_hybrid_ilmn_ont_snv_kitchensink_live_status_20260527T060711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_hybrid_ilmn_ont_snv_kitchensink_live_tmux_tail_20260527T060711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/blahab44_slurm_20260527T060711Z.log`
- Remaining non-terminal sessions: `bb44_ont_snv_alignstats_kitchensink` and `bb44_hybrid_ilmn_ont_snv_kitchensink` with `exit_code=null`, `completed_at=null`.
- ONT tmux tail showed progress at `13 of 106 steps (12%) done`; Hybrid tmux tail showed progress through `25 of 848 steps (3%) done`.
- Headnode Slurm evidence via `daylily_ec.aws.ssm.run_shell` as `ubuntu` on `ip-10-0-0-224`: `RUNNING=2`, `CONFIGURING=0`, `PENDING=0`, `COMPLETING=0`, `TOTAL=2`; job `48` `verifybamid2_contam-TVBONT5X-HG003-5x-1-D0-PF-ONT-PROMETHION` and job `185` `verifybamid2_contam-TVBHIO5X5X-HG003-ILMN5x-ONT5x-1-D0-PF-ILMN-NOVASEQ` were both running on `i192mem-dy-all-1` with elapsed `58:13`.

## Heartbeat 2026-05-27T06:37Z Monitoring

- Re-read repo instructions, plan-ledger SOP, current ledger, and git state. Repo branch remains `main` at `1f834ea2`; unrelated GoodOle3/cache/Kahlo/Sarek/Dewey files remain dirty or untracked and were not touched.
- AWS identity evidence before the live status check: `AWS_PROFILE=lsmc`, region `us-west-2`, account `108782052779`, ARN `arn:aws:iam::108782052779:root`.
- Workflow status/log sweep appended to `docs/plans/20260526T224018Z_blahab44_catalog_runs.jsonl` and wrote:
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ont_snv_alignstats_kitchensink_live_status_20260527T063711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ont_snv_alignstats_kitchensink_live_tmux_tail_20260527T063711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_hybrid_ilmn_ont_snv_kitchensink_live_status_20260527T063711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_hybrid_ilmn_ont_snv_kitchensink_live_tmux_tail_20260527T063711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/blahab44_slurm_20260527T063711Z.log`
- Remaining non-terminal sessions: `bb44_ont_snv_alignstats_kitchensink` and `bb44_hybrid_ilmn_ont_snv_kitchensink` with `exit_code=null`, `completed_at=null`.
- ONT tmux tail included `Error in rule sent_snv_ont`; Hybrid tmux tail showed progress through `21 of 848 steps (2%) done`.
- Headnode Slurm evidence via `daylily_ec.aws.ssm.run_shell` as `ubuntu` on `ip-10-0-0-224`: `RUNNING=2`, `CONFIGURING=0`, `PENDING=0`, `COMPLETING=0`, `TOTAL=2`; job `48` `verifybamid2_contam-TVBONT5X-HG003-5x-1-D0-PF-ONT-PROMETHION` and job `185` `verifybamid2_contam-TVBHIO5X5X-HG003-ILMN5x-ONT5x-1-D0-PF-ILMN-NOVASEQ` were both running on `i192mem-dy-all-1` with elapsed `1:28:13`.

## Heartbeat 2026-05-27T07:07Z Monitoring

- Re-read repo instructions, plan-ledger SOP, current ledger, and git state. Repo branch remains `main` at `1f834ea2`; unrelated GoodOle3/cache/Kahlo/Sarek/Dewey files remain dirty or untracked and were not touched.
- AWS identity evidence before the live status check: `AWS_PROFILE=lsmc`, region `us-west-2`, account `108782052779`, ARN `arn:aws:iam::108782052779:root`.
- Workflow status/log sweep appended to `docs/plans/20260526T224018Z_blahab44_catalog_runs.jsonl` and wrote:
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ont_snv_alignstats_kitchensink_live_status_20260527T070711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ont_snv_alignstats_kitchensink_live_tmux_tail_20260527T070711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_hybrid_ilmn_ont_snv_kitchensink_live_status_20260527T070711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_hybrid_ilmn_ont_snv_kitchensink_live_tmux_tail_20260527T070711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/blahab44_slurm_20260527T070711Z.log`
- Remaining non-terminal sessions: `bb44_ont_snv_alignstats_kitchensink` and `bb44_hybrid_ilmn_ont_snv_kitchensink` with `exit_code=null`, `completed_at=null`.
- ONT tmux tail showed `Error in rule sent_snv_ont` after `12 of 106 steps (11%) done`; Hybrid tmux tail showed `Error in rule sentdhiomr_sr_align` after `13 of 848 steps (2%) done`, then progress through `18 of 848 steps (2%) done`.
- Headnode Slurm evidence via `daylily_ec.aws.ssm.run_shell` as `ubuntu` on `ip-10-0-0-224`: `RUNNING=2`, `CONFIGURING=0`, `PENDING=0`, `COMPLETING=0`, `TOTAL=2`; job `48` `verifybamid2_contam-TVBONT5X-HG003-5x-1-D0-PF-ONT-PROMETHION` and job `185` `verifybamid2_contam-TVBHIO5X5X-HG003-ILMN5x-ONT5x-1-D0-PF-ILMN-NOVASEQ` were both running on `i192mem-dy-all-1` with elapsed `1:58:16`.

## Heartbeat 2026-05-27T07:37Z Monitoring

- Re-read repo instructions, plan-ledger SOP, current ledger, and git state. Repo branch remains `main` at `1f834ea2`; unrelated GoodOle3/cache/Kahlo/Sarek/Dewey files remain dirty or untracked and were not touched.
- AWS identity evidence before the live status check: `AWS_PROFILE=lsmc`, region `us-west-2`, account `108782052779`, ARN `arn:aws:iam::108782052779:root`.
- Workflow status/log sweep appended to `docs/plans/20260526T224018Z_blahab44_catalog_runs.jsonl` and wrote:
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ont_snv_alignstats_kitchensink_live_status_20260527T073711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ont_snv_alignstats_kitchensink_live_tmux_tail_20260527T073711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_hybrid_ilmn_ont_snv_kitchensink_live_status_20260527T073711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_hybrid_ilmn_ont_snv_kitchensink_live_tmux_tail_20260527T073711Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/blahab44_slurm_20260527T073711Z.log`
- Remaining non-terminal sessions: `bb44_ont_snv_alignstats_kitchensink` and `bb44_hybrid_ilmn_ont_snv_kitchensink` with `exit_code=null`, `completed_at=null`.
- ONT tmux tail showed `Error in rule sent_snv_ont` after `12 of 106 steps (11%) done`; Hybrid tmux tail showed `Error in rule sentdhiomr_call_svs`, then `Error in rule sentdhiomr_sr_align` after `13 of 848 steps (2%) done`, and progress through `15 of 848 steps (2%) done`.
- Headnode Slurm evidence via `daylily_ec.aws.ssm.run_shell` as `ubuntu` on `ip-10-0-0-224`: `RUNNING=2`, `CONFIGURING=0`, `PENDING=0`, `COMPLETING=0`, `TOTAL=2`; job `48` `verifybamid2_contam-TVBONT5X-HG003-5x-1-D0-PF-ONT-PROMETHION` and job `185` `verifybamid2_contam-TVBHIO5X5X-HG003-ILMN5x-ONT5x-1-D0-PF-ILMN-NOVASEQ` were both running on `i192mem-dy-all-1` with elapsed `2:28:25`.

## Heartbeat 2026-05-27T15:32Z Monitoring

- Re-read repo instructions, plan-ledger SOP, current ledger, and git state. Repo branch remains `main` at `1f834ea2`; unrelated GoodOle3/cache/Kahlo/Sarek/Dewey files remain dirty or untracked and were not touched.
- AWS identity evidence before the live status check: `AWS_PROFILE=lsmc`, region `us-west-2`, account `108782052779`, ARN `arn:aws:iam::108782052779:root`.
- Workflow status/log sweep appended to `docs/plans/20260526T224018Z_blahab44_catalog_runs.jsonl` and wrote:
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ont_snv_alignstats_kitchensink_live_status_20260527T153244Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_ont_snv_alignstats_kitchensink_live_tmux_tail_20260527T153244Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_hybrid_ilmn_ont_snv_kitchensink_live_status_20260527T153244Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/bb44_hybrid_ilmn_ont_snv_kitchensink_live_tmux_tail_20260527T153244Z.log`
  - `docs/plans/20260526T224018Z_blahab44_logs/blahab44_slurm_20260527T153244Z.log`
- Remaining non-terminal sessions: `bb44_ont_snv_alignstats_kitchensink` and `bb44_hybrid_ilmn_ont_snv_kitchensink` with `exit_code=null`, `completed_at=null`.
- ONT tmux tail captured the verifybamid2 contamination stage after `10 of 106 steps (9%) done`; Hybrid tmux tail captured restarted hybrid alignment/QC work without a terminal exit code in the status payload.
- Headnode Slurm evidence via `daylily_ec.aws.ssm.run_shell` as `ubuntu` on `ip-10-0-0-224`: `RUNNING=2`, `CONFIGURING=0`, `PENDING=0`, `COMPLETING=0`, `TOTAL=2`; job `48` `verifybamid2_contam-TVBONT5X-HG003-5x-1-D0-PF-ONT-PROMETHION` and job `185` `verifybamid2_contam-TVBHIO5X5X-HG003-ILMN5x-ONT5x-1-D0-PF-ILMN-NOVASEQ` were both running on `i192mem-dy-all-1` with elapsed `10:26:21`.

## 2026-05-27T16:14Z Destructive Cancellation Preflight

- User requested killing active `verifybamid2` jobs because the workflow is being removed from active use permanently.
- Re-read repo/global instructions, plan-ledger SOP, current ledger, and git state. Repo branch remains `main`; unrelated GoodOle3/cache/Kahlo/Sarek/Dewey files remain dirty or untracked and were not touched.
- AWS identity evidence before live inspection: `AWS_PROFILE=lsmc`, region `us-west-2`, account `108782052779`, ARN `arn:aws:iam::108782052779:root`.
- Non-destructive DAY-EC SSM helper preflight recorded candidate jobs in `docs/plans/20260526T224018Z_blahab44_logs/blahab44_verifybamid2_cancel_candidates_20260527T161000Z.log` and appended a `verifybamid2_cancel_preflight` event to `docs/plans/20260526T224018Z_blahab44_catalog_runs.jsonl`.
- Candidate destructive command is `scancel 48 185` on `blahab44` as `ubuntu`. This would cancel running Slurm jobs `48` (`verifybamid2_contam-TVBONT5X-HG003-5x-1-D0-PF-ONT-PROMETHION`) and `185` (`verifybamid2_contam-TVBHIO5X5X-HG003-ILMN5x-ONT5x-1-D0-PF-ILMN-NOVASEQ`), both in `RUNNING` state on `i192mem-dy-all-1` at elapsed `11:03:38`.
- No destructive action was executed; cancellation is blocked pending the required second explicit approval.

## Catalog Commands

| # | Command ID | Class | Catalog Pin | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | `illumina_snv_alignstats` | sample_analysis | `2.0.5` | SUCCESS | Forced dry-run `bb44_illumina_snv_alignstats_dryrun_retry2` exit `0`; live `bb44_illumina_snv_alignstats_retry2` exit `0` at `2026-05-27T01:50:46Z`. |
| 2 | `illumina_snv_alignstats_relatedness_vep_multiqc` | sample_analysis | `2.0.5` | FAIL | Forced dry-run exit `0`; live `bb44_illumina_snv_alignstats_relatedness_vep_multiqc_retry2` exit `1` at `2026-05-27T02:05:37Z`; `verifybamid2_v0.1` env creation hit `FileNotFoundError` under writable `/fsx/resources/environments/conda/.../fb4f97.../Tie/Array.pm`, consistent with concurrent shared conda-cache race/corruption. |
| 3 | `ultima_snv_alignstats` | sample_analysis | `2.0.5` | SUCCESS | Forced dry-run `bb44_ultima_snv_alignstats_dryrun_retry2` exit `0`; live `bb44_ultima_snv_alignstats_retry2` exit `0` at `2026-05-27T02:26:58Z`. |
| 4 | `ultima_snv_alignstats_kitchensink` | sample_analysis | `2.0.5` | SUCCESS | Forced dry-run `bb44_ultima_snv_alignstats_kitchensink_dryrun_retry2` exit `0`; live `bb44_ultima_snv_alignstats_kitchensink_retry2` exit `0`, started `2026-05-27T02:03:56Z`, completed `2026-05-27T03:18:30Z`; repo path `/fsx/analysis_results/ubuntu/bb44_ultima_snv_alignstats_kitchensink_retry2/daylily-omics-analysis`; result root `/fsx/analysis_results/ubuntu/bb44_ultima_snv_alignstats_kitchensink_retry2/daylily-omics-analysis/results`; final report `results/day/hg38_broad/reports/DAY_final_multiqc.html`; key tables `results/day/hg38_broad/other_reports/giab_concordance_mqc.tsv` and `results/day/hg38_broad/other_reports/vep_annotation_mqc.tsv`. |
| 5 | `ont_snv_alignstats` | sample_analysis | `2.0.5` | FAIL | Forced dry-run exit `0`; live `bb44_ont_snv_alignstats` exit `1` at `2026-05-27T02:17:17Z`; tmux tail captured `sentieon-cli dnascope-longread` failure path for `sentdont`. |
| 6 | `ont_snv_alignstats_kitchensink` | sample_analysis | `2.0.5` | RUNNING | Forced dry-run `bb44_ont_snv_alignstats_kitchensink_dryrun_retry2` exit `0`; live `bb44_ont_snv_alignstats_kitchensink` started `2026-05-27T02:07:09Z` and was non-terminal at `2026-05-27T15:32Z`; repo path `/fsx/analysis_results/ubuntu/bb44_ont_snv_alignstats_kitchensink/daylily-omics-analysis`; result root `/fsx/analysis_results/ubuntu/bb44_ont_snv_alignstats_kitchensink/daylily-omics-analysis/results`; latest status/tmux logs are `bb44_ont_snv_alignstats_kitchensink_live_status_20260527T153244Z.log` and `bb44_ont_snv_alignstats_kitchensink_live_tmux_tail_20260527T153244Z.log`; Slurm job `48` `verifybamid2_contam-TVBONT5X-HG003-5x-1-D0-PF-ONT-PROMETHION` continued running on `i192mem`. |
| 7 | `pacbio_snv_alignstats` | sample_analysis | `2.0.5` | FAIL | Forced dry-run exit `0`; live `bb44_pacbio_snv_alignstats` exit `1` at `2026-05-27T02:25:45Z`; rule log tail reported `ERROR: sentieon-cli dnascope-longread failed` and `ERROR: SNV VCF not produced by sentieon-cli`. |
| 8 | `roche_snv_alignstats` | sample_analysis | `2.0.5` | FAIL | Forced dry-run `bb44_roche_snv_alignstats_dryrun_retry2` exit `1`; Singularity could not open missing Roche container image `/fsx/references/runtime_assets/cached_envs/containers/7a424a40c6fd659f4d052893dd3554fa.simg`. |
| 9 | `hybrid_ilmn_ont_snv` | sample_analysis | `2.0.5` | FAIL | Forced dry-run exit `0`; live `bb44_hybrid_ilmn_ont_snv` exit `1` at `2026-05-27T02:17:45Z`; tmux tail captured `sentdhiomr_sr_align` cluster job external `64` nonzero and downstream `sentdhiomr_call_svs` error. |
| 10 | `hybrid_ilmn_ont_snv_kitchensink` | sample_analysis | `2.0.5` | RUNNING | Forced dry-run `bb44_hybrid_ilmn_ont_snv_kitchensink_dryrun_retry2` exit `0`; live `bb44_hybrid_ilmn_ont_snv_kitchensink` started `2026-05-27T02:12:02Z` and was non-terminal at `2026-05-27T15:32Z`; repo path `/fsx/analysis_results/ubuntu/bb44_hybrid_ilmn_ont_snv_kitchensink/daylily-omics-analysis`; result root `/fsx/analysis_results/ubuntu/bb44_hybrid_ilmn_ont_snv_kitchensink/daylily-omics-analysis/results`; latest status/tmux logs are `bb44_hybrid_ilmn_ont_snv_kitchensink_live_status_20260527T153244Z.log` and `bb44_hybrid_ilmn_ont_snv_kitchensink_live_tmux_tail_20260527T153244Z.log`; Slurm job `185` `verifybamid2_contam-TVBHIO5X5X-HG003-ILMN5x-ONT5x-1-D0-PF-ILMN-NOVASEQ` continued running on `i192mem`. |
| 11 | `hybrid_ultima_ont_snv` | sample_analysis | `2.0.5` | FAIL | Forced dry-run exit `0`; live `bb44_hybrid_ultima_ont_snv` exit `1` at `2026-05-27T02:19:49Z`; tmux tail captured `sentdhuomr_pass1` cluster job external `74` nonzero. |
| 12 | `complete_genomics_mgi_snv_concordance` | sample_analysis | `2.0.5` | BLOCKED | Candidate CG/MGI mate-pair contract remains unverified; `_386_1` and `_386_2` sizes are inconsistent and no substitution is authorized. |
| 13 | `illumina_run_qc` | run_analysis | `2.0.5` | FAIL | Forced dry-run exit `0`; live `bb44_illumina_run_qc` exit `1` at `2026-05-27T02:17:25Z`; MultiQC conda env creation failed under writable `/fsx/resources/environments/conda/.../259e5...` with pip `OSError` for `networkx-3.6.1.dist-info/...tmp`, consistent with shared conda-cache race/corruption. |
| 14 | `illumina_bclconvert` | run_analysis | `2.0.5` | FAIL | Forced dry-run exit `0`; live `bb44_illumina_bclconvert` exit `1` at `2026-05-27T02:21:39Z`; DRA run dir and `SampleSheet.csv` exist under `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4`, but `bclconvert_validate_inputs.log` reports `Sample_ID HG001-a at line 21 is not present in samples.tsv` after warning that SoftwareVersion `4.3.16` is newer than pinned runtime `4.0.3`. |
| 15 | `illumina_run_qc_bclconvert` | run_analysis | `2.0.5` | FAIL | Forced dry-run exit `0`; live `bb44_illumina_run_qc_bclconvert` exit `1` at `2026-05-27T02:26:58Z`; MultiQC conda env creation failed under shared writable cache hash `41740234...` with missing `python`/Jupyter post-link files, consistent with concurrent cache corruption. |
| 16 | `ont_run_qc` | run_analysis | `2.0.5` | FAIL | Forced dry-run exit `0`; live `bb44_ont_run_qc` exit `1` at `2026-05-27T02:27:02Z`; failure tail shows the same shared MultiQC conda env corruption class under hash `41740234...`; log also listed absent control-data FASTQs under `/fsx/control_data/.../NovaSeqX_WHGS_TruSeqPF_HG002-007/...`. |
| 17 | `ultima_run_qc` | run_analysis | `2.0.5` | FAIL | Forced dry-run exit `0`; live `bb44_ultima_run_qc` exit `1` at `2026-05-27T02:23:19Z`; `ultima_run_qc_report` invoked `summarize_run_qc_report.py` with empty `--run-s3-uri` and `--metrics-path` values and did not produce `ultima_run_qc_report.done`. |

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REL-001 | DayOA release | Commit and push the runtime asset path changes; create and push non-`v` tag `2.0.2` so the catalog can address the new checkin. | SUCCESS | config_or_startup_contract | Gate 1 | orchestrator | Commit `1b103c7c66a8f04d94c1feab7f8e591f5a3dd4b8` (`Pin runtime assets under references`) pushed to `origin/main`; annotated tag `2.0.2` pushed; remote readback showed `refs/heads/main` at `1b103c7c66a8f04d94c1feab7f8e591f5a3dd4b8` and `refs/tags/2.0.2` present. Baseline DayOA focused tests passed: `44 passed`. |  | DayOA runtime-asset path update is published and addressable by tag `2.0.2`. |
| REL-002 | DAY-EC catalog | Pin source and packaged DayOA catalog refs from `2.0.1` to `2.0.2`, update tests/docs, commit and push. | SUCCESS | config_or_startup_contract | Gate 1 | orchestrator | Source and packaged catalogs, README, docs, and catalog tests changed to `2.0.2`; source/package catalog parity passed; focused DAY-EC tests passed: `234 passed`. |  | DAY-EC catalog now resolves DayOA command clones to tag `2.0.2`. |
| REL-003 | DAY-EC self pin | Pin source and packaged `daylily_cli_global.yaml` from `5.0.1` to `5.0.2`, then tag/push `5.0.2` so the headnode configure step clones the new checkin. | SUCCESS | config_or_startup_contract | Gate 1 | orchestrator | No user-level global config exists; source and packaged global config changed to `5.0.2`; source/package global-config parity passed; focused DAY-EC tests passed: `234 passed`. |  | DAY-EC headnode configure will clone the `5.0.2` release tag after publication. |
| REL-004 | DayOA correction | Restore Snakemake `conda-prefix` to a writable path while keeping containers under reference runtime assets, then publish a new DayOA tag. | SUCCESS | config_or_startup_contract | Gate 3 | orchestrator | Commit `2398d4a` (`Restore writable Snakemake conda cache`) and tag `2.0.5` pushed; focused test `pytest tests/test_multiqc_sample_identifiers.py -q -> 26 passed`. | Initial live attempts under `2.0.3` failed because conda env creation targeted read-only `/fsx/references/runtime_assets/cached_envs/conda`. | DayOA `2.0.5` is the active catalog validation pin for retry work. |
| REL-005 | DAY-EC catalog correction | Pin source and packaged catalog refs to DayOA `2.0.5`, update DAY-EC self refs to `5.0.6`, then commit/tag/push. | SUCCESS | config_or_startup_contract | Gate 3 | orchestrator | Commit `104fadf3` (`Pin DayOA 2.0.5 in command catalog`) and tag `5.0.6` pushed; focused tests `99 passed` and package/default tests `7 passed`. | Catalog needed the new DayOA tag so launched workflows cloned the writable-cache fix. | DAY-EC `5.0.6` is published; local launch logs confirm `--git-tag 2.0.5`. |
| CLU-001 | Cluster create | Create new DAY-EC cluster `blahab44` in `us-west-2` using profile `lsmc`, after release pins are pushed. | SUCCESS | feature_implementation | Gate 2 | orchestrator | Preflight passed 12 checks; create completed in `21m 6s`; state `/Users/jmajor/.config/daylily/state_blahab44_20260526224612.json`; pcluster readback `CREATE_COMPLETE`, compute fleet `RUNNING`, headnode `i-0bc04c4642b1c4b8d`; headnode readiness confirmed DAY-EC `5.0.2`, runtime assets under `/fsx/references/runtime_assets`, no `/fsx/runtime_assets` or `/fsx/data`, empty Slurm queue. |  | `blahab44` is live and ready for catalog dry-runs. |
| CAT-001 | Catalog launch | Run all 17 DayOA command catalog commands against `blahab44`; each command row must reach `SUCCESS`, `FAIL`, `RUNNING`, or `BLOCKED` with exact dry-run/live evidence. | IN_PROGRESS | contract_test | Gate 3 | orchestrator | Event stream `docs/plans/20260526T224018Z_blahab44_catalog_runs.jsonl`; logs `docs/plans/20260526T224018Z_blahab44_logs/`; as of the `2026-05-27T15:32Z` status sweep: 3 live successes, 10 live failures, 1 dry-run failure, 2 live kitchensink rows still running, and 1 blocked command. Slurm evidence showed exactly 2 active jobs as `ubuntu`, both contamination jobs for the running kitchensinks, with no pending queue. | Post-fix live rows no longer fail on read-only reference conda path; residual failures are now command/runtime-specific or shared writable conda-cache concurrency issues. | Not terminal yet because two kitchensink rows are still running. First full kitchensink success is `ultima_snv_alignstats_kitchensink`. |
| FINAL-001 | Final report | Record final row counts, cluster state, output/export paths, residual blockers, and destructive-action boundary. | OPEN | contract_test | Gate 4 | orchestrator |  |  |  |
