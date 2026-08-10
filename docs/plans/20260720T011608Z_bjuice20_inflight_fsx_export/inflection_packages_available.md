# Bjuice20 in-flight FSx export and Inflection package availability

Generated at: `2026-07-20T01:16:08Z`

## Export scope

- Cluster: `ifx-p2-1000-120-0715`
- FSx source: `/fsx/analysis_results/ifx-p2-1000-120-0715/bjuiceprevalanalysis-complete`
- S3 destination: `s3://lsmc-dayoa-analysis-results-usw2/validation/inflight_pr53_recovery_20260720T011608Z/ifx-p2-1000-120-0715/bjuiceprevalanalysis-complete/`
- Export semantics: immutable destination prefix; no FSx or S3 deletion; source workflow remains active during export.
- Source code base: DayOA PR #53 merge commit `6255b1de9847a8d2da6f048543abc2d3c513b946`, plus the tested live recovery patch.

This is an **in-flight point-in-time export**, not the terminal release bundle. Files created or changed after the FSx export task observes a path may require a later terminal export.

## Inflection packages available at snapshot start

Eighteen per-analysis-unit package manifests were present. Every listed package reported `package_state=READY` and zero artifact failures. The delivery profile is `local`, so these are package-only analytical artifacts and are not evidence of customer delivery.

- `HG001-HG001-HG001-ILMN-LIB-HG001-ONT-LIB-BJUICE-PREVAL-HG001-HIOMRS-A1`
- `HG003-HG003-HG003-ILMN-LIB-HG003-ONT-LIB-BJUICE-PREVAL-HG003-HIOMRS-A1`
- `HG004-HG004-HG004-ILMN-LIB-HG004-ONT-LIB-BJUICE-PREVAL-HG004-HIOMRS-A1`
- `HG005-HG005-HG005-ILMN-LIB-HG005-ONT-LIB-BJUICE-PREVAL-HG005-HIOMRS-A1`
- `HG006-HG006-HG006-ILMN-LIB-HG006-ONT-LIB-BJUICE-PREVAL-HG006-HIOMRS-A1`
- `HG007-HG007-HG007-ILMN-LIB-HG007-ONT-LIB-BJUICE-PREVAL-HG007-HIOMRS-A1`
- `NA05067-NA05067-NA05067-ILMN-LIB-NA05067-ONT-LIB-BJUICE-PREVAL-NA05067-HIOMRS-A1`
- `NA10798-NA10798-NA10798-ILMN-LIB-NA10798-ONT-LIB-BJUICE-PREVAL-NA10798-HIOMRS-A1`
- `NA13189-NA13189-NA13189-ILMN-LIB-NA13189-ONT-LIB-BJUICE-PREVAL-NA13189-HIOMRS-A1`
- `NA14732-NA14732-NA14732-ILMN-LIB-NA14732-ONT-LIB-BJUICE-PREVAL-NA14732-HIOMRS-A1`
- `NA14733-NA14733-NA14733-ILMN-LIB-NA14733-ONT-LIB-BJUICE-PREVAL-NA14733-HIOMRS-A1`
- `NA15603-NA15603-NA15603-ILMN-LIB-NA15603-ONT-LIB-BJUICE-PREVAL-NA15603-HIOMRS-A1`
- `NA15848-NA15848-NA15848-ILMN-LIB-NA15848-ONT-LIB-BJUICE-PREVAL-NA15848-HIOMRS-A1`
- `NA15849-NA15849-NA15849-ILMN-LIB-NA15849-ONT-LIB-BJUICE-PREVAL-NA15849-HIOMRS-A1`
- `NA19235-NA19235-NA19235-ILMN-LIB-NA19235-ONT-LIB-BJUICE-PREVAL-NA19235-HIOMRS-A1`
- `NA20027-NA20027-NA20027-ILMN-LIB-NA20027-ONT-LIB-BJUICE-PREVAL-NA20027-HIOMRS-A1`
- `NA20230-NA20230-NA20230-ILMN-LIB-NA20230-ONT-LIB-BJUICE-PREVAL-NA20230-HIOMRS-A1`
- `NA20775-NA20775-NA20775-ILMN-LIB-NA20775-ONT-LIB-BJUICE-PREVAL-NA20775-HIOMRS-A1`

## Packages not yet available

- `NA23687-...-HIOMRS-A1`: HIOMRS core job `6712` was still running; the terminal gVCF/VCF and package manifest were absent at snapshot start. The repaired SR/LR read-group namespace was active.
- `HG002-...-HIOMRS-A1`: LongReadSV phenotype handling and the separate SR fallback completed, but package validation rejected an invalid fallback ALT allele (`GGCGCAGGCGCAGAG.` at `chr1:10621`). No HG002 package manifest was present.

## Terminal artifacts absent at snapshot start

- `DAY_final_multiqc.html`
- `DAY_final_multiqc_data/multiqc_data.json`
- `dayoa_evidence_manifest.json`
- `INFLECTION_delivery_set/delivery_set_manifest.json`

The terminal export must be run or refreshed after controller `rc=0` and all required final artifacts exist.
