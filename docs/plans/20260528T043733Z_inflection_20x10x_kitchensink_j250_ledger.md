# Inflection 20x10x HIOMR Kitchen-Sink J250 Ledger

Controlling plan: user request in this thread, "20x ILMN + 10x ONT HIOMR Kitchen-Sink Restart Plan", amended in-thread to use DayOA `2.0.13` and include Ganon2 metagenomics.
Ledger path: `docs/plans/20260528T043733Z_inflection_20x10x_kitchensink_j250_ledger.md`
Started: `2026-05-28T04:37:33Z`
Operator: `orchestrator`

## Objective

Restart only the 20x ILMN + 10x ONT Inflection run on `goodole3` in `us-west-2` from `/fsx/analysis_results/ubuntu/inflection_20260527-2.0.11/daylily-omics-analysis`, using DayOA `2.0.13`, with the catalog kitchen-sink/report expansion, non-VerifyBamID2 contamination, relatedness, VEP, broad Kraken2 and Ganon2 metagenomics, and final MultiQC. Run live only if the `-n` dry-run gate proves no alignment, dedup, variant calling, segdup/CNV/mito, or ExpansionHunter execution will rerun.

Amendment at `2026-05-28T04:52Z`: the Kraken2 DB must be persisted to the reference S3 bucket that is mounted on cluster creation and the workflow command must use that auto-mounted `/fsx/references/...` path, so future clusters do not rebuild the database.

Amendment at `2026-05-28T04:57Z`: include Ganon2 unmapped metagenomics execution and final MultiQC staging if not already included.

Amendment at `2026-05-28T04:59Z`: use DayOA tag `2.0.13`, not `2.0.11`.

Amendment at `2026-05-28T06:32Z`: use the `lsmc-bio` hacked MultiQC release with Ultima run-directory QC and first-class AlignStats support. The acceptable MultiQC runtime is the DayOA-pinned conda env containing `multiqc @ https://github.com/lsmc-bio/MultiQC/archive/refs/tags/1.36.dev0-lsmc.6.zip`; the upstream `docker://multiqc/multiqc:v1.35` container must not be used for this run.

## Gate 0 Baseline

### Local Repo

- Repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
- Branch: `codex/running-nextflow-pipes-doc...origin/codex/running-nextflow-pipes-doc`
- Instruction files read:
  - `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/AGENTS.md`
  - `/Users/jmajor/.agents/AGENTS.md`
  - `/Users/jmajor/.codex/AGENTS.md`
  - `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`
- Memory lookup:
  - `/Users/jmajor/.codex/memories/MEMORY.md` lines around `52-63` confirm supported SSM helper / initialized `dy-r` discipline.
  - `/Users/jmajor/.codex/memories/MEMORY.md` lines around `1023-1025` confirm interactive login-bash DayOA shell setup and compact nested Snakemake config discipline.

Local dirty worktree before this ledger, preserved:

```text
## codex/running-nextflow-pipes-doc...origin/codex/running-nextflow-pipes-doc
 M AGENTS.md
 M config/daylily_available_repositories.yaml
 M daylily_ec/cli.py
 M daylily_ec/repositories.py
 M daylily_ec/resources/payload/config/daylily_available_repositories.yaml
 M daylily_ec/resources/payload/etc/fsx_export.yaml
 M daylily_ec/scripts/daylily_run_omics_analysis_headnode.py
 M daylily_ec/workflow/export_data.py
 M docs/cli_reference.md
 M docs/monitoring_and_troubleshooting.md
 M docs/operations.md
 M docs/overview.md
 M docs/plans/20260528T003512Z_inflection_controller_rulegraphs/README.md
 M docs/plans/20260528T003512Z_inflection_controller_rulegraphs/dryrun_counts.tsv
 M docs/plans/20260528T003512Z_inflection_controller_rulegraphs/manifest.tsv
 M docs/plans/20260528T003512Z_inflection_controller_rulegraphs/remaining_summary.tsv
 M docs/plans/20260528T003512Z_inflection_controller_rulegraphs/remaining_summary_latest.tsv
 M docs/quickest_start.md
 M docs/s3_bucket_lifecycle.md
 M tests/test_cli_registry_v2.py
 M tests/test_export.py
 M tests/test_repository_catalog.py
 M tests/test_script_entrypoints.py
 M tests/test_ssm_e2e_runner.py
?? .tailscale_key
?? 20260514-LH01106-0009-B23TVLGLT4-HIOMRFULL-HG003-a-20260514-Altair3-ONT-full-HIOMR-0-HG003-a-PF-ILMN-NOVASEQ.ont.dmd.sentdhiomr.snv.sort.vcf.gz
?? daylily_ec/workflow/dewey_registration.py
?? docs/plans/20260527T163009Z_hg003_full1022_signed_urls.tsv
?? docs/plans/20260528T003512Z_inflection_controller_rulegraphs/dot/downsampled_with_segdup.rulegraph.dot
?? docs/plans/20260528T003512Z_inflection_controller_rulegraphs/dot/downsampled_with_segdup.rulegraph.mmd
?? docs/plans/20260528T003512Z_inflection_controller_rulegraphs/pdf/downsampled_with_segdup.rulegraph.pdf
?? docs/plans/20260528T003512Z_inflection_controller_rulegraphs/png/downsampled_with_segdup.rulegraph.png
?? docs/plans/20260528T003512Z_inflection_controller_rulegraphs/svg/downsampled_with_segdup.rulegraph.svg
?? docs/plans/20260528T004106Z_dayclone_outstanding/
?? docs/plans/20260528T004427Z_downsample_expt_outstanding/
?? docs/plans/20260528T005357Z_inflection_known_pass_segdup_restart_ledger.md
?? docs/plans/20260528T010932Z_interactive_shell_defaults_ledger.md
?? docs/plans/20260528T013958Z_inflection_export_dewey_kitchensink/
?? docs/plans/20260528T013958Z_inflection_export_dewey_kitchensink_ledger.md
?? docs/plans/20260528T040018Z_dayoa_dyec_dewey_qeo_registration_refactor_ledger.md
?? presign_url_sofar.md
```

Resumption note at `2026-05-28T05:16Z`: local worktree state has changed since Gate 0 while the remote Ganon2 build is running. This does not rewrite the original baseline; it records the current local dirty state for provenance:

```text
## codex/dyec-dewey-registration-refactor-20260528...origin/codex/dyec-dewey-registration-refactor-20260528
 M AGENTS.md
 M docs/plans/20260528T003512Z_inflection_controller_rulegraphs/README.md
 M docs/plans/20260528T003512Z_inflection_controller_rulegraphs/dryrun_counts.tsv
 M docs/plans/20260528T003512Z_inflection_controller_rulegraphs/manifest.tsv
 M docs/plans/20260528T003512Z_inflection_controller_rulegraphs/remaining_summary.tsv
 M docs/plans/20260528T003512Z_inflection_controller_rulegraphs/remaining_summary_latest.tsv
?? .tailscale_key
?? 20260514-LH01106-0009-B23TVLGLT4-HIOMRFULL-HG003-a-20260514-Altair3-ONT-full-HIOMR-0-HG003-a-PF-ILMN-NOVASEQ.ont.dmd.sentdhiomr.snv.sort.vcf.gz
?? docs/plans/20260527T163009Z_hg003_full1022_signed_urls.tsv
?? docs/plans/20260528T003512Z_inflection_controller_rulegraphs/dot/downsampled_with_segdup.rulegraph.dot
?? docs/plans/20260528T003512Z_inflection_controller_rulegraphs/dot/downsampled_with_segdup.rulegraph.mmd
?? docs/plans/20260528T003512Z_inflection_controller_rulegraphs/pdf/downsampled_with_segdup.rulegraph.pdf
?? docs/plans/20260528T003512Z_inflection_controller_rulegraphs/png/downsampled_with_segdup.rulegraph.png
?? docs/plans/20260528T003512Z_inflection_controller_rulegraphs/svg/downsampled_with_segdup.rulegraph.svg
?? docs/plans/20260528T004106Z_dayclone_outstanding/
?? docs/plans/20260528T004427Z_downsample_expt_outstanding/
?? docs/plans/20260528T005357Z_inflection_known_pass_segdup_restart_ledger.md
?? docs/plans/20260528T010932Z_interactive_shell_defaults_ledger.md
?? docs/plans/20260528T013958Z_inflection_export_dewey_kitchensink/
?? docs/plans/20260528T013958Z_inflection_export_dewey_kitchensink_ledger.md
?? docs/plans/20260528T043733Z_inflection_20x10x_kitchensink_j250_ledger.md
?? presign_url_sofar.md
```

### Live Cluster And Headnode

- `AWS_PROFILE=lsmc`, `AWS_DEFAULT_REGION=us-west-2`
- `pcluster list-clusters --region us-west-2`:
  - `goodole3` is `CREATE_COMPLETE`.
  - `jem-bucktst1` and `jem-bucktst2` are `CREATE_FAILED`.
- `daylily-ec --json headnode info --profile lsmc --region us-west-2 --cluster goodole3`:
  - `clusterStatus=CREATE_COMPLETE`
  - `computeFleetStatus=RUNNING`
  - headnode `i-0bd631af238bfac56`
  - private IP `10.0.0.144`
  - instance type `r7i.2xlarge`
- `daylily-ec headnode jobs --profile lsmc --region us-west-2 --cluster goodole3` returned only the header; no queued/running Slurm jobs.

Remote baseline through `daylily_ec.aws.ssm.run_shell(..., as_user="ubuntu")`:

```text
DATE=2026-05-28T04:38:31+00:00
USER=ubuntu HOST=ip-10-0-0-144

tmux:
inflection_20x10x_knownpass_j400_real_20260528T011810Z: 1 windows (created Thu May 28 01:18:10 2026)

squeue:
header only; no jobs

/fsx:
Size 4.4T, used 763G, available 3.7T, 18% used
```

### Remote DayOA Checkout

- Repo: `/fsx/analysis_results/ubuntu/inflection_20260527-2.0.11/daylily-omics-analysis`
- Gate 0 Git state: detached `HEAD`, `2.0.11`, commit `d5b5faefc33efbb0edb6ec58ce56cbcd5ae4a19e`
- Amended Git state at `2026-05-28T04:59Z`: detached `HEAD`, `2.0.13`, commit `30dd313053368be63a8362a54f33331ee124b3c7`
- `git fetch --tags origin` fetched tags `2.0.12` and `2.0.13`; tracked worktree was clean before checkout, so checkout proceeded. Existing untracked run logs and unit sidecars were preserved.
- Remote dirty state before this run, preserved:
  - existing untracked `.ignore/*` logs/rc/json files from earlier Inflection attempts
  - existing untracked `config/units.ILMN15x-ONT7x.tsv`
  - existing untracked `config/units.ILMN20x-ONT10x.tsv`
  - existing untracked `config/day_profiles/slurm/rule_config.yaml.bak.20260528T005757Z`
  - existing untracked `gatheredall.sentdhiomr.*` files and `sbatch_errs.log`

Remote unit table evidence:

```text
config/units.tsv lines=3 sha256=c4dff89293e7cdcfddbf40cc51e6f26efce45504841ca003c1aec3377ebd55b0
markers: 10x, 15x, 20x, 7x, ILMN15X, ILMN20X, ONT10X, ONT7X

config/units.ILMN20x-ONT10x.tsv lines=2 sha256=176b3eda3c3991bc4dc9fa1f72edfce556f264ef2ab29ba64b8c086f7d8e758a
markers: 10x, 20x, ILMN20X, ONT10X

config/units.ILMN15x-ONT7x.tsv lines=2 sha256=790073c6ab506422b448310119193718a7ea4ce6817be4d51865f8e88dfd1604
markers: 15x, 7x, ILMN15X, ONT7X
```

### Metagenomics DB Baseline

- Initial staging DB path: `/fsx/resources/metagenomics/kraken2/k2_pluspfp_16_GB_20260226`
- Durable S3 DB path: `s3://lsmc-dayoa-references-usw2/runtime_assets/tool_specific_resources/metagenomics/kraken2/k2_pluspfp_16_GB_20260226/`
- Auto-mounted workflow DB path: `/fsx/references/runtime_assets/tool_specific_resources/metagenomics/kraken2/k2_pluspfp_16_GB_20260226`
- Baseline state: missing.
- No Kraken/Ganon/Sourmash DB candidates found under `/fsx/resources`, `/fsx/references/runtime_assets`, or `/fsx/references/genomic_data`.
- `kraken2` was not on the base headnode `PATH`; DayOA has a `workflow/envs/unmapped_metagenomics_v0.1.yaml` conda env for the rule.
- Cluster-created reference DRA evidence:
  - `FileSystemId=fs-03509c3c3fcf86610`
  - `AssociationId=dra-0febd268a94636039`
  - `DataRepositoryPath=s3://lsmc-dayoa-references-usw2`
  - `FileSystemPath=/references/`
  - Headnode mount path `/fsx/references/`
- The prior `/fsx/resources/...` DB path is not acceptable for the live `dy-r` config because it is not the cluster startup reference DRA namespace.
- Current source for prebuilt DB: `https://genome-idx.s3.amazonaws.com/kraken/k2_pluspfp_16_GB_20260226.tar.gz`
- Current md5 manifest: `https://genome-idx.s3.amazonaws.com/kraken/pluspfp_16_GB_20260226/pluspfp_16_GB.md5`
- Local `curl -I` confirmed the tarball exists, content length `11275890960`, last modified `2026-03-11T14:55:50Z`.
- Local md5 manifest includes required files and tarball checksum `cf80ea5ad50b3b6276132fda43bfe714  k2_pluspfp_16_GB_20260226.tar.gz`.

## Control Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Ledger | Record Gate 0 baseline, including dirty worktree state. | SUCCESS | plan_amendment | Gate 0 | orchestrator | This ledger. |  | Gate 0 recorded before remote mutation. |
| DB-001 | Metagenomics DB | Create and atomically validate PlusPFP-16 Kraken2 DB if missing. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `/fsx/resources/metagenomics/kraken2/k2_pluspfp_16_GB_20260226.prepare_20260528T043733Z.log` shows tarball md5 OK and extracted-file md5 OK for `hash.k2d`, `opts.k2d`, `taxo.k2d`, and all manifest files. | Missing DB. | Validated staging DB exists. |
| DB-002 | Durable reference DB | Upload/export validated DB to `s3://lsmc-dayoa-references-usw2/runtime_assets/tool_specific_resources/metagenomics/kraken2/k2_pluspfp_16_GB_20260226/`, import/reference it on current FSx, and use `/fsx/references/runtime_assets/tool_specific_resources/metagenomics/kraken2/k2_pluspfp_16_GB_20260226` in Snakemake config. | SUCCESS | config_or_startup_contract | Gate 1 | orchestrator | Headnode direct S3 upload failed with `AccessDenied` for `s3:PutObject`; targeted sudo copied DB into `/fsx/references/runtime_assets/tool_specific_resources/metagenomics/kraken2/k2_pluspfp_16_GB_20260226`; FSx export task `task-09b3dbe03016a32c2` succeeded; S3 `head-object` passed for `hash.k2d`, `opts.k2d`, and `taxo.k2d`. | User amended durability requirement. | Durable reference S3 and current auto-mounted `/fsx/references` path are ready. |
| GANON2-001 | Ganon2 metagenomics | Include `produce_unmapped_metagenomics_ganon2_quick`, enable `unmapped_metagenomics_ganon2` in final MultiQC, and provide explicit durable `ganon2_db_prefixes`. | SUCCESS | feature_implementation | Gate 1 | orchestrator | DayOA `2.0.13` has target `produce_unmapped_metagenomics_ganon2_quick`; rule requires each prefix to have `.hibf` or `.ibf` plus `.tax`. No existing S3/FSx Ganon2 DB found. Conda build env `/fsx/resources/environments/ganon2-build-20260528` created with `ganon 2.4.1`; Slurm job `3302` built RefSeq ABFV complete-genomes top1 prefix `/fsx/resources/metagenomics/ganon2/dayoa_qc_refseq_abfv_complete_top1_20260528`; manifest completed at `2026-05-28T05:55:20+00:00`; output `.hibf` was `23G`, `.tax` was `943K`; copied to `/fsx/references/runtime_assets/tool_specific_resources/ganon2/`; FSx export task `task-0fe3cfb6b91a6756b` succeeded; S3 `head-object` passed for `.hibf`, `.tax`, and `.manifest.txt`. | User amended plan to add Ganon2 if absent. | Durable Ganon2 workflow prefix is `/fsx/references/runtime_assets/tool_specific_resources/ganon2/dayoa_qc_refseq_abfv_complete_top1_20260528`; final MultiQC dry-run command includes `produce_unmapped_metagenomics_ganon2_quick` and `unmapped_metagenomics_ganon2`. |
| VER-001 | DayOA version | Use DayOA `2.0.13` for dry-run/live, not `2.0.11`. | SUCCESS | plan_amendment | Gate 1 | orchestrator | Remote checkout switched to tag `2.0.13`, commit `30dd313053368be63a8362a54f33331ee124b3c7`. | User corrected required version before dry-run/live. | Tag switched before workflow launch. |
| CFG-001 | Remote config | Backup default `config/units.tsv`, copy one-row `config/units.ILMN20x-ONT10x.tsv`, and hard-validate no 15x/7x rows. | SUCCESS | config_or_startup_contract | Gate 1 | orchestrator | `.ignore/inflection_20x10x_kitchensink_j250_20260528T043733Z_units_prep.log`; backup `config/units.tsv.bak.20260528T043733Z` sha256 `c4dff89293e7cdcfddbf40cc51e6f26efce45504841ca003c1aec3377ebd55b0`; active `config/units.tsv` sha256 `176b3eda3c3991bc4dc9fa1f72edfce556f264ef2ab29ba64b8c086f7d8e758a`; validation confirmed exactly one data row and no `15x`, `7x`, `ILMN15X`, or `ONT7X`. |  | Active unit table is the 20x/10x one-row file. |
| DRY-001 | Dry-run | Run requested target set with `-j 250 --rerun-triggers mtime -n` from initialized interactive `ubuntu` tmux/login-shell pane. | FAIL | contract_test | Gate 2 | orchestrator | Dry-run ran in tmux session `inflection_20x10x_kitchensink_j250_20260528T043733Z` and returned `rc=1`; staged gate checker reported `GATE_FAIL` because dry-run rc was not `0`. Log: `.ignore/inflection_20x10x_kitchensink_j250_20260528T043733Z_dryrun_tmux.log`. | Snakemake DAG failed before job stats with `MissingInputException in rule write_dayoa_evidence_manifest`; missing inputs were `results/day/hg38_broad/reports/DAY_final_multiqc_data/multiqc.log`, `multiqc_data.json`, `multiqc_sources.txt`, and `multiqc_general_stats.txt`. | Dry-run command was executed after fixing a launcher quoting error by sending the missing dry-run line into the already initialized tmux pane; the workflow dry-run itself failed, so live execution is not allowed under the plan. |
| GATE-001 | Dry-run gate | Stop unless dry-run exits 0, only 20x/10x sample appears, no align/dedup/variant/segdup/CNV/mito/EH/VB2 reruns appear, and requested report work is present. | BLOCKED | legitimate_safety_handling | Gate 2 | orchestrator | Dry-run rc was `1`; DAG stopped at `write_dayoa_evidence_manifest` before a job-stats table could prove absence of heavy reruns. Unit/sample scope in the dry-run log showed only `ILMN20X-ONT10X`. | Gate condition `Dry-run exits 0` failed; blocking rule is `write_dayoa_evidence_manifest` with missing final MultiQC data-dir inputs. | Live run must not launch unless the user approves a DayOA/state repair or command adjustment and a new dry-run exits `0`. |
| LIVE-001 | Live run | If and only if dry-run gate passes, run exact command without `-n` in the same remote tmux shell. | BLOCKED | feature_implementation | Gate 3 | orchestrator | Not launched. | Dry-run gate failed. | Exact live command remains blocked by Gate 2. |
| ACCEPT-001 | Acceptance | Verify workflow success, empty queue for run, final MultiQC, expected rollups, metagenomics output, and no VerifyBamID2. | BLOCKED | contract_test | Gate 5 | orchestrator | Not run because live workflow was not launched. | Dry-run gate failed. | Acceptance cannot be evaluated until a live run is allowed and completes. |
| DRY-002 | Dry-run retry | User amended plan to retry dry-run without running `write_dayoa_evidence_manifest`. | FAIL | plan_amendment | Gate 2 | orchestrator | Retry with `--omit-from write_dayoa_evidence_manifest -n` ran in existing initialized tmux session and returned `rc=1`; Snakemake still failed at `write_dayoa_evidence_manifest`. | `produce_multiqc_all` explicitly requires `reports/dayoa_evidence_manifest.json`, so omitting the rule with `--omit-from` did not remove the evidence-manifest target edge during DAG construction. | The literal omit-rule flag was insufficient; retrying with `multiqc_final_wgs` instead of `produce_multiqc_all` to keep final MultiQC while not targeting the evidence manifest. |
| GATE-002 | Retry gate | Evaluate the omit-rule dry-run. Live remains blocked unless the retry exits `0` and proves no align/dedup/variant/segdup/CNV/mito/EH/VB2 reruns. | BLOCKED | legitimate_safety_handling | Gate 2 | orchestrator | Omit-rule retry rc was `1`; no job-stats table was available. | `produce_multiqc_all` still pulled `write_dayoa_evidence_manifest`. | Live remains blocked. |
| DRY-003 | Dry-run retry without evidence target | Retry dry-run with `multiqc_final_wgs` replacing `produce_multiqc_all`, so `write_dayoa_evidence_manifest` is not a target dependency. | FAIL | plan_amendment | Gate 2 | orchestrator | Retry got past the evidence-manifest target edge and printed only the `ILMN20X-ONT10X` wildcard set, but returned `rc=1` before job stats. | Missing Singularity image `/fsx/resources/environments/containers/ubuntu/ip-10-0-0-144/0cf0f68bb95f27c2fb097742ca8a47e7.simg`, which is the Snakemake cache hash for `docker://multiqc/multiqc:v1.35`. | Evidence manifest was no longer the blocker; container-cache setup is required before the dry-run can reach job stats. |
| CONT-001 | Container cache | Pre-pull required containers for the no-evidence dry-run into the profile `singularity-prefix`. | NO_LONGER_NEEDED | config_or_startup_contract | Gate 2 | orchestrator | The upstream MultiQC image and VEP image were pre-pulled after `DRY-003`, but the user amended the runtime contract before the next dry-run: the upstream `docker://multiqc/multiqc:v1.35` image is not acceptable for this run because DayOA must use the `lsmc-bio` MultiQC release with Ultima and AlignStats support. | User amended the required MultiQC runtime. | Superseded; do not use the upstream MultiQC container for retry/live. |
| MQC-001 | MultiQC runtime | Patch the remote DayOA run checkout so MultiQC rules use the DayOA-pinned `lsmc-bio` MultiQC conda env (`1.36.dev0-lsmc.6`) instead of `docker://multiqc/multiqc:v1.35`. | IN_PROGRESS | plan_amendment | Gate 2 | orchestrator | Remote inspection at `2026-05-28T06:33Z` confirmed `workflow/envs/multiqc_v0.1.yaml` pins `lsmc-bio/MultiQC` tag `1.36.dev0-lsmc.6`, while report rules still hardcode `docker://multiqc/multiqc:v1.35`. | User amended the runtime contract; the hardcoded container bypasses the required hacked MultiQC release. |  |
| DRY-004 | Dry-run retry after container cache setup | Retry `multiqc_final_wgs` no-evidence dry-run after container images are present. | NO_LONGER_NEEDED | plan_amendment | Gate 2 | orchestrator | The container-cache retry was superseded by the user amendment requiring the `lsmc-bio` MultiQC release rather than the upstream container. | User amended the required MultiQC runtime. | Replaced by `DRY-005`. |
| GATE-004 | Retry gate after container cache setup | Evaluate post-container dry-run. Live remains blocked unless the retry exits `0` and proves no align/dedup/variant/segdup/CNV/mito/EH/VB2 reruns. | NO_LONGER_NEEDED | legitimate_safety_handling | Gate 2 | orchestrator | The container-cache retry was superseded by the user amendment requiring the `lsmc-bio` MultiQC release rather than the upstream container. | User amended the required MultiQC runtime. | Replaced by `GATE-005`. |
| DRY-005 | Dry-run retry with lsmc-bio MultiQC | Retry `multiqc_final_wgs` no-evidence dry-run after the remote run checkout is corrected to use the `lsmc-bio` MultiQC env. | OPEN | plan_amendment | Gate 2 | orchestrator | Pending `MQC-001`. | User requested not to run `write_dayoa_evidence_manifest` and then amended the MultiQC runtime requirement. |  |
| GATE-005 | Retry gate with lsmc-bio MultiQC | Evaluate the `lsmc-bio` MultiQC dry-run. Live remains blocked unless the retry exits `0` and proves no align/dedup/variant/segdup/CNV/mito/EH/VB2/VerifyBamID2 reruns. | OPEN | legitimate_safety_handling | Gate 2 | orchestrator | Pending `DRY-005`. |  |  |

## Command Contract

## Execution Notes

- `2026-05-28T05:16Z`: Ganon2 build job `3302` still `RUNNING` on `i192mem-dy-all-1` with `48` CPUs, `256G`, and `--comment daylily-global`; prefix `/fsx/resources/metagenomics/ganon2/dayoa_qc_refseq_abfv_complete_top1_20260528`; download directory had `1357` files, `895M`; final `.hibf/.ibf` and `.tax` outputs were not present yet.
- `2026-05-28T05:20Z`: Ganon2 build job `3302` still `RUNNING` at `7:25`; download directory had `3422` files, `3.7G`; final output files still only included the manifest, so validation/export remains pending.
- `2026-05-28T05:24Z`: staged dry-run launcher `/home/ubuntu/inflection_20x10x_launch_dryrun.sh`; it creates a new tmux session named `inflection_20x10x_kitchensink_j250_20260528T043733Z`, pipes pane output to `.ignore/inflection_20x10x_kitchensink_j250_20260528T043733Z_dryrun_tmux.log`, and sends separate `source dyoainit`, `dy-a slurm hg38_broad`, and `dy-r ... -n` commands. It has not been executed; Ganon2 validation/export is still the active gate.
- `2026-05-28T05:25Z`: staged Ganon2 export helper `/home/ubuntu/inflection_20x10x_export_ganon2_db.sh`; it refuses to run while job `3302` is active, requires `.hibf` or `.ibf` plus `.tax` and a `completed_at` manifest marker, copies the built prefix files into `/fsx/references/runtime_assets/tool_specific_resources/ganon2/`, exports those paths through FSx tasking, and verifies S3 `head-object` for the required DB files.
- `2026-05-28T05:25Z`: Ganon2 build job `3302` still `RUNNING` at `12:19`; download directory had `5704` files, `5.1G`; no `.hibf/.ibf` or `.tax` outputs yet.
- `2026-05-28T05:28Z`: staged dry-run gate checker `/home/ubuntu/inflection_20x10x_gate_dryrun.py`; it parses the tmux dry-run log, validates the return marker, planned rule names, unit/sample scope, VerifyBamID2 absence, forbidden heavy-rule absence, and required downstream/report work presence-or-planning.
- `2026-05-28T05:32Z`: Ganon2 build job `3302` still `RUNNING` at `19:10`; only the manifest existed at the DB prefix, with no `.hibf/.ibf` or `.tax` yet.
- `2026-05-28T05:38Z`: Ganon2 build job `3302` still `RUNNING` at `24:56`; download/build files occupied `9.3G`; only the manifest existed at the DB prefix, with no `.hibf/.ibf` or `.tax` yet.
- `2026-05-28T05:40Z`: dry-run tmux session `inflection_20x10x_kitchensink_j250_20260528T043733Z` created and pane logging enabled. The staged launcher hit a quoting syntax error after `source dyoainit` and `dy-a slurm hg38_broad`; no dry-run command had been sent at the failure point. The missing dry-run marker and command were then sent into the same initialized tmux session without creating a duplicate.
- `2026-05-28T05:41Z`: dry-run completed with `__DAYOA_DRYRUN_DONE_RC_1__`. Snakemake failed during DAG construction at `write_dayoa_evidence_manifest`, missing final MultiQC data-dir inputs: `DAY_final_multiqc_data/multiqc.log`, `multiqc_data.json`, `multiqc_sources.txt`, and `multiqc_general_stats.txt`. The staged gate checker also returned `GATE_FAIL` because rc was not `0`. Per the user gate, no live command was launched.
- `2026-05-28T05:43Z`: Slurm queue contained only Ganon2 build job `3302`, still `RUNNING` at `30:23`; the Ganon2 DB prefix still lacked `.hibf/.ibf` and `.tax`.
- `2026-05-28T05:44Z`: read-only report-directory check confirmed `results/day/hg38_broad/reports/DAY_final_multiqc.html`, `dayoa_evidence_manifest.json`, and all four required `DAY_final_multiqc_data/*` files are absent. The reports directory only had benchmark summaries, so the dry-run failure is a DAG declaration/state issue rather than a stale final HTML shortcut.
- `2026-05-28T05:55Z`: Ganon2 build job `3302` still `RUNNING` at `41:47`; prefix now had `/fsx/resources/metagenomics/ganon2/dayoa_qc_refseq_abfv_complete_top1_20260528.hibf` (`23G`) and `.tax` (`943K`), but the manifest still lacked `completed_at`; export remains gated on job completion and manifest validation.
- `2026-05-28T05:58Z`: Ganon2 build job `3302` completed; manifest contained `completed_at=2026-05-28T05:55:20+00:00`; outputs were `.hibf` (`23645453479` bytes), `.tax` (`964706` bytes), and `.manifest.txt`.
- `2026-05-28T06:00Z`: Ganon2 export helper copied `.hibf`, `.tax`, and `.manifest.txt` into `/fsx/references/runtime_assets/tool_specific_resources/ganon2/`; FSx export task `task-0fe3cfb6b91a6756b` went `PENDING -> EXECUTING -> SUCCEEDED`; S3 `head-object` passed for all three required objects under `s3://lsmc-dayoa-references-usw2/runtime_assets/tool_specific_resources/ganon2/`.
- `2026-05-28T06:01Z`: final remote status check showed empty Slurm queue, both tmux sessions preserved, DayOA `2.0.13` at commit `30dd313053368be63a8362a54f33331ee124b3c7`, active `config/units.tsv` still the one-row 20x/10x file with sha256 `176b3eda3c3991bc4dc9fa1f72edfce556f264ef2ab29ba64b8c086f7d8e758a`, and the Ganon2 reference DB files present under `/fsx/references/runtime_assets/tool_specific_resources/ganon2/`.
- `2026-05-28T06:22Z`: user amended the dry-run gate: do not run `write_dayoa_evidence_manifest` and retry with `-n`.
- `2026-05-28T06:23Z`: retry with `--omit-from write_dayoa_evidence_manifest -n` returned `rc=1`; Snakemake still failed at `write_dayoa_evidence_manifest`. Inspection showed `produce_multiqc_all` requires `reports/dayoa_evidence_manifest.json`, so the next retry replaces `produce_multiqc_all` with `multiqc_final_wgs` to keep final MultiQC without targeting the evidence manifest.
- `2026-05-28T06:25Z`: retry with `multiqc_final_wgs` got past evidence-manifest wiring and printed only the `ILMN20X-ONT10X` wildcard set, then returned `rc=1` while validating missing Singularity image `/fsx/resources/environments/containers/ubuntu/ip-10-0-0-144/0cf0f68bb95f27c2fb097742ca8a47e7.simg`. The hash maps to `docker://multiqc/multiqc:v1.35`; `docker://ensemblorg/ensembl-vep:release_114.2` is also in the requested target set and maps to `27d2131deefbb283d9ca695343698d4b.simg`.

## Terminal Status

- Ledger rows are terminal: `G0-001`, `DB-001`, `DB-002`, `GANON2-001`, `VER-001`, and `CFG-001` are `SUCCESS`; `DRY-001` is `FAIL`; `GATE-001`, `LIVE-001`, and `ACCEPT-001` are `BLOCKED`.
- Workflow objective did not complete. The exact live command was not launched because the dry-run gate failed with `rc=1` at `write_dayoa_evidence_manifest`.
- Durable metagenomics DB objective completed for both Kraken2 and Ganon2. Future clusters mounting `s3://lsmc-dayoa-references-usw2` at `/fsx/references` can use:
  - Kraken2 DB: `/fsx/references/runtime_assets/tool_specific_resources/metagenomics/kraken2/k2_pluspfp_16_GB_20260226`
  - Ganon2 DB prefix: `/fsx/references/runtime_assets/tool_specific_resources/ganon2/dayoa_qc_refseq_abfv_complete_top1_20260528`

Dry-run command to execute from the remote interactive DayOA environment:

```bash
dy-r produce_sent_align produce_dmd_dedup_cram produce_sentdhiomr_sv produce_snv_concordances produce_sentdhiomr_snv_vcf produce_sentdhiomr_cnv produce_sentdhiomr_mito produce_sentdhiomr_segdup produce_expansionhunter produce_alignstats produce_relatedness produce_peddy produce_vep produce_gatk_contam_estimate produce_site_mix_contam_estimate produce_unmapped_metagenomics_quick produce_unmapped_metagenomics_ganon2_quick produce_multiqc_all --config units_table=/fsx/analysis_results/ubuntu/inflection_20260527-2.0.11/daylily-omics-analysis/config/units.tsv 'multiqc_qc={"enable_tools":["vep","unmapped_metagenomics","unmapped_metagenomics_ganon2"]}' 'unmapped_metagenomics={"kraken2_db":"/fsx/references/runtime_assets/tool_specific_resources/metagenomics/kraken2/k2_pluspfp_16_GB_20260226","ganon2_db_prefixes":["/fsx/references/runtime_assets/tool_specific_resources/ganon2/dayoa_qc_refseq_abfv_complete_top1_20260528"],"threads":16,"mem_mb":64000,"partition":"i192mem,i192bigmem","read_limit":"all"}' -j 250 -p -k -T 0 --rerun-triggers mtime --max-jobs-per-second 8 -n
```

Live command is the exact same command with only `-n` removed.
