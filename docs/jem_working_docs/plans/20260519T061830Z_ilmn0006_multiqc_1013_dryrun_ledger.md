# ILMN 0006 DayOA 1.0.13 Final MultiQC Dry-Run Ledger

Date opened: 2026-05-19T06:18:30Z

## Control

Controlling request: enter the existing ILMN 0006 headnode tmux run directory, run `git pull`, check out DayOA tag `1.0.13`, run `git pull` again, then dry-run final MultiQC generation with `--rerun-triggers mtime -n` to confirm the workflow will not rerun heavy upstream work.

Ledger path: `/Users/jmajor/projects/daylily/daylily-ephemeral-cluster/docs/plans/20260519T061830Z_ilmn0006_multiqc_1013_dryrun_ledger.md`

Execution scope:
- Local repo: `/Users/jmajor/projects/daylily/daylily-ephemeral-cluster`
- AWS profile: `lsmc`
- AWS region: `us-west-2`
- Cluster: `may26-d`
- Headnode: `i-0e7639ff46f207ae7`
- Tmux session: `ilmn_0006_align_dedup_alignstats_20260517T185626Z`
- Run checkout: `/fsx/analysis_results/ubuntu/ilmn_0006_align_dedup_alignstats_20260517T185626Z/daylily-omics-analysis`
- Run log dir: `/home/ubuntu/daylily-runs/ilmn_0006_align_dedup_alignstats_20260517T185626Z`

Hard boundaries:
- Dry-run only in this ledger.
- Stop after dry-run review if planned jobs include alignment, DMD dedup, SNV calling, alignstats, or other unexpectedly heavy upstream reruns.
- Preserve existing run-local dirty state before checking out `1.0.13`; do not reset or discard remote changes.
- Use DayEC SSM helpers as `ubuntu`.

## Gate 0 Baseline

- Local repo status at open: `## codex/docs-plans-ledgers...origin/codex/docs-plans-ledgers` with pre-existing untracked artifacts, including `docs/ntc_and_other_analysis_bugs.md`, `tmp-export/`, and several 0007 index reports.
- Headnode info: `daylily-ec --json headnode info --profile lsmc --region us-west-2 --cluster may26-d` returned cluster `CREATE_COMPLETE`, compute fleet `RUNNING`, headnode `i-0e7639ff46f207ae7`, private IP `10.0.0.121`.
- Baseline SSM command: `9c053690-10a8-459c-acf4-30efd2b8f475`.
- Baseline remote identity: `ubuntu@ip-10-0-0-121`.
- Baseline checkout: detached `HEAD`, `git describe=1.0.7-dirty`, `HEAD=a9d6a5da0a2778f2dcd135f6455c1c752e43d40e`, dirty `workflow/rules/common.smk`, untracked `sbatch_errs.log`.
- Baseline final report state: missing `results/day/hg38/reports/DAY_final_multiqc.html` and missing `results/day/hg38_broad/reports/DAY_final_multiqc.html`.
- Baseline tmux state: session `ilmn_0006_align_dedup_alignstats_20260517T185626Z` exists; pane `0.0` is in the run checkout with command `bash`.
- Baseline Slurm state: `squeue -u ubuntu` returned only the header; no active jobs.
- Recent run logs show previous direct MultiQC attempts through `stage_multiqc_inputs_final_forced_20260518T150028Z.log` and `multiqc_final_wgs_direct_live_20260518T143202Z.log`, but no final report exists.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | DayEC/DayOA | Record local repo, headnode, tmux, Slurm, remote checkout, and final report baseline before mutation. | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 Baseline section. |  | Baseline recorded before checkout/tag change. |
| TAG-001 | DayOA headnode | In the existing run tmux session, run pre-checkout `git pull`, fetch/check out tag `1.0.13`, and run post-checkout `git pull` while preserving dirty state. | SUCCESS | feature_implementation | Gate 1 | orchestrator | Write attempt with long remote filename failed before mutation because AWS SSM comments are capped at 100 chars. Retry wrote `/home/ubuntu/daylily-runs/ilmn0006_mqc1013_20260519T062200Z.sh` with `write_remote_text` command `5f281ad4-e376-430f-9be0-034b66619257` and launched it in tmux with command `70321371-fd1e-41cb-8dec-4029f4b722ba`. Pre-checkout `git pull --ff-only` fetched tags `1.0.8` through `1.0.13` and returned rc `1` because the checkout was detached. Dirty state was preserved in `stash@{0}` with message `codex-before-1.0.13-ilmn0006-20260519T062200Z`. `git checkout 1.0.13` succeeded at `aef09db649edf7edd2d91d07851dd249f991fba2`; post-checkout `git pull --ff-only` returned rc `1` because the checkout is detached. Status: `/home/ubuntu/daylily-runs/ilmn_0006_align_dedup_alignstats_20260517T185626Z/multiqc_1013_dryrun_20260519T062200Z.status.json`. |  | Run checkout is at exact tag `1.0.13`; previous run-local dirty state was not discarded. |
| MQC-DRYRUN-001 | DayOA headnode | Run `produce_multiqc_all -j 200 -p -k --rerun-triggers mtime -n` for ILMN 0006 at tag `1.0.13` with sent/dmd/sentd config. | BLOCKED | contract_test | Gate 2 | orchestrator | First dry-run attempt after checkout failed during activation: `dyoainit_rc=3`, `day_activate_rc=2`, because `USER` was unset. Retry with `USER/LOGNAME/HOME` set and sourced `./dyoainit --skip-project-check` successfully, but `bin/day_activate slurm hg38 remote` still failed with `DAY_ROOT is not set`; status `/home/ubuntu/daylily-runs/ilmn_0006_align_dedup_alignstats_20260517T185626Z/multiqc_1013_dryrun_retry_20260519T062600Z.status.json`. Final retry sourced run-local `./dyoainit --skip-project-check`, set the explicit slurm profile env, and ran `DAY_CONTAINERIZED=true bin/day_run produce_multiqc_all -j 200 -p -k --rerun-triggers mtime -n --config genome_build=hg38 "aligners=['sent']" "dedupers=['dmd']" "snv_callers=['sentd']" "sv_callers=[]"`. It reached Snakemake and failed with `SyntaxError in file .../workflow/rules/common.smk, line 1172: Expected name after module keyword.` Log: `/home/ubuntu/daylily-runs/ilmn_0006_align_dedup_alignstats_20260517T185626Z/multiqc_1013_manual_dryrun_20260519T063100Z.log`; status: `/home/ubuntu/daylily-runs/ilmn_0006_align_dedup_alignstats_20260517T185626Z/multiqc_1013_manual_dryrun_20260519T063100Z.status.json`, `dryrun_rc=1`. Operator correction was then applied exactly: `source ./dyoainit --skip-project-check` from the run checkout. This exact-path attempt had `dyoainit_rc=0`, `DAY_ROOT=/fsx/analysis_results/ubuntu/ilmn_0006_align_dedup_alignstats_20260517T185626Z/daylily-omics-analysis`, `profile_env_rc=0`, then failed at the same Snakemake syntax error. Log: `/home/ubuntu/daylily-runs/ilmn_0006_align_dedup_alignstats_20260517T185626Z/multiqc_1013_exact_dyoainit_dryrun_20260519T064000Z.log`; status: `/home/ubuntu/daylily-runs/ilmn_0006_align_dedup_alignstats_20260517T185626Z/multiqc_1013_exact_dyoainit_dryrun_20260519T064000Z.status.json`, `dryrun_rc=1`. | DayOA tag `1.0.13` has top-level Python variable assignment `module = importlib.util.module_from_spec(spec)` in `workflow/rules/common.smk`; Snakemake parses `module` as its directive keyword and aborts before DAG construction. | Dry-run command was attempted with exact `source ./dyoainit` and failed before any DAG/job table was produced. |
| SAFETY-001 | DayOA headnode | Review dry-run job table and confirm whether alignment, DMD dedup, SNV calling, alignstats, or VEP reruns are planned. | BLOCKED | legitimate_safety_handling | Gate 3 | orchestrator | SSM status command `e6ced0d3-0b83-4573-97d3-1c16fe1e34fa` showed no runner process and `squeue -u ubuntu` returned only the header. Because Snakemake failed before DAG construction, there is no job table to inspect. | The `1.0.13` `common.smk` syntax error prevents DAG construction. | No work was submitted or rerun, but safety review cannot answer planned-job counts until the syntax error is fixed. |
| FINAL-001 | DayEC/DayOA | Update ledger with terminal evidence and report whether it is safe to run the real final MultiQC command. | SUCCESS | contract_test | Gate 5 | orchestrator | Ledger rows updated with tag checkout, activation attempts, syntax failure, and empty Slurm evidence. |  | It is not safe to launch the real final MultiQC command from this checkout until the `common.smk` `module` variable bug is fixed and a clean dry-run produces an inspectable job table. |

## Terminal Summary

- Rows terminal: `5/5`.
- Objective complete: no. The run checkout is at exact tag `1.0.13`, but final MultiQC dry-run is blocked before DAG construction by a `common.smk` syntax error in the tag.
- Remote checkout state after this ledger: exact tag `1.0.13` at `aef09db649edf7edd2d91d07851dd249f991fba2`; pre-existing dirty state preserved in `stash@{0}`.
- No real workflow was launched; no Slurm jobs were submitted during the dry-run attempts.
- The exact-path activation evidence requested by the operator is in `/home/ubuntu/daylily-runs/ilmn_0006_align_dedup_alignstats_20260517T185626Z/multiqc_1013_exact_dyoainit_dryrun_20260519T064000Z.log`.
