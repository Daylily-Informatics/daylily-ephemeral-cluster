# DayOA and DYEC breaking-major prerelease ledger

Created: 2026-08-14T12:39:48Z

## Objective

Reconcile the preceding 12 hours of DayOA and DYEC release work, verify DYEC
17.0.29 is pinned to DayOA 14.0.22, promote both complete release trains to
`lsmc-bio` main through normal pull requests, and publish the merged main
commits as breaking-major prereleases DayOA 15.0.0 and DYEC 18.0.0.

## Inventory and orphan audit

- DayOA annotated tag `14.0.22` peels to
  `c0f8d4f16a2f123c0740c7743b504e0f4e7caac2`. Its post-tag release-evidence
  commit `741a10ea6b8a1f135ae37319060b722a4655ec26` was included in PR 109.
- DYEC annotated tag `17.0.29` peels to
  `e1a56a46ef06452126800ca43d306505c0805fce`. Its post-tag release-evidence
  commit `3dc3f12282e8ff12dec85d3b2f8bf7f05fc0a86f` is the promotion head.
- Recent DayOA worktrees have no uncommitted source changes; every recent
  source commit is contained by the promoted release train.
- Generated Bjuice manifests in operational DYEC worktrees are preserved as
  untracked run artifacts and are not release source.
- The dirty CG export ledger content from the older operational checkout is
  already present in `17.0.29`. Its catalog run record is also present. The
  proposed command-level evidence prefix is intentionally absent because the
  prefix is a DRA analysis export and does not contain the command-test receipt
  files required by `validation_evidence_s3_uri_prefix`.
- Commit `9184d1e0d7ff959d652e5578ccd14e4d611f4d9b` updated the now-retired
  `20260814T112116Z` ONT release ledger. DYEC 17.0.29 intentionally removes
  that intermediate ledger and supersedes it with
  `20260814T120856Z_dyec_17_0_29_immutable_dayoa_controller_release_ledger.md`;
  the deleted file is not reintroduced.

## Ledger

| ID | Action | State | Evidence |
|---|---|---|---|
| DAYOA-PR | Promote 14.0.22 release train to main | SUCCESS | PR 109; merge `5f00d136de0a0082b94115762a6f03df4521ba98` |
| DAYOA-1500 | Publish annotated breaking-major prerelease | SUCCESS | tag object `ea4831faa6082e79ac8138217caf3f0ea9fad924`; peeled merge `5f00d136de0a0082b94115762a6f03df4521ba98` |
| DYEC-1729 | Verify 17.0.29 uniformly pins DayOA 14.0.22 | SUCCESS | tag object `1059c2bc995e20a4ca0b67aed2f94d5e5d94e154`; peeled release `e1a56a46ef06452126800ca43d306505c0805fce`; source/payload SHA-256 `a270199257864fb29bb98d1132898deb40f8df248b33646998d3072d7b50f587` |
| ORPHAN-AUDIT | Reconcile recent source and worktree state | SUCCESS | unique work promoted; redundant operational files preserved; retired ledger supersession documented above |
| DYEC-PR | Promote 17.0.29 release train to main | IN_PROGRESS | branch `codex/dyec-17.0.29-main-promotion` |
| DYEC-1800 | Publish annotated breaking-major prerelease | PENDING | waits for normal PR merge and exact merged-main commit |

The running Bjuice controller, Slurm jobs, analysis root, export monitor, and
Slack thread are outside this source-release lane and are not modified here.
