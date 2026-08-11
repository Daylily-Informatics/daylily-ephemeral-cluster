# Prod-candidate-260911 DayOA and DYEC release-train ledger

Controlling request: reconcile the already merged DayOA and DYEC releases to
`main`; create `prod-candidate-260911` from each exact merged main commit; cut
the next DayOA release; then cut one DYEC release that pins that DayOA release,
removes the static DYEC self-pin, and makes `dyec_builds.current` the default
command-catalog view.

Controlling plan: this file.

Ledger path:
`docs/plans/20260811T160924Z_prod_candidate_260911_release_train_ledger.md`.

## Gate 0 inventory freeze

- DayOA repository/worktree:
  `/Users/jmajor/projects/lsmc/.codex-worktrees/dayoa-prod-candidate-260911`,
  branch `prod-candidate-260911`, clean at
  `a6a7cd493eecd51e9e942215414a1822510cffa9` (`origin/main`, annotated
  `13.4.31`).
- DYEC repository/worktree:
  `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-prod-candidate-260911`,
  branch `prod-candidate-260911`, clean at
  `cd41cd510c6ca60073006b3ed79f3251899db298` (`origin/main`, annotated
  `16.1.84`).
- Merge evidence: DayOA PR #103 merged to `main` at the DayOA baseline above;
  DYEC PR #95 merged to `main` at the DYEC baseline above.
- Remote inventory: `prod-candidate-260911`, DayOA `13.4.32`, DYEC `16.1.85`,
  and DYEC `16.1.86` were all absent before creation. The final amended train
  uses only DYEC `16.1.85`; `16.1.86` is not planned.
- Version sequence after both amendments below: DayOA `13.4.33` -> one DYEC
  `16.1.85` release. Historic catalog snapshots `16.1.81` and `16.1.82` must
  remain semantically unchanged.
- Current live pins before edits: current DayOA command rows and the immutable
  `16.1.82` catalog build use `13.4.31`; source and packaged global DYEC
  bootstrap configs contain redundant static self-pins to `16.1.82`.
- Baseline focused DYEC suite:
  `python -m pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py tests/test_tests_runner.py tests/test_cli_registry_v2.py tests/test_packaged_defaults.py tests/test_hiomrs_command_catalog.py tests/test_dayoa12_manifest_contract.py tests/test_command_sample_stats.py -q`
  -> `343 passed, 1 failed`. The pre-existing failure is
  `test_root_json_is_global_for_info`: its test constant still expected DayOA
  `13.4.30` while the merged catalog returned `13.4.31`.
- No workflow, AWS, cluster, Slurm, analysis-root, or destructive action is in
  scope. No unrelated dirty checkout is used by this release.

## Plan amendment

The first DayOA candidate commit and annotated tag `13.4.32` were pushed, but
the pre-commit `git diff --cached --check` had reported a trailing blank line
and the shell continued. The published tag is immutable and was not moved.
The formatting-only correction advances the usable DayOA release to
`13.4.33`; every downstream DYEC pin in this ledger therefore targets
`13.4.33`. Tag `13.4.32` remains preserved and explicitly superseded.

The owner then removed the two-stage DYEC requirement. DYEC headnode
configuration must derive the exact non-v release reported by the running
`dyec --version`, install that tag, and fail unless the headnode reports the
same version. The static source/package self-pin keys and the public
`headnode configure --dyec-version` override are removed, so no follow-up
self-pin release exists.

The command-catalog contract is also amended to version 5. Every default
catalog list/show/render/launch path resolves `dyec_builds.current`; numeric
snapshots are used only when an operator explicitly supplies
`--dyec-version`. At release creation, `current` is copied once to the new
numeric key (`16.1.85` here), and existing numeric snapshots are immutable.

## Control ledger

| ID | Area/repo | Requirement | Status | Category | Approval gate | Owner | Evidence | Root cause | Terminal note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Cross-repo | Freeze exact merged/tagged baselines, dirty state, remote targets, and focused test baseline. | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 inventory above. |  | Exact source and remote boundaries recorded before release edits. |
| MERGE-001 | DayOA | Merge the DayOA source consumed by DYEC `16.1.84` to `main`. | SUCCESS | feature_implementation | Gate 5 | orchestrator | PR #103; `origin/main=a6a7cd493eec...`; annotated `13.4.31` peels to that commit. |  | Requested merge was already complete when this task began. |
| MERGE-002 | DYEC | Merge DYEC `16.1.84` to `main`. | SUCCESS | feature_implementation | Gate 5 | orchestrator | PR #95; `origin/main=cd41cd510c6c...`; annotated `16.1.84` peels to that commit. |  | Requested merge was already complete when this task began. |
| BRANCH-001 | DayOA | Create `prod-candidate-260911` from exact `origin/main`. | SUCCESS | feature_implementation | Gate 1 | orchestrator | Candidate worktree status is clean at `a6a7cd493eec...`. |  | Local candidate branch created from merged main. |
| BRANCH-002 | DYEC | Create `prod-candidate-260911` from exact `origin/main`. | SUCCESS | feature_implementation | Gate 1 | orchestrator | Candidate worktree status is clean at `cd41cd510c6c...`. |  | Local candidate branch created from merged main. |
| DAYOA-REL | DayOA | Preserve superseded tag `13.4.32`, commit the formatting correction, and push usable annotated tag `13.4.33` plus the candidate branch. | SUCCESS | feature_implementation | Gate 5 | orchestrator | Candidate branch and both annotated tags are remote; `13.4.33` peels to `56208632627ccff4c1fb2b2525900e68de59ec12`; `git diff 13.4.31..13.4.33 --check` is clean. | The initial shell continued after the failed whitespace gate. | `13.4.32` remains immutable and superseded; `13.4.33` is the usable release. |
| DYEC-PIN | DYEC | Pin current DayOA rows to `13.4.33`, freeze the exact current catalog as immutable build `16.1.85`, preserve older snapshots, and validate the result. | SUCCESS | config_or_startup_contract | Gate 5 | orchestrator | Source/payload catalogs are byte-identical; all 29 current commands and the exact `16.1.85` copy use DayOA `13.4.33`; historic `16.1.81` and `16.1.82` remain `13.4.30` and `13.4.31`. |  | Implementation and release validation are complete; publication is tracked by FINAL-001. |
| DYEC-CURRENT | DYEC | Make catalog v5 use `dyec_builds.current` by default and consult numeric snapshots only for explicit `--dyec-version`. | SUCCESS | feature_implementation | Gate 3 | orchestrator | Default CLI probe returned `dyec_version=current`, 29 commands, and DayOA `13.4.33`; explicit `--dyec-version 16.1.82` returned 9 commands at `13.4.31`. Default model accessors are covered independently from repository rows. |  | Numeric snapshots are opt-in; `current` is the default for every catalog consumer. |
| DYEC-INSTALLED | DYEC | Remove static source/package self-pins and make every headnode configure path install and verify the running exact DYEC release. | SUCCESS | config_or_startup_contract | Gate 3 | orchestrator | Active config contains no self-pin key; public headnode help contains no `--dyec-version`; configuration derives `get_release_version()`, checks out `refs/tags/<running-version>`, and verifies the exact remote `dyec --version`. |  | A development/non-release installation now fails closed instead of selecting another DYEC version. |
| DYEC-SELF | DYEC | Publish a second DYEC self-pin release `16.1.86`. | NO_LONGER_NEEDED | config_or_startup_contract | Gate 5 | orchestrator | Superseded by the owner's installed-version contract; no `16.1.86` commit or tag was created. | Redundant static self-pinning caused the downgrade/confusion this release removes. | One DYEC `16.1.85` release is now the complete train. |
| FINAL-001 | Cross-repo | Verify remote branches, annotated tag objects and peeled commits, source/payload parity, clean release diffs, and terminal ledger state. | SUCCESS | contract_test | Gate 5 | orchestrator | DYEC branch and annotated tag were pushed; remote branch and peeled `16.1.85` both resolved to `fd1b583b73ccc22e3c3589357e4d3b09c8502d6a`, while remote tag object was `61ee2018596d25d92669d6ce6c943da9d5084a7e`. DayOA branch and peeled `13.4.33` both resolved to `56208632627ccff4c1fb2b2525900e68de59ec12`. |  | This docs-only closeout advances the DYEC candidate branch after the release without moving the immutable `16.1.85` tag. |

## Validation evidence before the release commit

- Release-specific test gate: `681 passed in 35.42s` across catalog, packaged
  defaults, versioning, CLI, headnode workflow, entrypoint, and failure-path
  coverage.
- Broad test gate: `2480 passed, 20 failed, 11 skipped` across 2511 tests.
  A detached exact-`16.1.84` worktree reproduced the same 20 failures: four
  Conda activation harness failures, six CLI-core mock-contract failures, one
  lock error-message mismatch, eight existing SSM `as_user` assertions, and
  one existing provider-neutral catalog-token assertion. The candidate adds no
  broad-suite failure relative to the merged release baseline.
- Targeted Ruff syntax/undefined-name rules, Python compilation, both
  `get_git_deets.sh` syntax checks, and `git diff --check` all passed.
- Source/package catalog, global config, and `get_git_deets.sh` copies are
  byte-identical. Parsed `dyec_builds.current` equals `dyec_builds.16.1.85`
  exactly and contains 29 commands pinned to DayOA `13.4.33`.
- From the clean annotated tag, `dyec --version` returned `Daylily Ephemeral
  Cluster 16.1.85` and the 681-test release gate passed again in 34.24 seconds.
- The DAY-EC environment does not contain the optional `build` frontend, so
  `python -m build` could not start. The equivalent isolated local wheel gate
  succeeded through `pip wheel --no-deps`: artifact
  `daylily_ephemeral_cluster-16.1.85-py3-none-any.whl`, SHA-256
  `3673f99b66c3ab317968f77a8960af89bd73795f779b17da3a69b88b0e9944e8`.
  Its metadata reports `Version: 16.1.85`, and all three embedded
  source/package parity targets matched byte-for-byte. No package-index upload
  was requested or performed.

## Published release refs

- DayOA usable release: annotated `13.4.33`; remote tag object
  `8df9d9bbd735691483ac0173e6e9226186d41056`; peeled commit and candidate
  branch `56208632627ccff4c1fb2b2525900e68de59ec12`.
- DayOA superseded release retained: annotated `13.4.32`; remote tag object
  `f5253e9dabd2c3a356abab72062204a447cfe047`; peeled commit
  `06483d03ac32373583daf8cdb11d79c791f4b00f`.
- DYEC release: annotated `16.1.85`; remote tag object
  `61ee2018596d25d92669d6ce6c943da9d5084a7e`; peeled release commit
  `fd1b583b73ccc22e3c3589357e4d3b09c8502d6a`.
- No `16.1.86` release was created; the installed-version contract makes the
  former second self-pin release unnecessary.

## Final report

All rows terminal: yes.

Objective complete: yes.

Status counts: `SUCCESS=10`, `OPEN=0`, `IN_PROGRESS=0`, `NO_LONGER_NEEDED=1`,
`BLOCKED=0`, `FAIL=0`.
