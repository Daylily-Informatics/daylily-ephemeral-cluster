# jul8itelx4 Catalog Progress And Packing Snapshot

Snapshot target: `jul8itelx4` in `us-west-2d`.

Remote snapshot directory: `/home/ubuntu/daylily-runs/jul8itelx4_status_snapshot_20260708T191050Z`.

Evidence windows:

- Progress/packing CSV refresh: `2026-07-08T19:16:38Z` wrapper run. The collector is hard-coded to write into the `20260708T191050Z` snapshot directory.
- Live queue follow-up: `2026-07-08T19:17:57Z`.
- FSx follow-up: `/fsx` was `570G / 6.6T`, 9% used, at `2026-07-08T19:17:35Z`.

## Executive Readout

- Catalog rows tracked: 15.
- Workflows at 100% by workflow exit code: 6 of 15.
- Running or partial workflows: 8 of 15.
- One workflow is currently failed/0% by its local status evidence: `ultima_run_qc`.
- Live Slurm queue follow-up: 132 pending jobs and 3 running jobs.
- Current live running jobs are all on `i192nvme-dy-price192nvme-1`, so Slurm is packing multiple jobs onto a large node.
- Slurm memory scheduling is not off. The headnode reports `SelectTypeParameters = CR_CPU_MEMORY`, so memory is a consumable scheduling dimension.
- Current pending reasons are mostly `BeginTime`, `ReqNodeNotAvail`, and `Priority`; only one live pending aggregate row showed `Resources`. Memory requests are still a real packing constraint because several large jobs request 125G, 62.5G, or 500G.

## Command Percent Complete

Percentages are from the latest Snakemake step line when the workflow is still active, or forced to 100% when workflow status has `exit_code=0`.

| # | Command | Analysis ID | Complete | Evidence | Steps |
|---:|---|---|---:|---|---:|
| 1 | `illumina_snv_alignstats` | `ccv_live_illumina_snv_alignstats_20260708T150500Z` | 18% | `snakemake_steps_line` | 6 / 33 |
| 2 | `illumina_snv_alignstats_relatedness_vep_multiqc` | `ccv_live_illumina_snv_alignstats_relatedness_vep_multiqc_20260708T152112Z` | 10% | `snakemake_steps_line` | 13 / 128 |
| 3 | `illumina_hg002_kitchensink_multiqc` | `ccv_live_illumina_hg002_kitchensink_multiqc_20260708T152112Z` | 9% | `snakemake_steps_line` | 13 / 144 |
| 4 | `ultima_snv_alignstats` | `ccv_live_ultima_snv_alignstats_20260708T152112Z` | 100% | `workflow_exit_0` | n/a |
| 5 | `ultima_snv_alignstats_kitchensink` | `ccv_live_ultima_snv_alignstats_kitchensink_20260708T152112Z` | 76% | `snakemake_steps_line` | 88 / 116 |
| 6 | `ont_snv_alignstats` | `ccv_live_ont_snv_alignstats_20260708T152112Z` | 100% | `workflow_exit_0` | n/a |
| 7 | `ont_snv_alignstats_kitchensink` | `ccv_live_ont_snv_alignstats_kitchensink_20260708T152112Z` | 61% | `snakemake_steps_line` | 68 / 112 |
| 8 | `pacbio_snv_alignstats` | `ccv_live_pacbio_snv_alignstats_20260708T152112Z` | 100% | `workflow_exit_0` | n/a |
| 9 | `roche_snv_alignstats` | `ccv_live_roche_snv_alignstats_20260708T152112Z` | 100% | `workflow_exit_0` | n/a |
| 10 | `hybrid_ilmn_ont_snv` | `ccv_live_hybrid_ilmn_ont_snv_20260708T152112Z` | 7% | `snakemake_steps_line` | 49 / 746 |
| 11 | `hybrid_ilmn_ont_snv_kitchensink` | `ccv_live_hybrid_ilmn_ont_snv_kitchensink_20260708T152112Z` | 4% | `snakemake_steps_line` | 34 / 841 |
| 12 | `inflection-bjuice-product-v0.1` | `ccv_live_inflection_bjuice_product_v0_1_20260708T152112Z` | 3% | `snakemake_steps_line` | 23 / 757 |
| 13 | `illumina_run_qc` | `ccv_live_illumina_run_qc_20260708T152112Z` | 100% | `workflow_exit_0` | n/a |
| 14 | `ont_run_qc` | `ccv_live_ont_run_qc_20260708T152112Z` | 100% | `workflow_exit_0` | n/a |
| 15 | `ultima_run_qc` | `ccv_live_ultima_run_qc_20260708T163200Z` | 0% | `no_progress_marker`, status exit code 1 | n/a |

## Live Running Packing

At `2026-07-08T19:17:57Z`, Slurm had three running jobs, all on `i192nvme-dy-price192nvme-1`.

| Job | Partition | CPUs | Memory | Node | Runtime | Rule |
|---:|---|---:|---:|---|---:|---|
| 360 | `i192nvme` | 48 | 125G | `i192nvme-dy-price192nvme-1` | 0:33 | `sentdhiomr_stage1` |
| 362 | `i192nvme` | 48 | 125G | `i192nvme-dy-price192nvme-1` | 0:06 | `sentdhiomr_pass1` |
| 364 | `i192nvme` | 32 | 62.50G | `i192nvme-dy-price192nvme-1` | 0:06 | `sentdhiomr_mapq0_bed` |

This live node is using 128 / 192 CPUs and approximately 312.5G requested memory. The node class is being shared by multiple jobs, not held exclusively by one job.

## Snapshot Packing By Rule And Partition

The refreshed CSV snapshot saw a transient Slurm configuring wave on `i384nvme`, with many jobs assigned to the same large-node partition. A later live follow-up had moved those jobs back to pending/running states, so this table should be read as packing evidence from that scheduling wave rather than a stable terminal state.

| Rule | Partition | State | Jobs | CPUs | Memory Requests | Top Placement / Reason Evidence |
|---|---|---:|---:|---:|---|---|
| `doppelmark_dups` | `i384nvme` | CF | 4 | 384 | 500G x4 | price384nvme nodes 1-3 were targeted |
| `sentdhiomr_hybrid_select` | `i384nvme` | CF | 13 | 52 | 50000M x13 | node 13 had 4 jobs; node 14 had 3; node 8 had 2 |
| `sentdhiomr_mapq0_bed` | `i384nvme` | CF | 24 | 768 | 62.50G x24 | nodes 15 and 11 each had 5 jobs; node 13 had 4 |
| `sentdhiomr_mapq0_slop` | `i384nvme` | CF | 11 | 22 | 50000M x11 | node 13 had 3 jobs; nodes 4 and 5 had 2 each |
| `sentdhiomr_merge_sr_bams` | `i384nvme` | CF | 1 | 32 | 62.50G x1 | node 9 had 1 job |
| `sentdhiomr_pass1` | `i384nvme` | CF | 25 | 1200 | 125G x25 | node 7 had 5 jobs; nodes 10 and 12 had 4 each |
| `vep_chromosome` | `i384nvme` | CF | 21 | 168 | 125G x21 | nodes 4 and 5 each had 5 jobs; node 8 had 4 |
| `vep_chromosome_input` | `i384nvme` | CF | 3 | 3 | 50000M x3 | node 1 had 3 jobs |

The node allocation snapshot also showed 16 allocated nodes: one `i192nvme` node and 15 `i384nvme` nodes. The `i384nvme` price nodes were heavily memory packed, commonly around 704G-740G allocated out of 747G. CPU was usually less saturated than memory on those nodes.

## Live Pending By Rule And Partition

At `2026-07-08T19:17:57Z`, the live queue had no configuring rows in the compact sample. Pending jobs were grouped as follows.

| Partition String | State | Memory | Reason | Jobs | CPUs | Interpretation |
|---|---|---:|---|---:|---:|---|
| `i192nvme,i384nvme,i192hugenvme` | PD | 125G | Priority | 2 | 96 | Scheduler priority, not a direct memory failure. |
| `i192nvme,i384nvme,i192hugenvme` | PD | 125G | Resources | 1 | 48 | One aggregate row is waiting for resources. Memory may participate because `CR_CPU_MEMORY` is enabled. |
| `i192nvme,i384nvme,i192hugenvme` | PD | 62.50G | Priority | 1 | 32 | Scheduler priority. |
| `i384nvme,i128nvme,i192nvme` | PD | 125G | BeginTime | 21 | 168 | VEP jobs delayed by begin time/planned scheduling. |
| `i384nvme,i128nvme,i192nvme` | PD | 125G | ReqNodeNotAvail on `i128nvme-dy-price128nvme-[1-15]` | 5 | 40 | Waiting on unavailable dynamic nodes in the listed range. |
| `i384nvme,i128nvme,i192nvme` | PD | 125G | Priority | 1 | 8 | Scheduler priority. |
| `i384nvme,i128nvme,i192nvme` | PD | 50000M | BeginTime | 3 | 3 | VEP input jobs delayed by begin time/planned scheduling. |
| `i384nvme,i192hugenvme,i192nvme` | PD | 125G | BeginTime | 25 | 1200 | Sentieon/HiOmics jobs delayed by begin time/planned scheduling. |
| `i384nvme,i192hugenvme,i192nvme` | PD | 125G | ReqNodeNotAvail on `i192hugenvme-dy-price192hugenvme-[1-15]` | 4 | 192 | Waiting on unavailable huge-NVMe dynamic nodes. |
| `i384nvme,i192hugenvme,i192nvme` | PD | 125G | Priority | 1 | 48 | Scheduler priority. |
| `i384nvme,i192hugenvme,i192nvme` | PD | 62.50G | BeginTime | 25 | 800 | Sentieon mapq0 bed jobs delayed by begin time/planned scheduling. |
| `i384nvme,i192hugenvme,i192nvme` | PD | 62.50G | ReqNodeNotAvail on `i192hugenvme-dy-price192hugenvme-[1-15]` | 5 | 160 | Waiting on unavailable huge-NVMe dynamic nodes. |
| `i384nvme,i192hugenvme,i192nvme` | PD | 50000M | BeginTime | 24 | 74 | Smaller sentieon support jobs delayed by begin time/planned scheduling. |
| `i384nvme,i192hugenvme,i192nvme` | PD | 50000M | ReqNodeNotAvail on `i192hugenvme-dy-price192hugenvme-[1-15]` | 10 | 34 | Waiting on unavailable huge-NVMe dynamic nodes. |
| `i384nvme,i192nvme` | PD | 500G | BeginTime | 4 | 384 | `doppelmark_dups` jobs are high-memory jobs. These substantially constrain packing. |

## Slurm Memory Scheduling

Slurm config evidence:

```text
DefMemPerNode           = UNLIMITED
SchedulerParameters     = nohold_on_prolog_fail
SchedulerType           = sched/backfill
SelectType              = select/cons_tres
SelectTypeParameters    = CR_CPU_MEMORY
TaskPlugin              = task/cgroup,task/affinity
TaskPluginParam         = (null type)
```

Conclusion: memory scheduling is enabled. `CR_CPU_MEMORY` means CPUs and memory are consumable resources for placement. The partition lines also show `MaxMemPerNode=UNLIMITED`, but that does not disable consumable-memory placement.

## Operational Notes

- The cluster is packing multiple jobs onto large instances when nodes are available.
- The strongest packing evidence is the `i384nvme` configuring wave, where large nodes had multiple `vep_chromosome`, `sentdhiomr_pass1`, `sentdhiomr_mapq0_bed`, and support jobs assigned per node.
- CPU is not the only gating dimension. Memory is frequently tighter, especially on `i384nvme` nodes near 704G-740G allocated out of 747G and for `doppelmark_dups` at 500G/job.
- The live queue at `19:17:57Z` does not show broad memory-blocked pending state. Most pending rows are `BeginTime`, `ReqNodeNotAvail`, or `Priority`; one aggregate row is `Resources`.
- `ReqNodeNotAvail` is concentrated on dynamic price node ranges for `i128nvme` and `i192hugenvme`, so some pending work is waiting on unavailable/resuming dynamic nodes rather than a command-catalog percentage issue.
