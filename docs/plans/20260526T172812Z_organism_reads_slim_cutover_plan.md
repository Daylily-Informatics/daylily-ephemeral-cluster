# Organism Reads Slim Cutover Plan

Created: 20260526T172812Z

## Scope

Build a slim control-data read prefix for command-catalog and small demo fixtures before relocating the large control-data corpus.

Slim destination prefix:
`s3://lsmc-dayoa-control-data-usw2/genomic_data/organism_reads_slim/{fastq,cram,bam}/`

Manifest:
`/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/plans/20260526T172812Z_organism_reads_slim_copy_manifest.tsv`

## Selected Objects

- Unique source objects including CRAM/BAM sidecars: 26
- Total copy size: 101475761473 bytes (101.48 GB, 94.51 GiB)
- bam: 8 objects, 62605818447 bytes (62.61 GB)
- cram: 12 objects, 24528938198 bytes (24.53 GB)
- fastq: 6 objects, 14341004828 bytes (14.34 GB)

## Destructive Gate

Do not move/delete remaining control-data or organism_reads objects until the exact source/destination prefixes and delete semantics receive second approval.
Proposed destructive move after slim validation:
- from `s3://lsmc-dayoa-control-data-usw2/genomic_data/organism_reads/`
- to `s3://lsmc-ssf-sequencing-data/control-data/genomic_data/organism_reads/`
- from `s3://lsmc-dayoa-control-data-usw2/cram_data/`
- to `s3://lsmc-ssf-sequencing-data/control-data/cram_data/`

## Missing Objects

- none
