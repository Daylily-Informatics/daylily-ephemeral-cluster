# Inflection Segdup Cancel Ledger

Created: 2026-05-27T23:27:21Z

## Gate 0

| Field | Value |
|---|---|
| Cluster | `goodole3` |
| Profile | `lsmc` |
| Region | `us-west-2` |
| Run directory | `/fsx/analysis_results/ubuntu/inflection_20260527-2.0.11/daylily-omics-analysis` |
| Controller tmux | `inflection_2011_real_j125_20260527T195621Z` |
| Controller rc file | `.ignore/inflection_2011_real_j125_latest.rc` |
| Main Snakemake log | `.snakemake/log/2026-05-27T195632.640964.snakemake.log` |
| Scope | Cancel only queued/running `sentdhiomr_call_segdup_gene` jobs for genes already observed failing: `CFH`, `CYP2D6`, `GBA`, `HBA`, `PMS2`, `STRC`; leave passing segdup genes and all non-segdup work alone. |

## Ledger

| Time UTC | Action | Result |
|---|---|---|
| 2026-05-27T23:27:21Z | Create ledger | Started. |
| 2026-05-27T23:33:52Z | First SSM cancellation/check pass | SSM command `36d7a5f6-cc44-4cc1-9d71-ccc6bab24b86` ran as `ubuntu`; both cancellation passes found `0` live failing `sentdhiomr_call_segdup_gene` candidates, so no `scancel` calls were issued. Evidence: `/fsx/analysis_results/ubuntu/inflection_20260527-2.0.11/daylily-omics-analysis/.ignore/segdup_cancel_20260527T233352Z.json`. |
| 2026-05-27T23:47:53Z | Interactive login-shell rerun | Started persistent tmux `inflection_segdup_ops_20260527T234753Z`, sourced `/tmp/inflection_segdup_ops_20260527T234753Z.sh` from an interactive `ubuntu` bash login shell, and copied sourced script evidence to `.ignore/inflection_segdup_ops_20260527T234753Z.sourced.sh`. |
| 2026-05-27T23:48:08Z | Verify interactive shell context | Confirmed `user=ubuntu`, shell flags include interactive `i`, `dy-r` alias is `bin/day_run`, and `dy-a` alias is `source bin/day_activate`. Evidence: `/fsx/analysis_results/ubuntu/inflection_20260527-2.0.11/daylily-omics-analysis/.ignore/segdup_interactive_ops_20260527T234753Z.log`. |
| 2026-05-27T23:49:39Z | Interactive cancellation pass 1/2 | Pass 1 and pass 2 both found `0` live failing segdup candidates; no `scancel` calls issued. Passing genes stayed PASS for both branches: `CYP11B1`, `NCF1`, `SMN1`. Failed genes recorded for both branches: `CFH`, `CYP2D6`, `GBA`, `HBA`, `PMS2`, `STRC`. Evidence: `.ignore/segdup_interactive_ops_20260527T234753Z.json`. |
| 2026-05-27T23:49:39Z | Conditional restart guard | Original controller `inflection_2011_real_j125_20260527T195621Z` was still running and `.ignore/inflection_2011_real_j125_latest.rc` was absent, so no restart was launched. Started watcher tmux `inflection_2011_no_segdup_restart_watch_20260527T234753Z`; it will start `inflection_2011_no_segdup_j125_20260527T234753Z` only if the original controller exits nonzero. |
| 2026-05-27T23:49:39Z | Remaining DAG classification | Interactive dry-runs completed `rc=0`: full target set has `1058` remaining/to-be-submitted jobs; no-segdup target set has `1043` remaining/to-be-submitted jobs. Strict parsed evidence is stored in `.ignore/segdup_interactive_ops_20260527T234753Z.json`; dry-run logs are `.ignore/inflection_2011_full_targets_remaining_dryrun_20260527T234753Z.log` and `.ignore/inflection_2011_no_segdup_targets_remaining_dryrun_20260527T234753Z.log`. |
| 2026-05-27T23:52:23Z | Current live queue refresh | Controller still running; no rc file. Live queue has `18` pending `15x7x sentdhiomr_stage3`, and `20x10x` SNV jobs: `2` running `sentdhiomr_pass2`, `4` pending `sentdhiomr_pass2`, `4` pending `sentdhiomr_model_apply`, `8` pending `sentdhiomr_concat_pass`. `/fsx` is `4.4T` size, `775G` used, `3.6T` available, `18%` used. |
