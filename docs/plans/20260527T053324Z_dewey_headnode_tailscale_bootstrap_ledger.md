# Dewey Headnode Tailscale Bootstrap Ledger

Created: 2026-05-27T05:33:24Z

## Objective

Allow current and future DayEC headnodes to reach `https://dewey.day.lsmc.bio/` by recording a Tailscale bootstrap in the headnode post-install path and publishing the updated boot script to the S3 runtime-assets location that ParallelCluster uses for node configuration.

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
| Tailscale install source | Official Tailscale package instructions for Ubuntu 22.04 use the stable Ubuntu Jammy keyring/list plus `apt-get install tailscale` |
| Baseline dirty state | `config/day_cluster/post_install_ubuntu_combined.sh`, packaged copy, and `tests/test_headnode_init.py` were already modified with environment-cache bootstrap changes before this Tailscale work; preserve and extend them |
| Live target DNS | `dewey.day.lsmc.bio` resolves to `100.75.231.53`; workstation curl to `https://dewey.day.lsmc.bio/` returns HTTP 401 via `/ui`, proving the service is reachable from a tailnet-capable client |
| Safety assumptions | This is a non-destructive S3 boot-script update. Missing Tailscale auth material must fail hard on new headnodes rather than silently skipping tailnet enrollment. |

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Baseline | Record repo, dirty state, source paths, S3 boot contract, and safety assumptions before changes. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | Gate 0 Inventory above. |  | Baseline recorded before Tailscale edits and S3 publish. |
| IMPL-001 | Boot script | Add headnode-only Tailscale install and `tailscale up` using an explicit SSM SecureString parameter. | SUCCESS | feature_implementation | Gate 2 | orchestrator | Updated `config/day_cluster/post_install_ubuntu_combined.sh` and synced `daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh`; headnode branch now installs Tailscale from `pkgs.tailscale.com`, retrieves `/daylily/dayec/tailscale/headnode-authkey` via `aws ssm get-parameter --with-decryption`, runs `tailscale up`, and verifies Dewey curl response. |  | Source and packaged boot scripts include headnode-only Tailscale bootstrap with explicit missing-auth-key failure. |
| TEST-001 | Validation | Add/update focused tests and run syntax/test checks for the boot script and packaged copy. | SUCCESS | contract_test | Gate 5 | orchestrator | Updated `tests/test_headnode_init.py`; `source ./activate && bash -n config/day_cluster/post_install_ubuntu_combined.sh && bash -n daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh && python -m pytest tests/test_headnode_init.py tests/test_packaged_defaults.py tests/test_workflow.py::TestClusterBootConfigPublish -q` -> 21 passed. |  | Syntax and focused boot/publisher tests passed. |
| PUB-001 | S3 runtime assets | Copy the updated post-install script to the active `runtime_assets/cluster_boot_config` S3 location used by ParallelCluster. | SUCCESS | feature_implementation | Gate 5 | orchestrator | Rendered `goodole3` cluster config points at `s3://lsmc-dayoa-references-usw2/runtime_assets/cluster_boot_config/post_install_ubuntu_combined.sh`; backed up previous object to `s3://lsmc-dayoa-references-usw2/runtime_assets/cluster_boot_config/backups/post_install_ubuntu_combined.sh.pre-tailscale-20260527T053324Z`; uploaded updated script to active key; active head object `LastModified=2026-05-27T05:40:28+00:00`, `ContentLength=19506`, `ETag=b1aaff5b61d4ce68e89f1644938683af`. |  | Updated active boot script is published where ParallelCluster reads it. |
| VERIFY-001 | Live proof | Verify S3 object readback matches the local source and record the auth-key blocker for actual tailnet enrollment. | SUCCESS | contract_test | Gate 5 | orchestrator | Downloaded active S3 object and compared to local source: local and S3 sha256 both `1f809ae6c94cdda2aa8f83a0cf57cdfbb98e0cfc6ffe5d0c6ec2c8c20b818a1b`; `cmp` returned 0; packaged script also matches source with `cmp_post_install=0`. |  | Active S3 boot script matches local source exactly. |
| AUTH-001 | Tailnet credential | Confirm the Tailscale auth-key SSM parameter exists without exposing its value. | BLOCKED | legitimate_safety_handling | Gate 5 | orchestrator | `aws ssm describe-parameters --parameter-filters Key=Name,Option=Equals,Values=/daylily/dayec/tailscale/headnode-authkey` returned `[]`. | Missing Tailscale auth-key SSM parameter. | New headnodes will install the script but fail hard at Tailscale enrollment until `/daylily/dayec/tailscale/headnode-authkey` is created as an SSM SecureString in `us-west-2` for profile/account `lsmc`. |

## Terminal Report

All rows are terminal. The boot-script implementation and S3 publish are complete. The operational objective is blocked on creating `/daylily/dayec/tailscale/headnode-authkey` with a valid Tailscale auth key whose tailnet ACL/tag policy can reach `dewey.day.lsmc.bio`.
