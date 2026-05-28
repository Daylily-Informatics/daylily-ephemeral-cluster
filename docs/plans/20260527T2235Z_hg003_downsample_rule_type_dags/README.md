# HG003 Downsample Rule-Type DAG PDFs

Generated from the DayOA 2.0.11 run directory on `goodole3`:
`/fsx/analysis_results/ubuntu/inflection_20260527-2.0.11/daylily-omics-analysis`

These are Snakemake `--rulegraph` DAGs, so per-chromosome/per-shard jobs are collapsed into single rule-type nodes. Node counts are from the active main controller log where available.

## PDFs
- [produce_dmd_dedup_cram.pdf](pdf/produce_dmd_dedup_cram.pdf)
- [produce_expansionhunter.pdf](pdf/produce_expansionhunter.pdf)
- [produce_sent_align.pdf](pdf/produce_sent_align.pdf)
- [produce_sentdhiomr_cnv.pdf](pdf/produce_sentdhiomr_cnv.pdf)
- [produce_sentdhiomr_mito.pdf](pdf/produce_sentdhiomr_mito.pdf)
- [produce_sentdhiomr_segdup.pdf](pdf/produce_sentdhiomr_segdup.pdf)
- [produce_sentdhiomr_snv_vcf.pdf](pdf/produce_sentdhiomr_snv_vcf.pdf)
- [produce_sentdhiomr_sv.pdf](pdf/produce_sentdhiomr_sv.pdf)
- [produce_snv_concordances.pdf](pdf/produce_snv_concordances.pdf)

## Evidence
- `remote_rulegraphs/`: fetched DOT files and stderr tails
- `rule_counts.tsv`: planned/finished/remaining rule counts from main controller log
- `remote_rulegraphs/manifest.txt`: remote generation manifest
