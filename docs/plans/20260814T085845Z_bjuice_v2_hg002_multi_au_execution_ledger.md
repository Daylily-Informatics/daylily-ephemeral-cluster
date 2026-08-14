# Bjuice v2 HG002 multi-AU HIOMR2 execution ledger

Created: 2026-08-14T08:58:45Z  
Controlling repository: `daylily-ephemeral-cluster`  
Controlling branch: `codex/bjuice-v2-multiau-orchestrator`  
Requested cluster: `prod-cand-1703` / `us-west-2` / profile `lsmc`

## Fixed run contract

One fresh neutral analysis ID will be allocated only after the release and Gate 0
rows succeed: `prod-cand-1703-hg002-bjuice-v2-multiau-<UTC>`.

| AU | ILMN target x | ONT hour interval |
|---|---:|---|
| `p5xp5` | 0.5 | `[0,1)` |
| `1x1` | 1 | `[0,2)` |
| `3x3` | 3 | `[0,7)` |
| `5x5` | 5 | `[0,11)` |
| `10x5` | 10 | `[0,19)` |
| `15x5` | 15 | `[0,24)` |
| `15x10` | 15 | `[0,19)` |

Live nullable EUID fields stay blank. No EUID generator will be added. Test
fixtures may persist non-unique `Z-*` values only as explicit test data.

## Execution rows

| ID | Workstream | Owner | Status | Gate | Evidence / next terminal condition |
|---|---|---|---|---|---|
| G0-001 | Record clean-worktree baseline and exact source refs. | Orchestrator | SUCCESS | Gate 0 | DYEC base `96cec5a45993e706e8e075853ac0f5fe27b812ac`; worktree created on this branch. |
| G0-002 | Verify cluster, mounts, controller/job baseline, and full-preval direct ILMN coverage receipt using DYEC only. | Operations | BLOCKED | Gate 0 | Both discovered full-preval candidates failed `dyec workflow status` rc=2 because their required `status.json` receipts are missing: `...ont0-24-mega-ifx-1409-20260813` and `...ont0-25-mega-ifx-1408-20260813`. Direct SR `WgsCoverageMean=43.707192` was observed in the first run output, but is not accepted as the required terminal receipt. |
| G0-003 | Preserve unrelated queue work and establish future-job attribution. | Operations | SUCCESS | Gate 0 | 2026-08-14T08:59:57Z: no live DYEC controller; 25 pre-existing Slurm jobs (11 RUNNING, 13 CONFIGURING, 1 PENDING) remain untouched. New jobs must match this analysis's controller/root. |
| DYO-001 | Implement and test per-AU ONT hour contract and immutable full-preval config in a clean DayOA worktree. | DayOA agent | SUCCESS | Code gate | Commit `8781a14abb48e5e17892e4b1d872f8ffa1e54173`, full integrated suite `1730 passed, 1 skipped`, and published annotated tag `14.0.15`. |
| DYE-001 | Implement and test Bjuice-v2 multi-AU manifest/catalog contract in a clean DYEC worktree. | DYEC agent | SUCCESS | Code gate | Integrated commit `0547ed69`; 357 focused tests passed; source and packaged catalog SHA-256 are both `fdd543213631a45d25bfd678838438000b2ed48bdcc01ae15129b16b529cae2a`; catalog pins DayOA `14.0.15` and keeps nullable live EUID fields blank. |
| REL-001 | Integrate DayOA release pin into DYEC release and verify exact tag availability on headnode. | Orchestrator | IN_PROGRESS | Release gate | DayOA `14.0.15` is published as an annotated tag at `8781a14abb48e5e17892e4b1d872f8ffa1e54173`; DYEC must pin and publish against it, then DYEC must verify headnode availability. |
| MAN-001 | Generate and validate seven-row manifest set from verified `C_ILMN`, with `ROUND_DOWN` fractions. | Operations | PENDING | Manifest gate | Reject missing/ambiguous denominator or target > denominator. |
| DRY-001 | Render and launch a distinct DYEC catalog dry run; prove seven AU roots and zero Slurm jobs. | Operations | PENDING | Dry-run gate | Controller must exit `0`; no dry-root reuse. |
| LIVE-001 | DYEC catalog live launch in its controller-owned tmux session. | Operations | PENDING | Launch gate | Visit/lock and fresh analysis root recorded by DYEC. |
| MON-001 | Poll DYEC workflow/controller/job state every 10 minutes until terminal. | Operations | PENDING | Monitor gate | Stop on terminal state; ask user at six hours before extending. |
| SLK-001 | Post first attributable-job update and all terminal updates in one JohnM/Mike K Slack thread keyed by `analysis -d <id>`. | Operations | PENDING | Notification gate | Thread timestamp recorded here. |
| EXP-001 | DYEC DRA export after live controller `rc=0` to the derived analysis-id prefix. | Operations | PENDING | Export gate | Verify task success, destination freshness/non-overlap, and receipt. |
| DEL-001 | Successful-export-gated FSx analysis-root deletion. | User + Operations | BLOCKED_APPROVAL | Destructive gate | Requires a second explicit approval after exact FSx source and final S3 URI are restated. |
| FIN-001 | Reconcile all rows, release refs, Slack thread, and final disposition. | Orchestrator | PENDING | Completion gate | All non-deletion rows terminal; deletion is SUCCESS or explicitly BLOCKED_APPROVAL. |

## Non-negotiable boundaries

- Cluster, controller, mount, status, launch, and export operations use `dyec`; no direct AWS, pcluster, SSM, Slurm, or raw DayOA invocation.
- Catalog launch owns the remote `ubuntu` tmux controller and uses DayOA's `dy-r` wrapper.
- The existing slim HG002 catalog commands and their fixture inputs are out of scope and remain unchanged.
- The export destination is `s3://lsmc-dayoa-analysis-results-usw2/derived/bjuice-v2-multi-analysis-unit/<analysis-id>/`.
