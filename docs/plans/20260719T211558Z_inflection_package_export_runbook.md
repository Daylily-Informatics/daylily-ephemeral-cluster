# Inflection package and FSx-to-S3 export example

Created: 2026-07-19T21:15:58Z

## Purpose and boundary

This note describes the exact HG003 1x Inflection package set exported from the
`ifx-p2-1000-120-0715` cluster, what DayOA annotated and packaged, and why the
export used a dedicated FSx staging root. It is an engineering example, not a
customer-release receipt: all four package manifests explicitly say
`NOT_READY_WITH_FAILED_ARTIFACTS` and `customer_release_eligible: false`.

## Exported example

- Batch: `Z-HG003-1X-1307-20260719`
- Source analysis:
  `/fsx/analysis_results/ifx-p2-1000-120-0715/hg003-1x-hiomrs-1307-4attempt-inflection-20260719T072500Z/daylily-omics-analysis`
- Source package path:
  `results/day/hg38/deliveries/inflection/Z-HG003-1X-1307-20260719`
- S3 batch prefix:
  `s3://lsmc-ssf-sequencing-data/derived/analysis_results/cluster_fsx_bulk_export/20260719T203824Z/ifx-p2-1000-120-0715/inflection-package-Z-HG003-1X-1307-20260719-export-20260719T203824Z/Z-HG003-1X-1307-20260719/`
- Export receipt:
  `docs/plans/20260719T203824Z_ifx_hg003_inflection_failed_multiqc_package_export_artifacts/fsx_export.yaml`

The batch contains these four analysis-unit packages:

| Analysis unit | Input subset | Manifest artifact rows | Declared artifact bytes |
|---|---:|---:|---:|
| `HG003-HG003-HG003-HYBRID-LIB-HG003-SR1x-ONT1x-A1` | SR 1x / ONT 1x | 57 | 554,563,550 |
| `HG003-HG003-HG003-HYBRID-LIB-HG003-SR1x-ONT1x-A2` | SR 1x / ONT 1x | 57 | 554,563,664 |
| `HG003-HG003-HG003-HYBRID-LIB-HG003-SR1x-ONT1x-A3-SR0p90-ONT0p90` | 90% of the 1x inputs | 57 | 498,108,511 |
| `HG003-HG003-HG003-HYBRID-LIB-HG003-SR1x-ONT1x-A4-SR0p75-ONT0p75` | 75% of the 1x inputs | 57 | 413,020,834 |

The package tree has 255 regular files totaling 2,020,625,008 bytes. The S3
subtree has the same byte total and 245 nonzero objects, matching the source's
245 nonzero files. Its 88 zero-byte objects are the 10 real zero-byte package
files plus 78 directory markers emitted by the FSx export.

## What is annotated and packaged

Each analysis-unit directory is self-describing through `package_manifest.json`.
Every artifact row records its semantic role, package-relative path, status,
byte count, SHA-256 digest, and materialization method where applicable. The
batch-level `inflection_delivery_manifest.json` and TSV index the four package
manifests and their hashes.

The 57 artifact roles per package fall into these groups:

- Evidence and QC: expected-artifact JSON/TSV, package metrics, package
  compliance, artifact-failure evidence, and SMN concordance JSON/TSV.
- Alignment: the short-read CRAM and CRAI.
- Small variants and copy number: SNV/indel VCF, CNV VCF, mitochondrial VCF,
  and adjacent tabix indexes.
- Structural variants: the selected native Sentieon LongReadSV VCF and index,
  its provenance JSON, plus the TIDDIT VCF and index.
- Repeat expansion: ExpansionHunter VCF, JSON, and tabular report.
- Segmental duplication: the merged VCF/index and summary; VCF/index pairs for
  CFH, CYP11B1, CYP2B6, CYP2D6, GBA1, HBA, NCF1, PMS2, RCCX1, RHD, SBDS, SMN1,
  and STRC; and the non-VCF IKBKG result JSON.
- SMN: native Sentieon SMN summary and SMN1 VCF/index, the
  SMNCopyNumberCaller summary, and generated cross-caller concordance evidence.

Ordinary deliverables are copied into a transactional package staging tree and
verified by size and SHA-256. The large short-read CRAM and CRAI are hardlinked
on FSx to avoid a second local data copy; their hashes and sizes are still
declared in the manifest, and the FSx export writes their bytes to S3. Generated
evidence files are written inside the package so validation travels with the
payload.

This example deliberately preserves failures instead of hiding them. Each
package records an ExpansionHunter VCF without a contig dictionary and an
ambiguous SMNCopyNumberCaller result with no explicit SMN1/SMN2 copy number.
That evidence forces `NOT_READY_WITH_FAILED_ARTIFACTS`, blocks customer release,
and remains inspectable in S3.

## DayOA rules involved

The relevant workflow sequence is:

1. `build_inflection_expected_artifacts` declares the exact source artifacts.
2. `package_inflection_library` validates one analysis unit and produces its
   transactional package plus `package_manifest.json`.
3. `collect_inflection_delivery_manifest` reconciles the per-unit manifests into
   the batch JSON and TSV.
4. `stage_inflection_multiqc` creates manifest-only custom-content inputs.
5. `create_inflection_multiqc_final` renders the Inflection MultiQC reports.
6. `produce_inflection_delivery_set` assembles a delivery set only from the
   validated manifests and reports.

The example reached step 3 for all four units. Its contemporaneous step 5 failed
with no final Inflection HTML, so the export intentionally contains the package
batch rather than claiming a completed delivery set.

## Why the export used a dedicated staging root

`dyec export` exports a top-level analysis directory. Exporting the original
analysis root would have included unrelated workflow products. Under an owned
analysis-root write lock, the exact package directory was therefore hardlinked
into this dedicated root:

`/fsx/analysis_results/ifx-p2-1000-120-0715/inflection-package-Z-HG003-1X-1307-20260719-export-20260719T203824Z`

Source and staging relative paths, inodes, sizes, file counts, and byte totals
were compared before export. The destination prefix was also confirmed empty.
The supported command was then run from the activated DYEC checkout:

```bash
dyec export \
  --cluster ifx-p2-1000-120-0715 \
  --source-path /fsx/analysis_results/ifx-p2-1000-120-0715/inflection-package-Z-HG003-1X-1307-20260719-export-20260719T203824Z \
  --destination-s3-uri s3://lsmc-ssf-sequencing-data/derived/analysis_results/cluster_fsx_bulk_export/20260719T203824Z/ifx-p2-1000-120-0715/inflection-package-Z-HG003-1X-1307-20260719-export-20260719T203824Z/ \
  --profile lsmc \
  --region us-west-2 \
  --output-dir docs/plans/20260719T203824Z_ifx_hg003_inflection_failed_multiqc_package_export_artifacts \
  --wait \
  --timeout-seconds 7200
```

The helper created a temporary DRA, submitted export task
`task-0e80915dbd466b819`, waited for `SUCCEEDED`, retained
`DeleteDataInFileSystem=false`, wrote `fsx_export.yaml`, and deleted temporary
DRA `dra-0231e35b82295fc79`. A live FSx query confirmed that association is gone.
The dedicated staging root remains on FSx because deleting it was not part of
the authorized export.

## DayOA version provenance

There is no pushed DayOA release tag that exactly names the producer state, so a
tag alone is insufficient provenance for this example.

- Nearest tag recorded by the package: `13.0.7`
- Package-recorded describe string: `13.0.7-1-g1818223c-dirty`
- Clean parent commit: `1818223c3dfc9fc9e8227db40a8fc29224406b4d`
- Exact committed producer snapshot: `097afddc8f6c64f35cc97c235d8584d86e437de4`
- Producer-source merge to `main`: PR `#51`, merge commit
  `1d44044cc6a1d62108acd09e831ae2cfb84d49f1`
- MultiQC dependency used by the preserved producer source:
  `1.36.dev0-lsmc.11`

Tag `13.0.11` predates PR #51 and must not be represented as containing this
exact producer snapshot. A future release tag must point at or descend from
`1d44044cc6a1d62108acd09e831ae2cfb84d49f1` before it can be cited as the tagged
release containing these packaging changes.
