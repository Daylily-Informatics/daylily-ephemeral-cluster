# DYEC 17.0.29 Immutable DayOA Controller Release Ledger

Controlling plan: user-directed DayOA/DYEC release reconciliation in this task.

Ledger path: `docs/plans/20260814T120856Z_dyec_17_0_29_immutable_dayoa_controller_release_ledger.md`

## Gate 0 baseline

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster-release-17.0.29-20260814`
- Branch: `codex/dyec-14.0.21-17.0.29`, created from immutable tag `17.0.28` (`420be9676dd279a9049bc9f882c97bffaf684435`).
- Current max DYEC tag at the user’s clarification: `17.0.28`; it already contains `17.0.18` as an ancestor.
- Current requested parent DayOA tag: `14.0.21`; DYEC must be updated only after the successor DayOA tag is published.
- Sweep baseline: prior controller contained runtime `patch_*` paths which rewrote DayOA source. Those paths must be removed comprehensively, with a pre/post clean-ref guard and negative tests.
- Live boundary: no controller, workflow, Slurm, FSx, S3, or cluster action is part of this release work.

## Control ledger

| ID | Area | Requirement | Status | Category | Gate | Evidence | Terminal note |
|---|---|---|---|---|---|---|---|
| DYEC-001 | Release ancestry | Base successor on max `17.0.28`, preserve `17.0.18` ancestry, and never move published tags. | SUCCESS | plan_amendment | Gate 0 | `git merge-base --is-ancestor 17.0.18^{} 17.0.28^{}` -> 0. | Existing tag is retained as the parent. |
| DYEC-002 | Controller source boundary | Remove every DayOA runtime source mutation path and add explicit pre/post immutable-ref checks. | SUCCESS | removable_compatibility_debt | Gate 1 | All embedded source writers and repair dispatches are removed; `verify_pinned_dayoa_checkout` verifies the selected ref, tracked/staged changes, and untracked files before dispatch and after return. `tests/test_script_entrypoints.py`: `43 passed, 1 warning`. | A controller now fails rather than editing a pinned checkout. |
| DYEC-003 | Operator docs | Add the immutable-source rule to DYEC `AGENTS.md` and `README.md`. | SUCCESS | feature_implementation | Gate 1 | Both documents explicitly prohibit runtime source patches/overlays/generated helpers and require a new DayOA release for missing behavior. | The operator-facing contract matches the implementation. |
| DYEC-004 | Catalog pin | Pin active DayOA catalog/default/current snapshot to the new published DayOA release without rewriting historic snapshots. | SUCCESS | config_or_startup_contract | Gate 4 | Active default and all 30 active command pins are `14.0.22`; `current` and immutable `17.0.29` snapshots match; source/payload catalogs are byte-identical. The catalog rebuild asserted every non-current historic raw block is verbatim from `17.0.28`. Per user instruction, no further test run was started after the focused run identified and the source-grounded stale expectations were corrected. | Historic snapshot content is retained; new current state pins published DayOA `14.0.22`. |
| DYEC-005 | Release provenance | Commit, push branch, annotate next unused DYEC tag, and verify remote tag objects. | IN_PROGRESS | contract_test | Gate 5 | `17.0.29` was absent from `origin` immediately before release preparation. | Pending commit, push, annotated tag, and remote verification. |

## Final acceptance

Pending. No live workflow or infrastructure action is authorized or required.
