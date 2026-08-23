# Runbook — Phase 3: prove the boundary alone

**What this isolates.** There are two unknowns in the scoped-role work: is the
*boundary* correct, and is the *deployer policy* correct. This phase changes
**only the boundary** and runs under the **existing over-privileged identity**
(`DaylilyBaselineDeploy`, still holding the wide policies). So any failure here
is unambiguously the boundary's fault. Phase 5 then tests the scoped policy
against a boundary already known good.

Collapse the two and a failure is ambiguous, and each guess costs a two-hour
cycle. That is the entire reason this phase exists.

---

## Prerequisites

| | Check |
|---|---|
| Boundary applied (Phase 1) | `aws iam get-policy --policy-arn arn:aws:iam::108782052779:policy/daylily/DayecClusterNodeBoundary` |
| ISS-80 ported (Phase 2) | on branch `wip/scoped-role-at-18.0.17`, commit `0031f0ff` |
| DYEC / DayOA | 18.0.17 / 15.0.9 |
| Template | `config/day_cluster/intel/us-west-2/us-west-2d/prod_cluster_intel_spot_us-west-2d.yaml` — the only one carrying the token |

Pick a distinct cluster name so no delete prompt can be confused with a live
run, e.g. `dayec-boundary-0820`. **DYEC caps cluster names at 20 characters**
(5-20, lowercase, digits and hyphens) and rejects longer ones at preflight in
0s — `dayec-boundary-test-0820` is 24 and fails. With a `dayec-` prefix you have
14 characters to work with. Edit `cluster_name` in
`config/baseline-cluster-request.yaml`.

---

## 0. Two gates that reject before anything is created

Both were hit on 2026-08-20. Each failed in seconds and created nothing, which is
the behaviour you want — but they cost a cycle each if you meet them cold.

### Cluster name: 5-20 characters

DYEC rejects longer names at preflight in 0s. `dayec-boundary-test-0820` is 24
and fails; `dayec-boundary-0820` is 19 and passes. With a `dayec-` prefix you
have 14 characters to work with. This is the fail-fast behaviour B7 is meant to
generalise, already present for the name length.

### DYEC will not deploy from a working branch

```
The running DYEC version is not an exact non-v release tag:
'18.0.18.dev6+gb5f76fbc1.d20260820'
```

`get_release_version()` (`versioning.py:84`) requires an exact semver tag. Any
commit past a release tag makes setuptools-scm derive a `.devN` version, so
**every phase that deploys with modified DYEC hits this** — Phase 3 and Phase 5
both.

The gate is correct: that version is the ref the head node clones DYEC at, and a
dev version has no tag on `lsmc-bio`. But our change is *deployer-side only* —
`render_iam_cluster_block()` runs locally to produce the cluster YAML, and
ParallelCluster attaches the boundary at stack-creation time. The head node never
needs it and should run a released DYEC.

Options, in preference order:

1. **Release ISS-80 upstream, then deploy from the tag.** No misreporting, and
   Phase 6's template rollout needs the merge anyway. Correct for Phase 5, whose
   result is the acceptance evidence.
2. **`SETUPTOOLS_SCM_PRETEND_VERSION=18.0.17`** — verified to satisfy the gate.
   Local DYEC renders the boundary from the branch; the head node clones released
   18.0.17. Each side runs what it should. Acceptable for Phase 3, whose purpose
   is isolating the boundary variable — but record in the run notes that the
   deployer reported a version it was not running.
3. **Tagging the branch locally is worse**, not better: `git describe` would
   satisfy the gate, but the head node would then try to clone a tag that does
   not exist on the remote, trading a clean failure for a confusing one.

---

## 1. Enable containment

```bash
export AWS_PROFILE=daylily-baseline
export DAY_IAM_PERMISSIONS_BOUNDARY=arn:aws:iam::108782052779:policy/daylily/DayecClusterNodeBoundary
# DAY_IAM_RESOURCE_PREFIX defaults to /daylily-pc/ — leave unset unless testing an override
date -u +%Y-%m-%dT%H:%M:%SZ        # <-- T0
```

## 2. Verify the render BEFORE spending anything

The cheapest possible check. If the `Iam:` block is absent here, the whole phase
is a no-op and you would not find out for 40 minutes.

```bash
cd ~/Documents/LSMC/LSMC_Code/daylily-ephemeral-cluster && source ./activate
python - <<'PY'
import os, re, yaml
from daylily_ec.workflow.create_cluster import render_iam_cluster_block
T = "config/day_cluster/intel/us-west-2/us-west-2d/prod_cluster_intel_spot_us-west-2d.yaml"
raw = open(T).read().replace("${REGSUB_IAM_CLUSTER_BLOCK}", render_iam_cluster_block())
doc = yaml.safe_load(re.sub(r"\$\{[A-Z_0-9]+\}", "placeholder", raw))
print("Iam block:", doc.get("Iam") or "ABSENT — env var not set, phase would be a no-op")
PY
```

Expect `{'PermissionsBoundary': 'arn:...:policy/daylily/DayecClusterNodeBoundary',
'ResourcePrefix': '/daylily-pc/'}`.

## 3. Deploy

```bash
dyec create \
  --region-az us-west-2d \
  --profile daylily-baseline \
  --config config/baseline-cluster-request.yaml \
  --pass-on-warn
```

Interactive + `--pass-on-warn` is required — 18.0.17's preflight still does the
user-shaped `check_daylily_policies` lookup, which hard-FAILs non-interactive
under a role. Two `iam.policy.*` WARNs are expected.

## 4. Verify the boundary actually landed

**Do this before the scale-up.** If the roles were created without the boundary,
the phase proves nothing and you should stop.

```bash
CL=dayec-boundary-0820
for R in $(aws iam list-roles --path-prefix /daylily-pc/ \
            --query "Roles[?starts_with(RoleName,'${CL}')].RoleName" --output text); do
  printf "%-62s %s\n" "$R" \
    "$(aws iam get-role --role-name "$R" --query 'Role.PermissionsBoundary.PermissionsBoundaryArn' --output text)"
done
```

Every role must show the boundary ARN, and all must sit under `/daylily-pc/`.
Expect roughly 18 roles.

## 5. Force a compute scale-up

```bash
aws ssm start-session --target <headnode-id> --profile daylily-baseline --region us-west-2
su - ubuntu -c "sbatch -p i8 --comment <cost-center> --wrap='sleep 300'"
squeue     # CF -> R
```

`sbatch` requires `--comment <cost-center>` at 18.0.17; a bare `sbatch` is
rejected by the enforcement wrapper.

## 6. Validation — all must hold

- Stack reaches `CREATE_COMPLETE`
- All cluster roles carry the boundary, under `/daylily-pc/`
- A compute node launches — proves the boundary permits `ec2:CreateFleet`
- `/var/log/parallelcluster/slurm_resume.log` shows no `AccessDenied`
- Head node SSM stays `Online` ≥10 min — proves the SSM baseline is adequate

## 7. Tear down

```bash
dyec delete --cluster-name dayec-boundary-0820 --profile daylily-baseline --region us-west-2
date -u +%Y-%m-%dT%H:%M:%SZ        # <-- T1
```

Then run the orphan check in Recovery §R4 regardless of outcome.

---

# Recovery

## R1 · Compute node never joins — **no teardown required**

The most likely boundary failure, and the cheapest. A permissions boundary is
referenced **by ARN**, and IAM evaluates against the policy's *current default
version* — so updating the boundary takes effect on **existing roles
immediately**. Iterate in place:

```bash
# 1. find the denial
aws ssm start-session --target <headnode-id> ...
grep -iE "AccessDenied|not authorized" /var/log/parallelcluster/slurm_resume.log | tail

# 2. add the action to daylily-boundary.tf, then
cd ~/Documents/LSMC/LSMC_Code/lsmc-infra/terraform/management/identity-center
AWS_PROFILE=daylily-baseline terraform apply -auto-approve

# 3. retry — no cluster recreate
su - ubuntu -c "sbatch -p i8 --comment <cost-center> --wrap='sleep 300'"
```

A ~2-minute loop. Record every action you add and what denied it.

> **Managed policies cap at 5 versions.** More than four iterations and
> `terraform apply` fails with `LimitExceeded`. Prune:
> ```bash
> aws iam list-policy-versions --policy-arn <boundary-arn> \
>   --query 'Versions[?!IsDefaultVersion].VersionId' --output text
> aws iam delete-policy-version --policy-arn <boundary-arn> --version-id vN
> ```

## R2 · Head node fails to bootstrap — the expensive one

Wait condition times out at **3600s**. Stack ends `CREATE_FAILED`.

This is the failure worth avoiding, because it costs an hour before you learn
anything. If the boundary blocks something the headnode needs at boot — and
especially if it blocks SSM — you lose the ability to diagnose from inside.

```bash
# diagnose from outside while the node still exists
aws ssm describe-instance-information --region us-west-2 \
  --query "InstanceInformationList[?InstanceId=='<id>'].PingStatus" --output text
aws ssm send-command --instance-ids <id> --document-name AWS-RunShellScript \
  --parameters 'commands=["tail -50 /var/log/cloud-init-output.log"]'
```

If SSM is `Online`, read `/var/log/daylily/*postinstall.log` and
`/var/log/cloud-init-output.log`. If SSM is **not** online, the boundary is
likely blocking the SSM agent — widen the `SsmAgentBaseline` statement first.

Then: `dyec delete`, fix the boundary, redeploy. **Never re-create into a
half-built stack.**

## R3 · Stack CREATE_FAILED for any other reason

```bash
aws cloudformation describe-stack-events --region us-west-2 --stack-name <cluster> \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
  --output text | head
dyec delete --cluster-name <cluster> --profile daylily-baseline --region us-west-2
```

## R4 · Orphaned FSx — **check after every failure**

The one that costs money silently. `dyec delete` requires the cluster to exist
(`delete_cluster.py:214` returns *"does not exist"* otherwise), and
`fsx_persistent2.py` has no delete counterpart to `ensure_persistent2_resources`.
So if the deploy dies **after storage provisioning but before the stack
materialises**, a 9600 GiB PERSISTENT_2 filesystem is left billing at
**~$8.47/hour** and no DYEC command will remove it.

```bash
aws fsx describe-file-systems --region us-west-2 \
  --query 'FileSystems[].{Id:FileSystemId,State:Lifecycle,GiB:StorageCapacity,Cluster:Tags[?Key==`parallelcluster:cluster-name`]|[0].Value}' \
  --output table
# anything tagged with the test cluster name and no live stack:
aws fsx delete-file-system --file-system-id fs-XXXX --region us-west-2
```

Delete its DRA first if one exists and the filesystem refuses to delete.

## R5 · Disable containment entirely

Instant rollback to pre-Phase-3 behaviour — no code change, no redeploy of
anything already running:

```bash
unset DAY_IAM_PERMISSIONS_BOUNDARY
```

Clusters already created keep their boundary; new ones are created without one.

## R6 · Terraform state lock stranded

Seen on 2026-08-20. If a run dies holding the lock:

```bash
aws dynamodb get-item --table-name lsmc-terraform-locks --region us-west-2 \
  --key '{"LockID":{"S":"lsmc-terraform-state/management/identity-center/terraform.tfstate"}}'
```

**Verify `Who` and `ID` match your own run before removing it** — deleting
someone else's lock corrupts their apply. Then `terraform force-unlock <ID>`, or
a conditional `delete-item` keyed on the exact `Info` blob.

Note `josh-durham` can take a lock (`PutItem`) but not release one
(`DeleteItem`); run Terraform as `DaylilyBaselineDeploy`, which now has both.

---

## Abort conditions

- Roles created **without** the boundary → stop; the phase proves nothing
- Head node SSM never comes online → boundary blocks the agent; widen before retrying
- Create exceeds ~50 min without `CREATE_COMPLETE` → inspect stack events, delete, do not retry into it
- Any prompt naming a cluster that is not the test cluster

## Exit criteria

One clean create → scale-up → delete with the boundary enforced, and every
widening recorded with the denial that motivated it. That list is a direct input
to Phase 5: anything the boundary needed is something the node plane genuinely
does, and belongs in the permanent record next to the 32 observed actions.

---

# Phase 3 run record — 2026-08-20

Cluster `dayec-boundary-0820`, us-west-2d, identity `DaylilyBaselineDeploy`
(over-privileged, deliberately), boundary **enforced**.

## Result: the boundary is sound. Two gaps found and fixed in place.

| Check | Outcome |
|---|---|
| Roles created under `/daylily-pc/` | 18 of 18 |
| All roles carry the boundary | 18 of 18 (verify with `GetRole` — `ListRoles` does **not** return `PermissionsBoundary`) |
| Head node full boot under the boundary | zero denials |
| SSM agent stayed `Online` | the `AmazonSSMManagedInstanceCore`-derived block was correct |
| `ec2:CreateFleet` under the boundary | compute node launched, 0 denials in `slurm_resume.log` |
| Cluster create | 14m 20s |
| Teardown under the boundary | clean after gap 3 fixed — 0 orphans |
| Window | 23:25:01Z -> 00:42:32Z (~77 min) |

Final state verified: stack gone, FSx `FileSystemNotFound`, no instances, **0
roles remaining under `/daylily-pc/`**. Boundary went v1 -> v4; 4 of the 5
permitted policy versions used, so a fifth iteration would have required pruning.

## Gap 3 — `s3:ListBucketVersions` on ParallelCluster's own bucket — **blocked teardown**

```
CleanupResourcesS3BucketCustomResource
  not authorized to perform: s3:ListBucketVersions
  on arn:aws:s3:::parallelcluster-4da281c1dc024f1c-v1-do-not-delete
  because no permissions boundary allows the s3:ListBucketVersions action
```

PC's cleanup Lambda empties PC's **own internal bucket** during stack DELETE. The
boundary's `DaylilyS3Only` statement scopes S3 to Daylily buckets, which that is
not. Result: `DELETE_FAILED`, cluster will not tear down, FSx keeps billing.

**This gap breaks the tidy story that boundary failures show up at runtime.** The
cluster created and ran perfectly, then would not delete — you discover it when
you are trying to stop paying.

**No capture could have found it.** Both baselines ran with *no boundary in
force*, so nothing was denied; the call succeeded and was attributed to the
deployer rather than flagged as a node-plane requirement. Observation reports what
a principal *did*, never what a *ceiling* would have blocked. That is a fourth
distinct limit of observe-over-derive, alongside conditional branches that did not
fire, S3 object-level calls, and CloudTrail-invisible services.

Fixed with a `ParallelClusterInternalBucketCleanup` statement scoped to
`arn:aws:s3:::parallelcluster-*` — tight despite the unpredictable hash, because
AWS creates those buckets with a fixed prefix.

## Gap 1 — `dynamodb:GetItem` on the cost-centre registry

```
not authorized to perform: dynamodb:GetItem on table/dayec-cost-centers
because no permissions boundary allows the dynamodb:GetItem action
```

The `sbatch` wrapper reads the cost-centre registry on **every** submission, so
this denied *all* job submission — no job, no compute node, nothing to observe.
The boundary scoped DynamoDB to `table/parallelcluster-*`.

Neither baseline capture found it: they recorded `budgets:DescribeBudget` from
that same code path but not the DynamoDB read behind it.

Fixed by adding `table/dayec-cost-centers` and `table/dayec-cost-center-usage`.

## Gap 2 — `ssm:GetParameter` scoped too tightly

The Inspector agent was denied `ssm:GetParameter`. The boundary allowed it only
on `parameter/daylily/*`; `AmazonSSMManagedInstanceCore` grants it on `*`,
because agents read AWS-owned parameters outside any Daylily path.

## R1 confirmed in practice

Both fixes: edit → `terraform apply` → **the new policy version took effect on
already-running roles**. No cluster recreate, ~2 minutes each. A boundary is
referenced by ARN and IAM evaluates the current default version, exactly as the
recovery section claims. Boundary went v1 → v3 during the run.

## Not a boundary problem: Slurm accounting

Post-create ran a cluster **update** to attach Slurm accounting, which failed and
left the stack `UPDATE_ROLLBACK_COMPLETE` with the fleet stopped
(`fleet_restored: False`).

```
fatal: Database schema is from a newer version of Slurm, downgrading is not possible.
```

`slurmdbd` refused to start against the shared accounting database — its schema
was written by a newer Slurm than this cluster runs. Nothing listened on 6819,
`sacctmgr` got connection refused, and the chef recipe
`aws-parallelcluster-slurm::config_slurm_accounting:85` failed.

The boundary is exonerated: `slurmdbd` reached MariaDB, read the schema and
rejected it on version — far past any IAM check. Its secret scope
(`secret:dayec/*`, `AccountingPassword*`) covers accounting fine.

**Two things follow.**

1. **Version skew in shared infrastructure.** Any cluster on the older Slurm can
   no longer attach to that accounting DB. Not caused by this work; affects
   others.
2. **18.0.17 defaults `--slurm-accounting` to `on`**, and the config keys that
   used to disable it (`slurm_accounting_enabled`) were dropped from the
   template — so setting them does nothing. The only way off is the CLI flag:
   ```
   dyec create ... --slurm-accounting off
   ```
   Use it for future capture runs: accounting is not wanted, and its failure
   stops the fleet and rolls the stack back.

## Recovery actually used

The fleet was left `STOPPED` by the failed update, which reads as
`sbatch: Required partition not available (inactive or drain)` — a lifecycle
state, not a permission. Restarted with:

```
pcluster update-compute-fleet --cluster-name <name> --region us-west-2 --status START_REQUESTED
```

Worth adding to the recovery section: **a stopped fleet looks like a Slurm
problem and is not one.**
