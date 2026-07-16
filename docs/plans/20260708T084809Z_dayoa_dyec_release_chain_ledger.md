# DayOA / DYEC Release Chain Ledger

Created: 2026-07-08T08:48:09Z

Objective: carry the current DayOA/DYEC state through the requested release chain: commit/tag DayOA if dirty, update DYEC DayOA pins if a new DayOA tag exists, release DYEC, then update DYEC self-pin to that DYEC release and cut the follow-up DYEC release.

## Gate 0 Inventory

Commands:

- DayOA: `git fetch origin --no-tags --prune && git fetch origin --tags --prune && git status --short --branch && git describe --tags --dirty --long`
- DYEC: `git fetch origin --no-tags --prune && git fetch origin --tags --prune && git status --short --branch && git describe --tags --dirty --long`
- Tag availability: `git ls-remote --tags origin '10.0.109' '10.0.110'`
- Annotation checks: `git cat-file -t 10.0.66` and `git cat-file -t 10.0.108`

Baseline:

- DayOA working dir: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DayOA branch: `jem-dev`
- DayOA status: clean
- DayOA current release: annotated tag `10.0.66` at commit `ce41c6c`
- DYEC working dir: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DYEC branch: `jem-dev`
- DYEC status before this ledger: clean
- DYEC describe before this ledger: `10.0.108-3-g42225777`
- DYEC current release: annotated tag `10.0.108`
- DYEC candidate next tags: `10.0.109` and `10.0.110`
- Remote tag availability: `10.0.109` and `10.0.110` absent on `origin`

Version plan:

- DayOA: no new tag; use existing `10.0.66` because the requested DayOA dirty commit stage has no dirty files to commit.
- DYEC pin release: `10.0.109`
- DYEC self-pin release: `10.0.110`

## Tracking Rows

| ID | Repo | Requirement | Status | Evidence | Terminal Note |
|---|---|---|---|---|---|
| REL-001 | DayOA | Commit dirty DayOA changes to `jem-dev`, push, tag, and push the tag. | NO_LONGER_NEEDED | `git status --short --branch -> ## jem-dev...origin/jem-dev`; `git describe -> 10.0.66-0-gce41c6c`; `git cat-file -t 10.0.66 -> tag`. | DayOA is already clean and released at annotated tag `10.0.66`; no empty commit or duplicate release tag was created. |
| REL-002 | DYEC | Verify DYEC DayOA pin surfaces already match the selected DayOA tag. | SUCCESS | `pyproject.toml` and catalog/test searches show DayOA pin `10.0.66`. | No DayOA pin edit required because DayOA did not advance past `10.0.66`. |
| REL-003 | DYEC | Commit/push/tag the current DYEC release state as `10.0.109`. | SUCCESS | Commit `f7a077a9`; `git tag -a 10.0.109 -m "Release 10.0.109"`; `git push origin jem-dev`; `git push origin 10.0.109`; `git cat-file -t 10.0.109 -> tag`. | DYEC `10.0.109` is an annotated tag on `jem-dev`. |
| REL-004 | DYEC | Update DYEC self-pin to `10.0.109`, commit/push, tag as `10.0.110`, and push the tag. | SUCCESS | Edited `config/daylily_cli_global.yaml`, `daylily_ec/resources/payload/config/daylily_cli_global.yaml`, `tests/test_lsmc_bio_fork_contract.py`; `pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py tests/test_cli_registry_v2.py tests/test_packaged_defaults.py -q -> 171 passed`; commit `9a127b59`; pushed `jem-dev`; `git tag -a 10.0.110 -m "Release 10.0.110"`; pushed tag; `git cat-file -t 10.0.110 -> tag`. | DYEC self-pin now points at `10.0.109`; follow-up annotated release tag `10.0.110` is pushed. |
| REL-005 | DYEC | Verify final branch/tag state and report versions. | SUCCESS | DayOA: `git describe -> 10.0.66-0-gce41c6c`, `git cat-file -t 10.0.66 -> tag`; DYEC: `git describe -> 10.0.110-0-g9a127b59` before this ledger-only closure update, `git cat-file -t 10.0.109 -> tag`, `git cat-file -t 10.0.110 -> tag`; `git ls-remote --tags origin '10.0.109' '10.0.110'` returned both tags. | Final release tags: DayOA unchanged at `10.0.66`; DYEC release `10.0.109`; DYEC self-pin follow-up `10.0.110`. |

## Final Notes

- No DayOA commit or tag was created because the DayOA worktree was clean and already exactly at annotated tag `10.0.66`.
- DYEC DayOA pin surfaces remain on `10.0.66`: `pyproject.toml`, both command catalog copies, and contract tests.
- DYEC self-pin surfaces now point to `10.0.109` in both config copies and `tests/test_lsmc_bio_fork_contract.py`.
- This ledger closure commit intentionally follows the `10.0.110` tag so the already-pushed release tag is not moved.
