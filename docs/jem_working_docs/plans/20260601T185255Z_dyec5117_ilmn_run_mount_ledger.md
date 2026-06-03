# dyec5117 Illumina Run Directory Mount Ledger

Date: 2026-06-01

## Objective

Mount the Illumina sequencing run directory `20260514_LH01106_0009_B23TVLGLT4` to the `dyec5117` DayEC cluster for BCL Convert testing.

## Control Ledger

Controlling plan: `docs/plans/20260601T185255Z_dyec5117_ilmn_run_mount_ledger.md`
Ledger path: `docs/plans/20260601T185255Z_dyec5117_ilmn_run_mount_ledger.md`

### Gate 0 Baseline

- Repo: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster`
- Branch at start: `codex/dyec515-full-catalog-20260531...origin/codex/dyec515-full-catalog-20260531`
- Pre-existing dirty files before this task: `AGENTS.md`, `docs/plans/20260601T144201Z_dyec_516_517_release_train_ledger.md`, and untracked `docs/plans/20260601T165015Z_hg003_illumina_*` catalog artifacts.
- Target cluster: `dyec5117`
- Target region/profile: `us-west-2`, AWS profile `lsmc`
- Source S3 URI: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0009_B23TVLGLT4/`
- Mount ID: `20260514_LH01106_0009_B23TVLGLT4`
- Expected FSx API path: `/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/`
- Expected headnode path: `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/`
- Mount mode: read-only run directory DRA, platform `ILMN`.
- Non-destructive boundary: this task may create an FSx DRA mount but must not delete mounts, delete cluster resources, or write into the run mount.

### Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DRA-001 | Cluster inventory | Verify the live `dyec5117` cluster and FSx target before creating the mount. | SUCCESS | feature_implementation | Gate 0: Inventory Freeze | Codex | `dyec --json cluster list --profile lsmc --region us-west-2` showed `dyec5117`; `dyec --json cluster describe --profile lsmc --region us-west-2 --cluster dyec5117` showed `CREATE_COMPLETE`, compute fleet `RUNNING`, headnode `i-0eea51f109f684a5d`; `dyec --json mounts list ...` initially returned `{"mounts": []}`. |  | Cluster and empty managed run-mount state verified before create. |
| DRA-002 | Mount creation | Create or reuse the read-only DRA for the exact run S3 URI under `/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/`. | SUCCESS | feature_implementation | Gate 1: Live Mount Creation | Codex | `dyec --json mounts create s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0009_B23TVLGLT4/ --profile lsmc --region us-west-2 --cluster dyec5117 --mount-id 20260514_LH01106_0009_B23TVLGLT4 --run-id 20260514_LH01106_0009_B23TVLGLT4 --platform ILMN --read-only --batch-import-metadata-on-create --auto-import NEW,CHANGED --wait --timeout-seconds 1200` -> `association_id=dra-0ab55b552007f1d6f`, `fsx_file_system_id=fs-0bce2fa59e4aa5290`, lifecycle `AVAILABLE`. |  | Read-only ILMN run DRA is available. |
| DRA-003 | Mount verification | Verify the headnode-visible path is usable for ILMN run data. | SUCCESS | contract_test | Gate 2: Final Acceptance | Codex | `dyec --json mounts verify --profile lsmc --region us-west-2 --cluster dyec5117 --mount-id 20260514_LH01106_0009_B23TVLGLT4 --platform ILMN --timeout-seconds 600` -> `verified=true`, `usable=true`, path `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4`. SSM inspection on headnode found `SampleSheet.csv`, `RunInfo.xml`, `RunParameters.xml`, `Data/Intensities/BaseCalls`, and lane dirs `L001,L002,L003,L004,L005,L006,L007,L008`. |  | Mounted run root is usable and has expected BCL Convert inputs. |
| DRA-004 | Reporting | Report association id, mount path, and any blockers. | SUCCESS | feature_implementation | Gate 2: Final Acceptance | Codex | Final ledger report below. |  | No blockers remain. |

### Working Notes

- `dyec mounts create` is the expected supported path for run-folder mounts.
- `dyec mounts verify` is headnode-only and should prove the `/fsx/run_dir_mounts/...` path from the target cluster.

### Final Report

- Terminal ledger rows: 4 `SUCCESS`, 0 `BLOCKED`, 0 `FAIL`, 0 working.
- Objective completion: complete.
- Cluster: `dyec5117` in `us-west-2`, headnode `i-0eea51f109f684a5d`.
- DRA: `dra-0ab55b552007f1d6f`.
- FSx: `fs-0bce2fa59e4aa5290`.
- Source S3 URI: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0009_B23TVLGLT4/`.
- Headnode path: `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/`.
- Verification: `dyec mounts verify` returned `verified=true`; direct headnode inspection found `SampleSheet.csv`, `RunInfo.xml`, `RunParameters.xml`, `Data/Intensities/BaseCalls`, and lanes `L001` through `L008`.
- Safety boundary: created a read-only DRA only; no mount deletion, cluster deletion, Slurm action, or writes to the run mount were performed.
