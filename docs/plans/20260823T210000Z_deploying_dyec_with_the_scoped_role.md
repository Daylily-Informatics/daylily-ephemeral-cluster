# Deploying DYEC with the scoped role

**How to create, operate and tear down a Daylily cluster without root-equivalent
credentials.**

Account `108782052779` · DYEC 18.0.17 · us-west-2 · written 2026-08-23

---

## Read this first: what stage this is at

The scoped identity today is **`DaylilyDeployerTest`**, an IAM role whose trust
policy allows exactly one principal — `user/josh-durham`. It is deliberately
narrow because Phase 5 needed a clean test subject, not a shared credential.

**So this runbook is currently single-operator.** Phase 6 converts the proven
action set into an Identity Center permission set that the team assumes through
SSO; at that point everything below stays true except the profile block, which
becomes an SSO profile. Nothing here should be read as "the team can start using
this today" — one person can.

The wide policies are all still attached and nothing has been detached. This is
additive.

---

## The identity

```
arn:aws:iam::108782052779:role/daylily/DaylilyDeployerTest
```

It holds **one** inline policy, `DaylilyDeployerPhaseA`, and no attached managed
policies. That isolation is the point: a principal that still carried
`DaylilyGlobalEClusterPolicy` would pass any test regardless of whether the
scoped policy is correct.

What it cannot do, verified by simulation and unchanged by later edits:

| Attempt | Result |
|---|---|
| `iam:CreateUser`, `iam:CreateAccessKey` | **explicitDeny** |
| `iam:PassRole` of an arbitrary role | **explicitDeny** |
| `iam:CreateRole` without the node boundary | implicitDeny |
| `iam:CreateRole` / `TagRole` outside `/daylily-pc/` | **explicitDeny** |
| anything in a region other than us-west-2 | implicitDeny |
| `lambda:InvokeFunction` on a non-`pcluster-*` function | implicitDeny |

## One-time local setup

Add to `~/.aws/config`:

```ini
[profile daylily-deployer-test]
role_arn = arn:aws:iam::108782052779:role/daylily/DaylilyDeployerTest
source_profile = default          # must be the josh-durham identity
region = us-west-2
output = json
duration_seconds = 43200
```

`source_profile` must resolve to `user/josh-durham` — the trust policy allows
nothing else, so any other source fails at `sts:AssumeRole`.

`duration_seconds = 43200` is deliberate. A create plus a DayOA init runs for
hours, and a one-hour session expiring mid-deploy surfaces as a wall of API
failures that look exactly like permission gaps — poisoning the signal you are
trying to read.

Check it works:

```bash
AWS_PROFILE=daylily-deployer-test aws sts get-caller-identity --query Arn --output text
# arn:aws:sts::108782052779:assumed-role/DaylilyDeployerTest/botocore-session-...
```

## Environment

```bash
export SETUPTOOLS_SCM_PRETEND_VERSION=18.0.17
export DAY_IAM_PERMISSIONS_BOUNDARY=arn:aws:iam::108782052779:policy/daylily/DayecClusterNodeBoundary
export DAY_IAM_RESOURCE_PREFIX=/daylily-pc/
```

- `SETUPTOOLS_SCM_PRETEND_VERSION` is only needed when running from a checkout
  that sits past the release tag. DYEC refuses to configure a headnode from a
  dev version (`18.0.18.dev6+...`), and this makes the working tree present
  itself as the release it is based on. Not needed from an installed release.
- The two `DAY_IAM_*` variables are what render the `Iam:` block into the cluster
  YAML. **Without them ParallelCluster creates node roles with no boundary and
  outside `/daylily-pc/`, and the deployer is denied** — the failure appears
  roughly nine minutes in, inside the compute-fleet stack.

## Create

```bash
cd <dyec-checkout>
conda run -n DAY-EC dyec create \
  --profile daylily-deployer-test \
  --region-az us-west-2d \
  --config config/baseline-cluster-request.yaml \
  --pass-on-warn \
  --slurm-accounting off
```

`--pass-on-warn` is **required**, not cosmetic. Two preflight checks
(`iam.policy.global`, `iam.policy.regional`) look for a policy by *name* attached
to an IAM *user*. Under an assumed role there is no user, and a correctly scoped
policy has a different name — so they can never pass. They surface as WARN in
interactive mode and `--pass-on-warn` proceeds. Non-interactive hard-fails and
aborts before any AWS mutation. C2 removes these checks.

`--slurm-accounting off` avoids a known-broken dependency: the shared accounting
database has version-skewed and `slurmdbd` refuses its schema. Note that the
config key which used to disable accounting is silently ignored in 18.0.17 — the
CLI flag is the only working control.

Expect roughly **35 minutes** and about **$8.47/hour** while it lives
(FSx PERSISTENT_2 9600 GiB $7.89, headnode `r7i.2xlarge` $0.53, EBS $0.05,
public IPv4 $0.005).

## Verify

`CREATE_COMPLETE` is **not** readiness. CloudFormation signals while DYEC's
post-create configuration is still installing the DAY-EC environment and
`day-clone` on the node. Poll for the tool, not the stack:

```bash
conda run -n DAY-EC dyec headnode run \
  --profile daylily-deployer-test --region us-west-2 --cluster <name> \
  "bash -lc 'command -v day-clone >/dev/null && echo READY || echo NOTREADY'"
```

Confirm the boundary actually landed on what ParallelCluster built:

```bash
for R in $(aws iam list-roles --path-prefix /daylily-pc/ --query 'Roles[].RoleName' --output text); do
  aws iam get-role --role-name "$R" \
    --query 'Role.[RoleName,PermissionsBoundary.PermissionsBoundaryArn]' --output text
done
```

Every role must show `policy/daylily/DayecClusterNodeBoundary`. A role at
`/daylily-pc/` **without** a boundary means the `Iam:` block did not render —
check the rendered YAML, not the template.

## DayOA

```bash
# on the headnode
day-clone --list                        # shows valid refs; DayOA default is 15.0.9
day-clone -d <analysis-id> -t 15.0.9
cd /fsx/analysis_results/<cluster>/<analysis-id>/daylily-omics-analysis
source dyoainit                         # SOURCED, not executed
```

**If `dyoainit` ends with `Failed to install the DAYOA environment`, run it
again.** The final step is a mermaid/Chrome PDF smoke test with a 30-second
timeout that fires while the machine is still saturated finishing the install.
The conda environment is already built at that point; a retry on an idle machine
succeeds. This is not a permissions problem — verify by confirming there is no
`AccessDenied` in the output.

## Delete

```bash
conda run -n DAY-EC dyec delete \
  --profile daylily-deployer-test \
  --region us-west-2 \
  --cluster-name <name> \
  --yes
```

Note `--region`, **not** `--region-az`. `create` and `delete` disagree on this
flag and the error is easy to misread as a permissions failure.

## When a deploy fails: it leaks a filesystem

This is the trap most likely to cost real money.

**The FSx filesystem is not a CloudFormation resource.** DYEC creates it as an
external CLUSTER_BOUND filesystem outside the stack, so **rollback does not
delete it**. `ROLLBACK_COMPLETE` gives a false impression that cleanup finished
while 9600 GiB keeps billing at ~$7.89/hour.

Worse, `dyec delete` cannot remove it either, because the FSx metadata import is
still running when cleanup begins:

```
An error occurred (BadRequest) when calling the DeleteFileSystem operation:
There is an active data repository task in progress for this file system.
```

Recovery, by hand:

```bash
FS=$(aws fsx describe-file-systems --region us-west-2 \
     --query "FileSystems[?Tags[?Value=='<cluster-name>']].FileSystemId" --output text)

TASK=$(aws fsx describe-data-repository-tasks --region us-west-2 \
       --filters Name=file-system-id,Values=$FS \
       --query 'DataRepositoryTasks[?Lifecycle==`EXECUTING`].TaskId' --output text)

aws fsx cancel-data-repository-task --region us-west-2 --task-id "$TASK"
# wait for it to leave EXECUTING/CANCELING, then:
aws fsx delete-file-system --region us-west-2 --file-system-id "$FS"
```

A *successful* cluster tears down cleanly with no intervention — this only bites
failed deploys, which is exactly when an operator is distracted. **After any
failed deploy, check for an orphaned filesystem before doing anything else.**

## Reading failures correctly

**Do not use `dyec aws validate permissions` as a pass/fail gate.** It simulates
with no `aws:RequestedRegion` and no `iam:PermissionsBoundary`, so every
region-conditioned Allow evaluates as denied. On a correct policy it reports
roughly PASS=19 / FAIL=31 and will never go green. Of its 195 "denied" actions,
82 were simulation artifacts. It is useful as a regression detector, not an
acceptance test.

Where real denials show up:

| Denial type | Where it appears | Why |
|---|---|---|
| Management-plane | CloudTrail, and CloudFormation stack events | normal |
| **Lambda invoke** | **CloudFormation stack events only** | invocations are *data* events; the org trail has no data-event selectors |
| **S3 data plane** | DYEC/bootstrap errors only | same reason |

Two live deploys were diagnosed from `describe-stack-events`, not CloudTrail. If
a deploy fails and CloudTrail looks clean, that is not evidence of no denial:

```bash
aws cloudformation describe-stack-events --region us-west-2 --stack-name <name> \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
  --output text | head
```

## If you need to add a permission

The policy lives in `lsmc-infra` at
`terraform/management/identity-center/DaylilyDeployer-PhaseA.json`, applied by
`aws_iam_role_policy.daylily_deployer_test_scoped`.

Before adding anything, check two things that produced most of Phase 5's false
alarms:

1. **Simulate with real context.** Pass `aws:RequestedRegion=us-west-2`, and
   `iam:PermissionsBoundary` for IAM writes. Without them a correct grant reads
   as denied.
2. **Ask whether it belongs to the node, not the deployer.** `ec2:CreateFleet`
   looks like a deployer gap and is not — it is in `DayecClusterNodeBoundary`
   because Slurm calls it at runtime. Check the boundary before widening the
   deployer.

Watch the size. The aggregate role-inline quota is 10,240 characters and the
document sits at 9,358 — roughly 880 characters, about 25 actions, of headroom. A customer-managed policy caps at 6,144, which it
already exceeds — so it cannot simply be moved. Phase 6's permission set
(10,240 inline plus 25 managed references) is the structural fix.

## What not to do

- **Do not deploy as root.** The root access key is in daily use and that is the
  thing this work exists to end.
- **Do not fall back to `DaylilyBaselineDeploy`** for a "quick" deploy. It is
  over-privileged by design and only exists to bootstrap this work; using it
  hides exactly the gaps this role is meant to reveal.
- **Do not add an action just because the validator says it is denied.**
  Re-simulate with context first; most of those are artifacts.
