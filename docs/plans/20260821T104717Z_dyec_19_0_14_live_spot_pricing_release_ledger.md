# DYEC 19.0.14 Live Spot Pricing Release Ledger

Created: 2026-08-21T10:47:17Z

## Control Ledger

Controlling request: release a new DYEC version based on `19.0.13` that pulls in the existing live Spot-price observation fix, push the commit and annotated tag, and update `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` to the new tag.

Ledger path: `docs/plans/20260821T104717Z_dyec_19_0_14_live_spot_pricing_release_ledger.md`

Gate 0 baseline:

- Source repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` at immutable annotated tag `19.0.13`, commit `ebaafce51cff23d96b4971e97342429e2821f747`.
- Original checkout: detached and tracked-clean with pre-existing untracked user paths; those paths are out of scope and must remain untouched.
- Isolated release worktree: `/Users/jmajor/.codex-worktrees/dyec-release-19.0.14-live-spot-pricing` on `codex/release-19.0.14-live-spot-pricing`, initially clean at `19.0.13`.
- Authoritative fix: pushed commit `2446d5cef10f8c6fee4d67ce37b421d7be703b36`, which keeps the live EC2 Spot-price lookup, records local lookup capture time as observation time, and retains the provider price-effective timestamp separately.
- Release tag check: `19.0.14` absent locally and from `origin` before work began.
- Baseline inspection: `git show --stat 2446d5ce` reports changes only to `daylily_ec/aws/spot_pricing.py`, `docs/cli_reference.md`, and `tests/test_spot_pricing.py`.
- Validation boundary: focused Spot-pricing tests only; no full repository suite and no live AWS create or retry.
- Release boundary: push only to `origin` (`lsmc-bio`), use a non-`v` annotated tag, and never move an existing tag.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| REL-001 | Spot pricing | Transplant exact fix commit `2446d5ce` onto `19.0.13` without introducing cached-price reuse or fallback behavior. | SUCCESS | feature_implementation | Gate 1 | orchestrator | Cherry-picked as `f0f54cbc`; `git diff --exit-code 2446d5ce -- daylily_ec/aws/spot_pricing.py tests/test_spot_pricing.py` returned no differences. |  | The exact implementation and tests were transplanted; restored-create documentation was retained around the one adapted live-pricing paragraph. |
| REL-002 | Release metadata | Advance the checked-in release and both command-catalog mirrors from `19.0.13` to immutable snapshot `19.0.14`. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | `CURRENT_DYEC_BUILD` and README now identify `19.0.14`; source and packaged catalogs are byte-identical; normalized `19.0.13` and `19.0.14` snapshots compare equal. |  | Added a new immutable snapshot without changing `19.0.13`. |
| REL-003 | Verification | Run focused Spot-pricing tests proving a live lookup remains authoritative when the provider effective timestamp is old. | SUCCESS | contract_test | Gate 5 | orchestrator | `source ./activate`; `python -m pytest tests/test_spot_pricing.py -q` -> `29 passed in 0.64s`. |  | The focused live-observation contract is green; no full repository suite was run. |
| REL-004 | Git release | Commit and push the release branch, then create and push an annotated `19.0.14` tag at the exact clean release commit. | IN_PROGRESS | feature_implementation | Gate 5 | orchestrator | Tag name verified free locally and remotely; release files are ready to commit. |  |  |
| REL-005 | Local checkout | Move `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` to detached tag `19.0.14` while preserving pre-existing untracked user files. | OPEN | feature_implementation | Gate 5 | orchestrator | Original checkout baseline recorded. |  |  |
| REL-006 | Live boundary | Do not retry cluster creation or perform any AWS mutation during this source release. | OPEN | legitimate_safety_handling | Gate 5 | orchestrator | User authorized source release and checkout update only. |  |  |

## Final Report

All rows terminal: no

Objective complete: no

Status counts:

- SUCCESS: 3
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0
- IN_PROGRESS: 1
- OPEN: 2

Changed files: live Spot pricing implementation/tests, restored-create CLI documentation, release metadata, both catalog mirrors, and this ledger.

Validation: focused Spot-pricing suite passed (`29 passed`); source/packaged catalog mirrors and normalized `19.0.13`/`19.0.14` snapshots compare exactly.

Non-success terminal rows: none.

Residual risks: release publication and original-checkout update remain pending; no live cluster retry was performed.
