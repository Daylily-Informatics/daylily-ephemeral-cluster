# Day-Clone Outstanding Work Snapshot

Generated from `goodole3` via SSM as `ubuntu`.

Snapshot UTC: `2026-05-28T00:41:06Z`

## Summary

Only one day-clone analysis had active Slurm jobs or an active Snakemake controller:

| analysis | submitted | running | pending | configuring | dry-run remaining | estimated not yet submitted |
|---|---:|---:|---:|---:|---:|---:|
| `inflection_20260527-2.0.11` | 123 | 20 | 79 | 24 | 192 | 69 |

Workdir:

`/fsx/analysis_results/ubuntu/inflection_20260527-2.0.11/daylily-omics-analysis`

The active controller target set is the downsampled inflection set:

`produce_sent_align produce_dmd_dedup_cram produce_sentdhiomr_sv produce_snv_concordances produce_sentdhiomr_snv_vcf produce_sentdhiomr_cnv produce_sentdhiomr_mito produce_sentdhiomr_segdup produce_expansionhunter`

## Evidence Files

- `outstanding_by_analysis.tsv`: per-analysis submitted and dry-run remaining counts.
- `submitted_rules_by_analysis.tsv`: submitted Slurm jobs grouped by analysis, rule, and state.
- `controllers.tsv`: active `day_run`/`snakemake` controller processes.
- `scontrol_jobs.txt`: raw `scontrol show job -o` evidence.
- `inflection_20260527-2.0.11.dryrun.tail`: dry-run tail used for remaining-task count.
