# BCL L003 16-Shard i192bigmem devshm O_DIRECT 48-Thread Ledger

Created: `2026-06-03T08:56:44Z`

## Objective

Run full lane `L003` from `20260514_LH01106_0009_B23TVLGLT4`, split into exactly `16` tile shards. Use the DayOA `dy-r` contract only, stage each shard under compute-node `/dev/shm`, pass `--shared-thread-odirect-output true`, use the 48-thread BCL Convert profile, and avoid hardcoded 192-thread or exclusive-node placement.

## Gate 0 Inventory

| Item | Value |
|---|---|
| Cluster | `dyec0602bcl` |
| Headnode | `i-0c36c39770c533c8e` |
| Region/profile | `us-west-2` / `lsmc` |
| Run dir | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4` |
| Sample sheet | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/SampleSheet.csv` |
| Output run id | `fasts_from_bclconvert_l003_16shard_i192bigmem_devshm_odirect48_20260603T085644Z` |
| DRA output | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/fasts_from_bclconvert_l003_16shard_i192bigmem_devshm_odirect48_20260603T085644Z` |
| Config | `docs/plans/20260603T085644Z_bcl_l003_16shard_i192bigmem_devshm_odirect48_configs/bclconvert_l003_16shard_i192bigmem_devshm_odirect48_20260603T085644Z.yaml` |
| DayOA source branch | `codex/dayoa-bclconvert-tile-shards-20260601` |
| DayOA source commit | `e3aefaf` |
| DayOA code change | `bclconvert.exclusive` is config-driven; focused test `python -m pytest tests/test_bclconvert_multiqc.py -q -> 13 passed` |
| Current bcl2fq job | Job `63` is unrelated; leave running/queued untouched |
| i192bigmem inventory | `i192bigmem-dy-all-1` was `idle~` at Gate 0 |
| Fit estimate | Prior 8-shard L003 output shard was `84.60 GB`; 16-shard estimate is `42.30 GB/shard`, `126.90 GB` for 3 concurrent shards |
| Prior `/dev/shm` free evidence | Bigmem shard log observed about `1.28 TB` available under `/dev/shm` |

## Execution Contract

Use a fresh headnode workset and persistent `ubuntu` tmux session:

```bash
cd /fsx/analysis_results/dyec0602bcl/bcl_l003_16shard_i192bigmem_devshm_odirect48_20260603T085644Z/daylily-omics-analysis
source dyoainit
dy-a slurm hg38
dy-r produce_bclconvert_fastqs -p -k -j 10 -T 0 --rerun-triggers mtime --configfile config/bclconvert_l003_16shard_i192bigmem_devshm_odirect48_20260603T085644Z.yaml -n
dy-r produce_bclconvert_fastqs -p -k -j 10 -T 0 --rerun-triggers mtime --configfile config/bclconvert_l003_16shard_i192bigmem_devshm_odirect48_20260603T085644Z.yaml
```

Do not invoke `snakemake` directly. Do not touch unrelated jobs/controllers. Do not fall back to another partition or staging root.

## Requested Config Contract

| Key | Value |
|---|---|
| `partition` | `i192bigmem` |
| `exclusive` | `""` |
| `threads` | `48` |
| `tile_shard_threads` | `48` |
| `mem_mb` / `tile_shard_mem_mb` | `500000` to target roughly 3 shards per bigmem node |
| `scratch_output_root` | `/dev/shm/dayoa_bclconvert` |
| `tmpdir` | `/dev/shm/dayoa_bclconvert_tmp` |
| `scratch_available_bytes_min` | `100000000000` |
| `tile_shard_level` | `16` |
| `tile_shard_lanes` | `"3"` |
| `shared_thread_odirect_output` | `true` |
| `merge_tile_fastqs` / `merge_lane_fastqs` | `false` / `false` |

## Tracking Rows

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| SRC-001 | DayOA | Remove hardcoded BCL Slurm exclusivity so 48-thread shards can share a bigmem node by config. | SUCCESS | feature_implementation | Gate 1 | Repo/DayOA Agent | DayOA commit `e3aefaf`; `BCL_EXCLUSIVE = str(BCLCFG.get("exclusive", "--exclusive") or "")`; tests `13 passed`. |  | BCL rules are config-driven; this run sets `exclusive: ""`. |
| CFG-001 | Config | Save a 16-shard L003 `/dev/shm` O_DIRECT-on 48-thread config. | SUCCESS | feature_implementation | Gate 1 | Orchestrator | Config saved under `docs/plans/20260603T085644Z_bcl_l003_16shard_i192bigmem_devshm_odirect48_configs/`. |  | Config sets no hardcoded `192` thread value. |
| FIT-001 | Capacity | Check if 3 concurrent 16-way shards should fit in `/dev/shm`. | SUCCESS | monitoring | Gate 1 | Monitor | Prior 8-shard output size `84.60 GB`; estimated 16-shard output `42.30 GB/shard`, 3 shards `126.90 GB`; prior bigmem `/dev/shm` availability about `1.28 TB`. |  | Fit estimate supports the requested plan; live preflight still checks compute-node free bytes. |
| PREP-001 | Workset | Prepare fresh headnode workset from pushed DayOA source commit `e3aefaf`. | SUCCESS | feature_implementation | Gate 2 | Headnode Agent | Workset `/fsx/analysis_results/dyec0602bcl/bcl_l003_16shard_i192bigmem_devshm_odirect48_20260603T085644Z/daylily-omics-analysis`; cloned from GitHub branch `codex/dayoa-bclconvert-tile-shards-20260601`; config installed at `config/bclconvert_l003_16shard_i192bigmem_devshm_odirect48_20260603T085644Z.yaml`; DRA output dir created as `ubuntu:ubuntu`. |  | Fresh workset prepared from pushed source. |
| DRY-001 | Dry-run | Run dry-run through `dy-r` and verify exactly 16 `run_bclconvert_tile_shard` jobs for `L003`. | SUCCESS | feature_implementation | Gate 3 | Runner | Tmux `dayoa_bcl_l003_16shard_48devshm_20260603`; marker `__DRY_BCL16_48DEVSHM_RC__0`; `tile_rule_count=16`, `lane_rule_count=0`, `threads48_count=16`, `partition_i192bigmem_count=18`, `exclusive_empty_count=19`. Shards: `0001_tiles0001-0049` through `0016_tiles0736-0784`. |  | Dry-run accepted the requested 16-shard, 48-thread, non-exclusive config. |
| LIVE-001 | Live run | Launch live `dy-r` with `-j 10 -T 0`. | SUCCESS | feature_implementation | Gate 4 | Runner | Live command launched in tmux `dayoa_bcl_l003_16shard_48devshm_20260603`; marker `__LIVE_BCL16_48DEVSHM_RC__0`; first wave jobs `64-67` and subsequent shard jobs completed on `i192bigmem-dy-all-1`. |  | Live run completed with no scheduler intervention. |
| MON-001 | Monitor | Track Slurm, tmux, shard logs, `/dev/shm` preflight, output counts, and benchmark TSVs. | SUCCESS | monitoring | Gate 4 | Monitor | Final snapshot `2026-06-03T10:19:32Z`: `16` shard logs started, `16` `Conversion Begins`, `16` `Conversion Complete`, `16` move events, `16` finished logs, `1344` FASTQs, `16` tile done markers, `16` shard benchmark TSVs, `601951490190` DRA bytes; `/dev/shm` preflight showed `1278242455552` bytes free and minimum `100000000000`. |  | Passive monitoring only; no kill/cancel/requeue/drain/resume action. |
| ACC-001 | Acceptance | Confirm 16 shard benchmarks, `84` sample FASTQs per shard class where expected, lane reports, no merged tile/lane FASTQs, and DRA/S3 visibility. | SUCCESS | monitoring | Gate 5 | Acceptance | DRA: `1344` FASTQs, `16` tile done markers, `18` total done markers, `16` BCL benchmark TSVs. Benchmark summary: min `239.8524s`, median `320.81465s`, max `371.6868s`, slowest `0008_tiles0344-0392` at `0:06:11`, fastest `0009_tiles0393-0441` at `0:03:59`, total task cost `1.387946`. S3: `2111` objects, `1344` FASTQs, `601947722894` bytes. |  | 16-shard L003 O_DIRECT-on `/dev/shm` run accepted. |
