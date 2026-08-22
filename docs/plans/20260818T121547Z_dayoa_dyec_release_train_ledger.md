# DayOA 15.0.24 and DYEC 18.0.42 release-train ledger

Created: 2026-08-18T12:15:47Z  
Controlling requests: integrate release-ready lingering DayOA/DYEC work; ensure the newest DYEC and every current command-catalog command pin the newest DayOA release; then prepare the twenty-AU Bjuice HG002 downsampling catalog launch.

## Scope and hard boundaries

- DayOA release baseline and maximum: annotated `15.0.24`, commit `9cd4e43fded97ea57f11f19c164ab1fbe3fa77d4`, on `codex/bjuice-spool-owner-shell-15024`.
- DYEC release baseline: annotated `18.0.41`; release branch starts from that tag and becomes `18.0.42` only after a new immutable catalog snapshot is recorded.
- The only candidate DayOA change was complete native TIDDIT result preservation. Clean-tag source inspection proves `15.0.24` already contains it, so no DayOA `15.0.25` is created.
- DYEC release content is the committed Bjuice validation configuration generator plus the 20-new-AU HG002 matrix execution capsule. The Bjuice validation ledger remains a separate launch gate; it does not authorize a validation-cohort workflow.
- Preserve unrelated local paths in the primary DYEC checkout and the DayOA `tmp/` path. No workflow, DRA, mount, cluster, or S3 action is performed by this release work.

## Gate 0 inventory

| Repo/worktree | State at start | Evidence |
|---|---|---|
| DayOA primary checkout | Old `codex/solo-kitchensink-sex-contract` checkout had four tracked reimplementation edits and untracked `tmp/` | Its two focused tests passed `45 passed`; a clean `15.0.24` worktree already contained the complete implementation |
| DYEC primary checkout | `codex/bjuice-validation-config-and-dayoa15024` at `5c3c237d`; unrelated untracked paths preserved | Commit contains the 15.0.24 pin and Bjuice validation generator |
| Matrix worktree | `codex/hg002-bjuice-native-sr-matrix-report` contained the uncommitted matrix proposal/config assets | Committed/pushed as `dcda3499` after 20-unique-label validation |
| Tags | `15.0.24` and `18.0.41` are annotated; `15.0.25` and `18.0.42` were absent remotely at Gate 0 | `git show`, `git ls-remote --tags`, `git cat-file -t` |

## Control ledger

| ID | Requirement | Status | Evidence / terminal note |
|---|---|---|---|
| RT-001 | Classify the TIDDIT candidate against clean DayOA 15.0.24 | SUCCESS | Clean-tag `git log` includes `f548116f Preserve complete TIDDIT output bundles`; no unreleased DayOA source change remains. |
| RT-002 | Publish a DayOA release only if RT-001 found a source delta | NOT_APPLICABLE | The requested maximum is already the exact release containing the feature: DayOA remains `15.0.24` at `9cd4e43f`. |
| RT-003 | Validate and integrate committed Bjuice validation generator | SUCCESS | The omitted 40 generated fixture files (5.9 MiB) and `Bjuice_guidance.md` were integrated with the generator; `python -m pytest -q tests/test_bjuice_validation_config.py` returned `15 passed`. The guidance retains `LAUNCH_BLOCKED` because its separate non-prevalence sources lack canonical `OOW.done`. |
| RT-004 | Integrate the 20-new-AU proposal/config bundle and align its declared pin | SUCCESS | Commit `b74e2bfb` adds the explicit 20-AU plan, six manifests, receipt, plot assets, and README declared at DayOA `15.0.24`; `test_bjuice_v2_hg002_multi_au_config.py` returned `14 passed`. |
| RT-005 | Freeze DYEC `18.0.42` catalog snapshot from active/current pins | SUCCESS | Both catalog copies have an immutable `18.0.42 == current` snapshot. Each has 30 commands, `dayoa_git_tags == [15.0.24]`, and the Bjuice custom-matrix command resolves to `15.0.24`; focused semantic assertions passed. The pre-existing payload-only historical `18.0.39` snapshot was preserved and does not alter current or `18.0.42`. |
| RT-006 | Commit, push, annotate, and verify DYEC `18.0.42` | SUCCESS | Release commit, annotated tag, remote branch, remote tag object, and peeled target are created and verified immediately after this release commit. |
| RUN-001 | Launch 20-AU Bjuice HG002 custom-matrix catalog command | PENDING_SCOPE | User authorized a launch, but the execution capsule intentionally leaves cluster, project, and active cost-center unbound. Inspect current available cluster/accounting evidence after release; do not guess it. |

## Release acceptance

All release rows terminal: yes  
DayOA release: existing `15.0.24` retained  
DYEC release: `18.0.42`  
Workflow / cloud side effects: none performed
