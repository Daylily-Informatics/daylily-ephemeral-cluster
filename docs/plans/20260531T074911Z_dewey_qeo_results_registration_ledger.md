# Dewey/QEO Results Registration Ledger

Controlling plan: user-approved "Ledgered Dewey Registration and QEO MultiQC Ingest Trial" from 2026-05-31.
Ledger path: `docs/plans/20260531T074911Z_dewey_qeo_results_registration_ledger.md`

## Gate 0 Inventory Freeze

- DYEC repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
  - Branch/status: `codex/dyec-dewey-registration-refactor-20260528...origin/codex/dyec-dewey-registration-refactor-20260528`; pre-existing dirty files include README/docs/headnode script/tests and `docs/plans/20260531T061528Z_*`.
- DayOA repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`
  - Branch/status: `codex/dayoa-local-evidence-dewey-refactor-20260528...origin/codex/dayoa-local-evidence-dewey-refactor-20260528`; pre-existing dirty files include README/docs, MultiQC/run-QC rules/tests, and `workflow/scripts/prepare_bclconvert_demux_fastqc_inputs.py`.
- Dewey repo: `/Users/jmajor/projects/mega_dayhoff/repos_work/dewey`
  - Branch/status: `codex/inf6-deploy-formalization-20260528...origin/codex/inf6-deploy-formalization-20260528`; clean at Gate 0.
- QEO repo: `/Users/jmajor/projects/lsmc/qeo`
  - Branch/status: `codex/inf6-deploy-formalization-20260528...origin/codex/inf6-deploy-formalization-20260528`; clean at Gate 0.
- Instructions read: `/Users/jmajor/.agents/AGENTS.md`, `/Users/jmajor/.codex/AGENTS.md`, local `AGENTS.md`, `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`, DayOA/Dewey/QEO `AGENTS.md`, fallback and AWS destructive-change memories.
- Sweep evidence:
  - `rg dewey_registration|artifact_registration|multiqc|evidence_manifest|qeo|dispatch_qeo|outbox|artifact_set daylily_ec tests docs config -S`
  - `sed` inspections of `daylily_ec/workflow/dewey_registration.py`, `daylily_ec/workflow/export_data.py`, `daylily_ec/repositories.py`, `daylily_ec/cli.py`, `tests/test_export.py`, and `config/daylily_available_repositories.yaml`.
- Live read-only AWS identity: `AWS_PROFILE=lsmc aws sts get-caller-identity` -> account `108782052779`, ARN `arn:aws:iam::108782052779:root`.
- Trial exported prefixes:
  - `s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test/ubuntu/ccv20260529r30_illumina_snv_alignstats_relatedness_vep_multiqc/`
  - `s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test/ubuntu/ccv20260530r50_illumina_hg002_kitchensink_multiqc/`
  - `s3://lsmc-ssf-sequencing-data/derived/validation/dyec-test/ubuntu/ccv20260530r57_illumina_run_qc_bclconvert/`
- Live checksum blocker evidence:
  - `head-object` for r30 `DAY_final_multiqc.html` returned FSx metadata (`user-agent=aws-fsx-lustre`, file atime/mtime/owner/group/permissions) but no SHA-256 object metadata.
  - ETag must not be substituted for SHA-256.
- Multi-agent split:
  - Orchestrator owns DYEC implementation, ledger, integration, live checks.
  - DayOA worker owns `/Users/jmajor/projects/daylily/daylily-omics-analysis` evidence-manifest changes.
  - Dewey/QEO worker owns `/Users/jmajor/projects/mega_dayhoff/repos_work/dewey` and `/Users/jmajor/projects/lsmc/qeo` contract/dispatch changes.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Inventory | Record repo states, instructions, target prefixes, and live checksum constraints before implementation. | SUCCESS | plan_amendment | Gate 0 | orchestrator | Gate 0 section above. |  | Baseline captured before code edits. |
| DYEC-001 | Catalog | Make artifact registration policy explicit for multiple MultiQC reports and alignment/variant/index outputs. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `daylily_ec/repositories.py`; root and packaged `config/daylily_available_repositories.yaml` include `manifest_source`, `multiqc_reports`, expanded classes/paths, and `illumina_run_qc_bclconvert` registration policy. |  | Catalog policy is explicit for final and run-level MultiQC plus BAM/CRAM/VCF/index outputs. |
| DYEC-002 | Registration builder | Register one analysis artifact set plus one MultiQC artifact set per configured/selected report. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `daylily_ec/workflow/dewey_registration.py`; `python -m pytest tests/test_repository_catalog.py tests/test_export.py -q` -> 36 passed. |  | Builder returns one analysis request plus a MultiQC request list and rejects unknown/duplicate report roots. |
| DYEC-003 | Existing exports | Add explicit registration-only flow for already exported S3 prefixes without DRA export, deletion, or QEO direct calls. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `daylily_ec/workflow/export_data.py`, `daylily_ec/cli.py`; command `exports register-dewey`; test coverage -> 36 passed. |  | Existing S3 exports can be registered through explicit Dewey-only command; S3 inventory requires SHA-256 metadata and performs no DRA/export/delete action. |
| DYEC-004 | Tests | Add DYEC tests for multi-MultiQC requests, selected BAM/CRAM/VCF/index artifacts, S3 inventory hard failures, and CLI registration-only flow. | SUCCESS | contract_test | Gate 5 | orchestrator | `tests/test_export.py`, `tests/test_repository_catalog.py`; `python -m py_compile daylily_ec/repositories.py daylily_ec/workflow/dewey_registration.py daylily_ec/workflow/export_data.py daylily_ec/cli.py`; pytest -> 36 passed. |  | Focused DYEC contract tests pass. |
| DAYOA-001 | Evidence manifest | Extend DayOA evidence classification/inventory for run-level MultiQC and alignment/variant/index artifacts. | SUCCESS | feature_implementation | Gate 1 | DayOA worker | Worker `019e7cff-cd3f-7031-8109-f64e13b92577`; changed `daylily_omics_analysis/evidence_manifest.py` and DayOA ledger `docs/plans/20260531T074927Z_dayoa_evidence_manifest_dewey_qeo_ledger.md`. |  | DayOA worker reported requested evidence-manifest implementation complete. |
| DAYOA-002 | Tests | Add DayOA tests for artifact classes, multiple MultiQC roots, and hard failures. | SUCCESS | contract_test | Gate 5 | DayOA worker | Worker `019e7cff-cd3f-7031-8109-f64e13b92577`; `python -m pytest tests/test_evidence_manifest.py -q` -> 9 passed; focused combined tests -> 19 passed; py_compile passed. |  | DayOA worker reported focused tests pass. |
| DEWEY-001 | Metadata | Confirm or add Dewey metadata persistence for artifact sets/artifacts and receipts. | SUCCESS | feature_implementation | Gate 1 | Dewey/QEO worker | Dewey files changed: `dewey_service/registration_contracts.py`, `dewey_service/services/artifact_set_registration.py`, `dewey_service/services/artifact_sets.py`; `source ./activate local && python -m pytest -q tests/test_qeo_artifact_set_registration.py tests/test_qeo_multiqc_registration.py tests/test_qeo_registration_events.py` -> 23 passed. |  | Dewey accepts and persists explicit artifact/artifact-set metadata. |
| DEWEY-002 | Dispatch filter | Add QEO outbox dispatch filtering by event ID and/or artifact-set EUID. | SUCCESS | feature_implementation | Gate 1 | Dewey/QEO worker | `dewey_service/services/outbox.py`, `dewey_service/cli/qeo.py`; same Dewey pytest command -> 23 passed. |  | Dewey dispatch accepts `event_ids` and `artifact_set_euids`; CLI exposes `--event-id` and `--artifact-set-euid`. |
| QEO-001 | Ingest boundary | Verify QEO remains Dewey-event-only and does not crawl S3 or accept DYEC direct ingest. | SUCCESS | contract_test | Gate 5 | Dewey/QEO worker | QEO files changed: `app/contracts.py`, `app/domain/dewey.py`, `tests/qeo_dewey/test_dewey_consumer.py`; `.venv/bin/python -m pytest -q tests/qeo_contracts/test_dewey_boundary.py tests/qeo_dewey/test_dewey_consumer.py` -> 16 passed. |  | QEO remains Dewey-event/receipt driven and preserves metadata without registering artifacts or crawling storage. |
| LIVE-001 | Dewey register trial | Try Dewey registration for r30/r50/r57 using explicit trial inputs and record receipts or exact blockers. | BLOCKED | feature_implementation | Gate 5 | orchestrator | `docs/plans/20260531T074911Z_live_registration_attempts/*/fsx_export.yaml`; all three registration-only preflights reached S3 inventory and failed before Dewey POST on missing SHA-256 metadata. `env | rg '^(DEWEY|QEO|AWS_PROFILE|AWS_REGION|AWS_DEFAULT_REGION)='` found no Dewey/QEO runtime variables. | Existing exported S3 objects lack SHA-256 metadata required by Dewey file-artifact contract, and no live Dewey URL/token was available in this shell. | Registration did not mutate Dewey; unblock by using DayOA evidence manifests with SHA-256 for all requested artifacts, re-exporting with SHA-256 metadata, or explicitly changing the Dewey checksum contract, plus providing live Dewey URL/token. |
| LIVE-002 | QEO dispatch trial | Dispatch only trial Dewey outbox events to QEO and verify QEO ingest/dead-letter state. | BLOCKED | feature_implementation | Gate 5 | orchestrator | No Dewey outbox events were created because LIVE-001 blocked before Dewey POST; no QEO runtime variables were present. | No trial Dewey artifact-set events exist to dispatch, and QEO dispatch config/token was unavailable in this shell. | Dispatch not attempted; unblock after successful Dewey registration and explicit QEO dispatch configuration. |
| TAG-001 | Evidence metadata | Tag `config/samples.tsv` and `config/units.tsv` and carry sample/experiment/run/unit metadata from DayOA evidence manifests. | SUCCESS | feature_implementation | Gate 1 | orchestrator | DayOA `daylily_omics_analysis/evidence_manifest.py`; `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_evidence_manifest.py -q -> 9 passed`. |  | DayOA emits explicit `samples_manifest` and `units_manifest` records with tags plus sample names, experiment IDs, run IDs, lane/barcode/library/platform metadata. |
| TAG-002 | Dewey propagation | Preserve evidence-manifest tags through DYEC artifact registration and select `samples.tsv`/`units.tsv` for Dewey registration. | SUCCESS | feature_implementation | Gate 1 | orchestrator | DYEC `daylily_ec/workflow/dewey_registration.py`, `daylily_ec/workflow/export_data.py`, root and packaged catalog YAML; `python -m pytest tests/test_repository_catalog.py tests/test_export.py -q -> 36 passed`. |  | DYEC copies record `tags` into Dewey artifact metadata and includes exact `config/samples.tsv` / `config/units.tsv` paths in registration policy. |
| DOC-002 | README setup docs | Document Dewey registration setup/test flow and the Dewey-owned QEO MultiQC load request path. | SUCCESS | documentation | Gate 5 | orchestrator | `README.md` section `Dewey Registration And QEO MultiQC Loading`. |  | README explains export-time registration, existing-export registration, SHA-256 requirements, receipt checks, QEO dispatch by MultiQC artifact-set EUID or event ID, and required Dewey QEO config. |
| DOC-001 | Final ledger state | Terminalize every row and state whether objective is complete or blocked. | SUCCESS | plan_amendment | Gate 5 | orchestrator | This ledger: 14 SUCCESS, 2 BLOCKED, 0 FAIL, 0 working rows. |  | Ledger is terminal; objective is not fully complete because live Dewey/QEO rows are blocked. |

## Status Log

- 2026-05-31T07:49:11Z: Gate 0 started and baseline recorded.
- 2026-05-31T07:49:11Z: Live r30 `DAY_final_multiqc.html` S3 object lacks SHA-256 metadata; S3-inventory registration must fail hard unless an evidence manifest supplies SHA-256 or Dewey contract changes explicitly.
- 2026-05-31T08:00:00Z: DYEC catalog, registration builder, existing-export registration command, and focused tests completed locally.
- 2026-05-31T08:00:00Z: DayOA worker reported evidence-manifest implementation complete with focused tests passing.
- 2026-05-31T08:05:00Z: Dewey/QEO worker reported metadata, dispatch filter, and QEO boundary work complete; orchestrator reran focused Dewey and QEO tests successfully.
- 2026-05-31T08:05:00Z: Registration-only preflight attempts for r30, r50, and r57 wrote terminal `fsx_export.yaml` blockers under `docs/plans/20260531T074911Z_live_registration_attempts/`; all three blocked on missing SHA-256 metadata before any Dewey POST.
- 2026-05-31T08:24:00Z: User requested explicit samples/units and MultiQC sample/experiment tagging. Added DayOA tag-context extraction from `config/samples.tsv` and `config/units.tsv`, plus DYEC propagation into Dewey artifact metadata.
- 2026-05-31T08:25:00Z: Added README setup/test guidance for Dewey registration and Dewey-owned QEO MultiQC dispatch requests.

## Final Status

- Rows: 14 `SUCCESS`, 2 `BLOCKED`, 0 `FAIL`, 0 working.
- All rows are terminal.
- Objective is not fully complete because live Dewey registration and QEO dispatch require SHA-256-complete evidence or an explicit checksum contract change, plus live Dewey/QEO runtime configuration.
