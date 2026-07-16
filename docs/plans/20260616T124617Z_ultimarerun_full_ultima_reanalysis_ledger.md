# Ultimarerun Full Ultima Reanalysis Ledger

Controlling request: run the mounted `ultima-23andme-40x` DRA cohort on `ultimarerun` as one DayOA workset, including HG003, with pangenome SNV, alignstats, mosdepth, contamination, relatedness/somalier, HG003 concordance where possible, Sentieon mito/segdup/CNV, ExpansionHunter, and Ultima MultiQC.

Ledger path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260616T124617Z_ultimarerun_full_ultima_reanalysis_ledger.md`

## Gate 0 Baseline

- Local DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`; `git status --short --branch` -> `## jem-dev...origin/jem-dev`; exact tag `10.0.41`.
- Local DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`; `git status --short --branch` -> `## jem-dev...origin/jem-dev`; exact tag `10.0.24`.
- Local activated DYEC executable drift: `daylily-ec version` and `dyec version` -> `10.0.34`; do not rely on the local installed executable for version semantics.
- Cluster: `ultimarerun`, region `us-west-2`, profile `lsmc`; ParallelCluster `clusterStatus=UPDATE_COMPLETE`, `computeFleetStatus=RUNNING`, headnode `i-0fd49ae30fc10b04e`, private IP `10.0.0.182`.
- Headnode shell: interactive Session Manager shell as `ubuntu` on `ip-10-0-0-182`.
- Headnode DYEC executable drift: `daylily-ec version` and `dyec version` -> `10.0.40.dev1+gf8c879a5`; `day-clone --list` default DayOA ref -> `10.0.23`.
- Version correction: because DYEC `10.0.41` is expected to pin DayOA `10.0.24`, and the live headnode default is stale, the workset must use explicit `day-clone -t 10.0.24` and verify `git describe --tags --exact-match HEAD == 10.0.24` before any `dy-r`.
- Mount: `daylily-ec mounts list --cluster ultimarerun --region us-west-2 --profile lsmc` -> `MOUNT_ID=ultima-23andme-40x`, `RUN_ID=ultima-23andme-40x`, `LIFECYCLE=AVAILABLE`, `ASSOCIATION_ID=dra-0c84c1391b453101c`, `HEADNODE_PATH=/fsx/run_dir_mounts/ultima-23andme-40x/`, `SOURCE_S3_URI=s3://lsmc-ssf-sequencing-data/staged_external_data/23andMePilot/ultima/40x/`.
- Mount policy: use existing mounted CRAM/CRAI paths directly; no remount and no broad S3 copy into `/fsx`.
- Mounted inventory: `find /fsx/run_dir_mounts/ultima-23andme-40x -type f -name '*.cram' | wc -l` -> `95`; `find ... -name '*.crai' | wc -l` -> `95`.
- Queue baseline: `squeue -o '%i  %P  %C  %t  %N  %c  %T  %m  %M  %D  %j'` -> header only, no active jobs.

## Agent Ledger

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | DYEC/cluster | Record cluster, mount, DYEC/DayOA refs, queue, and existing worksets. | SUCCESS | feature_implementation | Gate 0 | Agent 1 | Gate 0 baseline above records `ultimarerun`, `dra-0c84c1391b453101c`, 95 CRAM/CRAI pairs, local DYEC tag `10.0.41`, DayOA tag `10.0.24`, headnode executable drift, and no broad S3 copy. |  | Baseline complete; explicit DayOA `10.0.24` clone is required because headnode defaults are stale. |
| MANIFEST-001 | DayOA workset | Build full-cohort `samples.tsv` and `units.tsv` from mounted CRAMs. | SUCCESS | feature_implementation | Gate 1 | Agent 1 | Remote generator wrote `/fsx/analysis_results/ubuntu/ultimarerun_full_ultima_95samples_20260616T124617Z/daylily-omics-analysis/config/samples.tsv` and `config/units.tsv`; validation reported `config/samples.tsv data_rows=95 columns=13` and `config/units.tsv data_rows=95 columns=41`. Source CRAM root is `/fsx/run_dir_mounts/ultima-23andme-40x`; all `.cram.crai` files were required to exist and be non-empty. Sex metadata source was `/Users/jmajor/projects/lsmc/archived/bfx_pipe/daylily-ephemeral-cluster/processing_prod_data/23andme-run1-ILMN/sex_inference.tsv`, high-confidence male for all mounted cohort samples. |  | Manifest generation complete. HG003 is the only positive control and only row with GIAB truth path; non-HG003 rows are research gdna with no truth path. |
| WORKSET-001 | DayOA workset | Create new workset on headnode in persistent tmux. | SUCCESS | feature_implementation | Gate 1 | Agent 2 | Persistent tmux session `ultima_full95_20260616T124617Z` has one window/one pane. Explicit clone command `day-clone --executing-entity ubuntu -d ultimarerun_full_ultima_95samples_20260616T124617Z -t 10.0.24` created `/fsx/analysis_results/ubuntu/ultimarerun_full_ultima_95samples_20260616T124617Z/daylily-omics-analysis`; `git describe --tags --exact-match HEAD` -> `10.0.24`; `git rev-parse HEAD` -> `cb6ca4c212896b6d563e0c085922b09158657820`. |  | Workset created at the requested path. A first clone without `--executing-entity ubuntu` landed under `/fsx/analysis_results/ultimarerun/...`; it is not the active workset. |
| CONFIG-001 | DayOA workset | Configure active workset for requested caller/QC scope. | SUCCESS | config_or_startup_contract | Gate 2 | Agent 2 | Active config `/fsx/analysis_results/ubuntu/ultimarerun_full_ultima_95samples_20260616T124617Z/daylily-omics-analysis/config/day_profiles/slurm/rule_config.yaml` patched after `dy-a slurm hg38_broad`: `contam_identity.primary_snv_caller` is `sentpg`; `multiqc_qc.enable_tools` is `['contam_identity', 'expansionhunter', 'gatk_contam', 'site_mix', 'relatedness', 'mosdepth', 'alignstats', 'concordance']`; `multiqc_qc.enable_long_running` remains `false` to avoid unrelated long-running defaults. `dy-a` emitted a non-fatal stale/null git tag warning for the cluster runtime. |  | Requested caller/QC scope configured in active workset. |
| DRYRUN-001 | DayOA execution | Run requested dry-run with `dy-r ... -j 369 -p -k -T 0 -n`. | SUCCESS | contract_test | Gate 3 | Agent 3 | Initial dry-run attempt failed before DAG construction because quoted `--config` values were stored in a shell variable and passed literally to Snakemake: `Invalid config definition: Config entry must start with a valid identifier.` Corrected by sending the literal command directly to tmux. Real DAG failure then exposed a workflow contract gap: `contam_identity.primary_snv_caller=sentpg` produced no CRAM-capable pair because `QC_CRAM_ALIGNERS` excludes graph-only `pangenome_ug`. Active-workset patch in `workflow/rules/contam_identity.smk` routes graph SNV VCFs through `pangenome_ug/spmd` and `read_haps` BAM evidence through `ug/na` compat BAM. Final dry-run returned `RETURN CODE: 0` with `total 2989` jobs, including `sentieon_pangenome_ug=95`, `alignstats=95`, `mosdepth=95`, `gatk_contam=95`, `site_mix_contam=95`, `relatedness`, `haplocheck_vcf_contam_identity=95`, `read_haps_contam_identity=95`, `expansionhunter_call=95`, `sentdug_mito_call=95`, `sentdug_call_cnvs=95`, `sentdug_call_segdup=95`, `sentdug_call_segdup_gene=760`, and `rtg_vcfeval_roi=6`. |  | Dry-run succeeds after command-shape correction and active-workset contam-identity pangenome bugfix. |
| RULEGRAPH-001 | DayOA execution | Produce DAG after valid dry-run. | SUCCESS | contract_test | Gate 3 | Agent 3 | Same target/config command with `--rulegraph > rulegraph.dag` returned `RETURN CODE: 0`; remote file `/fsx/analysis_results/ubuntu/ultimarerun_full_ultima_95samples_20260616T124617Z/daylily-omics-analysis/rulegraph.dag` exists, size `5.6K`, `154` lines, starts with `digraph snakemake_dag {`. |  | Rulegraph generated successfully after valid dry-run. |
| LIVE-001 | DayOA execution | Run live cohort command. | IN_PROGRESS | feature_implementation | Gate 4 | Agent 4 | Live `dy-r` command launched in tmux `ultima_full95_20260616T124617Z` with the same target/config command and no `-n`/`--rulegraph`. Controller passed DAG construction, created Haplocheck/read_haps environments, and began Slurm submission. Evidence at `2026-06-16T13:12:33Z`: controller is at 8/2,989 Snakemake steps complete; latest log is `.snakemake/log/2026-06-16T130746.577717.snakemake.log`; first submitted wave is `pre_prep_ultima_cram-*`, 48 CPUs and 50 GB each, jobs `63`-`157` in Slurm `CONFIGURING` on `i192` nodes, including HG003 job `105`. Evidence at `2026-06-16T13:14:32Z`: Slurm state summary `R=120`, `CF=73`, `PD=144`; submitted rule counts include `sentieon_pangenome_ug=60` (`20 CF`, `40 PD`), `sentdug_specialty_bam=60`, `legacy_cram_compat_bam=38`, `mosdepth=31`, `alignstats=30`, `calc_coverage_evenness=29`, `gen_samstats=29`, `goleft=28`, and `expansionhunter_call=28`. Evidence at `2026-06-16T13:17:15Z`: reconnected after `sacct` reported `Slurm accounting storage is disabled`; tmux session still exists; queue summary is `R=139`, `CF=93`, `PD=137`; pangenome submitted count is `sentieon_pangenome_ug=94` (`5 R`, `21 CF`, `68 PD`). Evidence at `2026-06-16T13:31:38Z`: controller is at 169/2,989 steps complete; queue summary is `R=214`, `CF=4`, `PD=151`; pangenome critical path has `sentieon_pangenome_ug=95` (`20 R`, `75 PD`). |  | Live run is active; terminal status pending completion or concrete failure evidence. |
| VERIFY-001 | DayOA outputs | Verify pangenome, specialty, QC, concordance, and Ultima MultiQC outputs or record failure evidence. | OPEN | contract_test | Gate 5 | Agent 4 | Pending. |  |  |
| FINAL-001 | Ledger | Terminalize ledger. | OPEN | plan_amendment | Gate 5 | Agent 1 | Pending. |  |  |

## Target Command Shape

Targets:

```bash
produce_pangenome_ug_vcf produce_alignstats produce_mosdepth produce_gatk_contam_estimate produce_site_mix_contam_estimate produce_global_contam_check produce_relatedness produce_snv_concordances produce_sentdug_mito produce_sentdug_segdup produce_sentdug_cnv produce_expansionhunter produce_multiqc_ultima_reanalysis
```

Shared flags:

```bash
-j 369 -p -k -T 0 --config 'aligners=["ug","pangenome_ug"]' 'snv_callers=["sentpg"]' 'sv_callers=[]'
```

Explicit exclusions:

- Do not run `produce_sentdug_snv_vcf`.
- Do not run `produce_sentdug_sv`.

## Status Log

- `2026-06-16T12:46:17Z`: Ledger created with Gate 0 baseline. Headnode defaults are stale relative to requested DYEC `10.0.41`; workset will clone DayOA explicitly at `10.0.24`.
- `2026-06-16T12:47Z`: Persistent tmux session `ultima_full95_20260616T124617Z` created. Explicit DayOA `10.0.24` clone verified at `/fsx/analysis_results/ubuntu/ultimarerun_full_ultima_95samples_20260616T124617Z/daylily-omics-analysis`.
- `2026-06-16T12:54Z`: Full-cohort manifests installed and validated: 95 sample rows, 95 unit rows, 13/41 columns, all from mounted CRAM/CRAI inventory. Sex metadata is explicit from the prior 23andMe ILMN sex-inference TSV, not inferred in the generator.
- `2026-06-16T12:58Z`: `source dyoainit` and `dy-a slurm hg38_broad` completed in tmux. Active Slurm `rule_config.yaml` patched for `sentpg` contam identity and requested Ultima MultiQC inputs.
- `2026-06-16T13:04Z`: Dry-run initially exposed two issues: shell-variable quoting for `--config`, then a real `sentpg` contam-identity routing gap. Active workset patched `workflow/rules/contam_identity.smk` so pangenome VCF evidence uses `pangenome_ug/spmd` and read_haps BAM evidence uses `ug/na` compat BAM.
- `2026-06-16T13:05Z`: Corrected dry-run returned `RETURN CODE: 0`; DAG contains 2,989 jobs and no linear `produce_sentdug_snv_vcf` or `produce_sentdug_sv` target.
- `2026-06-16T13:06Z`: Rulegraph command returned `RETURN CODE: 0`; `rulegraph.dag` is non-empty (`5.6K`, 154 lines).
- `2026-06-16T13:09Z`: Live command launched. Controller passed DAG construction and started submitting `pre_prep_ultima_cram` jobs; initial queue has jobs `63` through `157` across `i192`/`i128`, with 48 CPUs and `50000M` per job.
- `2026-06-16T13:12Z`: Live monitor shows 8/2,989 steps complete. Slurm has `pre_prep_ultima_cram-*` jobs `63`-`157` in `CONFIGURING` on `i192` nodes, 48 CPUs and `50000M` per job; no controller failure is visible.
- `2026-06-16T13:14Z`: Live monitor shows active compute progression: Slurm state summary `R=120`, `CF=73`, `PD=144`; pangenome caller jobs are submitted (`sentieon_pangenome_ug=60`, `20 CF`, `40 PD`) along with Sentieon specialty BAM prep, ExpansionHunter, mosdepth, alignstats, goleft, and samstats jobs.
- `2026-06-16T13:17Z`: `sacct` is unavailable on this cluster (`Slurm accounting storage is disabled`), and the SSM shell exited after that probe; reconnected as `ubuntu` and verified tmux session `ultima_full95_20260616T124617Z` still exists. Queue summary: `R=139`, `CF=93`, `PD=137`; pangenome jobs are now running (`sentieon_pangenome_ug=94`, `5 R`, `21 CF`, `68 PD`).
- `2026-06-16T13:31Z`: Controller reports 169/2,989 steps complete. Queue summary: `R=214`, `CF=4`, `PD=151`; pangenome critical path is fully submitted with 95 jobs (`20 R`, `75 PD`).
