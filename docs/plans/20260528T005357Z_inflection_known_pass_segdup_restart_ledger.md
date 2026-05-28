# Inflection Known-Pass Segdup Restart Ledger

Created: 2026-05-28T00:53:57Z

## Gate 0

| Field | Value |
|---|---|
| Cluster | `goodole3` |
| Profile | `lsmc` |
| Region | `us-west-2` |
| Run directory | `/fsx/analysis_results/ubuntu/inflection_20260527-2.0.11/daylily-omics-analysis` |
| Requested scope | Stop the active downsample Snakemake controller, limit `sentdhiomr.segdup_genes` to known passing genes, dry-run with `-j 400 --rerun-triggers mtime -n`, then launch if completed outputs are not scheduled for rerun. |
| Known passing segdup genes | `CYP11B1`, `NCF1`, `SMN1` |
| Known failing segdup genes excluded | `CFH`, `CYP2D6`, `GBA`, `HBA`, `PMS2`, `STRC` |
| Config key | `sentdhiomr.segdup_genes` in `config/day_profiles/slurm/rule_config.yaml` |
| Interpretation of final user typo | Treat the final repeated `-n` as intended actual launch without `-n` only after a clean dry-run guard. |

## Ledger

| Time UTC | Action | Result |
|---|---|---|
| 2026-05-28T00:53:57Z | Create ledger | Started. |
| 2026-05-28T00:57:57Z | Stop combined downsample controller | Stopped the single combined `inflection_2011_real_j125_20260527T195621Z` controller. Before stop there were `80` matching Inflection Slurm jobs across `ILMN15x-ONT7x` and `ILMN20x-ONT10x`; after stop there were `0`. |
| 2026-05-28T00:57:57Z | Limit segdup genes and scope 20x-only config | Wrote `/fsx/analysis_results/ubuntu/inflection_20260527-2.0.11/daylily-omics-analysis/config/units.ILMN20x-ONT10x.tsv` with the single `ILMN20x-ONT10x` unit row. Backed up `config/day_profiles/slurm/rule_config.yaml` to `rule_config.yaml.bak.20260528T005757Z` and set `sentdhiomr.segdup_genes` from `CFH,CYP11B1,CYP2D6,GBA,NCF1,PMS2,SMN1,STRC,HBA` to `CYP11B1,NCF1,SMN1`. |
| 2026-05-28T01:03:03Z | Interactive dry-run plan | Ran the 20x-only known-pass dry-run from tmux/interactively as `ubuntu`: `bin/day_run produce_sent_align produce_dmd_dedup_cram produce_sentdhiomr_sv produce_snv_concordances produce_sentdhiomr_snv_vcf produce_sentdhiomr_cnv produce_sentdhiomr_mito produce_sentdhiomr_segdup produce_expansionhunter --config units_table=/fsx/analysis_results/ubuntu/inflection_20260527-2.0.11/daylily-omics-analysis/config/units.ILMN20x-ONT10x.tsv -j 400 -p -k --rerun-triggers mtime -n`; rc `0`; job stats total `31`. Evidence: `.ignore/inflection_20x10x_knownpass_j400_dryrun_interactive_20260528T010226Z.log` and `.ignore/inflection_20x10x_knownpass_j400_dryrun_latest.out`. |
| 2026-05-28T01:04:28Z | Kill all tmux sessions | Per user request, killed the headnode tmux server. Before kill: `48` tmux sessions; after kill: `0`; `who`/`w` empty after kill. Evidence: `/fsx/analysis_results/ubuntu/inflection_20260527-2.0.11/daylily-omics-analysis/.ignore/tmux_kill_all_20260528T010428Z.txt`; SSM command `a932442b-31ad-486a-8196-7b564662afae`. No Inflection Slurm jobs were present before or after the tmux kill snapshot. |
| 2026-05-28T01:17:15Z | First real launch attempt | Started tmux `inflection_20x10x_knownpass_j400_real_20260528T011703Z`, but the command exited immediately before submitting jobs because `bin/day_run` was invoked before `source dyoainit`/`dy-a`; rc `33`, error `colr: command not found`. No Slurm jobs were present after this failed attempt. |
| 2026-05-28T01:18:28Z | Real 20x10 launch | Started a new interactive `ubuntu` tmux/login-shell controller `inflection_20x10x_knownpass_j400_real_20260528T011810Z` on `goodole3`. The pane ran `source dyoainit`, `dy-a slurm hg38_broad` where `hg38_broad` was verified as the only directory under `results/day/`, then `dy-r produce_sent_align produce_dmd_dedup_cram produce_sentdhiomr_sv produce_snv_concordances produce_sentdhiomr_snv_vcf produce_sentdhiomr_cnv produce_sentdhiomr_mito produce_sentdhiomr_segdup produce_expansionhunter --config units_table=/fsx/analysis_results/ubuntu/inflection_20260527-2.0.11/daylily-omics-analysis/config/units.ILMN20x-ONT10x.tsv -j 400 -p -k --rerun-triggers mtime` without `-n`. At disconnect, tmux was still running, Snakemake had completed `2 of 31` steps and submitted Slurm jobs `3146`-`3151`; `squeue` showed `6 CONFIGURING`. Log: `.ignore/inflection_20x10x_knownpass_j400_real_20260528T011810Z.log`; rc file pending until controller exits: `.ignore/inflection_20x10x_knownpass_j400_real_20260528T011810Z.rc`. |
