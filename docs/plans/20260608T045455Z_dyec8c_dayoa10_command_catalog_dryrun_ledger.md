# dyec8c DayOA 10.0.0 Command-Catalog Dry-Run Ledger

Created: 2026-06-08T04:54:55Z

## Objective

Use DYEC `10.0.0` and DayOA `10.0.0` to run DYEC command-catalog dry-runs
against existing cluster `dyec8c` in `us-west-2`.

## Boundaries

- No cluster create, update, or delete.
- No live DayOA workflow execution; `dyec tests command-catalog --dry-run` only.
- No direct `snakemake`; DYEC/DayOA supported launch surfaces only.
- Do not create missing DRA mounts without explicit approval.

## Inputs

- Cluster: `dyec8c`
- Profile: `lsmc`
- Region: `us-west-2`
- Evidence root: `s3://lsmc-ssf-sequencing-data/derived/validation/`
- Stamp: `20260608T045455Z`
- Evidence prefix:
  `s3://lsmc-ssf-sequencing-data/derived/validation/dyec8c/command_catalog_results/10.0.0-20260608T045455Z/`

## Rows

| Row | Status | Evidence |
| --- | --- | --- |
| G0-001 | PASS | Local `dyec --json version` reports `10.0.0`; `pcluster version` reports `3.15.0`; cluster `dyec8c` is `CREATE_COMPLETE` with compute fleet `RUNNING`. |
| TAG-001 | PASS | Pushed DayOA and DYEC `jem-dev` plus annotated `10.0.0` tags to `origin`; `git ls-remote --tags origin 10.0.0` returns remote tag refs. |
| ALL-001 | BLOCKED | `--command-codes all` preflight found missing run-directory mounts for Illumina, ONT, and Ultima run S3 prefixes. No `--create-missing-mounts` was used. |
| SLIM-001 | BLOCKED | First slim batch exited before launch: `complete_genomics_mgi_snv_concordance` has no supported sample manifest mode. |
| SLIM-002 | FAIL | Retried 13 supported slim commands excluding CG/MGI; all 13 launched, all failed before dry-run on `[ERROR] goleft runtime repair target not found in workflow/rules/go_left.smk`. |
| FIX-001 | PASS | Patched DYEC headnode launcher to skip the old goleft runtime repair when DayOA already has native guarded `sex_args`; added `complete_genomics_solo` command-catalog manifest support. |
| TEST-001 | PASS | Focused tests: 65 passed. Full DYEC suite: 1068 passed, 8 skipped. |
| REL-001 | PASS | DYEC `10.0.1` committed, tagged, pushed, and installed locally. |
| RETRY-001 | BLOCKED | Retry2 recognized CG/MGI but config generation failed because the initial CG FASTQ fixture paths were absent from `s3://lsmc-dayoa-references-usw2/`. |
| FIX-002 | PASS | Updated CG/MGI fixture to verified control-data HG003 pair under `s3://lsmc-dayoa-control-data-usw2/genomic_data/organism_reads/H_sapiens/complete_genomics/`; DYEC `10.0.2` committed, tagged, pushed, installed locally. |
| RETRY-002 | FAIL | Retry3 launched all 14 non-run-directory catalog dry-runs, but the goleft native-guard marker still mismatched DayOA's escaped Snakemake shell text; all 14 returned nonzero. |
| FIX-003 | PASS | Corrected the generated marker to match DayOA's escaped `${{sex_args[@]}}` shell text; focused tests passed and full DYEC suite passed: `1068 passed, 8 skipped`. |
| REL-003 | RUNNING | Preparing DYEC `10.0.3` commit/tag/push and local reinstall before the next `dyec8c` dry-run. |
| RETRY-003 | PENDING | Retry dry-run after installing/pushing DYEC `10.0.3`. |
| REPORT-001 | PENDING | Final status after retry. |
