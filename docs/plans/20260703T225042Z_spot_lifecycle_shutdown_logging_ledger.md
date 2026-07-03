# Spot Lifecycle Shutdown Logging Ledger

Stamp: `20260703T225042Z`

Controlling request: implement DYEC spot lifecycle shutdown logging, extend `dyec pricing spot-logs` with lifecycle rows and per-instance cost intervals, publish updated boot config to S3, and do not retrofit currently running nodes.

Ledger path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260703T225042Z_spot_lifecycle_shutdown_logging_ledger.md`

## Gate 0 Baseline

- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch: `jem-dev...origin/jem-dev`
- Pre-existing dirty files before this work: `daylily_ec/cli.py`, `daylily_ec/headnode_readiness.py`, `daylily_ec/workflow/create_cluster.py`, `tests/test_cli_registry_v2.py`, `tests/test_headnode_readiness.py`, `tests/test_workflow.py`
- Pre-existing untracked file before this work: `docs/plans/20260703T215544Z_dragen_headnode_configure_ledger.md`
- Instruction files read: `/Users/jmajor/.agents/AGENTS.md`, `/Users/jmajor/.agents/AGENTS-HOW-TO-RUN-DAYOA.md`, `/Users/jmajor/.codex/AGENTS.md`, `/Users/jmajor/.codex/AGENTS-HOW-TO-RUN-DAYOA.md`, `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`, `/Users/jmajor/projects/lsmc/AGENTS.md`, `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/AGENTS.md`
- Live-system boundary: no Slurm restart, node drain/resume, job manipulation, cluster teardown, or active compute-node retrofit is in scope.
- S3 deployment boundary: after local tests pass, publish the boot config to `s3://lsmc-dayoa-references-usw2/runtime_assets/cluster_boot_config/` and verify object content/metadata.

## Row Status

| ID | Area | Requirement | Status | Category | Gate | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|
| SL-001 | Ledger | Create durable execution ledger with Gate 0 baseline. | CLOSED | plan_amendment | Gate 0 | This file. |  | Gate 0 inventory recorded before implementation. |
| SL-002 | Bootstrap | Install compute-node systemd lifecycle logger/watcher from Ubuntu and RHEL/DRAGEN post-install scripts. | CLOSED | config_or_startup_contract | Gate 2 | `config/day_cluster/post_install_ubuntu_combined.sh`; `config/day_cluster/post_install_rhel8_dragen.sh` |  | Both scripts install compute-only shutdown and interruption watcher units. |
| SL-003 | Bootstrap | Persist startup metadata under `/var/lib/daylily/spot_lifecycle/` and keep startup spot row compatible. | CLOSED | config_or_startup_contract | Gate 2 | `log_spot_price()` in both post-install scripts |  | Startup rows keep the legacy context format; metadata is persisted for shutdown reuse. |
| SL-004 | Payload | Mirror source boot-script changes into packaged payload resources. | CLOSED | config_or_startup_contract | Gate 2 | `daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh`; `daylily_ec/resources/payload/config/day_cluster/post_install_rhel8_dragen.sh` |  | Payload copies refreshed from source. |
| SL-005 | Parser | Extend spot log parser/scanner schema for `start`, `shutdown`, and `interruption_notice` lifecycle rows. | CLOSED | feature_implementation | Gate 1 | `daylily_ec/spot_price_logs.py` |  | Parser and generated SSM scanner recognize lifecycle rows; legacy rows default to `start`. |
| SL-006 | Cost | Add per-instance cost interval generation with `history` and `logged` price sources. | CLOSED | feature_implementation | Gate 1 | `daylily_ec/spot_price_logs.py` |  | Closed intervals costed from logged price or EC2 spot history; open intervals retained with blank cost. |
| SL-007 | CLI | Extend `dyec pricing spot-logs` JSON payload and add `--cost-output` / `--cost-price-source`. | CLOSED | feature_implementation | Gate 1 | `daylily_ec/cli.py` |  | JSON includes `cost_intervals`; optional summary CSV is separate from raw row CSV. |
| SL-008 | Tests | Add focused parser, CLI, boot-script, and packaging tests. | CLOSED | contract_test | Gate 5 | `tests/test_spot_price_logs.py`; `tests/test_cli_registry_v2.py`; `tests/test_headnode_init.py`; `tests/test_packaged_defaults.py` |  | Focused parser, CLI, boot-script, payload, and heredoc syntax coverage added and verified in SL-009. |
| SL-009 | Verification | Run focused pytest and bash syntax checks. | CLOSED | contract_test | Gate 5 | `source ./activate && pytest tests/test_spot_price_logs.py tests/test_cli_registry_v2.py tests/test_headnode_init.py tests/test_packaged_defaults.py tests/test_workflow.py -q && bash -n config/day_cluster/post_install_ubuntu_combined.sh && bash -n config/day_cluster/post_install_rhel8_dragen.sh` |  | 251 passed; both post-install scripts passed `bash -n`; tests also syntax-check extracted lifecycle helper heredocs. |
| SL-010 | S3 Publish | Publish updated boot config via existing publish path and verify uploaded objects. | CLOSED | config_or_startup_contract | Gate 5 | `publish_cluster_boot_config()` to `s3://lsmc-dayoa-references-usw2/runtime_assets/cluster_boot_config/`; SHA256 download verification in `/tmp/dyec-boot-config-verify.gs72mC` |  | Uploaded `post_install_rhel8_dragen.sh` size 28340 ETag `fed7c4262286b52df8600ef0f0e992a1` SHA256 `16e07ab36f982f50d628d37e828bf8aadde87b315930583bd2408d9791ced36e`; `post_install_ubuntu_combined.sh` size 27905 ETag `09c337306a5f648c0cefba65ee9cb30e` SHA256 `70d852b0c6ee317bdf3e0c884f0cffc4b63214ec2e50853302406d507bfe1225`; `sbatch` size 6520 ETag `6f548cacc1e8b40ac38abb80c126f7eb` SHA256 `7d03b2b2848438729d27a61b820210521553764c53093219af337253a7fd3ecf`; `sleep_test.sh` size 244 ETag `6d9690df817a391c798b5a70b19ee5d1` SHA256 `024531fc67ad8052a1660173d2b94ce83290baa63606099e887b0846aa3a4fae`. |
| SL-011 | Boundary | Record that currently running nodes were not retrofitted and only future node initialization is covered. | CLOSED | legitimate_safety_handling | Gate 5 | This ledger and final report. |  | No Slurm restart, node drain/resume, active compute mutation, or retrofit was performed; only future nodes initialized after the S3 publish receive lifecycle shutdown logging. |
