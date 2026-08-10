# Chr5 proof -> DayOA/DYEC release train -> chr19-20 validation ledger

Created: `2026-08-10T10:40:00Z`

## Objective

After the existing `init-test-chr5` DayOA `13.4.11` workflow reaches an
attributable controller RC `0`, publish the complete intended DayOA repair as
the next immutable annotated DayOA patch tag. Then advance DYEC through the
normal two-release sequence: first pin the new DayOA tag and publish the next
DYEC tag; next update DYEC's self-pin to that intermediate tag and publish the
following DYEC tag. Finally, use the final DYEC release on
`prod-cand-260809` to create `test-chr19and20` at the new DayOA tag and run the
catalogued HIOMR2 kitchen-sink mega plus Inflection packaging command through
dry-run and live execution to attributed RC `0`.

Existing controllers, Slurm jobs, and unrelated analyses remain outside this
ledger's mutation scope.

## Gate 0 baseline

- Current workflow root:
  `/fsx/analysis_results/prod-cand-260809/init-test-chr5`
- Current controller:
  `dayoa_init_test_chr5_hg002_5x5x_13411_live_20260810`, PID `713263`
- Current DayOA release: annotated tag `13.4.11`, commit
  `287923d167ca0ef6b05cb4469e290ade45f4852b`
- Latest observed controller state: `RUNNING`, `259 of 288` steps (`90%`), no
  terminal RC. Exact attributed logs contain a failed
  `sentdhiomr2_nicu_trussv` compile attempt: `src/svtype.cpp` uses `strlen`
  without including `<cstring>`. Under `-k`, remaining independent work is
  still running; no repair or rerun is authorized until the controller reaches
  a terminal nonzero RC.
- DayOA local checkout:
  `/Users/jmajor/projects/lsmc/daylily-omics-analysis`, branch
  `codex/vendor-trussv-13.4.10`, clean at `13.4.11` before the pending repair.
- DYEC local checkout:
  `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch
  `codex/pin-dayoa-13.4.10-16.1.45`, HEAD/tag `16.1.58`. The worktree contains
  extensive pre-existing untracked user artifacts which are not release scope.
- Current intended DYEC catalog edits are limited to the source and packaged
  `daylily_pipeline_command_catalog.yaml` copies. Both named HIOMR2+Inflection
  entries pass the nested override
  `sentdhiomr2={"hg38_sentdhiomr2_chrms":"19-20"}` in live and dry commands.
  Operator text states that full production scope is numeric `1-25`, where
  `23=X`, `24=Y`, and `25=M/MT` is resolved from the reference FAI.
- Version numbers are not reserved at Gate 0. Recompute the highest immutable
  remote semver tag immediately before each release so concurrent release work
  is never overwritten or shadowed.

## Control ledger

| ID | Gate | Requirement | Status | Evidence / terminal note |
|---|---|---|---|---|
| REL-001 | Current live proof | Exact `init-test-chr5` controller reaches attributed RC `0`; if terminal RC is nonzero, diagnose and apply only the minimal safe repair under the analysis-root lock, dry-run, then continue in a new tmux controller | SUCCESS | Exact live successor `dayoa_init_test_chr5_hg002_5x5x_comparisonfix_live_20260810` reached attributed RC `0`. Verified TrusSV VCF/TBI, all four comparison outputs plus marker, NICU artifact manifest/marker, analytical Inflection package manifest, final MultiQC, and one-row scope BED exactly `chr5 0 181538259`. |
| REL-002 | DayOA scope | Inventory all intended DayOA tracked/submodule changes and exclude unrelated files | SUCCESS | Clean feature branch equals remote at `e97960cf`; delta from `13.4.11` is exactly three repair commits and six intended files: TrusSV source/receipt, NICU rule/helper, and their two tests. |
| REL-003 | DayOA validation | Run focused and proportionate DayOA tests for every released change | SUCCESS | Consolidated Inflection, NICU manifest/rules/SV, and SeqOne v2 suite: `81 passed`; C++17 syntax check and `git diff --check` passed. |
| REL-004 | DayOA release | Commit and push the intended DayOA change set, then create/push the next annotated non-v semver tag and verify remote tag object/peeled commit | SUCCESS | Feature branch pushed through `e97960cf55d2cb5dfa76738515349c9d79b87c08`; annotated `13.4.12` pushed. Remote tag object `2bc53f36f53c5ca46f3348cd266032ad4731500d`, peeled commit `e97960cf55d2cb5dfa76738515349c9d79b87c08`. |
| REL-005 | DYEC DayOA pin | Update every live and packaged DayOA pin plus contract tests to the new DayOA tag | SUCCESS | Every source/payload catalog `default_ref`, `validated_version`, and command `git_tag` plus all active contract-test expectations now use DayOA `13.4.12`; no active `13.4.11` pin remains. |
| REL-006 | DYEC catalog | Validate source/payload catalog parity and both chr19-20 live/dry commands, including exact nested scope override and numeric full-scope guidance | SUCCESS | Source and payload catalogs are byte-identical. Both named entries carry the exact nested `19-20` override in live and dry commands and document full numeric `1-25`; the combined catalog, pin, payload, CLI-registry, manifest, sample-stats, and test-runner suite passed `338/338`. |
| REL-007 | DYEC intermediate release | Commit/push the DayOA-pin and catalog release, create/push the next annotated DYEC tag, and verify remote provenance | OPEN | Pending |
| REL-008 | DYEC self-pin | Advance every live and packaged DYEC self-pin to REL-007's tag; rerun focused tests | OPEN | Pending |
| REL-009 | DYEC final release | Commit/push the self-pin, create/push the following annotated DYEC tag, and verify clean remote state | OPEN | Pending |
| REL-010 | Fresh test boundary | Prove `/fsx/analysis_results/prod-cand-260809/test-chr19and20` and the planned tmux names are absent; preserve all other controllers/jobs | OPEN | Pending |
| REL-011 | Exact-tag clone/dry run | With final DYEC, use supported DYEC CLI launch to clone the new DayOA tag into `test-chr19and20`, stage the catalog's exact six-manifest fixture, and run its exact dry command to RC `0`; prove the rendered scope BED contains only chr19 and chr20 | OPEN | Pending |
| REL-012 | Live chr19-20 run | Remove only `-n`, run the identical catalog command in a new persistent tmux controller, and monitor only that controller to attributed RC `0` | OPEN | Pending |
| REL-013 | Final report | Report exact DayOA/DYEC commits and annotated tags, remote verification, catalog command, analysis root, tmux/controller, scope evidence, RC, outputs, and any remaining caveats | OPEN | Pending |

## Release order contract

1. Current chr5 workflow RC `0`.
2. DayOA change commit -> branch push -> annotated DayOA tag -> tag push.
3. DYEC DayOA pin/catalog commit -> branch push -> annotated intermediate DYEC
   tag -> tag push.
4. DYEC self-pin commit -> branch push -> annotated final DYEC tag -> tag push.
5. Final-DYEC exact-new-DayOA-tag chr19-20 dry run -> live run -> attributed
   RC `0`.

At every release step, commit before tagging, never move an existing tag, and
verify both the tag object and the exact remote ref after push.

## Execution log

- `2026-08-10T10:45Z`: the existing thread heartbeat was updated in place; no
  second monitor was created. It remains scoped to this ledger, the current
  `init-test-chr5` controller, and later only the explicitly named
  `test-chr19and20` successor.
- `2026-08-10T10:45Z`: DYEC focused catalog/payload/pin tests passed:
  `50 passed in 8.58s`.
- `2026-08-10T10:45:46Z`: exact current controller still `RUNNING`; `265` of
  `288` steps finished, three attributed Slurm jobs running, and the previously
  diagnosed TrusSV compile failure remains the only attributed failure marker.
  No repair, commit, push, or tag action has started.
- `2026-08-10T10:48:38Z`: exact controller still `RUNNING`; `271` of `288`
  steps finished (`94%`). One attributed job remains running. TrusSV job `164`
  has exhausted its attempts and remains the only failure marker, but the
  controller has not emitted a terminal RC, so the repair gate remains closed.
- `2026-08-10T11:08Z`: exact controller `status.json` reached terminal `FAILED`
  with RC `1`. The exact TrusSV rule log reports only the standard C++17
  compile error that `strlen` is undeclared and requires `<cstring>`.
- `2026-08-10T11:17Z`: acquired the exact analysis-root write lock without
  takeover. Added `<cstring>`, recorded the downstream vendoring patch and new
  vendored tree `6944f4c6425e751aa4b9d301fc88c8cac15bcc71`, updated the rule pin and
  focused test, and created local, unpushed DayOA fix commit
  `0bae7cd941294de9964cc2fceff9e098d3d51a8e`. Focused DayOA tests passed
  `38/38`, and `g++ -std=c++17 -fsyntax-only` passed. The identical commit was
  transported through the supported DYEC headnode upload relay and checked out
  cleanly in the analysis; unrelated untracked workflow artifacts were
  preserved.
- `2026-08-10T11:22Z`: exact continuation dry controller
  `dayoa_init_test_chr5_hg002_5x5x_trussvfix_dry_20260810` reached attributed
  RC `0`, submitted zero jobs, and planned 14 jobs: TrusSV plus only its
  downstream comparison, package, report, evidence, and target aggregation
  chain. No completed upstream caller or HIOMR2 rule was selected.
- `2026-08-10T11:26Z`: launched the mechanically identical live successor
  `dayoa_init_test_chr5_hg002_5x5x_trussvfix_live_20260810` with only `-n`
  removed. Exact status attributes controller PID `903475` and Snakemake log
  `2026-08-10T112601.791075.snakemake.log`; TrusSV external job `462` is the
  only submitted job and is `CONFIGURING`. No scheduler or node action was
  taken.
- `2026-08-10T11:31Z`: that successor terminated with attributed RC `1` after
  TrusSV compiled and linked successfully. The exact rule log stopped at the
  next assertion; direct reproduction proved the rendered regex
  `0\\.3\\.1` rejects `TrusSV 0.3.1`, while `0\.3\.1` accepts it. No tag was
  created. The already-created compilation-fix commit `0bae7cd9` had been
  pushed to the feature branch immediately before this terminal evidence was
  noticed.
- `2026-08-10T11:35Z`: fixed the version assertion, added a functional grep
  regression check, passed the focused DayOA suite `38/38`, committed as
  `1db34bb8938e1d9d1967a841ed7793b182bd9d95`, and pushed the feature branch.
  Transported the exact commit through DYEC, checked it out under the exact
  analysis write lock, and released the lock before controller launch.
- `2026-08-10T11:42Z`: exact dry session
  `dayoa_init_test_chr5_hg002_5x5x_trussv_versionfix_dry_20260810` reached
  attributed RC `0`, submitted zero jobs, and again selected only 14 TrusSV
  and downstream jobs.
- `2026-08-10T11:45Z`: launched live successor
  `dayoa_init_test_chr5_hg002_5x5x_trussv_versionfix_live_20260810` with only
  `-n` removed. Exact status attributes PID `958968` and Snakemake log
  `2026-08-10T114536.217984.snakemake.log`; TrusSV external job `464` is
  `CONFIGURING`. No Slurm or node action was taken.
- `2026-08-10T11:50Z`: exact TrusSV rule completed successfully: loaded
  `32,226` variants, formed `19,392` clusters, wrote/indexed `19,392` merged
  variants, and published the VCF plus TBI. The same controller later ended
  RC `1` in downstream `sentdhiomr2_nicu_comparison`; its exact log reports
  `missing=[] extra=['trussv']`, proving that the workflow passed the intended
  fourth lane but the shared helper still required exactly three.
- `2026-08-10T12:02Z`: implemented the exact four-lane comparison/topology
  contract, added functional four-lane tests, passed `62/62`, committed/pushed
  `e97960cf55d2cb5dfa76738515349c9d79b87c08`, and imported that exact commit
  under the analysis write lock.
- `2026-08-10T12:05Z`: comparison-fix dry session
  `dayoa_init_test_chr5_hg002_5x5x_comparisonfix_dry_20260810` reached
  attributed RC `0`, submitted zero jobs, and selected exactly 13
  comparison/downstream jobs; completed TrusSV was not selected.
- `2026-08-10T12:08Z`: launched live successor
  `dayoa_init_test_chr5_hg002_5x5x_comparisonfix_live_20260810` with only `-n`
  removed; exact controller PID `987385`. No other controller, scheduler job,
  or node was modified.
- `2026-08-10T12:20Z`: exact comparison-fix successor reached attributed RC
  `0`. Verified nonempty TrusSV VCF/TBI; source-support, four-lane concordance,
  BND topology, CNV/SV concordance and comparison marker; NICU experimental
  artifact manifest/marker; analytical Inflection package manifest; and final
  MultiQC. The scope BED contains exactly `chr5\t0\t181538259`. REL-001 is
  terminal `SUCCESS`; release validation is now active.
- `2026-08-10T12:24Z`: consolidated DayOA focused suite passed `81/81`; clean
  six-file release delta and remote-synchronized feature branch verified.
  Recomputed remote tags (`13.4.11` highest), created/pushed annotated DayOA
  `13.4.12`, and verified remote tag object
  `2bc53f36f53c5ca46f3348cd266032ad4731500d` peels to
  `e97960cf55d2cb5dfa76738515349c9d79b87c08`.
- `2026-08-10T12:32Z`: advanced every live, packaged, and tested DayOA pin to
  `13.4.12`, preserved byte-identical source/payload catalogs, and verified the
  exact `19-20` nested scope override plus numeric `1-25` production guidance.
  The combined focused DYEC suite passed `338/338`; REL-005 and REL-006 are
  terminal `SUCCESS`.
