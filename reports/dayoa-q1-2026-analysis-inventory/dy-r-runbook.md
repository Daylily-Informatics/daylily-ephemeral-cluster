# dy-r Runbook For Q1 2026 Daylily Omics Analysis Re-Runs

This runbook is generated from observed Q1 2026 exported Daylily analysis repositories.

## Inventory Summary

- Total analysis dirs: 81
- Complete: 60
- Partial results: 12
- No hg38 results: 0
- Metadata missing: 9

## Standard Headnode Session

Use the Daylily headnode shell configured for `ubuntu` in a bash login shell.

```bash
cd /fsx/analysis_results/ubuntu/<analysis-code>/daylily-omics-analysis
source ~/.bashrc
command -v dy-r
command -v dy-a
```

## Recreate Config Files

```bash
mkdir -p config
# Copy or regenerate the staged manifests:
cp /fsx/data/staged_sample_data/<stage-dir>/*_samples.tsv config/samples.tsv
cp /fsx/data/staged_sample_data/<stage-dir>/*_units.tsv config/units.tsv

head -n 3 config/samples.tsv
head -n 3 config/units.tsv
python - <<'PY'
import csv
for path in ['config/samples.tsv', 'config/units.tsv']:
    with open(path, newline='') as handle:
        rows = list(csv.DictReader(handle, delimiter='\t'))
    print(path, len(rows), rows[0].keys() if rows else 'EMPTY')
PY
```

## Launch Pattern

Use the observed profile convention, then run a dry-run before the real run.

```bash
dy-a slurm hg38
dy-r <target> -n
dy-r <target>

# Broad-profile runs observed in this inventory use:
dy-a slurm hg38_broad
dy-r <target> -n
dy-r <target>
```

## Observed Command Examples

### ILMN

```bash
snakemake --profile=/fsx/analysis_results/ubuntu/take2/daylily-omics-analysis/config/day_profiles/slurm produce_snv_concordances produce_sentD_vcf dedup_doppelmark produce_sentieon_bwa_sort_bam produce_manta produce_tiddit produce_multiqc_final_wgs -p -j 100 -k
```

### ONT

```bash
snakemake --profile=/fsx/analysis_results/ubuntu/ont_hg003_prod/daylily-omics-analysis/config/day_profiles/slurm produce_sentdont_vcf produce_alignstats produce_snv_concordances -p -j 20 -k -T 1 -n
```

### PacBio

```bash
snakemake --profile=/fsx/analysis_results/ubuntu/pbfill/daylily-omics-analysis/config/day_profiles/slurm produce_snv_concordances produce_alignstats produce_sentmm2_align_sort produce_sentdpb_vcf -p -k -j 5
```

### Ultima

```bash
snakemake --profile=/fsx/analysis_results/ubuntu/agbt_ug/daylily-omics-analysis/config/day_profiles/slurm produce_sentdug_vcf produce_alignstats produce_snv_concordances -p -j 20 -k -T 1
```

### Roche

```bash
snakemake --profile=/fsx/analysis_results/ubuntu/roche_filler/daylily-omics-analysis/config/day_profiles/slurm produce_snv_concordances produce_alignstats produce_deep19_r_vcf -p -k -j 12 --rerun-triggers mtime --rerun-incomplete
```

### Hybrid

```bash
snakemake --profile=/fsx/analysis_results/ubuntu/hio-cli-old/daylily-omics-analysis/config/day_profiles/slurm produce_snv_concordances -p -T 0 -j 24 --config aligners=[sentmm2ont] dedupers=[na] snv_callers=[deep19] --rerun-triggers mtime --forcerun prep_for_concordance_check
```

## Validation Checklist

- Confirm `config/samples.tsv` has the expected `SAMPLEID` values.
- Confirm `config/units.tsv` has expected `RUNID`, `SAMPLEID`, platform, and path columns.
- Run the dry-run command first and inspect missing input messages.
- Launch the real command only after the dry-run resolves.
- Check `day_cmd.log`, `day_pipe_stats.json`, and `daylily.successful_run` after completion.
