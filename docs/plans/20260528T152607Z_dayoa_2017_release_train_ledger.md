# DayOA 2.0.17 Kitchen-Sink Export And Release Train Ledger

Controlling request: 2026-05-28 user request to export the completed goodole3 DayOA clone, copy final MultiQC artifacts locally, update the command catalog kitchensink entry, and run the DayOA/DYEC release train through GitHub release publication.

Ledger path: `docs/plans/20260528T152607Z_dayoa_2017_release_train_ledger.md`

## Gate 0 Baseline

- DYEC repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
- DYEC branch at start: `codex/dyec-dewey-registration-refactor-20260528`
- DYEC status at start: untracked `docs/plans/20260528T132738Z_hg003_20x10x_qc_j300_ledger.md`, `docs/plans/20260528T142710Z_jem_bucktst_delete_ledger.md`, and `docs/plans/20260528T151100Z_inflection_20x10x_analysis_export_receipt/`.
- DayOA repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`
- DayOA branch at start: `codex/dayoa-local-evidence-dewey-refactor-20260528`
- DayOA status at start: dirty CHARR retirement, empty-unmapped sentinel, contam/report staging, goleft, and docs/tests/ledger work from the completed HG002 kitchensink validation.
- Completed headnode analysis directory: `/fsx/analysis_results/ubuntu/2.0.17`
- Completed headnode DayOA checkout: `/fsx/analysis_results/ubuntu/2.0.17/daylily-omics-analysis`
- Final MultiQC report: `/fsx/analysis_results/ubuntu/2.0.17/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc.html`
- Final MultiQC data directory: `/fsx/analysis_results/ubuntu/2.0.17/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc_data/`
- Export destination selected for this validation export: `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/2.0.17/`
- Local MultiQC copy destination: `/Users/jmajor/Downloads/new_dayoa/`
- Command catalog owner: DYEC `config/daylily_available_repositories.yaml`
- Release tag policy: non-`v` annotated semver tags on clean release commits; do not move pushed version tags.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| RT-001 | Ledger | Record Gate 0 baseline before export, catalog edits, commits, tags, or releases | SUCCESS | feature_implementation | Gate 0 | orchestrator | This file records repo paths, branches, dirty state, export/copy destinations, and release policy. |  | Ledger created before release-train mutations. |
| RT-002 | Export | Schedule/run DRA export of `/fsx/analysis_results/ubuntu/2.0.17` to S3 | SUCCESS | feature_implementation | Gate 5 | orchestrator | `dyec export --profile lsmc --region us-west-2 --cluster-name goodole3 --source-path /fsx/analysis_results/ubuntu/2.0.17 --destination-s3-uri s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/2.0.17/ --output-dir docs/plans/20260528T152607Z_dayoa_2017_export_receipt --verbose` completed. Receipt `docs/plans/20260528T152607Z_dayoa_2017_export_receipt/fsx_export.yaml`: status `success`, association `dra-0004979bb41204f75`, task `task-07b2dea880e6af45f`, task lifecycle `SUCCEEDED`, `FailedCount=0`, `SucceededCount=4909`, `TotalCount=4909`, `detached=true`, `detach_lifecycle=DELETED`. |  | Clone exported to the selected validation S3 prefix and the temporary DRA was detached without deleting FSx data. |
| RT-003 | Local copy | Copy final MultiQC HTML and data dir to `/Users/jmajor/Downloads/new_dayoa/` | SUCCESS | feature_implementation | Gate 5 | orchestrator | Copied via headnode SSM staging prefix `s3://lsmc-dayoa-analysis-results-usw2/transfers/new_dayoa/20260528T152607Z/` and local sync to `/Users/jmajor/Downloads/new_dayoa/`. Verification: 78 files, total 12M; `DAY_final_multiqc.html` 5.1M; `DAY_final_multiqc_data/` 7.1M. |  | Local report bundle is present for inspection. |
| RT-004 | Command catalog | Update DYEC kitchensink command entry with the exact command that reached final MultiQC | SUCCESS | feature_implementation | Gate 1 | orchestrator | Added catalog command `illumina_hg002_kitchensink_multiqc` with targets/config matching the final successful command: Sentieon align, dmd CRAM, sentd SNV, alignstats, GIAB concordance, relatedness, GATK/site-mix/global contamination, VEP, ExpansionHunter, HTD `cyrius`, metagenomics, final MultiQC, `-j 200 -p -k --rerun-triggers mtime`. Catalog loads with DayOA default/git pins `2.0.19`; packaged catalog synced. Tests: `python -m pytest -q tests/test_repository_catalog.py tests/test_packaged_defaults.py tests/test_cli_registry_v2.py` -> `107 passed`; `git diff --check` clean. |  | Command catalog now records the successful kitchen-sink command and release pin. |
| RT-005 | DayOA release | Commit all new/changed/dirty DayOA work, push branch, tag next non-`v` annotated semver, and push tag | SUCCESS | feature_implementation | Gate 5 | orchestrator | DayOA focused tests passed: `python -m pytest -q tests/test_unmapped_metagenomics.py tests/test_multiqc_staging_contracts.py tests/test_multiqc_qc_targets.py tests/test_contam_identity_bundle.py tests/test_multiqc_sample_identifiers.py tests/test_htd_callers_contract.py` -> `90 passed`; `git diff --check` clean. Commit `b377b8b557306fbb6832763a39661ce36d6f4bbd` pushed to `origin/codex/dayoa-local-evidence-dewey-refactor-20260528`; annotated tag `2.0.19` created (`git cat-file -t 2.0.19 -> tag`) and pushed. |  | DayOA release tag `2.0.19` is the pin target for the DYEC catalog update. |
| RT-006 | DYEC DayOA pin | Update DYEC env/config/pyproject DayOA pins to the new DayOA release, commit/push/tag | OPEN | feature_implementation | Gate 5 | orchestrator | DayOA pins updated in source and packaged catalogs plus docs/tests to `2.0.19`; `environment.yaml` and `pyproject.toml` do not carry a DayOA package dependency/pin in this repo, so no DayOA dependency edit was made there. Commit/tag pending. |  |  |
| RT-007 | DYEC self pin | Update DYEC self pin in config, commit/push/tag final version | OPEN | feature_implementation | Gate 5 | orchestrator | Pending. |  |  |
| RT-008 | GitHub release | Create GitHub release object for the final DYEC tag and mark it as FREEZE PROD candidate | OPEN | feature_implementation | Gate 5 | orchestrator | Pending. |  |  |
