# Remove Boot-Time Dewey Probe Ledger

Created: 2026-05-28T20:52:45Z

## Objective

Remove `*.day.lsmc.bio` service reachability from DAY-EC cluster bootstrap, publish the updated boot script to the active reference runtime-assets buckets requested by the user, and audit DayOA code/docs for other `*.day.lsmc.bio` URLs.

## Gate 0 Inventory

| Field | Evidence |
|---|---|
| Ledger path | `docs/plans/20260528T205245Z_remove_boot_dewey_probe_ledger.md` |
| DAY-EC repo | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| DAY-EC branch | `codex/dyec-dewey-registration-refactor-20260528...origin/codex/dyec-dewey-registration-refactor-20260528` |
| Initial DAY-EC dirty state | `?? docs/end_to_end_5.0.22.md` |
| Controlling source script | `config/day_cluster/post_install_ubuntu_combined.sh` |
| Packaged script | `daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh` |
| Initial active boot coupling | HeadNode block calls `configure_headnode_network-overlay` then `verify_headnode_dewey_access`; the verification curls `https://dewey.day.lsmc.bio/` and exits nonzero on curl failure. |
| Initial DAY-EC service URL sweep | `rg -n "[A-Za-z0-9._-]+\\.day\\.lsmc\\.bio" .` found active boot/test hits plus historical `docs/plans/` evidence for Dewey/Kahlo. |
| Initial DayOA repos checked | `/Users/jmajor/projects/daylily/daylily-omics-analysis`, `/Users/jmajor/projects/lsmc/bfx_pipe/daylily-omics-analysis`, `/Users/jmajor/projects/daylily-omics-analysis` |
| Initial DayOA service URL sweep | `rg -n --glob '!*.json' --glob '!*.log' --glob '!*.html' "[A-Za-z0-9._-]+\\.day\\.lsmc\\.bio" <dayoa repos>` returned no matches. |
| Initial bucket discovery | `AWS_PROFILE=lsmc aws s3api list-buckets` showed accessible matching reference bucket `lsmc-dayoa-references-usw2`; further publish-target discovery needed. |
| Region ambiguity | User requested `eu-east-1`, which is not an AWS region name; do not invent the intended region. |

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| BOOT-001 | DAY-EC boot script | Remove the Dewey URL and boot-time Dewey curl from source and packaged post-install scripts. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Removed `network-overlay_dewey_url`, `verify_headnode_dewey_access`, and the HeadNode call to that verifier from `config/day_cluster/post_install_ubuntu_combined.sh` and `daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh`; changed network overlay log line to no longer include a service URL. `cmp` confirms source and packaged scripts match. |  | Boot still configures network overlay, but cluster create no longer curls Dewey or any `*.day.lsmc.bio` service as a bootstrap gate. |
| TEST-001 | DAY-EC tests | Update focused tests so boot script no longer requires any `*.day.lsmc.bio` URL or `verify_headnode_dewey_access` function. | SUCCESS | contract_test | Gate 5 | orchestrator | Updated `tests/test_headnode_init.py`; `source ./activate && bash -n config/day_cluster/post_install_ubuntu_combined.sh && bash -n daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh && python -m pytest tests/test_headnode_init.py tests/test_packaged_defaults.py tests/test_workflow.py::TestClusterBootConfigPublish -q` -> `21 passed`; `python -m ruff check tests/test_headnode_init.py && git diff --check` passed. |  | Focused test/syntax/format checks pass with the Dewey probe removed. |
| AUDIT-001 | Service URL audit | Confirm active DAY-EC and DayOA code/docs contain no non-historical `*.day.lsmc.bio` service URLs after changes. | SUCCESS | contract_test | Gate 5 | orchestrator | `rg -n --glob '!docs/plans/**' --glob '!docs/aws_3month_retrospective_cost_analysis_assets/**' "[A-Za-z0-9._-]+\\.day\\.lsmc\\.bio" config daylily_ec tests docs` returned no matches. DayOA sweeps of `/Users/jmajor/projects/daylily/daylily-omics-analysis`, `/Users/jmajor/projects/lsmc/bfx_pipe/daylily-omics-analysis`, and `/Users/jmajor/projects/daylily-omics-analysis` with `.git`, `results`, and `.snakemake` excluded returned no matches. |  | Active DYEC source/docs and checked DayOA code/docs have no `*.day.lsmc.bio` service URLs; historical ledgers under `docs/plans/` still retain past evidence. |
| PUBLISH-001 | Runtime assets | Publish updated boot script to active accessible reference runtime-assets buckets requested by the user. | SUCCESS | feature_implementation | Gate 5 | orchestrator | Backed up and overwrote `s3://lsmc-dayoa-references-usw2/runtime_assets/cluster_boot_config/post_install_ubuntu_combined.sh` with profile `lsmc`, region `us-west-2`; backed up and overwrote `s3://daylily-dayoa-references-usw2/runtime_assets/cluster_boot_config/post_install_ubuntu_combined.sh` with profile `daylily`, region `us-west-2`; uploaded to `s3://lsmc-dayoa-omics-analysis-ap-south-1/runtime_assets/cluster_boot_config/post_install_ubuntu_combined.sh` with profile `lsmc`, region `ap-south-1`; uploaded to `s3://lsmc-dayoa-omics-analysis-eu-central-1/runtime_assets/cluster_boot_config/post_install_ubuntu_combined.sh` with profile `lsmc`, region `eu-central-1`. Readback SHA-256 matched local `06fd03938da69de6d3e3f8d2fcab93387c128a9887ad9f201d8221d5797c7ab2` for all four targets. |  | Confirmed targets now contain the no-Dewey boot script; us-west targets have timestamped backups under `runtime_assets/cluster_boot_config/backups/`; ap-south/eu-central did not have an existing boot-script key to back up. |
| AMBIG-001 | Region names | Resolve or block the invalid `eu-east-1` publish target without guessing. | SUCCESS | plan_amendment | Gate 5 | orchestrator | User clarified `eu-central-1`, not `eu-east-1`; published and verified `s3://lsmc-dayoa-omics-analysis-eu-central-1/runtime_assets/cluster_boot_config/post_install_ubuntu_combined.sh` with `bytes=18439`, SHA-256 `06fd03938da69de6d3e3f8d2fcab93387c128a9887ad9f201d8221d5797c7ab2`, `match=yes`. |  | Region ambiguity resolved by explicit user correction; eu-central-1 target is updated. |

## Terminal Report

- Terminal rows: `SUCCESS=5`, `BLOCKED=0`.
- Region correction: user clarified `eu-central-1`, not `eu-east-1`.
- Confirmed live publishes completed for `lsmc-dayoa-references-usw2`, `daylily-dayoa-references-usw2`, `lsmc-dayoa-omics-analysis-ap-south-1`, and `lsmc-dayoa-omics-analysis-eu-central-1`.
- Focused validation passed: shell syntax, package/source script parity, focused pytest, ruff, `git diff --check`, active URL sweeps, and S3 readback SHA checks.
