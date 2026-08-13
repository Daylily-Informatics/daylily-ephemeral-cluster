# DYEC 17.0.3 HG002 5x+5x HIOMR2 BJuice launch ledger

Created: `2026-08-13T10:41:18Z`

## Objective

Use the immutable DYEC `17.0.3` command-catalog entry
`inflection-bjuice-product-v0.2` to run the receipt-bound HG002 approximately
5x Illumina plus 5x ONT HIOMR2 slim kitchen-sink mega and analytical
Inflection packaging command on `hg38`. Launch a fresh dry lane with
`-j 333 -T 0 -p -n`, explicitly without `-k`; inspect its terminal receipt and
plan; and only if it succeeds, launch a fresh live lane from the same immutable
catalog snapshot with the catalog's sole dry-run flag `-n` removed.

If the immutable catalog contract is incorrect, stop before live workflow
launch, repair and release DayOA, pin that exact release in corrected source
and packaged catalogs, validate them, and create a new non-`v` annotated DYEC
release. Do not move or edit the `17.0.3` snapshot. The corrected dry and live
lanes must use the new immutable DYEC version.

No export, deletion, cluster teardown, Slurm intervention, budget-cap change,
or customer-release identity registration is in scope.

## Gate 0 inventory freeze

- Controlling ledger: this file.
- Local repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`,
  branch `codex/local-dyec-17.0.3`, exact annotated tag `17.0.3`, peeled commit
  `532ba64836067912e2269d603477465cfa983e76`.
- Worktree boundary: zero tracked modifications and extensive pre-existing
  untracked user artifacts. This ledger is the only local file owned by this
  execution; unrelated paths will not be edited, staged, or removed.
- Repair worktree: isolated
  `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-17.0.4-hiomr2-slim-jasmine`
  on `codex/dyec-17.0.4-hiomr2-slim-jasmine`, created clean from exact
  annotated DYEC `17.0.3` release commit
  `532ba64836067912e2269d603477465cfa983e76`. The controlling ledger was moved
  into this worktree so it can be committed with the corrected release; the
  dirty primary checkout remains otherwise untouched.
- Activated runtime: `dyec --json version` reports `17.0.3`; local catalog
  snapshot `--dyec-version 17.0.3` is catalog schema 6 and pins exact annotated
  DayOA tag `14.0.4`.
- Catalog command: `inflection-bjuice-product-v0.2`, resolved as the same-build
  analytical-package alias of `hiomr2_slim_kitchensink_mega`.
- Exact targets: `produce_sentdhiomr2_slim_kitchensink_mega` and
  `produce_sentdhiomr2_inflection_analytical_package`.
- Exact command contract: `DAY_CONTAINERIZED=true`, `hg38`, checked-in overlay
  `config/hg002_bjuice_5x5x_hiomr2.yaml`, HIOMR2 scope `19-20`,
  `-j 333 -T 0 -p --rerun-triggers mtime`, no `-k`; the dry command adds only
  terminal `-n`. DYEC additionally requests the analysis-artifact manifest and
  rulegraph.
- Input fixture:
  `/Users/jmajor/.config/daylily/resources/17.0.3/examples/staging/hg002_bjuice_verified_5x5x_fastq`.
  The six-manifest validator passed with foreign keys and ordered inputs valid,
  no network access, and no identity creation/rewriting. The fixture records
  ILMN depth `5.862704556x` and ONT depth `4.794169766x`; full-coverage inputs
  are forbidden substitutions. Its `Z-` identities are test-only and the unit
  is not customer-release eligible.
- Catalog validation: source and packaged catalogs are byte-identical;
  `tests/test_repository_catalog_aliases.py`,
  `tests/test_hg002_bjuice_5x5x_catalog_fixture.py`, and
  `tests/test_dayoa12_manifest_contract.py` passed `26/26`.
- DayOA repair release: exact annotated `14.0.6` tag object
  `7cd3bae983fcd2c8e9137c8220f6629fc3036660` peels locally and remotely to
  `105344052a71576588dbc3b6f37258eb2c6d2623`. Its two-line strict gate makes
  `hiomr2_jasmine_rtg_applicable()` return false before Truvari/RTG mode
  resolution when the explicit Jasmine switch is false. The focused adjacent
  suite passed `64`, the full suite passed `1675` with one expected skip, and
  the exact-version sdist/wheel checks passed.
- DYEC repair baseline: source/package catalogs were byte-identical and 82
  focused catalog, fixture, repository, and packaged-default tests passed
  before edits. Immutable `17.0.3` raw block SHA-256 is
  `a36b3eabdd4c3d6e8d22cca31543b739b2ab63ef556e4c7390ec9b657390d243`.
- DYEC repair candidate: active defaults and `current` now pin only exact
  DayOA `14.0.6`; new snapshot `17.0.4` equals `current`; every older snapshot,
  including `17.0.3` on DayOA `14.0.4`, is preserved. The resolved 17.0.4
  alias retains both requested targets, `hg38`, scope `19-20`,
  `-j 333 -T 0 -p`, no `-k`, and a dry command differing only by terminal
  `-n`. The expanded focused repair suite passed `364` tests.
- Candidate clusters: `prod-cand-1703` remains `CREATE_IN_PROGRESS` and is not
  runnable. `prod-cand-260809` is `UPDATE_COMPLETE`, compute fleet `RUNNING`,
  Ubuntu headnode `i-0ee0f65150b39b976` / `ip-10-0-0-13`, installed DYEC
  `17.0.3`, FSx `16%` used with `8,142,572,032 KiB` available.
- Workload baseline at `2026-08-13T10:38:46Z`: authoritative inventory reports
  zero DayOA controllers and zero Slurm jobs. Existing idle tmux sessions and
  stale receipts are foreign and will not be modified.
- Project / cost center: `prod-cand-260809` / `prod-cand-260809`; strict live
  validation explicitly listed project `prod-cand-260809` for `ubuntu`. The
  first dry attempt used `RnD` and failed before `dy-r` with controller RC `3`;
  that failed root is preserved and not reused, replaced, or deleted. The cost
  center is active, allows `ubuntu`, and has monthly cap `$900`. The corrected
  dry controller's
  strict live project check reported `$878.221` used (`97.58%`) against that
  cap. Admission must fail closed if the live freshness/budget gate rejects
  it; no cap change or budget bypass is authorized.
- AWS scope: profile `lsmc`, region `us-west-2`, cluster
  `prod-cand-260809`, executing entity `prod-cand-260809`, remote user
  `ubuntu`.
- Dry attempt 1 analysis / tmux:
  `hiomr2-bjuice-hg002-5x5x-1703-dry-20260813` /
  `hiomr2_bjuice_1703_dry_20260813`; terminal RC `3`, zero Slurm jobs, invalid
  explicit project `RnD`.
- Corrected dry analysis / tmux:
  `hiomr2-bjuice-hg002-5x5x-1703-dry2-20260813` /
  `hiomr2_bjuice_1703_dry2_20260813`; terminal controller RC `2`, zero Slurm
  jobs, exact Snakemake log
  `.snakemake/log/2026-08-13T104640.390589.snakemake.log`. DAG construction
  failed because the slim target's shared QC/report closure reached
  `sentdhiomr2_jasmine_integrated` while the shipped overlay explicitly sets
  `sentdhiomr2_jasmine.enabled: false`.
- The originally rendered `17.0.3` live lane was never launched and is
  superseded by the versioned repair.
- Corrected 17.0.4 dry analysis / tmux:
  `hiomr2-bjuice-hg002-5x5x-1704-dry-20260813` /
  `hiomr2_bjuice_1704_dry_20260813`.
- Corrected 17.0.4 live analysis / tmux:
  `hiomr2-bjuice-hg002-5x5x-1704-live-20260813` /
  `hiomr2_bjuice_1704_live_20260813`.
- Payload relays are separate explicit prefixes under
  `s3://lsmc-dayoa-control-data-usw2/dayoa_input_manifests/prod-cand-260809/`;
  DYEC will not delete relay objects automatically.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| CAT-001 | Catalog | Prove immutable `17.0.3` resolves the requested HG002 5x+5x analytical command with exact flags and no `-k` | SUCCESS | contract_test | Gate 0 | orchestrator | `catalog show/list --dyec-version 17.0.3`, source/package `cmp`, manifest validation, and focused `26 passed` |  | Command, tag, targets, fixture, scope, and flags are correct. |
| CAT-002 | Conditional repair | If CAT-001 is wrong at authoritative runtime, repair, validate, and publish new immutable DayOA and DYEC versions before live launch | ATTEMPTING_BUGFIX | plan_amendment | Gate 2 | orchestrator | Corrected dry2 RC `2`; exact DAG failure says `sentdhiomr2_jasmine.enabled must be true for Jasmine targets`; zero Slurm jobs | Static catalog and slim-rule source tests did not exercise the transitive QC/report DAG while Jasmine is explicitly disabled | Preserve `17.0.3` and DayOA `14.0.4`; release corrected successors. |
| RUN-001 | Dry render | Render a fresh dry catalog launch with explicit snapshot, inputs, cluster, project, cost center, user, session, and relay | SUCCESS | contract_test | Gate 1 | orchestrator | Immutable `17.0.3` dry/live renders resolved DayOA `14.0.4`; after normalizing the separate lane IDs, the DayOA commands differ only by `-n`; both have `-j 333 -T 0 -p`, no `-k`, and explicit relay/session/root values |  | Both de novo lane argv are fixed before launch. |
| AMEND-001 | Launch envelope | Correct the explicit DayOA project from invalid `RnD` to the live-authorized `prod-cand-260809` value without changing the catalog command | SUCCESS | plan_amendment | Gate 1 | orchestrator | Attempt 1 controller RC `3`; controller log says `Project 'RnD' is not valid for user 'ubuntu'` and lists `prod-cand-260809`; zero Slurm jobs and no attributable Snakemake log |  | Use a fresh dry2 root; preserve the failed attempt unchanged. |
| RUN-002 | DYEC 17.0.3 dry launch | Launch the exact catalog dry lane and require terminal controller RC 0 with a bounded valid plan and zero live Slurm work | FAIL | contract_test | Gate 1 | orchestrator | Dry2 controller RC `2`; manifest hashes, strict project, budget check, `dyoainit`, and `dy-a slurm hg38` passed; DAG construction failed; zero Slurm jobs | Slim kitchen-sink transitively requests disabled Jasmine through the shared QC/report closure | This immutable version cannot satisfy the requested command. No live 17.0.3 lane was launched. |
| DAYOA-001 | DayOA repair | Make the slim kitchen-sink reporting closure explicitly exclude disabled Jasmine dependencies and add a transitive regression test | SUCCESS | feature_implementation | Gate 2 | orchestrator | Behavioral test failed before the fix and passed after it; adjacent suite `64 passed`; full suite `1675 passed, 1 skipped` | Jasmine RTG applicability ignored the explicit disabled-Jasmine switch | Added a strict two-line route gate; no fallback or config default changed. |
| DAYOA-002 | DayOA release | Validate, commit, push, and create a new non-`v` annotated DayOA release without moving prior tags | SUCCESS | feature_implementation | Gate 3 | orchestrator | Release commit `105344052a71576588dbc3b6f37258eb2c6d2623`; annotated tag object `7cd3bae983fcd2c8e9137c8220f6629fc3036660`; local/remote peeled refs match |  | DayOA `14.0.6` and its dedicated branch are published; prior tags are unchanged. |
| DYEC-001 | Catalog repair | Pin the corrected exact DayOA release in a new immutable DYEC catalog snapshot and preserve the exact requested argv contract | SUCCESS | feature_implementation | Gate 3 | orchestrator | Source/package parity; current equals `17.0.4`; historical `17.0.3` hash frozen; resolved catalog show/render pins 14.0.6; normalized dry/live renders differ only by lane ID and dry-only `-n`; expanded focused suite `364 passed` |  | Active/current pins changed; older snapshots remain immutable. Both renders have `-j 333 -T 0 -p` and no `-k`. |
| DYEC-002 | DYEC release | Validate source/package parity, commit, push, and create a new non-`v` annotated DYEC release | IN_PROGRESS | feature_implementation | Gate 3 | orchestrator | Focused suite `364 passed`; complete suite `2515 passed, 11 skipped`; focused Ruff, compileall, catalog/model equality, and `git diff --check` passed; clean pretag wheel/sdist and `twine check` passed; commit, tag, and remote proof pending |  | The 11 skips are the explicit opt-in live staging scenarios. |
| BUILD-001 | Artifact hygiene | Exclude locally generated bytecode from DYEC package artifacts | SUCCESS | contract_test | Gate 3 | orchestrator | First pretag wheel inspection found compileall-generated payload `__pycache__`; only generated caches/build state were removed, then a bytecode-disabled rebuild produced zero `.pyc`/`__pycache__` members; wheel SHA-256 `ac01371241435856a71c0bd56f6a66cad3e25c18ac7b876446eb19b65872b6b5`, sdist SHA-256 `d35131a743704a8c0f3879ccc7c7b4de9e508b770bf4f4c3b478b187914fe03f` | Compileall traversed Python files inside the package-data payload before the first build | Clean rebuild has exact 17.0.4 metadata, byte-identical embedded catalog, and passing `twine check`. |
| HEADNODE-001 | Runtime refresh | Refresh `prod-cand-260809` to the corrected DYEC release and prove installed DYEC and pinned DayOA versions | OPEN | feature_implementation | Gate 4 | orchestrator | Pending |  |  |
| RUN-003 | Corrected dry launch | Launch a fresh dry lane from the corrected immutable catalog and require terminal controller RC 0 with a bounded valid plan and zero live Slurm work | OPEN | contract_test | Gate 4 | orchestrator | Pending |  |  |
| RUN-004 | Live launch | Only after RUN-003 succeeds, launch the fresh live catalog lane with `-n` removed and no other command-contract change | OPEN | feature_implementation | Gate 4 | orchestrator | Pending |  |  |
| RUN-005 | Launch proof | Record exact DayOA/DYEC tags and commits, analysis root, tmux, lock/controller receipt, and initial Slurm/controller state | OPEN | legitimate_safety_handling | Gate 5 | orchestrator | Pending |  |  |

## Acceptance boundary

This request is complete when corrected DayOA and DYEC versions are released,
the corrected dry lane terminates successfully, the live lane is launched from
that new immutable catalog with no `-k` and only `-n` removed from the DayOA
command, and the live controller/queue state is captured. A successful launch
is not a claim that the long-running workflow or Inflection package has
completed.

## Final report

All rows terminal: `no`

Objective complete: `no`

Current counts: `SUCCESS=7`, `ATTEMPTING_BUGFIX=1`, `IN_PROGRESS=1`, `OPEN=4`,
`FAIL=1`, `BLOCKED=0`.
