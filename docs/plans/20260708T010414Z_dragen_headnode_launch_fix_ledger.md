## Control Ledger

Controlling plan: `/Users/jmajor/projects/lsmc/dragen-fix-20260708/daylily-ephemeral-cluster/docs/plans/20260708T010414Z_dragen_headnode_launch_fix_ledger.md`
Ledger path: `/Users/jmajor/projects/lsmc/dragen-fix-20260708/daylily-ephemeral-cluster/docs/plans/20260708T010414Z_dragen_headnode_launch_fix_ledger.md`

### Objective

Create isolated DYEC and DayOA checkouts from the lsmc-bio forks, branch both for DRAGEN work, fix the July 7 RHEL8 DRAGEN headnode launch failure, bring up a fresh DRAGEN DYEC cluster, and run the requested DRAGEN test command using the DYEC-pinned DayOA tag.

### Gate 0 Baseline

- Workspace root: `/Users/jmajor/projects/lsmc/dragen-fix-20260708`
- DYEC repo: `/Users/jmajor/projects/lsmc/dragen-fix-20260708/daylily-ephemeral-cluster`
- DayOA repo: `/Users/jmajor/projects/lsmc/dragen-fix-20260708/daylily-omics-analysis`
- DYEC source: local clone of `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, whose `origin` is `git@github.com:lsmc-bio/daylily-ephemeral-cluster.git`; fresh clone origin reset to same lsmc-bio fork.
- DayOA source: local clone of `/Users/jmajor/projects/lsmc/daylily-omics-analysis`, whose `origin` is `git@github.com:lsmc-bio/daylily-omics-analysis.git`; fresh clone origin reset to same lsmc-bio fork.
- Requested DYEC start: `10.0.106`; branch `codex/dragen-headnode-launch-fix`.
- DYEC-pinned DayOA start: `10.0.65` from `pyproject.toml` dependency `daylily-omics-analysis @ git+https://github.com/lsmc-bio/daylily-omics-analysis.git@10.0.65`; branch `codex/dragen-headnode-launch-fix`.
- Initial DYEC status: `## codex/dragen-headnode-launch-fix` clean.
- Initial DayOA status: `## codex/dragen-headnode-launch-fix` clean.
- Live AWS profile/region: `lsmc`, `us-west-2`.
- July 7 failure evidence: `dragen-103-pg-20260707` launched headnode `i-005e60f6f047ee4eb`; `post_install_rhel8_dragen.sh` failed at `dnf -y install ...` with `rpmdb: ... DB_RUNRECOVERY` and `Error: rpmdb open failed`; stack rolled back and no `f2.6xlarge` compute launched.
- Starting source evidence: `config/day_cluster/post_install_rhel8_dragen.sh` already validates `rpm -qa` before `dnf`, but the live failure occurred after that guard during `dnf`; package-install recovery must wrap the actual `dnf` call.
- Baseline command: `cd /Users/jmajor/projects/lsmc/dragen-fix-20260708/daylily-ephemeral-cluster && source ./activate && dyec --help` -> `DAY-EC activated`, command list rendered.
- Live-system limits: creating a fresh DRAGEN cluster is a live AWS cost-incurring action requested by the user; no destructive cleanup of failed stacks, FSx, DRA, or instances is approved in this ledger.

### Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DGN-001 | Setup | Create isolated DYEC and DayOA checkouts from lsmc-bio forks and branch from `10.0.106` / pinned `10.0.65`. | SUCCESS | feature_implementation | Gate 0 | Codex | Fresh repos under `/Users/jmajor/projects/lsmc/dragen-fix-20260708`; both branches `codex/dragen-headnode-launch-fix`; clean statuses. |  | Isolated branch setup complete. |
| DGN-002 | Diagnosis | Identify the exact July 7 headnode launch failure and source surface to change. | SUCCESS | feature_implementation | Gate 0 | Codex | CloudWatch/cfn-init evidence showed `dnf -y install ...` failed with rpmdb `DB_RUNRECOVERY`; source guard only ran before `dnf`. |  | Root failure and source location identified. |
| DGN-003 | DYEC | Harden RHEL8 DRAGEN package install so rpmdb corruption during `dnf` is explicitly repaired and retried without fallback behavior. | SUCCESS | feature_implementation | Gate 1 | Codex | `config/day_cluster/post_install_rhel8_dragen.sh` now wraps `dnf -y install` with `dnf_install_with_rpmdb_repair`, detects only rpmdb corruption signatures, runs `rebuild_rhel_rpmdb`, and retries once. |  | Package install now handles the observed July 7 rpmdb failure while still failing hard for non-rpmdb `dnf` errors. |
| DGN-004 | DYEC | Keep source and packaged DRAGEN post-install scripts identical and add focused test coverage. | SUCCESS | contract_test | Gate 1 | Codex | Updated `daylily_ec/resources/payload/config/day_cluster/post_install_rhel8_dragen.sh`; added assertions in `tests/test_headnode_init.py`; `cmp -s` passed. |  | Source/payload parity and regression assertions complete. |
| DGN-005 | Verification | Run focused local syntax/tests for the boot-script change. | SUCCESS | contract_test | Gate 5 | Codex | `source ./activate && bash -n config/day_cluster/post_install_rhel8_dragen.sh && bash -n daylily_ec/resources/payload/config/day_cluster/post_install_rhel8_dragen.sh && cmp -s ... && pytest tests/test_headnode_init.py tests/test_packaged_defaults.py -q` -> `28 passed`. |  | Focused local verification passed. |
| DGN-006 | Live Cluster | Publish/use the fixed boot config and create a fresh DRAGEN cluster with a new name rather than deleting the failed July 7 stack. | ATTEMPTING_BUGFIX | config_or_startup_contract | Gate 5 | Codex | First live create `dragen-fix-20260708` published fixed boot config (`post_install_rhel8_dragen.sh` S3 ETag `5ca5ef5111d1671e553b621ef1c69151`) and got past the July 7 rpmdb/`dnf` failure, but failed at a one-shot Womtool file check after DRA directories appeared. S3 `head-object` confirms `s3://lsmc-dayoa-references-usw2/runtime_assets/tool_specific_resources/womtool_87.jar` exists (122320885 bytes, last modified `2026-05-26T15:14:38Z`). Second live create `dragen-fix2-20260708` used file-level Womtool waiting and got past the one-shot check, but failed at `HeadNodeWaitCondition20260708014100` after the headnode script was still waiting on FSx/DRA metadata (`/fsx/references/runtime_assets/tool_specific_resources` absent in read-only SSM sample) while FSx import task `task-03594deccb4d82150` was still `EXECUTING` at 410040/410041 succeeded. ParallelCluster docs say slow custom scripts/headnode bootstrap require `DevSettings.Timeouts.HeadNodeBootstrapTimeout`; invalid custom-action `Timeout` was rejected by pcluster dry-run and removed. Current patch sets RHEL DRAGEN reference wait and template bootstrap timeouts to 7200s; `DAY_BREAK=1 dyec create ... dragen-fix3-20260708` passed pcluster dry-run. | RHEL DRAGEN readiness initially did a one-shot Womtool check; after that was fixed, the remaining blocker was DRA metadata visibility taking longer than the effective headnode wait condition for this large reference bucket. | Retest pending with `dragen-fix3-20260708`; no destructive cleanup was performed on failed stacks. |
| DGN-007 | DRAGEN Test | Run the requested DRAGEN test command using DYEC-pinned DayOA from the fresh branch/tag context. | OPEN | feature_implementation | Gate 5 | Codex | Pending; exact command/test surface to be resolved from repo/ledger context before launch. |  |  |

### Status Counts

- SUCCESS: 5
- OPEN: 1
- IN_PROGRESS: 0
- ATTEMPTING_BUGFIX: 1
- BLOCKED: 0
- FAIL: 0
