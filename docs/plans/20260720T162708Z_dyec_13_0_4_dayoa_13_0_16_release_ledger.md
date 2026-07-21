# DYEC 13.0.4 / DayOA 13.0.16 pin release ledger

Created: 2026-07-20T16:27:08Z

Objective: publish DYEC `13.0.4` with source and payload catalogs pinned to DayOA `13.0.16`, and source and payload global configuration self-pinned to DYEC `13.0.4`.

## Gate 0

- DYEC base: clean release branch at `988cca3546138a23e4199802459bd757d9532e37`, annotated tag `13.0.3`.
- DayOA `13.0.16`: annotated remote tag resolving to `4b5e21c515f88aee490ce613b1059ab33c1f6c8a`.
- Existing pushed tags are immutable; `13.0.4` was unclaimed at inventory time.
- No PR, main merge, package-index upload, or live headnode mutation is included.

## Control ledger

| ID | Requirement | Status | Category | Gate | Evidence | Terminal note |
|---|---|---|---|---|---|---|
| PIN-001 | Pin source command catalog to DayOA `13.0.16` | SUCCESS | config_or_startup_contract | Gate 2 | Default ref and four current HIOMRS/Inflection catalog entries pin `13.0.16`; focused contract tests passed | Source catalog updated without fallback |
| PIN-002 | Pin bundled command catalog identically | SUCCESS | config_or_startup_contract | Gate 2 | Source/payload catalog byte parity passed | Bundled payload is identical |
| SELF-001 | Self-pin source and bundled DYEC config to `13.0.4` | SUCCESS | config_or_startup_contract | Gate 2 | Source/payload global-config byte parity passed | Both self-pin fields are `13.0.4` |
| QA-001 | Run focused and full supported-environment tests | SUCCESS | contract_test | Gate 5 | Focused: 40 passed; full: 2,230 passed, 11 skipped; Ruff and `git diff --check` passed | Supported DAY-EC environment green |
| REL-001 | Commit, push branch, and publish annotated `13.0.4` | OPEN | feature_implementation | Gate 5 | Pending | |
| CLOSE-001 | Verify clean tree, tag object type, and remote SHA | OPEN | contract_test | Gate 5 | Pending | |

## Release constraints

- Non-`v` annotated tags only.
- Do not move `13.0.3` or any earlier tag.
- The catalog records DayOA `13.0.16`; it does not silently fall back to an older DayOA ref.
