# DYEC DayOA 13.0.96 pin and self-pin release ledger

## Objective

Publish a two-release DYEC train from the clean annotated `16.1.11` base:

1. Update every active source, embedded payload, and contract-test DayOA pin
   from `13.0.94` to the immutable DayOA `13.0.96` release.
2. Release DYEC `16.1.12`.
3. Update the DYEC self-pin from `16.1.10` to `16.1.12`.
4. Release DYEC `16.1.13`.

Historical plan records are not rewritten. The source and packaged command
catalogs must remain byte-identical.

## Control ledger

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| INV-001 | Use clean annotated DYEC `16.1.11` as the release base | SUCCESS | Worktree began at commit `5b3ae647e13db2b255db915bb35d4d8b81d81fe6` |
| INV-002 | Verify candidate tags `16.1.12` and `16.1.13` are unused | SUCCESS | Remote tag lookup returned no matching refs before mutation |
| PIN-001 | Update all active DayOA pins to `13.0.96` | SUCCESS | Source catalog, payload catalog, and three contract-test constants now select `13.0.96` |
| PIN-002 | Preserve byte identity between source and payload catalogs | SUCCESS | `cmp` returned RC 0 |
| TST-001 | Run focused repository/catalog/registry/fork contract tests | SUCCESS | 237 focused tests passed in 10.15 seconds |
| REL-001 | Commit, push, and annotate DYEC `16.1.12` | SUCCESS | Annotated tag `16.1.12` peels to commit `844e469256e8724bf0c5aeba03db4326d88e0fbe` |
| SELF-001 | Update source and payload self-pins to `16.1.12` | SUCCESS | Both global YAMLs and `DYEC_BLESSED_TAG` now select `16.1.12`; YAML pair is byte-identical |
| TST-002 | Re-run focused self-pin and repository tests | SUCCESS | 237 focused tests passed in 9.72 seconds |
| REL-002 | Commit, push, and annotate DYEC `16.1.13` | OPEN | Git and remote tag evidence |
| RUN-001 | Use the resulting DayOA `13.0.96` tag explicitly for Take41 | OPEN | Headnode ledger and `day-clone` evidence |

## Acceptance

- No active source or embedded payload pin remains on DayOA `13.0.94`.
- `16.1.12` pins DayOA `13.0.96`.
- `16.1.13` contains the same DayOA pin and self-pins DYEC `16.1.12`.
- Both release tags are annotated, immutable, and peel to their clean release
  commits.
