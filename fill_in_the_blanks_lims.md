# Fill-In-The-Blanks LIMS Handoff For Bloom

Created: 2026-05-20  
Scope: Altair Illumina runs currently staged/mounted for `dra-enabled` and the associated BCLConvert outputs.

This document is for an agent that can create Bloom artifacts and relationships. It is intentionally explicit about what is known from the run directories and what should be assigned inside Bloom.

## Goal

Create a traceable Bloom chain from source gDNA through library preparation, index assignment, pooling, sequencing run, flowcell, instrument, and FASTQ data.

Target chain:

```text
Subject/Patient
  -> source gDNA tube
  -> lib prep source plate well
  -> library prep plate well
  -> indexed library well
  -> pooled library tube
  -> flowcell/load
  -> sequencing run
  -> instrument
  -> FASTQ data files
```

The key principle is to keep the sample/index/FASTQ chain lossless. Use the SampleSheet `Sample_ID`, `Index`, and `Index2`, plus the run directory FASTQ paths, as the primary evidence.

## Bloom Object Types To Create Or Reuse

Use Bloom's exact type names if they differ; these are semantic names.

| Bloom object | Create one per | Known seed value | Notes |
|---|---|---|---|
| `Subject` or `Patient` | SampleSheet `Sample_ID` | `Sample_ID` exactly, for example `HG003-a` | Do not silently merge `HG003-a`, `HG003-b`, and `HG003-c`. If Bloom supports donor grouping, add optional parent donor `HG003`. |
| `Specimen` | source gDNA material per sample | `Sample_ID` | For HG001-HG007, mark as GIAB/Coriell control gDNA if supported. For `NTC`, create a negative-control specimen, not a patient. |
| `Tube` | source gDNA tube, pooled library tube | assign Bloom EUID | Source tube IDs are not present in the run dirs; leave original barcode blank unless recovered elsewhere. |
| `Plate` | source/lib prep/index plate | assign Bloom EUID | Plate barcodes and physical well map are not present in the run dirs. Use a deterministic placeholder and update later. |
| `PlateWell` | sample-index well association | run + `Sample_ID` | If no physical well is available, use SampleSheet row number as the provisional well ordinal. |
| `IndexReagent` or `IndexPlateWell` | each dual index pair | `Index` + `Index2` | Create as a derived index plate/well if that is the Bloom model. |
| `Library` | indexed library per `Sample_ID` per run | run EUID + `Sample_ID` | One library per sample row, including the NTC as a control library if Bloom supports controls. |
| `PoolTube` | sequencing pool per run | run EUID + `pool` | One pooled library tube per run/flowcell side is sufficient for these runs. |
| `Flowcell` | flowcell reagent | `Flowcell` from `RunInfo.xml` | Assign a Bloom reagent EUID and store the vendor flowcell ID. |
| `SequencingRun` | run directory | `RunInfo Run Id` and SampleSheet `RunName` | Assign a Bloom EUID to the run. Store run directory, S3 URI, instrument, side, read cycles. |
| `Instrument` | sequencer | `LH01106` | Instrument type is `NovaSeqXPlus`. |
| `DataFile` | FASTQ or run metadata file | S3 URI or FSx path | Link FASTQs to run, library/sample, index pair, and read/lane. |

## Relationship Pattern

Create relationships in this order.

1. `Subject` has `Specimen`.
2. `Specimen` is contained in `source gDNA tube`.
3. `source gDNA tube` is aliquoted or transferred to `source/lib prep plate well`.
4. `source/lib prep plate well` feeds `library prep plate well`.
5. `library prep plate well` receives `IndexReagent` or `IndexPlateWell`.
6. `library prep plate well` creates `Library`.
7. `Library` is contained in or contributes to `PoolTube`.
8. `PoolTube` is loaded on `Flowcell`.
9. `Flowcell` is used by `SequencingRun`.
10. `SequencingRun` is run on `Instrument`.
11. `SequencingRun` produces `DataFile` artifacts.
12. Each sample FASTQ `DataFile` links back to `Library`, `Sample_ID`, `Index`/`Index2`, lane, read, run, and flowcell.

## EUID Seed Suggestions

These are not required EUIDs. They are stable names to use as idempotency keys or aliases while Bloom assigns real EUIDs.

| Artifact | Suggested alias/idempotency key |
|---|---|
| Run | `run:{RunInfo.Id}` |
| Flowcell | `flowcell:{Flowcell}` |
| Instrument | `instrument:LH01106` |
| Pooled library tube | `pool:{RunInfo.Id}:pool1` |
| Lib prep plate | `libprep_plate:{RunInfo.Id}` |
| Source plate | `source_plate:{RunInfo.Id}` |
| Derived index plate | `index_plate:{RunInfo.Id}` |
| Library well | `library:{RunInfo.Id}:{Sample_ID}` |
| Index reagent/well | `index:{RunInfo.Id}:{Sample_ID}:{Index}+{Index2}` |
| FASTQ | `fastq:{RunInfo.Id}:{Sample_ID}:L{lane}:R{read}` |

## Run-Level Known Values

| Run directory | SampleSheet RunName | RunInfo Flowcell | Instrument | Instrument type | Run number | Side | Date | Reads | S3 root | FSx mount |
|---|---|---|---|---|---:|---|---|---|---|---|
| `20260512_LH01106_0006_A23K3H2LT4` | `20260512_ILMN_Altair_Run_1` | `23K3H2LT4` | `LH01106` | `NovaSeqXPlus` | 6 | A | `2026-05-12T23:40:04Z` | `Y151;I10;I10;Y151` | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260512_LH01106_0006_A23K3H2LT4/` | `/fsx/run_dir_mounts/20260512_LH01106_0006_A23K3H2LT4/` |
| `20260512_LH01106_0007_B23K5JKLT4` | `20260512_ILMN_Altair_Run_2` | `23K5JKLT4` | `LH01106` | `NovaSeqXPlus` | 7 | B | `2026-05-12T23:55:25Z` | `Y151;I10;I10;Y151` | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260512_LH01106_0007_B23K5JKLT4/` | `/fsx/run_dir_mounts/20260512_LH01106_0007_B23K5JKLT4/` |
| `20260514_LH01106_0009_B23TVLGLT4` | `20260514_ILMN_Altair_Run_3` | `23TVLGLT4` | `LH01106` | `NovaSeqXPlus` | 9 | B | `2026-05-15T01:33:57Z` | `Y151;I10;I10;Y151` | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0009_B23TVLGLT4/` | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/` |

Common run metadata:

- `IndexOrientation`: `Forward`
- `SoftwareVersion`: `4.3.16`
- Sample rows per run: 41 total, 40 non-NTC sample rows and 1 NTC row.
- Read structure from `RunInfo.xml`: R1 151 cycles, I1 10 cycles, I2 10 cycles reverse-complemented by instrument metadata, R2 151 cycles.

## Source Files And Data Paths

Run metadata files:

```text
{run_root}/SampleSheet.csv
{run_root}/RunInfo.xml
{run_root}/RunParameters.xml
{run_root}/Analysis/1/Data/BCLConvert/fastq/
```

FASTQ file pattern:

```text
{run_root}/Analysis/1/Data/BCLConvert/fastq/{Sample_ID}_S{sample_number}_L{lane}_R{read}_001.fastq.gz
```

For mounted FSx paths:

```text
/fsx/run_dir_mounts/{RunInfo.Id}/Analysis/1/Data/BCLConvert/fastq/{Sample_ID}_S{sample_number}_L{lane}_R{read}_001.fastq.gz
```

For S3 paths:

```text
s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/{RunInfo.Id}/Analysis/1/Data/BCLConvert/fastq/{Sample_ID}_S{sample_number}_L{lane}_R{read}_001.fastq.gz
```

For Run 1 and Run 3, every non-NTC sample has eight lane pairs, L001-L008, R1/R2. Existing generated manifests with full comma-separated FASTQ lists:

```text
tmp/altair-reanalysis/re-ana-20260512_LH01106_0006_A23K3H2LT4/analysis_samples.tsv
tmp/altair-reanalysis/re-ana-20260514_LH01106_0009_B23TVLGLT4/analysis_samples.tsv
tmp/altair-reanalysis/re-ana-20260514_LH01106_0009_B23TVLGLT4-HG003-hybrid-ilmn-ont/analysis_samples.tsv
```

## Run 2 Caveat

Run 2, `20260512_LH01106_0007_B23K5JKLT4`, should be registered as a run/flowcell/pool attempt, but the named-sample FASTQs should not be treated as valid sample data without a human decision.

Observed evidence from BCLConvert:

- Named-sample FASTQs are effectively empty gzip stubs.
- `Undetermined` FASTQs contain the reads.
- `Demultiplex_Stats.csv` reports only 8 assigned non-Undetermined reads.
- Top unknown barcode rows have zero exact overlap with the 41 expected SampleSheet index pairs.
- For LIMS, create the planned sample/index/library/run chain if desired, but mark the run data outcome as failed or unexpected-index/undetermined, and register the `Undetermined` FASTQs as run-level data, not sample-level data.

## How To Register FASTQs

For each non-NTC sample row in a successful run:

1. Create 16 FASTQ `DataFile` records per sample: 8 lanes x 2 reads.
2. Link each FASTQ to:
   - `SequencingRun`
   - `Flowcell`
   - `Instrument`
   - `Library`
   - `Subject`/`Patient`
   - `IndexReagent` or index well
   - lane: `L001` through `L008`
   - read: `R1` or `R2`
3. Store both S3 URI and mounted FSx URI if Bloom supports alternate locations.
4. Use SampleSheet row number as `S{sample_number}` in the filename pattern.

For the NTC:

- Create a control library and control data files if Bloom supports negative controls.
- Do not create a patient.
- Link it to a `NegativeControl` or `NoTemplateControl` artifact.

## Plate And Well Mapping

Physical source plate, library prep plate, and index plate well coordinates are not available in the run directories. The other agent should either retrieve true well coordinates from upstream LIMS records or create provisional wells from SampleSheet order.

Provisional mapping if no physical plate map exists:

```text
S1  -> A01
S2  -> B01
S3  -> C01
...
S8  -> H01
S9  -> A02
...
S41 -> A06
```

If Bloom requires 96-well positions, use this only as a placeholder and set `well_position_confidence=provisional_from_samplesheet_order`.

## Index Table For Run 1 And Run 2

Run 1 and Run 2 have the same SampleSheet sample/index table.

| S# | Sample_ID | Index/I7 | Index2/I5 | Subject seed | Artifact hint |
|---:|---|---|---|---|---|
| S1 | `HG001-a` | `ACTGAATGAG` | `CCATAACATT` | `HG001-a` | GIAB/Coriell gDNA |
| S2 | `HG001-b` | `CGCAGGCACG` | `AAAGCTGGTT` | `HG001-b` | GIAB/Coriell gDNA |
| S3 | `HG001-c` | `GTTCTGGCGG` | `GCACCACCCT` | `HG001-c` | GIAB/Coriell gDNA |
| S4 | `HG002-a` | `GCCGAGAATT` | `CAAGTCAGAG` | `HG002-a` | GIAB/Coriell gDNA |
| S5 | `HG002-b` | `ACTACCTCTT` | `ACTGCCCGTT` | `HG002-b` | GIAB/Coriell gDNA |
| S6 | `HG002-c` | `TGCGAACGGT` | `TCAATCAATA` | `HG002-c` | GIAB/Coriell gDNA |
| S7 | `HG003-a` | `AGCTTGCGGG` | `CTCGCGGGTG` | `HG003-a` | GIAB/Coriell gDNA |
| S8 | `HG003-b` | `AGACGATTGT` | `AAAGACGACG` | `HG003-b` | GIAB/Coriell gDNA |
| S9 | `HG003-c` | `AGGGCTCCTA` | `TCATCACGCT` | `HG003-c` | GIAB/Coriell gDNA |
| S10 | `HG004-a` | `GAAAGCACGG` | `ATCAACTAGT` | `HG004-a` | GIAB/Coriell gDNA |
| S11 | `HG004-b` | `CGGCAGACCT` | `AGACCTTGGT` | `HG004-b` | GIAB/Coriell gDNA |
| S12 | `HG004-c` | `TCGAGTGGAT` | `CGCGCCGTTG` | `HG004-c` | GIAB/Coriell gDNA |
| S13 | `HG005-a` | `ATAGACCTCG` | `GTACTGACAA` | `HG005-a` | GIAB/Coriell gDNA |
| S14 | `HG005-b` | `AGGAAGCCTC` | `TCCTAGGTCT` | `HG005-b` | GIAB/Coriell gDNA |
| S15 | `HG005-c` | `CCACGCCTGC` | `GTCCTCGATG` | `HG005-c` | GIAB/Coriell gDNA |
| S16 | `HG006-a` | `CTGTCATCGC` | `GAAAGCCGTC` | `HG006-a` | GIAB/Coriell gDNA |
| S17 | `HG006-b` | `CATGTGGTAT` | `GTACTCTTTG` | `HG006-b` | GIAB/Coriell gDNA |
| S18 | `HG006-c` | `TGTCTGTTCA` | `TGCCTTGGGA` | `HG006-c` | GIAB/Coriell gDNA |
| S19 | `HG007-a` | `CCTTCTTCTG` | `CAGACGCGAC` | `HG007-a` | GIAB/Coriell gDNA |
| S20 | `HG007-b` | `TTGCCTCAGT` | `CCCTAGGCGC` | `HG007-b` | GIAB/Coriell gDNA |
| S21 | `HG007-c` | `TCGCGGCGTG` | `GAAGTAATAT` | `HG007-c` | GIAB/Coriell gDNA |
| S22 | `BUCCAL1-a` | `CTGTACCACG` | `AGGCAAACGA` | `BUCCAL1-a` | sample gDNA |
| S23 | `BUCCAL1-b` | `CCAGTAAGGG` | `AGTAGGATAT` | `BUCCAL1-b` | sample gDNA |
| S24 | `BUCCAL2-a` | `GAAAGTAAGA` | `GCGACACATA` | `BUCCAL2-a` | sample gDNA |
| S25 | `BUCCAL2-b` | `AAACCTTGTA` | `GACTTCGTGT` | `BUCCAL2-b` | sample gDNA |
| S26 | `BUCCAL3-a` | `CACTAATTCT` | `TAGCAGCTTG` | `BUCCAL3-a` | sample gDNA |
| S27 | `BUCCAL3-b` | `TTACGACAAG` | `AAACCGGTTA` | `BUCCAL3-b` | sample gDNA |
| S28 | `BUCCAL4-a` | `GTCACTTCAC` | `GCAGCCAAGA` | `BUCCAL4-a` | sample gDNA |
| S29 | `BUCCAL5-a` | `ATGCTGCCAG` | `TTTGGAAGAA` | `BUCCAL5-a` | sample gDNA |
| S30 | `BUCCAL6-a` | `TGCAAAGTAA` | `GAACATAGAG` | `BUCCAL6-a` | sample gDNA |
| S31 | `BUCCAL7-a` | `CGACGCGCGG` | `GACCGCATCA` | `BUCCAL7-a` | sample gDNA |
| S32 | `BUCCAL8-a` | `ATGGTGTGGC` | `ATCTTTCCCG` | `BUCCAL8-a` | sample gDNA |
| S33 | `BUCCAL9-a` | `CTGAGATATG` | `ACAATACTGA` | `BUCCAL9-a` | sample gDNA |
| S34 | `NA05115-a` | `TCATCATGTC` | `GTGCAACCGT` | `NA05115-a` | sample gDNA |
| S35 | `NA09216-a` | `TCACACGTTC` | `CAACATATAC` | `NA09216-a` | sample gDNA |
| S36 | `NA07439-a` | `AGCTCCGCTA` | `AACGCAACCT` | `NA07439-a` | sample gDNA |
| S37 | `NA20241-a` | `ACTATTAATC` | `ACAACTTAAC` | `NA20241-a` | sample gDNA |
| S38 | `NA05212-a` | `GCCCTGGAAG` | `TAGGCCCGCT` | `NA05212-a` | sample gDNA |
| S39 | `NA15849-a` | `CGCTACGGAA` | `ATGGCACCGT` | `NA15849-a` | sample gDNA |
| S40 | `NA20208-a` | `ACGGCCATTA` | `ACCACATCAT` | `NA20208-a` | sample gDNA |
| S41 | `NTC` | `TCACAAACGT` | `GTCTACATTG` | `NTC` | negative control |

## Index Table For Run 3

| S# | Sample_ID | Index/I7 | Index2/I5 | Subject seed | Artifact hint |
|---:|---|---|---|---|---|
| S1 | `HG001-a` | `GAGTAATATA` | `CCGACCGTGA` | `HG001-a` | GIAB/Coriell gDNA |
| S2 | `HG001-b` | `CGTCATGCTA` | `TAAAGTTCGT` | `HG001-b` | GIAB/Coriell gDNA |
| S3 | `HG001-c` | `TTGGCTAGGT` | `TATAGGAGTA` | `HG001-c` | GIAB/Coriell gDNA |
| S4 | `HG002-a` | `AGTCGACTCT` | `CGATCGTAAT` | `HG002-a` | GIAB/Coriell gDNA |
| S5 | `HG002-b` | `ACCAGCGCTC` | `CAAACTCGTC` | `HG002-b` | GIAB/Coriell gDNA |
| S6 | `HG002-c` | `AAAGAACATG` | `AATGGGAACT` | `HG002-c` | GIAB/Coriell gDNA |
| S7 | `HG003-a` | `TACACAGAGT` | `TACCGGGACA` | `HG003-a` | GIAB/Coriell gDNA |
| S8 | `HG003-b` | `CCGATAATAG` | `TGCTGATCAA` | `HG003-b` | GIAB/Coriell gDNA |
| S9 | `HG003-c` | `CCGCTTAAGG` | `GATCGTGATT` | `HG003-c` | GIAB/Coriell gDNA |
| S10 | `HG004-a` | `CCCTCCCTGC` | `ACTCCGACAG` | `HG004-a` | GIAB/Coriell gDNA |
| S11 | `HG004-b` | `CACCTGCCGA` | `TGACACTCAT` | `HG004-b` | GIAB/Coriell gDNA |
| S12 | `HG004-c` | `AGTAAATAAG` | `GCGTCCCAAG` | `HG004-c` | GIAB/Coriell gDNA |
| S13 | `HG005-a` | `TATGTAGAGA` | `TCTGAGTTAG` | `HG005-a` | GIAB/Coriell gDNA |
| S14 | `HG005-b` | `CTGACTCCAC` | `TGTTATACGC` | `HG005-b` | GIAB/Coriell gDNA |
| S15 | `HG005-c` | `GTACCGAATA` | `CCTTACTCTT` | `HG005-c` | GIAB/Coriell gDNA |
| S16 | `HG006-a` | `TTTACAAGAT` | `TGTATCGCCG` | `HG006-a` | GIAB/Coriell gDNA |
| S17 | `HG006-b` | `GTCCTCCTGC` | `GAGGCTGCTG` | `HG006-b` | GIAB/Coriell gDNA |
| S18 | `HG006-c` | `GAAACAGCGT` | `ACGTGTTGGA` | `HG006-c` | GIAB/Coriell gDNA |
| S19 | `HG007-a` | `AACAAATTCA` | `CCATTTCCCA` | `HG007-a` | GIAB/Coriell gDNA |
| S20 | `HG007-b` | `ATGGCTTCCG` | `CCGCACTCCT` | `HG007-b` | GIAB/Coriell gDNA |
| S21 | `HG007-c` | `CAACTATGCA` | `CCAGAGTGAC` | `HG007-c` | GIAB/Coriell gDNA |
| S22 | `BUCCAL1-a` | `ATTGCGAAGG` | `CTGAGGGCAC` | `BUCCAL1-a` | sample gDNA |
| S23 | `BUCCAL1-b` | `ATTGGTGCGG` | `ACGACCTAAT` | `BUCCAL1-b` | sample gDNA |
| S24 | `BUCCAL2-a` | `GCGAACGCAA` | `TTGTCAGAGA` | `BUCCAL2-a` | sample gDNA |
| S25 | `BUCCAL2-b` | `AGCGGGAGAT` | `ACAACAGCCT` | `BUCCAL2-b` | sample gDNA |
| S26 | `BUCCAL3-a` | `TAGCAAGGCT` | `GACCTACTGA` | `BUCCAL3-a` | sample gDNA |
| S27 | `BUCCAL3-b` | `GATAGAGAGG` | `CTCCGTCGAT` | `BUCCAL3-b` | sample gDNA |
| S28 | `BUCCAL4-a` | `ATAGGGAACA` | `TAAAGTATCG` | `BUCCAL4-a` | sample gDNA |
| S29 | `BUCCAL5-a` | `ACCACTTCTG` | `ATAAGGCCCA` | `BUCCAL5-a` | sample gDNA |
| S30 | `BUCCAL6-a` | `CAATAACGGC` | `TGCATGTGTA` | `BUCCAL6-a` | sample gDNA |
| S31 | `BUCCAL7-a` | `CGCGTGATCG` | `TAGGATCGGA` | `BUCCAL7-a` | sample gDNA |
| S32 | `BUCCAL8-a` | `TAGGCCATCG` | `ACGTTGGAGA` | `BUCCAL8-a` | sample gDNA |
| S33 | `BUCCAL9-a` | `TGCGCCGCAT` | `TGCGGTTCAG` | `BUCCAL9-a` | sample gDNA |
| S34 | `NA05115-a` | `ACTAGTCTCT` | `TTGTACATAG` | `NA05115-a` | sample gDNA |
| S35 | `NA09216-a` | `TTCGAGCCCA` | `CCAGAACTTC` | `NA09216-a` | sample gDNA |
| S36 | `NA07439-a` | `ACAGTTTATA` | `ATCGCACTTG` | `NA07439-a` | sample gDNA |
| S37 | `NA20241-a` | `CGCAGATAGC` | `CAGAGCAGTG` | `NA20241-a` | sample gDNA |
| S38 | `NA05212-a` | `CTAGACTTGT` | `TGGAGTCGTG` | `NA05212-a` | sample gDNA |
| S39 | `NA15849-a` | `CATAGGAATG` | `TATTGCAGTG` | `NA15849-a` | sample gDNA |
| S40 | `NA20208-a` | `AGGTCTACCA` | `TAACTCCCGG` | `NA20208-a` | sample gDNA |
| S41 | `NTC` | `AATTCGACCT` | `AATATGCAAC` | `NTC` | negative control |

## Fill-In-The-Blanks For The Bloom Agent

The following values are not available in the run folders and should be filled from Bloom, bench records, or assigned as new EUIDs.

| Missing value | Required action |
|---|---|
| True source gDNA tube barcode per sample | Find upstream sample receipt/extraction record or create new tube EUID with barcode blank/provisional. |
| True source plate barcode and well coordinates | Find upstream plate map, otherwise use provisional SampleSheet-order mapping. |
| True library prep plate barcode and well coordinates | Find prep record, otherwise assign new lib prep plate EUID and provisional wells. |
| Index plate barcode/name | Create a derived index plate or reagent set from `Index`/`Index2`; replace with true vendor plate if known. |
| Pool tube barcode | Assign per run, for example alias `pool:{RunInfo.Id}:pool1`. |
| Bloom run EUID | Assign per `RunInfo.Id`; preserve `RunName` as display name. |
| Bloom flowcell reagent EUID | Assign per `Flowcell`; store `Flowcell` as vendor serial/barcode. |
| Instrument EUID | Reuse or create `LH01106`; type `NovaSeqXPlus`. |
| Physical loading lane/lane group | These runs have BCLConvert lanes L001-L008; model as all eight lanes on the run/flowcell unless Bloom distinguishes lane groups. |
| Data file checksums and byte sizes | Can be filled by S3 HEAD or mount stat if Bloom requires them. |

## Minimal Create Order

1. Create or fetch instrument `LH01106`.
2. Create flowcell reagent from `RunInfo.Flowcell`.
3. Create sequencing run from `RunInfo.Id`, `RunName`, side, date, and read structure.
4. Link run to instrument and flowcell.
5. Create pool tube for the run and link pool tube to flowcell/run.
6. Create source and library prep plates for the run.
7. For each SampleSheet row:
   - create subject/patient or control
   - create source gDNA tube/specimen
   - create source plate well and library plate well
   - create or attach index reagent/well from `Index` + `Index2`
   - create indexed library
   - link indexed library to pooled library tube
8. For each FASTQ path:
   - create data file
   - link data file to run, library, sample, index pair, lane, read, flowcell, and instrument.

## Sanity Checks Before Writing To Bloom

- SampleSheet row count is 41.
- Non-NTC sample count is 40.
- For valid data runs, every non-NTC sample has 16 FASTQs: eight R1 and eight R2.
- R1/R2 filenames pair by lane and sample.
- Run 1 and Run 2 use the same planned index table, but Run 2 data should be flagged as demux/index failure.
- Run 3 has a different index table and should not reuse Run 1 index reagent aliases unless the reagent ontology intentionally models same sequence independently from plate position.
- Flowcell ID is the last token in the run directory name after the side letter, for example `A23K3H2LT4` contains side `A` plus flowcell `23K3H2LT4`; prefer `RunInfo.xml` for the canonical flowcell value.
