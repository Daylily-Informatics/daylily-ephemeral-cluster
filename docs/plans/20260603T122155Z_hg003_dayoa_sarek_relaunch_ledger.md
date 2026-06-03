# HG003 DayOA And Sarek Relaunch Ledger

Created: 2026-06-03T12:21:55Z

Objective: relaunch both HG003 5x benchmark arms on `dyec5128` after the DayOA `run:` plus `benchmark:` fix landed in DayOA `2.0.40`, and use the documented direct Nextflow path for `daylily-sarek`.

Cluster: `dyec5128`
Region/profile: `us-west-2` / `lsmc`
Executing entity: `ubuntu`

| ID | Step | Status | Evidence |
|---|---|---|---|
| G0-001 | Read current Sarek runbook and DYEC catalog. | SUCCESS | `docs/running_nextflow_pipes.md`; catalog row `daylily-sarek` default ref `0.7.379`; DayOA command `illumina_snv_alignstats` supports `--git-tag` override. |
| G0-002 | Confirm prior DayOA benchmark terminal state. | SUCCESS | Session `dyec5128_hg003_5x_ilmn_snv_20260603T110935Z` completed `2026-06-03T11:45:09Z`, `exit_code=1`, failure in `run:` + `benchmark:` path. |
| DYOA-001 | Launch new DayOA `2.0.40` HG003 5x arm. | RUNNING | Analysis `dyec5128_hg003_5x_ilmn_snv_dayoa2040_20260603T122856Z`; `dyec samples run` cloned DayOA tag `2.0.40` at commit `f9b3083a84c2ad15cd82b2a95838cb5a046ef1a1`. Initial launcher failed on stale headnode `daylily.sentieon_lic_path=/fsx/references/runtime_assets/cached_envs/x.lic`; headnode config was backed up to `/home/ubuntu/.config/daylily/daylily_cli_global.yaml.bak.20260603T123811Z` and corrected to existing `/fsx/references/runtime_assets/cached_envs/Life_Sciences_Manufacturing_Corporation_eval.lic`. Relaunched from prepared clone in tmux `dyec5128_hg003_5x_ilmn_snv_dayoa2040_20260603T122856Z_retry1` using `source dyoainit --skip-project-check`, `dy-a slurm hg38_broad`, then `dy-r produce_sent_align produce_dmd_dedup_cram produce_sentd_snv_vcf produce_snv_concordances produce_alignstats -p -k -j 20`. |
| SAREK-001 | Preflight/install pinned Sarek Nextflow runtime. | SUCCESS | Headnode `dyec5128` reachable as `ubuntu`; `/fsx` had 6.3T available; required HG003 FASTQs/truth/reference paths present. Created standard `/fsx/run_dir_mounts` and `/fsx/work/ubuntu` directories. Installed pinned Nextflow `24.10.5 build 5935` under `/fsx/resources/environments/nextflow/24.10.5` with Java 21 under `/fsx/resources/environments/nextflow/java-21`. |
| SAREK-002 | Clone/patch/launch `daylily-sarek` HG003 5x arm. | RUNNING | Analysis `dyec5128_hg003_5x_ilmn_sarek_20260603T123100Z`; `day-clone --repository daylily-sarek --destination ... --executing-entity ubuntu` cloned tag `0.7.379`, commit `d776c68b2d3b6ea6f3d5318777142e936e2c7d6b`. Wrote HG003 samplesheet with header `patient,sample,lane,fastq_1,fastq_2`. Applied documented run-local Sarek patches for `/fsx/references`, MUSE dbsnp channel names, and varlociraptor `def` removals. Reverted broken BWA/BWAMEM2 patch after Nextflow compile failure; unpatched modules now compile. Added run-local `DAYLILY_CONTAINER_CACHE` support and launched with per-analysis cache `/fsx/work/ubuntu/sarek/dyec5128_hg003_5x_ilmn_sarek_20260603T123100Z/container_cache` after shared cache lock permission failure. Active tmux: `sarek_dyec5128_hg003_5x_ilmn_sarek_20260603T123100Z`; Nextflow run name `mad_borg`. |
| MON-001 | Capture initial status for both arms. | SUCCESS | `2026-06-03T12:42:24Z`: DayOA tmux alive; jobs `59` and `60` submitted to `i192mem` in `CONFIGURING`. Sarek tmux alive; jobs `61`, `62`, and `63` submitted to `i128` in `CONFIGURING`. Existing unrelated job `58` remains running on `bcl2fq-i384-nvme-test`; no Slurm intervention performed. |
| MON-002 | Confirm both arms passed launch and first task execution. | SUCCESS | `2026-06-03T12:49:33Z`: DayOA benchmark Slurm job `59` (`sentieon_bwa_sort`) completed in `00:03:51` from workdir `/fsx/analysis_results/ubuntu/dyec5128_hg003_5x_ilmn_snv_dayoa2040_20260603T122856Z/daylily-omics-analysis`; DayOA tmux still alive and submitted downstream `doppelmark_dups` job `86` plus `no_dedup` job `87`. Slurm job `60` with the same name was confirmed unrelated, from `/fsx/analysis_results/dyec5128/ccv5128_20260603T122558Z_02_illumina_snv_alignstats/daylily-omics-analysis`. Sarek jobs `61` (`FASTP`), `62` (`CREATE_INTERVALS_BED`), and `63` (`TABIX_BGZIPTABIX_INTERVAL_COMBINED`) completed with exit code `0`; Sarek tmux still alive and downstream nf-core jobs were submitted/running (`FASTQC` job `90`, split/alignment-prep jobs `96`-`102`). |
| MON-003 | Attribute current downstream benchmark jobs. | SUCCESS | `2026-06-03T12:50:32Z`: DayOA benchmark job `86` (`doppelmark_dups`) completed in `00:01:54`; job `87` (`no_dedup`) remained `CONFIGURING`; jobs `103` (`alignstats`) and `104` (`sent_DNAscope`) were submitted from the DayOA benchmark workdir and remained `CONFIGURING`. Same-named jobs `88`/`89` were confirmed unrelated catalog-validation jobs from `/fsx/analysis_results/dyec5128/ccv5128_20260603T122558Z_02_illumina_snv_alignstats/daylily-omics-analysis`. |

## Active Handles

- DayOA analysis: `dyec5128_hg003_5x_ilmn_snv_dayoa2040_20260603T122856Z`
- DayOA retry tmux: `dyec5128_hg003_5x_ilmn_snv_dayoa2040_20260603T122856Z_retry1`
- DayOA retry log: `/home/ubuntu/daylily-runs/dyec5128_hg003_5x_ilmn_snv_dayoa2040_20260603T122856Z/manual_retry1.log`
- Sarek analysis: `dyec5128_hg003_5x_ilmn_sarek_20260603T123100Z`
- Sarek tmux: `sarek_dyec5128_hg003_5x_ilmn_sarek_20260603T123100Z`
- Sarek checkout: `/fsx/analysis_results/ubuntu/dyec5128_hg003_5x_ilmn_sarek_20260603T123100Z/sarek`
- Sarek work root: `/fsx/work/ubuntu/sarek/dyec5128_hg003_5x_ilmn_sarek_20260603T123100Z/work`
