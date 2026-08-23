# Phase 5 run record — proving the scoped deployer

**2026-08-23 · account `108782052779` · us-west-2d · DYEC 18.0.17**

## Result

A full Daylily cluster lifecycle — create, bootstrap, DayOA init, delete — ran
under `DaylilyDeployerTest`, a principal holding **only** the scoped deployer
policy: no `DaylilyGlobalEClusterPolicy`, no
`DaylilyRegionalEClusterPolicy-us-west-2`, no `daylily-service-cluster-policy`,
and none of `DaylilyBaselineDeploy`'s inline additions.

Two independent successful creates (runs 3 and 4), which is the precondition
Phase 6 sets before production templates are touched.

## What the deployer cannot do

Verified by simulation at every policy revision, and unchanged by the final
compression pass:

| Attempt | Result |
|---|---|
| `iam:CreateUser`, `iam:CreateAccessKey` | **explicitDeny** |
| `iam:PassRole` of an arbitrary admin role | **explicitDeny** |
| `iam:CreateRole` without the boundary | implicitDeny |
| `iam:CreateRole`/`TagRole` outside `/daylily-pc/` | **explicitDeny** |
| `ec2:RunInstances` in `eu-central-1` | implicitDeny |
| `lambda:InvokeFunction` on a non-`pcluster-*` function | implicitDeny |

The escalation path the wide policies leave open — `iam:Create*` beside
unconditional `PassRole` — is closed.

## What it proved it can do

- 53/53 stack resources, zero `CREATE_FAILED`, twice.
- **18 IAM roles created through the deployer**, every one landing at path
  `/daylily-pc/` with `DayecClusterNodeBoundary` attached. The
  `iam:PermissionsBoundary` condition holds against a real ParallelCluster
  deploy, not only in simulation.
- Head node bootstrapped: DYEC cloned from the pinned release via the deploy-key
  secret, FSx mounted (9.0 T), Slurm up with all five partitions.
- Node role reached the S3 references bucket under the boundary — the S3 data
  plane is invisible to CloudTrail, so this was only checkable empirically.
- `day-clone` authenticated and cloned **DayOA 15.0.9**, exercising the
  deploy-key secret on the DayOA path (a different secret ARN from DYEC's).
- `dyoainit` produced a working `DAYOA` environment with snakemake 7.25.0b113.
- `dyec delete` removed the cluster, the external FSx and the P2 security group
  under the scoped role, `exit=0`, no intervention.

## Cost

Four runs, roughly **$28**. Idle rate `$8.4707/hour`: FSx PERSISTENT_2 9600 GiB
$7.8904, headnode `r7i.2xlarge` $0.5292, root EBS $0.0461, public IPv4 $0.0050.

## The eleven defects this found

**Seven by simulation, for $0** — the loop is cheap and worth exhausting first:

1. `iam:SimulatePrincipalPolicy` missing; the validator could not test anything.
2. **The boundary ARN in the `CreateRole` condition had no `/daylily/` path.**
   It could never match, so `CreateRole` was permanently denied. Every deploy
   would have died ~9 minutes in inside the compute-fleet stack, reading as a
   permissions bug rather than a typo.
3. `iam:TagRole` gated on `iam:PermissionsBoundary`, a key AWS does not supply
   for `TagRole` — unsatisfiable by construction. The tell was the asymmetry:
   `UntagRole` sat unconditioned.
4. `iam:PassRole` denied outright on `*`, which blocks every deploy. Restructured
   into a `NotResource` Deny plus a `PassedToService`-conditioned Allow.
5-7. Region-condition placement for global-endpoint services, and the
   `ec2:CreateFleet` question (see below).

**Three classes only a live deploy could find** — simulation evaluates the
actions you hand it and is blind to the ones absent from the inventory entirely:

8. `lambda:InvokeFunction` on `pcluster-CleanupResources-*`. Killed run 1
   36 seconds into the stack.
9. **The whole tag-on-create family.** Creating a resource *with tags* needs the
   create action *and* the service's tag action. `cloudwatch:PutMetricAlarm` was
   allowed, `cloudwatch:TagResource` was not — run 2 died on
   `UnauthorizedTaggingOperation`. Rather than pay a 25-minute deploy per
   discovery, the family was simulated wholesale: 17 tag actions denied,
   including `elasticloadbalancing:AddTags`, `autoscaling:CreateOrUpdateTags`,
   `cloudformation:TagResource` and `logs:TagLogGroup` — each of which creates a
   tagged resource in this same deploy.
10. `fsx:CancelDataRepositoryTask`, teardown-only, invisible until the delete
    path was exercised under the scoped role rather than a privileged one.

**One deliberately refused:** `ec2:CreateFleet` came back denied but is present
in `DayecClusterNodeBoundary` — it is a node-role action Slurm calls at runtime,
not a deployer action. Granting it would have broadened the role for nothing.
This re-confirms the earlier ISS-73 finding.

## The validator cannot be the acceptance gate

`dyec aws validate permissions` simulates with no `aws:RequestedRegion` and no
`iam:PermissionsBoundary`. Every region-conditioned Allow — 103 actions across
`ClusterLifecycleRegional` and `SupportingServicesRegional` — therefore evaluates
as denied. Re-simulating its 195 "denied" actions with realistic request context:
**82 were artifacts, 113 genuine.**

It reached PASS=19 / FAIL=31 and will not go green on a correctly scoped policy.
This is the concrete form of the original plan's claim that the validator
penalises least privilege.

## Size, and why Phase 6 needs a permission set

The policy peaked at 9,972 of the 10,240-character **aggregate** role-inline
quota — about eight actions of headroom. Compressing read-only verbs into
prefixes (30 prefixes replacing 88 enumerated actions) brought it to 8,719.

Only read verbs were collapsed; `iam`, `secretsmanager`, `dynamodb` and
`cloudwatch` were excluded because their reads expose credentials, account
structure or data-plane contents. No `Create*`/`Delete*`/`Put*` wildcard exists
anywhere in the policy — verified programmatically after the rewrite.

That buys room but does not solve it. A managed policy caps at 6,144, which the
document already exceeds. Phase 6's Identity Center permission set (10,240 inline
plus up to 25 managed references) is the structural answer.

## Carried out of this phase

Five findings affecting people outside this work are recorded separately; two of
them — an account-wide outage caused by a root-key policy edit — are the concrete
argument for finishing this project.
