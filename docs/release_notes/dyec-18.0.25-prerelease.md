# DYEC 18.0.25 prerelease

> **AWS credential notice.** This release work used the still overly-permissioned `lsmc` AWS profile. Josh Durham (@jdurham38) is actively porting the workflow to a tightly scoped IAM role; that work is underway.

## Minimal correction

- `hiomr2_slim_kitchensink_mega` now defaults to numeric chromosomes `1-25` in both live and dry commands.
- `inflection-bjuice-product-v0.9` remains the full `1-25` HIOMR2 kitchen-sink mega plus Inflection packaging command, defaulting to all supplied ONT FASTQs.
- All active commands remain pinned to DayOA `15.0.14`.

Runbook: [RELASE-18.0.25-runbook.md](https://github.com/lsmc-bio/daylily-ephemeral-cluster/blob/18.0.25/docs/runbooks/18.0.25/RELASE-18.0.25-runbook.md).

## Production validated command-catalog evidence

Only the following production commands are included. The listed receipts are historical production evidence; fresh prerelease catalog tests must confirm the new 18.0.25 command definitions.

| Production command | Evidence S3 URI |
| --- | --- |
| `illumina_run_qc` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022_ilmn_seq_qc_15011_live_20260817T0712Z/daylily-omics-analysis/results/runs/20260618_LH01106_0011_A23MFMCLT3/run_qc/illumina/multiqc_report.html` |
| `ont_run_qc` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022_ont_seq_qc_15011_live_20260817T0752Z/daylily-omics-analysis/results/runs/20260615_ONT_Set4-FC1/run_qc/ont/multiqc_report.html` |
| `ultima_run_qc` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022_ultima_seq_qc_15011_live_20260817T0734Z/daylily-omics-analysis/results/runs/604834-20260717_2309/run_qc/ultima/ultima_native.multiqc.html` |
| `illumina_hg002_kitchensink_multiqc` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/analysis_results/pcand18022-ilmn-solo-slim-1511-20260817t075549z-live-r1/` |
| `ont_snv_alignstats_kitchensink` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/analysis_results/pcand18022-ont-solo-slim-1512-20260817t082933z-live-r2/` |
| `ultima_snv_alignstats_kitchensink` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/analysis_results/pcand18022-ultima-solo-slim-1511-20260817t075549z-live-r1/` |
| `complete_genomics_cg_snv_concordance` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/analysis_results/pcand18022-cg-solo-slim-1511-20260817t075549z-live-r1/` |
| `hiomr2_slim_kitchensink_mega` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022-hg002-slim5x5x-hiomr2-20260817t0648z/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc_data/multiqc_giab_concordance.txt` |
| `inflection-bjuice-product-v0.9` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022-hg002-slim5x5x-bjuice-ifx-20260817t0648z/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc_data/multiqc_giab_concordance.txt` |

No tests were run while creating this prerelease. No FSx data was deleted.
