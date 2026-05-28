# Inflection Controller Rulegraphs

Generated from `goodole3` / `lsmc` / `us-west-2`.

Run directory:

`/fsx/analysis_results/ubuntu/inflection_20260527-2.0.11/daylily-omics-analysis`

## Variants

- `downsampled_with_segdup`: active downsampled inflection controller target set, including `produce_sentdhiomr_segdup`.
- `no_segdup`: same downsampled target set with `produce_sentdhiomr_segdup` removed.

Only one live Snakemake controller process was active at `2026-05-28T00:33:59Z`, the downsampled inflection controller launched by `inflection_2011_real_j125_20260527T195621Z`. The sample names in the active process and Slurm queue are `ILMN15X-ONT7X` and `ILMN20X-ONT10X`; this is not the full-coverage/full1022 controller.

## Remaining Counts

Dry-runs at `2026-05-28T00:35:12Z` completed with `rc=0`:

- `downsampled_with_segdup`: `192` remaining jobs.
- `no_segdup`: `192` remaining jobs.

Queue refresh at `2026-05-28T00:36:30Z` showed `36` submitted jobs: `2` running and `34` pending. Estimated not-yet-submitted jobs for both target variants at that instant: `156`.

## Images

- `pdf/downsampled_with_segdup.rulegraph.pdf`
- `pdf/no_segdup.rulegraph.pdf`
- `png/downsampled_with_segdup.rulegraph.png`
- `png/no_segdup.rulegraph.png`
- `svg/downsampled_with_segdup.rulegraph.svg`
- `svg/no_segdup.rulegraph.svg`

The original Snakemake DOT files are under `dot/`; the Mermaid conversions used for local rendering are `dot/*.rulegraph.mmd`.

Files named `full.*` are retained from the initial artifact generation, but `downsampled_with_segdup.*` is the intended label.
