# Run Directory Mounting Ledger

Date: 2026-05-17

Controlling spec: `docs/LSMC_run_directory_mounting_run_analysis_spec.md`

Ledger status protocol: `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`

## Gate 0 Inventory Freeze

Gate 0 status: `SUCCESS`

### Repositories

| Repo | Path | Branch | Baseline commit | Dirty state |
|---|---|---|---|---|
| DayEC | `/Users/jmajor/projects/daylily/daylily-ephemeral-cluster` | `codex/run-directory-mounts` | `ac127367 2.3.4` | Pre-existing untracked files: `007_detected_visible_noN_indexes.summary.txt`, `007_detected_visible_noN_indexes.tsv`, `007_indexes.tsv`, `007_uncalled_indexes.summary.txt`, `007_uncalled_indexes.tsv`, `config/#daylily_available_repositories.yaml#`, `config/#daylily_cli_global.yaml#`, `docs/LSMC_run_directory_mounting_run_analysis_spec.md`, `qc_vs_qc.tsv`, `reports/stage_three_latest_20260516T130229Z/`, `tmp-export/`. |
| DayOA | `/Users/jmajor/projects/daylily/daylily-omics-analysis` | `codex/dayoa-run-directory-mounts` | `0df89d5 Fix MultiQC staging and Apptainer env setup` | Pre-existing untracked files: `0_7_724/`, `config/day_profiles/slurm/templates/#config.yaml#`. |
| Ursa | `/Users/jmajor/projects/daylily/daylily-ursa` | `codex/run-directory-mounts-ursa` | `039d139 Adopt TapDB explicit target config` | Path was absent at original Gate 0, then became available. Branch created from current checkout. Pre-existing modified files were present before Ursa implementation work and are treated as user-owned. |
| Ursa PR #3 worktree | `/Users/jmajor/.codex/worktrees/run-directory-mounts-ursa-pr3/daylily-ursa` | `codex/run-directory-mounts-ursa-pr3` | `46b5b10 Release Ursa no-fallback auth cutover` | Clean worktree created from `origin pull/3/head` after user directed that Ursa work should build against PR #3. |

### Baseline Tests

| Repo | Command | Result |
|---|---|---|
| DayEC | `source ./activate && python -m pytest tests/test_repository_catalog.py tests/test_stage_samples_from_local_to_headnode.py tests/test_cli_registry_v2.py -q` | `113 passed, 1 failed`; pre-existing failure: packaged repository catalog default ref is `0.7.758`, source catalog default ref is `0.7.763`. |
| DayOA | `conda activate DAY-EC && python -m pytest tests/test_run_qc_reports.py tests/test_bclconvert_multiqc.py -q` | `9 passed`. |

### Live-System Limits

- No default AWS credentials were available: `aws sts get-caller-identity` returned `Unable to locate credentials`.
- `aws configure list-profiles` returned no profiles.
- Staged data cleanup must remain `BLOCKED` until an explicit AWS profile/credential source is available and the exact S3 prefixes can be dry-run listed.
- No live destructive S3 delete and no live FSx DRA create/delete has been approved in this thread after exact effects were restated.

## Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Planning | Create tracked control ledger and record Gate 0 inventory. | `SUCCESS` | `plan_amendment` | Gate 0 | orchestrator | This file; repo status and baseline commands recorded above. |  | Gate 0 inventory recorded before implementation edits. |
| CLEAN-001 | Cleanup | Resolve exact S3 backing prefixes for the nine `remote_stage_*` directories and run `aws s3 rm --recursive --dryrun` only. | `SUCCESS` | `legitimate_safety_handling` | Gate 1 | orchestrator | `AWS_PROFILE=lsmc aws sts get-caller-identity` -> account `108782052779`; candidate scan found all nine prefixes only under `s3://lsmc-dayoa-omics-analysis-us-west-2/data/staged_sample_data/`; `aws s3 rm --recursive --dryrun` logs under `/tmp/dayec-delete-dryrun-20260517T110042Z/`; dry-run total `1374` objects / `6225854149563` bytes. |  | Exact backing S3 prefixes and dry-run counts are resolved; live delete remains separate. |
| CLEAN-002 | Cleanup | Live-delete the nine staged S3 prefixes after dry-run object counts are shown. | `SUCCESS` | `legitimate_safety_handling` | Gate 1 | orchestrator | User replied `delete please` after dry-run totals were shown. Live logs: `/tmp/dayec-delete-live-20260517T110213Z/` and `/tmp/dayec-delete-live-20260517T110245Z/`; deleted `1374` total objects. Final `s3api list-objects-v2` verification returned `0` objects for all nine prefixes. |  | The nine approved S3 staged prefixes were deleted and verified empty. |
| DEC-001 | DayEC | Implement FSx DRA run mount lifecycle and JSON CLI. | `SUCCESS` | `feature_implementation` | Gate 2 | Agent A + orchestrator | `daylily_ec/run_mounts.py`; `daylily_ec/cli.py`; `tests/test_run_mounts.py`; `python -m pytest -q` -> `842 passed, 7 skipped`. |  | `mounts list/create/describe/delete/verify` and `mount rundir` are registered; JSON mode is supported by mount lifecycle commands. |
| DEC-002 | DayEC | Persist local run mount state records under a deterministic state path. | `SUCCESS` | `feature_implementation` | Gate 2 | Agent A + orchestrator | `daylily_ec/run_mounts.py`; state path under `$XDG_CONFIG_HOME/daylily/run_mounts/<region>/<cluster-or-fsx>/<mount_id>.json`; `tests/test_run_mounts.py` -> covered in full suite. |  | Local run mount records are written and reused for list/describe/delete projections. |
| DEC-003 | DayEC | Add mounted-readonly sample staging contract and preserve mounted paths in generated TSVs. | `SUCCESS` | `feature_implementation` | Gate 2 | Agent B | `daylily_ec/stage_samples.py`; `tests/test_stage_samples_from_local_to_headnode.py`; `tests/test_staging_examples.py`; focused matrix -> `108 passed`; full suite -> `842 passed, 7 skipped`. |  | `mounted_readonly` rows validate mount paths and avoid source-byte copy while preserving mounted FASTQ/CRAM paths. |
| DEC-004 | DayEC | Upgrade repository catalog to v2 and add run-analysis command contracts. | `SUCCESS` | `feature_implementation` | Gate 2 | orchestrator | `daylily_ec/repositories.py`; `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`; `config/daylily_available_repositories.yaml`; packaged catalog synced; `python -m pytest tests/test_repository_catalog.py tests/test_cli_registry_v2.py tests/test_script_entrypoints.py -q` -> `115 passed`. |  | Catalog v2 fields are explicit; v1 load migration is limited to sample-analysis defaults; run-analysis commands require `run_context_file`, pass `--run-context-file`, and the launcher writes remote `config/runs.tsv`. |
| DEC-005 | DayEC | Add DayEC unit and CLI tests for mounts, mounted staging, and catalog v2. | `SUCCESS` | `contract_test` | Gate 2 | Agents A/B/C + orchestrator | `tests/test_run_mounts.py`; `tests/test_repository_catalog.py`; mounted staging tests; run-context launch tests; `python -m pytest -q` -> `844 passed, 7 skipped`. |  | DayEC mount, catalog v2, run-context launch, and mounted staging contracts are covered by local tests. |
| DOA-001 | DayOA | Add strict `config/runs.tsv` loading and run context helpers. | `SUCCESS` | `feature_implementation` | Gate 3 | Agent D + orchestrator | `workflow/rules/common.smk`; `tests/test_bclconvert_multiqc.py`; focused tests -> `10 passed`. |  | Required run-context columns are validated; `OUTPUT_ROOT` defaults to `results/runs/<RUNID>`. |
| DOA-002 | DayOA | Refactor run QC outputs to `results/runs/<runid>/run_qc/...` and support explicit mounted Illumina mode. | `SUCCESS` | `feature_implementation` | Gate 3 | Agent D + orchestrator | `workflow/rules/run_qc_reports.smk`; `tests/test_run_qc_reports.py`; focused tests -> `10 passed`. |  | Illumina mounted mode reads `RUN_DIR`; S3 mode requires explicit `SOURCE_S3_URI`, `PROFILE`, and `REGION`; outputs use run-scoped `summary.html`, `summary.tsv`, and `multiqc_report.html`. |
| DOA-003 | DayOA | Refactor BCL Convert outputs to `results/runs/<runid>/bclconvert/...` with generated units under `tables/`. | `SUCCESS` | `feature_implementation` | Gate 3 | orchestrator | `workflow/rules/bclconvert.smk`; `tests/test_bclconvert_multiqc.py`; `bash tests/test_bclconvert_bootstrap.sh` -> `11 passed`. |  | Run-context mode writes BCL Convert outputs under `results/runs/<runid>/bclconvert/`; explicit non-run-context bootstrap behavior remains covered. |
| DOA-004 | DayOA | Add DayOA parser, dry-run, and output path tests for run context, run QC, and BCL Convert. | `SUCCESS` | `contract_test` | Gate 3 | Agent D + orchestrator | `python -m pytest tests/test_run_qc_reports.py tests/test_bclconvert_multiqc.py -q` -> `10 passed`; `bash tests/test_bclconvert_bootstrap.sh` -> `11 passed`; `snakemake` and `python -m snakemake` unavailable locally. |  | Static/parser/output contract tests pass; actual Snakemake dry-run remains unavailable in this local shell because Snakemake is not installed. |
| URSA-001 | Ursa | Create `codex/run-directory-mounts-ursa` in `/Users/jmajor/projects/daylily/daylily-ursa`. | `NO_LONGER_NEEDED` | `config_or_startup_contract` | Gate 4 | Agent E | Gate 0 path check found the target path absent; later user made the checkout available. |  | Superseded by reopen row `URSA-001R`. |
| URSA-002 | Ursa | Add run mount and run analysis records, client wrappers, API routes, and UI split. | `NO_LONGER_NEEDED` | `feature_implementation` | Gate 4 | Agent E | Original row was blocked only by absent checkout; the checkout is now available. |  | Superseded by reopen row `URSA-002R`. |
| DOC-001 | Docs | Update DayEC/DayOA docs and examples for run mounts, run analysis, BCL Convert, and cleanup safety. | `SUCCESS` | `feature_implementation` | Gate 5 | orchestrator | `docs/cli_reference.md`; DayOA `docs/ops/multiqc_qc_targets.md`, `docs/ops/tests.md`, `docs/catalog_of_tools.md`; `git diff --check` passed in both repos. |  | Operator docs describe mount lifecycle commands, mounted staging fields, run-context QC, and BCL Convert run outputs. |
| QA-001 | QA | Run focused and broad local tests across implemented DayEC, DayOA, and Ursa PR #3 surfaces. | `SUCCESS` | `contract_test` | Gate 5 | orchestrator | DayEC `python -m pytest -q` -> `844 passed, 7 skipped`; DayOA focused pytest -> `10 passed`; DayOA BCL shell suite -> `11 passed`; Ursa PR #3 `python -m pytest -q` -> `312 passed, 2 skipped`; Ursa PR #3 `python -m ruff check ...` and `git diff --check` passed. |  | Local validation is green except DayOA Snakemake dry-run could not run because Snakemake is unavailable in this shell. |
| LIVE-001 | Live QA | Run live FSx DRA smoke on a designated non-production cluster. | `BLOCKED` | `legitimate_safety_handling` | Gate 5 | orchestrator | No live AWS profile/cluster and no explicit approval. | Live AWS mutation requires explicit approval and credentials. | Unblock by providing target and approval after dry-run/local tests pass. |
| REL-001 | Release | Prepare major bare-semver release plan: DayEC `3.0.0`, DayOA next major from non-`v` tags, Ursa next major from resolved repo. | `SUCCESS` | `plan_amendment` | Gate 5 | orchestrator | Non-`v` semver tags inspected: DayEC latest `2.3.4`; DayOA latest `0.7.763`; Ursa implementation target is now PR #3 base `46b5b10` in `/Users/jmajor/.codex/worktrees/run-directory-mounts-ursa-pr3/daylily-ursa`. |  | Planned release targets are DayEC `3.0.0`, DayOA `1.0.0`, and Ursa `3.0.0` against the PR #3 worktree. |

## Gate 4 Ursa Reopen

After the original terminal report, the user made `/Users/jmajor/projects/daylily/daylily-ursa` available. The orchestrator created `codex/run-directory-mounts-ursa` and ran a read-only Ursa pattern inspection. The active checkout already had unrelated modified files on entry, so those user-owned edits must not be reverted. The user then directed that Ursa implementation should build against Ursa PR #3; the orchestrator fetched `origin pull/3/head` as `codex/pr-3-base` and created a clean implementation worktree at `/Users/jmajor/.codex/worktrees/run-directory-mounts-ursa-pr3/daylily-ursa` on `codex/run-directory-mounts-ursa-pr3`.

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| URSA-001R | Ursa | Create `codex/run-directory-mounts-ursa` in `/Users/jmajor/projects/daylily/daylily-ursa` after the checkout became available. | `SUCCESS` | `config_or_startup_contract` | Gate 4 | orchestrator | `git status --short --branch` -> `## codex/run-directory-mounts-ursa`; baseline commit `039d139`; pre-existing modified files recorded in current repo status. |  | Ursa branch is now present; original `URSA-001` blocker is superseded by this reopen row. |
| URSA-002R | Ursa | Implement run mount records, run-analysis job records, JSON-only DayEC client wrappers, API routes, client contracts, and split run-analysis UI flow. | `SUCCESS` | `feature_implementation` | Gate 4 | Agent E + orchestrator | PR #3 worktree `/Users/jmajor/.codex/worktrees/run-directory-mounts-ursa-pr3/daylily-ursa` on `codex/run-directory-mounts-ursa-pr3`: added `RunDirectoryMountRecord`, `RunAnalysisJobRecord`, DayEC JSON mount wrappers, `/api/v1/run-mounts`, `/api/v1/run-analysis-commands`, `/api/v1/run-analysis-jobs`, and `/run-analysis` GUI split. Verification: `python -m pytest -q` -> `312 passed, 2 skipped`; `python -m ruff check ...` -> `All checks passed`; `git diff --check` passed. |  | Sample analysis and run analysis now use separate API/UI/job surfaces; existing staging and sample-analysis contracts are not overloaded. |
| URSA-003R | Ursa | Amend Gate 4 implementation base to Ursa PR #3 instead of the dirty local checkout. | `SUCCESS` | `plan_amendment` | Gate 4 | orchestrator | `git fetch origin pull/3/head:codex/pr-3-base --force`; `git worktree add -b codex/run-directory-mounts-ursa-pr3 /Users/jmajor/.codex/worktrees/run-directory-mounts-ursa-pr3/daylily-ursa codex/pr-3-base`; worktree `git status --short --branch` -> `## codex/run-directory-mounts-ursa-pr3`. |  | Ursa implementation is redirected to PR #3 without modifying or reverting user-owned changes in `/Users/jmajor/projects/daylily/daylily-ursa`. |

## Status Counts

- `SUCCESS`: 18
- `OPEN`: 0
- `BLOCKED`: 1
- `NO_LONGER_NEEDED`: 2
- `IN_PROGRESS`: 0
- `ATTEMPTING_BUGFIX`: 0
- `FAIL`: 0

## Final Terminal-State Report

- Terminal rows: yes. All rows are now `SUCCESS`, `BLOCKED`, or `NO_LONGER_NEEDED`; there are no `OPEN` or `IN_PROGRESS` rows.
- Objective complete: no. Local DayEC, DayOA, and Ursa PR #3 implementation rows are complete and tested, staged-data cleanup is complete, and live FSx DRA smoke remains blocked.
- Cleanup: the nine approved `lsmc-dayoa-omics-analysis-us-west-2` staged prefixes were deleted after dry-run evidence and separate user confirmation; final object counts are zero.
- Ursa status: the original checkout `/Users/jmajor/projects/daylily/daylily-ursa` remains dirty with user-owned changes; implementation is complete in the PR #3 worktree `/Users/jmajor/.codex/worktrees/run-directory-mounts-ursa-pr3/daylily-ursa` on `codex/run-directory-mounts-ursa-pr3`.
- Live AWS blocker: no live DRA smoke was attempted because live AWS mutation requires target credentials and a separate explicit approval.
