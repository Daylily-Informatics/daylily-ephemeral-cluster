# dyecX4 ILMN Latest Pangenome Model Rerun Ledger

Controlling request: run the ILMN pangenome workflow using the latest ILMN pangenome model and investigate whether ILMN and ULTIMA pangenome workflow commands use inconsistent command series.
Ledger path: `docs/plans/20260610T024325Z_dyecX4_ilmn_latest_pangenome_model_ledger.md`
Created: `2026-06-10T02:43:25Z`

## Gate 0 Baseline

- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DYEC branch/status: `jem-dev`, tracked clean; older untracked plan/log artifacts under `docs/plans/`
- DYEC version: `10.0.11`
- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DayOA branch/status: `jem-dev`, clean
- DayOA describe: `10.0.3`
- Cluster: `dyecX4`, region `us-west-2`, profile `lsmc`
- Cluster state: `CREATE_COMPLETE`; compute fleet `RUNNING`; headnode `i-05815cdeec4a6dad8`; Slurm queue empty at baseline
- Prior successful ILMN pangenome run: `pg_ilmn_hg002_hg003_30x_pangenome_concordance_20260609T200121Z`
- Prior successful ULTIMA pangenome run: `pg_ultima_hg003_30x_pangenome_concordance_20260609T194248Z`

## Investigation Notes

- FSx bundle inventory under `/fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.02/bundles` contains `SentieonIlluminaPangenomeRealignWGS1.0.bundle`, `SentieonIlluminaPangenomeWGS1.0.bundle`, and `SentieonIlluminaPangenomeRealignWGS1.2.bundle`; no ILMN `WGS1.3` bundle was present.
- Selected latest explicit ILMN pangenome model: `/fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.02/bundles/SentieonIlluminaPangenomeRealignWGS1.2.bundle`.
- DayOA source comparison:
  - ILMN rule: `workflow/rules/sentieon_pangenome_shortreads.smk`
  - ULTIMA rule: `workflow/rules/sentieon_pangenome_ug.smk`
  - Both rules call `bin/dayoa_sentieon_cli sentieon-pangenome`, run with `threads: 128`, use NVMe partitions `i384nvme,i192nvme,i128nvme`, and create temporary work under `/scratch`, not `/dev/shm`.
  - Expected platform differences: ILMN consumes paired FASTQs with `PL:ILLUMINA`, `--pcr_free`, ILMN model `SentieonIlluminaPangenomeRealignWGS1.2.bundle`, and pop VCF `pop-v20-20260528.vcf.gz`; ULTIMA consumes a CRAM plus patched KMC, uses `UltimaReadFilter`, ULTIMA model `SentieonUltimaPangenomeRealignWGS1.3.bundle`, conservative PCR indel model, and pop VCF `pop-v20g41-20251216.vcf.gz`.
- Prior rendered logs confirm the same wrapper family:
  - ILMN previous logs rendered `bwa mem`, `minimap2`, `DNAscope`, and `DNAModelApply` from `SentieonIlluminaPangenomeRealignWGS1.2.bundle`; `sentieon-cli exit code: 0`.
  - ULTIMA previous logs rendered `minimap2`, `DNAscope` with `UltimaReadFilter`, and `DNAModelApply` from `SentieonUltimaPangenomeRealignWGS1.3.bundle`; `sentieon-cli exit code: 0`.
- ONT solo comparison scope added by follow-up request:
  - Supported catalog ONT solo input is HG003 5x slim CRAM, not a discovered 30x ONT input: `/fsx/references/genomic_data/organism_reads_slim/cram/H_sapiens/giab/agbt_2026/ont/HG003_5x.cleaned.cram`.
  - Manifest source for launch: `docs/plans/20260526T224018Z_blahab44_inputs/generated/ont_snv_alignstats/20260526T233649Z_58971985_samples.tsv` and matching `units.tsv`.
  - Headnode verified current model bundle: `/fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.02/bundles/DNAscopeONT2.3.bundle`.
  - Headnode verified old model bundle: `/fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.02/bundles/DNAscopeONT2.2.bundle`.
  - No active `conda env create` process was present before the ONT comparison launch gate.

## Fresh ILMN Latest-Model Run

- Analysis id: `pg_ilmn_hg002_hg003_30x_latest_ilmn_model_20260610T025238Z`
- Tmux session: `pg_ilmn_hg002_hg003_30x_latest_ilmn_model_20260610T025238Z`
- Run state directory: `/home/ubuntu/daylily-runs/pg_ilmn_hg002_hg003_30x_latest_ilmn_model_20260610T025238Z`
- DayOA repo path: `/fsx/analysis_results/ubuntu/pg_ilmn_hg002_hg003_30x_latest_ilmn_model_20260610T025238Z/daylily-omics-analysis`
- DayOA ref: `10.0.3`
- DYEC version: `10.0.11`
- Command:
  `dy-r produce_pangenome_sr_vcf produce_snv_concordances -p -j 150 -k -T 0 --rerun-triggers mtime --sentieon-start-jitter --isolated-conda-prefix --config aligners=[pangenome_sr] dedupers=[spmd] snv_callers=[sentpg]`
- Export destination:
  `s3://lsmc-dayoa-analysis-results-usw2/validation/dyecX4/10.0.11/PR-evidence/analysis_results/ubuntu/pg_ilmn_hg002_hg003_30x_latest_ilmn_model_20260610T025238Z/`
- Initial status: launched via `dyec workflow launch`; controller active with `started_at=2026-06-10T02:53:36Z`.
- Runtime evidence:
  - Active profile config: `sentieon_pangenome_sr.model=/fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.02/bundles/SentieonIlluminaPangenomeRealignWGS1.2.bundle`, `threads=128`, `partition=i384nvme,i192nvme,i128nvme`, `distribution=block`.
  - DAG resolved `aligners=[pangenome_sr]`, `deduper=[spmd]`, `snv_callers=[sentpg]`.
  - Snakemake created isolated conda envs under `.snakemake/conda`.
  - Slurm pangenome jobs submitted: `59` for HG002 and `60` for HG003, both initially in `CF` on `i384nvme`.
  - Rendered HG003 shell command used `bin/dayoa_sentieon_cli sentieon-pangenome`, model `SentieonIlluminaPangenomeRealignWGS1.2.bundle`, `--pop_vcf pop-v20-20260528.vcf.gz`, paired FASTQs, `PL:ILLUMINA`, `$pcr_flag`, and `-t 128`.
  - At `2026-06-10T03:03:11Z`, jobs `59` and `60` were `R` on `i384nvme`; per-sample rule logs showed `INSTANCE TYPE: m8idb.96xlarge`, `TMPDIR created: /scratch/pangenome_sr_tmp_*`, and model `SentieonIlluminaPangenomeRealignWGS1.2.bundle`.
  - The pangenome logs include the same non-terminal `Error: no 'multiqc' found in the PATH` line seen in the prior successful ILMN pangenome run; terminal status remains pending on `sentieon-cli exit code`.

## Legacy hg38 Solo Concordance Run

- Analysis id: `ilmn_hg002_hg003_30x_oldhg38_solo_concordance_20260610T030657Z`
- Tmux session: `ilmn_hg002_hg003_30x_oldhg38_solo_concordance_20260610T030657Z`
- Run state directory: `/home/ubuntu/daylily-runs/ilmn_hg002_hg003_30x_oldhg38_solo_concordance_20260610T030657Z`
- DayOA repo path: `/fsx/analysis_results/ubuntu/ilmn_hg002_hg003_30x_oldhg38_solo_concordance_20260610T030657Z/daylily-omics-analysis`
- DayOA ref: `10.0.3`
- Genome: `hg38`
- Command:
  `dy-r produce_snv_concordances -p -j 150 -k -T 0 --rerun-triggers mtime --sentieon-start-jitter --isolated-conda-prefix --config aligners=[sent] dedupers=[dmd] snv_callers=[sentd]`
- Export destination:
  `s3://lsmc-dayoa-analysis-results-usw2/validation/dyecX4/10.0.11/PR-evidence/analysis_results/ubuntu/ilmn_hg002_hg003_30x_oldhg38_solo_concordance_20260610T030657Z/`
- Initial status: launched via `dyec workflow launch`; controller active with `started_at=2026-06-10T03:07:22Z`.
- Runtime evidence:
  - Active command log: `snakemake --profile=.../config/day_profiles/slurm --conda-prefix .../.snakemake/conda produce_snv_concordances -p -j 150 -k -T 0 --rerun-triggers mtime --config aligners=[sent] dedupers=[dmd] snv_callers=[sentd]`.
  - Activation log confirms `genome build set to ::: hg38`.
  - DAG resolved `aligners=[sent]`, `deduper=[dmd]`, `snv_callers=[sentd]`, samples HG002/HG003.
  - At `2026-06-10T03:08:38Z`, the hg38 run was creating `workflow/envs/rtgtools_v0.1.yaml` under its isolated `.snakemake/conda` prefix; pangenome jobs were running and no other conda builder was active.
  - At `2026-06-10T03:10:25Z`, `rtgtools_v0.1` and `sentieon_v0.1` envs were created; `sentD_v0.2` was building; only one conda env builder was active.
  - At `2026-06-10T03:12:24Z`, Slurm jobs were submitted for standard `sentieon_bwa_sort`: job `61` for HG002 and job `62` for HG003. Rendered HG003 command used `/fsx/references/genomic_data/organism_references/H_sapiens/hg38/fasta_fai_minalt/GRCh38_no_alt_analysis_set.fasta`, `SentieonIlluminaWGS2.2.bundle/bwa.model`, `PL:ILLUMINA`, and `/scratch/dayoa_sentieon_*` temp paths.

## ONT HG003 Solo Model Comparison

- Current-model analysis id: `ont_hg003_5x_current_model_concordance_20260610T031836Z`
- Old-model analysis id: `ont_hg003_5x_old_model_concordance_20260610T031836Z`
- Samples file: `docs/plans/20260526T224018Z_blahab44_inputs/generated/ont_snv_alignstats/20260526T233649Z_58971985_samples.tsv`
- Units file: `docs/plans/20260526T224018Z_blahab44_inputs/generated/ont_snv_alignstats/20260526T233649Z_58971985_units.tsv`
- Genome: `hg38_broad`
- Current-model command:
  `dy-r produce_sentdont_snv_vcf produce_snv_concordances -p -j 5 -k -T 0 --rerun-triggers mtime --isolated-conda-prefix --config aligners=[ont] dedupers=[na] snv_callers=[sentdont] 'sentdont={"dna_scope_snv_model":"/fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.02/bundles/DNAscopeONT2.3.bundle","dna_scope_apply_model":"/fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.02/bundles/DNAscopeONT2.3.bundle"}'`
- Old-model command:
  `dy-r produce_sentdont_snv_vcf produce_snv_concordances -p -j 5 -k -T 0 --rerun-triggers mtime --isolated-conda-prefix --config aligners=[ont] dedupers=[na] snv_callers=[sentdont] 'sentdont={"dna_scope_snv_model":"/fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.02/bundles/DNAscopeONT2.2.bundle","dna_scope_apply_model":"/fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.02/bundles/DNAscopeONT2.2.bundle"}'`
- Export destinations:
  - `s3://lsmc-dayoa-analysis-results-usw2/validation/dyecX4/10.0.11/PR-evidence/analysis_results/ubuntu/ont_hg003_5x_current_model_concordance_20260610T031836Z/`
  - `s3://lsmc-dayoa-analysis-results-usw2/validation/dyecX4/10.0.11/PR-evidence/analysis_results/ubuntu/ont_hg003_5x_old_model_concordance_20260610T031836Z/`

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Baseline | Record repo, cluster, queue, and prior run state before launching new work | SUCCESS | config_or_startup_contract | Gate 0 | orchestrator | `git status --short --branch`; DayOA `git describe --tags --always --dirty` -> `10.0.3`; `dyec --json version` -> `10.0.11`; cluster `CREATE_COMPLETE`/fleet `RUNNING`; `dyec headnode jobs` empty |  | Baseline recorded; no destructive cleanup planned. |
| CMD-001 | Investigation | Compare ILMN and ULTIMA pangenome command surfaces from DayOA source and prior rendered logs | SUCCESS | feature_implementation | Gate 1 | orchestrator | Source: `workflow/rules/sentieon_pangenome_shortreads.smk`, `workflow/rules/sentieon_pangenome_ug.smk`, `config/day_profiles/slurm/templates/rule_config.yaml`; rendered logs from prior ILMN and ULTIMA analyses show `sentieon-pangenome` wrapper with platform-specific internals |  | Same DayOA wrapper family; differences are expected platform/input/model/pop-VCF/read-filter differences, not an unrelated command series. |
| MODEL-001 | Investigation | Identify available ILMN pangenome model bundles and select the latest explicit ILMN model | SUCCESS | config_or_startup_contract | Gate 1 | orchestrator | FSx bundle inventory: latest explicit ILMN pangenome bundle is `SentieonIlluminaPangenomeRealignWGS1.2.bundle`; no ILMN `WGS1.3` bundle present |  | Selected `SentieonIlluminaPangenomeRealignWGS1.2.bundle`; prior successful ILMN run already used this model. |
| RUN-001 | Fresh rerun | Launch ILMN HG002/HG003 pangenome plus `produce_snv_concordances` using the selected latest ILMN model through `dyec workflow launch`/`dy-r` | IN_PROGRESS | feature_implementation | Gate 2 | agent-ilmn | `dyec workflow launch` returned tmux session and repo path; `dyec workflow status` started at `2026-06-10T02:53:36Z`; Slurm jobs `59`/`60` running on `i384nvme`; rule logs confirm `/scratch` TMPDIR and ILMN model `SentieonIlluminaPangenomeRealignWGS1.2.bundle` |  | Pangenome jobs running; terminal workflow status pending. |
| EXPORT-001 | Evidence | Verify workflow exit, DRA export receipt, output VCF/index files, and giabHC concordance F-scores | OPEN | feature_implementation | Gate 3 | orchestrator | Pending |  | Pending terminal workflow/export evidence. |
| HG38-001 | Comparison run | Launch the same HG002/HG003 ILMN 30x samples using legacy `hg38` solo SNV concordance workflow | IN_PROGRESS | feature_implementation | Gate 2 | agent-ilmn | `dyec workflow launch` returned tmux session and repo path; `dyec workflow status` started at `2026-06-10T03:07:22Z`; activation log shows `genome build set to ::: hg38`; DAG resolved `sent`/`dmd`/`sentd`; Slurm jobs `61`/`62` submitted for `sentieon_bwa_sort`; exact command recorded above |  | Controller active; standard hg38 alignment jobs submitted. |
| HG38-002 | Comparison evidence | Verify legacy `hg38` solo run exits 0, exports by DRA, and produces giabHC concordance metrics for HG002/HG003 | OPEN | feature_implementation | Gate 3 | orchestrator | Pending |  | Pending workflow/export evidence. |
| ONT-001 | Comparison run | Launch HG003 ONT solo `produce_snv_concordances` with current `DNAscopeONT2.3.bundle` | IN_PROGRESS | feature_implementation | Gate 2 | agent-ont | `dyec workflow launch` returned tmux session `ont_hg003_5x_current_model_concordance_20260610T031836Z`, run dir `/home/ubuntu/daylily-runs/ont_hg003_5x_current_model_concordance_20260610T031836Z`, repo path `/fsx/analysis_results/ubuntu/ont_hg003_5x_current_model_concordance_20260610T031836Z/daylily-omics-analysis`; export destination recorded above |  | Controller launched; terminal workflow/export evidence pending. |
| ONT-002 | Comparison run | Launch HG003 ONT solo `produce_snv_concordances` with old `DNAscopeONT2.2.bundle` after current-model conda-build window clears | OPEN | feature_implementation | Gate 2 | agent-ont | Input/model preflight complete; launch pending |  | Pending launch. |
| ONT-003 | Comparison evidence | Verify both ONT model-comparison runs exit 0, export by DRA, and produce giabHC concordance metrics | OPEN | feature_implementation | Gate 3 | orchestrator | Pending |  | Pending workflow/export evidence. |

## Final State Counts

- `OPEN`: 4
- `IN_PROGRESS`: 3
- `ATTEMPTING_BUGFIX`: 0
- `SUCCESS`: 3
- `BLOCKED`: 0
- `FAIL`: 0
