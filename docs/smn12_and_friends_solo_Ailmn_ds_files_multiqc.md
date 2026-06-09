# SMN12 And Friends Solo Analysis, ILMN 20x Files, MultiQC URLs

Generated: `2026-06-07T01:14:41Z`

Cluster: `hyb-only`  
AWS profile: `lsmc`  
Region: `us-west-2`  
CloudFront distribution: `E1O1EGAADAALSL` / `dlqovrcm5y71h.cloudfront.net`  
CloudFront origin path: `s3://lsmc-dayoa-omics-analysis-us-west-2/FSxLustre20260515T103052Z/analysis_results/ubuntu/`  
CloudFront invalidation: `IAHKH8N0YB7YYFN7MH48FVZXXT` (`Completed`)

## Status Summary

| Artifact | FSx status | S3 status | CloudFront status |
|---|---|---|---|
| ILMN solo kitchen-sink | cleaned from FSx after export | exported | report/data copied to CloudFront origin |
| ONT solo kitchen-sink | present on FSx | exported | report/data copied to CloudFront origin |
| ILMN 20x downsample FASTQs | present on FSx | exported from real-copy tree | not applicable |

CloudFront auth note: unauthenticated requests return the expected `401 Basic realm="LSMC QC"`. The pre-existing May 11 CloudFront credentials were recovered into `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/.may11cf` (`0400`) and authenticated successfully against the ILMN and ONT MultiQC HTML/data URLs. The newer `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/.cf` credentials are preserved but are not the credentials used by the May 11 CloudFront function `lsmc-giab-20x30x-v2-basic-auth-20260511`.

## MultiQC Links

| Analysis | MultiQC HTML | MultiQC data dir |
|---|---|---|
| ILMN solo | `https://dlqovrcm5y71h.cloudfront.net/hybonly_ilmn_kitchensink_mounted_20260606T053415Z/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc.html` | `https://dlqovrcm5y71h.cloudfront.net/hybonly_ilmn_kitchensink_mounted_20260606T053415Z/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc_data/` |
| ONT solo | `https://dlqovrcm5y71h.cloudfront.net/hybonly_ont_chipbarcode_limited_live_20260606T090222Z/daylily-omics-analysis/results/day/hg38_broad/reports/DAY_final_multiqc.html` | `https://dlqovrcm5y71h.cloudfront.net/hybonly_ont_chipbarcode_limited_live_20260606T090222Z/daylily-omics-analysis/results/day/hg38_broad/reports/DAY_final_multiqc_data/` |

## ILMN Solo Analysis

| Field | Value |
|---|---|
| Analysis ID | `hybonly_ilmn_kitchensink_mounted_20260606T053415Z` |
| Genome | `hg38` |
| FSx path | `/fsx/analysis_results/ubuntu/hybonly_ilmn_kitchensink_mounted_20260606T053415Z` |
| FSx status | `deleted_or_absent` after successful export/cleanup |
| S3 prefix | `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/hybonly_ilmn_kitchensink_mounted_20260606T053415Z/` |
| DRA receipt | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260605T000000Z_hyb_only_mounted_fastq_kitchensink_logs/ilmn_dra_export_20260606T101135Z/fsx_export.yaml` |
| S3 objects | `16042` |
| S3 bytes | `255917543393` |
| MultiQC HTML S3 | `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/hybonly_ilmn_kitchensink_mounted_20260606T053415Z/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc.html` |
| MultiQC data JSON S3 | `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/hybonly_ilmn_kitchensink_mounted_20260606T053415Z/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc_data/multiqc_data.json` |

CloudFront-origin object heads:

| Object | Bytes | Content type | Last modified |
|---|---:|---|---|
| `DAY_final_multiqc.html` | `12675488` | `text/html; charset=utf-8` | `2026-06-07T01:04:45Z` |
| `DAY_final_multiqc_data/multiqc_data.json` | `26705126` | `application/json` | `2026-06-07T01:04:49Z` |

## ONT Solo Analysis

| Field | Value |
|---|---|
| Analysis ID | `hybonly_ont_chipbarcode_limited_live_20260606T090222Z` |
| Genome | `hg38_broad` |
| FSx path | `/fsx/analysis_results/ubuntu/hybonly_ont_chipbarcode_limited_live_20260606T090222Z/daylily-omics-analysis` |
| FSx report path | `/fsx/analysis_results/ubuntu/hybonly_ont_chipbarcode_limited_live_20260606T090222Z/daylily-omics-analysis/results/day/hg38_broad/reports/` |
| S3 prefix | `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/hybonly_ont_chipbarcode_limited_live_20260606T090222Z/` |
| DRA receipt | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260605T000000Z_hyb_only_mounted_fastq_kitchensink_logs/ont_solo_dra_export_20260607T010531Z/fsx_export.yaml` |
| S3 objects | `17149` |
| S3 bytes | `209823451481` |
| FSx report dir size | `1.2G` |
| MultiQC HTML S3 | `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/hybonly_ont_chipbarcode_limited_live_20260606T090222Z/daylily-omics-analysis/results/day/hg38_broad/reports/DAY_final_multiqc.html` |
| MultiQC data JSON S3 | `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/hybonly_ont_chipbarcode_limited_live_20260606T090222Z/daylily-omics-analysis/results/day/hg38_broad/reports/DAY_final_multiqc_data/multiqc_data.json` |

CloudFront-origin object heads:

| Object | Bytes | Content type | Last modified |
|---|---:|---|---|
| `DAY_final_multiqc.html` | `13933924` | `text/html; charset=utf-8` | `2026-06-07T01:13:33Z` |
| `DAY_final_multiqc_data/multiqc_data.json` | `37015639` | `application/json` | `2026-06-07T01:13:34Z` |

## ILMN 20x Downsample Files

| Field | Value |
|---|---|
| Original FSx source | `/fsx/analysis_results/4_nas_ds_to_20x` |
| Real-copy FSx export source | `/fsx/analysis_results/ubuntu/4_nas_ds_to_20x_realcopy` |
| S3 prefix | `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/4_nas_ds_to_20x_realcopy/` |
| DRA receipt | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260605T000000Z_hyb_only_mounted_fastq_kitchensink_logs/ilmn20x_realcopy_dra_export_20260607T010234Z/fsx_export.yaml` |
| S3 objects | `38` |
| S3 bytes | `142645322518` |
| FASTQ objects | `8` |
| Real-copy verification | destination FASTQs have link count `1`; source hardlink tree was not used for final export |

| Sample | R1 S3 URI | R2 S3 URI |
|---|---|---|
| `NA00232-SMN` | `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/4_nas_ds_to_20x_realcopy/NA00232-SMN_S46_ds20x_R1_001.fastq.gz` | `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/4_nas_ds_to_20x_realcopy/NA00232-SMN_S46_ds20x_R2_001.fastq.gz` |
| `NA09677-SMN` | `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/4_nas_ds_to_20x_realcopy/NA09677-SMN_S47_ds20x_R1_001.fastq.gz` | `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/4_nas_ds_to_20x_realcopy/NA09677-SMN_S47_ds20x_R2_001.fastq.gz` |
| `NA03986-DMPK` | `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/4_nas_ds_to_20x_realcopy/NA03986-DMPK_S48_ds20x_R1_001.fastq.gz` | `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/4_nas_ds_to_20x_realcopy/NA03986-DMPK_S48_ds20x_R2_001.fastq.gz` |
| `NA05164-DMPK` | `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/4_nas_ds_to_20x_realcopy/NA05164-DMPK_S49_ds20x_R1_001.fastq.gz` | `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/4_nas_ds_to_20x_realcopy/NA05164-DMPK_S49_ds20x_R2_001.fastq.gz` |

## Current Hybrid SMN12 / Segdup Note

The active hybrid run is separate from the solo and downsample artifacts above:

| Field | Value |
|---|---|
| Analysis ID | `hybonly_hybrid_hiomr_na4_ds20x_split_snvsegsmn12_live_20260607T005400Z` |
| FSx path | `/fsx/analysis_results/ubuntu/hybonly_hybrid_hiomr_na4_ds20x_split_snvsegsmn12_live_20260607T005400Z/daylily-omics-analysis` |
| Current state at check | controller running |
| Segdup/SMN12 caller status | not started yet |
| Running prerequisites | `sentieon_bwa_sort`, `sentmm2ont_align_sort`, and `sentdhiomr_sr_align` jobs |
| Running threads | `192` CPUs/job |
