# Dewey Headnode network overlay Bootstrap Ledger

Created: 2026-05-27T05:33:24Z

## Objective

Allow current and future DayEC headnodes to reach `https://dewey.day.lsmc.bio/` by recording a network overlay bootstrap in the headnode post-install path and publishing the updated boot script to the S3 runtime-assets location that ParallelCluster uses for node configuration.

## Gate 0 Inventory

| Item | Evidence |
|---|---|
| Repo | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| Branch | `main` tracking `origin/main` |
| HEAD | `1f834ea2cdaeb2e6cc97cdf6362beacc3e46b417` |
| Controlling script | `config/day_cluster/post_install_ubuntu_combined.sh` |
| Packaged script | `daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh` |
| Publish helper candidate | `config/day_cluster/update_s3_day_boot_script_refs.sh`; inspected and not used for source-of-truth behavior because cluster creation publishes through `daylily_ec.workflow.create_cluster.publish_cluster_boot_config` and the helper only lists `sbatch` |
| PCluster boot URI contract | Cluster templates execute `${REGSUB_S3_BUCKET_INIT}/post_install_ubuntu_combined.sh`; `create_cluster.py` derives `${REGSUB_S3_BUCKET_INIT}` from the reference bucket as `runtime_assets/cluster_boot_config` |
| network overlay install source | Official network overlay package instructions for Ubuntu 22.04 use the stable Ubuntu Jammy keyring/list plus `apt-get install network-overlay` |
| Baseline dirty state | `config/day_cluster/post_install_ubuntu_combined.sh`, packaged copy, and `tests/test_headnode_init.py` were already modified with environment-cache bootstrap changes before this network overlay work; preserve and extend them |
| Live target DNS | `dewey.day.lsmc.bio` resolves to `100.75.231.53`; workstation curl to `https://dewey.day.lsmc.bio/` returns HTTP 401 via `/ui`, proving the service is reachable from a overlay-network-capable client |
| Safety assumptions | This is a non-destructive S3 boot-script update. Missing network overlay auth material must fail hard on new headnodes rather than silently skipping overlay-network enrollment. |

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Baseline | Record repo, dirty state, source paths, S3 boot contract, and safety assumptions before changes. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | Gate 0 Inventory above. |  | Baseline recorded before network overlay edits and S3 publish. |
| IMPL-001 | Boot script | Add headnode-only network overlay install and `network-overlay up` using an explicit SSM SecureString parameter. | SUCCESS | feature_implementation | Gate 2 | orchestrator | Updated `config/day_cluster/post_install_ubuntu_combined.sh` and synced `daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh`; headnode branch now installs network overlay from `pkgs.network-overlay.com`, retrieves `/daylily/dayec/network-overlay/headnode-credential` via `aws ssm get-parameter --with-decryption`, runs `network-overlay up`, and verifies Dewey curl response. |  | Source and packaged boot scripts include headnode-only network overlay bootstrap with explicit missing-auth-key failure. |
| TEST-001 | Validation | Add/update focused tests and run syntax/test checks for the boot script and packaged copy. | SUCCESS | contract_test | Gate 5 | orchestrator | Updated `tests/test_headnode_init.py`; `source ./activate && bash -n config/day_cluster/post_install_ubuntu_combined.sh && bash -n daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh && python -m pytest tests/test_headnode_init.py tests/test_packaged_defaults.py tests/test_workflow.py::TestClusterBootConfigPublish -q` -> 21 passed. |  | Syntax and focused boot/publisher tests passed. |
| PUB-001 | S3 runtime assets | Copy the updated post-install script to the active `runtime_assets/cluster_boot_config` S3 location used by ParallelCluster. | SUCCESS | feature_implementation | Gate 5 | orchestrator | Rendered `goodole3` cluster config points at `s3://lsmc-dayoa-references-usw2/runtime_assets/cluster_boot_config/post_install_ubuntu_combined.sh`; backed up previous object to `s3://lsmc-dayoa-references-usw2/runtime_assets/cluster_boot_config/backups/post_install_ubuntu_combined.sh.pre-network-overlay-20260527T053324Z`; uploaded updated script to active key; active head object `LastModified=2026-05-27T05:40:28+00:00`, `ContentLength=19506`, `ETag=b1aaff5b61d4ce68e89f1644938683af`. |  | Updated active boot script is published where ParallelCluster reads it. |
| VERIFY-001 | Live proof | Verify S3 object readback matches the local source and record the auth-key blocker for actual overlay-network enrollment. | SUCCESS | contract_test | Gate 5 | orchestrator | Downloaded active S3 object and compared to local source: local and S3 sha256 both `1f809ae6c94cdda2aa8f83a0cf57cdfbb98e0cfc6ffe5d0c6ec2c8c20b818a1b`; `cmp` returned 0; packaged script also matches source with `cmp_post_install=0`. |  | Active S3 boot script matches local source exactly. |
| AUTH-001 | Overlay network credential | Confirm the network overlay auth-key SSM parameter exists without exposing its value. | BLOCKED | legitimate_safety_handling | Gate 5 | orchestrator | `aws ssm describe-parameters --parameter-filters Key=Name,Option=Equals,Values=/daylily/dayec/network-overlay/headnode-credential` returned `[]`. | Missing network overlay auth-key SSM parameter. | New headnodes will install the script but fail hard at network overlay enrollment until `/daylily/dayec/network-overlay/headnode-credential` is created as an SSM SecureString in `us-west-2` for profile/account `lsmc`. |
| AUTH-002 | Overlay network credential | Test local `.network-overlay_key` without exposing the key value | SUCCESS | contract_test | Gate 5 | orchestrator | `2026-05-27T18:25Z` local isolated Docker test enrolled two sequential userspace network overlay nodes with `.network-overlay_key`; both reached `Running` state with distinct overlay-network IPs and `curl --socks5-hostname 127.0.0.1:1055 https://dewey.day.lsmc.bio/` returned `http_code=307`; both test nodes were logged out and removed; no `dayec-key-test-*` containers remain. |  | The key shape, reusability, overlay-network enrollment, and Dewey ACL path were validated. It has not yet been stored in SSM. |

## Terminal Report

All rows are terminal. The boot-script implementation and S3 publish are complete. The operational objective is blocked on creating `/daylily/dayec/network-overlay/headnode-credential` with a valid network overlay auth key whose overlay-network ACL/tag policy can reach `dewey.day.lsmc.bio`.

## Scope Clarification

2026-05-27T18:14Z user clarification: `https://dewey.day.lsmc.bio/` is the only required overlay-network reachability target for headnodes. Kahlo reachability is explicitly out of scope and should not drive further work.
