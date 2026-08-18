# Bjuice Validation Guidance

Inventory snapshot: `2026-08-18T11:55:36+00:00`

Scope: non-prevalence Betelgeuse/Bjuice validation only

Configuration state: `CONFIG_COMPLETE`

Execution state: `LAUNCH_BLOCKED`

No DayOA controller, dry-run controller, workflow, cluster, DRA, run mount, S3 write,
OWY repair, release, or cleanup was started while producing this guidance. The commands
near the end are retained for a future explicitly approved dry run; they were not executed.

## Outcome

The workbook maps 157 rows across four logical validation runs. Ninety-nine rows have both
an Illumina and an ONT alias and are eligible for hybrid analysis; 29 are ILMN-only and 29
are ONT-only. Bundle 1 is deliberately represented twice because two distinct ILMN runs use
the same Run 1 ONT cohort.

| Bundle | ILMN run | ONT cohort | Hybrid AUs | Capsule |
|---|---|---|---:|---|
| `bundle1a` | `20260624_LH01106_0012_A23WW3CLT4` | `20260626_ONT_BGS_ValR1_Set1` through `Set8` | 32 | `docs/jem/bjuice_validation/configs/bundle1a/` |
| `bundle1b` | `20260629_LH01106_0014_B23WV5HLT4` | same Run 1 ONT inputs as Bundle 1a | 32 | `docs/jem/bjuice_validation/configs/bundle1b/` |
| `bundle2` | `20260624_LH01106_0013_B23M753LT3` | `20250629_ONT_BGS_Run2_Set1` through `Set8` | 19 | `docs/jem/bjuice_validation/configs/bundle2/` |
| `bundle3` | `20260701_LH01106_0015_B23M5J7LT3` | `20260713_ONT_BGS_Run3_Set1` through `Set8` | 17 | `docs/jem/bjuice_validation/configs/bundle3/` |
| `bundle4` | `20260722_LH01106_0016_A23WW3YLT4` | `20260723_ONT_BGS_Run4_Set1` through `Set8` | 31 | `docs/jem/bjuice_validation/configs/bundle4/` |

Run 2's `pca100/2025/20250629_...` source names are literal preserved run-directory
names. They are not corrected dates.

## Source authority and inventory result

The sequencers write run directories to xfer1/SeqNAS and OWY publishes those preserved
directory names under `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/`. Read-only
checks used AWS profile `lsmc`, region `us-west-2`, account `108782052779`, and ARN
`arn:aws:iam::108782052779:root`. Bucket transfer acceleration was `Enabled`.

The canonical xfer1 DNS name did not resolve from the operator Mac. The authenticated
Tailnet peer map explicitly identified online peer `sfo1-xfer1.faun-salmon.ts.net` for
host `sfo1-xfer1`; read-only source checks used that peer as `johnm`. All five ILMN and all
32 ONT directories were present. Every ILMN run had `CopyComplete.txt`; every ONT Set had
three `final_summary_*.txt`, three `output_hash_*.csv`, and three `report_*.json` files.

The S3 inventory contains 450,599 objects and 38,603,057,564,236 bytes. All 37 roots are
nonempty and vendor-ready. None has canonical root `OOW.done`; none is launchable under
the OWY publication contract.

| Source | Platform | Canonical S3 URI | SeqNAS path | Objects | Bytes | Latest UTC | Ready | `OOW.done` |
|---|---|---|---|---:|---:|---|---|---|
| `ilmn-run1a` | ILMN | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260624_LH01106_0012_A23WW3CLT4/` | `/mnt/seqdata/LH01106/20260624_LH01106_0012_A23WW3CLT4` | 78,759 | 7,344,337,043,143 | `2026-06-27T04:21:40+00:00` | yes | **no** |
| `ilmn-run1b` | ILMN | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260629_LH01106_0014_B23WV5HLT4/` | `/mnt/seqdata/LH01106/20260629_LH01106_0014_B23WV5HLT4` | 78,861 | 8,473,513,300,755 | `2026-07-02T03:57:26+00:00` | yes | **no** |
| `ilmn-run2` | ILMN | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260624_LH01106_0013_B23M753LT3/` | `/mnt/seqdata/LH01106/20260624_LH01106_0013_B23M753LT3` | 76,380 | 3,231,975,613,163 | `2026-06-26T18:41:26+00:00` | yes | **no** |
| `ilmn-run3` | ILMN | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260701_LH01106_0015_B23M5J7LT3/` | `/mnt/seqdata/LH01106/20260701_LH01106_0015_B23M5J7LT3` | 76,514 | 3,178,177,598,586 | `2026-07-02T22:40:22+00:00` | yes | **no** |
| `ilmn-run4` | ILMN | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260722_LH01106_0016_A23WW3YLT4/` | `/mnt/seqdata/LH01106/20260722_LH01106_0016_A23WW3YLT4` | 78,885 | 8,286,984,089,094 | `2026-08-11T02:42:29+00:00` | yes | **no** |
| `ont-run1-set1` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260626_ONT_BGS_ValR1_Set1/` | `/mnt/seqdata/pca100/20260626_ONT_BGS_ValR1_Set1` | 3,515 | 376,695,621,796 | `2026-06-29T20:12:06+00:00` | yes | **no** |
| `ont-run1-set2` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260626_ONT_BGS_ValR1_Set2/` | `/mnt/seqdata/pca100/20260626_ONT_BGS_ValR1_Set2` | 3,384 | 398,734,804,772 | `2026-06-29T20:14:04+00:00` | yes | **no** |
| `ont-run1-set3` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260626_ONT_BGS_ValR1_Set3/` | `/mnt/seqdata/pca100/20260626_ONT_BGS_ValR1_Set3` | 3,473 | 425,239,813,029 | `2026-06-29T20:16:00+00:00` | yes | **no** |
| `ont-run1-set4` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260626_ONT_BGS_ValR1_Set4/` | `/mnt/seqdata/pca100/20260626_ONT_BGS_ValR1_Set4` | 4,124 | 361,524,503,104 | `2026-06-29T20:17:47+00:00` | yes | **no** |
| `ont-run1-set5` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260626_ONT_BGS_ValR1_Set5/` | `/mnt/seqdata/pca100/20260626_ONT_BGS_ValR1_Set5` | 3,115 | 366,932,513,975 | `2026-06-29T20:19:36+00:00` | yes | **no** |
| `ont-run1-set6` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260626_ONT_BGS_ValR1_Set6/` | `/mnt/seqdata/pca100/20260626_ONT_BGS_ValR1_Set6` | 3,308 | 318,254,446,429 | `2026-06-29T20:21:29+00:00` | yes | **no** |
| `ont-run1-set7` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260626_ONT_BGS_ValR1_Set7/` | `/mnt/seqdata/pca100/20260626_ONT_BGS_ValR1_Set7` | 3,480 | 378,630,504,031 | `2026-06-29T20:23:33+00:00` | yes | **no** |
| `ont-run1-set8` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260626_ONT_BGS_ValR1_Set8/` | `/mnt/seqdata/pca100/20260626_ONT_BGS_ValR1_Set8` | 4,363 | 535,739,595,900 | `2026-06-29T20:26:11+00:00` | yes | **no** |
| `ont-run2-set1` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2025/20250629_ONT_BGS_Run2_Set1/` | `/mnt/seqdata/pca100/20250629_ONT_BGS_Run2_Set1` | 1,185 | 179,384,166,630 | `2026-07-01T01:13:39+00:00` | yes | **no** |
| `ont-run2-set2` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2025/20250629_ONT_BGS_Run2_Set2/` | `/mnt/seqdata/pca100/20250629_ONT_BGS_Run2_Set2` | 1,166 | 202,889,951,157 | `2026-07-01T01:15:05+00:00` | yes | **no** |
| `ont-run2-set3` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2025/20250629_ONT_BGS_Run2_Set3/` | `/mnt/seqdata/pca100/20250629_ONT_BGS_Run2_Set3` | 1,353 | 197,311,275,983 | `2026-07-01T01:16:34+00:00` | yes | **no** |
| `ont-run2-set4` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2025/20250629_ONT_BGS_Run2_Set4/` | `/mnt/seqdata/pca100/20250629_ONT_BGS_Run2_Set4` | 1,289 | 192,172,819,239 | `2026-07-01T01:18:08+00:00` | yes | **no** |
| `ont-run2-set5` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2025/20250629_ONT_BGS_Run2_Set5/` | `/mnt/seqdata/pca100/20250629_ONT_BGS_Run2_Set5` | 1,343 | 198,562,772,666 | `2026-07-01T01:19:33+00:00` | yes | **no** |
| `ont-run2-set6` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2025/20250629_ONT_BGS_Run2_Set6/` | `/mnt/seqdata/pca100/20250629_ONT_BGS_Run2_Set6` | 1,184 | 214,214,745,311 | `2026-07-01T01:21:03+00:00` | yes | **no** |
| `ont-run2-set7` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2025/20250629_ONT_BGS_Run2_Set7/` | `/mnt/seqdata/pca100/20250629_ONT_BGS_Run2_Set7` | 1,300 | 203,501,305,278 | `2026-07-01T01:22:35+00:00` | yes | **no** |
| `ont-run2-set8` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2025/20250629_ONT_BGS_Run2_Set8/` | `/mnt/seqdata/pca100/20250629_ONT_BGS_Run2_Set8` | 1,662 | 226,710,509,230 | `2026-07-01T01:24:16+00:00` | yes | **no** |
| `ont-run3-set1` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260713_ONT_BGS_Run3_Set1/` | `/mnt/seqdata/pca100/20260713_ONT_BGS_Run3_Set1` | 1,235 | 224,983,682,708 | `2026-07-15T01:39:09+00:00` | yes | **no** |
| `ont-run3-set2` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260713_ONT_BGS_Run3_Set2/` | `/mnt/seqdata/pca100/20260713_ONT_BGS_Run3_Set2` | 1,142 | 204,851,881,217 | `2026-07-15T01:40:37+00:00` | yes | **no** |
| `ont-run3-set3` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260713_ONT_BGS_Run3_Set3/` | `/mnt/seqdata/pca100/20260713_ONT_BGS_Run3_Set3` | 1,481 | 208,690,840,714 | `2026-07-15T01:42:10+00:00` | yes | **no** |
| `ont-run3-set4` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260713_ONT_BGS_Run3_Set4/` | `/mnt/seqdata/pca100/20260713_ONT_BGS_Run3_Set4` | 1,121 | 186,947,827,025 | `2026-07-15T01:43:40+00:00` | yes | **no** |
| `ont-run3-set5` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260713_ONT_BGS_Run3_Set5/` | `/mnt/seqdata/pca100/20260713_ONT_BGS_Run3_Set5` | 1,327 | 209,311,598,871 | `2026-07-15T01:45:00+00:00` | yes | **no** |
| `ont-run3-set6` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260713_ONT_BGS_Run3_Set6/` | `/mnt/seqdata/pca100/20260713_ONT_BGS_Run3_Set6` | 1,152 | 193,818,895,857 | `2026-07-15T01:46:21+00:00` | yes | **no** |
| `ont-run3-set7` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260713_ONT_BGS_Run3_Set7/` | `/mnt/seqdata/pca100/20260713_ONT_BGS_Run3_Set7` | 1,206 | 199,490,487,871 | `2026-07-15T01:47:41+00:00` | yes | **no** |
| `ont-run3-set8` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260713_ONT_BGS_Run3_Set8/` | `/mnt/seqdata/pca100/20260713_ONT_BGS_Run3_Set8` | 1,279 | 184,971,359,863 | `2026-07-15T01:48:59+00:00` | yes | **no** |
| `ont-run4-set1` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260723_ONT_BGS_Run4_Set1/` | `/mnt/seqdata/pca100/20260723_ONT_BGS_Run4_Set1` | 1,538 | 219,838,257,835 | `2026-07-25T02:11:09+00:00` | yes | **no** |
| `ont-run4-set2` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260723_ONT_BGS_Run4_Set2/` | `/mnt/seqdata/pca100/20260723_ONT_BGS_Run4_Set2` | 1,170 | 219,200,233,150 | `2026-07-25T02:12:56+00:00` | yes | **no** |
| `ont-run4-set3` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260723_ONT_BGS_Run4_Set3/` | `/mnt/seqdata/pca100/20260723_ONT_BGS_Run4_Set3` | 1,737 | 215,400,450,630 | `2026-07-25T02:40:29+00:00` | yes | **no** |
| `ont-run4-set4` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260723_ONT_BGS_Run4_Set4/` | `/mnt/seqdata/pca100/20260723_ONT_BGS_Run4_Set4` | 1,639 | 229,038,115,232 | `2026-07-25T02:17:47+00:00` | yes | **no** |
| `ont-run4-set5` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260723_ONT_BGS_Run4_Set5/` | `/mnt/seqdata/pca100/20260723_ONT_BGS_Run4_Set5` | 1,736 | 212,589,476,807 | `2026-07-25T02:19:45+00:00` | yes | **no** |
| `ont-run4-set6` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260723_ONT_BGS_Run4_Set6/` | `/mnt/seqdata/pca100/20260723_ONT_BGS_Run4_Set6` | 1,432 | 206,035,580,687 | `2026-07-25T02:21:32+00:00` | yes | **no** |
| `ont-run4-set7` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260723_ONT_BGS_Run4_Set7/` | `/mnt/seqdata/pca100/20260723_ONT_BGS_Run4_Set7` | 1,479 | 221,368,551,892 | `2026-07-25T02:23:21+00:00` | yes | **no** |
| `ont-run4-set8` | ONT | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260723_ONT_BGS_Run4_Set8/` | `/mnt/seqdata/pca100/20260723_ONT_BGS_Run4_Set8` | 1,282 | 175,033,330,606 | `2026-07-25T02:25:11+00:00` | yes | **no** |

## Mount projections

These are projections expected by the manifests; no mount was created or changed.

| S3 mount root | FSx projection |
|---|---|
| `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260624_LH01106_0012_A23WW3CLT4/` | `/fsx/run_dir_mounts/20260624_LH01106_0012_A23WW3CLT4` |
| `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260629_LH01106_0014_B23WV5HLT4/` | `/fsx/run_dir_mounts/20260629_LH01106_0014_B23WV5HLT4` |
| `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260624_LH01106_0013_B23M753LT3/` | `/fsx/run_dir_mounts/20260624_LH01106_0013_B23M753LT3` |
| `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260701_LH01106_0015_B23M5J7LT3/` | `/fsx/run_dir_mounts/20260701_LH01106_0015_B23M5J7LT3` |
| `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260722_LH01106_0016_A23WW3YLT4/` | `/fsx/run_dir_mounts/20260722_LH01106_0016_A23WW3YLT4` |
| `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2025/` | `/fsx/run_dir_mounts/pca100-2025` |
| `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/` | `/fsx/run_dir_mounts/pca100-2026` |

## Crosswalk and input selection contract

The reviewed crosswalk is `docs/jem/bjuice_validation/sample_crosswalk.tsv`. It preserves
the canonical biological sample, modality aliases, source/internal IDs, logical run, ONT
Set/chip/position/barcode, pairing state, and blockers. One-sided rows stay in the crosswalk
but never enter a hybrid manifest.

Technical replicates are distinct AUs, libraries, and sequencing inputs. They still point to
one shared canonical biological `SAMPLEID`. IDs are local, deterministic, and bundle-qualified.
Every EUID column is blank; source strings that happen to begin with `M-` are retained only as
source identifiers or comments and are never represented as Meridian/TapDB EUIDs.

Explicit source-name translations are limited to the reviewed cases encoded in the generator:

- Run 2 CASE1 aliases map to BCL sample IDs `M-BCN-605`, `M-BCN-A613`, and `M-BCN-A5AE`.
- Run 2 BUCCAL7/8/9 map to `WRD6-20-26`, `BLD6-20-26`, and `CLD6-20-26`.
- Run 3 CASE1 aliases map to the same three `M-BCN-*` BCL IDs.
- Run 3 workbook GIAB aliases `HG002-c`, `HG003-c`, and `HG004-c` map to preserved BCL
  basenames `HG002-b`, `HG003-b`, and `HG004-b`.
- Run 4 `ILMN-CASE17-P` and `ILMN-CASE18-P` map to preserved BCL basenames
  `ILMN-CASE17` and `ILMN-CASE18`.

For ILMN, every selected file is nonempty, every available selected lane is included, and the
R1 and R2 lane sets are exactly equal. `SUBSAMPLE_PCT` is blank, so coverage is full.

For ONT, a Set contains three flowcells. Barcode alone is insufficient because a barcode
directory contains outputs from multiple flowcells. The exact selector is:

1. workbook logical run and decoded Set;
2. 24-chip plate position (`1A` through `3H`);
3. the flowcell, protocol-run prefix, and acquisition-run prefix from that position's
   `final_summary_*.txt`;
4. the decoded `fastq_pass/barcodeNN` directory; and
5. filename chunk hour.

Every decoded ONT row has exactly one nonempty chunk for each hour `0` through `23`.
The manifest supplies the exact flowcell-qualified FASTQ family and the AU sets
`ONT_FQ_START_HOUR=0`, exclusive `ONT_FQ_END_HOUR=24`, with blank
`ONT_SUBSAMPLE_PCT`.

## Exclusions

- The separate Bjuice-preval cohort, its `20260618_LH01106_0011_A23MFMCLT3` ILMN run,
  and its 15 `20260615` ONT directories are outside this inventory.
- All 58 one-sided workbook rows remain visible but are excluded from hybrid AUs.
- Workbook NTC rows and BCL samples `NTC` and `Undetermined` are excluded.
- Run 4 date-labelled BCL controls `20260717-1` through `20260717-4` and
  `20260722-1` through `20260722-4` are not workbook-mapped and are excluded.
- Across the 32 ONT roots, 32,468 passing candidate FASTQs were observed. Exactly 4,735
  match reviewed position/flowcell/barcode tuples; 27,733 cross-flowcell or NTC/nonmapped
  passing FASTQs are excluded.
- `fastq_fail` (23,932 objects) and `unclassified` (3,552 objects) are excluded.
- ONT QC directories, hidden dot-prefixes, and `*-migration-cleanup` prefixes are prohibited
  by the generator. None was selected.
- No fallback alias discovery, alternate root, prevalence input, or HG002-only overlay is used.

ILMN BCLConvert selection accounting is:

| Source | Candidate FASTQs | Selected workbook FASTQs | Unselected sample IDs |
|---|---:|---:|---|
| `ilmn-run1a` | 800 | 768 | `NTC`, `Undetermined` |
| `ilmn-run1b` | 800 | 768 | `NTC`, `Undetermined` |
| `ilmn-run2` | 352 | 320 | `NTC`, `Undetermined` |
| `ilmn-run3` | 352 | 320 | `NTC`, `Undetermined` |
| `ilmn-run4` | 800 | 640 | eight date-labelled controls, `NTC`, `Undetermined` |

## Configuration capsules

The repository root is `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`. Each listed
file is required; the six TSVs are the DayOA six-manifest set.

### Bundle 1a

- `docs/jem/bjuice_validation/configs/bundle1a/specimens.tsv`
- `docs/jem/bjuice_validation/configs/bundle1a/samples.tsv`
- `docs/jem/bjuice_validation/configs/bundle1a/libraries.tsv`
- `docs/jem/bjuice_validation/configs/bundle1a/sequencing_inputs.tsv`
- `docs/jem/bjuice_validation/configs/bundle1a/analysis_units.tsv`
- `docs/jem/bjuice_validation/configs/bundle1a/analysis_unit_inputs.tsv`
- `docs/jem/bjuice_validation/configs/bundle1a/bjuice_validation_bundle1a_hiomr2.yaml`
- `docs/jem/bjuice_validation/configs/bundle1a/generation_receipt.json`

### Bundle 1b

- `docs/jem/bjuice_validation/configs/bundle1b/specimens.tsv`
- `docs/jem/bjuice_validation/configs/bundle1b/samples.tsv`
- `docs/jem/bjuice_validation/configs/bundle1b/libraries.tsv`
- `docs/jem/bjuice_validation/configs/bundle1b/sequencing_inputs.tsv`
- `docs/jem/bjuice_validation/configs/bundle1b/analysis_units.tsv`
- `docs/jem/bjuice_validation/configs/bundle1b/analysis_unit_inputs.tsv`
- `docs/jem/bjuice_validation/configs/bundle1b/bjuice_validation_bundle1b_hiomr2.yaml`
- `docs/jem/bjuice_validation/configs/bundle1b/generation_receipt.json`

### Bundle 2

- `docs/jem/bjuice_validation/configs/bundle2/specimens.tsv`
- `docs/jem/bjuice_validation/configs/bundle2/samples.tsv`
- `docs/jem/bjuice_validation/configs/bundle2/libraries.tsv`
- `docs/jem/bjuice_validation/configs/bundle2/sequencing_inputs.tsv`
- `docs/jem/bjuice_validation/configs/bundle2/analysis_units.tsv`
- `docs/jem/bjuice_validation/configs/bundle2/analysis_unit_inputs.tsv`
- `docs/jem/bjuice_validation/configs/bundle2/bjuice_validation_bundle2_hiomr2.yaml`
- `docs/jem/bjuice_validation/configs/bundle2/generation_receipt.json`

### Bundle 3

- `docs/jem/bjuice_validation/configs/bundle3/specimens.tsv`
- `docs/jem/bjuice_validation/configs/bundle3/samples.tsv`
- `docs/jem/bjuice_validation/configs/bundle3/libraries.tsv`
- `docs/jem/bjuice_validation/configs/bundle3/sequencing_inputs.tsv`
- `docs/jem/bjuice_validation/configs/bundle3/analysis_units.tsv`
- `docs/jem/bjuice_validation/configs/bundle3/analysis_unit_inputs.tsv`
- `docs/jem/bjuice_validation/configs/bundle3/bjuice_validation_bundle3_hiomr2.yaml`
- `docs/jem/bjuice_validation/configs/bundle3/generation_receipt.json`

### Bundle 4

- `docs/jem/bjuice_validation/configs/bundle4/specimens.tsv`
- `docs/jem/bjuice_validation/configs/bundle4/samples.tsv`
- `docs/jem/bjuice_validation/configs/bundle4/libraries.tsv`
- `docs/jem/bjuice_validation/configs/bundle4/sequencing_inputs.tsv`
- `docs/jem/bjuice_validation/configs/bundle4/analysis_units.tsv`
- `docs/jem/bjuice_validation/configs/bundle4/analysis_unit_inputs.tsv`
- `docs/jem/bjuice_validation/configs/bundle4/bjuice_validation_bundle4_hiomr2.yaml`
- `docs/jem/bjuice_validation/configs/bundle4/generation_receipt.json`

## Runtime contract and validation boundary

Every bundle YAML sets:

- `ont_fastq_hour_window_mode: per_analysis_unit`;
- raw ONT FASTQ mode for every included biological sample;
- `sentdhiomr2.hg38_sentdhiomr2_chrms: "1-25"`;
- slim consensus enabled;
- NICU research and Jasmine disabled; and
- the verified HIOMR2 MultiQC lane contract.

GIAB HG001-HG004 samples use the verified SNV truth roots under
`/fsx/references/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/`.
Only HG002 receives the separately verified v5.0q SV Truvari VCF/TBI/BED mapping. Bundle 4
contains no verified GIAB sample, so its Truvari truthset map is empty. No truth path is
invented for another sample.

The five six-manifest sets and runtime YAMLs pass the manifest contract and configuration
schema read directly from annotated DayOA tag `15.0.22`, peeled commit
`e838b3aedd4a38078f916e4ef3c6fe22d3d8414f`. That tag contains both exact targets:

- `produce_sentdhiomr2_slim_kitchensink_mega`
- `produce_sentdhiomr2_inflection_analytical_package`

The Gate 0 DYEC catalog targeted DayOA `15.0.23`; a concurrent unrelated worktree edit later
advanced the uncommitted catalog target to `15.0.24`. In both observations the direct
`inflection-bjuice-product-v0.9` entry retained historical `validated_version: 15.0.3`, used
the HG002-specific overlay, and described only a global ONT slice. Therefore the current
catalog route is validation-pending and is not substituted for this reviewed DayOA `15.0.22`
per-AU configuration. The concurrent catalog/test edits were not changed by this work.

## Future dry-run sequence — documented only, not executed

Do not perform even this dry run until all 37 canonical `OOW.done` records are restored or
the owning OWY operator formally supplies an alternate publication receipt, the exact
15.0.22-versus-current-catalog version route is reviewed, and every declared mount exists.
No mount-creation command is included here.

For one future bundle, set the variables explicitly and use an interactive Ubuntu login shell
inside one persistent tmux pane. `BUNDLE_SOURCE` must be the reviewed capsule directory on
the headnode; it is not an alternate source-data root.

```bash
export BUNDLE=bundle1a
export ANALYSIS_ID=<future-approved-analysis-id>
export EXECUTING_ENTITY=<future-approved-executing-entity>
export BUNDLE_SOURCE=<absolute-reviewed-capsule-directory-on-headnode>
export SESSION=bjuice-validation-${BUNDLE}-dryrun

tmux new-session -d -s "$SESSION" 'bash -il'
tmux send-keys -t "$SESSION" "dyec analysis lock acquire --analysis-root /fsx/analysis_results/${EXECUTING_ENTITY}/${ANALYSIS_ID} --operation write --intent 'Bjuice validation dry run'" Enter
tmux send-keys -t "$SESSION" "day-clone -t 15.0.22 -d ${ANALYSIS_ID} --executing-entity ${EXECUTING_ENTITY}" Enter
tmux send-keys -t "$SESSION" "cd /fsx/analysis_results/${EXECUTING_ENTITY}/${ANALYSIS_ID}/daylily-omics-analysis" Enter
tmux send-keys -t "$SESSION" "cp ${BUNDLE_SOURCE}/specimens.tsv ${BUNDLE_SOURCE}/samples.tsv ${BUNDLE_SOURCE}/libraries.tsv ${BUNDLE_SOURCE}/sequencing_inputs.tsv ${BUNDLE_SOURCE}/analysis_units.tsv ${BUNDLE_SOURCE}/analysis_unit_inputs.tsv config/" Enter
tmux send-keys -t "$SESSION" "cp ${BUNDLE_SOURCE}/bjuice_validation_${BUNDLE}_hiomr2.yaml config/" Enter
tmux send-keys -t "$SESSION" 'source dyoainit' Enter
tmux send-keys -t "$SESSION" 'dy-a slurm hg38' Enter
tmux send-keys -t "$SESSION" "DAY_CONTAINERIZED=true dy-r produce_sentdhiomr2_slim_kitchensink_mega produce_sentdhiomr2_inflection_analytical_package --configfile config/bjuice_validation_${BUNDLE}_hiomr2.yaml --config 'genome_build=hg38' 'aligners=[\"sentmm2ont\"]' 'dedupers=[\"na\"]' 'snv_callers=[\"sentdhiomr2\"]' 'sentdhiomr2={\"hg38_sentdhiomr2_chrms\":\"1-25\"}' 'sv_callers=[]' 'htd_callers=[\"smn12\"]' 'hiomr2_inflection_package_mode=analytical' \"seqone_delivery_batch_id=${ANALYSIS_ID}\" -j 333 -T 0 -p --rerun-triggers mtime -n" Enter
```

After the dry controller is terminal, capture its attributable exit code and zero-submission
evidence, then release the lock. A live continuation would require a new explicit human
authorization and the same root, checkout, inputs, config hash, and controller context with
only `-n` removed. It is not authorized by this document or by the work that produced it.

## Reproduction and tests

The fail-closed generator is `daylily_ec/bjuice_validation_config.py`. It has separate
`crosswalk`, read-only `inventory`, and local `generate` modes. Generation requires an empty
output directory and verifies the source-spec and crosswalk hashes embedded in the inventory.
It rejects ambiguous aliases, duplicate barcodes, missing or unequal ILMN mates, empty inputs,
unexpected ONT filenames, and sources outside the explicit canonical roots.

The focused acceptance test is:

```bash
source ./activate
pytest -q tests/test_bjuice_validation_config.py
```

No test calls live AWS; S3 behavior in unit tests uses a mocked client. The checked-in source
inventory is the read-only live evidence snapshot.

## Evidence hashes

| Artifact | SHA-256 |
|---|---|
| Lab workbook `/Users/jmajor/Downloads/Betelgeuse Validation - LAB.xlsx` | `face0fc30a241b87ee02223c3f8117a831a6c16b17233b395ae8a15f4ba8bdd7` |
| `docs/jem/bjuice_validation/source_spec.json` | `a1ac9dbd0131e00d1d301c3701b0f94aa36380b51b2f5727b9b142b9690c4de9` |
| `docs/jem/bjuice_validation/sample_crosswalk.tsv` | `860b0d1e82824d46b669be78b3890b8c2a92b2e64488cc023ba886998e4077c9` |
| `docs/jem/bjuice_validation/source_inventory.json` | `3943667953917ac4d9292d5f18f8377b574a8ec125f641a6e9dcb06ebff07127` |

Each `generation_receipt.json` contains the exact six manifest hashes, runtime YAML hash,
inventory hash, selected source topology, and every exact S3 and projected FSx FASTQ path for
that bundle. Bundle 1a and 1b receipts have identical ONT path sets and disjoint ILMN roots.
