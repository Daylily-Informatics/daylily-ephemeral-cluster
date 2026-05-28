# Inflection HG003 Segdup Failure Investigation

Created: 2026-05-27T23:27Z

## Scope

Investigate `produce_sentdhiomr_segdup` failures in the active DayOA `2.0.11`
HG003 inflection run on `goodole3`.

Run directory:

`/fsx/analysis_results/ubuntu/inflection_20260527-2.0.11/daylily-omics-analysis`

Controller log:

`.snakemake/log/2026-05-27T195632.640964.snakemake.log`

## Current Finding

`sentdhiomr_call_segdup_gene` has two distinct failure modes:

1. `CFH`, `CYP2D6`, `GBA`, `HBA`, and `PMS2` fail in both samples with:

   `ValueError: too many values to unpack (expected 2)`

   Traceback path:

   `/fsx/resources/environments/conda/ubuntu/ip-10-0-0-144/eee36a29bf201e1d63af8b7da1cc7790_/lib/python3.10/site-packages/genecaller/bam_process.py`

   Relevant code:

   - `liftover()` line 538: `extract = extract.replace(",", " ")`
   - then `clip_to_region()` line 543 receives that string
   - `clip_to_region()` line 402 splits only on comma and line 403 calls `pysam.parse_region(region=region)`

   For multi-interval genes, comma-separated regions from `genes.yaml` are converted
   into one whitespace-separated string with multiple `chr:start-end` fragments.
   `pysam.parse_region()` then receives a malformed region string containing more
   than one colon.

2. `STRC` fails in both samples with:

   `whatshap polyphase ... returned non-zero exit status 1`

   Then `genecaller/gene.py` raises:

   `RuntimeError: One of the variant calling tasks failed.`

## Per-Gene Outcome

| Sample | OK genes | Failed genes |
|---|---|---|
| `15x7x` | `CYP11B1`, `NCF1`, `SMN1` | `CFH`, `CYP2D6`, `GBA`, `HBA`, `PMS2`, `STRC` |
| `20x10x` | `CYP11B1`, `NCF1`, `SMN1` | `CFH`, `CYP2D6`, `GBA`, `HBA`, `PMS2`, `STRC` |

## Input Validation

The required inputs exist for both branches and passed `samtools quickcheck`
where applicable:

| Sample | Long-read CRAM | SR merged BAM |
|---|---:|---:|
| `15x7x` | `4,945,485,410` bytes, quickcheck rc `0` | `39,149,845,178` bytes, quickcheck rc `0` |
| `20x10x` | `7,074,915,126` bytes, quickcheck rc `0` | `51,035,667,216` bytes, quickcheck rc `0` |

Reference/model paths checked present:

- `/fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.02/bundles/DNAscopeONT2.2.bundle/DNAscopeONT2.2.bundle`
- `/fsx/references/genomic_data/organism_references/H_sapiens/hg38_broad/Homo_sapiens_assembly38.fasta`
- `/fsx/references/genomic_data/organism_references/H_sapiens/hg38_broad/Homo_sapiens_assembly38.fasta.fai`

## Environment Evidence

DayOA checkout:

- tag: `2.0.11`
- head: `d5b5faefc33efbb0edb6ec58ce56cbcd5ae4a19e`

Segdup environment:

`/fsx/resources/environments/conda/ubuntu/ip-10-0-0-144/eee36a29bf201e1d63af8b7da1cc7790_`

Package evidence:

- `workflow/envs/segdup_v0.1.yaml` requests `git+https://github.com/Sentieon/segdup-caller.git@v0.4.0`
- installed `direct_url.json` requested revision: `v0.4.0`
- installed commit: `9cc8dc1d3e4ad76bcf181ad8a2139d26a63d72ee`
- installed package metadata version: `segdup-caller=0.3.0`
- `whatshap=2.8`
- `pysam=0.22.1`

## Rule Evidence

Rule source:

`workflow/rules/sent_hybrid_ilmn_ont_modular.refactored.smk`

The current rule calls:

`segdup-caller --short <sr_merged.bam> --long <ont.cram> --lr_model <DNAscopeONT2.2.bundle> --sr_model <SentieonIlluminaWGS2.2.bundle> --reference <hg38_broad fasta> --genes <gene> --threads 48 --workers 1`

The rule also contains a runtime fallback:

`pip install git+https://github.com/Sentieon/segdup-caller.git`

This fallback is unpinned and should not be kept as-is in DayOA; the conda env
already specifies the package revision explicitly.

## Interpretation

This is not caused by missing staged inputs, missing reference files, or corrupt
BAM/CRAM inputs.

The main blocker is an upstream `segdup-caller`/`genecaller` bug for multi-interval
liftover genes. `STRC` has a separate upstream tool failure in `whatshap polyphase`.

DayOA can make the failure cleaner by removing the unpinned runtime install fallback.
Producing complete segdup VCFs will require either a patched/pinned `segdup-caller`
or a targeted local patch to the `genecaller` environment before rerunning the
segdup target.
