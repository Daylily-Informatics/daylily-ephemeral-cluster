# prod-cand-260809 DayOA 13.4.9 HG002 5x+5x HIOMR2 execution ledger

Created: `2026-08-10T01:41:44Z`

Ledger path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260810T014144Z_prod_cand_1349_hg002_5x5x_hiomr2_ledger.md`

Objective: On existing cluster `prod-cand-260809`, create a fresh `init-test`
analysis from exact annotated DayOA tag `13.4.9`; use the authoritative HG002
approximately-5x Illumina plus 5x ONT slim-data inputs; initialize DayOA in one
persistent `ubuntu` Bash-login tmux pane; dry-run the literal HIOMR2 kitchen-sink
mega closure plus Inflection analytical packaging with `-j 333 -p -T 1 -k -n`;
and, only if that exact plan is valid, repeat it with only `-n` removed.

## Gate 0 inventory freeze

- Execution repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch
  `260809-prod-candidate`, commit `aa15d5b45d9e2b0d68a76c21a729ed8f8cf8d995`.
  The worktree contains extensive pre-existing untracked plans and artifacts;
  this ledger is the only local file owned by this execution.
- Local DayOA evidence repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`,
  branch `260809-prod-candidate`, clean at commit
  `4b1fab794de95796235f16deb081c161cf021167`; private origin
  `git@github.com:lsmc-bio/daylily-omics-analysis.git`.
- Release identity: annotated tag object
  `185fba7e7844eadf0cf692d538c24af80e39874f` named `13.4.9`, peeled commit
  `4b1fab794de95796235f16deb081c161cf021167`.
- DYEC runtime: local and headnode `16.1.44`.
- Explicit AWS scope: profile `lsmc`, region `us-west-2`, cluster
  `prod-cand-260809`.
- Live cluster at `2026-08-10T01:42Z`: ParallelCluster `3.15.0`, cluster/stack
  `UPDATE_COMPLETE`, compute fleet `RUNNING`, headnode
  `i-0ee0f65150b39b976` / `ip-10-0-0-13`, Ubuntu `22.04.5`, `ubuntu` remote user.
- FSx at `2026-08-10T01:43Z`: `9,613,144,064 KiB` total,
  `9,613,033,984 KiB` available, `1%` used.
- Controller baseline: zero DayOA controllers, zero Slurm jobs, zero tmux panes,
  and no stale controller receipts.
- Canonical proposed analysis root:
  `/fsx/analysis_results/prod-cand-260809/init-test`. It must be proved absent
  before creation; no alternate root may be inferred.
- Stable identity: `DAYOA_AGENT_ID=codex-prod-cand-init-test-1349-20260810`,
  `DAYOA_AGENT_KIND=codex`, `DAYOA_HUMAN_REQUESTOR=jmajor`,
  `DAYOA_TMUX_SESSION=dayoa_init_test_hg002_5x5x_1349_20260810`, and
  `DAYOA_LEDGER_PATH` equal to this ledger path.
- The current DYEC catalog is validated at DayOA `13.4.9`. Its BJuice mega
  entry proves the core target family, but it is a full-coverage/SeqOne-v2
  contract and therefore cannot silently replace the user's slim-data plus
  analytical-package request. The exact tagged HG002 5x5x overlay and literal
  target closure will be validated in the clone.
- No Slurm administration, job/controller cancellation, lock takeover,
  destructive AWS action, export, teardown, or budget-cap change is authorized.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| RUN-001 | Contracts | Read DayOA, tmux, DYEC, analysis-lock, and ledger instructions | SUCCESS | active_product_contract | Gate 0 | orchestrator | Required instruction files and current DYEC help read before headnode writes |  | Supported execution boundary fixed |
| RUN-002 | Cluster/release | Verify live cluster, empty controller baseline, and exact annotated `13.4.9` identity | SUCCESS | config_or_startup_contract | Gate 0 | orchestrator | Cluster/headnode/FSx/controller JSON and local tag object/peeled commit recorded above |  | Live scope and immutable release proven |
| RUN-003 | Analysis root | Prove proposed root unused; record visit; acquire lock; create one-pane persistent tmux | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | Root and parent were absent; write visit recorded; lock acquired by `codex-prod-cand-init-test-1349-20260810`; one window/pane `%0` in `dayoa_init_test_hg002_5x5x_1349_20260810`; Bash flags include `i` and `login_shell=yes` |  | Fresh persistent execution boundary established as `ubuntu` |
| RUN-004 | Clone | Run `day-clone -t 13.4.9 -d init-test` and prove private origin, exact detached HEAD, annotated tag, and clean checkout | BLOCKED | config_or_startup_contract | Gate 1 | orchestrator | Main repository reached clean detached `HEAD=4b1fab794de95796235f16deb081c161cf021167`, private SSH origin, and exact annotated tag object `185fba7e...`; `day-clone` then failed twice cloning gitlink `b7d0964...` from `https://github.com/lsmc-bio/TrusSV.git` with `fatal: could not read Username for 'https://github.com': terminal prompts disabled` and returned `Error: Git clone failed with exit code 1.` | Tag `13.4.9` declares the new private TrusSV submodule over unauthenticated HTTPS, while the strict temporary DayOA deploy-key environment supports the catalog's SSH parent transport and no HTTPS credential or permitted URL rewrite is configured | Clone is partial and deliberately not accepted as a successful exact-tag workspace; requires an owner-approved transport/release correction |
| RUN-005 | Inputs | Prove exact regular HG002 approximately-5x ILMN and 5x ONT slim-data paths plus six-manifest identity/lineage closure | BLOCKED | active_product_contract | Gate 2 | orchestrator | Not attempted after RUN-004 hard failure | Exact-tag clone contract is incomplete | No manifests or inputs were staged or changed |
| RUN-006 | Initialization | Run separate `source dyoainit` and `dy-a slurm hg38` commands in the persistent pane | BLOCKED | config_or_startup_contract | Gate 2 | orchestrator | Not attempted after RUN-004 hard failure | Exact-tag clone contract is incomplete | No DayOA environment was initialized |
| RUN-007 | Dry run | Run exact literal kitchen-sink mega plus Inflection analytical package closure with `-j 333 -p -T 1 -k -n`; require RC 0 and inspect DAG/config/input/target closure | BLOCKED | contract_test | Gate 3 | orchestrator | No `dy-r` command was issued | Exact-tag clone contract is incomplete | No dry-run plan exists |
| RUN-008 | Live run | If RUN-007 is valid, repeat the identical command once with only `-n` removed and capture controller/queue evidence | BLOCKED | feature_implementation | Gate 4 | orchestrator | DYEC inventory at `2026-08-10T01:52:48Z`: zero controllers and zero Slurm jobs | Dry-run gate did not run because the clone failed | No live workflow was submitted |
| RUN-009 | Handoff | Record exact tmux, root, tag/commit, command, controller state, jobs, lock state, and objective boundary | SUCCESS | legitimate_safety_handling | Gate 5 | orchestrator | Partial checkout preserved at the exact root; one idle Bash tmux pane remains; owned write lock was released and verified `unlocked`; final DYEC inventory has zero controllers/jobs and one tmux pane |  | Blocker and untouched execution boundary recorded without destructive cleanup |

## Acceptance boundary

The requested launch is complete only when the clone, exact inputs/manifests,
dry-run plan, and live controller start are proven. A successful launch is not a
claim that the long-running workflow or Inflection package has completed.

## Evidence log

- `2026-08-10T01:42Z` to `01:43Z`: DYEC proved cluster, headnode, FSx, and
  empty controller/Slurm/tmux baseline.
- The proposed root and its cluster parent were absent. The root was created,
  visited, locked, and assigned one persistent interactive Bash-login tmux pane
  as `ubuntu` before `day-clone` was issued.
- `day-clone -t 13.4.9 -d init-test` cloned the main private repository and
  checked out the exact peeled commit, then failed its mandatory recursive
  submodule clone twice. `.gitmodules` at the tag explicitly records
  `url = https://github.com/lsmc-bio/TrusSV.git`; the gitlink remains
  uninitialized (`-b7d0964...`). No Git URL rewrite, credential fallback,
  skipped-submodule behavior, or partial-clone workflow launch was used.
- The write lock was released after the hard failure. At
  `2026-08-10T01:52:48Z`, DYEC reported zero controllers, zero Slurm jobs, no
  stale receipts, and the single idle tmux pane at the partial checkout.

## Final report

All rows terminal: `yes`

Objective complete: `no`

Status counts:

- SUCCESS: `4`
- BLOCKED: `5`

Changed local files:

- This execution ledger only.

Live effects:

- Created and preserved the partial analysis root and its one idle tmux pane.
- Submitted no workflow controller or Slurm job.
- Released the analysis write lock.

Unblock condition: provide an owner-approved exact authentication/transport
contract for the private TrusSV gitlink. Because `13.4.9` is immutable, the
clean source fix is normally a new DayOA patch tag whose `.gitmodules` uses the
supported authenticated transport and whose recursive `day-clone` is proven.
An exact-tag one-off URL/credential override would be fallback behavior and was
not attempted without explicit approval.

## 2026-08-10 durable repair amendment

The user explicitly resumed this ledger with the instruction to make the fix
durable across newly built clusters. The earlier terminal snapshot remains the
historical result for `13.4.9`; the rows below now control the replacement
release and resumed launch.

Fresh diagnosis changed the preferred repair. Merely rewriting the submodule
URL from HTTPS to SSH would still ask the repository-scoped DayOA deploy key to
authenticate to a second private repository. New headnodes intentionally
receive only the DayOA and DYEC deploy-key contracts, so that would preserve a
cross-repository bootstrap dependency instead of fixing it. The durable design
is to vendor the exact 28-file, GPL-3.0 TrusSV `v0.3.1` source tree into DayOA,
record its origin commit and Git tree object, and make the rule verify the
vendored tree from the enclosing exact-tag checkout. This keeps the bootstrap
fully satisfied by the existing DayOA deploy key and adds no credential or
transport fallback.

Frozen upstream identity:

- repository: `https://github.com/lsmc-bio/TrusSV.git`
- tag: `v0.3.1`
- commit: `b7d0964a0c55fa1ed720d3106c4db06826f8e73d`
- root tree: `a61c4dd11ad7cda765c407e3b3b5cfb558c273d9`
- tracked files: `28`
- license: `GPL-3.0-or-later`

| ID | Area | Requirement | Status | Category | Approval Gate | Evidence / terminal note |
|---|---|---|---|---|---|---|
| FIX-001 | Diagnosis | Freeze the actual new-headnode credential boundary and select a no-fallback source contract | SUCCESS | config_or_startup_contract | Repair Gate 0 | Parent deploy key cannot satisfy a second private repository; exact TrusSV commit/tree recorded above |
| FIX-002 | DayOA source | Replace the gitlink with the byte-identical vendored upstream tree plus a provenance receipt | SUCCESS | feature_implementation | Repair Gate 1 | Staged vendored path has 28 files and Git tree `a61c4dd...`, exactly matching upstream; `.gitmodules` removed |
| FIX-003 | DayOA contract | Verify the enclosing checkout's vendored tree object in the HIOMR2 rule and add focused regressions | SUCCESS | contract_test | Repair Gate 1 | Rule checks committed tree plus working-path cleanliness; focused NICU, Inflection, and SeqOne v2 suite passed 81/81 |
| FIX-004 | DayOA release | Test, commit, push, and publish a new immutable annotated patch tag | SUCCESS | release | Repair Gate 2 | Annotated `13.4.10` tag object `d7b1a14b...` peels to pushed commit `118f70f4...`; `13.4.9` was not moved |
| FIX-005 | DYEC release | Pin source and packaged catalogs to the replacement DayOA tag, test parity, self-pin, and publish a new immutable DYEC tag | IN_PROGRESS | release | Repair Gate 3 | Source/payload catalogs are being pinned to `13.4.10`; new clusters must receive the corrected catalog and bootstrap payload |
| FIX-006 | Candidate proof | Refresh `prod-cand-260809` through DYEC and prove the corrected exact-tag clone as `ubuntu` | PENDING | config_or_startup_contract | Repair Gate 4 | No manual URL rewrite or credential injection is allowed |
| FIX-007 | Resumed launch | Re-enter the locked `init-test` root, initialize separately, prove exact inputs/targets, dry-run with the requested flags, then remove only `-n` if valid | PENDING | feature_implementation | Repair Gate 5 | No controller is running at amendment time |

The earlier `All rows terminal: yes` and `Objective complete: no` statements
apply only to the stopped `13.4.9` attempt and are superseded for current work
by this amendment.
