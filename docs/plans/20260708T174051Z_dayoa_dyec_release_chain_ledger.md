# DayOA + DYEC Release Chain Ledger

Date: 2026-07-08

## Objective

Commit and push the current dirty `daylily-omics-analysis` work on `jem-dev`,
tag the next DayOA release, update DYEC pins to that DayOA release, commit and
tag the next DYEC release, then update DYEC's self pin and tag the follow-up
DYEC release.

## Gate 0 Inventory

- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DayOA branch: `jem-dev` tracking `origin/jem-dev`
- DYEC branch: `jem-dev` tracking `origin/jem-dev`
- DayOA origin: `git@github.com:lsmc-bio/daylily-omics-analysis.git`
- DYEC origin: `git@github.com:lsmc-bio/daylily-ephemeral-cluster.git`
- DayOA max origin tag before work: `10.0.70`
- DYEC max origin tag before work: `10.0.118`
- Planned DayOA tag: `10.0.71`
- Planned DYEC DayOA-pin tag: `10.0.119`
- Planned DYEC self-pin tag: `10.0.120`
- Upstream DYEC tag fetch note: `upstream --tags` rejected older conflicting
  tags `2.2.4` through `2.2.8` and `5.0.2`; no tags were overwritten.

Initial DayOA dirty files:

```text
 M bin/day_activate
 M bin/day_run
 M tests/test_shell_wrapper_contracts.py
 M workflow/rules/common.smk
 M workflow/rules/run_qc_reports.smk
```

Initial DYEC dirty files:

```text
 M README.md
 M config/daylily_ephemeral_cluster_dragen_pcluster_image_rhel8_2c.yaml
 M config/daylily_ephemeral_cluster_template.yaml
 M config/daylily_pipeline_command_catalog.yaml
 M daylily_ec/aws/cost_centers.py
 M daylily_ec/cli.py
 M daylily_ec/config/models.py
 M daylily_ec/config/triplets.py
 M daylily_ec/resources/payload/config/daylily_ephemeral_cluster_template.yaml
 M daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml
 M daylily_ec/scripts/daylily_run_omics_analysis_headnode.py
 M daylily_ec/stage_samples.py
 M daylily_ec/tests_runner.py
 M docs/other/running_dragen_manually.md
 M tests/test_cli_registry_v2.py
 M tests/test_cluster_request_config.py
 M tests/test_cost_centers.py
 M tests/test_repository_catalog.py
 M tests/test_script_entrypoints.py
 M tests/test_stage_samples_from_local_to_headnode.py
 M tests/test_tests_runner.py
 M tests/test_triplets.py
?? docs/PR_runbook_dyec_10.0.118.md
?? docs/dyec-ccat-test-runtime-preds.md
?? docs/plans/20260708T140150Z_dyec_10_0_118_headnode_update_ledger.md
?? docs/plans/20260708T142032Z_intel_catalog_bjuice_jul8itelx4_dyec_10_0_118_ledger.md
?? docs/plans/20260708T142032Z_intel_catalog_bjuice_runtime/
?? docs/plans/20260708T142032Z_intel_catalog_bjuice_selected_commands.json
?? docs/plans/20260708T142032Z_intel_catalog_bjuice_selected_commands.tsv
?? docs/plans/20260708T142032Z_jul8itelx4_catalog_ops.py
?? docs/plans/20260708T165351Z_dragen_rhel_default_ami_delete_ledger.md
?? docs/plans/20260708T165539Z_dayoa_runtime_tmpdir_durable_fix_ledger.md
```

## Tracking Rows

| ID | Repo | Requirement | Status | Category | Gate | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|
| REL-001 | DayOA | Commit dirty DayOA work, push `jem-dev`, tag and push `10.0.71`. | SUCCESS | release | Gate 1 | `pytest tests/test_shell_wrapper_contracts.py -q` -> `25 passed`; commit `b20f16d`; `git push origin jem-dev`; annotated tag check `git cat-file -t 10.0.71` -> `tag`; `git push origin 10.0.71`. |  | DayOA `jem-dev` and release tag `10.0.71` are pushed. |
| REL-002 | DYEC | Update DayOA pins to `10.0.71`, commit dirty DYEC work, push `jem-dev`, tag and push `10.0.119`. | IN_PROGRESS | release | Gate 2 | Updating DayOA pins in DYEC. |  |  |
| REL-003 | DYEC | Update DYEC self pin to `10.0.119`, commit, push `jem-dev`, tag and push `10.0.120`. | OPEN | release | Gate 3 | Pending self-pin edits, tests, and git operations. |  |  |

## Final State

Pending.
