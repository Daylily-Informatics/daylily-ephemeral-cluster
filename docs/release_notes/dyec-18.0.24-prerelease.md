# DYEC 18.0.24 prerelease

> **AWS credential notice.** This release work used the still overly-permissioned `lsmc` AWS profile. Josh Durham (@jdurham38) is actively porting the workflow to a tightly scoped IAM role; that work is underway. The existing profile is not the desired steady-state permission boundary.

## Release status

This is a prerelease. It is intentionally not merged to `main`, and no Git tests were run while creating it at the user's direction. The next gate is a user-run complete command-catalog test cycle against the two prerelease tags. If that succeeds, the branch may be merged to `main`; the complete repository suite follows that merge.

## What changed

- All active current catalog commands now pin immutable DayOA `15.0.14`. This tag is the exact DayOA `15.0.12` source commit; it carries no new DayOA source or environment-YAML change. The unused `15.0.13` tag is not selected.
- The ILMN, ONT, Ultima, and CG solo kitchensinks explicitly pass numeric chromosome scope `1-25` in both live and dry command definitions.
- The direct long BJuice command is renamed to `inflection-bjuice-product-v0.9`. It uses the existing slim-data BJuice contract, default-selects all supplied ONT FASTQs, and retains only the explicit global slice escape hatch: pass both `--dy-config use_fq_data_starting_hrs=<n>` and `--dy-config use_fq_data_up_to_hrs=<n+n>`. The former per-analysis-unit ONT selector is absent.
- The current source catalog and packaged catalog mirror were changed together.
- Pulled the outstanding pcand-18022 catalog-evidence commit `58da516c2e1ea541dcced27ab6ee8641546be9d7`; the other recent catalog updates were already ancestors of DYEC 18.0.23.

## Merged operational runbook

The release runbook consolidates the three 18.0.22 pcand-18022 runbooks, including mounts, controller boundaries, historical rc=0 receipts, no-delete export tasks, and the new prerelease gates:

- [RELASE-18.0.24-runbook.md](https://github.com/lsmc-bio/daylily-ephemeral-cluster/blob/18.0.24/docs/runbooks/18.0.24/RELASE-18.0.24-runbook.md)

## Validated command-catalog evidence

This inventory records current-catalog entries with a recorded successful validation run and their available S3 evidence. A dash means the current catalog records only an FSx or repository-document receipt, not an S3 URI.

| Catalog command | Successful receipt(s) | S3 evidence URI(s) |
| --- | --- | --- |
| `illumina_snv_alignstats` | `tstver411b_dayoa_catalog_recipe_validation` | — |
| `illumina_snv_alignstats_relatedness_vep_multiqc` | `tstver411b_dayoa_catalog_recipe_validation` | — |
| `illumina_hg002_kitchensink_multiqc` | `pcand18015_ilmn_solo_slim_1510_ccenter_20260817t020600z_live` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18015/pcand18015_ilmn_solo_slim_1510_ccenter_20260817t020600z_live/` |
| `ultima_snv_alignstats` | `tstver411b_dayoa_catalog_recipe_validation` | — |
| `ultima_snv_alignstats_kitchensink` | `pcand18015_ultima_solo_slim_1510_ccenter_20260817t021200z_live` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18015/pcand18015_ultima_solo_slim_1510_ccenter_20260817t021200z_live/` |
| `ont_snv_alignstats` | `tstver411b_dayoa_catalog_recipe_validation` | — |
| `ont_snv_alignstats_kitchensink` | `pcand18015_ont_solo_slim_1510_ccenter_20260817t020900z_live` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18015/pcand18015_ont_solo_slim_1510_ccenter_20260817t020900z_live/` |
| `pacbio_snv_alignstats` | `tstver411b_dayoa_catalog_recipe_validation` | — |
| `complete_genomics_cg_snv_concordance` | `prod-cand-1703-cg-slim-20260814-1032` | `s3://lsmc-ssf-sequencing-data/derived/prod-cand-1703/pc1703-cg-solo-ks-17014-20260814-1032/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc.html` |
| `illumina_run_qc` | `preval_ilmn_run_qc_rnd_final_20260727T053100Z`, `pcand18015_ilmn_runqc_1509_live2_20260816T1404Z`, `pcand18022_ilmn_seq_qc_15011_live_20260817T0712Z` | `s3://lsmc-ssf-sequencing-data/preval-hiomr2/preval_ilmn_run_qc_rnd_final_20260727T053100Z/results/runs/20260618_LH01106_0011_A23MFMCLT3/run_qc/illumina/multiqc_report.html`<br>`s3://lsmc-ssf-sequencing-data/derived/pcand-18015/pcand18015_ilmn_runqc_1509_live2_20260816T1404Z/daylily-omics-analysis/results/runs/20260618_LH01106_0011_A23MFMCLT3/run_qc/illumina/multiqc_report.html`<br>`s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022_ilmn_seq_qc_15011_live_20260817T0712Z/daylily-omics-analysis/results/runs/20260618_LH01106_0011_A23MFMCLT3/run_qc/illumina/multiqc_report.html` |
| `ont_run_qc` | `pc1703-ont-set4fc1-seqqc-17018-20260814`, `pcand18015_ont_runqc_1509_live_20260816T1422Z`, `pcand18022_ont_seq_qc_15011_live_20260817T0752Z` | `s3://lsmc-ssf-sequencing-data/derived/prod-cand-1703/pc1703-ont-set4fc1-seqqc-17018-20260814/daylily-omics-analysis/results/runs/20260615_ONT_Set4-FC1/run_qc/ont/multiqc_report.html`<br>`s3://lsmc-ssf-sequencing-data/derived/pcand-18015/pcand18015_ont_runqc_1509_live_20260816T1422Z/daylily-omics-analysis/results/runs/20260615_ONT_Set4-FC1/run_qc/ont/multiqc_report.html`<br>`s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022_ont_seq_qc_15011_live_20260817T0752Z/daylily-omics-analysis/results/runs/20260615_ONT_Set4-FC1/run_qc/ont/multiqc_report.html` |
| `ultima_run_qc` | `pcand18015_ultima_runqc_1509_live_20260816T1513Z`, `pcand18022_ultima_seq_qc_15011_live_20260817T0734Z` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18015/pcand18015_ultima_runqc_1509_live_20260816T1513Z/daylily-omics-analysis/results/runs/604834-20260717_2309/run_qc/ultima/ultima_native.multiqc.html`<br>`s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022_ultima_seq_qc_15011_live_20260817T0734Z/daylily-omics-analysis/results/runs/604834-20260717_2309/run_qc/ultima/ultima_native.multiqc.html` |
| `inflection-bjuice-product-v0.2` (alias) | `pcand18022-hg002-slim5x5x-bjuice-ifx-20260817t0648z` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022-hg002-slim5x5x-bjuice-ifx-20260817t0648z/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc_data/multiqc_giab_concordance.txt` |
| `hiomr2_slim_kitchensink_mega` | `pcand18022-hg002-slim5x5x-hiomr2-20260817t0648z` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022-hg002-slim5x5x-hiomr2-20260817t0648z/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc_data/multiqc_giab_concordance.txt` |

The newly released 1-25 solo definitions and `inflection-bjuice-product-v0.9` have no fresh prerelease validation receipt yet. The historical controllers are deliberately not claimed as proof of their new contracts.

## pcand-18022 solo no-delete export receipts

All four historical solo controllers reached rc=0, and the following fresh no-delete DRA exports reached `SUCCEEDED`, detached their DRA association, and retained FSx data:

| Lane | DRA task | S3 root |
| --- | --- | --- |
| ILMN | `task-04d38f6f3f9f1686e` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/analysis_results/pcand18022-ilmn-solo-slim-1511-20260817t075549z-live-r1/` |
| ONT | `task-0beaff08d9ff23808` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/analysis_results/pcand18022-ont-solo-slim-1512-20260817t082933z-live-r2/` |
| Ultima | `task-087be8073f7e2dd05` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/analysis_results/pcand18022-ultima-solo-slim-1511-20260817t075549z-live-r1/` |
| CG | `task-0c093fafedd2f991f` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/analysis_results/pcand18022-cg-solo-slim-1511-20260817t075549z-live-r1/` |

No FSx deletion was performed for these four exports.
