# HG002 DayOA and DYEC Release Train Ledger

Created: `2026-07-27T00:31:34Z`

## Objective

Release the canonical HG002 informatics fixture mapping in DayOA, advance every
active DYEC DayOA command-catalog pin to that exact DayOA release, then cut a
second DYEC release whose active self-pin points at the intermediate DYEC
release.

## Gate 0: inventory freeze

- DayOA checkout:
  `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DayOA branch and baseline:
  `codex/preval-illumina-run-qc-sections` at `59df1ab3`, matching its remote
  before release work.
- DayOA latest remote numeric tag:
  `13.0.49` at `854e5123`, on the sibling
  `codex/hiomr2-artifact-preflight-20260726` lineage.
- DayOA release plan:
  commit the scoped HG002 fixture work, merge the latest `13.0.49` release
  commit without rewriting the published branch, test, and create annotated
  tag `13.0.50`.
- DYEC primary checkout:
  `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DYEC primary state:
  `jem-candidate-260725` at `1ab58bcb`, matching its remote but dirty with
  unrelated user-owned source, test, ledger, report, and runtime files.
- DYEC release worktree:
  `/tmp/dyec-hg002-release-20260727`
- DYEC release baseline:
  clean branch `codex/dyec-hg002-fixture-release-20260727` at latest annotated
  tag `14.0.20` (`b4f995ae`).
- DYEC baseline pins:
  all active DayOA catalog pins are `13.0.47`; active self-pin is `14.0.19`.
- DYEC release plan:
  annotated intermediate tag `14.0.21` pins DayOA `13.0.50`; annotated final
  tag `14.0.22` self-pins DYEC to `14.0.21`.
- No workflow, cluster, AWS, Dayhoff, Slurm, or deployment mutation is in scope.

## Control ledger

| ID | Repo | Requirement | Status | Category | Approval gate | Evidence | Root cause | Terminal note |
|---|---|---|---|---|---|---|---|---|
| REL-001 | DayOA | Complete focused and broad manifest validation for the HG002 owner-EUID mapping. | SUCCESS | contract_test | Gate 5 | Two offline six-manifest validations passed. Pre-merge suite: `142 passed`; post-merge suite: `143 passed`; `git diff --check` passed. |  | The stale source-string assertion was corrected to the current multiline assignment shape. |
| REL-002 | DayOA | Commit and push the HG002 fixture mapping and durable receipt. | SUCCESS | feature_implementation | Gate 5 | Commit `6c58fb05` (`Add canonical HG002 informatics fixture identities`) is included in pushed branch `codex/preval-illumina-run-qc-sections`. |  | Scoped fixture, receipt, ledger, and tests committed and pushed. |
| REL-003 | DayOA | Integrate the latest `13.0.49` release commit, retest, create annotated `13.0.50`, and push it. | SUCCESS | feature_implementation | Gate 5 | Merge commit `4e752669`; annotated tag `13.0.50` is a tag object, peels to `4e7526697d9d622c9bdb120f2b53e13412792797`, and is visible on origin. Branch divergence is `0 0`. |  | DayOA release complete. |
| REL-004 | DYEC | Advance all active and packaged DayOA catalog/test pins to exact tag `13.0.50`. | SUCCESS | config_or_startup_contract | Gate 4 | Both catalog copies and nine active contract-test files use exact `13.0.50`; both catalog copies are byte-identical; highest-release commit is `4e7526697d9d622c9bdb120f2b53e13412792797`. |  | No range, maximum, or fallback pin was introduced. |
| REL-005 | DYEC | Test, commit, push, and create annotated intermediate tag `14.0.21`. | SUCCESS | contract_test | Gate 5 | `source ./activate`; focused DYEC suite: `366 passed`; commit `2c154773`; annotated tag `14.0.21` is a tag object, peels to `2c154773817f089787b5dc82f90f6debbfc4a728`, and is visible on origin; branch divergence `0 0`. |  | Intermediate DayOA-pin release complete. |
| REL-006 | DYEC | Advance both active and packaged DYEC self-pins plus tests to `14.0.21`. | SUCCESS | config_or_startup_contract | Gate 4 | Both `daylily_cli_global.yaml` copies and `DYEC_BLESSED_TAG` now use exact `14.0.21`; config copies are byte-identical. |  | The final `14.0.22` release will intentionally self-pin to the immediately preceding `14.0.21` release. |
| REL-007 | DYEC | Retest, commit, push, and create annotated final tag `14.0.22`. | SUCCESS | contract_test | Gate 5 | Repeated focused suite: `366 passed`; critical Ruff selectors passed; compileall and `git diff --check` passed. Commit `3874501c`; annotated tag `14.0.22` is a tag object, peels to `3874501c8f4c54cc8ef13e2596a4c29acab3f2c4`, and is visible on origin. |  | Final self-pin release complete. |
| REL-008 | Remote acceptance | Verify all three tags are annotated, peel to the intended commits, exist on origin, and leave release branches clean and synchronized. | SUCCESS | contract_test | Gate 5 | `13.0.50`, `14.0.21`, and `14.0.22` each return `tag` from `git cat-file -t`; origin advertises each tag object and peeled commit. Both release branches reported divergence `0 0` after their release pushes. |  | All requested release tags are published and immutable. |

## Acceptance

- DayOA `13.0.50` contains the real Bloom-issued HG002 specimen, sample, and
  library EUID mapping, fixture receipt, and regression test.
- Every active DYEC DayOA command uses exact tag `13.0.50`; no bounded or
  maximum-version interpretation is introduced.
- DYEC `14.0.21` contains the DayOA pin, while DYEC `14.0.22` contains a
  self-pin to exact tag `14.0.21`.
- Live and packaged config copies match.
- All three remote tags are immutable annotated tag objects.
- Unrelated changes in the primary DYEC checkout remain untouched.

## Terminal report

- Status counts: `SUCCESS=8`.
- All rows are terminal and the objective is complete.
- DayOA release: `13.0.50` -> `4e7526697d9d622c9bdb120f2b53e13412792797`.
- DYEC DayOA-pin release: `14.0.21` ->
  `2c154773817f089787b5dc82f90f6debbfc4a728`.
- DYEC self-pin release: `14.0.22` ->
  `3874501c8f4c54cc8ef13e2596a4c29acab3f2c4`.
- DYEC `14.0.22` contains exact DayOA pin `13.0.50` and exact DYEC self-pin
  `14.0.21`.
- The primary dirty DYEC checkout was not edited, staged, committed, or
  cleaned by this release train.
