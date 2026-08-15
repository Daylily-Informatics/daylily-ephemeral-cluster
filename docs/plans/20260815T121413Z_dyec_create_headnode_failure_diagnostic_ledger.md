# DYEC 18.0.9 create headnode failure diagnostic ledger

Created: 2026-08-15T12:14:13Z

## Objective

Diagnose the failed `dyec create` for `prodcand-dyec-1809`, preserve the exact
live-resource boundary, implement and publish the durable installer repair, and
use that immutable release to finish configuration of the existing cluster.

## Gate 0 baseline

- Controlling ledger: `docs/plans/20260815T121413Z_dyec_create_headnode_failure_diagnostic_ledger.md`.
- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch
  `codex/dyec-cli-docs-18009`, HEAD `57916740ed2580883af5d1486726d5b27357fd16`.
- Release under diagnosis: annotated tag `18.0.9`, commit
  `5304927563169a4005005c37aa192d5d95f5b390`.
- Pre-existing unowned worktree paths: `TrusSV/` and
  `tmp/dayoa-ont-headnode-proof/`; neither was inspected or changed.
- User evidence: pasted create output ended after SSM command
  `26311973-3755-46d1-8ccf-072205260e34` returned `Failed`, response code `1`.
- Live inspection was read-only. No create retry, headnode reconfiguration,
  workflow command, Slurm action, resource deletion, budget change, cost-center
  change, or cleanup was authorized or performed.

## Implementation amendment: 2026-08-15

- The user explicitly authorized the durable code fix, commit, next immutable
  patch release, and `dyec headnode configure` against the existing cluster.
- Release branch: `codex/conda-channel-idempotence-18010`, created from current
  `origin/main` at `57916740ed2580883af5d1486726d5b27357fd16`.
- Current remote tag inventory ends at annotated tag `18.0.9`; the inferred
  next patch release is `18.0.10`.
- Focused pre-change baseline:
  `python -m pytest -q tests/test_install_miniconda.py` -> `12 passed`.
- The existing cluster, FSx, DRA, budget, and cost center will be reused. No
  second cluster create, resource replacement, cleanup, or Slurm action is in
  scope.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval gate | Owner | Evidence | Root cause | Terminal note |
|---|---|---|---|---|---|---|---|---|---|
| DIAG-001 | ParallelCluster | Establish whether cluster provisioning failed | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | `dyec cluster describe --profile lsmc --region us-west-2 --cluster prodcand-dyec-1809` returned cluster and CloudFormation `CREATE_COMPLETE`, compute fleet `RUNNING`, headnode `i-079894b81329b078a` running |  | Cluster provisioning completed; failure is later headnode configuration. |
| DIAG-002 | SSM | Capture the exact failed unit and stderr | SUCCESS | config_or_startup_contract | Gate 0 | orchestrator | `get-command-invocation` for command `26311973-3755-46d1-8ccf-072205260e34` returned comment `Rebuild DAY-EC and install headnode tools`, rc `1`, and `CondaKeyError: 'channels': value 'defaults' not present in config` |  | Failure is deterministic Conda bootstrap behavior, not FSx, DRA, quota, IAM preflight, or ParallelCluster creation. |
| DIAG-003 | DYEC source | Identify the causal source path | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | `create_cluster.py` runs an earlier `Install Miniconda` step, then `install-daylily-headnode-tools`; that installer invokes `bin/install_miniconda` again. `bin/install_miniconda:197-199` tests effective `conda config --show channels` for `defaults` and then removes it from explicit config. |  | The second installer invocation sees Conda's implicit effective `defaults` but no explicit `defaults` entry, so `conda config --remove channels defaults` fails. |
| DIAG-004 | Headnode | Verify partial configuration state without repair | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | `dyec headnode run` as `ubuntu` showed clean detached release commit `53049275...`, existing `DAY-EC`, explicit `.condarc` channels `conda-forge` and `bioconda`, effective channels also showing implicit `defaults`, helpers `day-clone`/`sq`/`sqq` present, and `daylily-headnode-bootstrap.sh` missing |  | Headnode configuration stopped after helper copies and during the nested Miniconda call, before managed login bootstrap creation and final readiness validation. |
| LIVE-001 | FSx/DRA | Preserve and report current storage state | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | FSx `fs-03af47199fe0c8812` is `AVAILABLE`, PERSISTENT_2, 2400 GiB, 125 MB/s/TiB; DRA `dra-082a6853a314b2099` is `AVAILABLE` at `/references/` for `s3://lsmc-dayoa-references-usw2` |  | Live storage exists and was not retried, detached, or deleted. |
| LIVE-002 | Budget/cost center | Preserve and report pre-create side effects | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | Project budget `prodcand-dyec-1809` exists at USD 200 monthly; cost center `prodcand-dyec-1809-ccenter` is active at USD 200 monthly for `ubuntu` |  | These resources were created before the headnode failure and remain active. |
| RECOVERY-001 | Durable repair | Define the supported next action without applying it | SUCCESS | plan_amendment | Gate 2 | orchestrator | Source and tests inspected; current tests simulate one successful removal and do not exercise a second installer run with implicit `defaults` |  | Repair `install_miniconda` idempotence in both source and packaged mirror, add a two-run regression test, publish the next immutable patch release, then run that release's `dyec headnode configure` against the existing cluster. Do not rerun `dyec create`. |
| AMEND-001 | Scope | Authorize implementation, release, and existing-cluster repair | SUCCESS | plan_amendment | Gate 2 | orchestrator | User explicitly requested the quoted durable path and a committed fix |  | Repair and non-destructive headnode configuration are now in scope; destructive cleanup remains out of scope. |
| FIX-001 | Installer | Make explicit channel removal idempotent in source and packaged mirror | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | `bin/install_miniconda` and packaged mirror now query `conda config --get channels`; `cmp` and `bash -n` pass |  | Effective implicit channels no longer trigger removal from explicit configuration; failed config queries still fail hard. |
| TEST-001 | Installer tests | Prove two consecutive installer runs succeed when `defaults` becomes implicit after the first run | SUCCESS | contract_test | Gate 2 | orchestrator | Dedicated two-run regression passes; combined installer/headnode/docs suite `41 passed`; full suite `2593 passed, 11 skipped` |  | The fake Conda contract rejects a second `defaults` removal, proving the original failure cannot recur silently. |
| GATE-001 | Release gate | Make the current operator-doc release check valid both on the authorized `18.0.10` release branch and exact tag | SUCCESS | plan_amendment | Gate 5 | orchestrator | Initial full suite reached `2592 passed, 11 skipped` with only the post-tag version assertion failing; current release statements now use `18.0.10`, base-release comparison passes, final full suite is green |  | Pretag PR and exact-tag validation now enforce the same release identity without changing historical ledgers or numeric catalog examples. |
| RELEASE-001 | GitHub/package release | Commit, PR, merge, and push annotated non-v tag `18.0.10` | IN_PROGRESS | feature_implementation | Gate 5 | orchestrator | Local full suite `2593 passed, 11 skipped`; static checks, source/payload identity, and whitespace checks pass |  |  |
| CONFIG-001 | Existing headnode | Run exact `18.0.10` `dyec headnode configure` for `prodcand-dyec-1809` | OPEN | config_or_startup_contract | Gate 5 | orchestrator | Existing cluster is `CREATE_COMPLETE`; no new create is needed |  |  |
| VERIFY-001 | Existing headnode | Verify exact installed DYEC version, managed login bootstrap, helpers, and readiness | OPEN | contract_test | Gate 5 | orchestrator | Pending successful configuration |  |  |

## Final report

All rows terminal: no

Diagnostic objective complete: yes

Repair objective complete: no; implementation is in progress.

Status counts:

- SUCCESS: 11
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0
- IN_PROGRESS: 1
- OPEN: 2

Validation:

- Live cluster, SSM invocation, FSx, DRA, budget, cost center, and bounded
  headnode state were inspected read-only.
- Release source and current tests were inspected at the exact tagged commit.
- Pre-change focused installer baseline: `12 passed`.
- Post-change full repository suite: `2593 passed, 11 skipped`.

Residual risks:

- `prodcand-dyec-1809` remains running and incurs cost; the create output's
  configured idle estimate was USD 1.0570/hour.
- Headnode readiness is incomplete and the managed login bootstrap is absent.
- Create returned before post-create heartbeat/state handling; no local
  `state_prodcand-dyec-1809_*` record exists.
- Re-running `dyec headnode configure` from unchanged `18.0.9` will traverse the
  same failing installer path.
