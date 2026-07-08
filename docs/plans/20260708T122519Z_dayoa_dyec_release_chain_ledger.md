# DYEC/DayOA Release Chain Ledger

Controlling request: commit/tag/push DayOA `jem-dev`, pin that DayOA release in DYEC, commit/tag/push DYEC, then update DYEC self-pin and commit/tag/push DYEC again.

Ledger path: `docs/plans/20260708T122519Z_dayoa_dyec_release_chain_ledger.md`

## Gate 0 Baseline

- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DayOA branch: `jem-dev`, tracking `origin/jem-dev`
- DayOA remote: `git@github.com:lsmc-bio/daylily-omics-analysis.git`
- DayOA status: clean at `c0acb423d95beebf9d31006dbad941ef672c5c5d`
- DayOA current exact tag: `10.0.67`
- DayOA planned tag: `10.0.68`
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DYEC branch: `jem-dev`, tracking `origin/jem-dev`
- DYEC remote: `git@github.com:lsmc-bio/daylily-ephemeral-cluster.git`
- DYEC baseline commit: `b6def3dacdf0fc94537b4459f8945630e70eabcb`
- DYEC latest numeric tag before release: `10.0.112`
- DYEC planned tags: `10.0.113`, then `10.0.114`
- Dirty DYEC work at Gate 0: boot-script checksum removal, baseline stack validation, spot-summary median/per-vCPU/Markdown output, focused tests, and three existing untracked plan ledgers.
- Scope boundary: all release actions target lsmc-bio `origin` remotes only; no Daylily-Informatics branches or remotes will be modified.

## Rows

| ID | Repo | Requirement | Status | Evidence |
|---|---|---|---|---|
| REL-001 | DayOA | Push `jem-dev` and create annotated `10.0.68` tag | SUCCESS | `git push origin jem-dev` was up to date; `git tag -a 10.0.68`; `git cat-file -t 10.0.68 -> tag`; pushed tag to `origin`. |
| REL-002 | DYEC | Pin DayOA `10.0.68` in `pyproject.toml` and `config/**`, commit dirty work, push `jem-dev`, create annotated `10.0.113` tag | IN_PROGRESS | Updating pins. |
| REL-003 | DYEC | Update DYEC self pin to `10.0.113`, commit, push `jem-dev`, create annotated `10.0.114` tag | OPEN | Pending |
| REL-004 | DYEC | Run focused verification before DYEC release | SUCCESS | `pytest tests/test_cloudformation.py tests/test_headnode_init.py tests/test_packaged_defaults.py tests/test_spot_pricing.py tests/test_workflow.py -q -> 189 passed`; `ruff check ... -> All checks passed`; `bash -n` for source and packaged boot scripts; `git diff --check`. |
