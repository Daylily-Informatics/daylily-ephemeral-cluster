# Recent Sequencing Run DRA Mount Ledger

Created: 2026-08-10T16:08:46Z
Scope: create, wait for, and verify three **read-only** FSx DRA mounts on
`prod-cand-260809` for later catalog RunQC use. This task does not create an
analysis root, stage manifests, launch DayOA/SeqQC, modify Slurm, write to S3,
or detach/delete any data repository association.

Controlling request: mount an actual Bjuice-preval Illumina run, a Bjuice-preval
ONT run, and a complete-seeming Ultima run for later DYEC sequencing-QC catalog
pipelines.

## Gate 0: inventory and baseline

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`.
- Existing worktree changes are user-owned and out of scope; this ledger is the
  only record created by this operation.
- Live target: `prod-cand-260809`, `UPDATE_COMPLETE`, `us-west-2`, profile
  `lsmc`; `dyec mounts list` initially returned no managed mounts.
- Selected immutable S3 input prefixes:
  - ILMN Bjuice-preval: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/`.
    It contains `RunInfo.xml`, `RunParameters.xml`, `SampleSheet.csv`,
    `RTAComplete.txt`, `Manifest.tsv`, and BCL/InterOp analysis directories.
  - ONT Bjuice-preval: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set4-FC1/`.
    This is the reviewed Bjuice Set4-FC1 source (HG002 is barcode15).
  - Ultima: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/RUN602202/2026/602202-20260512_1805/`.
    The prior source inventory recorded 9,541 objects and a run-level
    `602202_LibraryInfo.xml`; live listing confirms diverse sample prefixes.
- Mount contract: `--read-only`, metadata import enabled, no auto-export,
  purpose `run`, and a 5,400-second wait budget. No existing association may
  be duplicated while creating.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| MNT-001 | Live inventory | Resolve target cluster, current managed mounts, and three exact input prefixes. | SUCCESS | legitimate_safety_handling | Gate 0 | Codex | `dyec cluster-info`, `dyec mounts list`, and read-only S3 listings at ledger creation. |  | Baseline frozen. |
| MNT-002 | ILMN DRA | Create and await the read-only Bjuice-preval Illumina run mount. | SUCCESS | feature_implementation | Gate 1 | Codex | `dra-0fd9d1dbc1b329805` reached `AVAILABLE`; `dyec mounts verify` passed for `/fsx/run_dir_mounts/bjuicepreval-20260618-ilmn/`. |  | Mount is headnode-usable. |
| MNT-003 | ONT DRA | Create and await the read-only Bjuice-preval Set4-FC1 mount. | SUCCESS | feature_implementation | Gate 1 | Codex | `dra-0c1ad269bb841a34e` reached `AVAILABLE`; `dyec mounts verify` passed for `/fsx/run_dir_mounts/bjuicepreval-20260615-ont-set4-fc1/`. |  | Mount is headnode-usable. |
| MNT-004 | Ultima DRA | Create and await the read-only full-run Ultima mount. | SUCCESS | feature_implementation | Gate 1 | Codex | `dra-02af97c809a9fadd6` reached `AVAILABLE`; `dyec mounts verify` passed for `/fsx/run_dir_mounts/ultima-602202-20260512/`. |  | Mount is headnode-usable. |
| MNT-005 | Mount verification | Verify each AVAILABLE mount on the target headnode; do not launch QC. | SUCCESS | contract_test | Gate 1 | Codex | `dyec mounts verify` passed for the ILMN, ONT, and Ultima mount IDs. |  | All three requested mounts are headnode-usable; no QC workflow was launched. |

## Final report

All rows terminal: yes
Objective complete: yes

Status counts:
- SUCCESS: 5
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0

## Monitoring handoff

Heartbeat automation `monitor-recent-sequencing-dra-mounts` was paused at the
user's request on 2026-08-10T16:16:24Z. No scheduled task remains active in
this thread. The three DRA associations are left intact in their observed
creation state; resume monitoring only after explicit user permission.
