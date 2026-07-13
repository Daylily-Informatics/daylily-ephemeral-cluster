# Sentieon Dedicated License Server Cutover: Ten-Agent Ledger

Controlling request: configure the existing `usw2d-01.sentieon.lsmc.bio`
license-server host from the vendor-issued cluster license, move DayOA/DYEC to
the dedicated endpoint contract on the requested `10.3.4` release branch,
make that contract the generated default inherited by future branches, and
apply it to ParallelCluster `sentlic-e`.

Ledger path:
`docs/plans/20260713T103715Z_sentieon_license_server_cutover_10agent_ledger.md`

## Gate 0 Baseline

- DYEC worktree: `/Users/jmajor/projects/lsmc/.worktrees/dyec-10.3.4-sentieon-license`
  on new branch `10.3.4`, based on `origin/sentieon-single` commit
  `34d6761732d7d4bac2d7b08cff676d48b12013a1` / tag `10.3.1`.
- DayOA worktree: `/Users/jmajor/projects/lsmc/.worktrees/dayoa-10.3.4-sentieon-license`
  on new branch `10.3.4`, based on `origin/sentieon-single` commit
  `f1badba142059173376938fe05eea49c8bf811de` / tag `10.3.0`.
- Neither repository had a local or remote `10.3.4` ref before these isolated
  branches were created. The dirty `jem-dev` and existing `sentieon-single`
  worktrees remain untouched.
- Existing infrastructure: CloudFormation stack
  `sentieon-license-usw2d-01`, EC2 `i-03c42907b08018d1a`, `t3.xlarge`,
  `us-west-2d`, private IP `10.0.0.205`, EIP `52.40.208.196`, SG
  `sg-004e7647782ff1cf9`, backend `usw2d-01.sentieon.lsmc.bio`, client alias
  `license.sentieon.lsmc.bio:8990`.
- Vendor file: local source
  `/Users/jmajor/Downloads/Life_Sciences_Data_Manufacturing_cluster.lic`;
  SHA-256 `6f16e3e301c41d3e21736dc69732146dff8aad9db8eb2707bc0b05e3d7ca20f4`.
  The file contents and license key must never appear in command output,
  logs, tests, commits, or this ledger.
- License metadata already inspected without printing the key: bound to
  `usw2d-01.sentieon.lsmc.bio` and expiring `2026-07-31`.
- Target client cluster: `sentlic-e`, headnode `i-048ff099d73057e09`
  (`r7i.8xlarge`, `us-west-2d`, `10.0.0.184`), reached
  `CREATE_COMPLETE`; the headnode is SSM-online and shares VPC
  `vpc-06b01782f2abece1c` with the license server.
- Existing active controllers and Slurm jobs on any cluster are not restarted,
  cancelled, or modified by this cutover. Only new shells/jobs inherit the
  endpoint after configuration.
- Intended endpoint: `license.sentieon.lsmc.bio:8990`. DayOA retains the
  existing randomized 1-160 second client-start jitter for the initial soak,
  but no per-job local license server or local license-server probe.
- Network contract: explicit allowed CIDRs only. Never authorize
  `0.0.0.0/0` on TCP 8990. Same-VPC clients use the private split-horizon
  address; cross-VPC clients require an explicit observed NAT egress CIDR.
- Future-branch contract means source templates, packaged templates, startup
  code, and negative tests on `10.3.4` all use the endpoint schema. Branches
  created from this release line inherit it; Git history is not rewritten.
- Live mutation boundary: the user explicitly requested server configuration
  and `sentlic-e` application. Destructive replacement, instance teardown,
  cluster restart, or controller restart is not approved.

### Gate 0 Amendments

- While this isolated branch was under validation, the maintained descendants
  advanced through DayOA tag `10.3.8` and DYEC tag `10.3.5`. That work was
  preserved. The reviewed cutover commits were merged forward without resets,
  force pushes, tag movement, or history rewriting.
- The deployed `sentlic-e` configuration referenced mutable shared bootstrap
  keys. The exact five-file candidate was published append-only at
  `s3://lsmc-dayoa-references-usw2/runtime_assets/cluster_boot_config/releases/sha256-2f2578f6469fe4668a3fc86d9520b6a57060989c33c010e018caff5821e5ec8f/`.
  Future cluster creation now derives and renders a content-addressed prefix.
- ParallelCluster dry-run found a deleted headnode additional SG,
  `sg-0c8f3047dfc85b1c0`, in the saved configuration. AWS confirms that SG is
  absent and the running headnode uses only its managed SG
  `sg-05d44b1844e7651b0`. The candidate removes only the stale reference.
- The saved configuration also contains duplicate S3Access rows for
  `lsmc-ssf-sequencing-data`. ParallelCluster reconciles them to one effective
  write-enabled row even on a no-op reload. The candidate preserves that
  effective permission and records the existing normalization separately from
  the Sentieon queue-bootstrap changes.
- The first `sentlic-e` update exposed two pre-existing deleted dependencies:
  the configured Slurm accounting secret and an additional headnode security
  group. Rollback also could not restore the deleted security group. Recovery
  used CloudFormation continue-rollback with only `HeadNodeENI` and
  `RoleHeadNode` skipped; the headnode instance and FSx filesystem were not
  replaced.
- A supported `dyec slurm-accounting ensure --region-az us-west-2d` created the
  same-VPC accounting endpoint `10.0.1.23:3306`, client security group
  `sg-01f35feea21209aed`, and exact password secret
  `arn:aws:secretsmanager:us-west-2:108782052779:secret:AccountingPasswordSecret-UZMOKNavo6F9-FxUlfN`.
  The temporary exact bootstrap policy used during IAM propagation was removed
  after the cluster update succeeded.
- The final rendered `sentlic-e` candidate had SHA-256
  `1addec0f7f6455d891edbf8130d99fe0750c40f58bcd3ee74f95ea325fad23cf`.
  ParallelCluster reached `UPDATE_COMPLETE` with the original headnode
  `i-048ff099d73057e09` and FSx `fs-0596bfcffb12adb81`; all eleven queues now
  reference the immutable bootstrap bundle.
- The cost-center registry row was absent even though AWS already had a
  `$200` `sentlic-e` budget. A supported create operation registered the same
  `$200` cap, so this was not a budget increase. Compute smoke job `1` failed
  only because its diagnostic checked a nonexistent log path. Corrected job
  `2` completed in eight seconds and proved endpoint inheritance, private DNS,
  absence of a local service/file/listener, and successful vendor ping. The
  compute fleet was returned to `STOPPED` after the queue became empty.
- Retention hardening remains in the canonical CloudFormation source. Change
  set `sentieon-retain-hardening-20260713T120239Z` was deliberately not
  executed because its conditional EIP-association replacement was outside
  the approved live-mutation boundary; it made no live change.

## Agent Ownership

| Agent | Ownership | Exclusive write scope |
|---|---|---|
| 1 | Orchestrator, Gate 0, integration, live sequencing, ledger closeout | This ledger and final integration only |
| 2 | Secret ingestion and secret-safety validation | New secret/bootstrap scripts and secret tests |
| 3 | Sentieon server runtime/service installer | New server install/service assets and tests |
| 4 | CloudFormation IAM, instance bootstrap, and CloudWatch | License-server IaC template and IaC tests |
| 5 | Route 53, SG allowlist, and network validation | Network scripts/tests and network runbook section |
| 6 | DayOA activation/config endpoint contract | `dyoainit`, `bin/day_activate`, config and focused tests |
| 7 | DayOA wrappers/rules endpoint compatibility | Sentieon wrappers, active rule checks, focused tests |
| 8 | DYEC defaults and headnode/compute propagation | Source/packaged config, bootstrap/configure code, focused tests |
| 9 | Operator runbook and migration evidence | New dedicated runbook and docs tests |
| 10 | Read-only integration review and validation matrix | No production source writes; review report only |

Agents must not change files outside their exclusive scope. Agents 6 and 7
coordinate through the orchestrator before touching any shared shell test.

## Control Ledger

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| GATE-001 | Inventory | Freeze refs, dirty-tree isolation, live AWS identities, license hash, endpoint, and non-destructive boundaries | SUCCESS | plan_amendment | Gate 0 | 1 | Gate 0 baseline above; `git ls-remote` found no pre-existing `10.3.4`; isolated worktrees created from published `sentieon-single` bases |  | Baseline recorded before implementation. |
| SECRET-001 | DYEC/AWS | Store the vendor license as encrypted Secrets Manager binary material without printing or committing it | SUCCESS | feature_implementation | Gate 2 | 2 | Binary secret `dayec/sentieon/license-servers/usw2d-01`, exact version `3b3791ce-1417-4482-85e2-71048aed323a`; local metadata receipt mode `0600`; source and remote SHA-256 match `6f16e3e301c41d3e21736dc69732146dff8aad9db8eb2707bc0b05e3d7ca20f4` |  | Secret bytes never appeared in command output or repository state. |
| SECRET-002 | DYEC/AWS | Grant only the dedicated server role access to the exact secret and prove compute/headnode roles lack access | SUCCESS | contract_test | Gate 2 | 2 | IAM simulation: dedicated role `allowed`; `sentlic-e` headnode plus all eleven queue roles `implicitDeny` for exact-secret `GetSecretValue` |  | No client role received secret access. |
| SERVER-001 | DYEC/AWS | Install the minimal pinned Sentieon 202503.03 license-server runtime under `/opt/sentieon/202503.03` | SUCCESS | feature_implementation | Gate 2 | 3 | Four exact S3 objects installed root-owned; SHA-256 values `6630a9...`, `2d4dbf...`, `dbc621...`, and `1eb02f...` verified before and after install |  | Only `bin/sentieon`, `share/funcs`, `libexec/licsrvr`, and `libexec/licclnt` were installed. |
| SERVER-002 | DYEC/AWS | Install hardened systemd lifecycle using the vendor `licsrvr --start` contract, restricted files, and no secret leakage | SUCCESS | feature_implementation | Gate 2 | 3 | `sentieon-license-server.service` enabled/active, `MainPID=14484`, listener PID `14485`, zero restarts, systemd exposure score `4.8 OK`; license is `root:sentieon 0640` |  | Vendor service is the sole listener on private `10.0.0.205:8990`. |
| SERVER-003 | DYEC/AWS | Send license-server logs to CloudWatch with bounded retention and redact validation evidence | SUCCESS | feature_implementation | Gate 2 | 4 | Exact CloudWatch Agent `1.300069.0b1529` is enabled/active; log group `/sentieon/licsrvr/LicsrvrLog` has 90-day retention and stream `i-03c42907b08018d1a` |  | Source now installs the exact agent build explicitly and configures log collection without displaying payloads. |
| IAC-001 | DYEC | Promote the existing host draft into canonical IaC without replacing the live instance | SUCCESS | config_or_startup_contract | Gate 2 | 4 | Canonical template validates in CloudFormation; reviewed executed change set modified only the server IAM role and added the log group with `Replacement=False` |  | Instance, EIP, DNS, SG, and private address were unchanged. |
| NET-001 | AWS | Preserve split-horizon backend/service DNS and authorize only explicit client source CIDRs on TCP 8990 | SUCCESS | config_or_startup_contract | Gate 2 | 5 | Private DNS resolves both names to `10.0.0.205`; server SG `sg-004e7647782ff1cf9` allows TCP 8990 only from `10.0.0.0/16` |  | No public ingress or cross-VPC rule was added. |
| NET-002 | AWS | Validate same-VPC and, where applicable, cross-VPC endpoint reachability without opening public ingress | SUCCESS | contract_test | Gate 5 | 5 | Both FQDNs resolve to `10.0.0.205` in the shared VPC; SG ingress remains only TCP 8990 from `10.0.0.0/16`; no cross-VPC rule was required |  | Private-path validation complete. |
| DAYOA-001 | DayOA | Replace file-only activation/config assumptions with a strict `host:port` endpoint contract | SUCCESS | config_or_startup_contract | Gate 2 | 6 | Central parser/activation helper plus focused endpoint tests; DayOA full suite `755 passed`; published commits `404fff2`, `5d53937`, and `01328da` |  | Missing, file, scheme, path, malformed, inherited-mismatch, and repeated-source cases fail or resolve deterministically before execution. |
| DAYOA-002 | DayOA | Export the endpoint into Slurm and Singularity execution environments for every new job | SUCCESS | feature_implementation | Gate 2 | 6 | Profile env and config templates export `SENTIEON_LICENSE`, `APPTAINERENV_SENTIEON_LICENSE`, and `SINGULARITYENV_SENTIEON_LICENSE` |  | All active profile templates use the server endpoint. |
| DAYOA-003 | DayOA | Make all active Sentieon rules accept the endpoint and reject missing/malformed values consistently | SUCCESS | feature_implementation | Gate 2 | 7 | Included-rule dynamic sweep plus wrapper/rule tests; orchestrator focused suite `90 passed` |  | Active Sentieon calls cross the validated wrapper boundary. |
| DAYOA-004 | DayOA | Retain 1-160 second jitter while removing local licsrvr start/probe behavior | SUCCESS | legitimate_safety_handling | Gate 4 | 7 | Wrapper default samples `1..160`; repository sweep rejects local start/dump/ping behavior |  | Explicit jitter value `0` remains the deliberate disable control. |
| DYEC-001 | DYEC | Change source and packaged generated defaults to `license.sentieon.lsmc.bio:8990` with exact parity | SUCCESS | local_dev_default | Gate 2 | 8 | Source/package config and installer parity; focused DYEC suite `62 passed` |  | Canonical generated default is server mode and the service FQDN. |
| DYEC-002 | DYEC | Propagate the endpoint during headnode/compute configuration and reject stale file-only generated config | SUCCESS | config_or_startup_contract | Gate 2 | 8 | Ubuntu/RHEL source and packaged post-install paths plus readiness tests |  | Supported live configure awaits publication of branch `10.3.4`. |
| FUTURE-001 | Both | Add negative tests preventing future branches from restoring local license-file/server fallback | SUCCESS | contract_test | Gate 4 | 6-8 | Negative activation, bootstrap, packaged-default, and included-rule tests |  | Descendant branches inherit the contract; older divergent history is not rewritten. |
| DOC-001 | DYEC | Publish an operator runbook for server lifecycle, client migration, rotation, HA expansion, and rollback | SUCCESS | feature_implementation | Gate 5 | 9 | `docs/sentieon_license_server_runbook.md`, SHA-256 `049c943886179aebfd1953fa1c5366d1545890591f5efc182afabe92aa12169d` |  | Includes expiry gates, identity-policy-only secret access, explicit service restart approval, pinned CloudWatch installation, and immutable bootstrap rules. |
| LIVE-001 | AWS | Deploy secret/runtime/service changes to `usw2d-01` without EC2 replacement and prove TCP 8990 is listening | SUCCESS | feature_implementation | Gate 5 | 1 | Instance remained `i-03c42907b08018d1a`, private IP `10.0.0.205`, EIP `52.40.208.196`; service listener verified |  | No instance, address, DNS, or security-group replacement occurred. |
| LIVE-002 | AWS | Validate vendor client connectivity through backend and service FQDNs with redacted evidence | SUCCESS | contract_test | Gate 5 | 1 | `licclnt ping` succeeded through both `usw2d-01.sentieon.lsmc.bio:8990` and `license.sentieon.lsmc.bio:8990` |  | No raw dump or license value was emitted. |
| CLIENT-001 | sentlic-e | Wait for cluster readiness, configure the endpoint through supported DYEC paths, and verify new shell inheritance | SUCCESS | feature_implementation | Gate 5 | 1 | Supported `dyec headnode configure` completed from DYEC commit `40f50133`; a new login shell exported `SENTIEON_LICENSE=license.sentieon.lsmc.bio:8990`; no local unit, license file, or TCP 8990 listener existed | The first configure attempt correctly rejected an unpublished branch | The supported configure path succeeded after branch publication without replacing the headnode. |
| CLIENT-002 | sentlic-e | Run bounded non-workflow license-client smoke/load validation; do not launch DayOA or touch Slurm jobs | SUCCESS | contract_test | Gate 5 | 1 | 64 pings at concurrency 32 completed in one second from the headnode; no tmux sessions and empty `squeue` before/after |  | Client path is operational without a workflow launch. |
| BOOT-001 | DYEC/sentlic-e | Replace mutable shared compute bootstrap references with a content-addressed write-once bundle | SUCCESS | config_or_startup_contract | Gate 5 | 1 | Five exact objects published under `sha256-2f2578f6469fe4668a3fc86d9520b6a57060989c33c010e018caff5821e5ec8f`; final candidate SHA-256 `1addec0f...fad23cf`; `UPDATE_COMPLETE`; all eleven queues reference the immutable URI | Mutable shared prefix plus deleted accounting and SG references in the saved config | Headnode `i-048ff099d73057e09` and FSx `fs-0596bfcffb12adb81` were preserved. |
| CLIENT-003 | sentlic-e | Prove a fresh compute node inherits the endpoint and does not start a local licsrvr | SUCCESS | contract_test | Gate 5 | 1 | Slurm job `2`, partition `i8`, node `i8-dy-price8-1`, completed `0:0` in eight seconds; output records endpoint, private resolution to `10.0.0.205`, and `license_ping=ok`; silent assertions rejected any local unit, file, or listener | Smoke job `1` used a nonexistent diagnostic log path after all endpoint assertions had already passed | Corrected smoke did not run a DayOA workflow; queue was empty and compute fleet returned to `STOPPED`. |
| REVIEW-001 | Both/AWS | Independent read-only security, runtime, test, and drift review | SUCCESS | contract_test | Gate 5 | 10 | Review findings resolved: installer no longer restarts; restart requires `--approve-restart`; CloudWatch install is pinned/reproducible; identity-policy-only secret design documented; direct markdup binary path routes through wrapper |  | Live cluster update, supported configure, and fresh-node proof subsequently passed. |
| VAL-001 | Both | Run focused and full tests, syntax/YAML/IaC checks, packaged parity, and `git diff --check` | SUCCESS | contract_test | Gate 5 | 1 | DayOA `755 passed`; DYEC `1481 passed, 11 skipped`; Bash syntax, Ruff, packaged parity, config YAML, CloudFormation validation, strengthened live validators, and `git diff --check` pass |  | Descendant validation also passed: DayOA `755`; DYEC `1492 passed, 11 skipped`. |
| FUTURE-002 | Both | Merge the proven `10.3.4` cutover forward into maintained descendant branches without rewriting their newer work | SUCCESS | active_product_contract | Gate 5 | 1 | DayOA merge commits `299a049` and `1b51c1c` published to `sentieon-single` after tag `10.3.8`; DYEC merge commit `e1ddfacf` and closeout-ledger merge `43be0f21` published after the `10.3.5` line; non-force pushes only | Descendant branches advanced during live validation | Newer HIOMRS, VEP, accounting, pin, and evidence behavior remains intact. |
| RELEASE-001 | Both | Commit and push the requested `10.3.4` branches only after live proof; do not publish to PyPI | SUCCESS | active_product_contract | Gate 5 | 1 | DayOA implementation commits through `01328da`; DYEC implementation commits through `40f50133`, followed only by ledger closeout; both descendant forward merges published |  | No tag was created or moved and nothing was published to PyPI. |

## Acceptance

- `usw2d-01.sentieon.lsmc.bio` runs the pinned vendor license server under
  systemd and listens on TCP 8990.
- `license.sentieon.lsmc.bio:8990` is the sole generated client default.
- Secret contents never appear in source, command output, logs, or receipts.
- Security-group ingress is explicit and never public.
- No compute queue role can read the license secret.
- DayOA startup, wrappers, active rules, Slurm, and Singularity accept the
  endpoint without local licsrvr behavior.
- DYEC source and packaged defaults are identical and future-branch tests
  reject regression to the file/local-server contract.
- `sentlic-e` reaches the endpoint and inherits it for new shells/jobs without
  a workflow launch or disruption of existing controllers.
- Every ledger row is terminal and the objective is reported separately from
  any blocked external renewal or HA expansion work.

All control-ledger rows are `SUCCESS`. The requested cutover is complete.
License renewal before the recorded `2026-07-31` expiry and any future
multi-backend HA expansion are explicit follow-up operations, not hidden
fallbacks or blockers to this single-backend cutover.
