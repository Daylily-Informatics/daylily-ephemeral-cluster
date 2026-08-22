# DYEC 18.0.22 — pcand-18022 Bjuice-preval DRA and RunQC runbook

Created: 2026-08-17T07:17:08Z
Status: complete for the requested mounts, RunQC, three DYEC exports, and
authorized deletion of only the three exported FSx analysis roots.

Controlling ledger:
[`docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_ledger.md`](../../plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_ledger.md)

This is the task-owned runbook for the Bjuice-preval input mounts and the
three current catalog RunQC lanes on `pcand-18022`. It deliberately does not
modify the concurrent unrelated `runbooka.md`.

## Fixed scope and safety boundary

- DYEC: `18.0.22`; profile `lsmc`; region `us-west-2`; cluster
  `pcand-18022`; remote user `ubuntu`; project `pcand-18022`; cost center
  `pcand-18022-ccenter`.
- Every catalog render, dry controller, and live controller must use and
  explicitly pass DayOA tag `15.0.11`. A historical catalog validation tag is
  not a usable execution tag.
- All three mounts are read-only with metadata import and auto-import events
  `NEW,CHANGED`; no auto-export event is configured.
- Never run raw Snakemake, BCL Convert, ONT/Ultima basecalling, a direct Slurm
  action, DRA retry/replacement/detach, or an export without a separately
  approved exact destination prefix.
- Catalog launch owns the Ubuntu interactive tmux controller, DayOA setup,
  analysis visit/write lock, and `dy-r` invocation. This runbook never starts a
  manual headnode controller.

## Local setup and catalog pin

Run from an interactive local shell:

```zsh
cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate
dyec --help
```

Before every render, dry launch, and live launch, the command below must report
`"git_tag": "15.0.11"`; otherwise stop that lane.

```zsh
dyec --json catalog show <catalog-command-id>
```

The exact, task-owned run-context files are:

```text
docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/illumina_runs.tsv
docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/ont_runs.tsv
docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/ultima_runs.tsv
```

## Submitted read-only DRA mounts

The following three commands were submitted in parallel at
`2026-08-17T06:45:55Z`. A rejected local shell parse attempt preceded them and
did not invoke DYEC or create an association.

```zsh
dyec --json mounts create \
  s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/ \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --mount-id 20260618_LH01106_0011_A23MFMCLT3 \
  --run-id 20260618_LH01106_0011_A23MFMCLT3 \
  --platform ILMN \
  --purpose run \
  --read-only \
  --batch-import-metadata-on-create \
  --auto-import NEW,CHANGED \
  --no-wait

dyec --json mounts create \
  s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/ \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --mount-id pca100-2026 \
  --run-id pca100-2026 \
  --platform ONT \
  --purpose run \
  --read-only \
  --batch-import-metadata-on-create \
  --auto-import NEW,CHANGED \
  --no-wait

dyec --json mounts create \
  s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/RUN604834/2026/604834-20260717_2309/ \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --mount-id ultima-604834-20260717 \
  --run-id 604834-20260717_2309 \
  --platform ULTIMA \
  --purpose run \
  --read-only \
  --batch-import-metadata-on-create \
  --auto-import NEW,CHANGED \
  --no-wait
```

| Platform | Association ID | Mount ID | Source | Current evidence |
|---|---|---|---|---|
| ILMN | `dra-0cc3051c7e460429e` | `20260618_LH01106_0011_A23MFMCLT3` | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/` | `AVAILABLE`; verified usable at 2026-08-17T07:08:47Z. |
| ONT | `dra-0a739dd6aa2d433a0` | `pca100-2026` | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/` | `AVAILABLE` and verified usable at 2026-08-17T07:49:25Z. This single parent contains the reviewed 15 Bjuice ONT directories. |
| Ultima | `dra-080f12613e5deb4e8` | `ultima-604834-20260717` | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/RUN604834/2026/604834-20260717_2309/` | `AVAILABLE` and verified usable at 2026-08-17T07:31:15Z. |

Monitor only the three association IDs; `CREATING` is expected for at least 40
minutes. Do not retry, create a duplicate, replace, detach, delete, copy, or
time out an association during that interval.

```zsh
dyec --json mounts list \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022

dyec --json mounts verify \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --association-id dra-0cc3051c7e460429e
```

The ILMN verification returned command ID `ecc8eb22-db83-4d57-a9bf-fae0451e9734`,
`verified: true`, `usable: true`, and exact headnode path:

```text
/fsx/run_dir_mounts/20260618_LH01106_0011_A23MFMCLT3
```

When the other associations are `AVAILABLE`, verify each exact association once:

```zsh
dyec --json mounts verify \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --association-id dra-0a739dd6aa2d433a0

dyec --json mounts verify \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --association-id dra-080f12613e5deb4e8
```

On a verification failure or terminal DRA failure, record the exact response,
notify the user, and stop that lane without remediation.

## Illumina RunQC: executed path

The catalog entry describes `illumina_run_qc` as run-folder QC without BCL
Convert. Every catalog check reported `git_tag: 15.0.11`.

```zsh
dyec --json catalog show illumina_run_qc

dyec --json catalog render illumina_run_qc \
  --analysis-id pcand18022_ilmn_seq_qc_15011_dry_20260817T0709Z \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --remote-user ubuntu \
  --project pcand-18022 \
  --cost-center pcand-18022-ccenter \
  --strict-project-check \
  --git-tag 15.0.11 \
  --run-context-file docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/illumina_runs.tsv \
  --dry-run

dyec --json catalog show illumina_run_qc

dyec --json catalog launch illumina_run_qc \
  --analysis-id pcand18022_ilmn_seq_qc_15011_dry_20260817T0709Z \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --remote-user ubuntu \
  --project pcand-18022 \
  --cost-center pcand-18022-ccenter \
  --strict-project-check \
  --git-tag 15.0.11 \
  --run-context-file docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/illumina_runs.tsv \
  --dry-run

dyec --json workflow status \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --session pcand18022_ilmn_seq_qc_15011_dry_20260817T0709Z \
  --remote-user ubuntu \
  --receipt-wait-seconds 30
```

The dry controller terminal status was `SUCCEEDED`, attributable `exit_code: 0`,
zero submitted Slurm jobs, zero finished jobs, and no failure markers. Only then
was the distinct live controller rendered and launched:

```zsh
dyec --json catalog show illumina_run_qc

dyec --json catalog render illumina_run_qc \
  --analysis-id pcand18022_ilmn_seq_qc_15011_live_20260817T0712Z \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --remote-user ubuntu \
  --project pcand-18022 \
  --cost-center pcand-18022-ccenter \
  --strict-project-check \
  --git-tag 15.0.11 \
  --run-context-file docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/illumina_runs.tsv

dyec --json catalog show illumina_run_qc

dyec --json catalog launch illumina_run_qc \
  --analysis-id pcand18022_ilmn_seq_qc_15011_live_20260817T0712Z \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --remote-user ubuntu \
  --project pcand-18022 \
  --cost-center pcand-18022-ccenter \
  --strict-project-check \
  --git-tag 15.0.11 \
  --run-context-file docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/illumina_runs.tsv

dyec --json workflow status \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --session pcand18022_ilmn_seq_qc_15011_live_20260817T0712Z \
  --remote-user ubuntu \
  --receipt-wait-seconds 30

dyec workflow logs \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --session pcand18022_ilmn_seq_qc_15011_live_20260817T0712Z \
  --remote-user ubuntu \
  --stream controller \
  --lines 200
```

Initial live status: session is tmux-correlated and attributable, controller
PID `103156`, state `RUNNING`, no submitted Slurm jobs yet, and no terminal
failure marker. Continue monitoring only with `dyec --json workflow status` and
plain `dyec workflow logs` (the logs command does not support JSON mode).

At 2026-08-17T07:19:36Z, the live controller remains attributable and
tmux-correlated with zero submitted/finished Slurm jobs, no attributable
terminal exit code, and no failure markers. The ILMN mount remains `AVAILABLE`;
the ONT and Ultima mounts remain `CREATING`.

At 2026-08-17T07:22:17Z, a repeat status check still reports the controller
live and attributable but has no exact attributable Snakemake log, progress
line, or Slurm submission. A controller-log tail returned no content. Treat
this as a nonterminal controller-startup observation only: do not retry,
restart, cancel, or otherwise intervene.

At 2026-08-17T07:25:31Z, the state is unchanged: ILMN is `AVAILABLE`; ONT and
Ultima are `CREATING`; and the live ILMN controller remains attributable and
`RUNNING` with zero submitted/finished jobs, no progress/Snakemake log, no
terminal exit, and no failure marker. A fresh controller-log tail again had no
content, so the monitor made no intervention.

At 2026-08-17T07:30:52Z, the ILMN controller progressed to one submitted
workflow job: DYEC job `3` / Slurm job `6`, named
`illumina_run_qc_fetch_metric_subset-20260618_LH01106_0011_A23MFMCLT3`, in
`CONFIGURING` for `i192nvme-dy-bigmem192nvme-1`. It has an attributable
Snakemake log at `.snakemake/log/2026-08-17T072916.336921.snakemake.log`.
This is scheduler lifecycle evidence only; no Slurm intervention was made.

## Ultima RunQC: executed path

The Ultima association became `AVAILABLE` at 2026-08-17T07:30:52Z and was
verified at 2026-08-17T07:31:15Z. Verification command
`3da5b363-fb3a-4030-9feb-39e9eec9ffe6` returned `verified: true` and
`usable: true` for `/fsx/run_dir_mounts/ultima-604834-20260717`.

`ultima_run_qc` was checked before every render and launch and reported
`git_tag: 15.0.11`; the catalog commands are only
`produce_ultima_run_qc`, with no basecalling.

```zsh
dyec --json catalog show ultima_run_qc

dyec --json catalog render ultima_run_qc \
  --analysis-id pcand18022_ultima_seq_qc_15011_dry_20260817T0732Z \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --remote-user ubuntu \
  --project pcand-18022 \
  --cost-center pcand-18022-ccenter \
  --strict-project-check \
  --git-tag 15.0.11 \
  --run-context-file docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/ultima_runs.tsv \
  --dry-run

dyec --json catalog show ultima_run_qc

dyec --json catalog launch ultima_run_qc \
  --analysis-id pcand18022_ultima_seq_qc_15011_dry_20260817T0732Z \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --remote-user ubuntu \
  --project pcand-18022 \
  --cost-center pcand-18022-ccenter \
  --strict-project-check \
  --git-tag 15.0.11 \
  --run-context-file docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/ultima_runs.tsv \
  --dry-run

dyec --json workflow status \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --session pcand18022_ultima_seq_qc_15011_dry_20260817T0732Z \
  --remote-user ubuntu \
  --receipt-wait-seconds 30
```

The dry controller terminal receipt was attributable `SUCCEEDED`, `rc=0`, zero
submitted Slurm jobs, and no failure markers; its exact Snakemake log is
`.snakemake/log/2026-08-17T073338.077183.snakemake.log`. The distinct live
controller was then rendered and launched:

```zsh
dyec --json catalog show ultima_run_qc

dyec --json catalog render ultima_run_qc \
  --analysis-id pcand18022_ultima_seq_qc_15011_live_20260817T0734Z \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --remote-user ubuntu \
  --project pcand-18022 \
  --cost-center pcand-18022-ccenter \
  --strict-project-check \
  --git-tag 15.0.11 \
  --run-context-file docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/ultima_runs.tsv

dyec --json catalog show ultima_run_qc

dyec --json catalog launch ultima_run_qc \
  --analysis-id pcand18022_ultima_seq_qc_15011_live_20260817T0734Z \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --remote-user ubuntu \
  --project pcand-18022 \
  --cost-center pcand-18022-ccenter \
  --strict-project-check \
  --git-tag 15.0.11 \
  --run-context-file docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/ultima_runs.tsv

dyec --json workflow status \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --session pcand18022_ultima_seq_qc_15011_live_20260817T0734Z \
  --remote-user ubuntu \
  --receipt-wait-seconds 30
```

At 2026-08-17T07:35:40Z, the first live status has a tmux controller PID
`159673` but no attributable workflow receipt, submitted job, Snakemake log,
or terminal failure. Continue status/log monitoring only; do not intervene.

At 2026-08-17T07:37:57Z, ILMN live
`pcand18022_ilmn_seq_qc_15011_live_20260817T0712Z` has terminal attributable
`rc=0` with no failure marker; its temporary Slurm job `6` is no longer live.
Ultima live is now attributable and tmux-correlated (`PID 159673`) with active
Snakemake log `.snakemake/log/2026-08-17T073606.697766.snakemake.log`, but it
has zero submitted jobs and remains `RUNNING`. The 15-minute monitor cadence
is not eligible until all three live catalog lanes have each submitted a job.

At 2026-08-17T07:39:32Z, ONT remains `CREATING`. Ultima live remains
attributable and `RUNNING` with zero submitted/finished jobs, no progress or
terminal failure, and the same active Snakemake log. Its controller-log tail
had no content; no intervention or cadence change was made.

## ONT RunQC: executed path

At 2026-08-17T07:49:25Z, the ONT parent was verified usable at
`/fsx/run_dir_mounts/pca100-2026` by command
`c6118e13-5d9a-4e2f-aacd-faf570bc085e`. The full Bjuice ILMN + ONT input pair
is ready for the user to queue prevalence test runs; no manifest or Bjuice run
was created here. The current `ont_run_qc` catalog entry reported
`git_tag: 15.0.11` before every render and launch. Its target is
`produce_ont_run_qc_and_demux_multiqc`, with no basecalling and only the
explicit `20260615_ONT_Set4-FC1` context TSV.

```zsh
dyec --json catalog show ont_run_qc

dyec --json catalog render ont_run_qc \
  --analysis-id pcand18022_ont_seq_qc_15011_dry_20260817T0750Z \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --remote-user ubuntu \
  --project pcand-18022 \
  --cost-center pcand-18022-ccenter \
  --strict-project-check \
  --git-tag 15.0.11 \
  --run-context-file docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/ont_runs.tsv \
  --dry-run

dyec --json catalog show ont_run_qc

dyec --json catalog launch ont_run_qc \
  --analysis-id pcand18022_ont_seq_qc_15011_dry_20260817T0750Z \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --remote-user ubuntu \
  --project pcand-18022 \
  --cost-center pcand-18022-ccenter \
  --strict-project-check \
  --git-tag 15.0.11 \
  --run-context-file docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/ont_runs.tsv \
  --dry-run

dyec --json workflow status \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --session pcand18022_ont_seq_qc_15011_dry_20260817T0750Z \
  --remote-user ubuntu \
  --receipt-wait-seconds 30
```

The dry controller terminal receipt was attributable `SUCCEEDED`, `rc=0`, zero
submitted jobs, and no failure markers. Its exact Snakemake log is
`.snakemake/log/2026-08-17T075147.035108.snakemake.log`. The distinct live
controller was then rendered and launched:

```zsh
dyec --json catalog show ont_run_qc

dyec --json catalog render ont_run_qc \
  --analysis-id pcand18022_ont_seq_qc_15011_live_20260817T0752Z \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --remote-user ubuntu \
  --project pcand-18022 \
  --cost-center pcand-18022-ccenter \
  --strict-project-check \
  --git-tag 15.0.11 \
  --run-context-file docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/ont_runs.tsv

dyec --json catalog show ont_run_qc

dyec --json catalog launch ont_run_qc \
  --analysis-id pcand18022_ont_seq_qc_15011_live_20260817T0752Z \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --remote-user ubuntu \
  --project pcand-18022 \
  --cost-center pcand-18022-ccenter \
  --strict-project-check \
  --git-tag 15.0.11 \
  --run-context-file docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/ont_runs.tsv

dyec --json workflow status \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --session pcand18022_ont_seq_qc_15011_live_20260817T0752Z \
  --remote-user ubuntu \
  --receipt-wait-seconds 30
```

At 2026-08-17T07:54:18Z, the ONT live controller is attributable and
tmux-correlated (`PID 230907`), `RUNNING`, with zero submitted jobs and no
terminal failure. Ultima live has terminal attributable `rc=0` with no failure
marker. The approved 15-minute cadence is not eligible yet: ILMN submitted a
job, but Ultima completed without a submission and ONT has not submitted one.

At 2026-08-17T07:58:33Z, all three mounts remain `AVAILABLE`. ONT live remains
attributable and `RUNNING` with zero submitted/finished jobs, no terminal
failure, and open Snakemake log `.snakemake/log/2026-08-17T075421.171162.snakemake.log`.
Its controller-log tail had no content; no intervention or cadence change was
made.

At 2026-08-17T08:08:33Z, ONT live has 8 submitted jobs, 7 finished, and one
running Slurm job: external `171` / DYEC job `8`,
`ont_demux_fastq_qc-20260615_ONT_Set4-FC1`, on
`i192nvme-dy-bigmem192nvme-3`. Its attributable progress is `7 of 10 steps
(70%) done` at 2026-08-17T08:07:29Z with no terminal failure marker.

At 2026-08-17T08:10:40Z, the user's authorized cadence change was applied to
the existing and only heartbeat: its interval is now 15 minutes. ILMN had
submitted Slurm work and is terminal `rc=0`; Ultima is terminal `rc=0` without
a Slurm job; ONT has active submitted work. No second scheduled task was
created.

At 2026-08-17T08:22:27Z, ONT live remains `RUNNING`: 8 submitted jobs, 7
finished, and one active Slurm job `171`,
`ont_demux_fastq_qc-20260615_ONT_Set4-FC1`, on
`i192nvme-dy-bigmem192nvme-3`. It remains at 70% with no terminal failure. The
attributable Snakemake tail records its last progress at 08:07:29Z after the
MultiQC job completed and identifies job `171` as the remaining demultiplexed
FASTQ QC work. No intervention was taken.

At 2026-08-17T08:25:32Z, the same state persists: ONT live has one remaining
active job `171`, no terminal failure, and no log progress after the 08:07:29Z
70% event. The status read used `--receipt-wait-seconds 0` because the
controller receipt already exists. No workflow action was taken.

At 2026-08-17T08:37:18Z, the final ONT status check was:

```zsh
source ./activate
dyec --json workflow status \
  --profile lsmc --region us-west-2 --cluster pcand-18022 \
  --remote-user ubuntu \
  --session pcand18022_ont_seq_qc_15011_live_20260817T0752Z \
  --receipt-wait-seconds 0
```

It returned terminal `SUCCEEDED`, attributable `exit_code: 0` from the launch
receipt, and no failure markers. This is the terminal result after the earlier
eight submitted ONT Slurm jobs, including `ont_demux_fastq_qc` external job
`171`; no direct Slurm action was taken. ILMN and Ultima remain terminal
attributable `rc=0`, so the task's one heartbeat was deleted. The Bjuice
prevalence tests and any result export remain intentionally unqueued pending
separate user authorization and an exact export destination, respectively.

## ONT and Ultima RunQC: gated command form

Run an ONT or Ultima command only after the matching DRA is both `AVAILABLE`
and verified. Use a new unique dry analysis ID and, only after an attributable
dry `rc=0` with zero Slurm submissions, a different new unique live analysis
ID. Replace each angle-bracketed required value before executing; do not reuse
the displayed ILMN IDs.

```zsh
# ONT, explicitly limited to 20260615_ONT_Set4-FC1; no basecalling.
dyec --json catalog show ont_run_qc
dyec --json catalog render ont_run_qc \
  --analysis-id <new-unique-ont-dry-analysis-id> \
  --profile lsmc --region us-west-2 --cluster pcand-18022 \
  --remote-user ubuntu --project pcand-18022 \
  --cost-center pcand-18022-ccenter --strict-project-check \
  --git-tag 15.0.11 \
  --run-context-file docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/ont_runs.tsv \
  --dry-run
dyec --json catalog show ont_run_qc
dyec --json catalog launch ont_run_qc \
  --analysis-id <new-unique-ont-dry-analysis-id> \
  --profile lsmc --region us-west-2 --cluster pcand-18022 \
  --remote-user ubuntu --project pcand-18022 \
  --cost-center pcand-18022-ccenter --strict-project-check \
  --git-tag 15.0.11 \
  --run-context-file docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/ont_runs.tsv \
  --dry-run
dyec --json workflow status \
  --profile lsmc --region us-west-2 --cluster pcand-18022 \
  --session <new-unique-ont-dry-analysis-id> --remote-user ubuntu

# Launch only after the preceding status reports attributable terminal rc=0
# and zero submitted Slurm jobs.
dyec --json catalog show ont_run_qc
dyec --json catalog render ont_run_qc \
  --analysis-id <new-unique-ont-live-analysis-id> \
  --profile lsmc --region us-west-2 --cluster pcand-18022 \
  --remote-user ubuntu --project pcand-18022 \
  --cost-center pcand-18022-ccenter --strict-project-check \
  --git-tag 15.0.11 \
  --run-context-file docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/ont_runs.tsv
dyec --json catalog show ont_run_qc
dyec --json catalog launch ont_run_qc \
  --analysis-id <new-unique-ont-live-analysis-id> \
  --profile lsmc --region us-west-2 --cluster pcand-18022 \
  --remote-user ubuntu --project pcand-18022 \
  --cost-center pcand-18022-ccenter --strict-project-check \
  --git-tag 15.0.11 \
  --run-context-file docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/ont_runs.tsv

# Ultima; no basecalling.
dyec --json catalog show ultima_run_qc
dyec --json catalog render ultima_run_qc \
  --analysis-id <new-unique-ultima-dry-analysis-id> \
  --profile lsmc --region us-west-2 --cluster pcand-18022 \
  --remote-user ubuntu --project pcand-18022 \
  --cost-center pcand-18022-ccenter --strict-project-check \
  --git-tag 15.0.11 \
  --run-context-file docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/ultima_runs.tsv \
  --dry-run
dyec --json catalog show ultima_run_qc
dyec --json catalog launch ultima_run_qc \
  --analysis-id <new-unique-ultima-dry-analysis-id> \
  --profile lsmc --region us-west-2 --cluster pcand-18022 \
  --remote-user ubuntu --project pcand-18022 \
  --cost-center pcand-18022-ccenter --strict-project-check \
  --git-tag 15.0.11 \
  --run-context-file docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/ultima_runs.tsv \
  --dry-run
dyec --json workflow status \
  --profile lsmc --region us-west-2 --cluster pcand-18022 \
  --session <new-unique-ultima-dry-analysis-id> --remote-user ubuntu

# Launch only after the preceding status reports attributable terminal rc=0
# and zero submitted Slurm jobs.
dyec --json catalog show ultima_run_qc
dyec --json catalog render ultima_run_qc \
  --analysis-id <new-unique-ultima-live-analysis-id> \
  --profile lsmc --region us-west-2 --cluster pcand-18022 \
  --remote-user ubuntu --project pcand-18022 \
  --cost-center pcand-18022-ccenter --strict-project-check \
  --git-tag 15.0.11 \
  --run-context-file docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/ultima_runs.tsv
dyec --json catalog show ultima_run_qc
dyec --json catalog launch ultima_run_qc \
  --analysis-id <new-unique-ultima-live-analysis-id> \
  --profile lsmc --region us-west-2 --cluster pcand-18022 \
  --remote-user ubuntu --project pcand-18022 \
  --cost-center pcand-18022-ccenter --strict-project-check \
  --git-tag 15.0.11 \
  --run-context-file docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/ultima_runs.tsv
```

Monitor a launched live controller with its exact live analysis ID:

```zsh
dyec --json workflow status \
  --profile lsmc --region us-west-2 --cluster pcand-18022 \
  --session <live-analysis-id> --remote-user ubuntu

dyec workflow logs \
  --profile lsmc --region us-west-2 --cluster pcand-18022 \
  --session <live-analysis-id> --remote-user ubuntu \
  --stream controller --lines 200
```

Any attributable nonzero terminal exit code is a fail-closed blocker: record
the status and logs, notify the user, and do not retry or intervene.

## Bjuice handoff gate

When the ILMN association and ONT-parent association are both `AVAILABLE` and
verified, notify the user that the Bjuice full-coverage ILMN + ONT input pair
is ready for prevalence test-run queueing. Do not generate manifests or launch
the Bjuice command in this task.

## Default no-delete result-export protocol

This was the safe default before the user supplied exact output prefixes and a
separate explicit deletion confirmation. It remains the default for future
work: after a controller has terminal `rc=0`, an exact approved *empty*
destination prefix and exact result analysis root are required. Do not
substitute a guessed bucket or prefix, do not use `aws s3 cp`/`sync`, and do
not delete FSx data without a separate explicit approval.

Use the supported no-delete DYEC export protocol below from the supported
execution context. Preserve the analysis root and receipt until the DRA task is
`SUCCEEDED`, detached, and the expected result objects are verified at the exact
approved prefix.

```zsh
# Required values; do not execute with placeholders.
ANALYSIS_ROOT=<exact-completed-analysis-root>
DESTINATION_S3_URI=<exact-approved-empty-s3-prefix>
EXPORT_RECEIPT_DIR=<exact-receipt-directory-outside-an-active-dra>

dyec analysis visit \
  --analysis-root "$ANALYSIS_ROOT" \
  --mode export \
  --intent "export completed pipeline results to $DESTINATION_S3_URI without FSx cleanup" \
  --s3-visit-uri "$DESTINATION_S3_URI"

dyec export \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --source-path "$ANALYSIS_ROOT" \
  --destination-s3-uri "$DESTINATION_S3_URI" \
  --output-dir "$EXPORT_RECEIPT_DIR" \
  --wait \
  --timeout-seconds 5400
```

## Task-owned documentation commit and push

After validating the current task-owned files, stage only these paths; do not
stage the unrelated runbook or other pre-existing worktree changes.

```zsh
git add -- \
  config/daylily_pipeline_command_catalog.yaml \
  daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml \
  tests/test_repository_catalog.py \
  tests/test_repository_catalog_aliases.py \
  tests/test_ont_runqc_17_0_28_release.py \
  docs/runbooks/18.0.22/runbooka1.md \
  docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_ledger.md \
  docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/illumina_runs.tsv \
  docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/ont_runs.tsv \
  docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/ultima_runs.tsv \
  docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/exports/
git diff --cached --check
git diff --cached
git commit -m "Record pcand-18022 RunQC exports and catalog evidence"
git push origin HEAD
```

## 2026-08-17: approved three-root DRA export and FSx cleanup

The user supplied the three exact output prefixes and then separately confirmed
that only the three corresponding FSx analysis roots may be deleted after their
individual DYEC exports succeed. The original source run mounts are outside
this cleanup scope.

The pre-cleanup `dyec analysis visit` / delete-lock work was run through the
supported `dyec headnode run` path as remote user `ubuntu`; the local Mac does
not mount `/fsx`, so its initial local visit check failed without making any
remote mutation. Each exported root had an export visit and a clean delete lock
before the export. No raw S3 copy, raw filesystem deletion, or direct DRA
detach was used.

The exact export commands were:

```zsh
dyec export \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --source-path /analysis_results/pcand-18022/pcand18022_ilmn_seq_qc_15011_live_20260817T0712Z/ \
  --destination-s3-uri s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022_ilmn_seq_qc_15011_live_20260817T0712Z/ \
  --output-dir docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/exports/illumina \
  --delete-data-in-file-system \
  --wait \
  --timeout-seconds 5400

dyec export \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --source-path /analysis_results/pcand-18022/pcand18022_ont_seq_qc_15011_live_20260817T0752Z/ \
  --destination-s3-uri s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022_ont_seq_qc_15011_live_20260817T0752Z/ \
  --output-dir docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/exports/ont \
  --delete-data-in-file-system \
  --wait \
  --timeout-seconds 5400

dyec export \
  --profile lsmc \
  --region us-west-2 \
  --cluster pcand-18022 \
  --source-path /analysis_results/pcand-18022/pcand18022_ultima_seq_qc_15011_live_20260817T0734Z/ \
  --destination-s3-uri s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022_ultima_seq_qc_15011_live_20260817T0734Z/ \
  --output-dir docs/plans/20260817T064326Z_pcand18022_bjuice_preval_three_platform_seq_qc_contexts/exports/ultima \
  --delete-data-in-file-system \
  --wait \
  --timeout-seconds 5400
```

| Lane | Analysis root deleted after export | Export S3 root | Receipt / terminal DYEC evidence |
|---|---|---|---|
| ILMN | `/fsx/analysis_results/pcand-18022/pcand18022_ilmn_seq_qc_15011_live_20260817T0712Z/` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022_ilmn_seq_qc_15011_live_20260817T0712Z/` | `exports/illumina/fsx_export.yaml`; `dra-0eccda2383d501558`; `task-04314e6ad167c3da3` `SUCCEEDED`; `phase: complete`; detached and deletion enabled. |
| ONT | `/fsx/analysis_results/pcand-18022/pcand18022_ont_seq_qc_15011_live_20260817T0752Z/` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022_ont_seq_qc_15011_live_20260817T0752Z/` | `exports/ont/fsx_export.yaml`; `dra-07a7629ad6d148601`; `task-0ab635bdaf6de0351` `SUCCEEDED`; `phase: complete`; detached and deletion enabled. |
| Ultima | `/fsx/analysis_results/pcand-18022/pcand18022_ultima_seq_qc_15011_live_20260817T0734Z/` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022_ultima_seq_qc_15011_live_20260817T0734Z/` | `exports/ultima/fsx_export.yaml`; `dra-0392265fb9f0f8aa9`; `task-0764f6ed0d480690c` `SUCCEEDED`; `phase: complete`; detached and deletion enabled. |

DYEC postchecks confirmed all three listed FSx analysis roots are absent. The
temporary export associations no longer appear in `dyec --json mounts list`.
The original Ultima source mount `dra-080f12613e5deb4e8` is also absent, but the
user states that it was unmounted in a separate thread; this task did not
recreate, detach, or otherwise modify that source association.

The active `illumina_run_qc`, `ont_run_qc`, and `ultima_run_qc` catalog records
now point to the respective exported result-report prefixes and include the
DayOA `15.0.11` dry/live evidence. The active command definitions remain pinned
to `git_tag: 15.0.12` with `validated_version: 15.0.9`; these records do not
claim a new `15.0.12` validation.
