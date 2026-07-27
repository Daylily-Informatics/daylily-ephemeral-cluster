# Bjuice Preval-20 HIOMR2 input-mount ledger

Created: 2026-07-26T03:55:09Z  
Scope: Create and verify the two specified **read-only** FSx DRA input mounts
for the Bjuice Preval-20 HIOMR2 experiment. This ledger does not stage
manifests, launch DayOA, alter Slurm, or change data in S3.

Controlling note: `mount_preval_bjuice.md`  
Ledger path: `docs/plans/20260726T035509Z_bjuice_preval20_hiomr2_mounts_ledger.md`

## Gate 0: inventory and baseline

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch: `jem-candidate-260725`
- Baseline: the worktree contains pre-existing untracked plans, reports,
  recordings, temporary directories, `mount_preval_bjuice.md`, and other
  artifacts; none will be changed by this operation.
- Mount source contract:
  - Illumina: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/`
    -> `/fsx/run_dir_mounts/20260618_LH01106_0011_A23MFMCLT3/`
  - ONT: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/`
    -> `/fsx/run_dir_mounts/pca100-2026/`
- Both associations must be read-only, import metadata, use a 3600-second
  wait, and must not be duplicated while an existing association is creating.
- Live limit at ledger creation: the target cluster and existing mount state
  must be discovered and verified before any create operation.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| MNT-001 | DYEC / cluster inventory | Identify the target live cluster, its FSx file system, and whether either exact mount already exists. | SUCCESS | feature_implementation | Gate 0 | Codex | `dyec --json cluster-info --region us-west-2 --profile lsmc` -> `preval-hiomr2` (`UPDATE_COMPLETE`); `dyec --json mounts list --cluster preval-hiomr2 --region us-west-2 --profile lsmc` -> `[]`. |  | Target resolved; neither required mount exists. |
| MNT-002 | Illumina DRA | Create or verify the exact read-only eight-lane Illumina source mount. | SUCCESS | feature_implementation | Gate 1 | Codex | `dra-0e852587af67279b2` on `fs-0ce0851156199113a`: lifecycle `AVAILABLE` at 2026-07-26T04:16:36Z; correct source/target; read-only, no auto-export, batch metadata import enabled. |  | Association created without duplication. |
| MNT-003 | ONT DRA | Create or verify the deliberate read-only `pca100/2026/` parent mount, covering all 15 cells for 20 samples. | SUCCESS | feature_implementation | Gate 1 | Codex | `dra-07571825f38c091e3` on `fs-0ce0851156199113a`: lifecycle `AVAILABLE` at 2026-07-26T04:38:17Z; local projection present; correct source/target; read-only, no auto-export, batch metadata import enabled. |  | Association created without duplication. |
| MNT-004 | Headnode verification | Verify both mount paths are usable from the selected cluster headnode. | SUCCESS | feature_implementation | Gate 1 | Codex | `dyec mounts verify` succeeded for Illumina `/fsx/run_dir_mounts/20260618_LH01106_0011_A23MFMCLT3/` and ONT `/fsx/run_dir_mounts/pca100-2026/`; both DRA lifecycles `AVAILABLE`. |  | Both required input mount paths are usable on the `preval-hiomr2` headnode. |

## Final report

All rows terminal: yes  
Objective complete: yes

Status counts:
- SUCCESS: 4
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0

The initial verification attempt during DRA creation failed as expected because
the path was not yet projected. The post-availability retry passed; no mount
was recreated, altered, or deleted.
