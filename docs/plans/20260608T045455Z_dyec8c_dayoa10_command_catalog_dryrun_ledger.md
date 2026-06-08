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
| REL-001 | RUNNING | Preparing DYEC `10.0.1` patch release; DayOA remains `10.0.0`. |
| RETRY-001 | PENDING | Retry dry-run after installing/pushing DYEC `10.0.1`. |
| REPORT-001 | PENDING | Final status after retry. |
