# Three preserved FSx file systems delete ledger

Created: `2026-08-09T23:48:40Z`

Controlling ledger:
`/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260809T234840Z_three_preserved_fsx_delete_ledger.md`

## Objective

Delete exactly these three Amazon FSx for Lustre file systems in AWS account
`108782052779`, profile `lsmc`, region `us-west-2`, after the required second
destructive approval:

- `fs-0942c7bce60871db8` - 4,800 GiB
- `fs-0c3980010a92252b1` - 4,800 GiB
- `fs-0b2cb0424d3f85268` - 12,000 GiB

The user explicitly instructed that no FSx data be exported to S3 and that no
linked S3 data be deleted or changed. The execution path therefore targets only
the three FSx file systems through `DeleteFileSystem`. It must not issue S3
mutation commands or create an FSx data repository export task.

## Gate 0 inventory freeze

- Repo baseline: branch
  `codex/take222-runtime-report...origin/codex/take222-runtime-report` with many
  pre-existing modified and untracked user artifacts. Those artifacts are out
  of scope and must be preserved.
- All three file systems were refreshed live at `2026-08-09T23:42Z` and are
  `AVAILABLE`, `LUSTRE`, SSD, `PERSISTENT_2`.
- Live `ClientConnections` maximum was `0` for every file system in each of the
  three most recent five-minute CloudWatch datapoints.
- The only running EC2 instances in the two target VPCs were the regional Slurm
  accounting MariaDB host and the Sentieon license host. Read-only SSM command
  `c339a5d4-03d3-4111-9615-d8746db4f8ce`, executed as `ubuntu`, returned no
  Lustre mounts on either host.
- No pending or executing FSx data repository task exists for any target.
- No FSx backup exists for any target. S3-linked Lustre file systems do not
  support a final FSx backup.
- CloudFormation reports that stacks `ifx-sacctpost-10318`, `majors-cluster`,
  and `nvme-migration-test` do not exist. No non-terminated EC2 instance has
  one of those exact `parallelcluster:cluster-name` tags.
- The current shell does not expose `pcluster`; no substitute discovery path
  was used. This does not block exact FSx deletion because the filesystem,
  client, stack, instance, DRA, task, and backup checks are direct AWS reads.

## Exact resource state

| FSx ID | Created | Capacity | Current utilization | Prior owner | Preservation state | Live DRA associations |
|---|---|---:|---:|---|---|---|
| `fs-0942c7bce60871db8` | 2026-07-15 22:40:20 EDT | 4,800 GiB | 0.00% | `ifx-sacctpost-10318` | `dyec:fsx-lifecycle=CLUSTER_BOUND`; `ursa-preserve=true`; prior proof ledger retained it | `dra-0468354fff8b1bbdc`: `/references/` -> `s3://lsmc-dayoa-references-usw2` |
| `fs-0c3980010a92252b1` | 2026-07-18 05:14:24 EDT | 4,800 GiB | 6.52%, approximately 313 GiB of provisioned capacity | `majors-cluster` | `dyec:fsx-lifecycle=PRESERVED_AFTER_CLUSTER_DELETE`; `ursa-preserve=true`; a prior user instruction explicitly stopped its deletion | `dra-04ddc72645adc61a4`: `/run_dir_mounts/pca100-2026/` -> `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/`; `dra-06a58d32ab234e73d`: `/references/` -> `s3://lsmc-dayoa-references-usw2` |
| `fs-0b2cb0424d3f85268` | 2026-07-28 21:05:18 EDT | 12,000 GiB | 0.00% | `nvme-migration-test` | `dyec:fsx-lifecycle=CLUSTER_BOUND`; `dyec-preserve=true`; retained when the prior test work paused | `dra-0a58580d6e20fd0b0`: `/references/` -> `s3://lsmc-dayoa-references-usw2` |

The utilization metric is not a namespace inventory. A zero metric does not
prove the absence of local-only files. The 6.52% metric also does not distinguish
imported/cached S3 data from local-only data. Per the user's instruction, no
export or namespace walk is planned; all FSx-resident state is intentionally
treated as disposable if the second approval is given.

## S3 protection boundary

- All four current DRAs have automatic import policies and have
  `AutoExportPolicy=null`.
- No data repository task is `PENDING` or `EXECUTING`.
- The only historical task in current FSx task history is failed metadata
  import task `task-0e04c4f2fcc81cec6` on `fs-0b2cb0424d3f85268` with
  `1,354,377` successes and `1` failure. It is terminal and cannot export data.
- No export task will be created or awaited.
- No `s3`, `s3api`, DRA-update, or DRA-delete API call is part of the live
  mutation plan. Deleting each filesystem retires its associations as part of
  the filesystem lifecycle; linked S3 buckets, prefixes, and objects remain
  outside deletion scope.
- Immediately before any delete call, re-check that the filesystem is
  `AVAILABLE`, `ClientConnections=0`, and active repository task count is zero.
  Any mismatch fails hard and stops the sequence.

## Exact proposed live calls

After the separate second approval, issue only these filesystem API calls:

```bash
aws fsx delete-file-system \
  --profile lsmc \
  --region us-west-2 \
  --file-system-id fs-0942c7bce60871db8 \
  --client-request-token codex-20260809-fs-0942c7bce60871db8-delete \
  --lustre-configuration SkipFinalBackup=true

aws fsx delete-file-system \
  --profile lsmc \
  --region us-west-2 \
  --file-system-id fs-0c3980010a92252b1 \
  --client-request-token codex-20260809-fs-0c3980010a92252b1-delete \
  --lustre-configuration SkipFinalBackup=true

aws fsx delete-file-system \
  --profile lsmc \
  --region us-west-2 \
  --file-system-id fs-0b2cb0424d3f85268 \
  --client-request-token codex-20260809-fs-0b2cb0424d3f85268-delete \
  --lustre-configuration SkipFinalBackup=true
```

Do not run the DYEC cluster-delete workflow: all three owning stacks are gone,
one filesystem's preserved lifecycle tag deliberately excludes it from that
workflow, and the requested scope is the three exact FSx IDs only.

## Irreversible effect requiring second approval

- Permanently delete 21,600 GiB of provisioned FSx for Lustre capacity across
  the three named file systems.
- Permanently and unrecoverably delete every FSx-resident byte and namespace
  entry, including any local-only analysis output. No export and no final backup
  will be attempted.
- Retire the four live data repository associations listed above and remove
  service-managed resources belonging to the file systems.
- Supersede the prior preservation decisions and tags, including the explicit
  earlier deletion stop for `fs-0c3980010a92252b1`.
- Do not delete or modify S3 buckets, prefixes, or objects. Do not delete
  clusters, EC2 instances, standalone security groups, or unrelated resources.

## Tracking rows

| ID | Area | Requirement | Status | Category | Approval gate | Evidence / terminal note |
|---|---|---|---|---|---|---|
| FSXDEL-001 | Inventory | Resolve exact file systems, ownership, preservation, capacity, utilization, stacks, instances, mounts, DRAs, tasks, and backups. | SUCCESS | legitimate_safety_handling | Gate 0 | Direct live AWS reads and SSM command `c339a5d4-03d3-4111-9615-d8746db4f8ce`; exact state recorded above. |
| FSXDEL-002 | S3 boundary | Prove the deletion path performs no export and no S3 mutation. | SUCCESS | active_product_contract | Gate 1 | All four DRAs have no auto-export policy; no active task exists; exact proposed calls target only `fsx:DeleteFileSystem`. |
| FSXDEL-003 | Approval | Obtain a second explicit destructive approval after presenting the exact irreversible effect. | SUCCESS | legitimate_safety_handling | Gate 2 | At `2026-08-09T23:52Z`, the user repeated the exact three IDs, accepted permanent loss of all FSx-only data with no export or final backup, and prohibited changes to linked S3 data. |
| FSXDEL-004 | Delete | Re-check invariants, submit the three exact delete calls, and wait for all three IDs to become absent. | SUCCESS | feature_implementation | Gate 3 | Final preflight at `2026-08-09T23:52Z`: all three `AVAILABLE`, latest `ClientConnections=0`, zero active repository tasks. CloudTrail records the three exact `DeleteFileSystem` calls at `23:52:37Z`-`23:52:38Z`, each with `skipFinalBackup=true` and response `DELETING`. First observed absent: `fs-0942...` at `00:01:24Z`, `fs-0c398...` at `00:03:28Z`, and `fs-0b2cb...` at `00:07:23Z`. |
| FSXDEL-005 | Verification | Confirm all three FSx IDs and four DRAs are absent, while issuing no S3 mutation. | SUCCESS | contract_test | Gate 4 | Regional filtered filesystem query returned `[]`; exact-ID queries returned `FileSystemNotFound` for all three; exact four-association query returned `[]`; export-task query returned `[]`. No S3 mutation, export-task, DRA-update, or DRA-delete call was issued. |

## Execution and terminal verification

- CloudTrail deletion events:
  - `2026-08-09T23:52:37Z`: `fs-0942c7bce60871db8`,
    `skipFinalBackup=true`, response `DELETING`.
  - `2026-08-09T23:52:38Z`: `fs-0c3980010a92252b1`,
    `skipFinalBackup=true`, response `DELETING`.
  - `2026-08-09T23:52:38Z`: `fs-0b2cb0424d3f85268`,
    `skipFinalBackup=true`, response `DELETING`.
- The read-only 15-second monitor first observed the IDs absent at
  `2026-08-10T00:01:24Z`, `2026-08-10T00:03:28Z`, and
  `2026-08-10T00:07:23Z`, respectively.
- Direct terminal verification returned `FileSystemNotFound` for each exact
  filesystem ID.
- Direct verification of `dra-0468354fff8b1bbdc`,
  `dra-04ddc72645adc61a4`, `dra-06a58d32ab234e73d`, and
  `dra-0a58580d6e20fd0b0` returned an empty association list.
- The target-filesystem export-task query returned an empty list. No export was
  created, no final backup was requested, and no S3 mutation API was called.

## Current terminal-state report

Rows: `5 SUCCESS / 0 BLOCKED / 0 IN_PROGRESS`.

All rows are terminal `SUCCESS`, and the exact deletion objective is complete.
The three filesystems and their four DRA associations are absent. No export or
final backup was created, and no S3 object, cluster, instance, standalone
security group, or unrelated AWS resource was targeted for mutation.
