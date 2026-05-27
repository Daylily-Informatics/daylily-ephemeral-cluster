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
- `AWS_PROFILE=lsmc`
- `REGION=us-west-2`
- `REGION_AZ=us-west-2d`
- `CLUSTER_NAME=goodole3`

## Catalog Commands

| # | Command ID | Class | Planned DayOA Tag | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | `illumina_snv_alignstats` | sample_analysis | `2.0.3` | OPEN | Low-coverage input source pending run. |
| 2 | `illumina_snv_alignstats_relatedness_vep_multiqc` | sample_analysis | `2.0.3` | OPEN | Low-coverage input source pending run. |
| 3 | `ultima_snv_alignstats` | sample_analysis | `2.0.3` | OPEN | Low-coverage input source pending run. |
| 4 | `ultima_snv_alignstats_kitchensink` | sample_analysis | `2.0.3` | OPEN | Low-coverage input source pending run. |
| 5 | `ont_snv_alignstats` | sample_analysis | `2.0.3` | OPEN | Low-coverage input source pending run. |
| 6 | `ont_snv_alignstats_kitchensink` | sample_analysis | `2.0.3` | OPEN | Low-coverage input source pending run. |
| 7 | `pacbio_snv_alignstats` | sample_analysis | `2.0.3` | OPEN | Low-coverage input source pending run. |
| 8 | `roche_snv_alignstats` | sample_analysis | `2.0.3` | OPEN | Low-coverage input source pending run. |
| 9 | `hybrid_ilmn_ont_snv` | sample_analysis | `2.0.3` | OPEN | Low-coverage input source pending run. |
| 10 | `hybrid_ilmn_ont_snv_kitchensink` | sample_analysis | `2.0.3` | OPEN | Low-coverage input source pending run. |
| 11 | `hybrid_ultima_ont_snv` | sample_analysis | `2.0.3` | OPEN | Low-coverage input source pending run. |
| 12 | `complete_genomics_mgi_snv_concordance` | sample_analysis | `2.0.3` | OPEN | Candidate input `complete_genomics_mgi_hg003_candidate_blocked.tsv`; must fail hard if mate-pair contract remains unverifiable. |
| 13 | `illumina_run_qc` | run_analysis | `2.0.3` | OPEN | Low-coverage run-context source pending run. |
| 14 | `illumina_bclconvert` | run_analysis | `2.0.3` | OPEN | Low-coverage run-context source pending run. |
| 15 | `illumina_run_qc_bclconvert` | run_analysis | `2.0.3` | OPEN | Low-coverage run-context source pending run. |
| 16 | `ont_run_qc` | run_analysis | `2.0.3` | OPEN | Low-coverage run-context source pending run. |
| 17 | `ultima_run_qc` | run_analysis | `2.0.3` | OPEN | Candidate input `ultima_run_context_candidate.tsv`; must fail hard if no valid run context is available. |

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G0-001 | Gate 0 | Record start-time gate, repo state, fetched tags, AWS identity, pcluster baseline, goodole3 absence, worker-agent assignment, version amendment, and live-system boundary. | SUCCESS | plan_amendment | Gate 0 | orchestrator | Gate 0 section above; `git fetch --tags` completed in both repos; `goodole3` absence recorded. |  | Gate 0 is complete; version plan amended from fetched current source. |
| REL-001 | DayOA release | Test, commit, push, annotated-tag, and push the DayOA dirty peddy low-data changes as `2.0.3`. | SUCCESS | contract_test | Gate 1 | Agent 1 + orchestrator | Agent 1 reported `git diff --check -> 0`, focused tests `72 passed`, full tests `208 passed`; orchestrator reran `git diff --check`, focused tests `72 passed`, full tests `208 passed`; commit `970f4e1a8223bc594afe2b48eadf5c251cc65623` pushed to `origin/main`; annotated tag `2.0.3` pushed and remote readback showed `refs/tags/2.0.3`. |  | DayOA peddy low-data handling is published and addressable by tag `2.0.3`. |
| REL-002 | DYEC release A | Update source and packaged DayOA catalog pins from `2.0.2` to `2.0.3`, include Goodole3 plan artifacts, validate parity/tests, commit, push, annotated-tag `5.0.3`, and push tag. | SUCCESS | config_or_startup_contract | Gate 2 | Agent 2 + orchestrator | Source and packaged catalogs, README, docs, and catalog tests changed to `2.0.3`; catalog `cmp` passed; focused DYEC tests passed `234 passed`; `git diff --check` passed; commit `875b360f0fe38677f1d3145c930a166113b223c1` pushed to `origin/main`; annotated tag `5.0.3` pushed. |  | DYEC catalog resolves all DayOA command clones to tag `2.0.3`. |
| REL-003 | DYEC release B | Update source and packaged self-pins from `5.0.2` to final `5.0.4`, validate parity/tests/ruff/diff-check, commit, push, annotated-tag `5.0.4`, and push tag. | IN_PROGRESS | config_or_startup_contract | Gate 3 | Agent 2 + orchestrator | Source and packaged self-pins changed to `5.0.4`; global-config `cmp` passed; required pytest subset passed `104 passed`; initial `ruff check .` failed on unused imports/local in tracked files, minimal cleanup applied, rerun `ruff check . -> All checks passed`; `git diff --check` passed. Commit/tag pending. |  |  |
| CLU-001 | Cluster create | Create `goodole3` from final DYEC tag `5.0.4`, then verify `CREATE_COMPLETE`, compute fleet `RUNNING`, SSM as `ubuntu`, `/fsx`, required CLI tools, Slurm, and installed/configured final tag. | OPEN | feature_implementation | Gate 3 | Agent 2 + orchestrator | `goodole3` does not exist; cluster request YAML created from `jem-bucktst3` shape with only cluster name changed. |  |  |
| CAT-001 | Catalog validation | Run dry-run then live validation for all 17 catalog commands with low-coverage inputs; failed rows must enter `ATTEMPTING_BUGFIX` before `FAIL`; publish new tags if repo-grounded fixes are required. | OPEN | contract_test | Gate 4 | Agent 3 + orchestrator | Input directories exist; command matrix initialized above; execution pending final cluster readiness. |  |  |
| FINAL-001 | Final report | Record terminal status counts, pushed refs, cluster state, command matrix, result paths, remaining blockers, and destructive-action boundary. | OPEN | contract_test | Gate 5 | orchestrator |  |  |  |
