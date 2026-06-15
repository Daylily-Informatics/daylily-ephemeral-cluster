# dyecX4 4NA HiOMR SMN12 Combined Caller Report - Status Controls Revision

This revision applies the user-supplied interpretation that NA03986 and NA05164 should be expected `isSMA=False` and `smaCarrier=False`, while still preserving that no accessible SMN1/SMN2 copy-number truth claim was provided for those two samples. NA09677 and NA00232 remain the only published SMN copy-number controls in this report.

## Evidence Location

- Results S3 root: `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/hiomr_smn12_4na_chip4sub_20260612T015845Z/`
- Analysis S3 root: `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/hiomr_smn12_4na_chip4sub_20260612T015845Z/daylily-omics-analysis/`
- Revised report S3 URI: `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/hiomr_smn12_4na_chip4sub_20260612T015845Z/20260612T154500Z_dyecX4_4na_smn12_combined_report_status_controls.md`
- Local revised report: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260612T154500Z_dyecX4_4na_smn12_combined_report_status_controls.md`
- Full VCF manifest S3 URI: `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/hiomr_smn12_4na_chip4sub_20260612T015845Z/20260612T150000Z_dyecX4_4na_smn12_variant_manifest.tsv`
- Full evidence manifest S3 URI: `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/hiomr_smn12_4na_chip4sub_20260612T015845Z/20260612T150000Z_dyecX4_4na_smn12_evidence_manifest.tsv`
- Export receipt S3 URI: `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/hiomr_smn12_4na_chip4sub_20260612T015845Z/20260612T150000Z_dyecX4_4na_smn12_fsx_export.yaml`
- Analysis root on dyecX4: `/fsx/analysis_results/ubuntu/hiomr_smn12_4na_chip4sub_20260612T015845Z/daylily-omics-analysis`

## Control Claims And Expectations Used For Scoring

| sample | basis | claim_or_expectation | other_known_variant_control_use | references |
| --- | --- | --- | --- | --- |
| NA09677 | Published SMN CN control | SMA1 affected; SMN1 homozygous exon 7-8 deletion / 2-copy loss; SMN2 3 copies | PacBio PureTarget demo also lists SMN1 2-copy loss affected. | [Coriell NA09677][1]; [PacBio PureTarget poster][2] |
| NA00232 | Published SMN CN control | SMA1 affected; SMN1 homozygous exon 7-8 deletion / 2-copy loss; SMN2 2 copies | PacBio PureTarget demo also lists SMN1 2-copy loss affected. | [Coriell NA00232][3]; [PacBio PureTarget poster][2] |
| NA05164 | User-supplied SMN status expectation; no accessible SMN CN truth | No accessible SMN1/SMN2 copy-number claim found. Interpret as expected isSMA=False and smaCarrier=False per user instruction. | DM1 / DMPK CTG expansion: Coriell 21 / ~340 CTG; CDC GeT-RM consensus 21 / 377 +/- 53. | [Coriell NA05164][4]; [CDC GeT-RM DM1 allele sizes][5] |
| NA03986 | User-supplied SMN status expectation; no accessible SMN CN truth | No accessible SMN1/SMN2 copy-number claim found. Interpret as expected isSMA=False and smaCarrier=False per user instruction. | DM1 / DMPK CTG expansion: Coriell Southern blot 0-1.5 kb, up to ~500 CTG repeats. | [Coriell NA03986][6] |

## Top-Level Result

All eight 4NA units completed with `RETURN CODE: 0`. Each unit produced terminal output for five SMN12 evidence sources: SMNCopyNumberCaller, SMAca, Broad sma-finder, HapSMA, and Sentieon HiOMR segdup SMN1. DayOA checkout was `10.0.4-16-geb9dcb2`.

| sample | basis | claim_or_expectation | units | smncopy_calls | smncopy_status | sentieon_calls | sma_finder | interpretation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NA09677 | Published SMN CN control | SMA1 affected; SMN1 homozygous exon 7-8 deletion / 2-copy loss; SMN2 3 copies | chip1-chip2, chip3-chip4 | 0/1 | isSMA=True; carrier=False | 0/1 | has SMA | SMN1 loss status matches affected control; SMN2 copy count is under-called versus published claim |
| NA00232 | Published SMN CN control | SMA1 affected; SMN1 homozygous exon 7-8 deletion / 2-copy loss; SMN2 2 copies | chip1-chip2, chip4-only-sub-for-missing-chip3 | 0/1 | isSMA=True; carrier=False | 0/1 | has SMA | SMN1 loss status matches affected control; SMN2 copy count is under-called versus published claim |
| NA05164 | User-supplied SMN status expectation; no accessible SMN CN truth | No accessible SMN1/SMN2 copy-number claim found. Interpret as expected isSMA=False and smaCarrier=False per user instruction. | chip1-chip2, chip4-only-sub-for-missing-chip3 | 1/0 | isSMA=False; carrier=True | 0/1 | not enough coverage at SMN c.840 position | Expected non-SMA/non-carrier; SMNCopy reports non-SMA but carrier=True, and Sentieon CN should be interpreted cautiously because no published SMN CN truth is available |
| NA03986 | User-supplied SMN status expectation; no accessible SMN CN truth | No accessible SMN1/SMN2 copy-number claim found. Interpret as expected isSMA=False and smaCarrier=False per user instruction. | chip1-chip2, chip4-only-sub-for-missing-chip3 | 1/0 | isSMA=False; carrier=True | 1/0 | not enough coverage at SMN c.840 position | Expected non-SMA/non-carrier; SMNCopy reports non-SMA but carrier=True, and Sentieon CN should be interpreted cautiously because no published SMN CN truth is available |

Key interpretation: NA09677 and NA00232 match affected status through SMN1 loss (`SMN1=0`) by both SMNCopy and Sentieon, but both callers report `SMN2=1`, below the provided published SMN2 claims (`3` and `2`, respectively). NA03986 and NA05164 are now interpreted as expected non-SMA/non-carrier status controls: SMNCopy matches `isSMA=False` but reports `carrier=True` for both, so SMNCopy carrier status conflicts with the supplied expectation. Sentieon copy-number calls for NA03986 (`1/0`) and NA05164 (`0/1`) are reported, but those two samples do not have accessible SMN CN truth claims in this report.

## Per-Unit Caller Matrix

| na | unit | control_basis | expected_status | published_smn_cn | ont_fastqs | chip_counts | smncopy | smncopy_status_vs_control | smncopy_cn_vs_control | sentieon | sentieon_vs_control | sma_finder | smaca | hapsma |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NA00232 | chip1-chip2 | Published SMN CN control | isSMA=True; smaCarrier=False | SMN1/SMN2 0/2 | 146 | chip1:73,chip2:73 | 0/1; isSMA=True; carrier=False | isSMA match (True vs True); carrier match (False vs False) | SMN1 match (0 vs 0); SMN2 differs (1 vs 2) | 0/1 | SMN1 match (0 vs 0); SMN2 differs (1 vs 2) | has SMA (score 13; c840 0/14) | Pi=0.0/0.0/0.0; cov SMN1/2=4.72/7.01 | cov=7.71; no_call_no_phase_set/no_call_no_phase_set |
| NA00232 | chip4-only-sub-for-missing-chip3 | Published SMN CN control | isSMA=True; smaCarrier=False | SMN1/SMN2 0/2 | 73 | chip4:73 | 0/1; isSMA=True; carrier=False | isSMA match (True vs True); carrier match (False vs False) | SMN1 match (0 vs 0); SMN2 differs (1 vs 2) | 0/1 | SMN1 match (0 vs 0); SMN2 differs (1 vs 2) | has SMA (score 13; c840 0/14) | Pi=0.0/0.0/0.0; cov SMN1/2=4.72/7.01 | cov=3.32; no_call_low_coverage/no_call_low_coverage |
| NA03986 | chip1-chip2 | User-supplied SMN status expectation; no accessible SMN CN truth | isSMA=False; smaCarrier=False | not available | 146 | chip1:73,chip2:73 | 1/0; isSMA=False; carrier=True | isSMA match (False vs False); carrier differs (True vs False) | no published SMN CN truth; SMNCopy would be carrier-like by SMN1 CN alone; conflicts with expected smaCarrier=False | 1/0 | no published SMN CN truth; Sentieon would be carrier-like by SMN1 CN alone; conflicts with expected smaCarrier=False | not enough coverage at SMN c.840 position (score 0; c840 6/10) | Pi=0.3333333333333333/0.6/0.7142857142857143; cov SMN1/2=6.86/6.42 | cov=6.11; no_call_no_phase_set/no_call_no_phase_set |
| NA03986 | chip4-only-sub-for-missing-chip3 | User-supplied SMN status expectation; no accessible SMN CN truth | isSMA=False; smaCarrier=False | not available | 73 | chip4:73 | 1/0; isSMA=False; carrier=True | isSMA match (False vs False); carrier differs (True vs False) | no published SMN CN truth; SMNCopy would be carrier-like by SMN1 CN alone; conflicts with expected smaCarrier=False | 1/0 | no published SMN CN truth; Sentieon would be carrier-like by SMN1 CN alone; conflicts with expected smaCarrier=False | not enough coverage at SMN c.840 position (score 0; c840 6/10) | Pi=0.3333333333333333/0.6/0.7142857142857143; cov SMN1/2=6.86/6.42 | cov=2.81; no_call_low_coverage/no_call_low_coverage |
| NA05164 | chip1-chip2 | User-supplied SMN status expectation; no accessible SMN CN truth | isSMA=False; smaCarrier=False | not available | 146 | chip1:73,chip2:73 | 1/0; isSMA=False; carrier=True | isSMA match (False vs False); carrier differs (True vs False) | no published SMN CN truth; SMNCopy would be carrier-like by SMN1 CN alone; conflicts with expected smaCarrier=False | 0/1 | no published SMN CN truth; Sentieon would be affected-like by SMN1 CN alone; conflicts with expected isSMA=False | not enough coverage at SMN c.840 position (score 0; c840 2/5) | Pi=0.5/0.4/0.47368421052631576; cov SMN1/2=4.38/5.27 | cov=5.49; no_call_no_phase_set/no_call_no_phase_set |
| NA05164 | chip4-only-sub-for-missing-chip3 | User-supplied SMN status expectation; no accessible SMN CN truth | isSMA=False; smaCarrier=False | not available | 73 | chip4:73 | 1/0; isSMA=False; carrier=True | isSMA match (False vs False); carrier differs (True vs False) | no published SMN CN truth; SMNCopy would be carrier-like by SMN1 CN alone; conflicts with expected smaCarrier=False | 0/1 | no published SMN CN truth; Sentieon would be affected-like by SMN1 CN alone; conflicts with expected isSMA=False | not enough coverage at SMN c.840 position (score 0; c840 2/5) | Pi=0.5/0.4/0.47368421052631576; cov SMN1/2=4.38/5.27 | cov=2.35; no_call_low_coverage/no_call_low_coverage |
| NA09677 | chip1-chip2 | Published SMN CN control | isSMA=True; smaCarrier=False | SMN1/SMN2 0/3 | 146 | chip1:73,chip2:73 | 0/1; isSMA=True; carrier=False | isSMA match (True vs True); carrier match (False vs False) | SMN1 match (0 vs 0); SMN2 differs (1 vs 3) | 0/1 | SMN1 match (0 vs 0); SMN2 differs (1 vs 3) | has SMA (score 21; c840 0/22) | Pi=0.0/0.0/0.0; cov SMN1/2=6.55/8.37 | cov=7.24; no_call_no_phase_set/no_call_no_phase_set |
| NA09677 | chip3-chip4 | Published SMN CN control | isSMA=True; smaCarrier=False | SMN1/SMN2 0/3 | 82 | chip3:9,chip4:73 | 0/1; isSMA=True; carrier=False | isSMA match (True vs True); carrier match (False vs False) | SMN1 match (0 vs 0); SMN2 differs (1 vs 3) | 0/1 | SMN1 match (0 vs 0); SMN2 differs (1 vs 3) | has SMA (score 21; c840 0/22) | Pi=0.0/0.0/0.0; cov SMN1/2=6.55/8.37 | cov=3.83; no_call_low_coverage/no_call_low_coverage |

## Caller Completion Counts

| caller | complete_rows | expected_rows |
| --- | --- | --- |
| smn12 | 8 | 8 |
| smaca | 8 | 8 |
| sma_finder | 8 | 8 |
| hapsma | 8 | 8 |
| sentieon_segdup_smn1 | 8 | 8 |

## Variant And Evidence Manifests

- Full VCF manifest: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260612T150000Z_dyecX4_4na_smn12_variant_manifest.tsv` / `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/hiomr_smn12_4na_chip4sub_20260612T015845Z/20260612T150000Z_dyecX4_4na_smn12_variant_manifest.tsv`
- Full SMN12 evidence manifest: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260612T150000Z_dyecX4_4na_smn12_evidence_manifest.tsv` / `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/hiomr_smn12_4na_chip4sub_20260612T015845Z/20260612T150000Z_dyecX4_4na_smn12_evidence_manifest.tsv`
- VCF/VCF.GZ non-index counts: HapSMA=72, Sentieon HiOMR segdup SMN1=8
- Total VCF manifest rows including indexes: `152`
- Total non-index VCF/VCF.GZ rows: `80`

## Commands

Headnode workflow commands were run inside persistent `ubuntu` tmux sessions using the DayOA wrapper, not raw Snakemake:

```bash
cd /fsx/analysis_results/ubuntu/hiomr_smn12_4na_chip4sub_20260612T015845Z/daylily-omics-analysis
source dyoainit
dy-a slurm hg38_broad
dy-r produce_smn12_orthogonal_calls produce_htd_calls produce_sentdhiomr_segdup -p -T 0 -k -j 500 --rerun-triggers mtime -n
dy-r produce_smn12_orthogonal_calls produce_htd_calls produce_sentdhiomr_segdup -p -T 0 -k -j 500 --rerun-triggers mtime
dy-r produce_smn12_orthogonal_calls produce_htd_calls produce_sentdhiomr_segdup -p -T 0 -k -j 500 --rerun-triggers mtime --rerun-incomplete
```

DRA export command for the final analysis:

```bash
cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate
dyec export --cluster-name dyecX4 --source-path /fsx/analysis_results/ubuntu/hiomr_smn12_4na_chip4sub_20260612T015845Z --destination-s3-uri s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/hiomr_smn12_4na_chip4sub_20260612T015845Z/ --region us-west-2 --profile lsmc --output-dir docs/plans/20260612T150000Z_dyecX4_4na_smn12_export_receipt --wait --timeout-seconds 3600
```

## Runtime And Model Evidence

- Final log return: `RETURN CODE: 0`
- Dry-run planned jobs: `104`
- Resource summary: 192-thread rules included HapSMA, Sentieon HiOMR segdup gene calling, Sentieon SR alignment, sentmm2ont alignment/sort, sma-finder, SMAca, and SMNCopyNumberCaller; final sentmm2ont repair used i384nvme, 192 threads, and 650000 MB.
| field | value |
| --- | --- |
| Sentieon segdup LR model | /fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.02/bundles/DNAscopeONT2.3.bundle |
| Sentieon segdup SR model | /fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.02/bundles/SentieonIlluminaWGS2.2.bundle |
| Sentieon segdup threads | 192 |
| segdup-caller version | 0.5.1 |
| Sentieon version | 202503.02 |

## Interpretation Boundaries

- SMNCopyNumberCaller and Sentieon HiOMR segdup are the two sources in this run that directly emitted SMN1/SMN2 copy numbers.
- SMNCopy also emits `isSMA` and `isCarrier`; those are the status fields used for NA03986 and NA05164 under the new supplied expectation.
- Broad sma-finder emitted affected-status evidence only; it does not emit SMN1/SMN2 copy number or carrier status.
- SMAca completed and emitted raw coverage/Pi fields, but the current DayOA summary does not translate SMAca into final SMN1/SMN2 copy-number fields.
- HapSMA completed as a dev/exploratory long-read caller. It generated variant/phasing intermediates where coverage allowed, but all units are no-call for phase-set/SMN haplotype status in the summary table.
- `chip4-only-sub-for-missing-chip3` rows are explicitly approved substitutes where chip3 FASTQs were missing for that barcode. `NA09677 chip3-chip4` is the only true chip3+chip4 row.

## References

[1]: https://catalog.coriell.org/0/Sections/Search/Sample_Detail.aspx?Product=DNA&Ref=NA09677
[2]: https://www.pacb.com/wp-content/uploads/Belyeu_ASHG_2025_poster.pdf?utm_source=chatgpt.com
[3]: https://catalog.coriell.org/0/Sections/Search/Sample_Detail.aspx?Product=DNA&Ref=NA00232
[4]: https://catalog.coriell.org/0/Sections/Search/Sample_Detail.aspx?Ref=NA05164
[5]: https://www.cdc.gov/lab-quality/media/pdfs/2024/08/GeT-Rm-DM1-Allele-Sizes.pdf
[6]: https://catalog.coriell.org/0/Sections/Search/Sample_Detail.aspx?Ref=NA03986&product=DNA

## Source Artifacts Used To Build This Report

- Local report input package: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260612T_report_4na_smn12_inputs`
- Aggregate orthogonal caller TSV: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260612T_report_4na_smn12_inputs/results/day/hg38_broad/other_reports/smn12_orthogonal_calls_mqc.tsv`
- Aggregate HTD caller TSV: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260612T_report_4na_smn12_inputs/results/day/hg38_broad/other_reports/htd_calls_mqc.tsv`
- Previous revised controls report: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260612T153000Z_dyecX4_4na_smn12_combined_report_revised_controls.md`
- DYEC ledger: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260611T164617Z_dyecX4_4na_hiomr_smn12_validation_ledger.md`
