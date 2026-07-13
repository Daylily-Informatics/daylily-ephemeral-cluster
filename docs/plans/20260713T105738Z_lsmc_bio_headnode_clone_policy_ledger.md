## Control Ledger

Controlling request: make LSMC Git credential access less fussy so any DayEC head node can read the configured `lsmc-bio` deploy-key credentials and clone explicitly configured repositories.

Ledger path: `docs/plans/20260713T105738Z_lsmc_bio_headnode_clone_policy_ledger.md`

Gate 0 baseline:

- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster-sentieon-single`
- Branch/ref: `sentieon-single` at `202a04dcb35bb07d1411efbb159d279f6f177d01` (`10.3.2`).
- Pre-existing dirty state preserved: modified `docs/plans/20260713T083000Z_sent_hg003_hiomrs_kitchensink_1x_monitor_ledger.md` and untracked `docs/plans/20260712T192000Z_sent_hg003_runtime_cache_publish.py`.
- Live cluster: `sentlic-e`, `CREATE_COMPLETE`, compute fleet `RUNNING`, head node `i-048ff099d73057e09`, role `sentlic-e-RoleHeadNode-jGuA3osTN289`.
- Original failure: automatic SSM command `daab6b04-8686-41c7-92fe-d7ece19226f0` (`Clone repository to headnode`) failed with rc 1 but did not retain command stderr.
- Read-only credential probe: SSM command `436816de-39ff-40cc-8277-55c68887fba0` ran as `ubuntu` and proved the pinned known-hosts file, exact Secrets Manager read, OpenSSH private key, and GitHub `git ls-remote` all work; `origin/sentieon-single` resolved to `202a04dcb35bb07d1411efbb159d279f6f177d01`.
- Existing policies are repository-specific: `DayECHeadnodeDYECClone` reads one exact DYEC secret and `DayECHeadnodeDayOACloneExact` reads one exact DayOA secret.
- Existing secret-name prefix shapes are `dayec/github-deploy-keys/lsmc-bio/...` and `dayec/github-deploy-keys/lsmc-bio-...`.
- Approved target contract: one shared headnode-only policy may perform only `secretsmanager:DescribeSecret` and `secretsmanager:GetSecretValue` on `arn:aws:secretsmanager:us-west-2:108782052779:secret:dayec/github-deploy-keys/lsmc-bio*`. Compute roles receive no policy. Repository-to-secret mappings remain explicit; no list/discovery permission or credential fallback is added.
- Active-cluster inventory: `sentlic-e` is the only `CREATE_COMPLETE` ParallelCluster in `us-west-2` at Gate 0.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| IAM-001 | DYEC source | Replace exact-secret preflight/defaults with one explicit `lsmc-bio*` organization-prefix headnode policy contract | SUCCESS | config_or_startup_contract | User-approved headnode credential broadening | orchestrator | Updated validator, three source/packaged configs, README, CLI reference, and focused tests; 6 policy tests plus 6 workflow tests passed; packaged config byte-identical |  | Source contract is implemented without secret listing, discovery, compute attachment, or credential fallback |
| IAM-002 | AWS IAM | Create/update shared managed policy and attach it to every active DayEC head node, never compute roles | SUCCESS | active_product_contract | User-approved live IAM change | orchestrator | Created `DayECHeadnodeGitHubClone` v1 with exact two read actions on `...:secret:dayec/github-deploy-keys/lsmc-bio*`; attached to sole active headnode role; detached two redundant exact policies; simulation allowed all three existing secrets and denied `ListSecrets` |  | Shared policy is live on every active DayEC headnode and absent from compute roles |
| HN-001 | `sentlic-e` | Rerun supported headnode configuration and prove exact DYEC ref plus DayOA auth readiness | SUCCESS | config_or_startup_contract | Supported headnode configuration | orchestrator | `dyec headnode configure` completed successfully after the key-validation fix. SSM `a4c958e5-7dce-4f46-b711-009eaca1ccc2` ran as `ubuntu` and proved origin `git@github.com:lsmc-bio/daylily-ephemeral-cluster.git`, HEAD `202a04dcb35bb07d1411efbb159d279f6f177d01`, tag `10.3.2`, and `day-clone --check-auth --repository daylily-omics-analysis --git-tag 10.0.97` success | Clone bootstrap rejected a valid key because AWS CLI output included a trailing blank line and the shell required the final physical line to equal the OpenSSH end delimiter | Supported configuration and both explicit repository credential paths are ready |
| QA-001 | Repo/live acceptance | Run focused tests, packaged-config parity, diff checks, IAM readback, and final cluster/headnode checks | SUCCESS | contract_test | Final acceptance | orchestrator | Six deploy-key policy tests and six focused workflow tests passed; Ruff, packaged-config byte parity, and scoped `git diff --check` passed. Live source preflight passed for both exact secret mappings without reading values. IAM readback showed the shared policy only on `sentlic-e-RoleHeadNode-jGuA3osTN289`; every rendered compute queue omits it. Final cluster state remained `CREATE_COMPLETE`, compute fleet `RUNNING`, headnode running. The broader 141-test pair had 140 passes and one known unrelated Sentieon template `i96nvme` MaxCount contract failure. |  | Requested contract is accepted; unrelated pre-existing test failure was not changed |

## Current Report

All rows terminal: yes.

Objective complete: yes. The account now has one shared, read-only, headnode-only LSMC Bio deploy-key policy; current `sentlic-e` and future source defaults use it. Repository selection remains explicit and no credential fallback or secret discovery was introduced.

Operational note: the already-created `sentlic-e` stack's stored ParallelCluster configuration still names the two former exact policies, while the live headnode role has the shared policy and not those exact policies. This is expected live stack drift from repairing the active cluster; future clusters rendered from this source use the shared policy directly.
