# Private DayOA Deploy-Key Authentication Ledger

Objective: make private `lsmc-bio/daylily-omics-analysis` checkouts work through
`day-clone` on new DYEC headnodes using one read-only repository deploy key,
without granting GitHub credentials to compute nodes.

## Gate 0 Baseline

- DYEC checkout: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch/HEAD: `jem-dev` at `0fb6d4b1` (`10.0.155`), matching `origin/jem-dev`
- Worktree: clean (`git status --short --branch` reported only the branch line)
- DayOA visibility: `lsmc-bio/daylily-omics-analysis` is temporarily `PUBLIC`
- AWS account/profile: profile `lsmc`, account `108782052779`; caller is account root
- Existing direct dependency: DYEC `pyproject.toml` pins DayOA through `git+https`
- Existing clone surface: `day-clone` defaults to catalog HTTPS and supports explicit SSH
- Safety boundary: only the headnode may receive deploy-key secret access; no compute
  queue may receive the policy.

## Control Ledger

| ID | Work item | State | Evidence / terminal note |
|---|---|---|---|
| DK-001 | Add explicit deploy-key configuration and validation. | SUCCESS | Required exact secret and policy ARNs are parsed and preflighted in the target account and region. |
| DK-002 | Attach the exact secret-read policy only to the rendered headnode IAM block. | SUCCESS | Rendered-YAML helper rejects the policy in every queue and inserts it once under `HeadNode.Iam.AdditionalIamPolicies`. |
| DK-003 | Configure the non-secret deploy-key ARN/region on the headnode through SSM. | SUCCESS | Headnode configuration writes only `secret_arn` and `region` to the Daylily config. |
| DK-004 | Make DayOA catalog cloning explicitly SSH plus AWS deploy-key authenticated. | SUCCESS | Source and packaged catalogs declare `clone_transport: ssh` and `auth_mode: aws_deploy_key`; other rows remain explicit HTTPS/none. |
| DK-005 | Fetch, validate, use, and always remove the temporary deploy key in `day-clone`; add `--check-auth`. | SUCCESS | Implementation uses strict packaged host keys, mode `0700`/`0600` temporary storage, `IdentitiesOnly=yes`, and context-managed cleanup. |
| DK-006 | Remove DYEC's direct `git+https` DayOA dependency. | SUCCESS | DayOA is absent from `pyproject.toml` dependencies and is acquired through explicit version-pinned `day-clone`. |
| DK-007 | Add focused contract tests and run full local validation. | SUCCESS | `pytest -q`: 1376 passed, 11 skipped; targeted Ruff, Python/Bash syntax, YAML, payload parity, and `git diff --check` passed. Repository-wide Ruff remains nonzero only for 33 pre-existing errors in unrelated archived `docs/` scripts. |
| DK-008 | Create the repository deploy key, AWS secret, and exact IAM policy. | SUCCESS | GitHub key `156961830` is enabled, verified, and read-only; AWS secret and policy exist and pass DYEC preflight. |
| DK-009 | Return DayOA to private and verify authenticated access. | SUCCESS | DayOA is `PRIVATE`; unauthenticated HTTPS failed and real `day-clone --check-auth` succeeded for tag `10.0.95`. No paid cluster was created. |

## Bugfix Attempts

- `2026-07-11T02:15Z` — Focused baseline after the first implementation pass:
  `pytest -q tests/test_day_clone.py tests/test_repository_catalog.py
  tests/test_lsmc_bio_fork_contract.py tests/test_headnode_readiness.py
  tests/test_workflow.py` -> `112 passed, 31 failed`. Root cause: existing test and
  version-1 catalog fixtures did not yet declare the new explicit
  `clone_transport`/`auth_mode` fields, and workflow fixtures did not include the
  exact deploy-key secret/policy ARNs. Next attempt: update those fixtures and keep
  production parsing strict rather than adding inferred defaults.
- `2026-07-11T02:34Z` — First complete suite after the focused suite passed:
  `pytest -q` -> `1371 passed, 11 skipped, 5 failed`. All five failures were stale
  contract expectations: two CLI mocks lacked the new explicit empty deploy-key
  kwargs, two remote-test assertions still expected raw HTTPS cloning, and the
  legacy login-SSH sweep needed a path-specific exception for strict Git SSH host
  verification in `day-clone`. Next attempt: update only those exact expectations
  and preserve all other SSH/PEM prohibitions.

## Live Provisioning Evidence

- Secret ARN: `arn:aws:secretsmanager:us-west-2:108782052779:secret:dayec/github-deploy-keys/lsmc-bio-daylily-omics-analysis-igtfHD`
- Policy ARN: `arn:aws:iam::108782052779:policy/DayECHeadnodeDayOAClone`
- DYEC preflight: `iam.dayoa_deploy_key_secret_policy PASS`; the validator did not
  call `GetSecretValue`.
- Initial GitHub deploy-key attempt: HTTP 422, `Deploy keys are disabled for this
  repository`. After the organization owner enabled deploy keys, key `156961830`
  was created with `read_only: true`, `verified: true`, and `enabled: true`.
- Before the visibility change, real `day-clone --check-auth --repository
  daylily-omics-analysis --git-tag 10.0.95` fetched the secret and passed.
- DayOA was changed to `PRIVATE`. Credential-free HTTPS `git ls-remote` then failed
  with terminal prompting disabled, while the same real `day-clone --check-auth`
  command passed. GitHub recorded the deploy key as used.
- The protected local setup key and local auth-check home were removed. No matching
  `day-clone-key-*` or setup directory remains under `/tmp`.
- Fresh-headnode validation is intentionally deferred to the next normally requested
  DYEC cluster build; no additional paid cluster was created solely for this change.

## Closeout

- All ledger rows are terminal and successful.
- The implementation objective is complete locally and at the account/repository
  control plane.
- Implementation provenance: commit `75fa61c4` / tag `10.0.156`; current self-pinned
  DYEC head is `82f021fb` / tag `10.0.157`, matching `origin/jem-dev`.
- Remaining acceptance observation: confirm readiness and a full version-pinned clone
  on the next freshly created DYEC headnode.

## Live-Action Boundaries

- No cluster creation or teardown is authorized by this ledger.
- No secret material may be written into this ledger, repository files, command logs,
  cluster YAML, S3 bootstrap payloads, or DYEC state records.
- The private key may exist only in the local protected setup file, AWS Secrets Manager,
  and a mode-`0600` temporary headnode file for the lifetime of one Git operation.
- DayOA visibility changes happen only after the deploy key and AWS controls validate.

## Existing-Cluster Retrofit: ifx-reworkB

Date: 2026-07-11

| ID | Work item | State | Evidence / terminal note |
|---|---|---|---|
| RT-001 | Verify the local DYEC release payload. | SUCCESS | Local checkout is commit `82f021fb57ab30595502a01d112fdfad4226c71b`, exact annotated tag `10.0.157`. |
| RT-002 | Verify cluster, headnode, and SSM readiness. | SUCCESS | Cluster `ifx-reworkB` and CloudFormation stack are `CREATE_COMPLETE`; headnode `i-059642d9ee4d5c9ea` is running at `10.0.0.180`; SSM reports `Online`. |
| RT-003 | Prove headnode and compute IAM roles are distinct. | SUCCESS | Headnode role is `ifx-reworkB-RoleHeadNode-7Qqdb7DkjOvI`. Recursive CloudFormation, all queue instance profiles, and all compute launch templates resolved seven distinct compute roles listed below. |
| RT-004 | Attach the exact deploy-key policy only to the headnode role. | SUCCESS | `arn:aws:iam::108782052779:policy/DayECHeadnodeDayOAClone` is attached to the verified headnode role and absent from every compute role after attachment. |
| RT-005 | Configure the legacy headnode with DYEC `10.0.157` and the exact DayOA secret ARN. | BLOCKED | SSM command `00265ef9-676b-413a-9209-ebebc2e0f038` failed at the first “Clone repository to headnode” step with rc 128: the existing DYEC checkout uses private HTTPS origin and Git could not read a username. The configure path therefore never reached deploy-key installation or readiness. |
| RT-006 | Run `day-clone --check-auth` and a full temporary DayOA `10.0.95` clone. | BLOCKED | Not attempted because RT-005 is a hard prerequisite. No HTTPS credential, alternate key, wheel, bundle, or other fallback was used. |
| RT-007 | Verify temporary key cleanup and workflow boundary. | SUCCESS | No `/tmp/day-clone-key-*` path exists. No DayOA workflow was launched and no FSx analysis checkout was created by this retrofit. |

### Compute Roles Checked

- `ifx-reworkB-ComputeFleetQueues-Role0a4928560b35ff6d-ZxWlkYnj9YPy`
- `ifx-reworkB-ComputeFleetQueues-Role18b1a9ea4e81c872-zBYLkxivPcqU`
- `ifx-reworkB-ComputeFleetQueues-Role7e156bfc7a3b620e-pOPJnmFHfx0s`
- `ifx-reworkB-ComputeFleetQueues-Role94f0e27775450e09-Ax235FuRlltq`
- `ifx-reworkB-ComputeFleetQueues-RoleB6f7a4ba7d5a78bd-b14aOxHl4evy`
- `ifx-reworkB-ComputeFleetQueues-RoleCd53fa91fbffcf32-4Z4oG8qQjKOb`
- `ifx-reworkB-ComputeFleetQueues-RoleFfdcc1776faccb72-XBPWfaz4v8sG`

### Retrofit Blocker

The existing headnode DYEC checkout is commit
`08f21590f61d98ee1d6be38d78e040a6e2507169`, tag `10.0.149`, with origin
`https://github.com/lsmc-bio/daylily-ephemeral-cluster.git`. DYEC
`10.0.157` resolves the local release correctly, but its supported configure
sequence first synchronizes that private DYEC repository over its configured
origin. The supplied deploy key is repository-scoped to
`lsmc-bio/daylily-omics-analysis`, so it cannot authenticate the DYEC fetch.
The retrofit must remain blocked until the supported configure bootstrap can
obtain DYEC `10.0.157` without violating the explicit no-HTTPS/no-alternate-key
boundary.

## Existing-Cluster Retrofit: partrevert

Date: 2026-07-11

### Gate 0 Baseline

- Requested cluster: `partrevert`; AWS profile `lsmc`; region `us-west-2`.
- DYEC checkout: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch
  `jem-dev`, exact HEAD `82f021fb57ab30595502a01d112fdfad4226c71b`.
- Release gate: annotated tag `10.0.157` resolves to the same exact commit.
- Existing user work preserved: this ledger was already modified before the
  retrofit; no reset, commit, or push is authorized.
- Cluster and stack: `CREATE_COMPLETE`; compute fleet `RUNNING`.
- Headnode: `i-061e6053f5e015e5a`, `r7i.4xlarge`, `running`, Ubuntu, SSM `Online`.
- Headnode instance profile: `partrevert-InstanceProfileHeadNode-p1HWQXLCfKhi`.
- Headnode role: `partrevert-RoleHeadNode-bNKWzqHt04WS`.
- Compute-role inventory: recursive CloudFormation found 12 compute roles and
  all 20 compute launch templates resolved exactly the same 12-role set.
- Hard gate: headnode-role membership in compute set was `0`; the deploy-key
  policy was attached to neither the headnode role nor any compute role before
  the retrofit.
- Secret handling: only `DescribeSecret` metadata was read; secret value material
  was not requested or printed.

### Control Ledger

| ID | Work item | State | Evidence / terminal note |
|---|---|---|---|
| PR-001 | Verify exact DYEC release payload and preserve dirty work. | SUCCESS | HEAD and annotated `10.0.157` both resolve to `82f021fb57ab30595502a01d112fdfad4226c71b`; existing ledger changes remain in place. |
| PR-002 | Verify cluster, headnode, and SSM readiness. | SUCCESS | `partrevert` is `CREATE_COMPLETE`; headnode `i-061e6053f5e015e5a` is running Ubuntu and SSM reports `Online`. |
| PR-003 | Prove headnode and every compute IAM role are distinct. | SUCCESS | Recursive CloudFormation and all 20 launch templates agree on the 12 compute roles below; the headnode role is absent from that set. |
| PR-004 | Attach the exact deploy-key policy only to the verified headnode role and re-audit compute roles. | SUCCESS | `DayECHeadnodeDayOAClone` is attached to `partrevert-RoleHeadNode-bNKWzqHt04WS`; every compute role remains at attachment count zero. |
| PR-005 | Bootstrap and install DYEC `10.0.157` with its repository-scoped deploy key, preserving the prior checkout. | SUCCESS | Strict pinned-host SSH preflight command `2da91c38-ff9b-4521-b10b-aef73d7250e4` authenticated tag `10.0.157`. The old checkout was moved to `/home/ubuntu/projects/daylily-ephemeral-cluster.backup.20260711T043419Z`; the replacement checkout is detached and clean at annotated tag `10.0.157`, exact commit `82f021fb57ab30595502a01d112fdfad4226c71b`, and installed distribution version `10.0.157`. `dyec headnode configure` was not rerun. |
| PR-006 | Install the DayOA deploy-key reference and run `day-clone --check-auth` for private DayOA tag `10.0.95`. | SUCCESS | The original slash-form DayOA ARN was corrected to the actual hyphenated ARN in IAM policy default version `v5` and in the mode-`0600` headnode YAML through `write_remote_text` command `b1fa2e3a-3763-4359-bf76-7b5e7f7e4439`. `day-clone --check-auth` reported `Repository authentication validated: daylily-omics-analysis @ 10.0.95`. |
| PR-007 | Perform and verify a full DayOA `10.0.95` clone outside FSx analysis results. | SUCCESS | The isolated validation clone resolved annotated tag `10.0.95` to exact commit `2a0334dc1e571d3030a42818d748a92c74cb0be2`, with exact SSH origin, one `origin` remote, and a clean worktree. An agent-owned clean pinned checkout was also retained at `/home/ubuntu/projects/codex/dayoa-10.0.95/daylily-omics-analysis`; the pre-existing shared `DAYOA` conda environment was not modified. |
| PR-008 | Delete only the verified temporary validation root and close the workflow boundary. | SUCCESS | Verified root `/tmp/dayoa-private-clone.kTcbtz` was removed after all assertions passed. Final sweeps found no `/tmp/dayec-dyec-auth.*`, `/tmp/dayec-dyec-install.*`, `/tmp/day-clone-key-*`, or `/tmp/dayoa-private-clone.*`; Slurm and workflow-controller counts were both zero. |

### Compute Roles Checked

- `partrevert-ComputeFleetQueuesN-Role18b1a9ea4e81c872-0xP9wD8KGSLy`
- `partrevert-ComputeFleetQueuesN-Role208459e33242dc54-d1w9TJJH6hpO`
- `partrevert-ComputeFleetQueuesN-Role4d8f7af64ba38a45-nANyNXgCcD2s`
- `partrevert-ComputeFleetQueuesN-Role52e57f34624185bd-aDEnEHNpfYk7`
- `partrevert-ComputeFleetQueuesN-Role7e156bfc7a3b620e-AOWsQFya9m12`
- `partrevert-ComputeFleetQueuesN-Role81145a0a8d90023c-zPQqY2mOVrVg`
- `partrevert-ComputeFleetQueuesN-Role8ac012bc26fdf6ad-oqSfm5ZbKdoY`
- `partrevert-ComputeFleetQueuesN-Role94f0e27775450e09-gQx1csKsxKdG`
- `partrevert-ComputeFleetQueuesN-RoleA95f175d76145df0-FVYwazo6zWum`
- `partrevert-ComputeFleetQueuesN-RoleB6f7a4ba7d5a78bd-QCXNuTSzqt3e`
- `partrevert-ComputeFleetQueuesN-RoleCd53fa91fbffcf32-Sppt11fEurgj`
- `partrevert-ComputeFleetQueuesN-RoleE62fce35f6d0d474-I6QxtduM22Of`

### Retrofit Blocker

The requested existing-cluster configure route cannot bootstrap the verified
DYEC `10.0.157` payload because its first action synchronizes the private
`lsmc-bio/daylily-ephemeral-cluster` repository through an HTTPS origin. The
authorized deploy key and policy are scoped to
`lsmc-bio/daylily-omics-analysis`; they cannot authenticate that DYEC fetch.
The procedure therefore stopped before `day-clone --check-auth` or the temporary
DayOA clone, exactly as required by the no-fallback boundary.

A subsequent manual reinstall request was preflighted before removing the active
environment. On the headnode, `DAY-EC` resolves to
`/home/ubuntu/miniconda3/envs/DAY-EC` and imports DYEC from
`/home/ubuntu/projects/daylily-ephemeral-cluster`. With terminal prompting
disabled, `git ls-remote` against the private DYEC HTTPS repository for tag
`10.0.157` returned rc 128 because no GitHub username could be read. The agent
therefore did not run `conda env remove`, alter the existing checkout, or attempt
an unapproved source/credential fallback that could strand the headnode.

Final safety evidence:

- `partrevert` remains `CREATE_COMPLETE`; headnode
  `i-061e6053f5e015e5a` remains `running`.
- Headnode policy attachment count is exactly `1`.
- Twelve compute roles were rechecked; their deploy-key policy attachment sum
  is `0`.
- No secret value was retrieved or printed.
- No `/tmp/day-clone-key-*` or `/tmp/dayoa-private-clone.*` directory remains.
- No cluster lifecycle action and no DayOA workflow action was performed.

All `partrevert` retrofit rows are terminal, but the private-clone objective is
not complete because PR-005 through PR-007 are blocked by the private DYEC HTTPS
bootstrap dependency.

### Authorized DYEC Bootstrap Retry

The user subsequently supplied the existing repository-scoped DYEC deploy-key
secret ARN and authorized a bootstrap that does not depend on the unsupported
private-HTTPS configure path. Local Gate 0 was repeated before the retry:

- Local HEAD and annotated tag `10.0.157` both resolve exactly to
  `82f021fb57ab30595502a01d112fdfad4226c71b`.
- IAM policy `DayECHeadnodeDayOAClone` default version `v4` names exactly the
  DayOA and DYEC deploy-key secret ARNs.
- The existing `DAY-EC` environment and headnode checkout remain untouched
  until strict SSH `git ls-remote` authentication for the DYEC tag succeeds.
- The old checkout will be moved to a timestamped backup, never deleted.
- Neither private key may be printed, manually retrieved, or granted to a
  compute role. All temporary key material must be mode `0600` inside a mode
  `0700` `/tmp` directory and removed by a trap.
- The dirty ledger and the untracked IFX deploy-key ledger are existing local
  work and must remain preserved. No commit or push is authorized.

### Bootstrap Retry Closeout

The retry completed successfully without rerunning `dyec headnode configure`,
changing cluster lifecycle state, touching FSx analysis results, or starting a
DayOA workflow.

- Pinned known hosts were deployed with
  `daylily_ec.aws.ssm.write_remote_text` command
  `bbb163c9-8b1f-41e9-a9bb-cac00041f596`; remote SHA-256
  `c73ac5d045cd2a359d2202b79b551fb22a638463d5ddbe5ed59b1b3998869c88`
  matches the local source and remote mode is `0644`.
- The first DayOA check exposed an incorrect slash-form ARN. The actual secret
  ARN uses `lsmc-bio-daylily-omics-analysis-igtfHD`; shared policy default
  version `v5` and the headnode reference now use that exact ARN.
- `DayECHeadnodeDayOAClone` is attached to the `partrevert` headnode role and
  the separate `ifx-reworkB` headnode role only. No compute role is among the
  policy entities; the previously enumerated 12 `partrevert` compute roles
  received no deploy-key policy attachment.
- Headnode `i-061e6053f5e015e5a` remains `running`, Ubuntu, and SSM `Online`
  under instance profile
  `partrevert-InstanceProfileHeadNode-p1HWQXLCfKhi` and role
  `partrevert-RoleHeadNode-bNKWzqHt04WS`.
- The DYEC repository-scoped key was fetched only by a redirect directly into
  trapped mode-`0600` temporary files. DayOA key material was handled only by
  `day-clone`. Neither private key was printed or copied to local storage.
- DYEC is installed at exact commit
  `82f021fb57ab30595502a01d112fdfad4226c71b`, annotated tag `10.0.157`.
  DayOA is installed as an agent-owned checkout at exact commit
  `2a0334dc1e571d3030a42818d748a92c74cb0be2`, annotated tag `10.0.95`.
- Final cluster workload evidence was zero Slurm jobs and zero `dy-r` or
  Snakemake controllers. No workflow ran as part of this retrofit.
- Concurrent dirty changes in `day-clone`, both command-catalog mirrors, and
  their tests appeared during execution. They were treated as user work and
  were neither edited nor reverted by this retrofit; the untracked IFX ledger
  was also preserved. This retrofit's only local file edit was this ledger.

All `partrevert` rows are terminal and the private DYEC/DayOA clone objective
is complete.
