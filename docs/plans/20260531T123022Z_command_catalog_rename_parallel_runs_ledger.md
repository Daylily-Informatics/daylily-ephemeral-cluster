# Command Catalog Rename And Parallel Run Ledger

Date: 2026-05-31T12:30:22Z

## Objective

Rename the DAY-EC command catalog to `daylily_pipeline_command_catalog.yaml`, leave the old `daylily_available_repositories.yaml` filename as a link, then run three command-catalog commands expected to pass in parallel on cluster `dyec-515`.

## Gate 0 Inventory

| Item | Evidence |
|---|---|
| Repo | `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster` |
| Starting git state | Detached `HEAD`; pre-existing modified files from the detached-tag headnode configure fix: `daylily_ec/workflow/create_cluster.py`, `tests/test_workflow.py` |
| Cluster target | `dyec-515`, `us-west-2`, profile `lsmc`, headnode `i-002fac7d5932b5689`; prior configure verified `repo_describe=5.1.5` and `package_version=5.1.5` |
| Catalog source before rename | `config/daylily_available_repositories.yaml` |
| Packaged catalog before rename | `daylily_ec/resources/payload/config/daylily_available_repositories.yaml` |
| Prior passing command evidence used for candidate selection | `docs/plans/20260529T194248Z_dyec_test_command_catalog_validation_ledger.md` and its command log record passing live rows for `ultima_snv_alignstats`, `ont_snv_alignstats`, and `pacbio_snv_alignstats` |
| Candidate inputs | `docs/plans/20260526T224018Z_blahab44_inputs/ultima_hg003_5x.tsv`, `docs/plans/20260526T224018Z_blahab44_inputs/ont_hg003_5x.tsv`, `docs/plans/20260526T224018Z_blahab44_inputs/pacbio_hg003_5x.tsv` |
| Assumptions | Run the three commands on `dyec-515`; do not perform destructive AWS resource changes; avoid `--delete-on-export-success` unless separately requested |

## Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| CAT-001 | Catalog files | Rename source and packaged catalog to `daylily_pipeline_command_catalog.yaml`; keep old filename as a link. | OPEN | config_or_startup_contract | Gate 2 | orchestrator |  |  |  |
| CAT-002 | Code and docs | Update active code, tests, CLI help, and current docs to use the new canonical catalog filename. | OPEN | feature_implementation | Gate 2 | orchestrator |  |  |  |
| TEST-001 | Local validation | Run focused tests/checks proving the new catalog path loads and payload/source copies match. | OPEN | contract_test | Gate 5 | orchestrator |  |  |  |
| RUN-001 | Live dyec-515 | Launch `ultima_snv_alignstats` on `dyec-515` using the renamed catalog. | OPEN | feature_implementation | Gate 5 | orchestrator |  |  |  |
| RUN-002 | Live dyec-515 | Launch `ont_snv_alignstats` on `dyec-515` using the renamed catalog. | OPEN | feature_implementation | Gate 5 | orchestrator |  |  |  |
| RUN-003 | Live dyec-515 | Launch `pacbio_snv_alignstats` on `dyec-515` using the renamed catalog. | OPEN | feature_implementation | Gate 5 | orchestrator |  |  |  |
| RUN-004 | Live dyec-515 | Monitor all three launched runs to terminal status and record evidence. | OPEN | contract_test | Gate 5 | orchestrator |  |  |  |

## Final Status

In progress.
