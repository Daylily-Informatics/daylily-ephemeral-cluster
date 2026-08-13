# Cluster-generation cache namespace and DYEC 17.0.7 release ledger

Created: `2026-08-13T15:08:31Z`

## Objective

Prevent recycled headnode hostnames from selecting stale flattened Conda
prefixes, provide DayOA with one explicit immutable cluster-generation cache
namespace, pin the headnode-proven DayOA `14.0.9` release in a new immutable
DYEC `17.0.7` catalog snapshot, and configure the local workstation and
`prod-cand-1703` headnode to exact `17.0.7` only after the accepted workflow
controller is terminal. GitHub commit/branch/tag publication is authorized;
PyPI and all package-index uploads are forbidden.

## Gate 0 inventory freeze

- Worktree:
  `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-17.0.7-cache-namespace`.
- Branch: `codex/dyec-17.0.7-cache-namespace`, based on exact annotated DYEC
  tag `17.0.6` at `7dcb03d2d6b1f2078a16747eff78cc2387627209`.
- Planned DayOA pin: exact future annotated tag `14.0.9`; no catalog mutation
  or DYEC tag may treat that dependency as released until its remote tag is
  verified.
- Headnode safety boundary: `dyec headnode configure` resets/cleans the shared
  checkout, prunes and updates the shared Conda environment, reinstalls tools,
  and replaces the shared `sbatch` wrapper. It must not run while a DayOA
  controller is active.
- Primary-checkout boundary: unrelated user files in the primary checkout are
  not staged, removed, or committed. The final local exact-tag update will
  preserve them.
- Release boundary: no `twup`, `twine upload`, or PyPI action. Local artifact
  build plus `twine check` is validation only.

Gate 0 status: `SUCCESS`.

## Design contract

- Raw reference-cache Conda prefixes are no longer seeded into cluster-writable
  cache paths. The cluster cache starts empty so Conda can create real
  environments with their internal symlinks intact.
- The namespace is `<cluster-name>-<CloudFormation-stack-UUID>`. The UUID
  changes when a cluster name is recreated and remains stable across ordinary
  node replacement within one cluster generation.
- CloudFormation lookup occurs only on the headnode. Live evidence showed the
  headnode role can call `DescribeStacks`, while a ComputeFleet role receives
  `AccessDenied`; compute-node post-install therefore does not perform this
  lookup or initialize shared cache paths.
- `/etc/profile.d/daylily-cluster-cache-namespace.sh` exports the exact
  `DAYOA_CLUSTER_CACHE_NAMESPACE` consumed by DayOA. Missing or malformed
  namespace state fails readiness and DayOA profile rendering; there is no
  hostname fallback.
- `dyec headnode configure` performs its active-controller guard before any
  deploy-key, credential-helper, checkout, environment, tool, or wrapper
  mutation.

## Control ledger

| ID | Area | Requirement | Status | Evidence / terminal note |
|---|---|---|---|---|
| CACHE-001 | Node setup | Stop raw Conda-cache seeding and create empty cluster-generation paths on headnodes only | SUCCESS | Source/payload Ubuntu and RHEL scripts match; Bash syntax and contract tests pass. |
| CACHE-002 | Namespace | Resolve exact CloudFormation stack UUID, install explicit profile, and reject legacy top-level env links | SUCCESS | Headnode lookup proved against `prod-cand-1703`; ComputeFleet denial is handled by the headnode-only execution boundary. |
| SAFE-001 | Configure | Refuse headnode configuration before mutation when a DayOA controller is active | SUCCESS | Guard executes as the first remote call; focused failure-path test proves zero writes/follow-up calls. |
| READY-001 | Readiness | Require namespace profile and namespace-scoped writable directories; drop cached-Conda reference dependency | SUCCESS | Focused readiness tests pass with Ubuntu and EC2-user contracts. |
| TEST-001 | Validation | Pass source/payload parity, syntax, focused/full tests, lint/diff, and local wheel/sdist checks | SUCCESS | Complete suite: 2516 passed, 11 expected live-only skips. Source/payload catalog and post-install parity, Bash syntax, critical Ruff selectors, compile validation, and `git diff --check` pass. Exact 17.0.7 wheel/sdist pass `twine check`, embed the exact catalog, and contain no bytecode: wheel SHA-256 `c6ed6d1ebd4c1037ee6270a3482a05adbd0f93be4a0dce4a3b560342bde13cac`; sdist SHA-256 `1d536aa4e80a64a051316cff0a5d0892eac0dc8070621e82f5368709fe210d96`. No artifact was uploaded. |
| PIN-001 | Catalog | Add immutable `17.0.7 == current`, pin active rows to exact DayOA 14.0.9, and freeze all older snapshots | SUCCESS | Remote annotated DayOA tag object `91ecd2529d56538e0a268b94e73c30e421bbeae0` peels to live-proven commit `f4c7aa7e15f7dca602059097cb2314f96f05a826`. Source/payload catalogs are byte-identical; current equals `17.0.7` and pins 14.0.9; immutable `17.0.6` remains byte-frozen on 14.0.8 with SHA-256 `b8cb52a26e74a4757850f048d3f903df45393014cc596db50ad97ae27b4242b6`. |
| REL-001 | Release | Commit/push branch, create/push annotated 17.0.7, and verify remote tag object/peel | OPEN | Gated on PIN-001 and final validation. |
| LOCAL-001 | Local | Update primary local DYEC to exact clean 17.0.7 without disturbing user files | OPEN | Gated on remote DYEC tag verification. |
| HEAD-001 | Headnode | After controller terminal, configure headnode from exact DYEC 17.0.7 and verify namespace/readiness/version | OPEN | Active-controller guard intentionally blocks this while the retry runs. |

## Acceptance boundary

The objective is complete only when all rows are terminal, DayOA `14.0.9` and
DYEC `17.0.7` remote annotated tags peel to their clean tested commits, local
DYEC reports exact `17.0.7`, the terminal-controller gate is satisfied, and
headnode configuration/readiness reports exact `17.0.7` plus the immutable
cluster-generation namespace.

## Current report

All rows terminal: `no`

Objective complete: `no`
