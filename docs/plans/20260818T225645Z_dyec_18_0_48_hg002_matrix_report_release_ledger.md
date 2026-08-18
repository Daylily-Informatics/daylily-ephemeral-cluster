# DYEC 18.0.48 HG002 matrix-report release ledger

## Objective

Publish the validated HG002 Bjuice matrix-report visualization update as a clean DYEC patch release based on `18.0.47`, without including unrelated state from the primary DYEC checkout or old DayOA worktrees.

## Gate 0 baseline

- Repository: `lsmc-bio/daylily-ephemeral-cluster`
- Clean release baseline: annotated tag `18.0.47`, commit `6c034972727769ddc376791d15ddd1a76f84f019`
- Report source branch: `codex/hg002-bjuice-native-sr-matrix-report`
- Report source commit: `f16518c9` (`Update HG002 Bjuice matrix visualizations`), pushed to `origin`
- Release branch: `codex/release-18.0.48-hg002-matrix-report`
- Release target: annotated non-v tag `18.0.48`
- DayOA catalog/default pin inherited unchanged from `18.0.47`: `15.0.27`
- Exclusions: dirty primary DYEC checkout, its unrelated documentation/runtime artifacts, and old DayOA worktree changes.

## Execution ledger

| ID | Work | Status | Evidence | Acceptance |
|---|---|---|---|---|
| BASE-001 | Inventory the release baseline and exclusions. | SUCCESS | Remote `18.0.47` resolves to annotated tag object `1a3b0c33be2c2bc2b62e4f4f7da7f68f362d2b37` and commit `6c034972727769ddc376791d15ddd1a76f84f019`; clean isolated release worktree created from that commit. | Release starts from the current pushed DYEC tag and excludes unrelated worktree state. |
| REPORT-001 | Commit and push the validated HG002 matrix-report changes. | SUCCESS | Commit `f16518c9` pushed to `origin/codex/hg002-bjuice-native-sr-matrix-report`; six intended report/generator/checksum paths changed. | The report work has an independently reviewable source commit. |
| RELEASE-001 | Integrate the report update and its report-only prerequisite capsule on the clean release branch. | SUCCESS | Cherry-pick recorded as `c544af73`; the self-contained report, assets/evidence, and generator directories were then synchronized exactly from pushed source commit `f16518c9`. No source, catalog, infrastructure, or unrelated documentation paths were imported. | Release branch contains the `18.0.47` baseline plus the complete reproducible report update only. |
| VERIFY-001 | Validate generator syntax, generated-report reproducibility, checksums, and patch hygiene. | SUCCESS | Focused rebuild completed with 32 retained observations (12 prior plus 20 E4), 23 figures, and 13 tables; regenerated report tree compares exactly with source commit `f16518c9`; Python compilation and `git diff --check` passed. Per operator direction, no repository test suite was run. | Generator completes; Python compilation, checksum comparison, and `git diff --check` pass. |
| PUBLISH-READY-001 | Prepare the exact clean commit for release-branch push and annotated tag `18.0.48`. | SUCCESS | All intended report paths and this ledger are staged from the clean `18.0.47` release worktree; DayOA pins remain `15.0.27`; no unrelated primary-worktree state is present. Remote branch/tag verification is reported in the final handoff after publication. | The final clean commit is ready to receive the immutable annotated release tag. |

## Explicit non-goals

- No DayOA source, release, or tag changes.
- No controller, Slurm, FSx, S3, cluster, or deployment operations.
- No inclusion of unrelated primary-checkout changes.
- No package-index publication; this request covers the Git branch and release tag.
