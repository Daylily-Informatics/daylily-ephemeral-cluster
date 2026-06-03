# DYEC5128 Command Catalog Validation Ledger

Opened: 2026-06-03T09:06:02Z

## Objective

Run every `daylily-omics-analysis` command catalog command on `dyec5128`, capped at four active live workflows at a time, using existing control-data manifests/configs and grouping run-directory work by DRA mount.

## Source Of Truth

- Catalog: `config/daylily_pipeline_command_catalog.yaml`
- Repository: `daylily-omics-analysis`
- Catalog default tag: `2.0.38`
- Cluster: `dyec5128`
- Profile/region: `lsmc` / `us-west-2`
- Execution entity: `dyec5128`
- Export prefix pattern: `s3://lsmc-ssf-sequencing-data/derived/validation/dyec5128/dyec5128/<analysis_id>/`

## Driver

The durable driver for this ledger is:

```bash
source ./activate
python docs/plans/20260603T090602Z_dyec5128_command_catalog_validation/driver.py --preflight-only
python docs/plans/20260603T090602Z_dyec5128_command_catalog_validation/driver.py
```

The driver:

- Stops at Gate 0 if `dyec5128` is not visible.
- Generates sample configs using `dyec samples stage --config-only`.
- Uses each catalog command's targets/flags, `jobs`, `genome`, and `git_tag`.
- Launches via `dyec workflow launch`; submitted DayOA commands are forced through `source dyoainit; dy-a slurm <genome>; dy-r ...`.
- Refuses to submit rendered commands containing `bin/day_run` or `snakemake`.
- Launches dry-runs before live runs.
- Uses `--export-trigger on-success --delete-on-export-success` for live runs.
- Leaves run DRAs attached unless separately approved for deletion.
- Polls workflow status and captures workflow logs at terminal state.

## Command Groups

### No DRA

1. `simple-test`

### Startup Reference DRA Only

Sample configs are regenerated with `dyec samples stage --config-only` and must contain only `/fsx/references` paths, with no `/fsx/staging` paths.

- S1: `illumina_snv_alignstats`, `illumina_snv_alignstats_relatedness_vep_multiqc`, `illumina_hg002_kitchensink_multiqc`, `ultima_snv_alignstats`
- S2: `ultima_snv_alignstats_kitchensink`, `ont_snv_alignstats`, `ont_snv_alignstats_kitchensink`, `pacbio_snv_alignstats`
- S3: `roche_snv_alignstats`, `hybrid_ilmn_ont_snv`, `hybrid_ilmn_ont_snv_kitchensink`, `inflection-bjuice-product-v0.1`
- S4: `hybrid_ultima_ont_snv`, `complete_genomics_mgi_snv_concordance`

### Run-Directory DRAs

- Illumina 25B: `20260514_LH01106_0009_B23TVLGLT4`
  - `illumina_run_qc`
  - `illumina_bclconvert`
  - `illumina_run_qc_bclconvert`
- ONT: `20260513_ONT_HG003`
  - `ont_run_qc`
- Ultima: `602221-20260417_2346`
  - `ultima_run_qc`

## Gate 0

Status: pending driver execution.

Gate 0 requires:

- `dyec --json cluster describe --profile lsmc --region us-west-2 --cluster dyec5128` succeeds.
- Headnode read-only preflight succeeds.
- `/fsx/references` is readable.
- `/fsx` free space is recorded.
- Slurm state is recorded.

If Gate 0 remains blocked, the driver records the exact command and stderr in `events.jsonl` and `report.md`, and does not create mounts or launch workflows.
