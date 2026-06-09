# Hyb-Only Hybrid X8 Full Variant Ledger

Created: 2026-06-07T12:42:57Z

## Objective

Run the 4 NA samples as 8 hybrid units on cluster `hyb-only` using DayOA tag `5.0.17`, `hg38_broad`, mounted ONT FASTQs, and 20x ILMN downsampled FASTQs.

## Locked Inputs

- DayOA tag: `5.0.17`
- DayOA commit: `4df4571a928b3bd673113f3d79403cc620b62f2c`
- Cluster: `hyb-only`
- Headnode: `i-05374380b57fad901`
- Genome: `hg38_broad`
- Samples source: `docs/plans/20260605T000000Z_hyb_only_mounted_fastq_kitchensink_logs/hybrid_hiomr_na4_ds20x_split_config/20260606T153500Z_hybrid_hiomr_na4_ds20x_split_samples.tsv`
- Units source: `docs/plans/20260605T000000Z_hyb_only_mounted_fastq_kitchensink_logs/hybrid_hiomr_na4_ds20x_split_config/20260606T153500Z_hybrid_hiomr_na4_ds20x_split_units.tsv`

## Unit Shape

- `NA00232`: `chip1+chip2`, `chip4`
- `NA09677`: `chip1+chip2`, `chip3+chip4`
- `NA03986`: `chip1+chip2`, `chip4`
- `NA05164`: `chip1+chip2`, `chip4`

Total: 4 samples, 8 units.

## Launch Command

Setup:

```bash
source dyoainit
dy-a slurm hg38_broad
```

Dry-run:

```bash
dy-r produce_sentdhiomr_snv_vcf produce_sentdhiomr_sv produce_sentdhiomr_cnv produce_sentdhiomr_segdup produce_sentdhiomr_mito produce_expansionhunter produce_smn12 produce_tiddit_sv_vcf produce_alignstats -p -k -j 400 --rerun-triggers mtime -n --config 'aligners=["sent"]' 'dedupers=["dmd"]' 'snv_callers=["sentdhiomr"]' 'sv_callers=["tiddit"]' 'htd_callers=["smn12"]'
```

Live:

```bash
dy-r produce_sentdhiomr_snv_vcf produce_sentdhiomr_sv produce_sentdhiomr_cnv produce_sentdhiomr_segdup produce_sentdhiomr_mito produce_expansionhunter produce_smn12 produce_tiddit_sv_vcf produce_alignstats -p -k -j 400 --rerun-triggers mtime --config 'aligners=["sent"]' 'dedupers=["dmd"]' 'snv_callers=["sentdhiomr"]' 'sv_callers=["tiddit"]' 'htd_callers=["smn12"]'
```

## Status

| Row | State | Evidence |
|---|---|---|
| Gate 0 | pass | `/fsx` 7.5T free; `squeue -u ubuntu` empty |
| Config snapshot | pass | `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/config_snapshots/20260607T124257Z/hybrid_x8_fullvars_5017/` |
| `day-clone -t 5.0.17` | pass | `/fsx/analysis_results/hyb-only/hybonly_hybrid_hiomr_na4_ds20x_x8_fullvars_5017_20260607T124257Z/daylily-omics-analysis` |
| Dry-run | pass | `__HYB_X8_DRY_RC__:0` |
| Live run | running | Live `dy-r` submitted in tmux `hyb_x8_fullvars_5017_20260607T124257Z`; first Slurm submissions observed, jobs `13483`-`13498` |

## First Live Status

| Metric | Value |
|---|---|
| Controller PID | `2767356` |
| Jobs observed | 16 |
| Job states | `CF` on first probe |
| First job IDs | `13483`-`13498` |
| First rules | `sentmm2ont_align_sort`, `sentieon_bwa_sort` |
| `/fsx` | 8.8T size, 1.3T used, 7.5T free, 15% used |

## False Starts

- Initial tmux seeding assumed the clone path was under `/fsx/analysis_results/ubuntu/`; `day-clone` created the workspace under `/fsx/analysis_results/hyb-only/`. The SSM wrapper was cancelled before dry-run or Slurm submission.
- A generated `/fsx/analysis_results/ubuntu/config` directory from that false start was removed by the launch script.
