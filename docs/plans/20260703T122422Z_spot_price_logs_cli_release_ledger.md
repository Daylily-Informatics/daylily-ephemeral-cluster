# Spot Price Logs CLI And Release Ledger

Date: 2026-07-03

## Control

Ledger path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260703T122422Z_spot_price_logs_cli_release_ledger.md`

Implementation repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`

Release repos:

- DayOA: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DYEC: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`

## Gate 0 Inventory

- DYEC branch/status before this implementation: `jem-dev...origin/jem-dev`; dirty files were `README.md`, `config/day_cluster/post_install_rhel8_dragen.sh`, `config/daylily_pipeline_command_catalog.yaml`, `daylily_ec/cli.py`, `daylily_ec/repositories.py`, `daylily_ec/resources/payload/config/day_cluster/post_install_rhel8_dragen.sh`, `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`, `tests/test_cli_registry_v2.py`, `tests/test_repository_catalog.py`, and `tests/test_tests_runner.py`.
- DayOA branch/status before release stage: `jem-dev...origin/jem-dev`; no dirty files.
- Latest visible numeric DayOA tag before release: `10.0.56`.
- Latest visible numeric DYEC tag before release: `10.0.88`.
- Existing spot log producers:
  - `config/day_cluster/post_install_ubuntu_combined.sh`
  - `daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh`
  - `config/day_cluster/post_install_rhel8_dragen.sh`
  - `daylily_ec/resources/payload/config/day_cluster/post_install_rhel8_dragen.sh`
- Existing spot log format recorded timestamp, region, AZ, instance type, and spot price. It did not yet record Slurm partition/compute-resource context.
- Existing legacy helper `daylily_ec/resources/payload/bin/proc_spot_price_logs.sh` only summarized `/fsx/scratch/*price.log`; it did not expose a normalized cluster-wide CSV from `/fsx/logs`, `/fsx/scratch`, and `/fsx/tmp`.
- Release contract: use non-v annotated semver tags, commit first, push `jem-dev`, push tag; DayOA release first, DYEC DayOA-pin release second, DYEC self-pin release third.

## Tracking Rows

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| SPOTLOG-001 | Parser | Add normalized parsing/export support for all spot-price log rows | CLOSED | feature_implementation | Gate 5 | Codex | `daylily_ec/spot_price_logs.py`; `tests/test_spot_price_logs.py`; `python -m pytest tests/test_spot_price_logs.py ...` passed. | Missing public parser/export surface for spot-price history logs. | Added old/new-format parser, CSV schema, remote scanner payload markers, and payload extraction. |
| SPOTLOG-002 | CLI | Add read-only DYEC CLI command to fetch spot-price logs from the head node as one CSV | CLOSED | feature_implementation | Gate 5 | Codex | `dyec pricing spot-logs --help`; `tests/test_cli_registry_v2.py::test_pricing_spot_logs_exports_csv_via_ssm`; `tests/test_cli_registry_v2.py::test_pricing_spot_logs_supports_json`. | Spot price logs were only available as raw files on cluster storage. | Added `dyec pricing spot-logs` with CSV stdout/file output, JSON mode, repeatable remote paths/name globs, SSM remote-user support, and hard failure on empty results unless `--allow-empty`. |
| SPOTLOG-003 | Producers | Update node configuration scripts so future rows include node type, partition, compute resource, hostname, and instance id | CLOSED | feature_implementation | Gate 5 | Codex | `bash -n config/day_cluster/post_install_ubuntu_combined.sh ... post_install_rhel8_dragen.sh` passed. | Existing log rows lacked Slurm partition/compute-resource context needed for joined bid reporting. | Updated Ubuntu and RHEL/DRAGEN configure scripts, plus packaged copies, to log node type, Slurm partition, compute resource, hostname, and EC2 instance id. |
| SPOTLOG-004 | Tests | Add focused tests for parser, CLI registration, and SSM command shape | CLOSED | contract_test | Gate 5 | Codex | `python -m pytest tests/test_spot_price_logs.py tests/test_cli_registry_v2.py tests/test_repository_catalog.py tests/test_tests_runner.py -q`: 161 passed. | New CLI needed parser, registry, and SSM command-shape coverage before release. | Added parser tests, CSV schema tests, SSM scanner script tests, CLI CSV/JSON tests, and registry policy assertion. |
| REL-001 | DayOA | Commit dirty DayOA state, push `jem-dev`, tag and push next DayOA version | CLOSED | release | Gate 7 | Codex | `git status --short --branch`: `## jem-dev...origin/jem-dev`; `git rev-parse HEAD` equals `git rev-parse 10.0.56^{}` at `b68f8da2bad65fe36f1f7992854f0ddbb49925b2`; `git cat-file -t 10.0.56`: `tag`. | DayOA had no dirty files and current `jem-dev` was already released as annotated tag `10.0.56`. | No DayOA commit/tag/push was performed; DYEC DayOA pins remain at `10.0.56`. |
| REL-002 | DYEC DayOA pin | Update DYEC DayOA pins to the new DayOA tag, commit, push, tag and push next DYEC version | CLOSED | release | Gate 7 | Codex | Commit `d6d102efcaa08ab2af660d3079db8c6fb335a76c`; annotated tag `10.0.89`; `git push origin jem-dev`; `git push origin 10.0.89`. | DayOA had no new dirty release, so there was no new DayOA tag to pin. | Released DYEC implementation state as `10.0.89` with DayOA pins unchanged at `10.0.56`. |
| REL-003 | DYEC self-pin | Update DYEC self-pinned runtime version to the DYEC DayOA-pin tag, commit, push, tag and push final DYEC version | CLOSED | release | Gate 7 | Codex | `config/daylily_cli_global.yaml` and packaged copy set `git_ephemeral_cluster_repo_tag` and `git_ephemeral_cluster_repo_release_tag` to `10.0.89`; final release target `10.0.90`. | DYEC self-pins lagged the newly released implementation tag. | Self-pin commit will be tagged as `10.0.90`, so fresh installs pin to `10.0.89`. |

## Validation Evidence

- `bash -n config/day_cluster/post_install_ubuntu_combined.sh daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh config/day_cluster/post_install_rhel8_dragen.sh daylily_ec/resources/payload/config/day_cluster/post_install_rhel8_dragen.sh`: passed.
- `source ./activate && dyec pricing spot-logs --help`: rendered help for CSV/JSON spot-log export options.
- `source ./activate && python -m pytest tests/test_spot_price_logs.py tests/test_cli_registry_v2.py tests/test_repository_catalog.py tests/test_tests_runner.py -q`: 161 passed.
- `source ./activate && python -m ruff check daylily_ec/spot_price_logs.py daylily_ec/cli.py tests/test_spot_price_logs.py tests/test_cli_registry_v2.py`: passed.
- `source ./activate && python -m ruff format --check daylily_ec/spot_price_logs.py daylily_ec/cli.py tests/test_spot_price_logs.py tests/test_cli_registry_v2.py`: passed.
- `git diff --check`: passed.
