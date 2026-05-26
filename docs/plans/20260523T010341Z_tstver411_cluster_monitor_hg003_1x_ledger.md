# tstVer4-1-1 Cluster Build And HG003 1x Illumina Smoke Ledger

## Objective

Monitor the requested cluster build, verify headnode configuration after creation, stop if `day-clone` is unavailable or does not default to the maximum available DayOA version, and only then run a 1x-coverage HG003 Illumina workflow smoke test.

## Gate 0 Baseline

| Item | Evidence |
|---|---|
| Ledger path | `docs/plans/20260523T010341Z_tstver411_cluster_monitor_hg003_1x_ledger.md` |
| Local repo | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| Local branch | `codex/analysis-id-export-catalog-validation...origin/codex/analysis-id-export-catalog-validation` |
| Pre-existing dirty state | Untracked prior artifacts under `docs/`, `docs/plans/`, `fill_in_the_blanks_lims.md`, and `tmp/`; this ledger is the only file created for this request so far. |
| Requested cluster name | User requested `testVer-4-1-1`; `pcluster describe-cluster` did not find that exact name. |
| Resolved active cluster | `tstVer4-1-1` in `us-west-2`, profile `lsmc`; discovered by `pcluster list-clusters`. |
| Initial cluster state | `pcluster describe-cluster -n tstVer4-1-1 --region us-west-2` -> `clusterStatus=CREATE_IN_PROGRESS`, `cloudFormationStackStatus=CREATE_IN_PROGRESS`, headnode `i-05d8f894dc3466001` running, launch time `2026-05-23T00:57:21Z`, ParallelCluster `3.13.2`. |
| Headnode access rule | All headnode commands must use DayEC SSM helpers as `ubuntu` in a bash login shell. |
| Stop condition | If headnode config fails, `day-clone` is missing, or default `day-clone -d <dest>` does not clone the maximum non-`v` semver tag of DayOA, stop and report; do not run the HG003 workflow. |
| Test dataset assumption | Use the already staged HG003-a 30x Illumina bundle from `s3://lsmc-dayoa-omics-analysis-us-west-2/fsx/staging/staged_sample_data/remote_stage_20260522T203135Z/`, set `SUBSAMPLE_PCT=0.033333` for a 1x smoke test. |
| Planned smoke command | After dry-run succeeds: `bin/day_run produce_dmd_dedup_cram produce_sentd_snv_vcf produce_snv_concordances produce_alignstats --config 'aligners=["sent"]' 'dedupers=["dmd"]' 'snv_callers=["sentd"]' -p -j <safe concurrency> -k -T 1`. |
| Safety boundary | No delete, export, unmount, or cluster teardown action is part of this request. |

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Inventory | Record repo, cluster, resolved name, dirty state, stop conditions, and test assumptions. | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 Baseline above. |  | Baseline recorded before headnode mutation. |
| BUILD-001 | Cluster | Monitor `tstVer4-1-1` until ParallelCluster reports `CREATE_COMPLETE` or terminal failure. | SUCCESS | contract_test | Gate 1 | orchestrator | Initial state `CREATE_IN_PROGRESS`; headnode `i-05d8f894dc3466001` running. At `2026-05-23T01:18:45Z`, `pcluster describe-cluster` reported `clusterStatus=CREATE_COMPLETE`, `cloudFormationStackStatus=CREATE_COMPLETE`, and `computeFleetStatus=RUNNING`; DRA `dra-00ae17bd9eee386a9` was `AVAILABLE`. |  | Cluster build completed. |
| BOOT-001 | Headnode | Verify headnode config/bootstrap logs show successful config process before workflow work. | SUCCESS | contract_test | Gate 2 | orchestrator | SSM command `5cbb2772-717a-4e03-af22-dcf580873710` showed post-install log `Post-installation complete.`, CloudFormation signal `SUCCESS`, and cfn-init `Build complete`; Slurm partitions were visible and idle. |  | Bootstrap completed from the CloudFormation perspective. |
| CLONE-001 | DayOA default | Verify `day-clone` is available and defaults to the maximum DayOA version. Stop if not. | SUCCESS | contract_test | Gate 2 | orchestrator | Initial check at `2026-05-23T01:19Z` failed because login shell had not activated DAY-EC. Retry SSM command `b8f7bbb6-2b19-4ac0-99a7-eade49b77790` showed `CONDA_DEFAULT_ENV=DAY-EC`, `day-clone=/home/ubuntu/.local/bin/day-clone`, and DayOA default ref `1.0.18`. SSM command `5863becd-9e0f-4d27-a2d0-e5b348344687` ran `day-clone -d testver411-hg003a-1x-ilmn-20260523T012800Z`; clone checked out exact tag `1.0.18`, matching computed `MAX_NON_V_SEMVER_TAG=1.0.18`. |  | Default clone is available and points to the max DayOA tag. |
| DATA-001 | Test config | Prepare HG003-a 1x Illumina config from staged 30x bundle with `SUBSAMPLE_PCT=0.033333`. | SUCCESS | contract_test | Gate 3 | orchestrator | SSM command `582d7851-fc14-4897-9688-aa45e2bba749` wrote `config/samples.tsv` and `config/units.tsv`, set `SUBSAMPLE_PCT=0.033333`, rewrote truth paths from `/data/...` to host-visible `/fsx/references/...`, cleared ONT/PacBio/Ultima/Roche columns for Illumina-only smoke, and confirmed `ILMN_R1_COUNT=8`, `ILMN_R2_COUNT=8`, `ONT_CRAM=`. |  | HG003-a 1x Illumina-only config prepared. |
| DRY-001 | Workflow dry-run | Run HG003-a 1x Illumina workflow dry-run and capture scheduled work. | SUCCESS | contract_test | Gate 4 | orchestrator | Initial dry-run SSM command `42f7388b-6bd0-4785-b760-a2224178caaa` passed but scheduled ONT due hybrid config. Corrected Illumina-only dry-run SSM command `ba5526ae-8575-4aa0-a920-c99565b92836` returned `DRYRUN_RC=0`; job stats total `32`, including `sentieon_bwa_sort`, `doppelmark_dups`, `sent_DNAscope`, `rtg_vcfeval_roi`, `produce_snv_concordances`, and `produce_alignstats`. Dry-run command showed all eight R1 files and all eight R2 files streamed via ordered process substitutions. |  | Dry-run passed after making the test config explicitly Illumina-only. |
| LIVE-001 | Workflow live run | Run the HG003-a 1x Illumina workflow only after dry-run passes. | SUCCESS | contract_test | Gate 4 | orchestrator | Initial tmux launch failed before `day_run` because wrapper used `set -u` and `bin/day_activate` reads `$3`; no jobs were submitted. Relaunch SSM command `e81b3095-26a0-4c32-8492-de5ba9a9b87e` started tmux session `testver411_hg003a_1x`. Heartbeat polls showed Slurm progress through `sentieon` and `parse_vc`. Poll SSM command `092f34f6-3109-4f87-aa06-a1f0ab7083e8` found tmux stopped, queue empty, and `status.json` with `rc=0`, `start_utc=2026-05-23T01:41:13Z`, `end_utc=2026-05-23T02:13:59Z`. Verification SSM command `cee19430-508e-496f-a45e-18293354ca69` confirmed one dmd CRAM/CRAI, one Sentieon DNAscope VCF/TBI, one concordance sentinel, five concordance MQC TSVs, one gathered GIAB concordance MQC TSV, fifteen alignstats-named files, and two target alias done files. Compact evidence SSM command `e731825a-becb-4a6c-bc5c-dc11be22c416` recorded repo size `3.3G`, `/fsx` `128G` used and `4.3T` available, empty queue, and terminal Snakemake `32 of 32 steps (100%) done`. |  | Workflow completed successfully. |
| FINAL-001 | Final report | Report terminal state, analysis path, tmux/session/job ids, artifacts, and any stop reason. | SUCCESS | contract_test | Gate 5 | orchestrator | Analysis id `testver411-hg003a-1x-ilmn-20260523T012800Z`; repo `/fsx/analysis_results/ubuntu/testver411-hg003a-1x-ilmn-20260523T012800Z/daylily-omics-analysis`; run dir `/home/ubuntu/daylily-runs/testver411-hg003a-1x-ilmn-20260523T012800Z`; tmux session `testver411_hg003a_1x`; observed Slurm job IDs `1,2,10,12,13,15,16,18,19,21,22,23,24,25,26,27,28,29,30`; terminal `status.json rc=0`. |  | Objective complete. |

## Evidence Log

- `2026-05-23T01:03:41Z`: Created ledger after resolving active cluster name to `tstVer4-1-1`.
- `2026-05-23T01:03:41Z`: `pcluster describe-cluster` showed build still in progress with headnode instance running.
- `2026-05-23T01:06:05Z`: Read-only SSM check as `ubuntu` confirmed the headnode is reachable but not configured yet: `day-clone` was not on `PATH`, `cloud-init final`/`cfn-init` were still active, and the Daylily post-install log was waiting for `/fsx/references` reference entries.
- `2026-05-23T01:06:21Z`: `df -hT /fsx` on headnode showed FSx mounted at `/fsx` with `4.4T` available; DRA `dra-00ae17bd9eee386a9` remained `CREATING` for `s3://lsmc-dayoa-omics-analysis-us-west-2/data/` to `/data/`.
- `2026-05-23T01:07:59Z`: `pcluster describe-cluster` still showed `clusterStatus=CREATE_IN_PROGRESS` and `cloudFormationStackStatus=CREATE_IN_PROGRESS`.
- `2026-05-23T01:08Z`: Created heartbeat automation `monitor-tstver4-1-1-hg003-1x-smoke` to continue this ledger-driven monitor and run the smoke workflow after build/config checks pass.
- `2026-05-23T01:18:45Z`: Cluster reached `CREATE_COMPLETE`; DRA `dra-00ae17bd9eee386a9` reached `AVAILABLE`; no incomplete CloudFormation resources remained.
- `2026-05-23T01:19:23Z`: SSM command `5cbb2772-717a-4e03-af22-dcf580873710` verified bootstrap completion, but `day-clone` was missing (`rc=127`) and `CONDA_DEFAULT_ENV` was unset in the ubuntu bash login shell.
- `2026-05-23T01:20:04Z`: SSM command `974c79dc-2f33-43bd-aab4-787bc47d5acb` found conda installed and profile files present, but found no `day-clone`/`daylily-ec` command in common headnode paths; workflow launch stopped per the user instruction.
- `2026-05-23T01:27:20Z`: Retry SSM command `b8f7bbb6-2b19-4ac0-99a7-eade49b77790` showed `DAY-EC activated`, `CONDA_DEFAULT_ENV=DAY-EC`, `daylily-ec` and `day-clone` available, staged config present, `/fsx` with `4.4T` available, and empty Slurm queue.
- `2026-05-23T01:28:17Z`: SSM command `5863becd-9e0f-4d27-a2d0-e5b348344687` cloned DayOA using default `day-clone -d testver411-hg003a-1x-ilmn-20260523T012800Z`; actual tag `1.0.18` matched maximum non-`v` semver tag `1.0.18`.
- `2026-05-23T01:32:42Z`: Prepared initial 1x config and dry-ran. Dry-run passed but scheduled ONT pre-prep because the staged hybrid units file contained `ONT_CRAM`; this was not accepted as the final Illumina-only dry-run.
- `2026-05-23T01:35:27Z`: Inspected paths: `/data` is absent on the headnode; truth data exists under `/fsx/staging/staged_sample_data/remote_stage_20260522T203135Z/.../concordance_data`.
- `2026-05-23T01:36Z`: SSM command `582d7851-fc14-4897-9688-aa45e2bba749` normalized config to Illumina-only and host-visible truth paths.
- `2026-05-23T01:37:13Z`: SSM command `ba5526ae-8575-4aa0-a920-c99565b92836` ran corrected dry-run with `DRYRUN_RC=0`; no ONT jobs remained in job stats.
- `2026-05-23T01:39Z`: First live tmux launch exited before `day_run`; log showed `bin/day_activate: line 6: $3: unbound variable` caused by the wrapper's `set -u`, plus missing explicit conda shell initialization in the tmux context. No Slurm jobs were submitted.
- `2026-05-23T01:41:13Z`: Relaunched live run in tmux session `testver411_hg003a_1x` using explicit conda shell initialization and `source bin/day_activate slurm hg38 ""`; activation succeeded and `day_run` started.
- `2026-05-23T01:42:13Z`: Poll showed tmux session still running, Slurm queue empty while Snakemake was creating conda environment `workflow/envs/sentD_v0.2.yaml`; `status.json` not present yet because run is not terminal.
- `2026-05-23T01:53:11Z`: Heartbeat poll SSM command `1d2d04e6-1e54-4684-b23d-9e5c8ed7cf28` showed tmux session `testver411_hg003a_1x` still active, Slurm job `1` running `sentieon` on `i192mem-dy-all-1`, `/fsx` at `25G` used and `4.4T` available, and no terminal `status.json` yet.
- `2026-05-23T02:03:10Z`: Heartbeat poll SSM command `eb91ab7e-97af-4bdc-88ee-e5c29b35a345` showed tmux session `testver411_hg003a_1x` still active, Slurm job `1` still running `sentieon` on `i192mem-dy-all-1` for `12:17`, `/fsx` at `111G` used and `4.3T` available, and no terminal `status.json` yet.
- `2026-05-23T02:13:13Z`: Heartbeat poll SSM command `06228741-243e-461d-b0c8-e8bed821b065` showed tmux session `testver411_hg003a_1x` still active, Slurm jobs `17` and `18` running `parse_vc` on `i192mem-dy-all-1`, Snakemake progress at `28 of 32 steps (88%) done`, `/fsx` at `128G` used and `4.3T` available, and no terminal `status.json` yet.
- `2026-05-23T02:23:10Z`: Heartbeat poll SSM command `092f34f6-3109-4f87-aa06-a1f0ab7083e8` showed tmux stopped, Slurm queue empty, `/fsx` at `128G` used and `4.3T` available, and `status.json` terminal with `rc=0`, `start_utc=2026-05-23T01:41:13Z`, and `end_utc=2026-05-23T02:13:59Z`.
- `2026-05-23T02:25:02Z`: Verification SSM command `cee19430-508e-496f-a45e-18293354ca69` confirmed terminal outputs: `dmd_cram=1`, `dmd_crai=1`, `sentd_vcf=1`, `sentd_tbi=1`, `concordance_done=1`, `concordance_mqc=5`, `giab_concordance_mqc=1`, `alignstats_files=15`, and `target_done=2`.
- `2026-05-23T02:25:56Z`: Compact evidence SSM command `e731825a-becb-4a6c-bc5c-dc11be22c416` recorded repo size `3.3G`, `/fsx` `4.4T` total with `128G` used and `4.3T` available, empty `squeue`, no tmux server, dmd CRAM `745382295` bytes, dmd CRAI `90025` bytes, Sentieon DNAscope VCF `88284143` bytes, VCF TBI `1606966` bytes, and Snakemake log tail `32 of 32 steps (100%) done`.

## Final Report

- Cluster: `tstVer4-1-1` in `us-west-2`, profile `lsmc`.
- Build result: `CREATE_COMPLETE`; headnode `i-05d8f894dc3466001`; compute fleet `RUNNING`.
- Bootstrap result: CloudFormation and post-install completed successfully.
- Stop gate: cleared on retry. `day-clone` is now available and defaults to max DayOA tag `1.0.18`.
- Workflow result: SUCCESS. `status.json` recorded `rc=0`, `start_utc=2026-05-23T01:41:13Z`, and `end_utc=2026-05-23T02:13:59Z`; tmux has exited and Slurm queue is empty.
- Analysis id: `testver411-hg003a-1x-ilmn-20260523T012800Z`.
- Repo path: `/fsx/analysis_results/ubuntu/testver411-hg003a-1x-ilmn-20260523T012800Z/daylily-omics-analysis`.
- Run dir: `/home/ubuntu/daylily-runs/testver411-hg003a-1x-ilmn-20260523T012800Z`.
- Tmux session: `testver411_hg003a_1x`.
- Observed Slurm job ids: `1,2,10,12,13,15,16,18,19,21,22,23,24,25,26,27,28,29,30`.
- Key artifacts: dmd CRAM/CRAI, no-dedup sent CRAM/CRAI, Sentieon DNAscope SNV VCF/TBI, five concordance MQC TSVs, gathered `giab_concordance_mqc.tsv`, `alignstats_combo_mqc.tsv`, `alignstats_gs_mqc.tsv`, and target aliases `produce_dmd_dedup_cram.done` and `produce_sentd_snv_vcf.done`.
- FSx at terminal verification: `128G` used, `4.3T` available, `3%` use; DayOA repo size `3.3G`.
- Completion status: objective complete.
