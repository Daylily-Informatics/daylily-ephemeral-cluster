# ifx-reworkB Hybrid ILMN+ONT No-DRA Launch Ledger

Date: 2026-07-08

## Objective

Begin the `hybrid_ilmn_ont_snv` command-catalog run on `ifx-reworkB` without creating a new DRA mount. Use the default-mounted `/fsx/data` slim reads and a two-row pass-through manifest, excluding the unavailable 7x control-data ONT row.

## Gate 0: Inventory Freeze

| Item | Evidence |
|---|---|
| Repo | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` |
| Cluster | `ifx-reworkB`, `us-west-2`, profile `lsmc` |
| Runtime | `dyec --json info` reported DYEC `10.0.123.dev0+g80cd9b080.d20260708` from this checkout |
| Cluster state | `dyec headnode info --profile lsmc --region us-west-2 --cluster ifx-reworkB` reported cluster `CREATE_COMPLETE`, stack `CREATE_COMPLETE`, compute fleet `RUNNING`, headnode `i-059642d9ee4d5c9ea` |
| Queue baseline | `dyec headnode jobs --profile lsmc --region us-west-2 --cluster ifx-reworkB` showed only the Slurm header, no queued/running jobs |
| Catalog command | `hybrid_ilmn_ont_snv`, DayOA `10.0.72`, `sample_manifest`, `requires_staging=true`, `requires_run_mount=false`, genome `hg38_broad` |
| No-DRA launch shape | Use `STAGE_DIRECTIVE=pass_through` and local `--config-only` manifest generation, then launch with explicit `--samples-file` and `--units-file`; do not pass `--cluster` to `dyec samples stage` and do not create staged-prefix or run-directory DRAs |
| Input manifest | `docs/plans/20260708T214413Z_ifx_reworkB_hybrid_ilmn_ont_snv_no_dra/ifx_reworkB_hybrid_ilmn_ont_snv_nodra_pass_through_manifest.tsv` |
| Dirty worktree at start | Pre-existing modified DYEC spot-pricing files and untracked `20260708T212328Z_ifx_reworkB_spot_price_update*` artifacts were present before this run |

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| HNO-001 | Catalog selection | Use a hybrid ILMN+ONT command that does not require a run-directory DRA. | SUCCESS | feature_implementation | Gate 0 | Codex | `config/daylily_pipeline_command_catalog.yaml` lines for `hybrid_ilmn_ont_snv`: `requires_run_mount: false`; `dyec` catalog load resolved DayOA `10.0.72` and `hg38_broad`. |  | Selected `hybrid_ilmn_ont_snv`, the smallest prod hybrid ILMN+ONT row. |
| HNO-002 | Inputs | Restrict inputs to already default-mounted `/fsx/data` rows. | SUCCESS | feature_implementation | Gate 0 | Codex | Generated two-row pass-through manifest from `examples/staging/hybrid_ilmn_ont/analysis_samples_manifest.tsv`, retaining `SR1x-ONT1x` and `SR1x-ONT3x`; headnode preflight confirmed required `/fsx/data` annotation, ILMN FASTQ, ONT CRAM, and CRAI paths exist. |  | The unavailable 7x control-data row was excluded. |
| HNO-003 | Config generation | Generate DayOA `samples.tsv` and `units.tsv` without creating a staged-prefix DRA. | SUCCESS | feature_implementation | Gate 1 | Codex | `dyec samples stage ... --config-only` completed: rows checked=2, samples checked=1, source objects checked=44, concordance directories checked=2; generated `generated_config/20260708T214802Z_06a67ffd_samples.tsv` and `generated_config/20260708T214802Z_06a67ffd_units.tsv`. |  | No `--cluster` argument was passed to stage generation, so no staged-prefix DRA was requested. |
| HNO-004 | Launch | Start the workflow in a supported persistent headnode tmux session on `ifx-reworkB`. | SUCCESS | feature_implementation | Gate 1 | Codex | `dyec workflow launch ... --git-tag 10.0.72 --samples-file ... --units-file ... --dy-command "dy-r produce_snv_concordances produce_sentdhiomr_sv produce_sentdhiomr_snv_vcf --config 'dedupers=[\"na\"]' -p -j 100 -k"` created tmux session `ifx_reworkb_hybrid_ilmn_ont_snv_nodra_20260708t214413z`; status started at `2026-07-08T21:49:28Z`. |  | Workflow controller is running; workflow completion is out of scope for the "begin" request. |
| HNO-005 | Post-launch evidence | Record run id/session/status and confirm no run-directory DRA was created by this launch path. | SUCCESS | contract_test | Gate 5 | Codex | `dyec workflow status` reports `exit_code=null`; `dyec --json mounts list --cluster ifx-reworkB` reports `{"mounts":[]}`; `dyec headnode jobs` still shows no Slurm jobs while Snakemake creates conda environments; lock acquired by `codex-ifx-reworkb-hybrid-nodra-20260708t214413z`. |  | No DRA mounts are present; the workflow is currently inside Snakemake DAG/env setup before Slurm submission. |

## Terminal Report

The requested no-DRA hybrid command-catalog run has been started on `ifx-reworkB`.

- Analysis id/session: `ifx_reworkb_hybrid_ilmn_ont_snv_nodra_20260708t214413z`
- Analysis root: `/fsx/analysis_results/ubuntu/ifx_reworkb_hybrid_ilmn_ont_snv_nodra_20260708t214413z`
- Run dir: `/home/ubuntu/daylily-runs/ifx_reworkb_hybrid_ilmn_ont_snv_nodra_20260708t214413z`
- DayOA ref: `10.0.72`
- Command: `dy-r produce_snv_concordances produce_sentdhiomr_sv produce_sentdhiomr_snv_vcf --config 'dedupers=["na"]' -p -j 100 -k`
- Current state: tmux/controller alive, `exit_code=null`, Snakemake has built the DAG and is creating conda environments; no Slurm jobs yet at the last queue poll.
- DRA state: `dyec --json mounts list --cluster ifx-reworkB` returned an empty mounts list.
- Lock state: write lock owned by `codex-ifx-reworkb-hybrid-nodra-20260708t214413z` with heartbeat recorded.
