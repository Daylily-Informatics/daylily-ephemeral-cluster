# DYEC 19.0.1 orphaned-work pull-forward ledger

## Objective

Pin PyGraphviz bootstrap installation to `2.0.1`, allow one hour for FSx
reference imports during Ubuntu bootstrap, reconcile the mutable active command
catalog with the released current membership, pin the new catalog to DayOA
`16.0.2`, and publish an immutable annotated DYEC `19.0.1` release.

Cross-repository ledger:
`/Users/jmajor/.codex-worktrees/dayoa-new-break-ver/docs/plans/20260820T033801Z_orphaned_pull_forward_release_ledger.md`

## Gate 0 inventory

| Item | Evidence |
|---|---|
| Isolated checkout | `/Users/jmajor/.codex-worktrees/dyec-new-break-ver` is clean on `new-break-ver`, synchronized with `origin/new-break-ver`; the dirty primary checkout is not used for release edits. |
| Release lineage | Branch head `e7eee7439222c5f74a5f74867933e060cee81cc9` descends from annotated tag `19.0.0`, peeled commit `ece9195fd5da90731d38a89ea15131fa66e35293`. |
| Tag occupancy | `19.0.1` is absent locally and from `origin` at Gate 0. It must not be overwritten if it appears before publication. |
| PyGraphviz baseline | Both Ubuntu bootstrap surfaces use unbounded `pip install --upgrade pygraphviz`; the reviewed pull-forward is exact pin `pygraphviz==2.0.1`. |
| FSx baseline | `config/day_cluster/post_install_ubuntu_combined.sh` uses `reference_wait_timeout_seconds=1800`, shorter than the supported greater-than-40-minute import window. |
| Catalog baseline | Active repository definitions have 30 commands, retain obsolete `inflection-bjuice-product-v0.2`, and omit the two Sentieon pangenome kitchen-sink commands. Frozen `19.0.0` and `current` each have the intended 31-command membership, all pinned to DayOA `16.0.1`. Source and packaged catalogs are byte-identical. |
| Verification boundary | Per the user's earlier release instruction, no repository test suite will run. Verification is limited to YAML/model inspection, command counts and pins, historical snapshot comparison, source/package parity, shell syntax, diff checks, clean-state checks, annotated-tag type, and remote peeled-commit verification. |

## Execution rows

| ID | Scope | Action | Status | Category | Gate | Evidence / terminal condition |
|---|---|---|---|---|---|---|
| DYEC-001 | Ubuntu bootstrap | Pin global and DAY-EC PyGraphviz installation to `2.0.1`. | SUCCESS | config_or_startup_contract | Gate 2 | Both bootstrap copies use `python3 -m pip install --upgrade "pygraphviz==2.0.1"`; generated headnode configuration uses the same exact pin. Existing contract-test sources assert the pin and reject the unbounded command. |
| DYEC-002 | FSx bootstrap | Raise the reference-import wait to 3,600 seconds in authoritative source and packaged bootstrap copies. | SUCCESS | config_or_startup_contract | Gate 2 | Both byte-identical bootstrap copies use `reference_wait_timeout_seconds=3600`; `bash -n` passed for each. |
| DYEC-003 | Active catalog | Remove obsolete Bjuice v0.2 and add the two released Sentieon pangenome kitchen-sink definitions without altering historical numeric snapshots. | SUCCESS | active_product_contract | Gate 3 | Parsed active and current memberships are the same 31 command IDs; active v0.2 is absent and both Sentieon pangenome kitchen-sink definitions are present. Current still has exactly the approved 11 `prod` rows. |
| DYEC-004 | Release catalog | Pin active/default/current to DayOA `16.0.2`, add immutable `19.0.1 == current`, and preserve `19.0.0`. | SUCCESS | config_or_startup_contract | Gate 5 | Remote annotated DayOA tag object `04b8886b03a5f3977f0a9bd13902ecdf22a9237a` peels to `4c96505183ffd6cbb9e6473f14cf313b1d1037aa`. Default, all 31 active rows, current tag list, and all 31 current rows use `16.0.2`; `19.0.1 == current`. Frozen `19.0.0` retains semantic SHA-256 `b5c72ddd6070d35ddb9e160d1bc7d9b8b8c45040a036f36cfaf0bdadd224aa4f`; all pre-existing numeric history retains SHA-256 `a98902aee7c98eecb2fa074ff4debbe91e477582133536506bfb985eab0247a6`. |
| DYEC-005 | Verification | Confirm YAML parsing, model loading, source/package identity, shell syntax, exact counts/pins, production membership, and frozen-history preservation without running repository tests. | SUCCESS | contract_test | Gate 5 | Canonical/package catalogs and bootstrap scripts compare byte-identical; YAML and repository model loading passed; modified Python test/source files parsed with `ast`; both bootstrap scripts passed `bash -n`; `git diff --check` passed. Test expectations were advanced, but no repository test command ran by explicit instruction. |
| DYEC-006 | Release | Commit, push `new-break-ver`, create annotated tag `19.0.1`, push it, and verify its remote peel. | IN_PROGRESS | config_or_startup_contract | Gate 5 | Source is ready for the release commit; branch/tag publication remains. |

## Terminal gate

Open. Every row must be terminal before release completion is reported.
