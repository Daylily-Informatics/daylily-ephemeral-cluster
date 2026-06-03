# BCL Full 25B Batched Resume And Cluster Cleanup Ledger

## Baseline

- Started: 2026-06-02T20:31:17Z
- Active BCL cluster: dyec5117, us-west-2
- Existing BCL source mount: /fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4
- Existing analysis checkout: /fsx/analysis_results/ubuntu/bcl25b_full_shard008_odirect_off_20260602T115314Z/daylily-omics-analysis
- Approved unused cluster deletion target: dyec5123, us-west-2
- Local artifact root: bench_expts/full25b_shard008_lane_batched_resume_20260602T203117Z

## Execution Rows

| Row | Owner | Action | Status | Evidence |
| --- | --- | --- | --- | --- |
| 1 | Agent 1 | Record cluster and FSx baseline | RUNNING | pending |
| 2 | Agent 2 | Delete approved unused cluster dyec5123 | RUNNING | pending |
| 3 | Agent 3 | Preserve Phase 1 L001/L003/L008 evidence | RUNNING | pending |
| 4 | Agent 4 | Delete Phase 1 L001/L003 BCL lane data after preserve | PENDING | pending |
| 5 | Agent 5 | Dry-run Phase 2 L002/L006/L008 with --rerun-triggers mtime -n | PENDING | pending |
| 6 | Agent 5 | Run Phase 2 L002/L006/L008 if FSx gate passes | PENDING | pending |
| 7 | Agent 3 | Preserve Phase 2 L002/L006/L008 evidence | PENDING | pending |
| 8 | Agent 4 | Delete Phase 2 L002/L006/L008 BCL lane data after preserve | PENDING | pending |
| 9 | Agent 5 | Dry-run Phase 3 L004/L005/L007 with --rerun-triggers mtime -n | PENDING | pending |
| 10 | Agent 5 | Run Phase 3 L004/L005/L007 if FSx gate passes | PENDING | pending |
| 11 | Agent 3 | Preserve Phase 3 L004/L005/L007 evidence | PENDING | pending |
| 12 | Agent 4 | Delete Phase 3 L004/L005/L007 BCL lane data after preserve | PENDING | pending |
| 13 | Agent 1 | Final report with lane sizes, benchmarks, cleanup, FSx | PENDING | pending |

## Guardrails

- Do not start a new cluster.
- Do not create or mount a new DRA.
- Use only dyec5117 and the existing mounted ILMN run directory.
- Never call `snakemake` directly for DayOA work. Use `dy-r` only.
- DayOA workflow work must be run in a persistent, meaningfully named `tmux` session on the headnode as `ubuntu`, using an interactive bash login shell that remains alive after submitted commands exit.
- Required DayOA command sequence in that pane: `source dyoainit`, then `dy-a slurm hg38` or `dy-a slurm hg38_broad`, then `dy-r <targets> <flags>`.
- Copy benchmark TSVs and FASTQ size manifests only; do not copy FASTQ payloads locally.
- Before every live DayOA run, check /fsx space and run `--rerun-triggers mtime -n`.
- If workflow lock is stale, unlock through `dy-r` only, then rerun dry-run before live execution.
- Delete only exact manifest paths after evidence has been preserved.

## Corrections

- 2026-06-02T21:10Z: User clarified that DayOA workflow commands must never call `snakemake` directly. A prior direct `snakemake --unlock` attempt failed and is superseded. All subsequent workflow help, unlock, dry-run, and live execution must use `dy-r` inside a persistent interactive `ubuntu` tmux login shell.
