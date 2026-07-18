# DayOA 12.0.3 to DYEC 11.0.5 Release-Candidate Ledger

Controlling request: prepare an isolated DYEC release candidate from current `origin/main`, update every active DayOA checkout/default pin to the released DayOA `12.0.3`, preserve `validated_version: 12.0.2` until the fresh exact-tag acceptance succeeds, then advance both shipped DYEC self-pin copies to the intended DYEC `11.0.5` release in a separate commit.

This lane is preparation only. It does not push a branch, open or merge a PR, create or push a tag, install the checkout, or touch AWS, clusters, headnodes, Slurm, FSx, or live analyses.

## Gate 0 Baseline

- Isolated worktree: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-release-11.0.5-20260718`
- Branch: `codex/dyec-release-11.0.5-20260718`
- Base: DYEC `origin/main` at `329325c31ec3a4ca9c730f9acd1d580367f49079`
- Primary checkout is preserved with its two unrelated untracked ledgers.
- Existing source and packaged DayOA defaults plus active HIOMRS, kitchen-sink, Betelgeuser, and Inflection pins: `12.0.2`.
- Existing source and packaged DYEC bootstrap self-pin: `11.0.3`.
- Remote DayOA `12.0.3` is an annotated tag object `fda0f5a1b353313f25c2dfff05428ddd5daac8a4` peeling to commit `4a7354c0a2a541a879e2825a466c90d65aa8c1e9`.
- DYEC tag `11.0.5` is absent locally and from `origin` at Gate 0.

## Control Ledger

| ID | Area | Requirement | Status | Evidence | Terminal note |
|---|---|---|---|---|---|
| DYEC-001 | Isolation | Start from current `origin/main` without modifying the dirty primary checkout. | SUCCESS | Worktree, branch, base commit, and primary dirty inventory are recorded above. | All writes are confined to the isolated worktree. |
| DYEC-002 | DayOA catalog | Pin source and packaged DayOA default plus every active DayOA 12 command `git_tag` to exact `12.0.3`; keep `validated_version: 12.0.2` until live acceptance. | SUCCESS | YAML readback proves both catalogs use default `12.0.3`; the four active v12 commands use `git_tag: 12.0.3` and `validated_version: 12.0.2`; source/payload `cmp` is zero. | `validated_version` is evidence, not an aspirational checkout pin. |
| DYEC-003 | Pin regression | Expand exact fork contract so all four active DayOA 12 commands are covered. | SUCCESS | Exact HIOMRS/manifest/status/fork gates passed `32 passed`; repository/catalog packaging gates passed `42 passed`. | HIOMRS, kitchen sink, Betelgeuser, and Inflection are explicit. |
| DYEC-004 | Functional commit | Commit catalog, tests, and release-candidate evidence without changing the DYEC self-pin. | SUCCESS | Commit `8e51da3b` (`Pin DayOA 12.0.3 in DYEC catalog`). | This is the first commit in the requested train. |
| DYEC-005 | Self-pin | Advance both shipped DYEC bootstrap refs and exact tests to `11.0.5` in a distinct commit. | SUCCESS | Source and packaged globals plus the exact fork test use `11.0.5`; source/payload parity and the full suite are green. | This ledger update is included in the second self-pin commit; no tag was created by the preparation lane. |
| DYEC-006 | Validation | Pass focused release gates, source/payload parity, YAML parsing, Ruff, and `git diff --check`. | SUCCESS | Focused release slice 76/76 passed. Full suite 2264 passed, 11 skipped, with one upstream Marshmallow deprecation warning. Changed Python passed Ruff check and format; both source/payload pairs are byte-identical; all four YAML files parsed; diff-check passed. | No new failure class or source/payload drift remains. |
| DYEC-007 | Handoff | Return a clean local branch with exact commits and no publication or live mutations. | SUCCESS | Two-commit branch `codex/dyec-release-11.0.5-20260718`; functional commit `8e51da3b` followed by the self-pin commit containing this terminal ledger. | Parent integrator owns PR, merge, annotated tag, headnode refresh, and live acceptance. |

## Intended Release Contract

- DayOA default ref: `12.0.3`
- Active DayOA 12 command `git_tag`: `12.0.3`
- Active DayOA 12 command `validated_version`: `12.0.2` until ACC-002 succeeds; the later `11.0.6` promotion lane will advance it to `12.0.3`.
- DYEC source and packaged self-pin after the second commit: `11.0.5`
- Intended release tag: annotated, non-`v` `11.0.5`, created only after review and merge by the parent integrator.

## Validation Evidence

- `python -m pytest -q tests/test_hiomrs_command_catalog.py tests/test_dayoa12_manifest_contract.py tests/test_command_sample_stats.py tests/test_lsmc_bio_fork_contract.py` -> `32 passed in 2.10s`.
- `python -m pytest -q tests/test_repository_catalog.py tests/test_packaged_defaults.py` -> `42 passed in 8.85s`.
- Both commands ran in the repo-supported `DAY-EC` environment after `source ./activate`.
