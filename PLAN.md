# Q1 2026 Daylily Omics Analysis Inventory

## Summary
Inventory Jan/Feb/Mar 2026 S3 exports under `s3://lsmc-dayoa-omics-analysis-us-west-2/FSxLustre20260*/analysis_results/ubuntu/*/daylily-omics-analysis/`, classify each analysis repo by `results/day/hg38*` completion, and produce a TSV, spreadsheet, and runbook.

Use `AWS_PROFILE=daylily-service-lsmc` and read-only S3 listing/copy calls. Do not download large result files; only stream S3 metadata and small files like `day_cmd.log`, `config/samples.tsv`, `config/units.tsv`, `day_pipe_stats.json`, and `daylily.successful_run`.

## Key Outputs
- Write outputs under `reports/dayoa-q1-2026-analysis-inventory/`:
  - `analysis_dirs.tsv`: one row per `<analysis-code>/daylily-omics-analysis/`
  - `analysis_dirs.xlsx`: workbook with summary, all dirs, completed dirs, incomplete dirs, and command log sheets
  - `dy-r-runbook.md`: operational runbook for recreating configs and launching runs
  - `inventory_manifest.json`: metadata about scan time, bucket, prefixes, and object-count method
- Include TSV columns:
  - `fsx_export`, `export_month`, `analysis_code`, `repo_s3_uri`, `status`
  - `has_day_cmd_log`, `has_success_marker`, `hg38_result_prefixes`, `hg38_result_object_count`
  - `sample_count`, `unit_count`, `sample_ids`, `run_ids`, `platforms`, `coverage_or_experiment_ids`
  - `first_command_time`, `last_command_time`, `command_count`, `dryrun_command_count`
  - `pipeline_command`, `pipeline_targets`, `pipeline_genome`, `pipeline_profile`, `pipeline_jobs`
  - `total_runtime_seconds`, `rule_count`, `top_rules`, `notes`
- Define status values:
  - `complete`: `daylily.successful_run` exists and at least one object exists under `results/day/hg38*/`
  - `partial_results`: `results/day/hg38*/` exists but success marker is absent
  - `no_hg38_results`: repo exists but no `results/day/hg38*/` objects are found
  - `metadata_missing`: repo exists but key metadata files needed for counts/command parsing are absent

## Implementation
- Discover only Jan/Feb/Mar exports:
  - `FSxLustre20260122T043503Z`
  - `FSxLustre20260122T112533Z`
  - `FSxLustre20260122T113142Z`
  - `FSxLustre20260211T122354Z`
  - `FSxLustre20260213T142513Z`
  - `FSxLustre20260216T130001Z`
  - `FSxLustre20260309T122755Z`
- Build a small inventory script that:
  - lists `analysis_results/ubuntu/` child prefixes
  - keeps only prefixes containing `daylily-omics-analysis/`
  - checks `results/day/` common prefixes matching `hg38` or `hg38_*`
  - parses `day_cmd.log` `SMK>` entries and chooses `pipeline_command` as the latest non-dryrun command, falling back to latest command if only dry-runs exist
  - parses `config/samples.tsv` and `config/units.tsv`; `sample_count` is unique `SAMPLEID`, `unit_count` is data rows in `units.tsv`
  - parses `day_pipe_stats.json` for total runtime and rule names when present
- Build `dy-r-runbook.md` from observed repo conventions:
  - activate cluster/headnode Daylily shell
  - clone or enter `/fsx/analysis_results/ubuntu/<analysis-code>/daylily-omics-analysis`
  - create/copy `config/samples.tsv` and `config/units.tsv`
  - validate with `head`, row counts, and expected columns
  - run dry-run and real commands with `dy-a slurm hg38` or `dy-a slurm hg38_broad`, then `dy-r ... -n` and `dy-r ...`
  - include examples for ILMN, ONT, PacBio, Ultima, Roche, and hybrid runs based on observed `COMMANDS_MUST_RUN.md`/`day_cmd.log`

## Test Plan
- Run the inventory script against one known completed prefix and one likely incomplete prefix first.
- Validate the TSV:
  - header has all expected columns
  - every row has stable tab count
  - `complete` rows have nonzero `hg38_result_object_count`
  - no April export is included
- Open/read the generated XLSX with Python to confirm sheet names and row counts match the TSV.
- Spot-check at least three S3 rows manually against `aws s3 ls` and streamed metadata files.

## Assumptions
- The user meant `aws s3 ls`, not `aws ls`.
- “Jan/Feb/March 2026 dirs” excludes the April `FSxLustre20260412T103705Z` export even though it matches `FSxLustre20260*`.
- It is acceptable to use read-only S3 API calls and stream small metadata files locally, but not sync large result trees.
- If `day_cmd.log` has several commands, the report should preserve all commands in the spreadsheet and use the latest non-dryrun command as the primary pipeline run.
