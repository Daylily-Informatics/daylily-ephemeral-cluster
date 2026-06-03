# BCL L003 8-Tile O_DIRECT Staging Comparison Ledger

Created: `2026-06-03T08:09:31Z`

## Objective

Repeat the successful L003 8-tile `tile_smoke` BCL Convert experiment with `shared_thread_odirect_output: true`, first staging output under compute-node `/dev/shm`, then staging output under compute-node `/scratch` if `/scratch` exists and has enough free space for this 8-tile payload. Both runs use DayOA through `dy-r` only, fresh worksets, `-T 0`, and distinct DRA-backed output directories.

## Commit/Code State

| Repo | State |
|---|---|
| DayOA | No new code edits required for this phase. Required tile-smoke support is already in pushed commit `a0c3a81`; current source branch also contains later unrelated commit `16a93d9`. |
| DYEC | New ledger/config docs only; no runtime code edits required for this phase. |

## Gate 0 Inventory

| Item | Value |
|---|---|
| Cluster | `dyec0602bcl` |
| Region/profile | `us-west-2` / `lsmc` |
| Headnode | `i-0c36c39770c533c8e` |
| Source run dir | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4` |
| Source S3 | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0009_B23TVLGLT4/` |
| Flowcell/run class | `25B`; `RunParameters.xml` has `FlowCell Name=25B`, `RecipeName=25B Sequencing` |
| Lane/tiles | `L003`, first 8 lane-3 tiles: `s_3_1101` through `s_3_1108` |
| Baseline off-ODIRECT output | `fasts_from_bclconvert_l003_8tile_tilesmoke_i192bigmem_devshm_20260603T0740Z` |
| Baseline off-ODIRECT S3 state | `161` objects, `84` `.fastq.gz`, `6102998592` bytes, done/report markers present |
| Current Slurm state before this phase | no `ubuntu` jobs in `squeue` |
| `/dev/shm` config | `scratch_output_root: /dev/shm/dayoa_bclconvert`, `scratch_available_bytes_min: 650000000000` |
| `/scratch` config | `scratch_output_root: /scratch/dayoa_bclconvert`, `scratch_available_bytes_min: 20000000000`; this is an 8-tile existence/sufficiency probe, not a full-lane capacity gate |

## Planned Configs

| Staging root | Config |
|---|---|
| `/dev/shm` | `docs/plans/20260603T080931Z_bcl_l003_8tile_odirect_devshm_scratch_configs/bclconvert_l003_8tile_tilesmoke_odirect_on_devshm_20260603T080931Z.yaml` |
| `/scratch` | `docs/plans/20260603T080931Z_bcl_l003_8tile_odirect_devshm_scratch_configs/bclconvert_l003_8tile_tilesmoke_odirect_on_scratch_20260603T080931Z.yaml` |
| `/fsx/scratch/tmp` | `docs/plans/20260603T080931Z_bcl_l003_8tile_odirect_devshm_scratch_configs/bclconvert_l003_8tile_tilesmoke_odirect_on_fsx_scratch_tmp_20260603T082415Z.yaml` |
| `bcl2fq` `/scratch` | `docs/plans/20260603T080931Z_bcl_l003_8tile_odirect_devshm_scratch_configs/bclconvert_l003_8tile_tilesmoke_bcl2fq_scratch_20260603T083401Z.yaml` |

## Planned Output Directories

| Staging root | Run ID / DRA directory name |
|---|---|
| `/dev/shm` | `fasts_from_bclconvert_l003_8tile_tilesmoke_odirect_on_devshm_20260603T080931Z` |
| `/scratch` | `fasts_from_bclconvert_l003_8tile_tilesmoke_odirect_on_scratch_20260603T080931Z` |
| `/fsx/scratch/tmp` | `fasts_from_bclconvert_l003_8tile_tilesmoke_odirect_on_fsx_scratch_tmp_20260603T082415Z` |
| `bcl2fq` `/scratch` | `fasts_from_bclconvert_l003_8tile_tilesmoke_bcl2fq_scratch_20260603T083401Z` |

## Execution Contract

Use DayOA only from initialized persistent `ubuntu` tmux sessions:

```bash
cd /fsx/analysis_results/dyec0602bcl/<workset>/daylily-omics-analysis
source dyoainit
dy-a slurm hg38
dy-r produce_bclconvert_fastqs -p -k -j 10 -T 0 --rerun-triggers mtime --configfile config/<config>.yaml -n
dy-r produce_bclconvert_fastqs -p -k -j 10 -T 0 --rerun-triggers mtime --configfile config/<config>.yaml
```

Do not invoke `snakemake` directly. Do not merge tile FASTQs or lane FASTQs. Do not touch unrelated jobs/controllers.

## Tracking Rows

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| BASE-001 | Baseline | Confirm previous 8-tile output is visible in S3 before reruns. | SUCCESS | monitoring | Gate 0 | Monitor | S3 prefix has `161` objects, `84` `.fastq.gz`, `6102998592` bytes, marker/report objects present. |  | Baseline export complete. |
| CFG-001 | Config | Save O_DIRECT-on `/dev/shm` and `/scratch` configs. | SUCCESS | feature_implementation | Gate 1 | Orchestrator | Config files saved under `docs/plans/20260603T080931Z_bcl_l003_8tile_odirect_devshm_scratch_configs/`. |  | Configs differ from baseline only by run id, O_DIRECT toggle, staging root, and `/scratch` free-space threshold. |
| PREP-001 | Workset | Prepare fresh DayOA workset and DRA dir for O_DIRECT-on `/dev/shm`. | SUCCESS | feature_implementation | Gate 1 | Headnode Agent | Workset `/fsx/analysis_results/dyec0602bcl/bcl_l003_8tile_tilesmoke_odirect_on_devshm_20260603T080931Z/daylily-omics-analysis`, commit `a0c3a81`, tmux `dayoa_bcl_l003_8tile_odirect_devshm_20260603`. |  | Fresh workset and output dir prepared. |
| DRY-001 | Dry-run | Run O_DIRECT-on `/dev/shm` dry-run through `dy-r`. | SUCCESS | feature_implementation | Gate 2 | Runner | `dry_devshm_20260603T0811Z.stdout.txt`: one `run_bclconvert_tile_shard`, `L003/0001_tiles0001-0008`, `threads=192`, `partition=i192bigmem`, `--shared-thread-odirect-output true`, `/dev/shm/dayoa_bclconvert`. |  | Dry-run accepted. |
| LIVE-001 | Live run | Run O_DIRECT-on `/dev/shm` live job through `dy-r`. | SUCCESS | feature_implementation | Gate 3 | Runner | Job `57`, tmux marker `__LIVE_DEVSHM_ODIRECT_RC__0`, 84 FASTQs and 3 done markers in DRA. |  | Live run completed successfully. |
| ACC-001 | Acceptance | Confirm O_DIRECT-on `/dev/shm` output, benchmark, logs, S3 visibility. | SUCCESS | monitoring | Gate 4 | Acceptance | `success_devshm_harvest_20260603T0824Z.stdout.txt`: tile benchmark `45.6894s`; S3 prefix has `161` objects, `84` FASTQs, `6102999247` bytes and marker/report objects. |  | O_DIRECT-on tmpfs run succeeded and exported to S3. |
| PREP-002 | Workset | Prepare fresh DayOA workset and DRA dir for O_DIRECT-on `/scratch`. | SUCCESS | feature_implementation | Gate 1 | Headnode Agent | Workset `/fsx/analysis_results/dyec0602bcl/bcl_l003_8tile_tilesmoke_odirect_on_scratch_20260603T080931Z/daylily-omics-analysis`, commit `a0c3a81`, tmux `dayoa_bcl_l003_8tile_odirect_scratch_20260603`. |  | Fresh workset and output dir prepared. |
| DRY-002 | Dry-run | Run O_DIRECT-on `/scratch` dry-run through `dy-r`. | SUCCESS | feature_implementation | Gate 2 | Runner | `dry_scratch_20260603T0821Z.stdout.txt`: one `run_bclconvert_tile_shard`, `L003/0001_tiles0001-0008`, `scratch_output_root=/scratch/dayoa_bclconvert`, O_DIRECT true. |  | Dry-run accepted; compute-node existence check is live-only. |
| LIVE-002 | Live run | Run O_DIRECT-on `/scratch` live job through `dy-r`; allow compute-node scratch preflight to fail hard if `/scratch` is absent/too small. | BLOCKED | feature_implementation | Gate 3 | Runner | Job `59`, tmux marker `__LIVE_SCRATCH_ODIRECT_RC__1`; Slurm stderr shows `PermissionError: [Errno 13] Permission denied: '/scratch'`; SSH probe shows `/scratch` absent on `i192bigmem-dy-all-1`. | `/scratch` does not exist on the compute node, so Snakemake cannot create `/scratch/dayoa_bclconvert_tmp`. | No BCL conversion started; BCL log is 0 bytes. |
| ACC-002 | Acceptance | Confirm O_DIRECT-on `/scratch` output/benchmark/S3, or record `/scratch` blocker. | BLOCKED | monitoring | Gate 4 | Acceptance | `failure_scratch_slurm_20260603T0823Z.stdout.txt`: `/scratch` absent, no FASTQs, no benchmark. | Compute-node local `/scratch` path is unavailable. | Acceptance is blocked by missing path, not by BCL Convert output failure. |
| PREP-003 | Workset | Prepare fresh DayOA workset and DRA dir for O_DIRECT-on `/fsx/scratch/tmp`. | SUCCESS | feature_implementation | Gate 1 | Headnode Agent | Workset `/fsx/analysis_results/dyec0602bcl/bcl_l003_8tile_tilesmoke_odirect_on_fsx_scratch_tmp_20260603T082415Z/daylily-omics-analysis`, tmux `dayoa_bcl_l003_8tile_odirect_fsxscratch_20260603`; `/fsx/scratch/tmp` created with `ubuntu` ownership. |  | Fresh workset, config, and output dir prepared. |
| DRY-003 | Dry-run | Run O_DIRECT-on `/fsx/scratch/tmp` dry-run through `dy-r`. | SUCCESS | feature_implementation | Gate 2 | Runner | Dry-run planned one `run_bclconvert_tile_shard`, `L003/0001_tiles0001-0008`, `partition=i192bigmem`, `threads=192`, `TMPDIR=/fsx/scratch/tmp/dayoa_bclconvert_tmp`, `scratch_output_root=/fsx/scratch/tmp`. |  | Dry-run accepted. |
| LIVE-003 | Live run | Run O_DIRECT-on `/fsx/scratch/tmp` live job through `dy-r`. | SUCCESS | feature_implementation | Gate 3 | Runner | Job `60`, tmux marker `__LIVE_FSXSCRATCH_ODIRECT_RC__0`; log shows `run_output_dir: /fsx/scratch/tmp/dayoa_bclconvert_60/...`, BCL Convert completed, and rsync moved `6.10G` at `452.14M bytes/sec`. |  | Live run completed successfully. |
| ACC-003 | Acceptance | Confirm O_DIRECT-on `/fsx/scratch/tmp` output, benchmark, logs, S3 visibility, or record blocker. | SUCCESS | monitoring | Gate 4 | Acceptance | DRA output has `84` FASTQs and `3` done markers; BCL log records `scratch_available_bytes: 6737338433536`, O_DIRECT warning for distributed filesystem, conversion start and completion. |  | Local `/fsx/scratch/tmp` staging works, but BCL Convert warns that O_DIRECT/ASIO can perform poorly or hang on a distributed filesystem. |
| PREP-004 | Workset | Prepare fresh DayOA workset and DRA dir for 8-tile `bcl2fq` `/scratch` run. | SUCCESS | feature_implementation | Gate 1 | Headnode Agent | Workset `/fsx/analysis_results/dyec0602bcl/bcl_l003_8tile_tilesmoke_bcl2fq_scratch_20260603T083401Z/daylily-omics-analysis`, commit `a0c3a81`, tmux `dayoa_bcl_l003_8tile_bcl2fq_scratch_20260603`, config `bclconvert_l003_8tile_tilesmoke_bcl2fq_scratch_20260603T083401Z.yaml`. |  | Fresh workset, config, and output dir prepared. |
| DRY-004 | Dry-run | Run 8-tile `bcl2fq` `/scratch` dry-run through `dy-r`. | SUCCESS | feature_implementation | Gate 2 | Runner | Dry-run marker `__DRY_BCL2FQ_SCRATCH_RC__0`; planned one `run_bclconvert_tile_shard` for `L003/0001_tiles0001-0008`, `threads=48`, `partition=bcl2fq`, `exclusive=--exclusive`, `TMPDIR=/scratch/dayoa_bclconvert_tmp`, `scratch_output_root=/scratch/dayoa_bclconvert`. |  | Dry-run accepted; compute-node `/scratch` existence is live-only. |
| LIVE-004 | Live run | Launch 8-tile `bcl2fq` `/scratch` live job through `dy-r`. | RUNNING | feature_implementation | Gate 3 | Runner | Live command launched in tmux with `-j 10 -T 0`; Slurm job `63` submitted. Latest snapshot `2026-06-03T08:47:17Z`: `PD (BeginTime)`, `Restarts=5`, requested `48` CPUs and `300000M`, no BCL log yet. | `bcl2fq` node allocation is cycling through `CF` and `PD (BeginTime)` before compute shell execution. | Controller remains active; no scheduler intervention performed. |
| ACC-004 | Acceptance | Confirm 8-tile `bcl2fq` `/scratch` output, benchmark, logs, and S3 visibility, or record blocker. | OPEN | monitoring | Gate 4 | Acceptance |  |  |  |
