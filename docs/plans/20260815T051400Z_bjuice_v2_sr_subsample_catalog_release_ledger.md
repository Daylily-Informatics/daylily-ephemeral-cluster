# Bjuice v2 SR subsample catalog release ledger

| Field | Value |
|---|---|
| Opened | 2026-08-15 UTC |
| Baseline | DYEC `18.0.4`, DayOA command pin `15.0.1` |
| DayOA repair | `15.0.2`, PR #112 / commit `1a390cf17f27dc7bd0d8172ecf91cdce233ad21a` |
| Scope | Pin only the literal Bjuice v2 multi-AU catalog command to the repaired DayOA release and preserve controller immutability checks. |

## Required changes

- The literal Bjuice v2 multi-AU command must pin `validated_version` and `git_tag` to DayOA `15.0.2` in both source and packaged catalogs.
- The controller must accept only the closed list of DayOA-generated workflow report files (`pipeline_details.md`, planned/final report pairs, and timestamped checkpoint report pairs). It must still reject all other untracked files and all tracked-source mutations.
- Verify source/payload byte parity and focused catalog/controller tests before an annotated DYEC release tag.
- A new DYEC-tagged dry run must show every generated `SUBSAMPLE_PCT` is routed to the repaired DayOA rule before live launch.

## Progress

| Item | Status |
|---|---|
| DayOA `15.0.2` available | complete |
| Catalog pin and controller report allowlist | in progress |
| DYEC tests and release | pending |
| Fresh catalog dry run | pending |
| Fresh live run / export | pending |
