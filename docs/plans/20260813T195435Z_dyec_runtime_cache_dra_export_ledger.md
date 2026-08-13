# DYEC runtime-cache DRA export and 17.0.8 release ledger

Created: `2026-08-13T19:54:35Z`

## Objective

Add one supported DYEC CLI command that saves complete cluster-scoped Conda
environments and container images for later cluster reuse without allowing an
AWS S3 CLI transport. The command must stage immutable cache entries with
`cp -a` into a fresh
`/fsx/analysis_results/<executing-entity>/<cache-export-id>/` root, preserve
internal symlinks, and invoke only the existing DYEC FSx DRA export workflow.
Missing source contracts, active cache builders, an existing staging root, an
overlapping DRA, a non-empty S3 destination, or unavailable DRA infrastructure
must fail closed. There is no `aws s3 cp`, `aws s3 sync`, `aws s3 mv`, SDK
object-copy loop, or other object-transfer fallback.

This is a DYEC-only product change. DayOA remains exact `14.0.9`; no DayOA
source or version change is authorized or required. The previously attempted
live cache staging/export on `prod-cand-1703` is cancelled and will not be
resumed by this release work.

## Gate 0 inventory freeze

- Worktree:
  `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-17.0.8-cache-dra-export`.
- Branch: `codex/dyec-17.0.8-cache-dra-export`, created from exact annotated
  tag `17.0.7` at commit
  `716137b81e951140fa25fb31a46e65f900b14638`.
- Remote maximum strict numeric-semver DYEC tag at inventory: `17.0.7`;
  intended patch release: `17.0.8`.
- Exact retained DayOA pin: annotated tag `14.0.9`, commit
  `f4c7aa7e15f7dca602059097cb2314f96f05a826`.
- Existing export implementation: `dyec exports transfer` already performs
  attach, explicit `EXPORT_TO_REPOSITORY`, receipt write, and safe detach for
  one exact analysis root. It does not stage runtime caches.
- Existing cache implementation: DYEC `17.0.7` creates a generation-scoped
  writable Conda/container namespace. Conda starts empty because historical
  high-level S3 promotion flattened package symlinks; safe container seeds are
  still linked from the reference DRA.
- AWS FSx contract: neither the staging FSx path nor its S3 destination may
  overlap an active DRA. A reference DRA that maps an entire bucket therefore
  prevents an output DRA from targeting a subprefix of that same bucket on the
  same filesystem; the new command must detect this before staging.
- Primary checkout and the active HG002 controller are outside this release
  worktree and will not be modified, configured, stopped, or monitored here.
- Release authorization: commit, push, PR, merge after green checks, and an
  annotated non-`v` tag are authorized by the user's release-chain direction.
  PyPI/package-index publication is not requested and is excluded.

Gate 0 status: `SUCCESS`.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| CMD-001 | CLI | Add an explicit discoverable runtime-cache export command with cluster, cache identity, immutable destination, receipt, timeout, and cache-user inputs | SUCCESS | feature_implementation | Gate 1 | Codex | `dyec runtime-cache export --help` and JSON dry-run succeeded; registry records JSON, mutation, and long-running policies. |  | Command is discoverable and writes one combined durable receipt for live work. |
| STAGE-001 | Headnode staging | Inventory only real completed environment directories plus adjacent YAMLs and real nonempty SIF/SIMG files, reject active builders, and stage with `cp -a` | SUCCESS | feature_implementation | Gate 1 | Codex | `daylily_ec/runtime_cache_export.py`; generated Bash passed `bash -n`; tests require completed Conda history/YAML, real SIF/SIMG, active-workflow rejection, byte/symlink checks, and stable before/after source inventory. |  | Seeded container links are counted but not recopied; complete real generation entries are preserved. |
| DRA-001 | Transfer boundary | Reject overlapping/non-empty destinations and hand off only to DYEC FSx DRA attach/export/detach; retain staged FSx data | SUCCESS | legitimate_safety_handling | Gate 4 | Codex | DRA preflight runs before and after staging; `validate_no_overlapping_export_dra` now checks both FSx and S3 paths; unit path asserts `delete_data_in_file_system=False`, successful detach, and no object-copy command. |  | Destination collision or DRA failure is terminal with retained stage/receipt evidence. |
| GUIDE-001 | Operator guidance | Block high-level AWS S3 CLI/SDK object copying for runtime cache trees and document the sole `cp -a` plus DRA path | SUCCESS | config_or_startup_contract | Gate 4 | Codex | `AGENTS.md`, `docs/cli_reference.md`, and `dyec --json agent guidance` carry the same DRA-only/no-fallback boundary. |  | Historical evidence scripts remain records, but current operator guidance forbids their cache-copy transport. |
| TEST-001 | Validation | Add unit/CLI/help/negative tests, source-payload parity checks, focused/full tests, Ruff, compile, and diff checks | SUCCESS | contract_test | Gate 5 | Codex | Focused suite: `293 passed`; full suite: `2524 passed, 11 skipped`; new-file Ruff/format, critical Ruff selectors, `py_compile`, help/JSON smoke, catalog byte parity, and `git diff --check` passed. |  | Two pre-existing deprecation warnings only. |
| PIN-001 | Catalog | Add immutable `17.0.8` catalog snapshot equal to current and keep every DayOA ref at exact `14.0.9` | SUCCESS | config_or_startup_contract | Gate 5 | Codex | Source and packaged catalogs are byte-identical; `17.0.8 == current`; catalog/fork/alias tests passed; `17.0.7` remains preserved. |  | DayOA is unchanged at annotated tag `14.0.9`, commit `f4c7aa7e15f7dca602059097cb2314f96f05a826`. |
| REL-001 | Release | Commit, push, open PR, wait for required checks, merge, and push annotated tag `17.0.8` on the clean merged commit | IN_PROGRESS | feature_implementation | Gate 5 | Codex | Implementation and local release gates are green. |  | Awaiting commit, remote PR checks, merge, and annotated tag push. |
| LIVE-001 | Cancelled live export | Do not run this command on the cancelled `prod-cand-1703` cache set | NO_LONGER_NEEDED | plan_amendment | Gate 5 | Codex | User explicitly cancelled all live cache export/copy work before requesting the reusable command. | Live execution was withdrawn. | Product implementation and local/mocked verification only. |

## Acceptance boundary

All rows must be terminal. Objective completion requires a tested CLI command,
hard negative evidence for AWS S3 CLI/SDK object-copy paths, a DRA-only receipt
path, updated operator guidance, exact DayOA `14.0.9` preservation, a clean
merged DYEC commit, and an annotated remote `17.0.8` tag. No live cache export,
FSx cleanup, S3 deletion, headnode configuration, PyPI publication, or Slurm
action is part of acceptance.

## Current report

All rows terminal: `no`

Objective complete: `no`

Status counts: `SUCCESS=6`, `IN_PROGRESS=1`, `OPEN=0`,
`NO_LONGER_NEEDED=1`.
