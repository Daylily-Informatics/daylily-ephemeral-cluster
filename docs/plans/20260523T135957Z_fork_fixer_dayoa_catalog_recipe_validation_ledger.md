# Fork-Fixer DayOA Catalog Recipe Validation Ledger

Created: 2026-05-23T13:59:57Z

## Objective

Create a new DAY-EC cluster named `fork-fixer` in `us-west-2d`, then validate every DayOA recipe command listed in `config/daylily_available_repositories.yaml` using low-coverage input data where available. Produce a final matrix of exact command, tag, input data, stage/run context, status, output evidence, and failure cause for any non-success row.

No teardown, DRA deletion, cleanup, export, or other destructive AWS action is in scope. Tagging, deletion, stop/terminate, retention changes, and cleanup are not authorized by this ledger.

## Gate 0 Baseline

| Field | Value |
|---|---|
| Workspace | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| Branch | `codex/analysis-id-export-catalog-validation` tracking `origin/codex/analysis-id-export-catalog-validation` |
| Pre-existing dirty files | `config/day_cluster/post_install_ubuntu_combined.sh`, `daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh`, `tests/test_headnode_init.py` |
| Pre-existing untracked paths | `docs/AWS_3month_retrospective_cost_analysis.md`, `docs/aws_3month_retrospective_cost_analysis_assets/`, prior `docs/plans/*` ledgers, `fill_in_the_blanks_lims.md`, `tmp/` |
| DAY-EC version | `daylily-ephemeral-cluster 4.1.3.dev0+g6531a5307.d20260523` |
| AWS profile | `lsmc` |
| AWS identity | `arn:aws:iam::108782052779:root` in account `108782052779` |
| Region/AZ | `us-west-2` / `us-west-2d` |
| Existing clusters in `us-west-2` | `hyb-hg003` `CREATE_COMPLETE`; no `fork-fixer` cluster present at Gate 0 |
| Ledger path | `docs/plans/20260523T135957Z_fork_fixer_dayoa_catalog_recipe_validation_ledger.md` |
| Cluster config path | `docs/plans/20260523T135957Z_fork_fixer_cluster_config.yaml` |

## Cluster Config Values

| Key | Value |
|---|---|
| `cluster_name` | `fork-fixer` |
| `budget_email` | `johnm@lsmc.com` |
| `heartbeat_email` | `johnm@lsmc.com` |
| `fsx_fs_size` | `9600` GiB |
| `headnode_instance_type` | `r7i.2xlarge` |
| `cluster_template_yaml` | `config/day_cluster/prod_cluster.yaml` |
| `max_count_8I` | `1` |
| `max_count_128I` | `8` |
| `max_count_192I` | `14` |
| `max_count_192I` template behavior | Applies to `i192`, `i192mem`, and `i192bigmem` |
| `public_subnet_id` | `subnet-0e9acb65aba5a0330` |
| `private_subnet_id` | `subnet-087a4872d0c34e642` |
| `iam_policy_arn` | `arn:aws:iam::108782052779:policy/pclusterTagsAndBudget` |
| `s3_bucket_name` | `lsmc-dayoa-omics-analysis-us-west-2` |

## Ledger Rows

| ID | Owner | Requirement | Gate | Status | Evidence |
|---|---|---|---|---|---|
| `G0-001` | Orchestrator | Record repo status, dirty files, DAY-EC version, AWS identity, existing clusters, cluster config values, catalog command list, and no-teardown boundary. | Gate 0 | `SUCCESS` | Baseline recorded above. Catalog snapshot reconciled in `CAT-001`. |
| `CFG-001` | Cluster Agent | Create non-interactive cluster config for `fork-fixer` with requested capacity, email, FSx, default headnode, and explicit `USESETVALUE` triplets. | Gate 1 | `SUCCESS` | Created `docs/plans/20260523T135957Z_fork_fixer_cluster_config.yaml`. |
| `PRE-001` | Cluster Agent | Run `dyec preflight --profile lsmc --region-az us-west-2d --config <config> --non-interactive`; block on quota/config failure. | Gate 1 | `SUCCESS` | `dyec preflight --profile lsmc --region-az us-west-2d --config docs/plans/20260523T135957Z_fork_fixer_cluster_config.yaml --non-interactive` passed 12 checks: IAM global/regional, pcluster policy, repository catalog, on-demand/spot/vpc/EIP/NAT/IGW quota, S3 bucket select/verify. |
| `CREATE-001` | Cluster Agent | Run `dyec create --profile lsmc --region-az us-west-2d --config <config> --non-interactive`; monitor until `CREATE_COMPLETE` and compute fleet `RUNNING`. | Gate 2 | `SUCCESS` | `dyec create --profile lsmc --region-az us-west-2d --config docs/plans/20260523T135957Z_fork_fixer_cluster_config.yaml --non-interactive` completed. Cluster created in 35m24s, headnode configured, budgets ensured (`daylily-global`, `da-us-west-2d-fork-fixer`), heartbeat configured, state written to `/Users/jmajor/.config/daylily/state_fork-fixer_20260523140206.json`. Headnode `i-031d99598446e6d56`, public IP `44.227.78.165`; rendered YAML `/Users/jmajor/.config/daylily/fork-fixer_cluster_20260523140206.yaml` matched requested headnode, FSx, and queue max counts. |
| `BOOT-001` | Headnode Agent | Verify SSM ubuntu login shell, `/fsx`, DRA availability, `day-clone`, `dyec`, Slurm partitions, and empty initial queue. | Gate 2 | `SUCCESS` | SSM via `daylily_ec.aws.ssm.run_shell` command `aa9bafe3-3b67-4df9-a1da-874a818296d4` ran as `ubuntu` in `/bin/bash`. Verified `/fsx` mounted Lustre with 8.8T available, `/fsx/data` present, `day-clone`, `dyec`, `squeue`, `sinfo`, and `lfs` available, compute fleet `RUNNING`, Slurm partitions `i8`, `i128`, `i192`, `i192mem`, `i192bigmem` up, and `squeue -h` empty. `/fsx/run_dir_mounts` was created during run-mount DRA work. Headnode DAY-EC reports `4.1.2`; local creator is `4.1.3.dev0+g6531a5307.d20260523`. |
| `CAT-001` | Catalog Agent | Snapshot all DayOA commands from `config/daylily_available_repositories.yaml`; require default/git tags `1.0.21`. | Gate 3 | `SUCCESS` | Catalog Agent confirmed exactly 13 DayOA commands, 9 sample recipes and 4 run-context recipes, with repository `default_ref=1.0.21` and every command `git_tag=1.0.21`. `config/daylily_available_repositories.yaml` and packaged catalog copy are identical. No mismatch against requested matrix; README still mentions `1.0.18` but catalog is authoritative for this run. |
| `DATA-001` | Data Agent | Build or select low-coverage manifests/run contexts for every required data mode; no silent substitutions. | Gate 3 | `SUCCESS_WITH_BLOCKERS` | Data Agent verified ILMN 5x FASTQs, ONT 5x CRAM/CRAI, Ultima 5x CRAM/CRAI, PacBio 5x BAM/BAI, Roche BAM/BAI, Illumina run prefix, ONT run prefix, and Ultima RUN602221/RUN504970 candidates. CG/MGI is blocked pending mate-pair confirmation because planned `_386_1` is 90.6 GB while `_386_2` is 10.8 GB and nearby `_388_2` is 97.8 GB. Run-context dry-runs failed before parser-specific validation because DayOA required sample/unit contracts even for run-context recipes. |
| `STAGE-001` | Staging Agent | Precheck and stage sample-analysis manifests with `dyec samples stage`; capture stage dirs and generated TSVs. | Gate 4 | `SUCCESS_WITH_BLOCKERS` | ILMN stages `remote_stage_20260523T145944Z` and `remote_stage_20260523T150351Z` were created by `dyec samples run --dry-run`. ONT stage `remote_stage_20260523T150612Z`, Ultima stage `remote_stage_20260523T151313Z`, PacBio stage `remote_stage_20260523T151638Z`, Roche stage `remote_stage_20260523T151947Z`, hybrid ILMN+ONT stage `remote_stage_20260523T152627Z`, and hybrid Ultima+ONT stage `remote_stage_20260523T153033Z` were created. CRAM/BAM-based stages required scoped FSx metadata import tasks before headnode visibility because `/data` DRA has no automatic import policy. Hybrid Ultima+ONT is blocked: both staged `ULTIMA_CRAM` and `ONT_CRAM` point to the same destination basename, and S3 contains only the 5.26 GB ONT `HG003_5x.cleaned.cram`, not the 8.36 GB Ultima CRAM. |
| `RUNMOUNT-001` | Run-Mount Agent | Create read-only run DRAs for ILMN, ONT, and Ultima run-analysis commands; write exact `runs.tsv` files. | Gate 4 | `SUCCESS` | Ultima run DRA `dra-0d9808292112c9ed6`, ONT run DRA `dra-08f17b5dc6c296b25`, and ILMN run DRA `dra-0a592634650dd2f5c` are all `AVAILABLE`. No delete/cleanup action taken. |
| `DRY-001` | Workflow Agents | Dry-run every catalog recipe exactly as catalog-defined; block any recipe whose dry-run schedules impossible or unintended work. | Gate 5 | `SUCCESS_WITH_BLOCKERS` | Dry-run success: `illumina_snv_alignstats`, `illumina_snv_alignstats_relatedness_vep_multiqc`, `ont_snv_alignstats`, `ultima_snv_alignstats`, `pacbio_snv_alignstats`, and `hybrid_ilmn_ont_snv`. Blocked/failed before live: `complete_genomics_mgi_snv_concordance` data contract, `hybrid_ultima_ont_snv` stage collision, `roche_snv_alignstats` missing Singularity image during containerized conda setup, and all four run-context recipes due DayOA config/runtime contract failures. |
| `LIVE-001` | Workflow Agents | Run `illumina_snv_alignstats` after dry-run passes. | Gate 6 | `SUCCESS` | First live session `ff_illumina_snv_alignstats_5x_1021` failed during concurrent shared Conda env creation (`alignstats_v0.2`, missing `share/terminfo/67/gator`). Retry `ff_illumina_snv_alignstats_5x_1021_retry1` completed with `status.json exit_code=0` at `2026-05-23T16:17:24Z`. Verified output files include dmd CRAM/CRAI, sentd VCF/TBI, alignstats JSON, `other_reports/giab_concordance_mqc.tsv`, and concordance marker/log files. Concordance created `.SKIPPED` sentinel. |
| `LIVE-002` | Workflow Agents | Run `illumina_snv_alignstats_relatedness_vep_multiqc` after dry-run passes. | Gate 6 | `SUCCESS` | Live session `ff_illumina_fullqc_5x_1021` completed with `status.json exit_code=0` at `2026-05-23T16:33:40Z`; no Slurm jobs remained. Verified output files include dmd CRAM/CRAI, sentd VCF/TBI, alignstats JSON, VEP VCF/TBI and summaries, relatedness reports, final MultiQC HTML/data, and concordance marker/log/report files. Concordance created `.SKIPPED` sentinel because no ROI footprints were expanded. |
| `LIVE-003` | Workflow Agents | Run `ultima_snv_alignstats` after dry-run passes. | Gate 6 | `SUCCESS` | First live session failed during concurrent shared Conda env creation (`rtgtools_v0.1`, pip/import corruption). Retry `ff_ultima_snv_alignstats_5x_1021_retry1` completed with `status.json exit_code=0` at `2026-05-23T16:11:32Z`. Verified output files include Ultima sentdug VCF/TBI, alignstats JSON, `other_reports/giab_concordance_mqc.tsv`, and concordance marker/log files. Concordance created `.SKIPPED` sentinel. |
| `LIVE-004` | Workflow Agents | Run `ont_snv_alignstats` after dry-run passes. | Gate 6 | `SUCCESS` | First live session failed during concurrent shared Conda env creation (`rtgtools_v0.1`, missing `ast`). Retry `ff_ont_snv_alignstats_5x_1021_retry1` completed with `status.json exit_code=0` at `2026-05-23T16:14:57Z`. Verified output files include ONT sentdont SNV VCF/TBI, SV VCF/TBI, alignstats JSON, `other_reports/giab_concordance_mqc.tsv`, and concordance marker/log files. Concordance created `.SKIPPED` sentinel. |
| `LIVE-005` | Workflow Agents | Run `pacbio_snv_alignstats` after dry-run passes. | Gate 6 | `SUCCESS` | First live session failed during concurrent shared Conda env creation (`sentieon_v0.3`, missing Python stdlib file). Retry `ff_pacbio_snv_alignstats_5x_1021_retry1` completed with `status.json exit_code=0` at `2026-05-23T16:36:02Z`; no Slurm jobs remained. Verified output files include sentmm2 CRAM/CRAI, alignstats JSON, sentdpb SNV VCF/TBI, sentdpb SV VCF/TBI, `other_reports/giab_concordance_mqc.tsv`, and concordance marker/log files. Concordance created `.SKIPPED` sentinel because no ROI footprints were expanded. |
| `LIVE-006` | Workflow Agents | Run `roche_snv_alignstats` after dry-run passes. | Gate 6 | `BLOCKED` | Live not launched because dry-run failed during DAG/container setup with missing Singularity image `/fsx/resources/environments/containers/ubuntu/ip-10-0-0-86/7a424a40c6fd659f4d052893dd3554fa.simg`. |
| `LIVE-007` | Workflow Agents | Run `hybrid_ilmn_ont_snv` after dry-run passes. | Gate 6 | `FAILED` | First live session failed during concurrent shared Conda env creation (`rtgtools_v0.1`, missing conda source). Retry `ff_hybrid_ilmn_ont_snv_5x5x_1021_retry1` failed with `status.json exit_code=1` at `2026-05-23T16:12:13Z`. Rule `sentdhiom_hybrid_select` failed because `PATH` resolved `python` to `/home/ubuntu/miniconda3/bin/python` (`Python 3.13.13`) instead of the active env `/fsx/resources/environments/conda/ubuntu/ip-10-0-0-86/820d63e794b17600006e2216064970b8_/bin/python`; log shows `ModuleNotFoundError: No module named 'sentieon_cli'`. |
| `LIVE-008` | Workflow Agents | Run `hybrid_ultima_ont_snv` after dry-run passes. | Gate 6 | `BLOCKED` | Live not launched because staging collision overwrote/collapsed the distinct Ultima and ONT CRAM inputs to one destination path. |
| `LIVE-009` | Workflow Agents | Run `complete_genomics_mgi_snv_concordance` after dry-run passes. | Gate 6 | `BLOCKED` | Live not launched because CG/MGI mate-pair input contract is suspicious and no substitution is authorized. |
| `LIVE-010` | Workflow Agents | Run `illumina_run_qc` after dry-run passes. | Gate 6 | `BLOCKED` | Dry-run failed with `WorkflowError`: `config/units.tsv` not found while loading DayOA common rules. |
| `LIVE-011` | Workflow Agents | Run `illumina_bclconvert` after dry-run passes. | Gate 6 | `BLOCKED` | Dry-run failed with `WorkflowError`: `No read pairs specified for analysis unit 20260514_LH01106_0009_B23TVLGLT4`. |
| `LIVE-012` | Workflow Agents | Run `ont_run_qc` after dry-run passes. | Gate 6 | `BLOCKED` | Dry-run failed with `WorkflowError`: `config/units.tsv` not found while loading DayOA common rules. |
| `LIVE-013` | Workflow Agents | Run `ultima_run_qc` after dry-run passes. | Gate 6 | `BLOCKED` | Dry-run failed with `WorkflowError`: `config/units.tsv` not found while loading DayOA common rules. |
| `REPORT-001` | Report Agent | Produce final matrix: command id, exact command, git tag, input data, stage/run context, status, output evidence, failure cause if any. | Gate 7 | `SUCCESS` | Final report matrix below is complete for all 13 catalog commands with exact commands, tag, inputs, stage/run context, final status, output evidence, and failure cause for non-success rows. |
| `FINAL-001` | Orchestrator | Terminalize all ledger rows; report counts and whether the objective is complete. | Gate 7 | `SUCCESS` | All 25 ledger rows are terminal: 14 `SUCCESS`, 3 `SUCCESS_WITH_BLOCKERS`, 7 `BLOCKED`, and 1 `FAILED`. The validation objective is complete as a catalog recipe validation run; five recipes succeeded end-to-end, and all non-success recipes have concrete failure/blocker evidence. |

## Catalog Recipe Matrix

| Command ID | Catalog Tag | Exact Catalog Command |
|---|---|---|
| `illumina_snv_alignstats` | `1.0.21` | `bin/day_run produce_sent_align produce_dmd_dedup_cram produce_sentd_snv_vcf produce_snv_concordances produce_alignstats -p -k -j 20` |
| `illumina_snv_alignstats_relatedness_vep_multiqc` | `1.0.21` | `bin/day_run produce_sent_align produce_dmd_dedup_cram produce_sentd_snv_vcf produce_alignstats produce_snv_concordances produce_relatedness produce_vep produce_multiqc_all --config 'multiqc_qc={"enable_tools":["vep"]}' -p -j 100 -k` |
| `ultima_snv_alignstats` | `1.0.21` | `bin/day_run produce_alignstats produce_na_dedup_cram produce_sentdug_snv_vcf produce_snv_concordances -p -j 20 -k` |
| `ont_snv_alignstats` | `1.0.21` | `bin/day_run produce_alignstats produce_sentdont_snv_vcf produce_snv_concordances -p -j 5 -k` |
| `pacbio_snv_alignstats` | `1.0.21` | `bin/day_run produce_sentmm2_align produce_na_dedup_cram produce_sentdpb_snv_vcf produce_alignstats produce_snv_concordances -p -j 2 -k -T 1` |
| `roche_snv_alignstats` | `1.0.21` | `bin/day_run produce_alignstats produce_na_dedup_cram produce_rochehc_snv_vcf -p -j 5 -k` |
| `hybrid_ilmn_ont_snv` | `1.0.21` | `bin/day_run produce_snv_concordances produce_sentdhiom_sv produce_sentdhiom_snv_vcf --config 'dedupers=["dmd"]' -p -j 100 -k` |
| `hybrid_ultima_ont_snv` | `1.0.21` | `bin/day_run produce_sentdhuom_snv_vcf produce_alignstats produce_snv_concordances -p -j 100 -k` |
| `complete_genomics_mgi_snv_concordance` | `1.0.21` | `bin/day_run produce_sentcg_align produce_dmd_dedup_cram produce_cgt7p_snv_vcf produce_alignstats produce_snv_concordances -p -j 20 -k -T 1 --retries 0 --rerun-incomplete --keep-incomplete` |
| `illumina_run_qc` | `1.0.21` | `bin/day_run produce_illumina_run_qc -p -j 5 -k` with workflow launch `--config run_context_file=config/runs.tsv` |
| `illumina_bclconvert` | `1.0.21` | `bin/day_run produce_bclconvert_fastqs_and_metrics -p -j 20 -k` with workflow launch `--config run_context_file=config/runs.tsv` |
| `ont_run_qc` | `1.0.21` | `bin/day_run produce_ont_run_qc -p -j 5 -k` with workflow launch `--config run_context_file=config/runs.tsv` |
| `ultima_run_qc` | `1.0.21` | `bin/day_run produce_ultima_run_qc -p -j 5 -k` with workflow launch `--config run_context_file=config/runs.tsv` |

## Low-Coverage Input Plan

| Mode | Planned Input | Status |
|---|---|---|
| ILMN sample | `s3://lsmc-dayoa-omics-analysis-us-west-2/data/genomic_data/organism_reads/H_sapiens/giab/NovaSeqX_WHGS_TruSeqPF_HG002-007/downsampled/HG003_5x_R1.fastq.gz` and `_R2.fastq.gz` | Verified present: R1 3,902,280,885 bytes; R2 4,023,184,443 bytes. |
| ONT sample | `s3://lsmc-dayoa-omics-analysis-us-west-2/data/genomic_data/organism_reads/H_sapiens/giab/agbt_2026/ont/HG003_5x.cleaned.cram` plus `.crai` | Verified present: CRAM 5,260,585,144 bytes; CRAI 34,592 bytes. |
| Ultima sample | `s3://lsmc-dayoa-omics-analysis-us-west-2/data/genomic_data/organism_reads/H_sapiens/giab/agbt_2026/ug/HG003_5x.cleaned.cram` plus `.crai` | Verified present: CRAM 8,356,213,863 bytes; CRAI 136,673 bytes. |
| PacBio sample | `s3://lsmc-dayoa-omics-analysis-us-west-2/data/genomic_data/organism_reads/H_sapiens/giab/agbt_2026/pacbio/HG003/R0-HG003-D0-0-D0/5p0x/HG003_5p0x.bam` plus `.bai` | Verified present: BAM 6,915,253,876 bytes; BAI 16 bytes. `PB_BAM_ALIGNER=sentmm2` examples do not require sidecar preflight. |
| Roche sample | Existing Roche HG003 BAM with `ROCHE_DOWNSAMPLE_RATIO=0.086` | Verified present: BAM 50,124,943,440 bytes; BAI 10,035,552 bytes. Ratio is explicit and derived as `5 * 0.0172`. |
| CG/MGI sample | `ML150002521_L01_UDB-386_1.fq.gz` and `_2.fq.gz` with explicit low-coverage `SUBSAMPLE_PCT` | `BLOCKED`: planned pair exists but size mismatch is suspicious: `_386_1` 90.6 GB vs `_386_2` 10.8 GB; nearby `_388_2` is 97.8 GB. Do not substitute without confirmation. |
| ILMN run | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0009_B23TVLGLT4/` | Verified present: 78,893 objects, 7.7 TiB, includes `RunInfo.xml`, `RunParameters.xml`, `SampleSheet.csv`, BCLConvert `fastq_list.csv`, and Reports metrics. |
| ONT run | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260513_ONT_HG003/` | Verified present: 480 objects, 625.4 GiB, includes `fastq_pass/`, `pod5/`, `other_reports/`, and sequencing summary. Block if recipe requires `pod5_pass/`. |
| Ultima run | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/RUN602221/2026/602221-20260417_2346/` or `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/RUN504970/2026/504970-20260331_1722/` | Both verified with plausible metrics and local production manifests; parser contract still requires dry-run/live proof. |

## Manifest And Run-Context Artifacts

Generated under `docs/plans/20260523T135957Z_fork_fixer_inputs/`.

| Artifact | Purpose | Precheck |
|---|---|---|
| `illumina_hg003_5x.tsv` | ILMN sample-analysis recipes | `dyec samples stage --precheck-only` passed: 1 row, 1 sample, 17 source objects, 1 concordance directory. |
| `ont_hg003_5x.tsv` | ONT sample-analysis recipe | `dyec samples stage --precheck-only` passed: 1 row, 1 sample, 17 source objects, 1 concordance directory. |
| `ultima_hg003_5x.tsv` | Ultima sample-analysis recipe | `dyec samples stage --precheck-only` passed: 1 row, 1 sample, 17 source objects, 1 concordance directory. |
| `pacbio_hg003_5x.tsv` | PacBio sample-analysis recipe | `dyec samples stage --precheck-only` passed: 1 row, 1 sample, 16 source objects, 1 concordance directory. |
| `roche_hg003_5x.tsv` | Roche sample-analysis recipe | `dyec samples stage --precheck-only` passed: 1 row, 1 sample, 16 source objects, 1 concordance directory. |
| `hybrid_ilmn_ont_hg003_5x5x.tsv` | Hybrid ILMN+ONT sample-analysis recipe | `dyec samples stage --precheck-only` passed: 1 row, 1 sample, 19 source objects, 1 concordance directory. |
| `hybrid_ultima_ont_hg003_5x5x.tsv` | Hybrid Ultima+ONT sample-analysis recipe | `dyec samples stage --precheck-only` passed: 1 row, 1 sample, 19 source objects, 1 concordance directory. |
| `complete_genomics_mgi_hg003_candidate_blocked.tsv` | CG/MGI candidate only | DayEC manifest precheck passed, but row remains `BLOCKED` because mate-size mismatch and downstream low-coverage bounding are not proven. |
| `illumina_run_context.tsv` | ILMN run QC and BCL Convert | DRA mounted; both dry-runs failed before live execution. |
| `ont_run_context.tsv` | ONT run QC | DRA mounted; dry-run failed before live execution. |
| `ultima_run_context_candidate.tsv` | Ultima run QC candidate | DRA mounted; dry-run failed before live execution. |

## Dry-Run Evidence

| Command ID | Dry-Run Status | Stage/Context | Evidence |
|---|---|---|---|
| `illumina_snv_alignstats` | `SUCCESS` | `/fsx/data/staged_sample_data/remote_stage_20260523T145944Z` | `dyec samples run --dry-run` launched `ff_illumina_snv_alignstats_5x_1021_dryrun`; `status.json` exit code `0`, started `2026-05-23T15:01:08Z`, completed `2026-05-23T15:03:02Z`, no Slurm jobs left. |
| `illumina_snv_alignstats_relatedness_vep_multiqc` | `SUCCESS` | `/fsx/data/staged_sample_data/remote_stage_20260523T150351Z` | `dyec samples run --dry-run` launched `ff_illumina_fullqc_5x_1021_dryrun`; `status.json` exit code `0`, started `2026-05-23T15:05:25Z`, completed `2026-05-23T15:05:52Z`, no Slurm jobs left. |
| `ont_snv_alignstats` | `SUCCESS` | `/fsx/data/staged_sample_data/remote_stage_20260523T150612Z` | Initial `dyec samples run --dry-run` staged data but failed before launch with SSM stdout `__DAYLILY_ERROR__=missing_stage_dir`. Scoped FSx import task `task-067b813a95f729cb1` for the staged S3 prefix succeeded; `dyec workflow launch` using the catalog dry-run command launched `ff_ont_snv_alignstats_5x_1021_dryrun`; `status.json` exit code `0`, started `2026-05-23T15:11:59Z`, completed `2026-05-23T15:12:24Z`, no Slurm jobs left. |
| `ultima_snv_alignstats` | `SUCCESS_WITH_WARNING` | `/fsx/data/staged_sample_data/remote_stage_20260523T151313Z` | `dyec samples stage` succeeded; scoped FSx import task `task-0a16d61a29f314400` succeeded; `dyec workflow launch` using the catalog dry-run command launched `ff_ultima_snv_alignstats_5x_1021_dryrun`; `status.json` exit code `0`, started `2026-05-23T15:15:33Z`, completed `2026-05-23T15:15:59Z`, no Slurm jobs left. Warning: dry-run log showed the concordance sentinel with no ROI footprints, so the live row must verify real concordance outputs rather than treating dry-run as proof of concordance content. |
| `pacbio_snv_alignstats` | `SUCCESS` | `/fsx/data/staged_sample_data/remote_stage_20260523T151638Z` | `dyec samples stage` succeeded; scoped FSx import task `task-01053d3d8427601ad` succeeded; `dyec workflow launch` using the catalog dry-run command launched `ff_pacbio_snv_alignstats_5x_1021_dryrun`; `status.json` exit code `0`, started `2026-05-23T15:18:50Z`, completed `2026-05-23T15:19:15Z`, no Slurm jobs left. |
| `roche_snv_alignstats` | `FAILED` | `/fsx/data/staged_sample_data/remote_stage_20260523T151947Z` | `dyec samples stage` succeeded; scoped FSx import task `task-056fd90f7470673bb` succeeded; dry-run session `ff_roche_snv_alignstats_5x_1021_dryrun` exited `1`. DAG setup attempted to pull `docker://broadinstitute/gatk-nightly:2025-08-19-4.6.2.0-17-g2a1f41bf3-NIGHTLY-SNAPSHOT` and `docker://roche/sbxd-small-variant-caller:latest`, then failed while trying `conda info --json` inside missing image `/fsx/resources/environments/containers/ubuntu/ip-10-0-0-86/7a424a40c6fd659f4d052893dd3554fa.simg`. |
| `hybrid_ilmn_ont_snv` | `SUCCESS_WITH_WARNING` | `/fsx/data/staged_sample_data/remote_stage_20260523T152627Z` | `dyec samples stage` succeeded; scoped FSx import task `task-05a719e0331161bb5` succeeded; dry-run session `ff_hybrid_ilmn_ont_snv_5x5x_1021_dryrun` exited `0`, started `2026-05-23T15:29:37Z`, completed `2026-05-23T15:30:02Z`. Warning: dry-run log showed the concordance sentinel with no ROI footprints, so the live row must verify real concordance outputs. |
| `hybrid_ultima_ont_snv` | `BLOCKED` | `/fsx/data/staged_sample_data/remote_stage_20260523T153033Z` | Stage generation produced one `units.tsv` row where `ULTIMA_CRAM` and `ONT_CRAM` both point to `/fsx/data/staged_sample_data/remote_stage_20260523T153033Z/FFHUO5X5X_HG003-ULTIMA-PF-gdna-UG5x-ONT5x_D0_0/HG003_5x.cleaned.cram`. S3 listing shows only one CRAM object at that path, size `5,260,585,144` bytes, matching ONT and not the distinct Ultima CRAM size `8,356,213,863` bytes. Live was not launched. |
| `complete_genomics_mgi_snv_concordance` | `BLOCKED` | `docs/plans/20260523T135957Z_fork_fixer_inputs/complete_genomics_mgi_hg003_candidate_blocked.tsv` | Candidate manifest precheck passed mechanically, but the `_386_1`/`_386_2` mate-size mismatch and unproven low-coverage bounding mean this row is blocked by data contract, with no substitution authorized. |
| `illumina_run_qc` | `FAILED` | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/` via `illumina_run_context.tsv` | Dry-run session `ff_illumina_run_qc_1021_dryrun` exited `1`. Exact failure: `WorkflowError ... The units table was not found at .../config/units.tsv. Create config/units.tsv or set --config units_table=/path/to/units.tsv.` |
| `illumina_bclconvert` | `FAILED` | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/` via `illumina_run_context.tsv` | Dry-run session `ff_illumina_bclconvert_1021_dryrun` exited `1`. Exact failure: `WorkflowError ... No read pairs specified for analysis unit 20260514_LH01106_0009_B23TVLGLT4.` |
| `ont_run_qc` | `FAILED` | `/fsx/run_dir_mounts/20260513_ONT_HG003/` via `ont_run_context.tsv` | Dry-run session `ff_ont_run_qc_1021_dryrun` exited `1`. Exact failure: `WorkflowError ... The units table was not found at .../config/units.tsv. Create config/units.tsv or set --config units_table=/path/to/units.tsv.` |
| `ultima_run_qc` | `FAILED` | `/fsx/run_dir_mounts/602221-20260417_2346/` via `ultima_run_context_candidate.tsv` | Dry-run session `ff_ultima_run_qc_1021_dryrun` exited `1`. Exact failure: `WorkflowError ... The units table was not found at .../config/units.tsv. Create config/units.tsv or set --config units_table=/path/to/units.tsv.` |

## Final Report Matrix

| Command ID | Exact Command | Git Tag | Input Data | Stage/Run Context | Final Status | Output Evidence | Failure Cause |
|---|---|---|---|---|---|---|---|
| `illumina_snv_alignstats` | `bin/day_run produce_sent_align produce_dmd_dedup_cram produce_sentd_snv_vcf produce_snv_concordances produce_alignstats -p -k -j 20` | `1.0.21` | HG003 ILMN 5x FASTQ R1/R2 | `/fsx/data/staged_sample_data/remote_stage_20260523T145944Z` | `SUCCESS` | Dry-run `ff_illumina_snv_alignstats_5x_1021_dryrun` exit code `0`; retry live session `ff_illumina_snv_alignstats_5x_1021_retry1` completed with `status.json exit_code=0` at `2026-05-23T16:17:24Z`; outputs include dmd CRAM/CRAI, sentd VCF/TBI, alignstats JSON, and concordance marker/log/report files. | First live attempt failed only during concurrent shared Conda env creation. Concordance produced `.SKIPPED` sentinel because no ROI footprints were expanded. |
| `illumina_snv_alignstats_relatedness_vep_multiqc` | `bin/day_run produce_sent_align produce_dmd_dedup_cram produce_sentd_snv_vcf produce_alignstats produce_snv_concordances produce_relatedness produce_vep produce_multiqc_all --config 'multiqc_qc={"enable_tools":["vep"]}' -p -j 100 -k` | `1.0.21` | HG003 ILMN 5x FASTQ R1/R2 | `/fsx/data/staged_sample_data/remote_stage_20260523T150351Z` | `SUCCESS` | Dry-run `ff_illumina_fullqc_5x_1021_dryrun` exit code `0`; live session `ff_illumina_fullqc_5x_1021` completed with `status.json exit_code=0` at `2026-05-23T16:33:40Z`; outputs include dmd CRAM/CRAI, sentd VCF/TBI, alignstats JSON, VEP VCF/TBI and summaries, relatedness reports, final MultiQC HTML/data, and concordance marker/log/report files. | Concordance produced `.SKIPPED` sentinel because no ROI footprints were expanded. |
| `ultima_snv_alignstats` | `bin/day_run produce_alignstats produce_na_dedup_cram produce_sentdug_snv_vcf produce_snv_concordances -p -j 20 -k` | `1.0.21` | HG003 Ultima 5x CRAM/CRAI | `/fsx/data/staged_sample_data/remote_stage_20260523T151313Z` | `SUCCESS` | Dry-run `ff_ultima_snv_alignstats_5x_1021_dryrun` exit code `0`; retry live session `ff_ultima_snv_alignstats_5x_1021_retry1` completed with `status.json exit_code=0` at `2026-05-23T16:11:32Z`; outputs include sentdug VCF/TBI, alignstats JSON, and concordance marker/log/report files. | Concordance produced `.SKIPPED` sentinel because no ROI footprints were expanded. |
| `ont_snv_alignstats` | `bin/day_run produce_alignstats produce_sentdont_snv_vcf produce_snv_concordances -p -j 5 -k` | `1.0.21` | HG003 ONT 5x CRAM/CRAI | `/fsx/data/staged_sample_data/remote_stage_20260523T150612Z` | `SUCCESS` | Dry-run `ff_ont_snv_alignstats_5x_1021_dryrun` exit code `0`; retry live session `ff_ont_snv_alignstats_5x_1021_retry1` completed with `status.json exit_code=0` at `2026-05-23T16:14:57Z`; outputs include sentdont SNV VCF/TBI, sentdont SV VCF/TBI, alignstats JSON, and concordance marker/log/report files. | Concordance produced `.SKIPPED` sentinel because no ROI footprints were expanded. |
| `pacbio_snv_alignstats` | `bin/day_run produce_sentmm2_align produce_na_dedup_cram produce_sentdpb_snv_vcf produce_alignstats produce_snv_concordances -p -j 2 -k -T 1` | `1.0.21` | HG003 PacBio 5x BAM | `/fsx/data/staged_sample_data/remote_stage_20260523T151638Z` | `SUCCESS` | Dry-run `ff_pacbio_snv_alignstats_5x_1021_dryrun` exit code `0`; retry live session `ff_pacbio_snv_alignstats_5x_1021_retry1` completed with `status.json exit_code=0` at `2026-05-23T16:36:02Z`; outputs include sentmm2 CRAM/CRAI, alignstats JSON, sentdpb SNV VCF/TBI, sentdpb SV VCF/TBI, and concordance marker/log/report files. | First live attempt failed only during concurrent shared Conda env creation. Concordance produced `.SKIPPED` sentinel because no ROI footprints were expanded. |
| `roche_snv_alignstats` | `bin/day_run produce_alignstats produce_na_dedup_cram produce_rochehc_snv_vcf -p -j 5 -k` | `1.0.21` | HG003 Roche BAM with `ROCHE_DOWNSAMPLE_RATIO=0.086` | `/fsx/data/staged_sample_data/remote_stage_20260523T151947Z` | `DRY_RUN_FAILED_LIVE_NOT_RUN` | Stage import task `task-056fd90f7470673bb`; dry-run `ff_roche_snv_alignstats_5x_1021_dryrun` exit code `1`. | Missing Singularity image during containerized conda setup: `/fsx/resources/environments/containers/ubuntu/ip-10-0-0-86/7a424a40c6fd659f4d052893dd3554fa.simg`. |
| `hybrid_ilmn_ont_snv` | `bin/day_run produce_snv_concordances produce_sentdhiom_sv produce_sentdhiom_snv_vcf --config 'dedupers=["dmd"]' -p -j 100 -k` | `1.0.21` | HG003 ILMN 5x FASTQ plus ONT 5x CRAM/CRAI | `/fsx/data/staged_sample_data/remote_stage_20260523T152627Z` | `FAILED` | Dry-run `ff_hybrid_ilmn_ont_snv_5x5x_1021_dryrun` exit code `0`; retry live session `ff_hybrid_ilmn_ont_snv_5x5x_1021_retry1` failed with `status.json exit_code=1` at `2026-05-23T16:12:13Z`. | Rule `sentdhiom_hybrid_select` used base `/home/ubuntu/miniconda3/bin/python` (`Python 3.13.13`) ahead of the active Conda env `python`; `from importlib.resources import files; files('sentieon_cli.scripts')` failed with `ModuleNotFoundError: No module named 'sentieon_cli'`. |
| `hybrid_ultima_ont_snv` | `bin/day_run produce_sentdhuom_snv_vcf produce_alignstats produce_snv_concordances -p -j 100 -k` | `1.0.21` | HG003 Ultima 5x CRAM/CRAI plus ONT 5x CRAM/CRAI | `/fsx/data/staged_sample_data/remote_stage_20260523T153033Z` | `BLOCKED` | Stage generated `units.tsv`, but both `ULTIMA_CRAM` and `ONT_CRAM` point at the same destination `HG003_5x.cleaned.cram`; S3 contains only one CRAM object of 5.26 GB, matching ONT. | Staging collision/collapse of two distinct CRAM inputs with identical basenames; live not launched. |
| `complete_genomics_mgi_snv_concordance` | `bin/day_run produce_sentcg_align produce_dmd_dedup_cram produce_cgt7p_snv_vcf produce_alignstats produce_snv_concordances -p -j 20 -k -T 1 --retries 0 --rerun-incomplete --keep-incomplete` | `1.0.21` | CG/MGI candidate pair `ML150002521_L01_UDB-386_1.fq.gz` and `_386_2.fq.gz` | `docs/plans/20260523T135957Z_fork_fixer_inputs/complete_genomics_mgi_hg003_candidate_blocked.tsv` | `BLOCKED` | DayEC manifest precheck passed only mechanically. | `_386_1`/`_386_2` mate-size mismatch and unproven low-coverage bounding; no substitution authorized. |
| `illumina_run_qc` | `bin/day_run produce_illumina_run_qc -p -j 5 -k --config run_context_file=config/runs.tsv` | `1.0.21` | ILMN run prefix `20260514_LH01106_0009_B23TVLGLT4` | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/` | `DRY_RUN_FAILED_LIVE_NOT_RUN` | Dry-run `ff_illumina_run_qc_1021_dryrun` exit code `1`. | `WorkflowError`: `config/units.tsv` not found while loading common DayOA rules. |
| `illumina_bclconvert` | `bin/day_run produce_bclconvert_fastqs_and_metrics -p -j 20 -k --config run_context_file=config/runs.tsv` | `1.0.21` | ILMN run prefix `20260514_LH01106_0009_B23TVLGLT4` | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/` | `DRY_RUN_FAILED_LIVE_NOT_RUN` | Dry-run `ff_illumina_bclconvert_1021_dryrun` exit code `1`. | `WorkflowError`: `No read pairs specified for analysis unit 20260514_LH01106_0009_B23TVLGLT4`. |
| `ont_run_qc` | `bin/day_run produce_ont_run_qc -p -j 5 -k --config run_context_file=config/runs.tsv` | `1.0.21` | ONT run prefix `20260513_ONT_HG003` | `/fsx/run_dir_mounts/20260513_ONT_HG003/` | `DRY_RUN_FAILED_LIVE_NOT_RUN` | Dry-run `ff_ont_run_qc_1021_dryrun` exit code `1`. | `WorkflowError`: `config/units.tsv` not found while loading common DayOA rules. |
| `ultima_run_qc` | `bin/day_run produce_ultima_run_qc -p -j 5 -k --config run_context_file=config/runs.tsv` | `1.0.21` | Ultima run prefix `602221-20260417_2346` | `/fsx/run_dir_mounts/602221-20260417_2346/` | `DRY_RUN_FAILED_LIVE_NOT_RUN` | Dry-run `ff_ultima_run_qc_1021_dryrun` exit code `1`. | `WorkflowError`: `config/units.tsv` not found while loading common DayOA rules. |

## Terminal Summary

Generated: 2026-05-23T16:37:00Z

| Scope | Count | Notes |
|---|---:|---|
| Ledger rows | 25 | All terminal. |
| Ledger `SUCCESS` rows | 14 | Includes cluster creation, bootstrap, catalog snapshot, five live recipe successes, `REPORT-001`, and `FINAL-001`. |
| Ledger `SUCCESS_WITH_BLOCKERS` rows | 3 | Data/staging/dry-run rows succeeded overall while preserving explicit blockers. |
| Ledger `BLOCKED` rows | 7 | Roche live, hybrid Ultima+ONT, CG/MGI, and four run-context recipes were not run live. |
| Ledger `FAILED` rows | 1 | Hybrid ILMN+ONT failed during live rule execution. |
| Recipe `SUCCESS` rows | 5 | ILMN simple, ILMN full QC/VEP/MultiQC, Ultima, ONT, and PacBio. |
| Recipe non-success rows | 8 | All have exact dry-run/live failure or blocker evidence. |

No teardown, DRA deletion, cleanup, export, or other destructive AWS action was performed.

## Post-Run Catalog Correction

Recorded: 2026-05-24T04:17:54Z

The `hybrid_ilmn_ont_snv` failure above exercised the deprecated `sentdhiom` target family. The valid production family is `sentdhiomr`; DAY-EC catalog entries should use `produce_sentdhiomr_sv` and `produce_sentdhiomr_snv_vcf` for ILMN+ONT hybrid validation. The historical failure remains recorded because it is what was actually run, but it should not be interpreted as evidence against the production HIOMR path.
