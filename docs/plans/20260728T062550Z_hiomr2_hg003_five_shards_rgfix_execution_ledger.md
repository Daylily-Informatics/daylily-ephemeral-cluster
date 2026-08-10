# HIOMR2 HG003 original-five-shard RG/VCF contract execution ledger

## Objective

Run the released HIOMR2 kitchen-sink plus Inflection analytical-package test for
HG003 only, using the original five chromosome shards on `hg38`.  Preserve shards
with `--keep-temp`; use `RnD` and delivery batch `this-time-go`.

## Immutable execution contract

- Cluster/headnode: `preval-hiomr2`, interactive `ubuntu` login shell in tmux
  session `hiomr2_hg003_five_shards_rgfix_20260728`.
- Fresh analysis root:
  `/fsx/analysis_results/preval-hiomr2/hiomrks-hg003-five-shards-rgfix-20260728`.
- DayOA source: merge commit `2096c956243c71f11821a4ea1ce81c90bc7093a4`, annotated
  release tag `13.0.66` (PR #77 merged to `main`).
- Input source and exact seven-file staging source:
  `/fsx/analysis_results/preval-hiomr2/hg003-hiomr2-five-chrom-shards-20260726-live7/daylily-omics-analysis/config/`.
  Each staged file was byte-compared against that source.  The original overlay
  SHA-256 is `3f17500fc419e94aae53388822ece61e97bec11d95e6c81f87d43fa794b782bb`;
  its backup is `bkup/initial_config_20260728/hiomr2_hg003_five_chrom_shards.yaml`.
- Five original scopes: `1-5`, `6-10`, `11-15`, `16-20`, and `21,22,23-25`
  (the final tokens map to X/Y/M under the workflow contract).
- Resolved runtime analysis unit: `HG003-t95ar0arttm7d0`; no HG004 input was staged.

## Command

```bash
dy-r produce_sentdhiomr2_kitchensink produce_sentdhiomr2_inflection_analytical_package \
  -j 300 -p -T 0 \
  --configfile config/hiomr2_hg003_five_chrom_shards.yaml \
  --config 'genome_build=hg38' 'aligners=["sentmm2ont"]' \
  'dedupers=["na"]' 'snv_callers=["sentdhiomr2"]' 'sv_callers=[]' \
  'htd_callers=["smn12"]' use_fq_data_starting_hrs=0 \
  use_fq_data_up_to_hrs=25 'seqone_delivery_batch_id=this-time-go' \
  'hiomr2_inflection_package_mode=analytical' \
  --rerun-triggers mtime --rerun-incomplete --keep-temp
```

## Gate ledger

| ID | Gate | Status | Evidence |
| --- | --- | --- | --- |
| SRC-001 | Released RG/VCF and hard-VCF package contract | COMPLETE | `13.0.66` tag points to `2096c956243c71f11821a4ea1ce81c90bc7093a4`; PR #77 is merged. |
| IN-001 | HG003-only, original five-shard inputs staged with backup | COMPLETE | Seven manifest/overlay inputs copied from the completed original-five-shard root and `cmp`-verified. |
| PLAN-001 | Initial dry-run of exact command | COMPLETE | RC 0; 16 jobs: 5 shard gVCFs, concat, hard-VCF conversion, CNVscope, LongReadSV, manifest, package, and targets. Package planned only `--scoped-vcf`/index. |
| RUN-001 | First live submission | TERMINAL BLOCKED | Controller RC 1 before any Slurm job was accepted. `DAY_PROJECT` had been overwritten by `source dyoainit` without `--project`, so sbatch received `preval-hiomr2`; its registry lookup returned empty JSON. The controller released the lock. |
| FIX-001 | Source-backed cost-center correction | COMPLETE | `source dyoainit --project RnD --skip-project-check`, then `dy-a slurm hg38`, leaves `DAY_PROJECT=<RnD>`. `dyec cost-centers show RnD --profile lsmc` reports active, user `ubuntu`, cap `$500`; July usage is `$0`. |
| PLAN-002 | Corrected-environment dry-run | COMPLETE | RC 0 at 2026-07-28 06:31 UTC after explicit `RnD` initialization. It plans the same 16 jobs, one `HG003-t95ar0arttm7d0` AU, five `sentdhiomr2_scoped_shard_gvcf` jobs, one concat, hard-VCF conversion, CNVscope, LongReadSV, command manifest, and package. No HG004 or completed work is in scope. |
| RUN-002 | Corrected-environment live execution | TERMINAL DIAGNOSED | DYEC accepted Slurm job `491` under `RnD`; preflight completed RC 0 in 25 seconds. LR preparation job `492` then failed RC 1 because Sentieon rejected literal tab characters in the `-R` value, which left no accepted `@RG`; its log explicitly requires escaped `\\t` delimiters. Per the user's explicit stop-and-debug instruction, the persistent controller was stopped and the only remaining run job (`493`, SR preparation) was canceled through the guarded root operation. Final queue state was empty; no unrelated job or Slurm service was changed. |
| FIX-002 | HIOMR-style aligner read-group rendering | IN PROGRESS | The working HIOMR SR and LR rules both pass `-R "@RG\\tID:..."` to their aligners. HIOMR2 currently passes a real-tab header string through `{params.read_group:q}`. The narrow repair is to use an escaped-tab renderer only for HIOMR2 fastq-alignment `-R` parameters and retain real tabs for SAM/CRAM header validation and reheadering. The analysis-root lock was transitioned from the authorized kill operation to the current write operation. |
| PLAN-003 | Post-RG-repair dry-run | COMPLETE | The corrected exact command, with `-T 0`, no `-k`, `--rerun-triggers mtime`, `--rerun-incomplete`, and `--keep-temp -n`, returned RC 0 at 2026-07-28 06:59 UTC. It plans 15 HG003-only jobs: SR/LR preparation, five shard gVCFs, concat, hard-VCF materialization, CNVscope, LongReadSV, manifest, and package. The hard-VCF rule consumes the final five-shard gVCF; no independent gVCF caller or completed core task is planned. |
| RUN-003 | HIOMR-style RG live retry | COMPLETE | Exact command completed `15/15` with controller RC `0` at 2026-07-28 08:29 UTC. Final `sacct` evidence records command manifest `532`, hard-VCF `533`, and analytical package `534` as `COMPLETED 0:0`; `squeue` was empty at 10:14 UTC. The old job `492` failure and job `493` cancellation belong to the superseded pre-fix attempt, not this successful retry. The rendered LR command contains `-R '@RG\\tID:HG003-t95ar0arttm7d0-lr\\tSM:HG003-t95ar0arttm7d0\\tLB:M-BNQ-11F\\tPL:ONT\\tLR:1'`, the same escaped-tab CLI representation used by HIOMR. |
| DIAG-001 | HIOMR2 kitchen-sink QC coverage | EXPOSED | The active target's declared inputs are only the final five-shard gVCF, CNVscope, LongReadSV, hard VCF, and command manifest. Its source explicitly excludes VEP, MultiQC, mitochondrial, specialty, and delivery targets. Accordingly, the RC-0 15-job plan contains no AlignStats, idxstats, VEP, relatedness, peddy, contamination, ExpansionHunter, SMN, mitochondrial, metagenomics, or MultiQC jobs; they will not appear later in this controller. The HIOMR catalog kitchen-sink command does request the comparable QC/output surface. |
| EVID-001 | Native LongReadSV call content | COMPLETE | At 2026-07-28 07:31 UTC, the completed `HG003-t95ar0arttm7d0.sentdhiomr2.longreadsv.summary.json` reports `native: true`, `fallback_used: false`, and `variant_records: 29913`. Direct decompression of the indexed VCF showed populated `SVTYPE=INS` call records with genotypes (for example chr1:90393, chr1:136934, chr1:180108); this is not an empty or header-only VCF. |
| EVID-002 | SR scratch versus FSx contract | COMPLETE | At 2026-07-28 07:37 UTC, active job `494` had only its scratch-claim metadata and 1.94 MB live tool log outside `work/tmp`; `work/tmp/job18668` occupied 64 GB of active Sentieon sort data. The FSx `align/sentdhiomr2/sr/` directory contains no final files yet. The rule retains the local aligned BAM/index, LocusCollector score, deduplicated CRAM/index/metrics, header-validation file, done marker, provenance fragment, and tool temporaries in scratch until validation. It then publishes only the final CRAM/index/metrics/done marker and immutable provenance fragment to FSx; the cleanup trap publishes the tool log and removes the claimed scratch root. |
| EVID-003 | Live log and benchmark observability | EXPOSED | At 2026-07-28 07:38 UTC, the active SR tool log exists only on compute-node scratch and is not yet visible under the declared FSx log path; it is copied only by the task cleanup trap. The declared Snakemake benchmark target is the FSx path `results/day/hg38/HG003-t95ar0arttm7d0/benchmarks/HG003-t95ar0arttm7d0.sentdhiomr2.sr-prepare.bench.tsv`; it exists neither in the active scratch tree nor on FSx while the job is running. Completed-rule benchmark files are on FSx, so the SR benchmark will be emitted there only when the rule exits. |
| EVID-004 | Final SR/LR CRAM read-group proof | COMPLETE | At 2026-07-28 08:19 UTC, direct `samtools 1.24 view -H` of the published CRAMs showed exactly one `@RG` each: SR `ID:HG003-t95ar0arttm7d0-sr SM:HG003-t95ar0arttm7d0 LB:M-BNQ-CJ PL:ILLUMINA`; LR `ID:HG003-t95ar0arttm7d0-lr SM:HG003-t95ar0arttm7d0 LB:M-BNQ-11F PL:ONT LR:1`. Both CRAMs pass `samtools quickcheck`; sampled alignment records carry the matching `RG:Z` tag. The LB values match the staged HG003 SR/LR library EUIDs. |
| VERIFY-001 | Terminal artifacts and identity contract | PENDING | Verify controller RC 0, five retained shard gVCF/index pairs, merged gVCF, hard VCF/index, AU-only headers, and package manifest roles. |

## Notes

- The first correction was shell initialization order. The second, pending source
  repair is restricted to the HIOMR2 aligner `-R` representation; it does not
  change the caller, shard, concat, header-validation, or reheader contracts.
- `RnD` requires `--skip-project-check` because the older local budget-tag file
  does not list it, while the current DYEC registry authorizes `ubuntu`.
- The active follow-up monitor is the 45-minute thread heartbeat
  `hiomr2-hg003-five-shard-rg-fix-monitor`; its scope is read-only status and
  ledger evidence unless the explicit spot-loss recovery contract is met.

## Monitor updates

- 2026-07-28 07:59 UTC: Read-only DYEC/ubuntu snapshot confirmed the persistent
  controller and wrapped DayOA process remain alive. Current RnD job `494`
  (`sentdhiomr2_sr_prepare`) is `RUNNING` on
  `i128nvme-dy-price128nvme-2` (128 CPUs); the node is allocated, with no
  reported `DOWN`, `DRAIN`, or spot-loss state. `sacct` separately records the
  corrected LR-preparation job `495` and LongReadSV job `496` as completed
  `0:0`; prior jobs `492`/`493` belong to the superseded pre-RG-fix attempt.
  The tmux pane last reported `2 of 15 steps (13%) done`. No restart or Slurm
  intervention was warranted.

- 2026-07-28 10:14 UTC: Read-only DYEC/ubuntu interactive-shell monitor recorded
  a read visit for the analysis root. The persistent tmux controller reports
  `15 of 15 steps (100%) done`, `WORKFLOW SUCCESS`, and `RETURN CODE: 0`, then
  released its write lock. `dyec cluster-info` reports `preval-hiomr2`
  `UPDATE_COMPLETE`; `squeue` was empty. `sacct` confirms the final
  command-manifest job `532`, hard-VCF job `533`, and analytical-package job
  `534` all completed `0:0` (09:45–09:49 UTC). No spot-node loss or controller
  failure was present; no restart or Slurm intervention was performed.

- 2026-07-28 11:02 UTC: Read-only follow-up from the existing DYEC Ubuntu
  interactive shell found the persistent tmux controller still present and
  idle at its completed terminal state: `15 of 15 steps (100%) done`,
  `WORKFLOW SUCCESS`, and controller `RETURN CODE: 0`. The current Slurm queue
  is empty; `sacct` records the terminal analytical-package job `512` as
  `COMPLETED 0:0` in 40 seconds (08:28:54–08:29:34 UTC). Local DYEC
  `cluster-info` reports `preval-hiomr2 UPDATE_COMPLETE`. The headnode's own
  `dyec cluster-info` wrapper could not list clusters, but that did not affect
  the controller or Slurm evidence. No spot-node loss or other failure was
  present, so no restart or Slurm intervention was performed.
