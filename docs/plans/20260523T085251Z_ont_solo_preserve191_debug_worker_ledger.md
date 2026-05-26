# ONT Solo Preserve-Temp 191-Thread Debug Worker Ledger

Date: 2026-05-23

## Scope

Debug the full-coverage HG003 ONT solo Sentieon DNAscope failure on `hyb-hg003`.
No destructive AWS actions are allowed. Do not edit the source repository for the
pipeline change; patch only the launched DayOA clone through the workflow launch
command.

Fixed context:

- AWS profile: `lsmc`
- Region: `us-west-2`
- Cluster: `hyb-hg003`
- Executing entity: `johnm`
- Project: `hyb-hg003`
- DayOA tag: `1.0.18`
- Genome: `hg38_broad`
- Full coverage stage dir: `/fsx/data/staged_sample_data/remote_stage_20260522T203135Z`
- Known failure: `sent_snv_ont` reports `DNAscope: Failed to open output file /dev/shm/.../out_diploid_tmp.vcf.gz_1180`

## Gate 0 Baseline

- Ledger path: `docs/plans/20260523T085251Z_ont_solo_preserve191_debug_worker_ledger.md`
- Related orchestrator ledger: `docs/plans/20260523T004101Z_hyb_hg003_hg003_dayoa_1018_validation_ledger.md`
- Repo state: `## codex/analysis-id-export-catalog-validation...origin/codex/analysis-id-export-catalog-validation`; existing untracked cost reports, prior ledgers, and `tmp/` content are pre-existing and not owned by this worker.
- Instruction sources read: `/Users/jmajor/.agents/AGENTS.md`, `/Users/jmajor/.codex/AGENTS.md`, `/Users/jmajor/.codex/memory.md`, `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`, repo `AGENTS.md`, and `/Users/jmajor/.augment/rules/*.md`.
- Prior full-coverage ONT runs without temp preservation: `hg003a_ont_snv_alignstats_1018`, `hg003a_ont_snv_alignstats_1018_bigmem`.
- Prior lower-coverage control: `hg003_ont_3x_snv_alignstats_1018` succeeded.
- Existing ledger search for `preserv`, `191`, and `sentdont_tmp` found no temp-preserving 30x ONT run.
- No source DayOA files will be edited in this repo for the run patch.

## Ledger Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-ONT-001 | Baseline | Confirm instructions, repo state, prior ONT failure evidence, and no existing temp-preserve run. | SUCCESS | contract_test | Gate 0 | ONT worker | Read instructions and current orchestrator ledger. Prior failures and no-preserve state recorded above. |  | Gate 0 complete. |
| PATCH-ONT-001 | Patch strategy | Define a launch-only patch that sets `sentdont` to both partitions, requests/uses 191 threads, and preserves `/dev/shm` evidence to FSx on failure. | NO_LONGER_NEEDED | feature_implementation | Gate 1 | ONT worker | User redirected this worker to sidecar-only inspection while the real run was launched by another agent. |  | Superseded by sidecar rows below. |
| DRY-ONT-191-001 | Dry-run | Launch full-coverage ONT solo dry-run with the preserve/191 patch and verify the DAG/resources before real run. | NO_LONGER_NEEDED | contract_test | Gate 1 | ONT worker | Dry-run `hg003a_ont_snv_alignstats_1018_191_preservetmp_dryrun` already existed by sidecar inspection. |  | Superseded by sidecar rows below. |
| RUN-ONT-191-001 | Real run | Launch full-coverage ONT solo real run with temp preservation, monitor status, node names, and Slurm state. | NO_LONGER_NEEDED | feature_implementation | Gate 2 | ONT worker | Real run `hg003a_ont_snv_alignstats_1018_191_preservetmp` was launched by another agent; this worker did not launch or cancel. |  | Superseded by sidecar rows below. |
| EVID-ONT-191-001 | Failure evidence | If the run fails, inspect copied FSx artifacts and, if still possible, `/dev/shm` on the compute node. | NO_LONGER_NEEDED | contract_test | Gate 3 | ONT worker | Sidecar evidence captured below. |  | Superseded by sidecar rows below. |
| FINAL-ONT-191-001 | Deliverable | Report preservation existence, patch strategy, commands/session names, status, nodes, FSx evidence paths, and diagnosis. | SUCCESS | contract_test | Gate 4 | ONT worker | Sidecar final evidence captured below. |  | Deliverable prepared. |

## Sidecar Amendment - 2026-05-23T09:02Z

Newest user direction: this worker must act as the ONT solo debug sidecar. The
real full-coverage run is being launched separately. This worker must not launch
or cancel jobs; it should independently inspect prior failures and the new run,
collect the `sent_snv_ont` Slurm job id/node, verify effective 191-thread config
and both partitions, and investigate preserved tmp evidence if the run fails.

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| SIDE-ONT-001 | Sidecar scope | Do not launch or cancel; observe the separately launched real preserve-temp run. | SUCCESS | plan_amendment | Gate 1 | ONT worker | No launch/cancel commands were run by this worker after sidecar redirection; only SSM read/probe commands were run. |  | Sidecar scope maintained. |
| SIDE-PRIOR-001 | Prior failures | Summarize prior full-coverage ONT failure evidence from existing run artifacts. | SUCCESS | contract_test | Gate 1 | ONT worker | Orchestrator ledger rows `RUN-ONT-001`, `BIGMEM-RUN-ONT-001`, and `BIGMEM-SHM-001` record full-coverage failures at `sent_snv_ont`, including `/dev/shm/.../out_diploid_tmp.vcf.gz_214`, `_215`, and `_1180`; 3x ONT control succeeded. |  | Prior full-coverage DNAscope failure evidence confirmed. |
| SIDE-RUN-001 | New run config | Once the real run exists, verify `sentdont` config and rule capture patch in the launched clone. | SUCCESS | contract_test | Gate 2 | ONT worker | SSM `77f3903b-08c2-496f-a041-6f6020a278bd`, `17e660b2-bf86-4ed2-8d07-147e547e8596`, and `21ba2f56-1d02-44d3-9aec-270dc08dc960`: real run `hg003a_ont_snv_alignstats_1018_191_preservetmp` existed, `sentdont` config was `threads=191`, `use_threads=191`, `partition=i192mem,i192bigmem`, `mem_mb=300000`; rule file still had original cleanup `trap 'rm -rf "$TMPDIR" ...'` and no `capture_sentdont_tmp` or `ont_tmp_capture`. Tmux log shows patch Python failed with `NameError: name 'log' is not defined`, then `bin/day_run` continued. |  | Config patched; tmp-preservation rule patch did not apply. |
| SIDE-JOB-001 | Slurm tracking | Capture `sent_snv_ont` Slurm job id, node name, CPUs, memory, and state. | NO_LONGER_NEEDED | contract_test | Gate 2 | ONT worker | The real run failed before `sent_snv_ont` submitted. SSM `608007ca-c915-46b9-a80d-c8b7f621f46a` and `fff2b56b-a7ec-4186-9ef9-cb750fc264e1`: only `pre_prep_ont_cram` Slurm job `180` appeared, on `i192-dy-all-1`, `48` CPUs, `20000M`. `scontrol show job 180` later reported `CANCELLED`, `ExitCode=0:0`, `StartTime=2026-05-23T08:58:00`, `EndTime=2026-05-23T09:00:04`. |  | No `sent_snv_ont` job/node exists for this run. |
| SIDE-EVID-001 | Failure evidence | If failed, inspect `ont_tmp_capture` and live compute-node `/dev/shm` when still accessible. | SUCCESS | contract_test | Gate 3 | ONT worker | SSM `fff2b56b-a7ec-4186-9ef9-cb750fc264e1`: status `exit_code=1`, completed `2026-05-23T09:00:04Z`; no `ont_tmp_capture` dirs and no sentdont logs existed. SSM `42e6b28f-6cb7-49a8-93d3-4366228ae175`: from headnode, `ssh i192-dy-all-1` showed `/dev/shm` `378G`, `0` used, no `sentdont_tmp_*`, and no Sentieon/DNAscope processes. |  | Failure was before DNAscope; no tmp evidence was available. |

## Sidecar Terminal Summary

- Real session: `hg003a_ont_snv_alignstats_1018_191_preservetmp`
- Dry-run session: `hg003a_ont_snv_alignstats_1018_191_preservetmp_dryrun`
- Real status: `exit_code=1`, started `2026-05-23T08:57:38Z`, completed `2026-05-23T09:00:04Z`
- Effective real `sentdont` config: `threads=191`, `use_threads=191`, `partition=i192mem,i192bigmem`, `mem_mb=300000`
- Effective rule patch state: not preserved; rule still has `trap 'rm -rf "$TMPDIR" 2>/dev/null || true' EXIT`
- Patch failure cause: embedded Python used an f-string containing Snakemake `{log}` without escaping it, causing `NameError: name 'log' is not defined`; because the dy-command then continued to `bin/day_run`, the config changes persisted but the rule trap did not change.
- Slurm evidence: only `pre_prep_ont_cram` job `180` submitted on `i192-dy-all-1`; `sent_snv_ont` never submitted.
- Compute-node `/dev/shm`: checked `i192-dy-all-1` after failure; `/dev/shm` was empty of `sentdont_tmp_*`.
- Interpretation: this run did not exercise the DNAscope failure. It failed early and also was not a valid temp-preservation run because the rule patch did not apply.

## V2 Sidecar Follow-Up - 2026-05-23T09:15Z

Newest user direction: inspect corrected real run
`hg003a_ont_snv_alignstats_1018_191_preservetmp_v2`; monitor Slurm job
`182`; if it fails inspect FSx `ont_tmp_capture` and live `/dev/shm` on
`i192mem-dy-all-1`. Do not cancel or mutate.

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| V2-SCOPE-001 | Sidecar scope | Observe only; do not launch, cancel, or mutate AWS/jobs. | SUCCESS | plan_amendment | Gate 1 | ONT worker | Only SSM read/probe commands were run for v2: `cf0bff51-5dd7-49f1-ae41-559eb330f434`, `f62b5b86-742e-4bdd-8f9e-af702d165910`, `7f94c1f8-3053-4d23-8889-5f98bd618bb3`, `932bf32f-4f85-4a69-b30e-674c9cad7ee1`, `5f844771-3746-4229-9976-dad7abd1abcb`, `ab5cbe91-155c-4912-b427-3ed1fdd16a8d`. |  | Sidecar scope maintained. |
| V2-CONFIG-001 | Config/rule patch | Verify v2 clone config and capture trap are effective. | SUCCESS | contract_test | Gate 1 | ONT worker | V2 clone `config/day_profiles/slurm/rule_config.yaml`: `sentdont threads=191`, `use_threads=191`, `partition=i192mem,i192bigmem`, `mem_mb=300000`. `workflow/rules/sent_snv_ont.smk` has `TMPDIR=/dev/shm/sentdont_tmp_$timestamp`, `SENTIEON_TMPDIR=$TMPDIR`, capture root `/fsx/analysis_results/johnm/hg003a_ont_snv_alignstats_1018_191_preservetmp_v2/ont_tmp_capture`, `capture_sentdont_tmp`, and `trap capture_sentdont_tmp EXIT`. |  | Config and capture trap verified. |
| V2-JOB182-001 | Slurm attempt 1 | Monitor Slurm job `182` and capture node/status/failure. | FAIL | contract_test | Gate 2 | ONT worker | Job `182`: `sent_snv_ont`, partition `i192mem`, node `i192mem-dy-all-1`, `191` CPUs, `300000M`, start `2026-05-23T09:09:52`, end `2026-05-23T09:12:00`, `FAILED`, `ExitCode=1:0`. Live sample at `2026-05-23T09:10:06Z` showed Sentieon `--thread_count 191` writing `/dev/shm/sentdont_tmp_20260523091003_11408/tmp4qwld70p/out_diploid_tmp.vcf.gz`; `/dev/shm` grew only to ~54M before failure. Rule log: `DNAscope: Failed to open output file .../out_diploid_tmp.vcf.gz_209`; Sentieon `Return code 255`; Python cleanup then `FileNotFoundError` for `tmp4qwld70p`. | Sentieon failed opening internal DNAscope temp output under `/dev/shm` despite low tmpfs usage. | Snakemake retried the same rule as job `185`. |
| V2-JOB185-001 | Slurm attempt 2 | Monitor retry job `185` and capture node/status/failure. | FAIL | contract_test | Gate 2 | ONT worker | Job `185`: `sent_snv_ont`, partition `i192mem`, node `i192mem-dy-all-1`, `191` CPUs, `300000M`, start `2026-05-23T09:12:09`, end `2026-05-23T09:14:13`, `FAILED`, `ExitCode=1:0`. Rule log: `Failed to create temporary directory /dev/shm/sentdont_tmp_20260523091219_15587/job15794: No such file or directory`; Sentieon `Return code 1`; Python cleanup then `FileNotFoundError` for `tmp4sjd77jh`. `/dev/shm` again peaked only around 54M during polling. | Sentieon lost or removed its expected `/dev/shm` parent path during DNAscope processing; this is related to temp path lifecycle rather than full `/dev/shm`. | Workflow terminalized failed after retry. |
| V2-CAPTURE-001 | Tmp capture | Inspect FSx capture artifacts and live compute-node `/dev/shm`. | SUCCESS | contract_test | Gate 3 | ONT worker | Capture dirs: `/fsx/analysis_results/johnm/hg003a_ont_snv_alignstats_1018_191_preservetmp_v2/ont_tmp_capture/i192mem-dy-all-1_20260523T091158Z_11408/summary.txt` and `/fsx/analysis_results/johnm/hg003a_ont_snv_alignstats_1018_191_preservetmp_v2/ont_tmp_capture/i192mem-dy-all-1_20260523T091411Z_15587/summary.txt`. Both summaries show `/dev/shm` size `378G`, used `4.0K`, inode use 1%, memory `755Gi` total / `716Gi` free, and only lingering `licsrvr` processes. No `.tgz` was created because the Sentieon tmp dir was already gone when the shell trap ran. Final live-node SSH showed `/dev/shm` empty and no Sentieon/DNAscope processes. |  | Captures confirm the failing tmp paths disappear before the rule-level trap can archive them. |
| V2-FINAL-001 | Final status | Record terminal v2 workflow status and interpretation. | FAIL | contract_test | Gate 4 | ONT worker | `status.json`: `exit_code=1`, started `2026-05-23T09:04:56Z`, completed `2026-05-23T09:14:29Z`; final queue empty. Tmux markers show `Submitted job 2 external jobid 182`, `Trying to restart job 2`, `Submitted job 2 external jobid 185`, then `Exiting because a job execution failed` and `RETURN CODE: 1`. | Full-coverage ONT solo still fails in Sentieon DNAscope with 191 threads on `i192mem`; observed `/dev/shm` and memory usage are far below capacity, so simple capacity exhaustion is not supported. | Objective of preserving enough evidence partly succeeded; actual temp shard contents were unavailable because Sentieon removed them before the shell trap. |

V2 interpretation:

- This is now a valid corrected preserve-temp run in the sense that the capture
  trap was present and fired for both failed attempts.
- The core failure reproduced with 191 threads and both allowed partitions:
  first as `Failed to open output file ... out_diploid_tmp.vcf.gz_209`, then as
  `Failed to create temporary directory .../job15794`.
- Both failures occurred on `i192mem-dy-all-1` with `/dev/shm` essentially
  empty and the node having hundreds of GiB free memory.
- The failing tmp directories were already removed by Sentieon/sentieon-cli
  cleanup before the shell trap could tar them. The durable captures therefore
  contain system state, not temp-file contents.

## V4 Retain-Tmp Real Run - 2026-05-23T11:00Z

Newest user direction: launch the full-coverage HG003 ONT solo v4 diagnostic
as its own workflow session, with `sentieon-cli dnascope-longread
--retain_tmpdir` and the FSx `/dev/shm` capture trap. Use session and analysis
id `hg003a_ont_snv_alignstats_1018_191_retain_tmp_v4`.

Exact-session check: no run directory or analysis directory existed for
`hg003a_ont_snv_alignstats_1018_191_retain_tmp_v4`; tmux prefix matching
initially matched the dry-run session
`hg003a_ont_snv_alignstats_1018_191_retain_tmp_v4_dryrun`, so the final
existence check used explicit directory inspection and tmux session listing.

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| V4-LAUNCH-001 | Real launch | Launch full-coverage ONT v4 real diagnostic with hard-failing clone-local patch. | SUCCESS | feature_implementation | Gate 2 | ONT worker | `dyec workflow launch --profile lsmc --region us-west-2 --cluster hyb-hg003 --stage-dir /fsx/data/staged_sample_data/remote_stage_20260522T203135Z --analysis-id hg003a_ont_snv_alignstats_1018_191_retain_tmp_v4 --session-name hg003a_ont_snv_alignstats_1018_191_retain_tmp_v4 --executing-entity johnm --git-tag 1.0.18 --project hyb-hg003 --genome hg38_broad --dy-command <hard-failing patch plus day_run>` returned code `0`; session created at `2026-05-23T11:00:13Z`. |  | Real v4 diagnostic launched. |
| V4-PATCH-001 | Patch verification | Verify launched clone uses `sentdont` 191 threads, both memory partitions, FSx capture trap, and `--retain_tmpdir`. | SUCCESS | contract_test | Gate 2 | ONT worker | Repo `/fsx/analysis_results/johnm/hg003a_ont_snv_alignstats_1018_191_retain_tmp_v4/daylily-omics-analysis`; `rule_config.yaml` has `sentdont.threads=191`, `use_threads=191`, `partition="i192mem,i192bigmem"`, `mem_mb=300000`. `workflow/rules/sent_snv_ont.smk` grep shows `capture_sentdont_tmp`, capture root `/fsx/analysis_results/johnm/hg003a_ont_snv_alignstats_1018_191_retain_tmp_v4/ont_tmp_capture`, `trap capture_sentdont_tmp EXIT`, and `sentieon-cli dnascope-longread --retain_tmpdir`. |  | Patch is present in the launched clone only. |
| V4-STATUS-001 | Immediate status | Report run dir, repo path, status, and current ONT/Slurm jobs after launch. | IN_PROGRESS | contract_test | Gate 3 | ONT worker | Run dir `/home/ubuntu/daylily-runs/hg003a_ont_snv_alignstats_1018_191_retain_tmp_v4`; repo path `/fsx/analysis_results/johnm/hg003a_ont_snv_alignstats_1018_191_retain_tmp_v4/daylily-omics-analysis`; `dyec workflow status` has `exit_code=null`, `completed_at=null`, `started_at=2026-05-23T11:00:13Z`. Current queue at first check: Slurm job `316`, `pre_prep_ont_cram`, partition `i192`, node `i192-dy-all-1`, `48` CPUs, `20000M`, `CONFIGURING`; no `sent_snv_ont` job submitted yet and no `ont_tmp_capture` dirs yet. |  | Continue monitoring until `sent_snv_ont` submits or the workflow terminalizes. |
