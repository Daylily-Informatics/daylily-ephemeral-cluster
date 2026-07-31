# DayOA 13.0.104 and DYEC release-train ledger

## Objective

Publish the outstanding HIOMR2 DayOA work as an immutable release, advance all
active DYEC DayOA catalog pins to that release, publish a DYEC pin release, and
then publish a second DYEC release whose source and packaged self-pins reference
the pin release.

## Gate 0 baseline

- DayOA source branch: `codex/remove-hiomr2-prepublish-gates`
- DayOA release: annotated tag `13.0.104`, peeled commit
  `e21fa3f08fa4197da0f960f64d0afdcd2c9dd103`
- DayOA focused proof: `28 passed in 0.48s`; staged diff check passed
- DYEC release base: remote branch
  `codex/dyec-dyoa-13096-pin-20260730t161018z` at `5f5fee80`, containing
  annotated release `16.1.13` plus its post-tag evidence commits
- DYEC release branch: `codex/dyec-dayoa-13104-pin-20260731`
- Planned immutable tags: `16.1.14` for the DayOA pin and `16.1.15` for the
  self-pin
- Existing untracked run, export, recording, backup, and temporary evidence in
  the older DYEC checkout is outside the source-release boundary and remains
  untouched.

## Execution ledger

| ID | Requirement | Status | Evidence |
|---|---|---:|---|
| DAYOA-001 | Commit and push all current DayOA source and ledger changes | SUCCESS | Commit `e21fa3f0` pushed on `codex/remove-hiomr2-prepublish-gates` |
| DAYOA-002 | Create and push annotated DayOA `13.0.104` | SUCCESS | `git cat-file -t 13.0.104` returned `tag`; peeled commit is `e21fa3f0` |
| DYEC-001 | Preserve the outstanding HIOMR2 catalog repair | SUCCESS | Commit `8ddb72f9` pushed on `codex/hiomr2-catalog-repair`; the current 16.1.13 lineage already contains byte-equivalent catalog/test changes |
| DYEC-002 | Advance every active DayOA catalog/test pin to `13.0.104` | SUCCESS | Source and packaged catalogs are byte-identical; all active catalog pins and three contract-test constants now name `13.0.104`; the recorded release commit is `e21fa3f0` |
| DYEC-003 | Run focused DYEC pin-contract tests | SUCCESS | `237 passed in 10.50s`; catalog payload `cmp` and `git diff --check` passed |
| DYEC-004 | Commit, push, tag, and push DYEC `16.1.14` | IN_PROGRESS | Release commit is ready |
| DYEC-005 | Advance source and packaged DYEC self-pins to `16.1.14` | OPEN | |
| DYEC-006 | Commit, push, tag, and push DYEC `16.1.15` | OPEN | |
| VERIFY-001 | Verify clean branch, annotated tag objects, peeled commits, and remote refs | OPEN | |
