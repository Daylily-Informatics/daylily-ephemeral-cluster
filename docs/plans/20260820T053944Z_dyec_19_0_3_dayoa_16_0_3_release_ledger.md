# DYEC 19.0.3 / DayOA 16.0.3 Release Ledger

Date: 2026-08-20

## Scope

Create a DYEC patch release from the maximum published `19.0.*` tag, pin the active repository catalog and the released `current` command catalog to the existing DayOA `16.0.3` tag, preserve all older numeric catalog snapshots, and publish the clean DYEC branch and annotated tag.

## Control Ledger

Controlling request: user request in the current Codex task

Ledger path: `docs/plans/20260820T053944Z_dyec_19_0_3_dayoa_16_0_3_release_ledger.md`

Gate 0 baseline:

- Repository/worktree: `/Users/jmajor/.codex-worktrees/dyec-pin-dayoa-16.0.3-19.0.3`
- Branch: `codex/pin-dayoa-16.0.3-dyec-19.0.3`
- Base: maximum published DYEC `19.0.*` tag `19.0.2`, commit `3dea2ea3bfb80132983f2d5322231c3631a9e5fe`.
- Candidate occupancy: local and remote DYEC tag `19.0.3` absent; proposed branch absent before creation.
- DayOA release: annotated tag `16.0.3`, tag object `58b3e1a1e6842a124e1e7abdb7f3ed61b987400e`, peeled commit `bcd2e804a063be33dbc0ae414b82b5fee061741a`.
- Baseline repository state: clean (`git status --short --branch` showed only the branch header).
- Canonical and packaged catalog SHA-256: `f6ffde7d26e306bdaae394d98d5d551519efc1d2bd9aa153a1510c1f9d9a1d49`; byte-identical.
- Active repository catalog: 31 commands, `default_ref: 16.0.2`, and all 31 `git_tag` values are `16.0.2`.
- `dyec_builds.current`: 31 commands, `dayoa_git_tags: [16.0.2]`, and all 31 command pins are `16.0.2`; semantic SHA-256 `7891a4c31cb694e4aa36503ed7b85e15a0386c754d8155834bfe04427e7ae5c9`.
- Numeric history: 48 snapshots; `current` is equal to frozen `19.0.1` at baseline. DYEC `19.0.2` is a headnode-only patch release and intentionally has no numeric catalog snapshot.
- Production membership: exactly 11 commands: `complete_genomics_cg_snv_concordance`, `hiomr2_slim_kitchensink_mega`, `illumina_hg002_kitchensink_multiqc`, `illumina_run_qc`, `illumina_sentieon_pangenome_kitchensink`, `inflection-bjuice-product-v0.9`, `ont_run_qc`, `ont_snv_alignstats_kitchensink`, `ultima_run_qc`, `ultima_sentieon_pangenome_kitchensink`, and `ultima_snv_alignstats_kitchensink`.
- Sweep: `rg -n '19\\.0\\.1|16\\.0\\.2|19\\.0\\.2|16\\.0\\.3' tests` identified mutable-current expectations plus historical release assertions that must remain frozen.
- Baseline validation: the activated `DAY-EC` Python environment parsed the YAML and recorded counts, pins, production membership, semantic hashes, and source/package parity. No live cluster/workflow action is in scope.
- Release boundary: no pull request, GitHub Release, package-registry publication, headnode configuration, workflow launch, AWS mutation, or historical tag movement is authorized or planned.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| REL-001 | DYEC | Start from the maximum `19.0.*` release and reserve an unoccupied patch branch/tag | SUCCESS | feature_implementation | Gate 0 | orchestrator | Branch created from exact annotated tag `19.0.2`; `19.0.3` and branch were absent remotely |  | Gate 0 release base and candidate occupancy verified |
| CAT-001 | DYEC catalog | Retarget the active DayOA repository default and all 31 active commands to `16.0.3` | SUCCESS | feature_implementation | Gate 1 | orchestrator | Parsed catalog: `default_ref == 16.0.3`; 31 active commands; unique active pin set is `{16.0.3}` |  | Active repository pin is uniformly retargeted without command-membership drift |
| CAT-002 | DYEC catalog | Retarget `dyec_builds.current` and create immutable `19.0.3` with all 31 commands pinned to `16.0.3` | SUCCESS | feature_implementation | Gate 1 | orchestrator | `current == 19.0.3`; 31 commands; `dayoa_git_tags == [16.0.3]`; every command pin is `16.0.3`; CLI render reports the same |  | New numeric snapshot is the exact retargeted current catalog |
| CAT-003 | DYEC catalog | Preserve every prior numeric snapshot and canonical/package byte parity | SUCCESS | active_product_contract | Gate 5 | orchestrator | All 48 prior numeric snapshots compare equal to tag `19.0.2`; both catalog files are byte-identical at SHA-256 `b98bfe4f26aa7ee49ed09001f82af3b32ab2106a06ee8c77b752e6a90d3ae67d`; reconstructed expected text matches exactly |  | Historical catalog data and packaged parity are preserved |
| TEST-001 | DYEC tests | Update mutable-current expectations and add release-specific invariants for `19.0.3` without weakening historical checks | SUCCESS | contract_test | Gate 5 | orchestrator | Initial focused gate: 6 passed. Broader gate exposed three stale `bin/day_run` assertions; targeted rerun after test-only correction: 2 passed. Final combined gate: 16 passed in 171.08s. New release test passes Ruff check and format check. | Stale test-only wrapper expectations survived the prior DayOA 16 boundary release. | Mutable expectations now follow `19.0.3`; `19.0.1` remains explicitly frozen at `16.0.2`; all focused checks pass |
| REL-002 | DYEC release | Validate, commit, push the branch, create an annotated `19.0.3` tag, and push the tag | SUCCESS | feature_implementation | Gate 5 | orchestrator | Implementation commit `43b9574c2dae0ec764a758077cbb508f74b20cc5` pushed to `origin/codex/pin-dayoa-16.0.3-dyec-19.0.3`; remote candidate tag remained unoccupied; this terminal closeout is the exact clean commit targeted by annotated tag `19.0.3` and its immediate push |  | DYEC `19.0.3` publication sequence completed without moving an existing tag |

## Final Report

All rows terminal: yes

Objective complete: yes

Status counts:

- SUCCESS: 6
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0

Changed files:

- Canonical and packaged command catalogs: `config/daylily_pipeline_command_catalog.yaml`, `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`
- Current/release contract tests: `tests/test_repository_catalog.py`, `tests/test_repository_catalog_aliases.py`, `tests/test_hiomrs_command_catalog.py`, `tests/test_release_18_0_46_pangenome_catalog.py`, `tests/test_release_18_0_56_rc0_catalog_consolidation.py`, `tests/test_release_18_0_59_ultima_cram_downsampling.py`, `tests/test_release_19_0_1_orphaned_pull_forward.py`, `tests/test_release_19_0_3_dayoa_16_0_3_pin.py`
- Durable release ledger: this file

Validation:

- Final focused catalog/release pytest gate: 16 passed in 171.08 seconds.
- `dyec --json catalog list --dyec-version 19.0.3`: 31 commands, one DayOA tag (`16.0.3`), and 11 production commands.
- Exact-text reconstruction from tag `19.0.2`: both catalog files match the intended 32 active substitutions, 32 `current` substitutions, and appended `19.0.3` snapshot exactly.
- Historical semantic comparison: all 48 pre-existing numeric snapshots are unchanged.
- Canonical/package SHA-256 parity: both are `b98bfe4f26aa7ee49ed09001f82af3b32ab2106a06ee8c77b752e6a90d3ae67d`.
- New `19.0.3` release test: Ruff check and format check pass.
- `git diff --check`: pass.

Non-success terminal rows: none.

Live approvals/actions not performed: no workflow, cluster, headnode, AWS, package-registry, GitHub Release, or pull-request action was part of this release.

Residual risk: the release used the focused 16-test catalog gate requested for a fast pin-only release; the complete DYEC test suite was not run.
