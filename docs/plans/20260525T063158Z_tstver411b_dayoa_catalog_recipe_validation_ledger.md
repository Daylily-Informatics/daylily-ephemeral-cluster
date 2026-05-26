# tstVer4-1-1b DayOA Catalog Recipe Validation Ledger

Created: 2026-05-25T06:31:58Z

## Objective

Create a new DAY-EC cluster named `tstVer4-1-1b` in `us-west-2d` based on prior `tstVer4-1-1` settings, with FSx size `12000` GiB, then re-run the fork-fixer DayOA catalog validation matrix. Hybrid workflows must use `r`-suffixed rule families where available; retired non-`r` hybrid targets must not be executed.

No teardown, DRA deletion, cleanup, export, or other destructive AWS action is in scope. The final matrix report path is `docs/tstver411b_command_catalog_test_results.md`.

## Gate 0 Baseline

| Field | Value |
|---|---|
| Workspace | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| Branch | `codex/analysis-id-export-catalog-validation` tracking `origin/codex/analysis-id-export-catalog-validation` |
| HEAD | `012a3b5b30d2e69a07aa80dd4c224ad1ee26d3a4` / tag `4.1.3` |
| `git describe` | `4.1.3-dirty` |
| Pre-existing dirty files | `config/day_cluster/post_install_ubuntu_combined.sh`, `daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh`, `tests/test_headnode_init.py` |
| Pre-existing untracked paths | Prior cost/cluster ledgers and reports under `docs/`, `docs/plans/`, `tmp/`, and `fill_in_the_blanks_lims.md`; none are reverted by this ledger. |
| DAY-EC local package | `daylily-ephemeral-cluster 4.1.3.dev0+g6531a5307.d20260523` |
| Clean source requirement | Use a separate clean worktree at tag `4.1.3` for `dyec preflight/create`; keep this ledger/report in the current worktree. |
| AWS profile | `lsmc` |
| AWS identity | `arn:aws:iam::108782052779:root` in account `108782052779` |
| Region/AZ | `us-west-2` / `us-west-2d` |
| Existing clusters in `us-west-2` | `fork-fixer` `CREATE_COMPLETE`, `hyb-hg003` `CREATE_COMPLETE`; no `tstVer4-1-1b` observed at Gate 0. |
| Prior source cluster | `tstVer4-1-1` was previously deleted; old rendered config used headnode `r7i.4xlarge`, queue max counts of `1`, FSx `4800` GiB, and the same subnets, bucket, IAM policy, budget, heartbeat, and template. |
| Ledger path | `docs/plans/20260525T063158Z_tstver411b_dayoa_catalog_recipe_validation_ledger.md` |
| Cluster config path | `docs/plans/20260525T063158Z_tstver411b_cluster_config.yaml` |

## Cluster Config Values

| Key | Value |
|---|---|
| `cluster_name` | `tstVer4-1-1b` |
| `budget_email` | `johnm@lsmc.com` |
| `heartbeat_email` | `johnm@lsmc.com` |
| `fsx_fs_size` | `12000` GiB |
| `headnode_instance_type` | `r7i.4xlarge` |
| `cluster_template_yaml` | `config/day_cluster/prod_cluster.yaml` |
| `max_count_8I` | `1` |
| `max_count_128I` | `1` |
| `max_count_192I` | `1` |
| `max_count_192I` template behavior | Applies to `i192`, `i192mem`, and `i192bigmem`. |
| `public_subnet_id` | `subnet-0e9acb65aba5a0330` |
| `private_subnet_id` | `subnet-087a4872d0c34e642` |
| `iam_policy_arn` | `arn:aws:iam::108782052779:policy/pclusterTagsAndBudget` |
| `s3_bucket_name` | `lsmc-dayoa-omics-analysis-us-west-2` |

## Ledger Rows

| ID | Owner | Requirement | Gate | Status | Evidence |
|---|---|---|---|---|---|
| `G0-001` | Orchestrator | Record repo state, DAY-EC version, AWS identity, prior `tstVer4-1-1` settings, no-teardown boundary, and report paths. | Gate 0 | `SUCCESS` | Baseline recorded above. |
| `CFG-001` | Cluster Agent | Render `tstVer4-1-1b` config from `tstVer4-1-1` settings with FSx `12000` GiB. | Gate 1 | `SUCCESS` | Created `docs/plans/20260525T063158Z_tstver411b_cluster_config.yaml`. |
| `PRE-001` | Cluster Agent | Run `dyec preflight --profile lsmc --region-az us-west-2d --config <config> --non-interactive`; block on quota/config errors. | Gate 1 | `SUCCESS` | Clean worktree `/tmp/dayec_tstver411b_413` at tag `4.1.3`; `dyec preflight --profile lsmc --region-az us-west-2d --config /Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/plans/20260525T063158Z_tstver411b_cluster_config.yaml --non-interactive` passed 12 checks: IAM global/regional, pcluster policy, repository catalog, on-demand/spot/vpc/EIP/NAT/IGW quota, S3 bucket select/verify. Preflight state: `/Users/jmajor/.config/daylily/preflight_tstVer4-1-1b_20260525063455.json`. |
| `CREATE-001` | Cluster Agent | Run `dyec create --profile lsmc --region-az us-west-2d --config <config> --non-interactive`; monitor until `CREATE_COMPLETE` and compute fleet `RUNNING`. | Gate 2 | `SUCCESS_WITH_CONFIG_RETRY` | `dyec create --profile lsmc --region-az us-west-2d --config /Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/plans/20260525T063158Z_tstver411b_cluster_config.yaml --non-interactive` created the cluster in `34m21s`. Rendered YAML `/Users/jmajor/.config/daylily/tstVer4-1-1b_cluster_20260525063533.yaml` has headnode `r7i.4xlarge`, FSx `StorageCapacity: 12000`, project/cluster tags `tstVer4-1-1b`, and queue `MaxCount: 1` for `i8`, `i128`, `i192`, `i192mem`, and `i192bigmem`. Final describe: cluster `CREATE_COMPLETE`, compute fleet `RUNNING`, headnode `i-0e08d1087dcce4d0a`, FSx `fs-0445f465f1a8d6b48`, DRA `dra-02c0d074383f04c9c`. Automatic post-create headnode configuration failed from detached clean worktree with `Could not resolve headnode repository source: fatal: ref HEAD is not a symbolic ref`; recovery is tracked under `BOOT-001`. |
| `BOOT-001` | Headnode Agent | Verify ubuntu SSM shell, `/fsx`, DRA, `day-clone`, `dyec`, Slurm partitions, and queue. | Gate 2 | `SUCCESS` | Automatic headnode configure failed from detached clean worktree, then recovery `dyec headnode configure --profile lsmc --region us-west-2 --cluster tstVer4-1-1b` succeeded from branch `codex/analysis-id-export-catalog-validation`. Boot verification SSM command `374552c8-463b-4e76-9dcf-7c41d0f6a47f` ran as `ubuntu`; `/fsx` mounted Lustre with `11T` available, `/fsx/references` present read-only, DRA `dra-02c0d074383f04c9c` `AVAILABLE`, `day-clone`, `dyec`, `squeue`, `sinfo`, and `lfs` available. Slurm partitions present: `i8`, `i128`, `i192`, `i192mem`, `i192bigmem`; `squeue -h` empty. Headnode DAY-EC version `4.1.3`. |
| `CAT-001` | Catalog Agent | Snapshot current catalog commands and DayOA tag, expected `1.0.21`; identify `r`-suffix hybrid substitutions. | Gate 3 | `SUCCESS` | `dyec repositories commands --repository daylily-omics-analysis` reports catalog version `2`, default repository `daylily-omics-analysis`, default ref `1.0.21`, and 13 command rows. Workflow clones resolved DayOA tag `1.0.21` to commit `c2ffe93f246ff19c346f0a99e04fddc9e2712ff3`. Current DAY-EC catalog has `hybrid_ilmn_ont_snv` using `produce_sentdhiomr_sv produce_sentdhiomr_snv_vcf`. Catalog still lists old `hybrid_ultima_ont_snv` command `produce_sentdhuom_snv_vcf`, so this run will override only after proving DayOA tag `1.0.21` exposes `produce_sentdhuomr_snv_vcf`. Local tag inspection of `/Users/jmajor/projects/daylily/daylily-omics-analysis` at `1.0.21` found `config/workflow_target_aliases.tsv:42` alias `produce_sentdhuomr_snv_vcf -> produce_sentdhuomr_vcf` plus `workflow/rules/sent_hybrid_ug_ont_modular.refactored.smk` rules, including `produce_sentdhuomr_vcf` and `produce_sentdhuomr_sv`. |
| `DATA-001` | Data Agent | Build low-coverage input manifests and run contexts; no silent substitutions. | Gate 3 | `SUCCESS_WITH_BLOCKERS` | Created new local input artifacts under `docs/plans/20260525T063158Z_tstver411b_inputs/`. All eight sample manifest mechanical prechecks passed. Source sizes verified: ILMN R1/R2 `3,902,280,885`/`4,023,184,443` bytes; ONT CRAM/CRAI `5,260,585,144`/`34,592`; Ultima CRAM/CRAI `8,356,213,863`/`136,673`; PacBio BAM/BAI `6,915,253,876`/`16`; Roche BAM/BAI `50,124,943,440`/`10,035,552`. Hybrid Ultima+ONT manifest explicitly uses `STAGE_DIRECTIVE=pass_through` and distinct `/data/.../ug/HG003_5x.cleaned.cram` and `/data/.../ont/HG003_5x.cleaned.cram` paths to avoid known identical-basename staging collision. CG/MGI remains blocked despite mechanical precheck because `_386_1` is `90,600,002,744` bytes, `_386_2` is `10,794,018,984` bytes, and nearby `_388_2` is `97,844,317,264` bytes; no substitution is authorized. |
| `STAGE-001` | Staging Agent | Stage sample-analysis data and validate generated TSVs. | Gate 4 | `SUCCESS_WITH_BLOCKERS` | Sample staging succeeded for all non-CG sample-analysis dry-runs. Stage dirs: ILMN `/fsx/staging/staged_sample_data/remote_stage_20260525T071517Z`; ILMN full QC `/fsx/staging/staged_sample_data/remote_stage_20260525T072540Z`; Ultima `/fsx/staging/staged_sample_data/remote_stage_20260525T072907Z`; ONT `/fsx/staging/staged_sample_data/remote_stage_20260525T073112Z`; PacBio `/fsx/staging/staged_sample_data/remote_stage_20260525T073306Z`; Roche `/fsx/staging/staged_sample_data/remote_stage_20260525T073504Z`; ILMN+ONT `/fsx/staging/staged_sample_data/remote_stage_20260525T074001Z`; Ultima+ONT `/fsx/staging/staged_sample_data/remote_stage_20260525T074404Z`. Ultima+ONT generated TSV has distinct pass-through paths: UG `/fsx/references/.../ug/HG003_5x.cleaned.cram` at `8,356,213,863` bytes and ONT `/fsx/references/.../ont/HG003_5x.cleaned.cram` at `5,260,585,144` bytes. Run-context DRAs created and verified: ILMN `dra-073d8c1fbda87df4d`, ONT `dra-062bb9457a8117d57`, Ultima `dra-0a246cd72f629eeef`, all `AVAILABLE`. CG/MGI blocked by unverified mate-pair contract. |
| `DRY-001` | Workflow Agents | Dry-run every recipe before live execution. | Gate 5 | `SUCCESS_WITH_FAILURES_AND_BLOCKERS` | Dry-run gate complete. Passed dry-runs: `illumina_snv_alignstats`, `illumina_snv_alignstats_relatedness_vep_multiqc`, `ultima_snv_alignstats`, `ont_snv_alignstats`, `pacbio_snv_alignstats`, `hybrid_ilmn_ont_snv` using `sentdhiomr`, and `hybrid_ultima_ont_snv` using `sentdhuomr`. Failed dry-runs: Roche missing Singularity image; `illumina_run_qc`, `ont_run_qc`, and `ultima_run_qc` missing `config/units.tsv`; `illumina_bclconvert` reports `No read pairs specified for analysis unit 20260514_LH01106_0009_B23TVLGLT4`. Blocked before dry-run: CG/MGI mate-pair contract. |
| `LIVE-001` | Workflow Agents | Run `illumina_snv_alignstats` after dry-run passes. | Gate 6 | `SUCCESS` | Dry-run `tvb_illumina_snv_alignstats_5x_1021_dryrun` completed `2026-05-25T07:18:38Z` with `exit_code=0`; live `tvb_illumina_snv_alignstats_5x_1021` completed `2026-05-25T09:20:32Z` with `exit_code=0`; no Slurm jobs remained. Output evidence under `/fsx/analysis_results/johnm/tvb_illumina_snv_alignstats_5x_1021/daylily-omics-analysis/results/day/hg38_broad/`: CRAM count `2`, VCF count `1`, alignstats matched `15` files, concordance matched `7` files including `concordance.done`. |
| `LIVE-002` | Workflow Agents | Run `illumina_snv_alignstats_relatedness_vep_multiqc` after dry-run passes. | Gate 6 | `SUCCESS` | Dry-run `tvb_illumina_related_vep_multiqc_5x_1021_dryrun` completed `2026-05-25T07:27:36Z` with `exit_code=0`; live `tvb_illumina_related_vep_multiqc_5x_1021` completed `2026-05-25T10:10:02Z` with `exit_code=0`; output evidence under `/fsx/analysis_results/johnm/tvb_illumina_related_vep_multiqc_5x_1021/daylily-omics-analysis/results/day/hg38_broad/`: 2 CRAM, 52 VCF, 17 alignstats matches, 8 concordance matches, 36 MultiQC matches, 7 relatedness matches. |
| `LIVE-003` | Workflow Agents | Run `ultima_snv_alignstats` after dry-run passes. | Gate 6 | `SUCCESS` | Dry-run `tvb_ultima_snv_alignstats_5x_1021_dryrun` completed `2026-05-25T07:30:54Z` with `exit_code=0`; live `tvb_ultima_snv_alignstats_5x_1021` completed `2026-05-25T10:18:07Z` with `exit_code=0`; output evidence under `/fsx/analysis_results/johnm/tvb_ultima_snv_alignstats_5x_1021/daylily-omics-analysis/results/day/hg38_broad/`: 1 VCF, 11 alignstats matches, 7 concordance matches. |
| `LIVE-004` | Workflow Agents | Run `ont_snv_alignstats` after dry-run passes. | Gate 6 | `SUCCESS` | Dry-run `tvb_ont_snv_alignstats_5x_1021_dryrun` completed `2026-05-25T07:32:48Z` with `exit_code=0`; live `tvb_ont_snv_alignstats_5x_1021` completed `2026-05-25T10:34:37Z` with `exit_code=0`; output evidence under `/fsx/analysis_results/johnm/tvb_ont_snv_alignstats_5x_1021/daylily-omics-analysis/results/day/hg38_broad/`: 2 VCF, 11 alignstats matches, 7 concordance matches. |
| `LIVE-005` | Workflow Agents | Run `pacbio_snv_alignstats` after dry-run passes. | Gate 6 | `SUCCESS` | Dry-run `tvb_pacbio_snv_alignstats_5x_1021_dryrun` completed `2026-05-25T07:34:45Z` with `exit_code=0`; live `tvb_pacbio_snv_alignstats_5x_1021` completed `2026-05-25T11:12:49Z` with `exit_code=0`; output evidence under `/fsx/analysis_results/johnm/tvb_pacbio_snv_alignstats_5x_1021/daylily-omics-analysis/results/day/hg38_broad/`: 1 CRAM, 2 VCF, 11 alignstats matches, 7 concordance matches. |
| `LIVE-006` | Workflow Agents | Run `roche_snv_alignstats` after dry-run passes. | Gate 6 | `FAILED` | Dry-run `tvb_roche_snv_alignstats_5x_1021_dryrun` completed `2026-05-25T07:39:43Z` with `exit_code=1`; live not launched. Failure reproduces fork-fixer pattern on this new cluster: missing Singularity image `/fsx/resources/environments/containers/ubuntu/ip-10-0-0-103/7a424a40c6fd659f4d052893dd3554fa.simg` while preparing containerized conda environment for Roche/GATK images. |
| `LIVE-007` | Workflow Agents | Run `hybrid_ilmn_ont_snv` with `sentdhiomr` after dry-run passes. | Gate 6 | `SUCCESS` | Dry-run `tvb_hybrid_ilmn_ont_snv_5x5x_1021_dryrun` completed `2026-05-25T07:42:08Z` with `exit_code=0`; command used `produce_sentdhiomr_sv produce_sentdhiomr_snv_vcf`; stage `/fsx/staging/staged_sample_data/remote_stage_20260525T074001Z`; live `tvb_hybrid_ilmn_ont_snv_5x5x_1021` launched `2026-05-25T11:13:04Z` and completed `2026-05-25T19:32:57Z` with `exit_code=0`. Output evidence under `/fsx/analysis_results/johnm/tvb_hybrid_ilmn_ont_snv_5x5x_1021/daylily-omics-analysis/results/day/hg38_broad/`: final `sentdhiomr.snv.sort.vcf.gz` plus `.tbi`, per-region HIOMR VCFs, `sentdhiomr.sv.vcf.gz` plus `.tbi`, and 7 concordance matches including `concordance.done`. |
| `LIVE-008` | Workflow Agents | Run `hybrid_ultima_ont_snv` only with `sentdhuomr` if available; otherwise block. | Gate 6 | `FAILED` | DayOA tag `1.0.21` exposes `produce_sentdhuomr_snv_vcf`. Dry-run override `tvb_hybrid_ultima_ont_snv_5x5x_1021_dryrun` completed `2026-05-25T07:46:05Z` with `exit_code=0`; stage `/fsx/staging/staged_sample_data/remote_stage_20260525T074404Z`; live `tvb_hybrid_ultima_ont_snv_5x5x_1021` completed `2026-05-25T19:59:00Z` with `exit_code=1`. No retired `sentdhuom` target was executed. Failure rule `sentdhuomr_hybrid_select`, Slurm external jobs `878` and `879`, resources `threads=8`, `mem_mb=16000`, partition `i192mem,i192bigmem`. Slurm stderr shows `HYBRID_SELECT=$(python -c "from importlib.resources import files; print(files('sentieon_cli.scripts').joinpath('hybrid_select.py'))")` resolved Python to `/home/ubuntu/miniconda3/lib/python3.13/...` and failed with `ModuleNotFoundError: No module named 'sentieon_cli'`. Rule log only contained `Starting hybrid_select pipeline at Mon May 25 19:58:48 UTC 2026`; benchmark missing; no Slurm jobs remained at final check. |
| `LIVE-009` | Workflow Agents | Run `complete_genomics_mgi_snv_concordance` after dry-run passes and exact mate-pair contract is verified. | Gate 6 | `BLOCKED` | Not run. Exact valid mate-pair contract remains unverified: `_386_1` is `90,600,002,744` bytes, `_386_2` is `10,794,018,984` bytes, and nearby `_388_2` is `97,844,317,264` bytes; no substitution authorized. |
| `LIVE-010` | Workflow Agents | Run `illumina_run_qc` after dry-run passes. | Gate 6 | `FAILED` | Dry-run `tvb_illumina_run_qc_1021_dryrun` completed `2026-05-25T08:50:20Z` with `exit_code=1`; live not launched. Exact error: `WorkflowError ... The units table was not found at .../config/units.tsv. Create config/units.tsv or set --config units_table=/path/to/units.tsv.` |
| `LIVE-011` | Workflow Agents | Run `illumina_bclconvert` after dry-run passes. | Gate 6 | `FAILED` | Dry-run `tvb_illumina_bclconvert_1021_dryrun` completed `2026-05-25T08:51:13Z` with `exit_code=1`; live not launched. Exact error: `WorkflowError ... No read pairs specified for analysis unit 20260514_LH01106_0009_B23TVLGLT4.` |
| `LIVE-012` | Workflow Agents | Run `ont_run_qc` after dry-run passes. | Gate 6 | `FAILED` | Dry-run `tvb_ont_run_qc_1021_dryrun` completed `2026-05-25T08:52:05Z` with `exit_code=1`; live not launched. Exact error: `WorkflowError ... The units table was not found at .../config/units.tsv. Create config/units.tsv or set --config units_table=/path/to/units.tsv.` |
| `LIVE-013` | Workflow Agents | Run `ultima_run_qc` after dry-run passes. | Gate 6 | `FAILED` | Dry-run `tvb_ultima_run_qc_1021_dryrun` completed `2026-05-25T08:52:58Z` with `exit_code=1`; live not launched. Exact error: `WorkflowError ... The units table was not found at .../config/units.tsv. Create config/units.tsv or set --config units_table=/path/to/units.tsv.` |
| `REPORT-001` | Report Agent | Write matrix report with commands, data, cluster, versions, outcomes, and evidence. | Gate 7 | `SUCCESS` | Wrote `docs/tstver411b_command_catalog_test_results.md` with exact command matrix, cluster/version context, input manifests, stage/run context paths, dry-run/live outcomes, output evidence, failure strings, and fork-fixer comparison. |
| `FINAL-001` | Orchestrator | Terminalize rows and report objective completion. | Gate 7 | `SUCCESS` | All 24 ledger rows are terminal. Recipe matrix outcome: 6 `SUCCESS`, 6 `FAILED`, 1 `BLOCKED`. Objective complete as a validation/reporting pass; not all recipes passed. Cluster remains `CREATE_COMPLETE`, compute fleet `RUNNING`, `/fsx` mounted with about `11T` available, and no Slurm jobs remained at final check. No teardown, export, deletion, or cleanup was performed. |

## Catalog Commands To Validate

| Command ID | Tag | Command |
|---|---|---|
| `illumina_snv_alignstats` | `1.0.21` | `bin/day_run produce_sent_align produce_dmd_dedup_cram produce_sentd_snv_vcf produce_snv_concordances produce_alignstats -p -k -j 20` |
| `illumina_snv_alignstats_relatedness_vep_multiqc` | `1.0.21` | `bin/day_run produce_sent_align produce_dmd_dedup_cram produce_sentd_snv_vcf produce_alignstats produce_snv_concordances produce_relatedness produce_vep produce_multiqc_all --config 'multiqc_qc={"enable_tools":["vep"]}' -p -j 100 -k` |
| `ultima_snv_alignstats` | `1.0.21` | `bin/day_run produce_alignstats produce_na_dedup_cram produce_sentdug_snv_vcf produce_snv_concordances -p -j 20 -k` |
| `ont_snv_alignstats` | `1.0.21` | `bin/day_run produce_alignstats produce_sentdont_snv_vcf produce_snv_concordances -p -j 5 -k` |
| `pacbio_snv_alignstats` | `1.0.21` | `bin/day_run produce_sentmm2_align produce_na_dedup_cram produce_sentdpb_snv_vcf produce_alignstats produce_snv_concordances -p -j 2 -k -T 1` |
| `roche_snv_alignstats` | `1.0.21` | `bin/day_run produce_alignstats produce_na_dedup_cram produce_rochehc_snv_vcf -p -j 5 -k` |
| `hybrid_ilmn_ont_snv` | `1.0.21` | `bin/day_run produce_snv_concordances produce_sentdhiomr_sv produce_sentdhiomr_snv_vcf --config 'dedupers=["dmd"]' -p -j 100 -k` |
| `hybrid_ultima_ont_snv` | `1.0.21` | Planned override only if available: `bin/day_run produce_sentdhuomr_snv_vcf produce_alignstats produce_snv_concordances -p -j 100 -k`; otherwise `BLOCKED`. |
| `complete_genomics_mgi_snv_concordance` | `1.0.21` | `bin/day_run produce_sentcg_align produce_dmd_dedup_cram produce_cgt7p_snv_vcf produce_alignstats produce_snv_concordances -p -j 20 -k -T 1 --retries 0 --rerun-incomplete --keep-incomplete` |
| `illumina_run_qc` | `1.0.21` | `bin/day_run produce_illumina_run_qc -p -j 5 -k --config run_context_file=config/runs.tsv` |
| `illumina_bclconvert` | `1.0.21` | `bin/day_run produce_bclconvert_fastqs_and_metrics -p -j 20 -k --config run_context_file=config/runs.tsv` |
| `ont_run_qc` | `1.0.21` | `bin/day_run produce_ont_run_qc -p -j 5 -k --config run_context_file=config/runs.tsv` |
| `ultima_run_qc` | `1.0.21` | `bin/day_run produce_ultima_run_qc -p -j 5 -k --config run_context_file=config/runs.tsv` |

## Work Log

- `2026-05-25T06:31:58Z`: Created ledger and explicit cluster config. Gate 0 recorded before cluster preflight/create.
- `2026-05-25T06:34:55Z`: Preflight passed from clean tag `4.1.3` worktree.
- `2026-05-25T06:35:59Z`: `dyec create` submitted cluster `tstVer4-1-1b`; monitor in progress.
- `2026-05-25T06:42:00Z`: Generated `tstVer4-1-1b` input manifests and run contexts; sample manifest prechecks passed. CG/MGI remains blocked by mate-pair contract.
- `2026-05-25T06:45:00Z`: Catalog snapshot recorded. DAY-EC catalog is already `sentdhiomr` for ILMN+ONT; DayOA tag `1.0.21` exposes `produce_sentdhuomr_snv_vcf` for Ultima+ONT, despite DAY-EC catalog still listing old `sentdhuom`.
- `2026-05-25T07:09:54Z`: Cluster reached `CREATE_COMPLETE` and compute fleet `RUNNING`, but automatic headnode configuration failed from detached clean worktree with `fatal: ref HEAD is not a symbolic ref`.
- `2026-05-25T07:13:00Z`: Headnode configure retry from branch checkout succeeded; boot verification passed and initial Slurm queue was empty.
- `2026-05-25T07:18:38Z`: First recipe dry-run, `illumina_snv_alignstats`, completed with `exit_code=0`; staged data lives at `/fsx/staging/staged_sample_data/remote_stage_20260525T071517Z`.
- `2026-05-25T07:27:36Z`: `illumina_snv_alignstats_relatedness_vep_multiqc` dry-run completed with `exit_code=0`.
- `2026-05-25T07:30:54Z`: `ultima_snv_alignstats` dry-run completed with `exit_code=0`.
- `2026-05-25T07:32:48Z`: `ont_snv_alignstats` dry-run completed with `exit_code=0`.
- `2026-05-25T07:34:45Z`: `pacbio_snv_alignstats` dry-run completed with `exit_code=0`.
- `2026-05-25T07:39:43Z`: `roche_snv_alignstats` dry-run failed with `exit_code=1` on missing Singularity image `/fsx/resources/environments/containers/ubuntu/ip-10-0-0-103/7a424a40c6fd659f4d052893dd3554fa.simg`.
- `2026-05-25T07:42:08Z`: `hybrid_ilmn_ont_snv` dry-run completed with `exit_code=0` using `sentdhiomr`.
- `2026-05-25T07:44:35Z`: `hybrid_ultima_ont_snv` staging completed with `STAGE_DIRECTIVE=pass_through`; generated TSV preserved distinct UG and ONT CRAM paths and expected file sizes.
- `2026-05-25T07:46:05Z`: `hybrid_ultima_ont_snv` dry-run completed with `exit_code=0` using `sentdhuomr`; no retired `sentdhuom` target was executed.
- `2026-05-25T08:48:36Z`: Run-context DRAs completed and verified for Illumina, ONT, and Ultima run mounts.
- `2026-05-25T08:50:20Z`: `illumina_run_qc` dry-run failed with `WorkflowError` for missing `config/units.tsv`.
- `2026-05-25T08:51:13Z`: `illumina_bclconvert` dry-run failed with `WorkflowError`: `No read pairs specified for analysis unit 20260514_LH01106_0009_B23TVLGLT4`.
- `2026-05-25T08:52:05Z`: `ont_run_qc` dry-run failed with `WorkflowError` for missing `config/units.tsv`.
- `2026-05-25T08:52:58Z`: `ultima_run_qc` dry-run failed with `WorkflowError` for missing `config/units.tsv`.
- `2026-05-25T09:20:32Z`: `illumina_snv_alignstats` live run completed with `exit_code=0`; expected CRAM/VCF/alignstats/concordance artifacts verified.
- `2026-05-25T10:10:02Z`: `illumina_snv_alignstats_relatedness_vep_multiqc` live run completed with `exit_code=0`; expected CRAM/VCF/alignstats/concordance/MultiQC/relatedness artifacts verified.
- `2026-05-25T10:18:07Z`: `ultima_snv_alignstats` live run completed with `exit_code=0`; expected VCF/alignstats/concordance artifacts verified.
- `2026-05-25T10:34:37Z`: `ont_snv_alignstats` live run completed with `exit_code=0`; expected VCF/alignstats/concordance artifacts verified.
- `2026-05-25T11:12:49Z`: `pacbio_snv_alignstats` live run completed with `exit_code=0`; expected CRAM/VCF/alignstats/concordance artifacts verified.
- `2026-05-25T19:32:57Z`: `hybrid_ilmn_ont_snv` live run completed with `exit_code=0` using `sentdhiomr`; expected SNV VCF/TBI, SV VCF/TBI, and concordance artifacts verified.
- `2026-05-25T19:59:00Z`: `hybrid_ultima_ont_snv` live run failed with `exit_code=1` in `sentdhuomr_hybrid_select`; Slurm stderr shows `ModuleNotFoundError: No module named 'sentieon_cli'` while resolving `files('sentieon_cli.scripts').joinpath('hybrid_select.py')`.
- `2026-05-25T20:04:08Z`: Final read-only status check: cluster `CREATE_COMPLETE`, compute fleet `RUNNING`, `/fsx` mounted with about `11T` available, Slurm queue empty, partitions present.
- `2026-05-25T20:04:39Z`: Wrote matrix report and terminalized ledger. No teardown, export, deletion, or cleanup performed.
