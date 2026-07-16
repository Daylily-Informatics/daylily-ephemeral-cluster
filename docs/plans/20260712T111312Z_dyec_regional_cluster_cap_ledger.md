# DYEC Regional Cluster Cap Ledger

Controlling request: cap DYEC cluster creation at five active ParallelCluster
clusters per AWS region by default, and require a state-bound double override
to create above that limit.

Ledger path: `docs/plans/20260712T111312Z_dyec_regional_cluster_cap_ledger.md`

## Gate 0 Baseline

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch: `jem-dev`
- Pre-existing untracked files, preserved and out of this feature's write scope:
  `docs/plans/20260712T102020Z_sentieon_license_server_usw2d_cloudformation.yaml`
  and `docs/plans/20260712T102020Z_sentieon_license_server_usw2d_ledger.md`.
- Shared create boundary: `daylily_ec.workflow.create_cluster.run_create_workflow`.
- Public CLI boundary: `daylily_ec.cli.create`.
- Stable Python helper: `daylily_ec.create.create_cluster`.
- ParallelCluster subprocess boundary: `daylily_ec.pcluster.runner`.
- Current live `us-west-2` evidence: three counted clusters
  (`ifx-reworkB`, `partrevert`, `hiomr-hg003-5x-0710`) and one excluded failed
  creation (`ursa-ilmnqc-0703`, ParallelCluster `CREATE_FAILED`, CloudFormation
  `ROLLBACK_COMPLETE`).
- Counting contract: count every cluster whose CloudFormation stack has not
  reached `ROLLBACK_COMPLETE` or `DELETE_COMPLETE`. This conservatively counts
  create/update/delete in progress and failed stacks that may still own live
  resources.
- Failure contract: unavailable CLI, malformed JSON, missing cluster fields,
  or an unrecognized/nonterminal state fails closed. No inferred count or
  cost-only bypass is allowed.
- Override contract: the default constant remains five. A proposed higher
  per-invocation cap requires a request-only invocation that returns a token,
  followed by a second invocation with the same account, region, target cluster,
  active-cluster snapshot, requested cap, and reason plus a named approver.
- Live mutation boundary: implementation and tests only. No cluster is created,
  updated, deleted, cancelled, or otherwise modified by this work.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| CAP-001 | Core contract | Define the default five-cluster regional cap and conservative active-state parsing | IN_PROGRESS | feature_implementation | Gate 2 | orchestrator | Planned module and tests |  |  |
| CAP-002 | PCluster | Add a strict `list-clusters` runner result used by the shared create boundary | OPEN | feature_implementation | Gate 2 | orchestrator | `daylily_ec/pcluster/runner.py` |  |  |
| CAP-003 | Override | Require request token, matching confirmation token, reason, approver, and unchanged state | OPEN | legitimate_safety_handling | Gate 4 | orchestrator | Planned token tests |  |  |
| CAP-004 | CLI/API | Expose and forward override options through `dyec create` and the stable Python helper | OPEN | config_or_startup_contract | Gate 2 | orchestrator | `daylily_ec/cli.py`, `daylily_ec/create.py` |  |  |
| CAP-005 | Tests | Cover below-cap, at-cap, failed-stack exclusion, fail-closed parsing, request, confirmation, mismatch, and CLI forwarding | OPEN | contract_test | Gate 5 | orchestrator | Focused pytest suite |  |  |
| CAP-006 | Docs | Document the hard default and exact two-invocation override flow | OPEN | active_product_contract | Gate 5 | orchestrator | `docs/cli_reference.md` |  |  |
| CAP-007 | Validation | Run focused tests, Ruff, CLI help, and diff checks without live creation | OPEN | contract_test | Gate 5 | orchestrator | Final validation commands |  |  |

## Acceptance Boundary

The objective is complete only when all rows are terminal, the default projected
sixth active cluster fails before any create/dry-run mutation, the override token
is invalidated by any bound-state change, and no live AWS cluster action occurs.
