# DayOA Local Evidence, DYEC Dewey Registration, Dewey QEO Import Ledger

Created: 2026-05-28T04:00:18Z

## Objective

Implement the clean ownership split for analysis artifact registration:

- DayOA emits local evidence and workflow provenance only.
- DYEC exports `/fsx` analysis outputs to S3, records the FSx-to-S3 mapping, selects artifacts from explicit command catalog policy, and calls Dewey.
- Dewey registers artifact sets and emits QEO-ready events.

## Gate 0 Inventory Freeze

Controlling ledger: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/plans/20260528T040018Z_dayoa_dyec_dewey_qeo_registration_refactor_ledger.md`

Repositories:

- DYEC: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
  - Branch: `codex/running-nextflow-pipes-doc...origin/codex/running-nextflow-pipes-doc`
  - Dirty at Gate 0: `AGENTS.md`, existing `docs/plans/20260528T003512Z_inflection_controller_rulegraphs/*`, and unrelated untracked artifacts already present.
- DayOA: `/Users/jmajor/projects/daylily/daylily-omics-analysis`
  - Branch: `main...origin/main`
  - Dirty at Gate 0: `AGENTS.md`
- Dewey: `/Users/jmajor/projects/mega_dayhoff/repos_work/dewey`
  - Branch: `codex/security-dewey-share-auth-20260526...origin/codex/security-dewey-share-auth-20260526 [ahead 1]`
  - Dirty at Gate 0: `AGENTS.md`

Sweep commands:

- `rg -l "qeo|dewey|artifact_manifest|ingest_manifest|outbox|storage_root" -S /Users/jmajor/projects/daylily/daylily-omics-analysis | wc -l` -> `25`
- `rg -l "dewey|artifact_registration|fsx_export|destination_s3_uri|source_path|headnode_path" -S daylily_ec tests config | wc -l` -> `42`
- `git -C /Users/jmajor/projects/mega_dayhoff/repos_work/dewey rev-parse 3.0.19^{commit}` -> `f2b6fb3b33eb3701234a88b27e365d6788224cff`

Baseline limits:

- No live AWS, cluster, or Dewey deployment mutation is approved in this thread.
- Existing dirty files outside the new implementation are user/worktree state and must not be reverted.
- No compatibility shims, fallback behavior, legacy aliases, or DayOA-side Dewey/QEO deprecation path are allowed.

## Tracking Rows

| ID | Area/Repo | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0 | DYEC ledger | Record Gate 0 inventory, repo state, sweep counts, assumptions, and live-action limits before runtime code changes. | SUCCESS | feature_implementation | Gate 0 | orchestrator | This ledger records repo states, sweep counts, and live limits. |  | Gate 0 complete before runtime deletion/refactor. |
| A1 | DayOA | Remove DayOA Dewey/QEO registration rules, config, manifests, receipts, and outbox generation with no deprecation path. | SUCCESS | removable_compatibility_debt | Gate 1 | DayOA Agent | Deleted `daylily_omics_analysis/qeo_registration.py`, `workflow/rules/qeo_registration.smk`, `workflow/scripts/register_qeo_artifacts.py`, and `docs/qeo/*`; `workflow/Snakefile` now includes `rules/evidence_manifest.smk`; `rg -n "qeo_registration|register_qeo_artifacts|produce_qeo_|dewey_receipt|qeo_manifest|qeo_ingest_manifest|publish_qeo_ingest_event|DAY_final_multiqc\.artifact_manifest|dewey_url|Dewey token|qeo_" --glob '!docs/plans/**' --glob '!resources/**' --glob '!quarantine/**'` finds only negative test assertions. |  | DayOA no longer has an active Dewey/QEO/S3 registration path. |
| A2 | DayOA | Emit a concrete local evidence manifest from actual analysis-root files with relative paths, sizes, hashes, classification, parser relevance, required flags, and provenance refs. | SUCCESS | feature_implementation | Gate 1 | DayOA Agent | Added `daylily_omics_analysis/evidence_manifest.py`, `workflow/scripts/write_dayoa_evidence_manifest.py`, and `workflow/rules/evidence_manifest.smk`; `produce_multiqc_all` now requires `results/day/<genome>/reports/dayoa_evidence_manifest.json`; focused DayOA tests include relative-path rejection, required-file failure, hashes, classifications, parser relevance, and deterministic output. |  | DayOA evidence manifest is local `/fsx` evidence only and uses analysis-root relative paths. |
| A3 | DayOA | Generate `pipeline_details.md` before run from rulegraph/rule information plus shell command and tool-version extraction. | SUCCESS | feature_implementation | Gate 1 | DayOA Agent | Added `daylily_omics_analysis/pipeline_reports.py`; `bin/day_run` writes `pipeline_details.md` before non-dry-run Snakemake launch; `tests/test_pipeline_reports.py` covers rule parsing, shell command extraction, and version-source reporting with explicit `unavailable`. |  | Pre-run pipeline details report is implemented and tested. |
| A4 | DayOA | Generate beautified Mermaid workflow `.mmd` and PDF for planned, checkpoint, and final states. | SUCCESS | feature_implementation | Gate 1 | DayOA Agent | `daylily_omics_analysis/pipeline_reports.py` writes planned/checkpoint/final Mermaid and invokes required `mmdc` PDF rendering; `bin/day_run` writes planned and checkpoint diagrams before launch, monitors checkpoint diagrams during execution, and writes final success/failure diagrams; tests cover Mermaid content and missing renderer hard failure. |  | Mermaid/PDF generation is implemented with no fallback renderer path. |
| A5 | DYEC | Add explicit per-command `artifact_registration` policy to command catalog. | SUCCESS | config_or_startup_contract | Gate 2 | DYEC Agent | Added `ArtifactRegistrationIdentity` and `ArtifactRegistrationPolicy` in `daylily_ec/repositories.py`; added catalog policy anchor in `config/daylily_available_repositories.yaml` and synced packaged copy; `cmp -s config/daylily_available_repositories.yaml daylily_ec/resources/payload/config/daylily_available_repositories.yaml` passed; `tests/test_repository_catalog.py` covers explicit policy and launch argv. |  | Artifact selection is catalog-driven and commands without a policy are rejected for registration. |
| A6 | DYEC | Extend `fsx_export.yaml` receipt with explicit FSx-to-S3 mapping fields. | SUCCESS | feature_implementation | Gate 1 | DYEC Agent | `daylily_ec/workflow/export_data.py` now writes schema version 4 with `fsx_root`, `s3_root`, `dayoa_analysis_root`, and `dayoa_s3_root`; packaged example `daylily_ec/resources/payload/etc/fsx_export.yaml`, docs, `tests/test_export.py`, and `tests/test_ssm_e2e_runner.py` updated. |  | Export receipts deterministically map DayOA relative paths to S3 roots. |
| A7 | DYEC | After successful export, load DayOA manifest, apply catalog policy, construct Dewey requests, post them, and store receipts. | SUCCESS | feature_implementation | Gate 2 | DYEC Agent | Added `daylily_ec/workflow/dewey_registration.py`; `dyec export`, `dyec workflow launch`, and headnode runner accept artifact-registration command id plus Dewey URL/token env; tests prove exported DayOA manifest loading, S3 URI construction, fake Dewey posts, receipt writing, malformed manifest hard failure, no receipt on failure, and rejection of unused Dewey URL/token options without explicit artifact registration. |  | DYEC owns Dewey registration after successful export; missing manifest, policy, Dewey URL, token env, token, or valid response fails hard. |
| A8 | Dewey | Verify Dewey tag `3.0.19` contracts for registration endpoints and QEO-ready outbox events. | BLOCKED | contract_test | Gate 5 | Dewey Agent | Local tag verification: `git rev-parse 3.0.19^{}` -> `f2b6fb3b33eb3701234a88b27e365d6788224cff`; `git grep` on tag shows `POST /api/v1/artifact-sets/analysis/register`, `POST /api/v1/artifact-sets/multiqc/register`, registration contracts, QEO event contract docs, outbox service, and tests asserting events omit `storage_uri`/`relative_path`. | Live deployed Dewey endpoint, tag, and credentials were not provided or approved in this thread. | Local tag contract is verified; deployed-service verification remains blocked until a Dewey base URL, bearer-token env, and approval to query the live service are provided. |
| A9 | Integration | Add fixture tests covering DayOA manifest plus DYEC export receipt plus Dewey registration request construction. | SUCCESS | contract_test | Gate 5 | Integration Agent | DYEC `python -m pytest -q tests/test_repository_catalog.py tests/test_export.py tests/test_ssm_e2e_runner.py tests/test_cli_registry_v2.py tests/test_script_entrypoints.py` -> `168 passed`; DayOA `python -m pytest -q tests/test_evidence_manifest.py tests/test_pipeline_reports.py tests/test_multiqc_qc_targets.py tests/test_shell_wrapper_contracts.py` -> `37 passed`. |  | Fixture integration proves selected DayOA files become S3-backed Dewey registration requests and receipts through DYEC. |

## Final Terminal-State Report

Updated: 2026-05-28T04:30:28Z

Terminal rows: 10 of 10.

- `SUCCESS`: G0, A1, A2, A3, A4, A5, A6, A7, A9
- `BLOCKED`: A8 deployed Dewey verification only
- `OPEN`, `IN_PROGRESS`, `ATTEMPTING_BUGFIX`: none

Validation commands:

- DYEC: `eval "$(conda shell.zsh hook)" && conda activate DAY-EC && python -m py_compile daylily_ec/repositories.py daylily_ec/workflow/export_data.py daylily_ec/workflow/dewey_registration.py daylily_ec/cli.py daylily_ec/scripts/daylily_run_omics_analysis_headnode.py && python -m pytest -q tests/test_repository_catalog.py tests/test_export.py tests/test_ssm_e2e_runner.py tests/test_cli_registry_v2.py tests/test_script_entrypoints.py` -> `168 passed`
- DayOA: `eval "$(conda shell.zsh hook)" && conda activate DAY-EC && python -m py_compile daylily_omics_analysis/evidence_manifest.py daylily_omics_analysis/pipeline_reports.py workflow/scripts/write_dayoa_evidence_manifest.py && python -m pytest -q tests/test_evidence_manifest.py tests/test_pipeline_reports.py tests/test_multiqc_qc_targets.py tests/test_shell_wrapper_contracts.py` -> `37 passed`
- DayOA removal sweep: only negative assertions remain for old Dewey/QEO registration identifiers.
- DYEC catalog sync: `cmp -s config/daylily_available_repositories.yaml daylily_ec/resources/payload/config/daylily_available_repositories.yaml` -> `catalog copies match`

Objective status: local code and fixture integration are complete. Live Dewey deployment verification is explicitly blocked, not silently substituted by local evidence.
