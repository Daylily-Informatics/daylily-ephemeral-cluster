# BCL L003 Tile-Smoke 16/4 Experiment Ledger

Created: `2026-06-03T08:08:03Z`

## Objective

Preserve the completed L003 8-tile `tile_smoke` DayOA BCL Convert configuration, then run the same L003 `/dev/shm`/O_DIRECT-off `tile_smoke` experiment with 16 selected tiles and 4 selected tiles. Each experiment must use a fresh workset, a fresh DRA-backed output directory, `dy-r`, `-T 0`, and distinct evidence.

## Gate 0 Inventory

| Item | Value |
|---|---|
| Cluster | `dyec0602bcl` |
| Region/profile | `us-west-2` / `lsmc` |
| Headnode | `i-0c36c39770c533c8e` |
| Source run dir | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4` |
| Source S3 | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0009_B23TVLGLT4/` |
| Flowcell/run class | `25B`; `RunParameters.xml` has `FlowCell Name=25B`, `RecipeName=25B Sequencing` |
| Lane | `L003` |
| DayOA branch/commit | `codex/dayoa-bclconvert-tile-shards-20260601` / `a0c3a81` |
| Baseline 8-tile config | `docs/plans/20260603T080803Z_bcl_l003_tilesmoke_4_16_configs/bclconvert_l003_8tile_tilesmoke_i192bigmem_devshm_20260603T0740Z.yaml` |
| Baseline 8-tile S3 visibility | `161` objects, `84` `.fastq.gz`, `6102998592` bytes, done/report markers present |
| Current Slurm state at baseline retrieval | no `ubuntu` jobs in `squeue` |
| Existing relevant tmux sessions | `dayoa_bcl_l003_8tile_tilesmoke_20260603`, `bcl2fq_scratch_dra_20260603T011121Z` |
| Local DYEC branch | `codex/dyec515-full-catalog-20260531` |
| Local DYEC dirty state | pre-existing untracked benchmark/ledger artifacts are present; this phase only owns files under this ledger/config directory |

## Execution Contract

Use DayOA only from initialized persistent `ubuntu` tmux sessions:

```bash
cd /fsx/analysis_results/dyec0602bcl/<workset>/daylily-omics-analysis
source dyoainit
dy-a slurm hg38
dy-r produce_bclconvert_fastqs -p -k -j 10 -T 0 --rerun-triggers mtime --configfile config/<config>.yaml -n
dy-r produce_bclconvert_fastqs -p -k -j 10 -T 0 --rerun-triggers mtime --configfile config/<config>.yaml
```

Do not invoke `snakemake` directly. Do not reuse the completed 8-tile output directory. Do not merge tile FASTQs or lane FASTQs.

## Tracking Rows

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| BASE-001 | Baseline | Save exact successful 8-tile config in repo docs/plans. | SUCCESS | feature_implementation | Gate 0 | Orchestrator | Saved config at `docs/plans/20260603T080803Z_bcl_l003_tilesmoke_4_16_configs/bclconvert_l003_8tile_tilesmoke_i192bigmem_devshm_20260603T0740Z.yaml`. |  | Exact headnode YAML preserved. |
| S3-001 | Baseline | Confirm completed 8-tile L003 outputs are visible in S3. | SUCCESS | monitoring | Gate 0 | Monitor | S3 prefix has `161` objects, `84` `.fastq.gz`, `6102998592` bytes; marker/report objects present. |  | DRA auto-export completed for the successful 8-tile smoke output. |
| CFG-016 | Config | Create 16-tile config derived only by changing run id and tile limit. | OPEN | feature_implementation | Gate 1 | Headnode Agent |  |  |  |
| CFG-004 | Config | Create 4-tile config derived only by changing run id and tile limit. | OPEN | feature_implementation | Gate 1 | Headnode Agent |  |  |  |
| DRY-016 | Dry-run | Run 16-tile dry-run via `dy-r`; confirm one L003 tile-smoke job and no full-lane job. | OPEN | feature_implementation | Gate 2 | Runner |  |  |  |
| LIVE-016 | Live run | Run 16-tile live job via `dy-r` with `-T 0`. | OPEN | feature_implementation | Gate 3 | Runner |  |  |  |
| ACC-016 | Acceptance | Confirm 16-tile outputs, marker files, S3 visibility, and benchmark. | OPEN | monitoring | Gate 4 | Acceptance |  |  |  |
| DRY-004 | Dry-run | Run 4-tile dry-run via `dy-r`; confirm one L003 tile-smoke job and no full-lane job. | OPEN | feature_implementation | Gate 2 | Runner |  |  |  |
| LIVE-004 | Live run | Run 4-tile live job via `dy-r` with `-T 0`. | OPEN | feature_implementation | Gate 3 | Runner |  |  |  |
| ACC-004 | Acceptance | Confirm 4-tile outputs, marker files, S3 visibility, and benchmark. | OPEN | monitoring | Gate 4 | Acceptance |  |  |  |

## Pause Note

At `2026-06-03T08:09:31Z`, user redirected the active work to repeat the successful 8-tile experiment with `shared_thread_odirect_output: true` and compare `/dev/shm` vs `/scratch` staging. The 16-tile and 4-tile rows remain unmodified and are intentionally not being executed until explicitly resumed.

## Planned Output Directories

| Tiles | Run ID / DRA directory name |
|---:|---|
| 16 | `fasts_from_bclconvert_l003_16tile_tilesmoke_i192bigmem_devshm_20260603T080803Z` |
| 4 | `fasts_from_bclconvert_l003_4tile_tilesmoke_i192bigmem_devshm_20260603T080803Z` |

## Acceptance Notes

- `tile_shard_level` remains `tile_smoke`.
- `tile_shard_lanes` remains `"3"`.
- `shared_thread_odirect_output` remains `false`.
- `scratch_output_root` remains `/dev/shm/dayoa_bclconvert`.
- `scratch_available_bytes_min` remains `650000000000`.
- `partition` remains `i192bigmem`.
- `threads` and `tile_shard_threads` remain `192`.
