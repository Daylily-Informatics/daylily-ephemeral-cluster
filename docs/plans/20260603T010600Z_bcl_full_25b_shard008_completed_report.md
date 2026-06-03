# BCL Full 25B Shard008 Completed Report

Generated: 2026-06-03T01:06:53Z

## Status

- Cluster: dyec5117
- Run: 20260514_LH01106_0009_B23TVLGLT4
- Mode: full-flowcell shard008, no FASTQ merge, ODIRECT disabled
- Workflow controller: completed with RETURN CODE: 0
- squeue pipe status checked: PIPESTATUS 0 0, squeue lines 0
- Active controller/process status: no Snakemake/day-run/BCL Convert process running
- Phase 3 exact manifest paths deleted and verified absent
- Current /fsx after cleanup: 6.6T size, 3.2T used, 3.5T available, 48% used

## Local Evidence

- Evidence root: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster/bench_expts/full25b_shard008_lane_batched_resume_20260602T203117Z`
- Final lane totals TSV: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster/bench_expts/full25b_shard008_lane_batched_resume_20260602T203117Z/final_lane_fastq_totals.tsv`
- Final shard totals TSV: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster/bench_expts/full25b_shard008_lane_batched_resume_20260602T203117Z/final_shard_fastq_totals.tsv`
- Final benchmark index TSV: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster/bench_expts/full25b_shard008_lane_batched_resume_20260602T203117Z/final_benchmark_index.tsv`
- Benchmark TSVs preserved: 79
- phase1_L001_L003_L008: 23 benchmark TSVs, 5 manifest TSVs
- phase2_L002_L006_L008: 28 benchmark TSVs, 5 manifest TSVs
- phase3_L004_L005_L007: 28 benchmark TSVs, 6 manifest TSVs

## Final Lane FASTQ Totals

L008 uses the complete Phase 2 row; the earlier partial Phase 1 L008 row is retained locally but not counted here.

| Lane | Phase | Done shards | FASTQ files | Total GiB | Undetermined GiB | Assigned GiB |
|---|---:|---:|---:|---:|---:|---:|
| L001 | phase1_L001_L003_L008 | 8/8 | 672 | 560.350 | 116.315 | 444.035 |
| L002 | phase2_L002_L006_L008 | 8/8 | 672 | 560.769 | 115.975 | 444.794 |
| L003 | phase1_L001_L003_L008 | 8/8 | 672 | 559.955 | 117.666 | 442.288 |
| L004 | phase3_L004_L005_L007 | 8/8 | 672 | 561.921 | 118.071 | 443.850 |
| L005 | phase3_L004_L005_L007 | 8/8 | 672 | 561.649 | 119.169 | 442.479 |
| L006 | phase2_L002_L006_L008 | 8/8 | 672 | 558.375 | 118.435 | 439.940 |
| L007 | phase3_L004_L005_L007 | 8/8 | 672 | 562.089 | 121.493 | 440.596 |
| L008 | phase2_L002_L006_L008 | 8/8 | 672 | 560.001 | 116.584 | 443.417 |
| TOTAL | final | 64/64 | 5376 | 4485.109 | 943.708 | 3541.400 |

## All Captured Phase Rows

| Phase | Lane | Done shards | FASTQ files | Total GiB | Undetermined GiB | Assigned GiB | Note |
|---|---:|---:|---:|---:|---:|---:|---|
| phase1_L001_L003_L008 | L001 | 8/8 | 672 | 560.350 | 116.315 | 444.035 |  |
| phase1_L001_L003_L008 | L003 | 8/8 | 672 | 559.955 | 117.666 | 442.288 |  |
| phase1_L001_L003_L008 | L008 | 4/8 | 336 | 282.403 | 61.056 | 221.348 | superseded partial row |
| phase2_L002_L006_L008 | L002 | 8/8 | 672 | 560.769 | 115.975 | 444.794 |  |
| phase2_L002_L006_L008 | L006 | 8/8 | 672 | 558.375 | 118.435 | 439.940 |  |
| phase2_L002_L006_L008 | L008 | 8/8 | 672 | 560.001 | 116.584 | 443.417 |  |
| phase3_L004_L005_L007 | L004 | 8/8 | 672 | 561.921 | 118.071 | 443.850 |  |
| phase3_L004_L005_L007 | L005 | 8/8 | 672 | 561.649 | 119.169 | 442.479 |  |
| phase3_L004_L005_L007 | L007 | 8/8 | 672 | 562.089 | 121.493 | 440.596 |  |

## Cleanup State

- Phase 1 deleted: L001 and L003 exact manifest paths; L008 kept until Phase 2 completion.
- Phase 2 deleted: L002, L006, and L008 exact manifest paths.
- Phase 3 deleted: L004, L005, and L007 exact manifest paths.
- Remaining remote analysis checkout may still contain lightweight workflow metadata, configs, global logs, and marker files, but lane FASTQ payload directories listed in deletion manifests are absent.

## Cluster Deletion Readiness

The BCL workload is complete, no squeue jobs are running, the controller is idle, and the required local evidence is preserved. I have not deleted dyec5117 because deleting the active cluster is a destructive AWS action that needs explicit confirmation.
