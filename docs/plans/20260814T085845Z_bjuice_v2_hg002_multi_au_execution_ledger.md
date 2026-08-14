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
| REL-001 | Integrate DayOA release pin into DYEC release. | Orchestrator | SUCCESS | Release gate | Published annotated DayOA `14.0.15` (tag object `76a069704cd7e7150b03ca0cd377ba5622c30d51`) at `8781a14abb48e5e17892e4b1d872f8ffa1e54173`; published annotated DYEC `17.0.15` (tag object `ed745666bf77fb62ed34771c85961da56da45cd1`) at `0644308e2a80edfb133654a0add6463cfb2d36cf`. Both remote tag refs were verified. The DYEC `17.0.15` catalog snapshot pins DayOA `14.0.15`. |
| HN-001 | Make the released DYEC catalog available to the headnode and verify its exact tag through DYEC. | Operations | BLOCKED | Launch preflight | Deferred because G0-002 lacks the terminal direct-coverage receipt. No controller configuration or launch is justified until the receipt arrives; unrelated queue work remains untouched. |
| MAN-001 | Generate and validate seven-row manifest set from verified `C_ILMN`, with `ROUND_DOWN` fractions. | Operations | BLOCKED | Manifest gate | Blocked by G0-002. Reject missing/ambiguous denominator or target > denominator. |
| DRY-001 | Render and launch a distinct DYEC catalog dry run; prove seven AU roots and zero Slurm jobs. | Operations | BLOCKED | Dry-run gate | Blocked by G0-002; controller must exit `0` and no dry-root may be reused. |
| LIVE-001 | DYEC catalog live launch in its controller-owned tmux session. | Operations | BLOCKED | Launch gate | Blocked by G0-002; visit/lock and fresh analysis root must be recorded by DYEC. |
| MON-001 | Poll DYEC workflow/controller/job state every 10 minutes until terminal. | Operations | BLOCKED | Monitor gate | Blocked by G0-002 because no controller may start; if launched later, stop on terminal state and ask the user at six hours before extending. |
| SLK-001 | Post first attributable-job update and all terminal updates in one JohnM/Mike K Slack thread keyed by `analysis -d <id>`. | Operations | BLOCKED | Notification gate | Blocked by G0-002 because no attributable job exists; thread timestamp will be recorded only after first detected job. |
| EXP-001 | DYEC DRA export after live controller `rc=0` to the derived analysis-id prefix. | Operations | BLOCKED | Export gate | Blocked by G0-002 because no live controller exists; later verify task success, destination freshness/non-overlap, and receipt. |
| DEL-001 | Successful-export-gated FSx analysis-root deletion. | User + Operations | BLOCKED_APPROVAL | Destructive gate | Requires a second explicit approval after exact FSx source and final S3 URI are restated. |
| FIN-001 | Reconcile all rows, release refs, Slack thread, and final disposition. | Orchestrator | BLOCKED | Completion gate | Code/release rows are terminal, but G0-002 blocks every operational row. Resume only with one terminal full-preval HG002 direct-ILMN coverage receipt. Deletion remains separately BLOCKED_APPROVAL even after a successful export. |

## Non-negotiable boundaries

- Cluster, controller, mount, status, launch, and export operations use `dyec`; no direct AWS, pcluster, SSM, Slurm, or raw DayOA invocation.
- Catalog launch owns the remote `ubuntu` tmux controller and uses DayOA's `dy-r` wrapper.
- The existing slim HG002 catalog commands and their fixture inputs are out of scope and remain unchanged.
- The export destination is `s3://lsmc-dayoa-analysis-results-usw2/derived/bjuice-v2-multi-analysis-unit/<analysis-id>/`.
