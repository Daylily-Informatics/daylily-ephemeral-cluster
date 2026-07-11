# Private DYEC Deploy-Key Bootstrap Ledger

Created: 2026-07-11T04:08:08Z

## Objective

Add a separate read-only GitHub deploy key for
`lsmc-bio/daylily-ephemeral-cluster`, store it in a dedicated AWS Secrets
Manager secret, grant access only to the verified `ifx-reworkB` headnode role,
and use it to reinstall current DYEC before resuming the HG003 5x HIOMR run.
The existing DayOA deploy key and policy remain unchanged.

## Gate 0

- GitHub repository: `lsmc-bio/daylily-ephemeral-cluster`, private, default
  branch `jem-dev`, no existing deploy keys.
- AWS account/profile/region: `108782052779`, `lsmc`, `us-west-2`.
- No existing secret named
  `dayec/github-deploy-keys/lsmc-bio-daylily-ephemeral-cluster`.
- No existing managed policy named `DayECHeadnodeDYECClone`.
- Headnode: `i-059642d9ee4d5c9ea`; role
  `ifx-reworkB-RoleHeadNode-7Qqdb7DkjOvI`.
- Seven compute roles were enumerated by the cluster-specific IAM prefix; the
  headnode role is not in that set.
- The legacy headnode checkout is clean at DYEC `10.0.149`; its private HTTPS
  origin cannot authenticate. The working `DAY-EC` environment remains intact
  until deploy-key authentication is proven.

## Control Ledger

| ID | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|
| KEY-001 | Create a repository-scoped read-only DYEC GitHub deploy key | SUCCESS | config_or_startup_contract | Gate 1 | orchestrator | GitHub deploy key `156964384` exists on `lsmc-bio/daylily-ephemeral-cluster`, verified enabled and read-only |  | Repository-scoped DYEC authentication is available. |
| SECRET-001 | Store the private key in a dedicated Secrets Manager secret | SUCCESS | config_or_startup_contract | Gate 1 | orchestrator | Secret ARN `arn:aws:secretsmanager:us-west-2:108782052779:secret:dayec/github-deploy-keys/lsmc-bio/daylily-ephemeral-cluster-pE4FFN` exists |  | Private material remains in Secrets Manager and was not recorded. |
| IAM-001 | Create least-privilege secret-read policy and attach only to the headnode role | SUCCESS | legitimate_safety_handling | Gate 2 | orchestrator | `DayECHeadnodeDYECClone` is attached to `ifx-reworkB-RoleHeadNode-7Qqdb7DkjOvI`; all seven compute roles had zero attachment |  | No compute role received deploy-key secret access. |
| AUTH-001 | Prove headnode authentication with a temporary key and clean it up | SUCCESS | contract_test | Gate 3 | orchestrator | Strict pinned-host SSH authentication succeeded; final sweeps found no temporary deploy-key directory |  | Authentication and cleanup contracts passed. |
| INSTALL-001 | Recreate `DAY-EC`, clone/install DYEC `10.0.157`, and validate readiness | SUCCESS | live_validation | Gate 4 | orchestrator | Headnode reports DYEC `10.0.157` at exact commit `82f021fb57ab30595502a01d112fdfad4226c71b`; prior checkout retained as a timestamped backup |  | Current DYEC is installed from its private repository. |
| DAYOA-001 | Validate private DayOA clone through its separate deploy key | SUCCESS | live_validation | Gate 4 | orchestrator | `day-clone --check-auth` and a full version-pinned private DayOA clone succeeded with the separate DayOA deploy key |  | Both private repositories clone independently. |
| RUN-001 | Resume the fresh HG003 5x HIOMR launch | NO_LONGER_NEEDED | live_validation | Gate 5 | orchestrator | Workflow execution is controlled by `docs/plans/20260711T035603Z_hiomr_hg003_5x_index_fix_live_ledger.md`, not this authentication ledger |  | Deploy-key acceptance does not depend on launching a paid workflow. |

## Compute Roles

- `ifx-reworkB-ComputeFleetQueues-Role0a4928560b35ff6d-ZxWlkYnj9YPy`
- `ifx-reworkB-ComputeFleetQueues-Role18b1a9ea4e81c872-zBYLkxivPcqU`
- `ifx-reworkB-ComputeFleetQueues-Role7e156bfc7a3b620e-pOPJnmFHfx0s`
- `ifx-reworkB-ComputeFleetQueues-Role94f0e27775450e09-Ax235FuRlltq`
- `ifx-reworkB-ComputeFleetQueues-RoleB6f7a4ba7d5a78bd-b14aOxHl4evy`
- `ifx-reworkB-ComputeFleetQueues-RoleCd53fa91fbffcf32-4Z4oG8qQjKOb`
- `ifx-reworkB-ComputeFleetQueues-RoleFfdcc1776faccb72-XBPWfaz4v8sG`

## Closeout

- All rows are terminal.
- The private DYEC bootstrap objective is complete.
- No compute role received either repository deploy-key policy.
- No workflow was launched as part of this authentication ledger.
