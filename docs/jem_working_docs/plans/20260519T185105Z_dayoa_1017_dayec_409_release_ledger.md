# DayOA 1.0.17 / DayEC 4.0.9 Release Ledger

## Gate 0

- DayOA repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`
- DayOA release branch: `codex/multi-fastq-catalog-validation`
- DayOA release commit: `c654bd9 Honor skip-budget clusters in dyoainit`
- DayOA tag: `1.0.17`
- DayEC repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
- DayEC release branch: `codex/analysis-id-export-catalog-validation`
- Previous DayEC release tag: `4.0.8`
- Target DayEC release tag: `4.0.9`

## Tracking Rows

| ID | Area | Requirement | Status | Evidence | Terminal Note |
| --- | --- | --- | --- | --- | --- |
| REL-001 | DayOA | Create and push annotated DayOA tag `1.0.17`. | SUCCESS | `git tag -a 1.0.17 -m "1.0.17"`; `git push origin 1.0.17`. | DayOA fix for skip-budget `dyoainit` is published. |
| REL-002 | DayEC pins | Update DayOA catalog/default/docs pins to `1.0.17`. | SUCCESS | Source and packaged catalog updated; active docs/tests updated; `rg -n "1\.0\.16"` returned no active refs outside historical plan files; catalog mirror `cmp=0`; focused pytest passed `104 passed`. | Ready for release commit. |
| REL-003 | DayEC self-version | Update DayEC bootstrap config pins to `4.0.9`. | SUCCESS | Source and packaged `daylily_cli_global.yaml` updated; active scan for `4.0.8` returned no active refs outside historical plan files; CLI global mirror `cmp=0`; `git diff --check` clean. | Ready for release commit and tag. |
| REL-004 | DayEC release | Commit, push, tag `4.0.9`, and push tags. | READY | Validation complete; release commit and annotated tag `4.0.9` are the next release actions. | Final push/tag evidence is recorded in the release closeout response. |
