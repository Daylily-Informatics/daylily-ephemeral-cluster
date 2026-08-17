# Slurm Accounting PrivateLink Reconciliation Ledger

Created: 2026-08-17T04:24:01Z

## Objective

Make a DYEC cluster create that requests Slurm accounting reconcile an existing,
deterministically named PrivateLink bridge to the running DYEC template contract
before it is resolved for cluster attachment. A stale bridge must be upgraded in
place or fail before any compute-fleet mutation; no guessed CIDR, alternate bridge,
or service-specific discovery is allowed.

## Control Ledger

Controlling plan: this file

Ledger path: `docs/plans/20260817T042401Z_slurm_accounting_privatelink_reconciliation_ledger.md`

Gate 0 baseline:

- Repo: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-18020-privatelink-reconcile`
- Branch/base: `codex/dyec-18020-privatelink-reconcile` at `0c5b49ca37a436ae43d98233a73cdaec9afcd9cf`, tracking `origin/main`.
- Initial status: clean (`git status --short --branch`).
- Current release baseline: latest merged annotated release is `18.0.19`; this change targets the next patch release.
- Source sweep: `git grep -n "resolve_slurm_accounting_privatelink_bridge_for_consumer\|ensure_slurm_accounting_privatelink_bridge" -- daylily_ec tests` -> 13 matches.
- Baseline tests: `python -m pytest -q tests/test_slurm_accounting_privatelink.py tests/test_attach_slurm_accounting.py` -> 22 passed.
- Incident evidence: Ursa provider `ursa-m-rgx-hp08` reached base `CREATE_COMPLETE`; post-create accounting stopped at `service_preparation` because existing bridge `dayec-sacct-pl-vpc-06b01782f2abece1c` lacked `AccountingClientSecretReadPolicyArn`. Running the public idempotent `slurm-accounting privatelink ensure` command updated that exact stack in place, after which supported attach reached `UPDATE_COMPLETE` with accounting enabled.
- Ownership: DYEC owns bridge reconciliation and cluster/accounting orchestration. Ursa remains an upstream caller of the public DYEC create contract.
- Live limits: source/test work is authorized. No cluster deletion, Slurm daemon administration, job mutation, or other destructive AWS action is part of this ledger.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| PL-001 | DYEC PrivateLink | Reconcile an existing deterministic bridge using its authoritative stored subnet CIDR and the current packaged template. | SUCCESS | feature_implementation | Gate 2 | orchestrator | `reconcile_existing_slurm_accounting_privatelink_bridge_for_consumer` reads the exact `ConsumerEndpointSubnetCidr` CloudFormation parameter, calls the existing idempotent ensure operation on the deterministic stack, and rejects missing stack/parameter state. |  | Existing-only reconciliation is implemented without guessed network defaults. |
| PL-002 | DYEC post-create accounting | When explicitly approved accounting creation encounters a regional provider in another VPC, reconcile the deterministic existing bridge before resolving it. | SUCCESS | feature_implementation | Gate 2 | orchestrator | `prepare_slurm_accounting_update` reconciles only when `create_if_missing=True` and exactly one regional provider exists; read-only attach continues to resolve without mutation. |  | The operation remains before update-config rendering and all compute-fleet mutation. |
| PL-003 | Contract tests | Prove stale existing bridges update before resolution and that missing/ambiguous configuration fails before fleet mutation. | SUCCESS | contract_test | Gate 4 | orchestrator | `python -m pytest -q tests/test_slurm_accounting_privatelink.py tests/test_attach_slurm_accounting.py tests/test_postcreate_slurm_accounting.py tests/test_slurm_accounting_contract.py tests/test_cli_docs_contract.py` -> 67 passed; `git diff --check` -> pass. |  | Positive reconciliation, stored-CIDR reuse, negative missing-CIDR, read-only reuse, structured failure, post-create receipt, and docs contracts pass. |
| PL-004 | Release | Commit, publish, merge, and create the next immutable annotated DYEC patch release. | SUCCESS | feature_implementation | Gate 5 | orchestrator | Source commit `ff0946346fd8576e00b3ea3f89654cbfdebc7aec`; PR `#125`; merge `b0eb6f5112e6e941101131408d892534016310d3`; annotated tag `18.0.20` object `e64464eec4755a6b2508b78d2ebc1c080dcd3f85` peels to the merge commit; GitHub release published. |  | Immutable DYEC `18.0.20` is released. |
| PL-005 | Ursa integration | Pin the released DYEC patch in Ursa and prove Ursa's create command retains explicit accounting approval and final `UPDATE_COMPLETE` gating. | SUCCESS | contract_test | Gate 5 | orchestrator | Ursa `11.0.38` commit/tag `d80590697b22297963a345e084ee62efbcb3fb77` pins DYEC `18.0.20` and DayOA `15.0.10`; focused integration tests passed. The required third-pass full suite produced 2,115 passed, 4 skipped, and 29 failures, all reproduced from untouched pre-change commit `f14d4ec9fe9f217fed858149ec7dc2a7434990d7` in the affected files. |  | Explicit accounting-create/cost acknowledgement and the `UPDATE_COMPLETE` plus live-`ENABLED` scheduling boundary remain strict. |
| PL-006 | Production acceptance | Build/deploy the released Ursa image and capture read-only evidence from a fresh Ursa cluster create. | SUCCESS | feature_implementation | Gate 5 | orchestrator | Ursa image digest `sha256:d60367d0a9902dd3c8cd71b57175111816d448afbe8c0e745fec53e382419e2c` was built only on Dayhoff EC2 `i-07df3a933e4839f52` and narrowly deployed to all six Ursa roles with zero restarts and seven unchanged non-Ursa identities. Local/public readiness reports Ursa `11.0.38`; in-container evidence reports DYEC `18.0.20`, DayOA `15.0.10`, and catalog SHA-256 `8b066bf824ed1bf2cad4bcfe125799f97a1c86e0b658625ad61acd13f4217738`. Fresh scheduler-created provider `ursa-m-rgx-hnm0` is `UPDATE_COMPLETE`; its stack includes the current bridge policy and read-only SSM command `103c4d3f-220c-48ed-b35f-496f0427a014` proved `sacctmgr` registration at `10.0.0.184:6820` and `AccountingStorageType=accounting_storage/slurmdbd`. |  | The post-deploy scheduler queue was empty, so no additional billable cluster was created solely to duplicate the live proof. |

## Final Report

All rows terminal: yes

Objective complete: yes
