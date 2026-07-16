# jul8itelx4 Percent Complete And Spot Cost Snapshot

Snapshot time: `2026-07-08T19:30:43+00:00`

## Summary

- Unweighted command-catalog completion: `53.3%` across `15` commands.
- Completed commands: `6`; failed/nonzero status rows: `1`.
- Active partial workflows, step-weighted only: `11.1%` (`318/2877` steps).
- ComputeFleet spot cost so far: `$26.82` across `42` spot intervals.
- Currently open/running spot intervals: `1` at about `$2.30/hr`.
- Predicted remaining cost, progress-ratio model: `$23.53`; predicted total: `$50.35`.
- Alternate current-burn projection: `3.9` remaining wall-hours at `$2.30/hr` = `$8.92` remaining, but this undercounts if Slurm brings more nodes online.

## Command Progress

| # | Command | Complete | Evidence | Steps |
|---:|---|---:|---|---:|
| 1 | `illumina_snv_alignstats` | 18.0% | `snakemake_steps_line` | 6 / 33 |
| 2 | `illumina_snv_alignstats_relatedness_vep_multiqc` | 10.0% | `snakemake_steps_line` | 13 / 128 |
| 3 | `illumina_hg002_kitchensink_multiqc` | 9.0% | `snakemake_steps_line` | 13 / 144 |
| 4 | `ultima_snv_alignstats` | 100.0% | `workflow_exit_0` | n/a |
| 5 | `ultima_snv_alignstats_kitchensink` | 78.0% | `snakemake_steps_line` | 90 / 116 |
| 6 | `ont_snv_alignstats` | 100.0% | `workflow_exit_0` | n/a |
| 7 | `ont_snv_alignstats_kitchensink` | 69.0% | `snakemake_steps_line` | 77 / 112 |
| 8 | `pacbio_snv_alignstats` | 100.0% | `workflow_exit_0` | n/a |
| 9 | `roche_snv_alignstats` | 100.0% | `workflow_exit_0` | n/a |
| 10 | `hybrid_ilmn_ont_snv` | 7.0% | `snakemake_steps_line` | 51 / 746 |
| 11 | `hybrid_ilmn_ont_snv_kitchensink` | 5.0% | `snakemake_steps_line` | 45 / 841 |
| 12 | `inflection-bjuice-product-v0.1` | 3.0% | `snakemake_steps_line` | 23 / 757 |
| 13 | `illumina_run_qc` | 100.0% | `workflow_exit_0` | n/a |
| 14 | `ont_run_qc` | 100.0% | `workflow_exit_0` | n/a |
| 15 | `ultima_run_qc` | 0.0% | `no_progress_marker` | n/a |

## Spot Cost Intervals By Partition

| Partition | Intervals | Open | Instance-hours | Cost so far |
|---|---:|---:|---:|---:|
| `i128` | 34 | 0 | 7.15 | $18.84 |
| `i192` | 7 | 0 | 1.44 | $2.94 |
| `i192nvme` | 1 | 1 | 2.19 | $5.04 |

## Open Spot Instances

| Instance | Host | Type | Partition | Running Hours | Avg $/hr | Cost So Far |
|---|---|---|---|---:|---:|---:|
| `i-05f94baf43c54eea3` | `i192nvme-dy-price192nvme-1` | `i7i.48xlarge` | `i192nvme` | 2.19 | $2.3007 | $5.04 |

## Caveats

- ComputeFleet spot intervals only; headnode excluded.
- Starts use EC2 LaunchTime where visible, otherwise CloudTrail RunInstances, otherwise the FSx spot-log timestamp.
- Closed intervals use EC2 state transition time when visible, otherwise CloudTrail TerminateInstances time.
- Cost integrates EC2 Spot price history over each interval; logged price is fallback only.
- Remaining cost progress-ratio model uses unweighted average of the 15 command percentages.
- Current-burn model assumes only currently open spot instances continue running at current burn rate.

Artifacts:

- `docs/plans/20260708T192900Z_jul8itelx4_cost_progress/summary.json`
- `docs/plans/20260708T192900Z_jul8itelx4_cost_progress/command_progress.csv`
- `docs/plans/20260708T192900Z_jul8itelx4_cost_progress/spot_cost_intervals.csv`
- `docs/plans/20260708T192900Z_jul8itelx4_cost_progress/spot_start_rows.json`
