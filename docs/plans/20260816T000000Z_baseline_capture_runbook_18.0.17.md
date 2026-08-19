# Runbook — Daylily baseline capture, us-west-2d — DYEC 18.0.17 / DayOA 15.0.9

**Goal:** observe every AWS API call a real deploy makes, so the `DaylilyDeployer`
policy and `DayecClusterNodeBoundary` can be derived from evidence instead of
documentation.

Supersedes `20260814T020000Z_baseline_capture_runbook.md`, which targeted DYEC
7.0.0. That version's findings are folded in below.

---

## Version and remote setup — read this first

The local clone's `origin` was `Daylily-Informatics/daylily-ephemeral-cluster`,
the **pre-fork** repo, whose tags stop at **7.0.0**. Active development moved to
**`lsmc-bio/daylily-ephemeral-cluster`**, which is at **18.0.17**. If you are
looking at tags and see nothing above 7, you are looking at the old repo.

```bash
git remote add lsmc-bio https://github.com/lsmc-bio/daylily-ephemeral-cluster.git
git fetch --tags lsmc-bio
git checkout 18.0.17
```

**The DayOA pin needs no editing.** `pyproject.toml` at 18.0.17 no longer pins
DayOA at all — the pin moved into `config/daylily_pipeline_command_catalog.yaml`,
which sets
`default_ref: "15.0.9"` for `daylily-omics-analysis` and is what the
`config.repository_catalog` preflight check validates. DYEC 18.0.17 + DayOA
15.0.9 is the matched pair.

---

## 0. Pre-flight (10 min)

```bash
export AWS_PROFILE=daylily-baseline

# a. Is us-west-2d quiet?
aws ec2 describe-instances --region us-west-2 \
  --filters "Name=tag:Name,Values=Compute" Name=instance-state-name,Values=running \
  --query 'Reservations[].Instances[].{Cluster:Tags[?Key==`parallelcluster:cluster-name`]|[0].Value,AZ:Placement.AvailabilityZone,Type:InstanceType}' \
  --output table

# b. Confirm the role still assumes
aws sts get-caller-identity          # expect assumed-role/DaylilyBaselineDeploy/...

# c. RECORD START TIME
date -u +%Y-%m-%dT%H:%M:%SZ          # <-- T0
```

**Tell people you are deploying.** On 2026-08-14 the baseline cluster was deleted
through Ursa's admin API ten minutes after CREATE_COMPLETE — by a person, not a
reaper. The config now sets `sweep_protection_tag: dyec-preserve=true`, but a tag
is not a substitute for announcing the run.

**Abort if:** a compute node is already running in **us-west-2d**.

---

## 1. Create the cluster

```bash
cd ~/Documents/LSMC/LSMC_Code/daylily-ephemeral-cluster
source ./activate

dyec create \
  --region-az us-west-2d \
  --profile daylily-baseline \
  --config config/baseline-cluster-request.yaml \
  --pass-on-warn
```

### Do NOT add `--non-interactive`

At 18.0.17 the preflight still calls `check_daylily_policies(iam,
aws_ctx.iam_username, ...)` (`daylily_ec/aws/iam.py:369`). Under an assumed role
there is no IAM user, the lookup throws `NoSuchEntity`, and the result is
`CheckStatus.WARN if interactive else CheckStatus.FAIL`. Non-interactive
therefore hard-FAILs before any AWS mutation. Interactive + `--pass-on-warn`
(`create_cluster.py:535,576`) is the documented bridge.

Every value in the config is `USESETVALUE`, so interactive mode still prompts for
nothing.

**Expect `iam.policy.global` / `iam.policy.regional` WARNs.** The ISS-75/C2 fix
that removed these was never upstreamed; it lives on the local branch
`wip/iss75-80-99-baseline-tooling-at-7.0.0`. Expect an IAM write too:
`ensure_pcluster_omics_policy()` is still an idempotent create on the deploy
path. Both are real 18.0.17 behaviour and belong in the capture.

### ⚠ There is no safe "dry run" at 18.0.17

`dyec create` has no `--dry-run` flag. `DAY_BREAK=1` (`pcluster/runner.py:279`)
stops cleanly after the pcluster dry-run and before `pcluster_create` — but
**18.0.17 added a `LIVE AWS STORAGE PROVISIONING` phase that runs *before* the
dry-run.** It creates, for real:

- the FSx filesystem (9600 GiB PERSISTENT_2 here — **~$8.47/hour**)
- a P2 client security group
- the reference DRA, which starts the ~2.45M-object metadata import

Earlier phases also publish boot config to S3, ensure budgets, and create a
cost-center row. So `DAY_BREAK=1` bounds *cluster* creation, not *spend*.

The phase is "**creating or resuming**", so the filesystem is deliberately
reusable: a real deploy that follows soon after reuses it with the metadata
import already warm, which is worth far more than the 43-minute cold create on
2026-08-14. Treat `DAY_BREAK=1` as "validate and leave storage warm", not as a
no-op. If you are not deploying shortly afterwards, delete the filesystem, its
DRA and the security group.

### FSx sizing is a correctness requirement

The config sets **9600 GiB PERSISTENT_2, 1000 MB/s/TiB, AUTOMATIC metadata** —
not the 4800/SCRATCH_2 used on 2026-08-14. The head node boot script blocks until
five paths appear under `/fsx/references/` and `exit 1`s at **1800s**
(`post_install_ubuntu_combined.sh`, `wait_for_reference_data`). Those paths
arrive via an FSx metadata import of ~2.45M objects whose rate scales with
capacity. At 4800/SCRATCH_2 it sustained ~1,400–1,700 objects/sec and cleared the
gate with **80 seconds to spare**.

**Measured 2026-08-14 timeline (4800 GiB SCRATCH_2 — expect faster now):**

| Elapsed | Milestone |
|---|---|
| +0.2 min | IAM roles + head node instance profile created |
| +9 min | FSx AVAILABLE; compute-fleet roles/profiles created |
| +12 min | HeadNode running, SSM online |
| +14→43 min | **blocked** on the FSx metadata import |
| +43.4 min | stack CREATE_COMPLETE |

Minutes 14→43 look like a hang and are not. Watch:

```bash
tail -f /var/log/daylily/*postinstall.log     # on the head node
aws fsx describe-data-repository-tasks --region us-west-2 \
  --filters Name=file-system-id,Values=<fsx-id> --query 'DataRepositoryTasks[0].Status'
```

---

## 2. Connect

```bash
aws ec2 describe-instances --region us-west-2 \
  --filters "Name=tag:parallelcluster:cluster-name,Values=dayec-baseline-0816" \
            "Name=tag:Name,Values=HeadNode" Name=instance-state-name,Values=running \
  --query 'Reservations[].Instances[].InstanceId' --output text

aws ssm start-session --target <id> --profile daylily-baseline --region us-west-2
```

Use a persistent tmux session as `ubuntu` (AGENTS.md contract).

---

## 3. Force a compute scale-up — DO NOT SKIP

```bash
sbatch -p i8 --wrap='sleep 300'
squeue          # CF -> R
sinfo -s
```

This populates the **instance-role** bucket, not the deployer policy.
`slurm_resume.log` on 2026-08-14 showed `Found credentials from IAM Role:
<cluster>-RoleHeadNode-…` → `fleet_manager:create_fleet`, alongside DynamoDB
hostname writes and Route 53 record changes. `ec2:CreateFleet` is a **node-role**
permission; ISS-73 flagging it as a missing *deployer* action was a false
positive.

**If no compute node appears, stop and diagnose.**

---

## 4. Tear down

```bash
dyec delete --cluster-name dayec-baseline-0816 --profile daylily-baseline --region us-west-2
date -u +%Y-%m-%dT%H:%M:%SZ          # <-- T1
```

Type **`please delete`** at the FSx prompt (`--yes` skips it).
⚠️ Check the cluster name twice — production clusters share this account.

Doing the delete **yourself** matters: on 2026-08-14 someone else deleted the
cluster, so the teardown was attributed to `daylily-service` and the deployer's
teardown authorization was never demonstrated.

---

## 5. Capture

```bash
conda run -n DAY-EC python bin/util/capture_baseline.py \
  --start <T0> --end <T1> \
  --region us-west-2 \
  --global-region us-east-1 \
  --profile daylily-baseline \
  --principal DaylilyBaselineDeploy \
  --compare-derived \
  --out baseline_capture.json
```

Wait ~15 min after T1 for CloudTrail delivery. Expect **30–60 min** of runtime:
a busy account produces ~150k management events in a 90-minute window and
`lookup-events` is capped near 2 req/s.

`bin/util/capture_baseline.py` is **not part of the 18.0.17 tree** — restore it
with:

```bash
git checkout wip/iss75-80-99-baseline-tooling-at-7.0.0 -- \
  bin/util/capture_baseline.py tests/test_capture_baseline.py
```

### `--global-region` is not optional

**IAM, STS, budgets and Route 53 log to us-east-1 regardless of deploy region.**
A us-west-2-only scan returns zero IAM events and invites the conclusion that the
deployer needs no IAM permissions. The 2026-08-14 baseline made **95 IAM write
calls** — 12 `CreateRole`, 10 `CreateInstanceProfile`, 30 `AttachRolePolicy`, 33
`PutRolePolicy`, 10 `AddRoleToInstanceProfile` — none visible in us-west-2. The
script prints an `IAM WRITES BY THE DEPLOYER` section; **if it says `none`, the
scan is wrong, not the deploy.**

**Blind spots:**
- S3 object-level calls are absent — management events only.
- Filtering CloudTrail by cluster name **misses calls carrying only resource
  ids** (`fsx:DeleteFileSystem`, `ec2:DeleteSecurityGroup`,
  `DeleteNetworkInterface`, `ReleaseAddress`, `DisassociateAddress`,
  `fsx:DeleteDataRepositoryAssociation`).
- Teardown windows are dominated by **AWS Config/SecurityHub observer traffic**
  reacting to deletions; only the mutating set is a deployer requirement.
- The `instance-role` bucket catches any other ParallelCluster head node live in
  the window.
- `dyec create` opens several botocore sessions and `pcluster` runs as a
  subprocess with its own; single-session filtering misses most of the deploy.

---

## 6. Expected results — 2026-08-14 baseline

Compare against these; deviations are the interesting part.

| | Actions |
|---|---:|
| Deployer (create + teardown) | 135 (53 write / 82 read) |
| Cluster node roles | 26 |

**18.0.17's own inventory** is 38 groups / 204 actions (was 23/135 at 7.0.0), and
still omits three actions the baseline observed the deployer making:
`ec2:CreateLaunchTemplate`, `budgets:CreateBudget`, `kms:CreateGrant`.
`iam:CreateRole` is now present; `ec2:CreateFleet` is still absent, correctly, as
a node-role action.

**Observed failures that are expected, not faults:**
- `budgets:CreateBudget` → `DuplicateRecordException` (global budget exists)
- `sns:CreateTopic` → `AccessDenied`; the regional policy's SNS list omits
  `CreateTopic`, and the global grant is limited to `ParallelClusterImage-*`
- FSx import ends `FAILED` with `FailedCount: 1` — one object
  (`…/sentieon-genomics-202503.03/bundles/DNAscopeElementBioWGS2.1.bundle`)
  exists in S3 as both a file and a prefix, so FSx cannot represent it
  (`S3ObjectTypeMismatch`). Pre-existing, affects every cluster, benign here.

---

## 7. Cleanup

```bash
dyec cluster-info --profile daylily-baseline --region us-west-2
aws fsx describe-file-systems --region us-west-2 \
  --query 'FileSystems[].{Id:FileSystemId,State:Lifecycle,Cluster:Tags[?Key==`parallelcluster:cluster-name`]|[0].Value}' --output table
```

Delete the temporary over-privileged role once the capture is derived:

```bash
aws iam delete-role-policy --role-name DaylilyBaselineDeploy --policy-name ReadCloudTrailEventHistory --profile lsmc-dev
aws iam detach-role-policy --role-name DaylilyBaselineDeploy --policy-arn arn:aws:iam::108782052779:policy/DaylilyGlobalEClusterPolicy --profile lsmc-dev
aws iam detach-role-policy --role-name DaylilyBaselineDeploy --policy-arn arn:aws:iam::108782052779:policy/DaylilyRegionalEClusterPolicy-us-west-2 --profile lsmc-dev
aws iam delete-role --role-name DaylilyBaselineDeploy --profile lsmc-dev
```

Budgets are never deleted by `dyec delete`; the ones this run creates persist.

---

## Timing and abort conditions

| Phase | Duration |
|---|---|
| Pre-flight | 10 min |
| Create | 25–45 min |
| Scale-up | ~10 min |
| Teardown | 10–15 min |
| Capture | 30–60 min (+15 min lag) |
| **Total** | **~2 hours** |

- Create exceeds ~50 min without CREATE_COMPLETE — inspect stack events; a
  half-built stack must be deleted, not re-created
- No compute node after `sbatch` — the capture is worthless without `CreateFleet`
- Any prompt naming a cluster that is not `dayec-baseline-0816`
- The cluster disappears mid-run — check `DeleteStack` in CloudTrail before
  assuming failure; `DeletionTime` plus `"User Initiated"` in stack events is the
  tell, and CloudTrail cannot name the human because Ursa authenticates as the
  shared `daylily-service` user
