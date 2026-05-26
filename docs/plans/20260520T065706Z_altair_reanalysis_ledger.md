# Altair Reanalysis + HG003 Hybrid Ledger

Created: 2026-05-20T06:57:06Z  
Target: `profile=lsmc`, `region=us-west-2`, `cluster=dra-enabled`, DayOA `1.0.17`, executing entity `johnm`

## Operating Assumptions

- No export and no delete-after-export are part of this run.
- Run 2 is investigation-only; no named-sample workflow launch is allowed for `20260512_LH01106_0007_B23K5JKLT4`.
- Hybrid uses an existing ONT CRAM only if it is verified compatible with DayOA `hg38_broad`; otherwise ONT remap is required before hybrid.
- Destructive FSx/DRA/AWS changes require a separate explicit confirmation. This ledger does not authorize deletion.

## Gate 0 Inventory

Status: `SUCCESS`

### Local Repo And Tool State

- DayEC checkout: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
- DayEC branch: `codex/analysis-id-export-catalog-validation...origin/codex/analysis-id-export-catalog-validation`
- DayEC working tree: untracked `tmp/` existed before this ledger work.
- DayEC CLI version: `4.0.6.dev0+ge450d4830.d20260518`
- Local `git describe --tags --dirty --always`: `4.0.9`
- Local catalog pins DayOA `1.0.17`; headnode catalog was later found to still pin `1.0.16`, so all launches must pass `--git-tag 1.0.17` explicitly.
- DayOA checkout: `/Users/jmajor/projects/daylily/daylily-omics-analysis`
- DayOA branch: `codex/multi-fastq-catalog-validation...origin/codex/multi-fastq-catalog-validation`
- DayOA tag `1.0.17` peels to `c654bd99289252d10c31c310a4d6518e3d738ddc`

### Cluster State

- Cluster `dra-enabled`: `CREATE_COMPLETE`
- Compute fleet: `RUNNING`
- Headnode instance: `i-07ec9d66e9a88e538`
- Headnode instance type: `r7i.8xlarge`
- Headnode public IP: `52.33.34.102`
- Scheduler: `slurm`
- ParallelCluster version: `3.13.2`
- `/fsx`: `11T` size, `141G` used, `11T` available, `2%` used.
- `squeue -u ubuntu`: no active jobs at Gate 0.
- Existing tmux sessions at Gate 0:
  - `giab_multi_fq_test_20260518`
  - `johnm_catalog_smoke_ilmn_20260519T125836Z`
  - `johnm_hg002_multifq_20260519T132658Z`
  - `johnm_hg002_multifq_fix_20260519T133147Z`
  - `johnm_hg003_10x_ksink_20260519T130812Z`

### Mounted DRA State

| Run directory | DRA id | Mount path | Lifecycle | Source |
|---|---:|---|---|---|
| `20260512_LH01106_0006_A23K3H2LT4` | `dra-02d344e4dc8840a90` | `/fsx/run_dir_mounts/20260512_LH01106_0006_A23K3H2LT4/` | `AVAILABLE` | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260512_LH01106_0006_A23K3H2LT4/` |
| `20260512_LH01106_0007_B23K5JKLT4` | `dra-01fab4a0acde07c0e` | `/fsx/run_dir_mounts/20260512_LH01106_0007_B23K5JKLT4/` | `AVAILABLE` | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260512_LH01106_0007_B23K5JKLT4/` |
| `20260513_ONT_HG003` | `dra-006ba927d666a551f` | `/fsx/run_dir_mounts/20260513_ONT_HG003/` | `AVAILABLE` | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260513_ONT_HG003/` |
| `20260514_LH01106_0008_A23TVNWLT4` | `dra-06d806e2e1413adf7` | `/fsx/run_dir_mounts/20260514_LH01106_0008_A23TVNWLT4/` | `AVAILABLE` | `s3://lsmc-ssf-sequencing-data/raw/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0008_A23TVNWLT4/` |

Required Run 3 mount `20260514_LH01106_0009_B23TVLGLT4` was not mounted at Gate 0.

### Source FASTQ And SampleSheet Counts

| Run | SampleSheet RunName | Non-NTC tags | All tags | FASTQ `.gz` count | FASTQ bytes | Undetermined `.gz` count | Undetermined bytes |
|---|---|---:|---:|---:|---:|---:|---:|
| `20260512_LH01106_0006_A23K3H2LT4` | `20260512_ILMN_Altair_Run_1` | 40 | 41 | 672 | 4,992,111,390,944 | 16 | 809,240,005,502 |
| `20260512_LH01106_0007_B23K5JKLT4` | `20260512_ILMN_Altair_Run_2` | 40 | 41 | 672 | 5,212,420,253,681 | 16 | 5,212,420,238,483 |
| `20260514_LH01106_0009_B23TVLGLT4` | `20260514_ILMN_Altair_Run_3` | 40 | 41 | 672 | 4,993,039,853,037 | 16 | 732,146,449,057 |

Run 2 named sample FASTQs are effectively empty gzip stubs; Run 2 investigation must focus on `Undetermined` index evidence.

## Agent Lane Assignments

| Lane | Owner | Scope | Mutation boundary |
|---|---|---|---|
| Orchestrator | local controller | Ledger, Gate 0, row assignment, destructive-action gates, final pass/fail | May edit this ledger and controlled local scratch only |
| Agent A, Manifest Builder | Newton (`019e442c-5845-7350-a230-936e65a52f0e`) | Source inventory and manifest rules for Runs 1/3 | Read-only exploration |
| Agent B, DayOA multi-FASTQ | local controller | Comma-list validation and manifest generation | Local scratch, then copied into assigned analysis dirs only |
| Agent C, Run 2 Forensics | Nietzsche (`019e442c-5893-7870-8b26-e090dcb199b9`) | Undetermined index-pair report | Read-only exploration |
| Agent D, Hybrid | Noether (`019e442c-58f2-7613-939d-39206b4a9e1a`) | ONT CRAM compatibility and hybrid launch preparation | Read-only exploration until assigned run dir exists |
| Agent E, Monitor/Evidence | Huygens (`019e442c-5ae2-7873-9cc3-2b0a3f561c9f`) | Slurm/tmux/log evidence | Read-only exploration |

## Ledger Rows

| Row id | Status | Analysis id | Owner | Objective | Evidence |
|---|---|---|---|---|---|
| `GATE-000` | `SUCCESS` | n/a | Orchestrator | Freeze repo, cluster, mount, Slurm, FSx, and source FASTQ baseline. | Gate 0 inventory recorded above; Agent E confirmed account `108782052779`, FSx `fs-017ab7a7cdbf44c54`, no Slurm jobs, 10.7T available by `lfs df`, and headnode catalog drift requiring explicit DayOA `1.0.17` tag. |
| `MOUNT-003` | `SUCCESS` | n/a | Orchestrator | Mount Run 3 to the standard CLI DRA location. | `dyec --json mounts create ...20260514_LH01106_0009_B23TVLGLT4/ --platform ILMN --wait --timeout-seconds 1800` created `dra-0e036df15b52f3f85`; `dyec --json mounts verify --mount-id 20260514_LH01106_0009_B23TVLGLT4 ...` returned `verified=true`, `usable=true`, headnode path `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/`. |
| `BUGFIX-EC-001` | `SUCCESS` | n/a | Orchestrator | Fix DayEC workflow launcher tmux session existence checks to use exact session names. | Run 3 launch initially failed with SSM stdout `__DAYLILY_ERROR__=session_exists` because `tmux has-session -t "$SESSION_NAME"` treated `re-ana-20260514_LH01106_0009_B23TVLGLT4-HG003-hybrid-ilmn-ont` as a prefix match for the shorter Run 3 session. Patched `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py` to use `tmux has-session -t "=$SESSION_NAME"` for exact targets and updated `tests/test_script_entrypoints.py`; `pytest tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_launches_workflow_session -q` -> 1 passed; `pytest tests/test_script_entrypoints.py -q` -> 22 passed. |
| `MANIFEST-001` | `SUCCESS` | `re-ana-20260512_LH01106_0006_A23K3H2LT4` | Agent A / Orchestrator | Generate Run 1 mounted-readonly analysis manifest for all 40 non-NTC tags, lane `0`, ordered comma-list R1/R2. | `tmp/altair-reanalysis/re-ana-20260512_LH01106_0006_A23K3H2LT4/analysis_samples.tsv` -> 40 rows; each row has 8 ordered R1/R2 lane pairs; `dyec samples stage --precheck-only` passed with rows=40, samples=40, source objects=504, concordance directories=21. |
| `MANIFEST-003` | `SUCCESS` | `re-ana-20260514_LH01106_0009_B23TVLGLT4` | Agent A / Orchestrator | Generate Run 3 mounted-readonly analysis manifest for all 40 non-NTC tags, lane `0`, ordered comma-list R1/R2. | `tmp/altair-reanalysis/re-ana-20260514_LH01106_0009_B23TVLGLT4/analysis_samples.tsv` -> 40 rows; each row has 8 ordered R1/R2 lane pairs; `dyec samples stage --precheck-only` passed with rows=40, samples=40, source objects=504, concordance directories=21. |
| `FORENSICS-002` | `SUCCESS` | `re-ana-20260512_LH01106_0007_B23K5JKLT4-unexpected-index-report` | Agent C / Orchestrator | Report observed Run 2 `Undetermined` index pairs vs expected SampleSheet tags; do not launch named sample workflows. | `tmp/altair-reanalysis/20260512_LH01106_0007_B23K5JKLT4_unexpected_index_report.md`; BCLConvert reports 8 assigned non-Undetermined reads, 8,000 top unknown barcode rows, zero exact overlap with 41 expected pairs, and lane unknown-read sums totaling 25,642,549,782 across top-unknown rows. No sample workflow launched for Run 2. |
| `LAUNCH-001-DRY` | `SUCCESS` | `re-ana-20260512_LH01106_0006_A23K3H2LT4` | Agent B / Orchestrator | `day-clone -t 1.0.17 -d <analysis_id>` then dry-run Run 1 command in persistent tmux login bash session. | Initial `workflow launch` created tmux `re-ana-20260512_LH01106_0006_A23K3H2LT4` and repo `/fsx/analysis_results/johnm/re-ana-20260512_LH01106_0006_A23K3H2LT4/daylily-omics-analysis`; first dry-run failed because parallel staging collision corrupted remote `units.tsv` (`HG001-b` R1 `/fsx/r`, R2 empty). Restaged Run 1 to `/fsx/data/staged_sample_data/remote_stage_20260520T072438Z`, verified line lengths on headnode, copied clean config into the same repo, and reran in the same tmux session. Rerun dry-run reached `RETURN CODE: 0` before live execution. |
| `LAUNCH-001-LIVE` | `FAILED` | `re-ana-20260512_LH01106_0006_A23K3H2LT4` | Agent B / Orchestrator | Launch Run 1 command after dry-run passes. | Rerun live command in tmux `re-ana-20260512_LH01106_0006_A23K3H2LT4` ended with `RETURN CODE: 1`; tmux pane returned to `bash -il`. `status.rerun.json` was never written, and primary `status.json` still reflects the initial failed launch. Failure mode is disk exhaustion: `bin/day_run: line 204: daylily.failed_run: No space left on device`; all 40 sampled sent sort logs contained `No space left on device`; no final CRAM/VCF/alignstats/concordance/relatedness/contam/mosdepth/goleft/MultiQC outputs were present. |
| `LAUNCH-003-DRY` | `SUCCESS` | `re-ana-20260514_LH01106_0009_B23TVLGLT4` | Agent B / Orchestrator | `day-clone -t 1.0.17 -d <analysis_id>` then dry-run Run 3 command in persistent tmux login bash session. | Stage dir `/fsx/data/staged_sample_data/remote_stage_20260520T073058Z`; tmux session `re-ana-20260514_LH01106_0009_B23TVLGLT4`; repo `/fsx/analysis_results/johnm/re-ana-20260514_LH01106_0009_B23TVLGLT4/daylily-omics-analysis`; dry-run reached `RETURN CODE: 0` at `tmux.log` line 41494. The launch only succeeded after `BUGFIX-EC-001` exact-session tmux fix. |
| `LAUNCH-003-LIVE` | `FAILED` | `re-ana-20260514_LH01106_0009_B23TVLGLT4` | Agent B / Orchestrator | Launch Run 3 command after dry-run passes. | Live command in tmux `re-ana-20260514_LH01106_0009_B23TVLGLT4` ended with `RETURN CODE: 1`; status JSON has `exit_code=1`; tmux pane returned to `bash -il`. Failure mode is disk exhaustion: `bin/day_run: line 204: daylily.failed_run: No space left on device`; all 40 sampled sent sort logs contained `No space left on device`; no final CRAM/VCF/alignstats/concordance/relatedness/contam/mosdepth/goleft/MultiQC outputs were present. |
| `HYBRID-001` | `SUCCESS` | `re-ana-20260514_LH01106_0009_B23TVLGLT4-HG003-hybrid-ilmn-ont` | Agent D / Orchestrator | Verify hg38_broad-compatible ONT CRAM for HG003. | Selected `/fsx/data/genomic_data/organism_reads/H_sapiens/giab/agbt_2026/ont/HG003_30x.cleaned.cram`; `.crai` present; `htsfile` reports CRAM v3.0; cached `samtools 1.23.1` quickcheck passed; CRAM has 195 SQ records, all 195 are present in `hg38_broad` FASTA with identical lengths, zero missing-from-ref and zero length mismatches; chr1:100000000-101000000 decoded 1,000 records. Caveat: CRAM dictionary is a subset of the full 3,366-contig `hg38_broad` FASTA, not an identical full dictionary. |
| `HYBRID-002` | `FAILED` | `re-ana-20260514_LH01106_0009_B23TVLGLT4-HG003-hybrid-ilmn-ont` | Agent D / Orchestrator | Launch HG003 hybrid using Run 3 `HG003-a` comma-list ILMN plus verified ONT CRAM. | Stage dir `/fsx/data/staged_sample_data/remote_stage_20260520T072148Z`; tmux session `re-ana-20260514_LH01106_0009_B23TVLGLT4-HG003-hybrid-ilmn-ont`; dry-run reached `RETURN CODE: 0`; live Snakemake failed with `exit_code=1`. Failure was in rule `sentdhiom_sr_align` with ordered comma-list ILMN inputs plus ONT CRAM; rule log `.../align/ont/dmd/snv/sentdhiom/log/...ont.dmd.1-24.sr_align.log` reports `Error: Failed to write to .../vcfs/1-24/tmp/sr_aligned.bam: No space left on device` while `/fsx` was at `100%`. Early outputs present before failure: ONT CRAM/CRAI and one sentdhiom SV VCF. This is a disk-exhaustion failure, not evidence of comma-list FASTQ incompatibility. |
| `HYBRID-003` | `BLOCKED` | `re-ana-20260514_LH01106_0009_B23TVLGLT4-HG003-hybrid-ilmn-ont-concat-fallback` | Agent D / Orchestrator | Ordered concat fallback only if hybrid fails specifically on comma-list raw FASTQ handling. | Blocked until `HYBRID-002` proves fallback is needed. |
| `MONITOR-001` | `SUCCESS` | all live analysis ids | Agent E / Orchestrator | Track tmux sessions, Slurm job ids, terminal workflow status, and required artifacts. | Final monitor pass at 2026-05-20T10:58Z found no remaining Slurm jobs and all watched tmux panes back at `bash -il`. Run 1, Run 3, and Hybrid were terminal failed from FSx exhaustion, with `/fsx` at 100% and only 9.2G available; no post-completion kitchen-sink dry-runs were launched. |
| `POST-KS-001-DRY` | `BLOCKED` | `re-ana-20260512_LH01106_0006_A23K3H2LT4` | Orchestrator / Monitor | After the current Run 1 workflow is terminal successful, dry-run the expanded kitchen-sink targets with VEP, relatedness, contamination, and final MultiQC, using `--rerun-triggers mtime -n`. | Blocked because `LAUNCH-001-LIVE` failed before producing a valid terminal-success state. No post-completion kitchen-sink dry-run is allowed until FSx capacity is fixed and the base workflow is rerun or otherwise repaired. |
| `POST-KS-001-LIVE` | `BLOCKED` | `re-ana-20260512_LH01106_0006_A23K3H2LT4` | Orchestrator / Monitor | Run the Run 1 expanded kitchen-sink command only after `POST-KS-001-DRY` proves no unwanted upstream reruns. | Blocked on current workflow success and dry-run approval evidence. |
| `POST-KS-003-DRY` | `BLOCKED` | `re-ana-20260514_LH01106_0009_B23TVLGLT4` | Orchestrator / Monitor | After the current Run 3 workflow is terminal successful, dry-run the expanded kitchen-sink targets with VEP, relatedness, contamination, and final MultiQC, using `--rerun-triggers mtime -n`. | Blocked because `LAUNCH-003-LIVE` failed before producing a valid terminal-success state. No post-completion kitchen-sink dry-run is allowed until FSx capacity is fixed and the base workflow is rerun or otherwise repaired. |
| `POST-KS-003-LIVE` | `BLOCKED` | `re-ana-20260514_LH01106_0009_B23TVLGLT4` | Orchestrator / Monitor | Run the Run 3 expanded kitchen-sink command only after `POST-KS-003-DRY` proves no unwanted upstream reruns. | Blocked on current workflow success and dry-run approval evidence. |
| `POST-KS-HYB-DRY` | `BLOCKED` | `re-ana-20260514_LH01106_0009_B23TVLGLT4-HG003-hybrid-ilmn-ont` | Orchestrator / Monitor | After the current hybrid workflow is terminal successful, dry-run hybrid-compatible kitchen-sink additions with VEP, relatedness, contamination, and final MultiQC, using `--rerun-triggers mtime -n`. | Blocked because `HYBRID-002` failed before terminal success; no hybrid kitchen-sink dry-run is allowed until the disk-exhaustion failure is resolved and the hybrid workflow is rerun or otherwise brought to a valid terminal-success state. |
| `POST-KS-HYB-LIVE` | `BLOCKED` | `re-ana-20260514_LH01106_0009_B23TVLGLT4-HG003-hybrid-ilmn-ont` | Orchestrator / Monitor | Run the hybrid expanded kitchen-sink command only after `POST-KS-HYB-DRY` proves no unwanted upstream reruns and target compatibility. | Blocked on current workflow success and dry-run approval evidence. |
| `RETRY-003-CLEANUP` | `SUCCESS` | `re-ana-20260514_LH01106_0009_B23TVLGLT4` | Orchestrator | Delete the confirmed failed Run 3 partial analysis directory before retry. | User confirmed `CONFIRM DELETE FSX RUN3 PARTIAL ANALYSIS AND RETRY RUN3`. Removed `/fsx/analysis_results/johnm/re-ana-20260514_LH01106_0009_B23TVLGLT4` (`1.7T`), killed the stale tmux session, and archived `/home/ubuntu/daylily-runs/re-ana-20260514_LH01106_0009_B23TVLGLT4` to `.failed-20260520T223708Z`. `/fsx` recovered to about `1.7T` free. |
| `RETRY-003-FIRSTPASS` | `FAILED` | `re-ana-20260514_LH01106_0009_B23TVLGLT4` | Orchestrator / Monitor | Retry Run 3 through sent alignment, dmd dedup CRAM, sentd SNV VCF, SNV concordance, and alignstats using combined lane FASTQs. | Fresh `dyec workflow launch` using DayOA `1.0.17`, stage dir `/fsx/data/staged_sample_data/remote_stage_20260520T073058Z`, and tmux session `re-ana-20260514_LH01106_0009_B23TVLGLT4`. First-pass command dry-run returned `RETURN CODE: 0`, then live command started with `-j 12`; submitted Slurm jobs `698-709` for `sentieon_bwa_sort`. At 2026-05-20T23:10Z all 12 sort jobs were still running, status JSON remained `exit_code=None`, analysis size was `1.2T`, and `/fsx` had dropped to `396G` free (`97%` used). At 2026-05-20T23:40Z the retry was terminal failed: status JSON `exit_code=1`, no Slurm jobs remained, `/fsx` was back to `6.5G` free (`100%` used), no CRAM/VCF outputs were present, and logs reported `No space left on device` from `sentieon_bwa_sort` plus `bin/day_run: line 204: daylily.failed_run: No space left on device`. |
| `RETRY-003-KS-DRY` | `BLOCKED` | `re-ana-20260514_LH01106_0009_B23TVLGLT4` | Orchestrator / Monitor | If `RETRY-003-FIRSTPASS` succeeds, dry-run kitchen sink to final MultiQC with `--rerun-triggers mtime -n` before live launch. | Blocked because first-pass retry failed from FSx exhaustion before producing completed alignment/dedup/SNV outputs. |
| `RETRY-003-KS-LIVE` | `BLOCKED` | `re-ana-20260514_LH01106_0009_B23TVLGLT4` | Orchestrator / Monitor | Launch kitchen sink to final MultiQC only after dry-run confirms no unwanted upstream reruns. | Blocked on `RETRY-003-KS-DRY`. |
| `DRA-CLEANUP-003` | `SUCCESS` | n/a | Orchestrator | Delete all non-Run3 DRA associations on `dra-enabled`; preserve Run3 DRA. | User confirmed `CONFIRM DELETE DRA MOUNTS EXCEPT RUN3 AND DELETE FSX RUN3 PARTIAL ANALYSIS`. Deleted non-Run3 associations for Run 1 `dra-02d344e4dc8840a90`, ONT HG003 `dra-006ba927d666a551f`, and Run 0008 raw `dra-06d806e2e1413adf7`. `dyec mounts list` subsequently showed only Run3 `20260514_LH01106_0009_B23TVLGLT4` / `dra-0e036df15b52f3f85`. Cached `/fsx/run_dir_mounts/*` directories were not deleted. |
| `RETRY-003-CLEANUP-2` | `SUCCESS` | `re-ana-20260514_LH01106_0009_B23TVLGLT4` | Orchestrator | Delete failed Run3 partial analysis directory before a lower-concurrency retry. | Removed `/fsx/analysis_results/johnm/re-ana-20260514_LH01106_0009_B23TVLGLT4` (`1.4T`), killed stale tmux, and archived run state to `/home/ubuntu/daylily-runs/re-ana-20260514_LH01106_0009_B23TVLGLT4.failed-20260521T181258Z`. `/fsx` recovered to about `1.4T` free (`88%` used). |
| `RETRY-003-FIRSTPASS-J4` | `FAILED` | `re-ana-20260514_LH01106_0009_B23TVLGLT4` | Orchestrator / Monitor | Retry Run 3 through dmd dedup CRAM, sentd SNV VCF, SNV concordance, and alignstats using combined lane FASTQs, with reduced sort concurrency. | Launched fresh tmux session `re-ana-20260514_LH01106_0009_B23TVLGLT4` using DayOA `1.0.17`, stage dir `/fsx/data/staged_sample_data/remote_stage_20260520T073058Z`, and command `produce_dmd_dedup_cram produce_sentd_snv_vcf produce_snv_concordances produce_alignstats ... -j 4`. Dry-run returned `RETURN CODE: 0`; live command started and submitted Slurm jobs `734-737` for `sentieon_bwa_sort`. At 2026-05-21T18:48Z the four sort jobs were still running, status JSON remained `exit_code=None`, analysis size was `414G`, `/fsx` had `1007G` free (`91%` used), and no no-space or rule-error markers were observed. At 2026-05-21T19:18Z the first four sort jobs had completed, four new sort jobs `738-741` were running, status still `exit_code=None`, analysis size was `471G`, `/fsx` had `891G` free (`93%` used), and no no-space or rule-error markers were observed. At 2026-05-21T19:52Z jobs `738-741` were still running, status remained `exit_code=None`, analysis size had grown to `1.1T`, `/fsx` had `281G` free (`98%` used), `8` sent sort BAMs were present, and no no-space or rule-error markers were observed. At 2026-05-21T20:22Z jobs `742-745` were running, status remained `exit_code=None`, analysis size was still `1.1T`, `/fsx` had `299G` free (`98%` used), one OST was down to `19.2G` free (`99%` used), `8` sent sort BAMs were present, and no no-space or rule-error markers were observed. At 2026-05-21T20:52Z the workflow was terminal failed with `status.json exit_code=1`, no Slurm jobs remained, `/fsx` had only `5.5G` free (`100%` used), analysis size was `1.4T`, artifact probe found `0` CRAM, `0` CRAI, `0` VCFs, `8` sent sort BAMs, `137` temporary BAM shards, and logs showed repeated `Error in rule sentieon_bwa_sort` plus explicit `No space left on device` writes. |
| `RETRY-003-KS-DRY-2` | `BLOCKED` | `re-ana-20260514_LH01106_0009_B23TVLGLT4` | Orchestrator / Monitor | If `RETRY-003-FIRSTPASS-J4` succeeds, dry-run kitchen sink to final MultiQC with `--rerun-triggers mtime -n` before live launch. | Blocked because lower-concurrency first-pass retry failed from FSx exhaustion before completed alignment/dedup/SNV outputs were available. |
| `RETRY-003-KS-LIVE-2` | `BLOCKED` | `re-ana-20260514_LH01106_0009_B23TVLGLT4` | Orchestrator / Monitor | Launch kitchen sink to final MultiQC only after dry-run confirms no unwanted upstream reruns. | Blocked on `RETRY-003-KS-DRY-2`. |

## Monitoring Updates

### 2026-05-20T09:00Z heartbeat

- Headnode check ran through supported SSM as `ubuntu` on `dra-enabled`; no destructive action, export, delete-after-export, or Run 2 named-sample workflow was launched.
- `/fsx` capacity: `11T` size, `6.6T` used, `4.4T` available, `61%` used.
- Slurm queue: `201 RUNNING` jobs for `ubuntu`; grouped as 40 Run 1 `fastqc_subsampled`, 40 Run 1 `seqfu`, 20 Run 1 `sentieon_bwa_sort`, 40 Run 3 `fastqc_subsampled`, 40 Run 3 `seqfu`, 20 Run 3 `sentieon_bwa_sort`, and 1 hybrid `sentdhiom_sr_align`.
- Run 1 `re-ana-20260512_LH01106_0006_A23K3H2LT4`: live rerun remains active under tmux with Snakemake PID `355402` elapsed about `01:31`; primary `status.json` still records the earlier failed launch (`exit_code=1`) and `status.rerun.json` is not present yet. Process tree shows the live command is still running through `/home/ubuntu/rerun_run1_altair.sh`; repo size was `1.5T`; no final CRAM/VCF/alignstats/concordance/relatedness/contam/mosdepth/goleft/MultiQC artifact set was detected in the bounded probe.
- Run 3 `re-ana-20260514_LH01106_0009_B23TVLGLT4`: live workflow remains active with status `exit_code=null`; process tree shows Snakemake PID `412356` elapsed about `01:16`; log markers still show dry-run `RETURN CODE: 0` and submitted Slurm external job IDs through `517`.
- Hybrid `re-ana-20260514_LH01106_0009_B23TVLGLT4-HG003-hybrid-ilmn-ont`: live workflow remains active with status `exit_code=null`; process tree shows Snakemake PID `368505` elapsed about `01:28`; log markers show dry-run `RETURN CODE: 0`, live submitted external job IDs `415`, `416`, and `417`, and `Finished job 0` in the Snakemake log while the top-level Snakemake process is still present. Early hybrid artifacts include one `sentdhiom` SV VCF at `results/day/hg38/20260514-LH01106-0009-B23TVLGLT4-HG003-a-20260514-ILMN-Altair-Run-3-0-HG003-a-PF-ILMN-NOVASEQ/align/ont/dmd/sv/sentdhiom/20260514-LH01106-0009-B23TVLGLT4-HG003-a-20260514-ILMN-Altair-Run-3-0-HG003-a-PF-ILMN-NOVASEQ.ont.dmd.sentdhiom.sv.vcf.gz`.
- The broad artifact-count probe over live result trees timed out at 120 seconds; follow-up check found no leftover monitor-side `find` process on the headnode.
- No post-completion kitchen-sink dry-run was launched because none of the current Run 1, Run 3, or Hybrid workflows has a confirmed terminal-success status.

### 2026-05-20T09:28Z heartbeat

- Headnode check ran through supported SSM as `ubuntu` on `dra-enabled`; no destructive action, export, delete-after-export, Run 2 named-sample workflow, or live kitchen-sink command was launched.
- `/fsx` capacity: `11T` size, `8.4T` used, `2.6T` available, `77%` used. Lustre OSTs were balanced at roughly `77-78%` used; MDT was `3%` used.
- Slurm queue: `201 RUNNING` jobs for `ubuntu`, grouped as 40 Run 1 `fastqc_subsampled`, 40 Run 1 `seqfu`, 20 Run 1 `sentieon_bwa_sort`, 40 Run 3 `fastqc_subsampled`, 40 Run 3 `seqfu`, 20 Run 3 `sentieon_bwa_sort`, and 1 hybrid `sentdhiom_sr_align`.
- Run 1 `re-ana-20260512_LH01106_0006_A23K3H2LT4`: live rerun remains active under tmux with Snakemake PID `355402` elapsed about `01:57`; primary `status.json` still records the earlier failed launch (`exit_code=1`) and `status.rerun.json` is still absent. Repo size was `1.9T`; bounded artifact probe found zero final CRAM, CRAI, VCF, alignstats, concordance, relatedness, contamination, mosdepth summary, `goleft.done`, or MultiQC HTML outputs.
- Run 3 `re-ana-20260514_LH01106_0009_B23TVLGLT4`: live workflow remains active with status `exit_code=null`; Snakemake PID `412356` elapsed about `01:43`; log markers still show dry-run `RETURN CODE: 0` and submitted Slurm external job IDs through `517`. Repo size was `1.3T`; bounded artifact probe found zero final CRAM, CRAI, VCF, alignstats, concordance, relatedness, contamination, mosdepth summary, `goleft.done`, or MultiQC HTML outputs.
- Hybrid `re-ana-20260514_LH01106_0009_B23TVLGLT4-HG003-hybrid-ilmn-ont`: live workflow remains active with status `exit_code=null`; Snakemake PID `368505` elapsed about `01:55`; log markers show dry-run `RETURN CODE: 0`, submitted external job IDs `415`, `416`, `417`, and `Finished job 0` while the top-level Snakemake process remains present. Targeted artifact probe found 1 CRAM, 1 CRAI, and 1 `sentdhiom` SV VCF: `results/day/hg38/20260514-LH01106-0009-B23TVLGLT4-HG003-a-20260514-ILMN-Altair-Run-3-0-HG003-a-PF-ILMN-NOVASEQ/align/ont/20260514-LH01106-0009-B23TVLGLT4-HG003-a-20260514-ILMN-Altair-Run-3-0-HG003-a-PF-ILMN-NOVASEQ.cram`, matching `.cram.crai`, and `results/day/hg38/20260514-LH01106-0009-B23TVLGLT4-HG003-a-20260514-ILMN-Altair-Run-3-0-HG003-a-PF-ILMN-NOVASEQ/align/ont/dmd/sv/sentdhiom/20260514-LH01106-0009-B23TVLGLT4-HG003-a-20260514-ILMN-Altair-Run-3-0-HG003-a-PF-ILMN-NOVASEQ.ont.dmd.sentdhiom.sv.vcf.gz`.
- No post-completion kitchen-sink dry-run was launched because none of the current Run 1, Run 3, or Hybrid workflows has a confirmed terminal-success status. The next monitor pass should keep a close eye on `/fsx` free space before allowing any post-completion dry-runs.

### 2026-05-20T09:58Z heartbeat

- Headnode check ran through supported SSM as `ubuntu` on `dra-enabled`; no destructive action, export, delete-after-export, Run 2 named-sample workflow, Slurm cancellation, or kitchen-sink command was launched.
- `/fsx` reached critical capacity: first check showed `11T` size, `11T` used, `107G` available, `100%` used; follow-up at 2026-05-20T09:59:24Z showed `73G` available. Lustre OSTs were effectively full: OST0 `99%`, OST1 `99%`, OST2 `99%`, OST3 `100%`, OST4 `100%`, OST5 `100%`; MDT remained `3%`.
- Slurm queue at 09:58Z: `173 RUNNING`, `11 CONFIGURING`, `6 PENDING`; at 09:59Z: `165 RUNNING`, `10 CONFIGURING`. Work was still active rather than terminal.
- Run 1 `re-ana-20260512_LH01106_0006_A23K3H2LT4`: live rerun remained active under tmux with Snakemake PID `355402` elapsed about `02:27`; primary `status.json` still reflected the earlier failed launch (`exit_code=1`) and `status.rerun.json` remained absent. Repo size was `2.5T`; bounded artifact probe still found zero final CRAM, CRAI, VCF, alignstats, concordance, relatedness, contamination, mosdepth summary, `goleft.done`, or MultiQC HTML outputs. `tmux.log` advanced to 2026-05-20T09:58Z and showed repeated `Error in rule sentieon_bwa_sort` entries while continuing under `-k`.
- Run 3 `re-ana-20260514_LH01106_0009_B23TVLGLT4`: live workflow remained active with status `exit_code=null`; Snakemake PID `412356` elapsed about `02:13`. Repo size was not fully captured in the truncated output, but the live log mtime was 2026-05-20T09:57:51Z and showed repeated `Error in rule sentieon_bwa_sort` entries while continuing under `-k`.
- Per-rule error probes confirmed write failures in both Run 1 and Run 3 `sentieon_bwa_sort` logs. Examples include Run 1 `NA20208-a`, `NA07439-a`, `NA20241-a`, and `HG005-c` logs with `Error: Failed to write to .../align/sent/logs/../tmp/sentieon_sort_...`; Run 3 `BUCCAL2-b` and `HG003-b` logs showed the same `Error: Failed to write to .../sentieon_sort_...` pattern. Several other sent sort logs also showed SSL shutdown messages after the write failures. Combined with `/fsx` at `100%`, these failures are consistent with disk exhaustion during Sentieon sort scratch/output writes.
- Hybrid terminal state could not be fully captured in the first 09:58Z output because Run 1 and Run 3 error context consumed the output budget. The prior 09:28Z heartbeat had the hybrid workflow active with a produced ONT CRAM/CRAI and one sentdhiom SV VCF; no kitchen-sink dry-run was launched because the workset did not have confirmed terminal success in this heartbeat.
- No post-completion kitchen-sink dry-run was launched. The next operator decision should be about preserving evidence and freeing/expanding `/fsx` or intentionally stopping/restarting the affected alignment jobs; continuing to launch additional work while `/fsx` is full is unsafe.

### 2026-05-20T10:28Z heartbeat

- Headnode check ran through supported SSM as `ubuntu` on `dra-enabled`; no destructive action, export, delete-after-export, Run 2 named-sample workflow, Slurm cancellation, or kitchen-sink command was launched.
- `/fsx` remained critically full: `11T` size, `11T` used, `44G` available at 2026-05-20T10:28:36Z, then `40G` available at 2026-05-20T10:29:16Z. All six checked OSTs reported `100%`; MDT remained `3%`.
- Slurm queue had dropped to `35 RUNNING` jobs, all `fastqc_subsampled` jobs for Run 1 or Run 3. `sacct` did not show failed/cancelled/timeouts in the simple filtered view, but Snakemake logs showed many rule-level failures.
- Run 1 `re-ana-20260512_LH01106_0006_A23K3H2LT4`: Snakemake controller still active under tmux with PID `355402`, elapsed about `02:57`; primary `status.json` still reflected the earlier failed launch (`exit_code=1`) and `status.rerun.json` remained absent. Repo size was `2.5T`; bounded artifact probe still found zero final CRAM, CRAI, VCF, alignstats, concordance, relatedness, contamination, mosdepth summary, `goleft.done`, or MultiQC HTML outputs. Live log showed repeated `Error in rule sentieon_bwa_sort` plus `Error in rule fastqc_subsampled`; sampled sent sort logs contained explicit `No space left on device` write failures, for example `...BUCCAL7-a...sent.sort.bam_31_0_rWQksz.bam: No space left on device` and `...HG006-a...sent.sort.bam_15_0_rMKnVp.bam: No space left on device`.
- Run 3 `re-ana-20260514_LH01106_0009_B23TVLGLT4`: Snakemake controller still active under tmux with PID `412356`, elapsed about `02:43`; status JSON remained `exit_code=null`. Repo size was `1.7T`; bounded artifact probe still found zero final CRAM, CRAI, VCF, alignstats, concordance, relatedness, contamination, mosdepth summary, `goleft.done`, or MultiQC HTML outputs. Live log showed repeated `Error in rule fastqc_subsampled`; sampled sent sort logs contained explicit `No space left on device` write failures, for example `...HG006-a...sent.sort.bam_31_0_VPdVi4.bam: No space left on device` and `...HG003-c...sent.sort.bam_15_0_jBFGNn.bam: No space left on device`.
- Hybrid `re-ana-20260514_LH01106_0009_B23TVLGLT4-HG003-hybrid-ilmn-ont`: terminal failed with `status.json exit_code=1`; tmux pane had returned to an interactive `bash -il`. Error context shows rule `sentdhiom_sr_align` failed after retry external job `589`; the rule used Run 3 `HG003-a` ordered comma-list ILMN inputs plus the ONT CRAM/CRAI and attempted to write `.../align/ont/dmd/snv/sentdhiom/vcfs/1-24/tmp/sr_aligned.bam`. The rule log reports `Error: Failed to write to .../sr_aligned.bam: No space left on device`. Early artifacts remain: 1 ONT CRAM, 1 CRAI, and 1 sentdhiom SV VCF; no alignstats/concordance/relatedness/contam/mosdepth/MultiQC outputs.
- No post-completion kitchen-sink dry-runs were launched. `POST-KS-HYB-DRY` is now blocked by the failed hybrid row, and Run 1/Run 3 are not terminal-success. The operational blocker is FSx exhaustion, not a target-selection or comma-list FASTQ issue.

### 2026-05-20T10:58Z heartbeat

- Headnode check ran through supported SSM as `ubuntu` on `dra-enabled`; no destructive action, export, delete-after-export, Run 2 named-sample workflow, Slurm cancellation, or kitchen-sink dry-run was launched.
- `/fsx` was full: `11T` size, `11T` used, `9.2G` available, `100%` used. All six checked OSTs reported `100%` used with less than 1.5G free on each; MDT remained `3%`.
- Slurm queue for `ubuntu` was empty. The three watched tmux panes were back at `bash -il`, with no top-level Snakemake subprocess left to monitor.
- Run 1 `re-ana-20260512_LH01106_0006_A23K3H2LT4`: terminal failed from the monitor perspective. `status.rerun.json` was absent and primary `status.json` still reflected the earlier failed launch, but `tmux.log` ended with `bin/day_run: line 204: daylily.failed_run: No space left on device` and `RETURN CODE: 1`. Repo size was `2.5T`; bounded artifact probe found zero final CRAM, CRAI, VCF, alignstats, concordance, relatedness, contamination, mosdepth summary, `goleft.done`, or MultiQC HTML outputs. All 40 sampled `sentieon_bwa_sort` logs contained `No space left on device` hits.
- Run 3 `re-ana-20260514_LH01106_0009_B23TVLGLT4`: terminal failed. `status.json` had `exit_code=1`, `status.rerun.json` was absent, and `tmux.log` ended with `bin/day_run: line 204: daylily.failed_run: No space left on device` and `RETURN CODE: 1`. Repo size was `1.7T`; bounded artifact probe found zero final CRAM, CRAI, VCF, alignstats, concordance, relatedness, contamination, mosdepth summary, `goleft.done`, or MultiQC HTML outputs. All 40 sampled `sentieon_bwa_sort` logs contained `No space left on device` hits.
- Hybrid `re-ana-20260514_LH01106_0009_B23TVLGLT4-HG003-hybrid-ilmn-ont`: remained terminal failed with `status.json exit_code=1`. The failure was still `sentdhiom_sr_align` writing `.../vcfs/1-24/tmp/sr_aligned.bam`, with the rule log reporting `No space left on device`. Early outputs remained limited to one ONT CRAM, one CRAI, and one sentdhiom SV VCF.
- Post-completion kitchen-sink rows remain blocked because no watched workflow reached terminal success. The monitor objective is now terminal with failed analyses; operator remediation is required for FSx capacity before rerun or cleanup decisions.

### 2026-05-20T23:10Z heartbeat

- Headnode check ran through supported SSM as `ubuntu` on `dra-enabled`; no destructive action, export, unmount, Slurm cancellation, or kitchen-sink dry-run/live command was launched.
- Run 3 retry `re-ana-20260514_LH01106_0009_B23TVLGLT4` remained active. `status.json` had `exit_code=None`, tmux pane `re-ana-20260514_LH01106_0009_B23TVLGLT4` was present, and Slurm showed all 12 submitted `sentieon_bwa_sort` jobs `698-709` in `RUNNING` state with elapsed times around 27 minutes.
- `/fsx` capacity was tight again: `11T` size, `11T` used, `396G` available, `97%` used; Lustre summary reported `10.9T` total, `10.5T` used, `394.2G` available.
- Analysis directory size was `1.2T`. Artifact probe found `0` CRAMs, `0` CRAIs, `0` VCFs, `1` alignstats TSV, `4` concordance TSVs, `84` temporary BAM shards, and no `No space left on device` or `Error in rule` markers in the sampled log output.
- No kitchen-sink dry-run was launched because first pass has not reached terminal success. The immediate risk is FSx capacity while the 12 large sort jobs are still running.

### 2026-05-20T23:40Z heartbeat

- Headnode check ran through supported SSM as `ubuntu` on `dra-enabled`; no destructive action, export, unmount, Slurm cancellation, or kitchen-sink dry-run/live command was launched.
- Run 3 retry `re-ana-20260514_LH01106_0009_B23TVLGLT4` reached terminal failure. `status.json` had `exit_code=1`, no Slurm jobs remained, and the tmux pane was back at `bash`.
- `/fsx` was full again: `11T` size, `11T` used, `6.5G` available, `100%` used; Lustre summary reported `10.9T` total, `10.9T` used, `6.4G` available. All ten OSTs reported `100%` used.
- Analysis directory size was `1.4T`. Artifact probe found `0` CRAMs, `0` CRAIs, `0` VCFs, `1` alignstats TSV, `4` concordance TSVs, `200` temporary BAM shards, and `0` final sent sort BAMs.
- Log markers showed repeated `Error in rule sentieon_bwa_sort`, then `OSError: [Errno 28] No space left on device` in `.snakemake/incomplete/...`, `bin/day_run: line 204: daylily.failed_run: No space left on device`, and final `RETURN CODE: 1`.
- Recent per-sample sent sort logs contained explicit no-space failures, including `BUCCAL3-b`, `HG005-a`, `HG003-a`, `NA05115-a`, `BUCCAL2-b`, `HG004-a`, `BUCCAL9-a`, `HG002-a`, `BUCCAL2-a`, `HG001-c`, `BUCCAL3-a`, `NA20208-a`, `NA20241-a`, `NA07439-a`, `HG003-b`, `HG002-c`, `BUCCAL6-a`, `NA05212-a`, `HG004-b`, `HG002-b`, `HG003-c`, and `BUCCAL5-a`.
- No kitchen-sink dry-run was launched because first pass failed before producing completed alignment/dedup/SNV outputs. The retry monitor objective is terminal with failure; further progress requires capacity remediation and a new operator decision.

### 2026-05-21T18:48Z heartbeat

- Headnode check ran through supported SSM as `ubuntu` on `dra-enabled`; no destructive action, export, unmount, Slurm cancellation, or kitchen-sink dry-run/live command was launched.
- Lower-concurrency Run 3 retry `re-ana-20260514_LH01106_0009_B23TVLGLT4` remained active. `status.json` had `exit_code=None`, tmux pane `re-ana-20260514_LH01106_0009_B23TVLGLT4` was present, and Slurm showed four `sentieon_bwa_sort` jobs `734-737` in `RUNNING` state with elapsed times around 27 minutes.
- `/fsx` capacity was improved relative to the failed `-j 12` retry: `11T` size, `9.9T` used, `1007G` available, `91%` used; Lustre summary reported `10.9T` total, `9.9T` used, `1006.4G` available. OSTs ranged from `91%` to `92%` used with roughly `95G-105G` free each.
- Analysis directory size was `414G`. Artifact probe found `0` CRAMs, `0` CRAIs, `0` VCFs, `1` alignstats TSV, `4` concordance TSVs, `28` temporary BAM shards, and no final sent sort BAMs yet.
- Log markers still showed the dry-run `RETURN CODE: 0`, live DAG build, completed setup jobs `8-10`, and submitted sort jobs `734-737`; no `No space left on device`, `Error in rule`, or recent sent sort log errors were observed.
- No kitchen-sink dry-run was launched because first pass has not reached terminal success.

### 2026-05-21T19:18Z heartbeat

- Headnode check ran through supported SSM as `ubuntu` on `dra-enabled`; no destructive action, export, unmount, Slurm cancellation, or kitchen-sink dry-run/live command was launched.
- Lower-concurrency Run 3 retry `re-ana-20260514_LH01106_0009_B23TVLGLT4` remained active. `status.json` had `exit_code=None`, tmux pane `re-ana-20260514_LH01106_0009_B23TVLGLT4` was present, and Slurm showed four `sentieon_bwa_sort` jobs `738-741` in `RUNNING` state. The first four sort jobs `734-737` had finished, and Snakemake submitted the next four sort jobs.
- `/fsx` remained tight but not full: `11T` size, `11T` used, `891G` available, `93%` used; Lustre summary reported `10.9T` total, `10.0T` used, `889.3G` available. OSTs were `92%` to `93%` used with roughly `82G-92G` free each.
- Analysis directory size was `471G`. Artifact probe found `4` final sent sort BAMs, `28` temporary BAM shards, `0` CRAMs, `0` CRAIs, `0` VCFs, `1` alignstats TSV, and `4` concordance TSVs.
- Log markers showed the dry-run `RETURN CODE: 0`, finished sort jobs `658`, `82`, `602`, and `610`, and submitted sort jobs `738-741`; no `No space left on device`, `Error in rule`, or recent sent sort log errors were observed.
- No kitchen-sink dry-run was launched because first pass has not reached terminal success.

### 2026-05-21T19:52Z heartbeat

- Headnode check ran through supported SSM as `ubuntu` on `dra-enabled`; no destructive action, export, unmount, Slurm cancellation, or kitchen-sink dry-run/live command was launched.
- Lower-concurrency Run 3 retry `re-ana-20260514_LH01106_0009_B23TVLGLT4` remained active. `status.json` had `exit_code=None`, tmux pane `re-ana-20260514_LH01106_0009_B23TVLGLT4` was present, and Slurm showed four `sentieon_bwa_sort` jobs `738-741` still `RUNNING` with elapsed times around `39-45` minutes.
- `/fsx` was again near capacity: `11T` size, `11T` used, `281G` available, `98%` used; Lustre summary reported `10.9T` total, `10.6T` used, `280.8G` available. OSTs were all `98%` used with roughly `24G-33G` free each.
- Analysis directory size was `1.1T`. Artifact probe found `8` final sent sort BAMs, `28` temporary BAM shards, `0` CRAMs, `0` CRAIs, `0` VCFs, `1` alignstats TSV, and `4` concordance TSVs.
- Log markers still showed no `No space left on device`, `Error in rule`, or recent sent sort log errors, but the free-space margin is now small.
- No kitchen-sink dry-run was launched because first pass has not reached terminal success.

### 2026-05-21T20:22Z heartbeat

- Headnode check ran through supported SSM as `ubuntu` on `dra-enabled`; no destructive action, export, unmount, Slurm cancellation, or kitchen-sink dry-run/live command was launched.
- Lower-concurrency Run 3 retry `re-ana-20260514_LH01106_0009_B23TVLGLT4` remained active. `status.json` had `exit_code=None`, tmux pane `re-ana-20260514_LH01106_0009_B23TVLGLT4` was present, and Slurm showed four `sentieon_bwa_sort` jobs `742-745` in `RUNNING` state with elapsed times around `21-28` minutes. Jobs `738-741` had completed and Snakemake submitted the next four sort jobs.
- `/fsx` remained near capacity: `11T` size, `11T` used, `299G` available, `98%` used; Lustre summary reported `10.9T` total, `10.6T` used, `296.4G` available. OSTs ranged from `97%` to `99%` used, and OST0 had only `19.2G` free.
- Analysis directory size remained `1.1T`. Artifact probe found `8` final sent sort BAMs, `28` temporary BAM shards, `0` CRAMs, `0` CRAIs, `0` VCFs, `1` alignstats TSV, and `4` concordance TSVs.
- Log markers showed finished jobs `108`, `642`, `578`, and `214`, with new submitted Slurm job IDs `742-745`; no `No space left on device`, `Error in rule`, or recent sent sort log errors were observed.
- No kitchen-sink dry-run was launched because first pass has not reached terminal success.

### 2026-05-21T20:52Z heartbeat

- Headnode check ran through supported SSM as `ubuntu` on `dra-enabled`; no destructive action, export, unmount, Slurm cancellation, or kitchen-sink dry-run/live command was launched.
- Lower-concurrency Run 3 retry `re-ana-20260514_LH01106_0009_B23TVLGLT4` reached terminal failure. `status.json` had `exit_code=1`, the tmux pane remained present, and no Slurm jobs remained for `ubuntu`.
- `/fsx` was full again: `11T` size, `11T` used, `5.5G` available, `100%` used; Lustre summary reported `10.9T` total, `10.9T` used, `5.4G` available. OSTs were all `100%` used, with several below `400M` free and OST6 at `32.2M` free.
- Analysis directory size was `1.4T`. Artifact probe found `0` CRAMs, `0` CRAIs, `0` VCFs, `1` alignstats TSV, `4` concordance TSVs, `137` temporary BAM shards, `8` final sent sort BAMs, `0` dedup BAMs, and no MultiQC HTML.
- Log markers showed repeated `Error in rule sentieon_bwa_sort`, retries through external Slurm job IDs `746-763`, `OSError: [Errno 28] No space left on device` in `.snakemake/incomplete`, `bin/day_run: line 204: daylily.failed_run: No space left on device`, and final `RETURN CODE: 1`.
- Recent sent sort logs contained explicit no-space write/open failures for samples including `BUCCAL3-b`, `HG005-a`, `HG003-a`, `NA15849-a`, `HG001-c`, `BUCCAL2-a`, `BUCCAL3-a`, `NA20241-a`, `HG003-b`, `HG003-c`, and `HG004-b`.
- No kitchen-sink dry-run was launched because first pass failed before producing completed alignment/dedup/SNV outputs.

## Required Live Commands

Run 1 and Run 3 dry-run first with `-n`, then live without `-n`:

```bash
bin/day_run produce_sent_align produce_dmd_dedup_cram produce_sentd_snv_vcf produce_snv_concordances produce_alignstats produce_relatedness produce_contam_estimate produce_verifybamid2_panel_comparison produce_mosdepth produce_multiqc_cram --config 'aligners=["sent"]' 'dedupers=["dmd"]' 'snv_callers=["sentd"]' 'multiqc_qc={"include_no_dedup_alignment_qc":false}' -p -j 100 -k -T 1
```

Hybrid first attempt:

```bash
bin/day_run produce_snv_concordances produce_sentdhiom_sv produce_sentdhiom_snv_vcf --config 'dedupers=["dmd"]' -p -j 100 -k
```

Post-completion Run 1 and Run 3 kitchen-sink dry-run command, then live command only after confirming no alignment/dedup/SNV reruns are scheduled:

```bash
bin/day_run produce_sent_align produce_dmd_dedup_cram produce_sentd_snv_vcf produce_alignstats produce_snv_concordances produce_relatedness produce_contam_estimate produce_verifybamid2_panel_comparison produce_vep produce_multiqc_all --config 'aligners=["sent"]' 'dedupers=["dmd"]' 'snv_callers=["sentd"]' 'multiqc_qc={"enable_tools":["vep"]}' -p -j 100 -k -T 1 --rerun-triggers mtime -n
```

Post-completion hybrid kitchen-sink dry-run command to test compatibility, then live command only after confirming no completed hybrid upstream work is scheduled for rerun:

```bash
bin/day_run produce_snv_concordances produce_sentdhiom_sv produce_sentdhiom_snv_vcf produce_relatedness produce_contam_estimate produce_verifybamid2_panel_comparison produce_vep produce_multiqc_all --config 'dedupers=["dmd"]' 'multiqc_qc={"enable_tools":["vep"]}' -p -j 100 -k --rerun-triggers mtime -n
```

## Acceptance Evidence Checklist

- Run 1 and Run 3: dmd/sent CRAMs, SNV VCFs, concordance TSV, alignstats TSVs, relatedness output, contamination output, mosdepth summaries, and `goleft.done`.
- Run 2: unexpected-index report only, with no named-sample workflow launch.
- Hybrid: successful HG003 hybrid, or exact comma-list failure plus successful ordered concat fallback.
- Final report: each analysis id, tmux session, Slurm job ids, terminal status, and key artifact paths.
