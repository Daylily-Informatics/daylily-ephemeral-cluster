# us-west-2 Slurm Accounting Singleton Cleanup Ledger

Date: 2026-07-13

## Objective

Reduce DayEC Slurm accounting infrastructure in `us-west-2` to exactly one
regional database. Retain the database actually used by Ursa only if live
consumer evidence and schema/version evidence show that it is current. Do not
perform any destructive action until the exact deletion scope receives the
required second explicit approval.

## Control Ledger

Controlling plan: this file

Ledger path: `docs/plans/20260713T102027Z_usw2_slurm_accounting_singleton_cleanup_ledger.md`

### Gate 0 baseline

- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster-sentieon-single`
- Branch: `sentieon-single` tracking `origin/sentieon-single`.
- Pre-existing user files preserved: `docs/plans/20260712T192000Z_sent_hg003_runtime_cache_publish.py` and `docs/plans/20260713T083000Z_sent_hg003_hiomrs_kitchensink_1x_monitor_ledger.md` are untracked.
- Earlier changes from this task remain uncommitted: `daylily_ec/aws/slurm_accounting.py` and `tests/test_slurm_accounting.py` exclude `dayec-costacct-*` validation stacks from implicit selection.
- Regional CloudFormation inventory at `2026-07-13T10:20Z`: six non-deleted stacks tagged `daylily-ec:component=slurm-accounting-mysql`; four are `CREATE_COMPLETE`, two are `ROLLBACK_COMPLETE`.
- Independent EC2 inventory: five running instances tagged `daylily-ec:component=slurm-accounting-mysql`; one is the retained orphan from rolled-back stack `dayec-slurm-accounting-cmdcat-103b`.
- No AWS mutation has occurred in this cleanup task.
- User request is first destructive approval only. Exact resources and effects must be restated before a separate second approval.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| SACCT-001 | AWS us-west-2 | Freeze all DayEC accounting stacks, instances, secrets, security groups, and statuses | SUCCESS | feature_implementation | Gate 0 | orchestrator | Six stack records; five running hosts; four retained 20 GiB EBS volumes are in deletion scope |  | Regional inventory frozen before mutation |
| SACCT-002 | AWS us-west-2 | Map each accounting database to active ParallelCluster and Ursa consumers | SUCCESS | active_product_contract | Gate 3 | orchestrator | `dayec-slurm-accounting-us-west-2c` client SG is attached to `sent-hg003-5x-0712`, tagged `ursa-preserve=true`; old `us-west-2d` client SG is attached to live `sentlic-e`; other client SGs have no ENIs |  | Consumer map complete |
| SACCT-003 | AWS us-west-2 | Verify schema and Slurm accounting service version/freshness for viable databases | SUCCESS | active_product_contract | Gate 3 | orchestrator | Keeper: Slurm 25.11.4, active slurmdbd, MariaDB 10.6.23, conversion version 16, current job rows through 2026-07-13T10:00Z. All queryable extras also report conversion version 16 |  | Keeper is current; no stale-schema blocker |
| SACCT-004 | DYEC | Select and document the single canonical regional accounting database | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Selected `dayec-slurm-accounting-us-west-2c`, created 2026-07-12, URI `10.0.1.237:3306`, instance `i-088957ddbc7fcf3d1` |  | Newest database, live Ursa-preserved consumer, current schema |
| SACCT-005 | AWS us-west-2 | Prepare exact deletion manifest for all non-canonical stacks and retained resources | SUCCESS | feature_implementation | Gate 4 | orchestrator | Five stack records, four instances, four EBS volumes, eight SGs, four secrets, four roles/profiles; exact IDs below |  | Manifest complete; no mutation performed |
| SACCT-006 | Approval | Obtain second explicit approval for exact destructive manifest | SUCCESS | legitimate_safety_handling | Gate 4 | orchestrator | User replied `CONFIRM DELETE THE FOUR EXTRA US-WEST-2 SLURM ACCOUNTING HOSTS AND ALL RETAINED RESOURCES` |  | Second explicit approval received |
| SACCT-007 | AWS us-west-2 | Execute only the approved destructive cleanup | SUCCESS | feature_implementation | Gate 4 | orchestrator | Five stack records deleted; four instances terminated; four volumes deleted; eight SGs deleted; four secrets force-deleted; four IAM profile/role pairs deleted |  | Approved manifest completed at 2026-07-13T10:31Z |
| SACCT-008 | Acceptance | Verify exactly one healthy, current, Ursa-connected regional accounting database remains | SUCCESS | contract_test | Gate 5 | orchestrator | Independent inventory: one active tagged host, one active tagged stack, two keeper SGs, one keeper secret; keeper MariaDB active, schema 16, 183 job rows |  | Regional live count is exactly one |
| SACCT-009 | DYEC architecture | Prevent recreation of per-AZ/per-VPC accounting stacks | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Regional name/tag/discovery contract implemented; explicit names and validation stacks count; mismatched VPC fails before create; keeper migrated with tag-only CFN change set |  | Live same-VPC resolve passes and overlapping-VPC plus explicit-name bypasses fail hard |

## Initial Regional Inventory

| Stack | Stack status | AZ | VPC | DB host / URI | Initial classification |
|---|---|---|---|---|---|
| `dayec-slurm-accounting-us-west-2d` | `CREATE_COMPLETE` | `us-west-2d` | `vpc-06b01782f2abece1c` | `i-0fec5d1a28b6d27aa` / `10.0.1.39:3306` | Candidate |
| `dayec-costacct-20260705T005955Z` | `CREATE_COMPLETE` | `us-west-2d` | `vpc-06b01782f2abece1c` | `i-089b87fc6d966ec03` / `10.0.1.58:3306` | Validation candidate |
| `dayec-slurm-accounting-cmdcat-103c` | `CREATE_COMPLETE` | `us-west-2c` | `vpc-0bdcf0eff7ce4a231` | `i-052339da98d06719b` / `172.31.8.74:3306` | Candidate |
| `dayec-slurm-accounting-us-west-2c` | `CREATE_COMPLETE` | `us-west-2c` | `vpc-0f41176d568ae7b1e` | `i-088957ddbc7fcf3d1` / `10.0.1.237:3306` | Candidate |
| `dayec-slurm-accounting-cmdcat-103b` | `ROLLBACK_COMPLETE` | `us-west-2c` | `vpc-0bdcf0eff7ce4a231` | retained `i-06940617dae9625d9` / `172.31.6.104` | Orphan candidate |
| `dayec-slurm-accounting-cmdcat-103` | `ROLLBACK_COMPLETE` | `us-west-2c` | `vpc-0a3157ee01bef4232` | none | Empty failed stack |

## Canonical Database To Keep

- Stack: `dayec-slurm-accounting-us-west-2c`
- Created: `2026-07-12T12:11:35Z`, newest of the five database hosts.
- Host: `i-088957ddbc7fcf3d1`, `10.0.1.237:3306`, volume `vol-0b481de207f5b19f1`.
- Client SG: `sg-0e1a8da66cbee0a47`; attached to headnode `i-04059f0d8c4f701d2` for `sent-hg003-5x-0712`.
- Ursa evidence: headnode tag `ursa-preserve=true`.
- Freshness: headnode Slurm `25.11.4`; `slurmdbd` active; database conversion version `16`; 183 job rows and current writes through `2026-07-13T10:00Z`.
- Known tuning warnings, not schema failures: SlurmDBD reports non-recommended `innodb_buffer_pool_size` and `innodb_lock_wait_timeout`; it is active and writing.

## Exact Destructive Manifest Awaiting Second Approval

### CloudFormation stack records

Disable termination protection and delete these five stack records. Their
resources use `DeletionPolicy: Retain`, so retained resources must then be
deleted explicitly.

1. `dayec-slurm-accounting-us-west-2d`
2. `dayec-costacct-20260705T005955Z`
3. `dayec-slurm-accounting-cmdcat-103c`
4. `dayec-slurm-accounting-cmdcat-103b`
5. `dayec-slurm-accounting-cmdcat-103`

### EC2 hosts and EBS volumes

Disable EC2 termination protection, terminate four `t4g.micro` instances, and
delete their retained encrypted `gp3` root volumes (`80 GiB` total):

| Instance | Volume | Database evidence that will be lost |
|---|---|---|
| `i-0fec5d1a28b6d27aa` | `vol-02caa6b741e86c280` | `sent-liscc` and `sentlic-e` registrations; zero job rows at audit time |
| `i-089b87fc6d966ec03` | `vol-0958a841ed26fc81a` | `dyec-costacct-005955`; 4 job rows |
| `i-052339da98d06719b` | `vol-00445793f93ce7a51` | `cmdcat-103-all-20260707`; 6,045 job rows, about 21.7 MiB database |
| `i-06940617dae9625d9` | `vol-0bbe7df9fbac2b7c2` | Rolled-back orphan; SSM unavailable, contents not queryable |

No dump, snapshot, or merge into the keeper is included in the requested
aggressive deletion. Known deletion is at least 6,049 historical job rows plus
the unqueryable orphan volume.

### Network effect and security groups

- Remove accounting client SG `sg-0c8f3047dfc85b1c0` from live `sentlic-e`
  headnode ENI `eni-037fd783d392c41cb`, leaving its cluster SG
  `sg-05d44b1844e7651b0` attached.
- This deliberately severs `sentlic-e` from its active Slurm accounting DB.
  At audit time its queue was empty, SlurmDBD was active, and no job rows had
  yet been written. The keeper is in another VPC and cannot replace it without
  explicit inter-VPC networking.
- Revoke retained accounting ingress/egress rules and delete these eight SGs:
  `sg-0c8f3047dfc85b1c0`, `sg-0619812d6a455c694`,
  `sg-058f0a3b836320398`, `sg-0472b75bd26b1c897`,
  `sg-03f4d4b7fc608b7ea`, `sg-042443cee20a43b8c`,
  `sg-0dd41519e39d1cb85`, and `sg-00ff459cfcd910733`.

### Secrets and IAM

- Force-delete four retained Secrets Manager secrets with no recovery window:
  `AccountingPasswordSecret-LIXjs4Jyv7oh-b82PTx`,
  `AccountingPasswordSecret-2RA5iP6oOrnR-4nkGWC`,
  `AccountingPasswordSecret-92BEr4g2XZHh-nTwoQn`, and
  `AccountingPasswordSecret-LbNa3JfFnch7-6dzKdQ`.
- Delete the four retained accounting instance profiles and four associated IAM
  roles whose names begin with each deleted stack name, after removing role
  bindings and inline policies.

## Approval State

Second explicit approval received with the exact confirmation phrase. Execute
only the manifest above and append live receipts below.

## Execution Receipts

- Preflight revalidated the keeper stack, running instance, EBS volume, client
  SG, `sent-hg003-5x-0712` headnode, and `ursa-preserve=true` tag before the
  first mutation.
- Disabled termination protection and deleted all five approved obsolete stack
  records.
- Removed obsolete accounting client SG `sg-0c8f3047dfc85b1c0` from
  `sentlic-e` ENI `eni-037fd783d392c41cb`, leaving cluster SG
  `sg-05d44b1844e7651b0`.
- Terminated instances `i-0fec5d1a28b6d27aa`, `i-089b87fc6d966ec03`,
  `i-052339da98d06719b`, and `i-06940617dae9625d9`.
- Deleted volumes `vol-02caa6b741e86c280`, `vol-0958a841ed26fc81a`,
  `vol-00445793f93ce7a51`, and `vol-0bbe7df9fbac2b7c2`.
- Revoked retained rules and deleted all eight approved client/database SGs.
- Submitted force deletion without recovery for all four approved secrets.
- Removed all four approved retained IAM instance profiles and roles.
- Independent post-cleanup AWS inventory at `2026-07-13T10:31Z`:
  - one active tagged instance: keeper `i-088957ddbc7fcf3d1` at `10.0.1.237`;
  - one active tagged stack: `dayec-slurm-accounting-us-west-2c`,
    `CREATE_COMPLETE`;
  - two tagged SGs: keeper client `sg-0e1a8da66cbee0a47` and DB
    `sg-09151c49d1b2edeaf`;
  - one tagged secret: keeper `AccountingPasswordSecret-nuhQFFjm0r6B`.
- Live keeper verification: MariaDB active, conversion schema version `16`,
  cluster `sent-hg003-5x-0712`, 183 job rows, and active SlurmDBD/Sacct access
  from the headnode.

## Final Report

All rows terminal: yes

Cleanup objective complete: yes

Status counts:

- `SUCCESS`: 9
- `BLOCKED`: 0

## Regional Singleton Recurrence Prevention

- Live network evidence: keeper VPC `vpc-0f41176d568ae7b1e` and former `2d`
  VPC `vpc-06b01782f2abece1c` both use `10.0.0.0/16`; automatic VPC peering is
  invalid because the CIDRs overlap.
- `derive_slurm_accounting_stack_name("us-west-2c")` now derives regional name
  `dayec-slurm-accounting-us-west-2` for a new region.
- New stacks receive required tag `daylily-ec:region=<region>`.
- Discovery counts every DayEC accounting stack in the region, including
  explicit and validation-style names. More than one is a hard error.
- A missing explicit name cannot bypass an existing regional singleton.
- The selected cluster VPC must equal the singleton's tagged VPC. A mismatch
  fails before database or cluster creation and never creates a fallback DB.
- CloudFormation change set
  `regional-singleton-tag-20260713T104002Z` migrated keeper stack
  `dayec-slurm-accounting-us-west-2c` to explicit tag
  `daylily-ec:region=us-west-2`. CloudFormation reported tag-only modifications
  with `Replacement: False` for all eight affected resources; final stack state
  is `UPDATE_COMPLETE`.
- Live verification after migration:
  - regional count `1`;
  - keeper-VPC resolution returns `10.0.1.237:3306` across AZ selection;
  - overlapping `2d` VPC request fails with `A second regional accounting stack is forbidden`;
  - missing explicit-name request fails with the same singleton guard;
  - Slurm `25.11.4`, SlurmDBD active, MariaDB active, schema version `16`.
- Validation:
  - focused singleton/validation/CLI suites: `225 passed`;
  - full suite: `1435 passed, 11 skipped, 1 unrelated failure`;
  - unrelated failure is the concurrently modified Sentieon single template
    rendering queue `MaxCount` inconsistent with the existing pinned test value
    `1`; no accounting code participates in that failure.
