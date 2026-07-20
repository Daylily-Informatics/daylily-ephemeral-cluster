# DYEC 13.0.3 and DayOA 13.0.15 pin release ledger

Created: 2026-07-20T15:39:02Z

Objective: publish one coherent DYEC release that pins the newly published DayOA `13.0.15` in every source and packaged command catalog and self-pins DYEC `13.0.3` in every source and packaged global configuration.

## Gate 0

- DYEC base: `origin/main` at `759e5dfc`, annotated tag `13.0.2`.
- DayOA `13.0.15` is an annotated remote tag resolving to commit `38d6dcdc9900cee25b4e0b94a3f40ce9cc853cfd`.
- Release branch: `codex/dayoa-13.0.15-dyec-release-20260720`.
- Dirty primary checkouts and unrelated untracked ledgers remain untouched.

## Control ledger

| ID | Requirement | State | Evidence |
|---|---|---|---|
| PIN-001 | Update source command catalog to DayOA `13.0.15` | SUCCESS | Default ref and current HIOMRS/Inflection commands updated |
| PIN-002 | Update packaged command catalog identically | SUCCESS | Source/payload byte parity verified |
| PIN-003 | Self-pin source and packaged DYEC config to `13.0.3` | SUCCESS | Source/payload byte parity verified |
| QA-001 | Run focused and full DYEC tests | SUCCESS | Focused: 30 passed; full supported environment: 2,230 passed, 11 skipped; changed-file Ruff and `git diff --check` passed |
| REL-001 | Push release branch and annotated `13.0.3` | OPEN | Clean tested commit required |
| CLOSE-001 | Verify remote branch/tag SHAs and tag type | OPEN | Terminal reconciliation pending |

## Release rules

- Use the non-`v` annotated tag `13.0.3`.
- Never move an existing pushed tag.
- Do not merge or open a PR as part of this request.
