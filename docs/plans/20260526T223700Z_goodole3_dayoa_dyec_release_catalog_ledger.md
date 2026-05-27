# Goodole3 DayOA/DYEC Release And Catalog Validation Ledger

Date opened: 2026-05-27T00:15:20Z

Controlling request: implement the Goodole3 DayOA/DYEC release and catalog validation plan, starting no earlier than 2026-05-26T22:37Z, using exactly three worker agents.

Ledger path: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/plans/20260526T223700Z_goodole3_dayoa_dyec_release_catalog_ledger.md`

Cluster request path: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/plans/20260526T223700Z_goodole3_cluster_request.yaml`

## Gate 0 Inventory

- Start gate: `date -u` returned `2026-05-27T00:15:20Z`; `TZ=America/Los_Angeles date` returned `2026-05-26 17:15:20 PDT`, which is after the required start time `2026-05-26T22:37Z`.
- Instructions read: `/Users/jmajor/.agents/AGENTS.md`, `/Users/jmajor/.codex/AGENTS.md`, `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`, DayOA `AGENTS.md`, and DYEC `AGENTS.md`.
- Worker agents spawned exactly as requested:
  - Agent 1 DayOA release validation: `019e66c9-b3f8-74e1-8b41-807913afa2f0`.
  - Agent 2 DYEC pin/self-pin and cluster readiness: `019e66c9-cadf-7253-a2cc-4588db3f983f`.
  - Agent 3 catalog validation readiness and failed-row bugfix support: `019e66c9-de8b-7590-b502-ef2f22fe3d9c`.
- DayOA repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`, remote `git@github.com:Daylily-Informatics/daylily-omics-analysis.git`, branch `main`, HEAD `1b103c7c66a8f04d94c1feab7f8e591f5a3dd4b8`, describe `2.0.2-dirty`, status `## main...origin/main`.
- DayOA dirty state after `git fetch --tags origin`: modified `tests/test_giab_qc_contracts.py`, modified `workflow/rules/peddy.smk`, untracked `bin/util/write_peddy_low_data_outputs.py`, untracked `tests/test_peddy_low_data_outputs.py`. Diffstat: `2 files changed, 26 insertions(+), 5 deletions(-)` plus 2 untracked files.
- DayOA latest fetched non-`v` semver tag: `2.0.2`. Plan amendment: the original plan expected `2.0.2`, but it already exists on `origin/main`; the next DayOA release tag for this dirty state is `2.0.3`.
- DYEC repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`, remote `git@github.com:Daylily-Informatics/daylily-ephemeral-cluster.git`, branch `main`, HEAD `8debeb68295d01b6d9c8a317d6666a3fcd150370`, describe `5.0.2-dirty`, status `## main...origin/main`.
- DYEC dirty state after `git fetch --tags origin`: modified `docs/plans/20260526T224018Z_blahab44_catalog_validation_ledger.md`; 100 untracked `docs/plans/20260526T224018Z_blahab44*` validation artifacts from the pre-existing `blahab44` run. These are not Goodole3 artifacts and are not staged by default.
- DYEC catalog pins before this run: source and packaged `config/daylily_available_repositories.yaml` pin DayOA repository `default_ref: 2.0.2` and all DayOA command `git_tag: 2.0.2`.
- DYEC self-pins before this run: source and packaged `daylily_cli_global.yaml` pin `git_ephemeral_cluster_repo_tag: 5.0.2` and `git_ephemeral_cluster_repo_release_tag: 5.0.2`.
- DYEC latest fetched non-`v` semver tag: `5.0.2`. Plan amendment: the original plan expected intermediate `5.0.2` and final `5.0.3`, but `5.0.2` already exists; the recomputed DYEC intermediate tag is `5.0.3` and final tag is `5.0.4`.
- AWS identity: `AWS_PROFILE=lsmc aws sts get-caller-identity` returned account `108782052779`, ARN `arn:aws:iam::108782052779:root`.
- ParallelCluster baseline: `AWS_PROFILE=lsmc pcluster list-clusters --region us-west-2` listed `blahab44` and `jem-bucktst3` as `CREATE_COMPLETE`, and `jem-bucktst2`/`jem-bucktst1` as failed rollback stacks.
- Goodole3 absence proof: `AWS_PROFILE=lsmc pcluster describe-cluster --cluster-name goodole3 --region us-west-2` returned message `Cluster 'goodole3' does not exist or belongs to an incompatible ParallelCluster major version.`
- Tooling baseline: `pcluster version -> 3.13.2`; `aws --version -> aws-cli/1.44.69 Python/3.12.12 Darwin/25.1.0 botocore/1.42.79`.
- Low-coverage inputs exist at `docs/plans/20260525T063158Z_tstver411b_inputs/`; existing 0.1x Illumina artifact exists at `docs/plans/20260526T213400Z_jem_bucktst3_ilmn_0p1x_kitchensink/`.
- Non-destructive boundary: live cluster creation and catalog job launch are authorized by the controlling plan; cluster deletion, teardown, stack deletion, or other destructive AWS actions are not authorized.

## Planned Release Pins

- `DAYOA_TAG=2.0.3`
- `DYEC_INTERMEDIATE_TAG=5.0.3`
- `DYEC_FINAL_TAG=5.0.4`
- Post-live amendment: `DAYOA_PATCH_TAG=2.0.4` and `DYEC_PATCH_TAG=5.0.5`.
  The 0.1x Goodole3/Jem validation exposed a same-file `.ped` copy bug in
  DayOA low-data Peddy placeholder generation after `2.0.3` was already
  published. Catalog validation now uses DayOA `2.0.4` through DYEC `5.0.5`.
- Post-export amendment: DYEC export fixes were published as `5.0.8` and
  `5.0.9`. Commit `56b01450` (`5.0.8`) adds explicit output export bucket
  support and tolerant cleanup for workflow-created temporary export DRAs.
  Commit `61cef3d2` (`5.0.9`) grants the headnode FSx DRA/export task
  permissions through source and packaged `pcluster_env.yml`.
- User amendment at 2026-05-27T03:21Z: switch active validation launches to
  `day-clone -t 2.0.6` / DYEC `--git-tag 2.0.6`. The serial validation driver
  now uses `GIT_TAG=2.0.6`, `REMOTE_BASE=/home/ubuntu/ds/gd3serialksv206`,
  and JSONL evidence path `docs/plans/20260527T032100Z_goodole3_serial_kitchensink_v206_runs.jsonl`.
  The prior `2.0.5` Ultima run `gd3ks1-ug5x` was interrupted at the user's
  request and recorded `exit_code=1`; its analysis directory was not deleted.
- Ultima low-coverage input note: the active Ultima kitchensink units file
  `docs/plans/20260526T224018Z_blahab44_inputs/generated/ultima_snv_alignstats_kitchensink/20260526T233423Z_7f724d71_units.tsv`
  sets `EXPERIMENTID=5x` and points to
  `/fsx/references/genomic_data/organism_reads_slim/cram/H_sapiens/giab/agbt_2026/ug/HG003_5x.cleaned.cram`.
  It is low coverage, but not the 0.1x Illumina input.
- User amendment at 2026-05-27T05:28Z: run three live `day-clone`
  sample-analysis jobs concurrently, then increase to four after the first
  three v206 rows are complete if `/fsx` has no space pinch. Driver
  `docs/plans/20260527T020500Z_goodole3_serial_kitchensink_driver.py` now has
  `INITIAL_MAX_ACTIVE=3`, `BUMPED_MAX_ACTIVE=4`, `MIN_FREE_GIB_FOR_BUMP=1024`,
  and `MAX_USED_PCT_FOR_BUMP=80`; active evidence at `2026-05-27T05:28:22Z`
  showed `active_count=3`, `/fsx` `used_pct=3`, and `avail_gib=4345.2`.
- `AWS_PROFILE=lsmc`
- `REGION=us-west-2`
- `REGION_AZ=us-west-2d`
- `CLUSTER_NAME=goodole3`

## Catalog Commands

| # | Command ID | Class | Planned DayOA Tag | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | `illumina_snv_alignstats` | sample_analysis | `2.0.6` | RUNNING | `gd3v206-ilmnbase5x` launched with `--git-tag 2.0.6` at `2026-05-27T05:26:48Z`; status at `2026-05-27T05:28:14Z` showed `exit_code=null`; output prefix will be `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ilmnbase5x/`. |
| 2 | `illumina_snv_alignstats_relatedness_vep_multiqc` | sample_analysis | `2.0.6` | SUCCESS | `gd3v206-ilmn5x` completed at `2026-05-27T04:00:16Z` with `exit_code=0`; export task `task-0f19b0e256839a19a` succeeded `3794/3794`, failed `0`; temporary DRA removed; output prefix `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ilmn5x/`. |
| 3 | `ultima_snv_alignstats` | sample_analysis | `2.0.6` | OPEN | Low-coverage input source pending bounded-concurrency slot. |
| 4 | `ultima_snv_alignstats_kitchensink` | sample_analysis | `2.0.6` | SUCCESS | `gd3v206-ug5x` completed at `2026-05-27T04:33:52Z` with `exit_code=0`; export task `task-09ec78aca28507a30` succeeded `3266/3266`, failed `0`; temporary DRA `dra-0b277cbee8929b3af` removed; output prefix `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ug5x/`. |
| 5 | `ont_snv_alignstats` | sample_analysis | `2.0.6` | OPEN | Low-coverage input source pending bounded-concurrency slot. |
| 6 | `ont_snv_alignstats_kitchensink` | sample_analysis | `2.0.6` | RUNNING | `gd3v206-ont5x` launched with `--git-tag 2.0.6` at `2026-05-27T04:38:50Z`; active Slurm work includes `sent_snv_ont`, `gatk_contam`, and `calc_coverage_evenness`; output prefix will be `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ont5x/`. |
| 7 | `pacbio_snv_alignstats` | sample_analysis | `2.0.6` | OPEN | Low-coverage input source pending bounded-concurrency slot. |
| 8 | `roche_snv_alignstats` | sample_analysis | `2.0.6` | OPEN | Low-coverage input source pending bounded-concurrency slot. |
| 9 | `hybrid_ilmn_ont_snv` | sample_analysis | `2.0.6` | OPEN | Low-coverage input source pending bounded-concurrency slot. |
| 10 | `hybrid_ilmn_ont_snv_kitchensink` | sample_analysis | `2.0.6` | RUNNING | `gd3v206-hio5x` launched with `--git-tag 2.0.6` at `2026-05-27T05:21:46Z`; status at `2026-05-27T05:28:05Z` showed `exit_code=null`; output prefix will be `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-hio5x/`. |
| 11 | `hybrid_ultima_ont_snv` | sample_analysis | `2.0.6` | OPEN | Low-coverage input source pending bounded-concurrency slot. |
| 12 | `complete_genomics_mgi_snv_concordance` | sample_analysis | `2.0.6` | OPEN | Candidate input `complete_genomics_mgi_hg003_candidate_blocked.tsv`; must fail hard if mate-pair contract remains unverifiable. |
| 13 | `illumina_run_qc` | run_analysis | `2.0.6` | OPEN | Low-coverage run-context source pending run. |
| 14 | `illumina_bclconvert` | run_analysis | `2.0.6` | OPEN | Low-coverage run-context source pending run. |
| 15 | `illumina_run_qc_bclconvert` | run_analysis | `2.0.6` | OPEN | Low-coverage run-context source pending run. |
| 16 | `ont_run_qc` | run_analysis | `2.0.6` | OPEN | Low-coverage run-context source pending run. |
| 17 | `ultima_run_qc` | run_analysis | `2.0.6` | OPEN | Candidate input `ultima_run_context_candidate.tsv`; must fail hard if no valid run context is available. |

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G0-001 | Gate 0 | Record start-time gate, repo state, fetched tags, AWS identity, pcluster baseline, goodole3 absence, worker-agent assignment, version amendment, and live-system boundary. | SUCCESS | plan_amendment | Gate 0 | orchestrator | Gate 0 section above; `git fetch --tags` completed in both repos; `goodole3` absence recorded. |  | Gate 0 is complete; version plan amended from fetched current source. |
| REL-001 | DayOA release | Test, commit, push, annotated-tag, and push the DayOA dirty peddy low-data changes as `2.0.3`. | SUCCESS | contract_test | Gate 1 | Agent 1 + orchestrator | Agent 1 reported `git diff --check -> 0`, focused tests `72 passed`, full tests `208 passed`; orchestrator reran `git diff --check`, focused tests `72 passed`, full tests `208 passed`; commit `970f4e1a8223bc594afe2b48eadf5c251cc65623` pushed to `origin/main`; annotated tag `2.0.3` pushed and remote readback showed `refs/tags/2.0.3`. |  | DayOA peddy low-data handling is published and addressable by tag `2.0.3`. |
| REL-002 | DYEC release A | Update source and packaged DayOA catalog pins from `2.0.2` to `2.0.3`, include Goodole3 plan artifacts, validate parity/tests, commit, push, annotated-tag `5.0.3`, and push tag. | SUCCESS | config_or_startup_contract | Gate 2 | Agent 2 + orchestrator | Source and packaged catalogs, README, docs, and catalog tests changed to `2.0.3`; catalog `cmp` passed; focused DYEC tests passed `234 passed`; `git diff --check` passed; commit `875b360f0fe38677f1d3145c930a166113b223c1` pushed to `origin/main`; annotated tag `5.0.3` pushed. |  | DYEC catalog resolves all DayOA command clones to tag `2.0.3`. |
| REL-003 | DYEC release B | Update source and packaged self-pins from `5.0.2` to final `5.0.4`, validate parity/tests/ruff/diff-check, commit, push, annotated-tag `5.0.4`, and push tag. | SUCCESS | config_or_startup_contract | Gate 3 | Agent 2 + orchestrator | Source and packaged self-pins changed to `5.0.4`; global-config `cmp` passed; required pytest subset passed `104 passed`; initial `ruff check .` failed on unused imports/local in tracked files, minimal cleanup applied, rerun `ruff check . -> All checks passed`; `git diff --check` passed; commit `2f6cc5027dff492c331868955398c0451947bfb5` and annotated tag `5.0.4` are present on `origin/main`. |  | DYEC `5.0.4` was published and used to build `goodole3`. |
| REL-004 | DayOA patch release | Publish the same-file Peddy low-data `.ped` copy fix after live 0.1x validation exposed the bug. | SUCCESS | contract_test | Gate 4 | orchestrator | `git diff --check` passed; `pytest -q tests/test_peddy_low_data_outputs.py tests/test_giab_qc_contracts.py::test_peddy_rule_hard_fails_and_does_not_unconditionally_mark_done -> 2 passed`; commit `7d7ac739c408a6a77a9cf55d92667ebc7323b9a8` pushed to `origin/main`; annotated tag `2.0.4` pushed and read back from `origin`. |  | DayOA `2.0.4` supersedes `2.0.3` for remaining catalog validation. |
| REL-005 | DYEC patch release | Repin source and packaged DayOA catalog entries from `2.0.3` to `2.0.4`, advance source and packaged DYEC self-pins from `5.0.4` to `5.0.5`, validate, commit, push, and tag. | SUCCESS | config_or_startup_contract | Gate 4 | orchestrator | Source/package catalog parity passed; source/package global-config parity passed; `pytest -q tests/test_repository_catalog.py tests/test_cli_registry_v2.py tests/test_packaged_defaults.py tests/test_resources_extraction.py tests/test_workflow.py tests/test_run_mounts.py tests/test_stage_samples_from_local_to_headnode.py tests/test_headnode_init.py tests/test_headnode_readiness.py tests/test_s3.py -> 282 passed`; `ruff check . -> All checks passed`; `git diff --check` passed. |  | DYEC catalog and self-pins are ready to publish as `5.0.5`; this row's release commit/tag publication is recorded by the surrounding git history. |
| REL-006 | DYEC export patch release | Publish export destination S3 URI support and temporary-DRA cleanup behavior after live export repair showed missing export-bucket access and DRA cleanup sensitivity. | SUCCESS | config_or_startup_contract | Gate 4 | orchestrator | Commit `56b01450` pushed and annotated tag `5.0.8` pushed; focused tests `214 passed`; full DYEC tests `900 passed, 7 skipped`; `ruff check .`; `git diff --check`; config parity checks passed. | Headnode could not export Goodole3 results without explicit output bucket and robust temporary DRA cleanup behavior. | DYEC `5.0.8` fixes workflow export command behavior. |
| REL-007 | DYEC headnode IAM patch release | Grant the headnode FSx DRA and data repository task permissions required for live result exports, and self-pin source and packaged config to the new tag. | SUCCESS | config_or_startup_contract | Gate 4 | orchestrator | Commit `61cef3d2` pushed and annotated tag `5.0.9` pushed; source/package `config/day_cluster/pcluster_env.yml` grants FSx DRA/task actions; source/package self-pins are `5.0.9`; `cmp` checks passed; pytest subset `85 passed`; `ruff check .`; `git diff --check`. | Headnode role lacked FSx DRA/export task permissions. | DYEC `5.0.9` is the installed/configured cluster-side DYEC release for export validation. |
| CLU-001 | Cluster create | Create `goodole3` from final DYEC tag `5.0.4`, then verify `CREATE_COMPLETE`, compute fleet `RUNNING`, SSM as `ubuntu`, `/fsx`, required CLI tools, Slurm, and installed/configured final tag. | SUCCESS | feature_implementation | Gate 3 | Agent 2 + orchestrator | `goodole3` exists with headnode `i-0bd631af238bfac56`, FSx `fs-03509c3c3fcf86610`, state file `/Users/jmajor/.config/daylily/state_goodole3_20260527002251.json`; cluster reached `CREATE_COMPLETE`, compute fleet `RUNNING`, SSM as `ubuntu`, `/fsx` mounted, and required tools present. |  | Cluster remains running; no destructive delete/teardown is authorized. |
| CAT-001 | Catalog validation | Run dry-run then live validation for all 17 catalog commands with low-coverage inputs; failed rows must enter `ATTEMPTING_BUGFIX` before `FAIL`; publish new tags if repo-grounded fixes are required. | RUNNING | contract_test | Gate 4 | Agent 3 + orchestrator | Current bounded-concurrency `2.0.6` driver evidence is in `docs/plans/20260527T032100Z_goodole3_serial_kitchensink_v206_runs.jsonl`; `gd3v206-ilmn5x` and `gd3v206-ug5x` are terminal success with exports; active sessions are `gd3v206-ont5x`, `gd3v206-hio5x`, and `gd3v206-ilmnbase5x`; driver evidence at `2026-05-27T05:28:22Z` showed `active_count=3`, `max_active=3`, `/fsx` `used_pct=3`, `avail_gib=4345.2`; headnode `squeue` at the same checkpoint had 11 rows. Original all-17 command objective is not yet terminal. |  | Continue bounded v206 rows; driver will bump to `max_active=4` after the first three v206 rows complete if `/fsx` remains above 1024 GiB available and at or below 80% used. |
| FINAL-001 | Final report | Record terminal status counts, pushed refs, cluster state, command matrix, result paths, remaining blockers, and destructive-action boundary. | OPEN | contract_test | Gate 5 | orchestrator |  |  |  |
