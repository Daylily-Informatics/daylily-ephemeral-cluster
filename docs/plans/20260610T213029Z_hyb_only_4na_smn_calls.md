# hyb-only 4NA SMN calls

Analysis:
`hybonly_hybrid_hiomr_na4_ds20x_x8_fullvars_5017_20260607T124257Z`

Export root:
`s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/hybonly_hybrid_hiomr_na4_ds20x_x8_fullvars_5017_20260607T124257Z/daylily-omics-analysis/`

Sentieon source pattern:
`results/day/hg38_broad/<unit>/align/sentmm2ont/dmd/segdup/sentdhiomr/results/SMN1/<unit>.SMN1.yaml`

SMNCopyNumberCaller source pattern:
`results/day/hg38_broad/<unit>/align/sent/dmd/htd/smn12/<unit>.summary.tsv`

## Collapsed 4NA calls

Both units for each NA produced identical calls within each caller.

| NA | Units | Sentieon SMN1 | Sentieon SMN2 | Sentieon SMN1 VCF variants | SMNCopy SMN1 | SMNCopy SMN2 | SMNCopy SMN2delta7-8 | SMNCopy isSMA | SMNCopy isCarrier | Caller agreement |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | --- | --- | --- |
| NA00232 | chip1+chip2; chip3+chip4 | 0 | 1 | none | 0 | 1 | 0 | True | False | agree |
| NA09677 | chip1+chip2; chip3+chip4 | 0 | 1 | none | 0 | 1 | 0 | True | False | agree |
| NA03986 | chip1+chip2; chip3+chip4 | 1 | 0 | none | 1 | 0 | 0 | False | True | agree |
| NA05164 | chip1+chip2; chip3+chip4 | 0 | 1 | none | 1 | 0 | 0 | False | True | discordant |

## SMNCopy raw values

| NA | Total_CN_raw | Full_length_CN_raw | g.27134T>G_CN | Info | Median_depth | Coverage_MAD |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| NA00232 | 0.922 | 1.031 | 0 | PASS:Majority | 27.18 | 0.091 |
| NA09677 | 1.096 | 1.545 | 0 | PASS:Majority | 27.56 | 0.095 |
| NA03986 | 0.980 | 0.985 | 0 | PASS:Majority | 28.54 | 0.101 |
| NA05164 | 0.711 | 0.820 | 0 | PASS:Majority | 27.94 | 0.098 |

## Sentieon metadata

- `segdup-caller`: `0.5.1`
- `sentieon`: `202503.02`
- Sentieon SMN1 VCFs had no non-header variant rows for all eight units.
- Sentieon YAMLs reference `DNAscopeONT2.2.bundle` and `SentieonIlluminaWGS2.2.bundle`.
