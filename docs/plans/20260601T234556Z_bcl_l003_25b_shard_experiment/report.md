# 25B NovaSeq X Lane003 BCL Convert Sharding Experiment Report

Run ID: `20260514_LH01106_0009_B23TVLGLT4`
Experiment stamp: `20260601T234556Z`

## BCL Convert Summary

BCL Convert metrics exclude downstream tile-shard merge and lane-ready sentinel benchmarks.

| Arm | Shard level | Tasks | Critical wall min | Total task cost | CPU eff % | Max RSS GiB | Tail ratio | Full 8-lane cost | Full 8-lane parallel min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `shard002` | 2 | 2 | 25.30 | 0.6601 | 24.4 | 86.2 | 1.01 | 5.2812 | 25.30 |
| `shard004` | 4 | 4 | 12.32 | 0.5911 | 25.5 | 104.3 | 1.14 | 4.7290 | 12.32 |
| `shard008` | 8 | 8 | 6.63 | 0.6576 | 23.1 | 99.4 | 1.04 | 5.2611 | 6.63 |
| `shard016` | 16 | 16 | 12.12 | 2.2848 | 5.8 | 89.7 | 1.06 | 18.2787 | 12.12 |
| `shard032` | 32 | 32 | 11.42 | 3.7777 | 3.5 | 84.8 | 1.07 | 30.2215 | 11.42 |
| `whole_lane_odirect_off` | lane | 1 | 60.14 | 3.1705 | 4.9 | 253.7 | 1.00 | 25.3642 | 60.14 |

## Arms Without BCL Benchmarks

- `whole_lane` produced no `run_bclconvert.L003*.bench.tsv`; see `harvested_benchmarks/whole_lane/log_extracts.txt`.

## FASTQ Accounting

Unmerged FASTQ totals use `tile_fastqs` for sharded arms and `lane_fastqs` for whole-lane arms. `Unassigned` is the `Undetermined_S0` subset of the unmerged total.

| Arm | Unmerged FASTQ files | Unmerged FASTQ GiB | Unassigned files | Unassigned GiB | Assigned GiB | Lane FASTQ GiB |
|---|---:|---:|---:|---:|---:|---:|
| `shard002` | 168 | 559.95 | 4 | 117.67 | 442.29 | 442.29 |
| `shard004` | 336 | 559.95 | 8 | 117.67 | 442.29 | 442.29 |
| `shard008` | 672 | 559.95 | 16 | 117.67 | 442.29 | 442.29 |
| `shard016` | 1344 | 559.95 | 32 | 117.67 | 442.29 | 442.29 |
| `shard032` | 2688 | 559.96 | 64 | 117.67 | 442.29 | 442.29 |
| `whole_lane_odirect_off` | 84 | 560.77 | 2 | 117.86 | 442.91 | 560.77 |

## Planned Final Arms

- `shard008_odirect_off`: planned with `merge_lane_fastqs=false`, `shared_thread_odirect_output=false`, default shard008 tile flags, `-j 384`. Not launched because the prelaunch FSx capacity gate failed: `701.85 GiB` available versus `1105.19 GiB` required.
- `shard008_cpu_tuned_odirect_off`: planned serially after `shard008_odirect_off`, with `merge_lane_fastqs=false`, `shared_thread_odirect_output=false`, `tile_parallel_tiles=12`, `tile_conversion_threads=2`, `tile_compression_threads=16`, `tile_decompression_threads=8`, `tile_shard_threads=48`, `-j 384`.

## shard016 Decision

shard016 eligible=true; shard008_vs_shard004_faster_pct=46.165; cost_ok=true; tail_ok=true; cpu_ok=true.


## Merge Benchmarks

| Arm | Merge min | Merge cost | CPU eff % | io_in | io_out |
|---|---:|---:|---:|---:|---:|
| `shard002` | 8.78 | 0.002417 | 89.99 | 194256.12 | 427140.59 |
| `shard004` | 10.54 | 0.002893 | 90.68 | 396711.00 | 442301.60 |
| `shard008` | 11.45 | 0.003143 | 85.88 | 448104.07 | 448042.32 |
| `shard016` | 12.36 | 0.003395 | 75.72 | 450802.98 | 450752.72 |
| `shard032` | 15.06 | 0.004135 | 60.74 | 445556.57 | 445549.79 |
