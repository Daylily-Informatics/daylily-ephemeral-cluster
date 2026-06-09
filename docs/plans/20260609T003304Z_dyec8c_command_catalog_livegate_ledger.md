# dyec8c Command Catalog Dry-Run And Live Gate Ledger

Created: 2026-06-09T00:33:04Z

## Objective

Run DYEC command-catalog commands in dry-run mode on existing cluster `dyec8c`.
If the dry-runs pass, run the solo Illumina, solo ONT, solo Ultima, and
ILMN+ONT hybrid command-catalog entries live without `-n`.

## Boundaries

- Use existing cluster `dyec8c` in `us-west-2` with AWS profile `lsmc`.
- Use DYEC/DayOA supported launch surfaces only.
- Never invoke `snakemake` directly; DayOA execution must go through `dy-r`.
- Do not perform Slurm/node/job interventions. Monitoring and reporting only.
- Creating read-only run-directory DRAs is allowed only through DYEC's
  `--create-missing-mounts` path and must wait long enough for FSx DRA creation.
- Live run gate: launch live commands only if the full dry-run pass succeeds.

## Gate 0 Baseline

- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DYEC branch/state: `jem-dev...origin/jem-dev` with pre-existing dirty files
  and many untracked prior plan artifacts. This run will not alter unrelated
  source files.
- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`,
  `jem-dev...origin/jem-dev`.
- Required DayOA contract read: `/Users/jmajor/.codex/AGENTS-HOW-TO-RUN-DAYOA.md`.
- DYEC CLI: `dyec --json version` -> `10.0.4`.
- Cluster: `dyec8c`.
- Initial run-mount state: `dyec mounts list --cluster dyec8c --profile lsmc --region us-west-2` -> `No mounts found.`
- Initial all-catalog dry-run preflight:
  `dyec tests command-catalog --cluster dyec8c --profile lsmc --region us-west-2 --command-codes all --evidence-s3-uri s3://lsmc-ssf-sequencing-data/derived/validation/ --dry-run --stamp 20260609T003304Z --output-dir docs/plans/20260609T003304Z_dyec8c_command_catalog_dryrun_livegate_logs --timeout-minutes 1 --poll-interval-seconds 30`
  -> blocked before launch on missing run-directory DRA mounts.
- Missing run-directory sources:
  - `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0009_B23TVLGLT4/`
  - `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/RUN602221/2026/602221-20260417_2346/`
  - `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260513_ONT_HG003/`

## Control Ledger

| Row | Status | Evidence | Root Cause | Terminal Note |
| --- | --- | --- | --- | --- |
| G0-001 | SUCCESS | Gate 0 baseline above. |  | Baseline recorded. |
| DRY-001 | BLOCKED | Initial `--command-codes all --dry-run` stopped on missing run-directory DRA mounts before launching workflows. | `dyec8c` had no existing run-directory mounts. | Superseded by DRY-002 with supported `--create-missing-mounts`. |
| DRY-002 | ATTEMPTING_BUGFIX | First full catalog dry-run with `--create-missing-mounts` failed before creating a mount: `Invalid length for parameter Tags, value: 0, valid min length: 1`. Patched `daylily_ec/run_mounts.py` to omit `Tags` when the tag map is empty and added `tests/test_run_mounts.py::test_create_run_mount_omits_empty_tags_from_fsx_payload`; `pytest tests/test_run_mounts.py -q` -> `29 passed`. | DYEC FSx create-DRA payload included `Tags=[]`; FSx requires the `Tags` member to be absent when no tags are supplied. | Retrying dry-run after local bugfix. |
| LIVE-001 | OPEN | Pending live solo Illumina command after dry-run success. |  |  |
| LIVE-002 | OPEN | Pending live solo ONT command after dry-run success. |  |  |
| LIVE-003 | OPEN | Pending live solo Ultima command after dry-run success. |  |  |
| LIVE-004 | OPEN | Pending live ILMN+ONT hybrid command after dry-run success. |  |  |
| REPORT-001 | OPEN | Pending final report. |  |  |

## Final State

Pending.
