# DayOA 13.4.11 and DYEC 16.1.57/16.1.58 Release Ledger

Controlling request: publish the DayOA change proven by the active
`prod-cand-260809/init-test-x2` controller, publish the completed DYEC workflow
observability CLI work while pinning that DayOA release, then publish a second
DYEC release whose self-pin points at the first DYEC release.

Ledger path:
`docs/plans/20260810T091723Z_dayoa_dyec_release_train_ledger.md`

## Gate 0 baseline

- DayOA repository: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`.
- DayOA branch: `codex/vendor-trussv-13.4.10`, initially clean at annotated
  tag `13.4.10` and commit `118f70f4db525a06f672fa298e6c6a364fb9a6ff`.
- DYEC repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`.
- DYEC branch: `codex/pin-dayoa-13.4.10-16.1.45`, initially at annotated tag
  `16.1.56` and commit `f59fd0527d4d7c91f1f23bf77423641af86b7a74`.
- Remote tags were fetched before version selection. The next free release tags
  were DayOA `13.4.11`, then DYEC `16.1.57` and `16.1.58`.
- The DYEC worktree contains many unrelated untracked plans, reports, backups,
  recordings, temporary files, and `TrusSV/`. They are excluded from every
  release commit by exact-path staging.
- Release contract: commit first, push the tracked branch, create a non-`v`
  annotated tag, push the tag, and verify the tag object and peeled commit.

## Live DayOA proof

- Exact headnode checkout:
  `/fsx/analysis_results/prod-cand-260809/init-test-x2/daylily-omics-analysis`.
- The only tracked headnode diff moved the Sentieon `202503.03` version probe
  ahead of `dayoa_spool_init`, retained the version output in memory, and
  removed the undeclared `sentieon-driver.version.txt` scratch receipt.
- That exact patch passed `sentdhiomr2_preflight` and allowed the active
  controller to reach submitted Slurm work before local formalization.
- The formalized local patch has focused ordering/no-receipt regression
  coverage. The focused DayOA suite reported `37 passed`.

## Control ledger

| ID | Area | Requirement | Status | Evidence | Terminal note |
|---|---|---|---|---|---|
| REL-001 | DayOA | Port the exact live-proven preflight fix and add regression coverage | SUCCESS | `workflow/rules/sent_hybrid_ilmn_ont_modular2.smk`; `tests/test_hiomr2_core_rules.py`; `37 passed` | Local rule diff matches the isolated headnode change. |
| REL-002 | DayOA release | Commit, push, and publish annotated tag `13.4.11` | SUCCESS | Commit `287923d167ca0ef6b05cb4469e290ade45f4852b`; remote tag object `9604b9de2cd369bcf7283b0dbf975f73281bf863` peels to that commit | Branch and tag push succeeded. |
| REL-003 | DYEC observability | Preserve and validate the completed status/Snakemake-log CLI implementation, docs, and tests | SUCCESS | `docs/plans/20260810T073000Z_dyec_workflow_observability_ledger.md`; `283 passed`; live read-only exact-log proof | Eleven observability rows are terminal SUCCESS. |
| REL-004 | DYEC DayOA pin | Update source and packaged command catalogs plus contract tests to DayOA `13.4.11` | SUCCESS | Source/payload catalog byte parity; combined observability and pin suite `362 passed`; Ruff, mypy, py_compile, and diff checks pass | No historical ledgers or unrelated files are rewritten. |
| REL-005 | DYEC release | Commit, push, and publish annotated tag `16.1.57` | SUCCESS | Commit `776e2be963378da4cde76690dc643c9c91c38f9b`; remote tag object `4ff12b2edb6edd4f99bdf46bba3e5e3e260cd2a7` peels to that commit | Includes observability work and DayOA pin. |
| REL-006 | DYEC self-pin | Update source and packaged DYEC self-pin to `16.1.57` and rerun contract tests | SUCCESS | Source/payload byte parity; `188 passed, 57 deselected`; focused fork contract `4 passed`; YAML value check passes | Self-pin points to the preceding immutable DYEC release. |
| REL-007 | DYEC release | Commit, push, and publish annotated tag `16.1.58` | SUCCESS | Exact-path staged self-pin release; annotated tag and synchronized release branch verified after commit | Final release leaves only pre-existing unrelated untracked files. |
| REL-008 | Final verification | Verify all three remote tags are annotated and peel to their intended commits | SUCCESS | Local `git cat-file -t` plus exact remote tag-object and peeled-commit refs for `13.4.11`, `16.1.57`, and `16.1.58` | No tag was moved and no force-push was used. |

## Release sequence

1. DayOA `13.4.11`: live-proven HIOMR2 preflight fix.
2. DYEC `16.1.57`: workflow observability feature plus DayOA `13.4.11` pin.
3. DYEC `16.1.58`: self-pin to immutable DYEC `16.1.57`.

## Current state

All rows terminal: **yes**

Objective complete: **yes**

Status counts:

- SUCCESS: 8
- FAIL: 0
- BLOCKED: 0

The active workflow, Slurm jobs, cluster resources, analysis outputs, and
runtime caches are outside this release mutation and are not modified here.
