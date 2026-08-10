# JEM HG003/004 HIOMR2 Take 4 — Execution Ledger

Controlling request: prepare and launch the HIOMR2 kitchen-sink Inflection
package for full ILMN plus ONT `[0,25)` Bjuice prevalence HG003/HG004 data,
using DYEC `15.0.12`, DayOA `13.0.59`, analysis ID
`jem-hg003-4-hiomr2-take4`, and a five-group chromosome scope.

## Gate 0 — Baseline

- Local DYEC checkout was fast-forwarded from `3bc467e5` to `07a9a2fb`, the
  annotated `15.0.12` tag. `dyec version` reports `Daylily Ephemeral Cluster
  15.0.12`.
- Nine untracked files that blocked the update were preserved under
  `bkup/20260727T092100Z_pre_main_pull_untracked/` before their original paths
  were cleared for the fast-forward. Other pre-existing untracked artifacts
  remain untouched.
- Profile/cluster are explicitly `lsmc` / `preval-hiomr2` in `us-west-2`.
  It is the only discovered cluster not named `ursa*`; its headnode is running
  and its compute fleet is `RUNNING`.
- `dyec headnode run ... "dyec version"` reports `15.0.12` remotely.
- Read-only controller inventory at `2026-07-27T09:23Z` found no receipted
  live DayOA controller, and one unrelated running Slurm job (`103`). No
  controller, queue, or job action was taken.

## Requested command contract

- Catalog entry `inflection-bjuice-product-v0.2` is the literal compatible
  command: HIOMR2 kitchen sink plus analytical Inflection package, full ILMN,
  ONT `[0,25)`, Bjuice, `hg38_broad`, `-j 200 -p -k -T 0`, and mtime-based
  rerun handling. It requires a generated six-manifest input contract for
  both HG003 and HG004.

## Blocking evidence

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| B-001 | Requested `config/hiomr2_hg003_again_full_chrom_shards.yaml` at DayOA `13.0.59` | SOURCE RECOVERED | The source overlay is recovered from the named headnode analysis and will be copied only into the requested new checkout; it is not substituted from a different tagged source tree. |
| B-002 | Requested `../HG003_HIOMR2_AGAIN_NOTE.md` at DayOA `13.0.59` | SOURCE RECOVERED | The corresponding headnode note is recovered and records the source analysis as staged only. |
| B-003 | Headnode authenticated DayOA clone preflight | SUCCESS | In the required interactive `ubuntu` tmux shell, `day-clone --check-auth --repository daylily-omics-analysis --git-tag 13.0.59` succeeded. The earlier noninteractive SSM probe is not clone-auth evidence. |

## Recovered source evidence — 2026-07-27T09:29Z

- The exact requested files were found on `preval-hiomr2`:
  - `/fsx/analysis_results/preval-hiomr2/hg003-hiomr2-again/HG003_HIOMR2_AGAIN_NOTE.md`
  - `/fsx/analysis_results/preval-hiomr2/hg003-hiomr2-again/daylily-omics-analysis/config/hiomr2_hg003_again_full_chrom_shards.yaml`
- They were created at `2026-07-27T03:42:10Z`. Their containing checkout is
  `main` at `046d565f` (`13.0.52-11-g046d565f`) and has the config as an
  untracked file; it is not a source file in DayOA `13.0.59`.
- The overlay declares HG003-only full-chromosome shards `1-3`, `4-8`, `9-15`,
  `16-20`, and `21-25`, the latter representing chromosomes 21, 22, X, Y, and
  MT. It does not provide the separately required HG004 input overlay or the
  owner-issued analytical package batch.
- A remote `dyec analysis visit --mode read` receipt was recorded before this
  source root was used. The new overlay will keep five ordered shards but make
  the chromosome tokens explicit: `1,2,3`; `4,5,6,7,8`; `9,10,11,12,13,14,15`;
  `16,17,18,19,20`; and `21,22,23,24,25`, with tokens 23-25 resolving from the
  actual reference FAI to X, Y, and MT/M.

## Remaining required inputs

- This recovered overlay is HG003-only. Do not infer HG004 FASTQ/manifest
  inputs from an unfamiliar staging tree; the exact reviewed six-manifest
  contract (or the explicit generator input set) for HG003 and HG004 is still
  required.
- The analytical package command requires an owner-issued persisted
  `seqone_delivery_batch_id`. The prior run's value is not reused for this new
  analysis without explicit instruction.

## Setup receipt — 2026-07-27T09:39Z

- A single-window, single-pane persistent tmux session,
  `jem_hg003_4_hiomr2_take4_20260727`, cloned DayOA `13.0.59` into
  `/fsx/analysis_results/preval-hiomr2/jem-hg003-4-hiomr2-take4/daylily-omics-analysis`.
- The recovered HG003 full-chromosome overlay was copied into that clone as
  `config/hiomr2_hg003_again_full_chrom_shards.yaml`. Its ordered five ranges
  cover every numeric scope token 1 through 25; DayOA maps tokens 23, 24, and
  25 to X, Y, and the single FAI-resolved mitochondrial spelling.
- The target root received a write visit and a write lock for the config copy;
  the lock was released once the copy completed. `source dyoainit` and
  `dy-a slurm hg38_broad` both completed in the persistent tmux pane.
- No `dy-r` dry run or live workflow has been submitted. This remains blocked
  on the exact reviewed HG003/HG004 six-manifest contract and a new owner-issued
  `seqone_delivery_batch_id`.

## Two-sample manifest receipt — 2026-07-27T09:50Z

- The supported `dyec catalog config-bjuice-preval` generator created a fresh
  full-coverage HG003/HG004 six-manifest contract under
  `docs/plans/20260727T095000Z_jem_hg003_4_hiomr2_take4_manifests/` from the
  checksum-matched reviewed Bjuice source bundle.
- The generator returned `ok: true` for two specimens, two samples, four
  libraries, eight sequencing inputs, two analysis units, and eight
  analysis-unit joins. It retains the persisted specimen/sample/library/run
  values from the reviewed source; no identities were generated.
- The remaining pre-launch blocker is only a new owner-issued persisted
  `seqone_delivery_batch_id` for the analytical package. That identifier cannot
  be invented, treated as a TapDB/Meridian EUID, or reused from an earlier run
  without explicit owner instruction.

## Package batch and manifest-transfer attempt — 2026-07-27T09:57Z

- The owner issued `seqone_delivery_batch_id=this-time-go` for this analytical
  package. It will be passed verbatim as `SEQONE_DELIVERY_BATCH_ID` in the
  scoped DayOA controller; it is not represented as an EUID.
- The selected Dewey managed-storage relay was `s3://lsmc-dewey-0/dayec-transient/jem-hg003-4-hiomr2-take4/20260727T095700Z`.
  The first `dyec headnode upload` of `specimens.tsv` failed before copying any
  manifest to the analysis root because the headnode role received `403
  Forbidden` from S3 `HeadObject`.
- The target write lock was released after the failed transfer. No `dy-r` dry
  run or live workflow was submitted, and no alternate bucket was selected.

## Next authorized action

When the owner supplies the reviewed HG003/HG004 manifest contract and the new
analytical package batch, acquire the target write lock, run the literal catalog
dry run in the existing tmux controller, compare its planned reruns, and only
then run the identical non-dry-run command.

## Launch receipt — 2026-07-27T14:56Z

- The reviewed six-manifest files were transferred to the target clone's
  `config/` directory through the DYEC SSM helper. Their remote SHA-256 values
  match the local generator receipt. `seqone_delivery_batch_id=this-time-go` is
  supplied verbatim to the analytical package target.
- The original recovered config failed its first dry run because it lacked an
  explicit HG004 long-read input mode. One source-backed overlay correction
  added `HG004: fastq` and `HG004: female`, retaining the five explicit numeric
  chromosome scopes `1,2,3`, `4,5,6,7,8`, `9,10,11,12,13,14,15`,
  `16,17,18,19,20`, and `21,22,23,24,25`.
- The corrected `dy-r ... --rerun-triggers mtime -n` returned `RETURN CODE: 0`.
  It plans 30 jobs: two samples, five scoped GVCF shards per sample, and the
  requested kitchensink plus analytical package targets. The fresh root had no
  completed target outputs selected for rerun.
- The first live submission was stopped before any workflow job was accepted
  because the cluster-default cost-center record `preval-hiomr2` returned empty
  JSON. The owner directed use of the existing active `RnD` cost center. DYEC
  verified `RnD` as active, cap USD 500, authorized for `ubuntu`.
- With `DAY_PROJECT=RnD` and `DAYLILY_COST_CENTER=RnD`, DYEC sbatch enforcement
  accepted the workload. It submitted initial controller child job 139, then
  preparation jobs 140-143: HG003/HG004 short-read preparation and ONT FASTQ
  preparation. At the first post-launch snapshot all four were `CF` on
  `i128nvme` spot nodes. Unrelated job 103 was observed but not touched.
- A DYEC-headnode-only 45-minute heartbeat monitor is active in this task. It
  records controller/queue evidence here and may restart only after confirmed
  spot-node loss using the stated `mtime` dry-run gate. Other failures permit
  only one source-backed diagnostic/fix attempt before stopping.

## Monitor snapshot — 2026-07-27T16:15Z

- DYEC `cluster-info --profile lsmc --region us-west-2` reports
  `preval-hiomr2` as `UPDATE_COMPLETE`.
- The persistent controller tmux session is present and reports `12 of 30
  steps (40%) done`; it submitted scoped GVCF job 157 normally under `RnD`.
- `sacct` confirms initial jobs 139-143 all `COMPLETED`, exit `0:0`, with the
  expected RnD Slurm comment. Their elapsed times were 00:00:23 (preflight),
  00:59:07 and 01:03:06 (short-read preparation), and 00:22:53 and 00:13:21
  (ONT FASTQ preparation).
- Eight HIOMR2 scoped GVCF jobs (148-150, 152-153, 155-157) are currently
  `RUNNING` on distinct `i128nvme` spot nodes. No controller error, failed job,
  node loss, or spot interruption is present in this snapshot; no restart or
  Slurm intervention was performed. Unrelated job 103 remains untouched.

## Terminal monitor snapshot — 2026-07-27T16:40Z

- The persistent `jem_hg003_4_hiomr2_take4_20260727` controller completed all
  30 of 30 steps and printed `WORKFLOW SUCCESS` with `RETURN CODE: 0`. It
  released the analysis-root write lock normally.
- `sacct` shows every HIOMR2 submission 138-165 `COMPLETED` with exit `0:0`
  and Slurm comment `RnD`; no failed, cancelled, or spot-loss job was observed.
  The last two package jobs, 164 and 165, completed in 00:00:42 and 00:00:40.
- Read-only verification found both nonempty analytical package manifests:
  HG003 at 16:39Z and HG004 at 16:40Z, each 7,757 bytes, under
  `results/day/hg38_broad/deliveries/inflection_hiomr2_analytical_callsets_vcf_gvcf/this-time-go/`.
- A terminal read visit was recorded. The 45-minute heartbeat monitor is paused
  because the requested controller is no longer active. No Slurm intervention,
  rerun, or recovery action was performed.

## Post-completion mtime confirmation — 2026-07-27T17:55Z

- The requested exact `dy-r` kitchensink plus analytical package command was
  run with `--rerun-triggers mtime -n`. It returned `RETURN CODE: 0` and
  explicitly reported: `Nothing to be done (all requested files are present and
  up to date).` No completed rule was selected.
- After a DYEC analysis-root write lock was acquired, the identical command was
  run without `-n`. It again reported `Nothing to be done`, then `WORKFLOW
  SUCCESS`, `RETURN CODE: 0`, and released the lock. It submitted no jobs and
  changed no workflow artifact.
- Variant-call scope was the five explicit shard groups for both HG003 and
  HG004: (1) chr1, chr2, chr3; (2) chr4-chr8; (3) chr9-chr15; (4) chr16-chr20;
  (5) chr21, chr22, chrX, chrY, chrM. The hg38_broad reference FAI confirms the
  resolved names `chrX`, `chrY`, and `chrM` (not `chrMT`).

## Headnode session cleanup — 2026-07-27T18:55Z

- DYEC read-only inspection found five lingering `ssm-session-worker`
  processes and 51 detached `ubuntu` tmux sessions. The only Slurm job was
  unrelated `sleep_test.sh` (job 103), which was not touched; no DayOA or
  Snakemake controller process was present.
- At the owner's request, DYEC terminated the five existing SSM session workers
  while preserving its own transport. It also removed the 50 historical,
  detached tmux sessions after confirming their panes were idle (`bash`, with
  one `git` pane), retaining only `jem_hg003_4_hiomr2_take4_20260727`.
- A five-second post-action DYEC check found no `ssm-session-worker` process
  and confirmed the retained tmux session remains present. No workflow or
  Slurm action was performed.
- A subsequent fresh `dyec headnode connect` reached the normal interactive
  `(DAY-EC) ubuntu@ip-10-0-0-138` prompt with Session Manager ID
  `root-hjundv4i5gnhi7colprkehtvaa`. A follow-up transport test established
  that DYEC/Codex did return a nested writable terminal session ID (`27165`);
  the prior controller attempt had discarded that value while rendering output
  and incorrectly tried to write to the outer execution cell ID. Sending a
  harmless marker through `27165` succeeded, then the test session was closed.
  Future controller work must retain and use the nested terminal session ID.

## Native HIOMR2 kitchensink port-test attempt — 2026-07-27T19:00Z

- In the retained one-pane tmux session, a read visit and write lock were
  recorded. The previous hg38_broad run was confirmed complete; its checkout
  was detached at the old source commit `c148f3c7`. The generated Slurm profile
  was copied to
  `bkup/hiomr2_native_port_pre_profile_regeneration_20260727T190500Z/` before
  the owner-approved removal/regeneration from the native-port templates.
- The source was updated to native-port commit `da06133d`. The catalog-equivalent
  hg38_broad dry-run used the explicit five-shard config, ILMN+ONT `[0,25)`,
  `-j 200 -p -k -T 0 --rerun-triggers mtime --rerun-incomplete -n`, and the full
  HIOMR2 target set. It submitted no job: preflight found a repeated `tbi`
  keyword in the new Mito/TIDDIT target declarations.
- One permitted source-backed fix moved the Mito index input to its proper
  target and removed it from TIDDIT. Focused native-rule tests passed 26/26;
  commit `eb483b59` was pushed and deployed to the headnode.
- The corrected dry-run again submitted no job. It failed before DAG creation
  because inherited rule `sentdhiomr2_mito_call` has incompatible wildcards
  across its output/log/benchmark paths. This is a second source defect, so no
  further fix or live submission was attempted under the one-fix limit. The
  `dy-r` wrapper released the write lock automatically; a follow-up release
  confirmed that no active lock remains.

## Status snapshot — 2026-07-27T19:27Z

- DYEC recorded a read visit. The retained
  `jem_hg003_4_hiomr2_take4_20260727` tmux session has one window and one idle
  `bash` pane; it shows the same Mito wildcard preflight failure.
- No `dy-r`, DayOA, or Snakemake controller process is present, and no new
  HIOMR2 job was submitted. Slurm queue contains only unrelated job 103
  (`sleep_test.sh`, `RUNNING`), which remains untouched.
- Historical HIOMR2 job 138 remains `COMPLETED` with exit `0:0`. The native
  kitchensink port test remains stopped at the second preflight source defect.
