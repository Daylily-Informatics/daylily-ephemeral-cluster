# DYEC Cost-Center Creation, Launch Propagation, and HIOMR2 Recovery Ledger

Date: 2026-07-26

## Control Ledger

Controlling plan: user request in this task to create the `bjuice` cost center, make `dyec create` provision a valid cost center when Slurm accounting is enabled, expose an explicit cost-center workflow-launch input, and rerun the blocked HG003 HIOMR2 workflow.

Ledger path: `docs/plans/20260726T095455Z_dyec_cost_center_create_and_launch_ledger.md`

### Gate 0 baseline

- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` at `jem-candidate-260725`; the DayOA-command pin work advanced the shared branch to `c65c9dca` / `14.0.14` during this task. The worktree has numerous pre-existing untracked ledgers, artifacts, recordings, and temporary directories; this work owns only this ledger and the source/tests subsequently named here.
- Source sweep: `rg -n -C 3 "budget_monitor_url|cost_center_monitor_url|_PostCreateInputs|_resolve_post_create_inputs|def workflow_launch|def build_parser|--project|cost-center|cost_center" daylily_ec config/day_cluster/sbatch tests`.
- Wrapper baseline: `config/day_cluster/sbatch` calls undefined `budget_monitor_url` and `cost_center_monitor_url` at its reporting lines. The deployed `preval-hiomr2` wrapper has the same defect.
- Create baseline: `daylily_ec/workflow/create_cluster.py` currently collects cluster/global budget inputs but does not collect, validate, or create a cost-center registry record.
- Launch baseline: `dyec workflow launch` accepts `--project` but not `--cost-center`; its headnode controller passes the project into `dyoainit`, which becomes Slurm `--comment` through DayOA's submit helper.
- Live baseline: `preval-hiomr2` is up in `us-west-2`; `bjuice` is absent from `dayec-cost-centers`; the prior HIOMR2 controller exited before the first Slurm job was accepted. Cluster AWS Budget is `$200`, usage `$0` at inspection.
- Approval record: the user first requested a `$500` increase, was shown the cluster `$200 -> $700` proposal, then directed “fix the budget and then please run the hiomr2 run... fix whatever is blocking this.” This is the second approval for the `$700` cluster and `bjuice` caps plus the supported wrapper refresh. No job, service, partition, or node intervention is authorized.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| CC-001 | DYEC create | Collect explicit cost-center name, monthly cap, and allowed submitters at the start of the budget/accounting inputs; validate and create the registry plus current usage record when Slurm accounting/enforcement is enabled. | SUCCESS | feature_implementation | Gate 2 | Codex | Commit `2cbeba28`; `daylily_ec/workflow/create_cluster.py`; `daylily_ec/aws/cost_centers.py`; focused suite `441 passed` |  | Creates a missing active cost center or rejects a non-matching existing record; no silent cap mutation. |
| CC-002 | DYEC workflow launch | Expose explicit `--cost-center`, validate it, preserve the value in the controller receipt, and export it as `DAY_PROJECT` before `dy-r` so Slurm submission uses the chosen cost center. | SUCCESS | feature_implementation | Gate 3 | Codex | Commit `2cbeba28`; `daylily_ec/cli.py`; `daylily_ec/repositories.py`; `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`; live receipt has `__DAYLILY_COST_CENTER__=bjuice` |  | `--project` remains the `dyoainit` input; the explicit cost center is applied only for job submission. |
| CC-003 | DYEC sbatch wrapper | Define the monitor URL helper functions used by the wrapper so budget/cost-center reporting does not fail before registry validation. | SUCCESS | feature_implementation | Gate 2 | Codex | Source/payload wrapper mirrors; `tests/test_sbatch_wrapper.py`; live DYEC log reports both monitor URLs and accepts `bjuice` before submitting job `1` | Missing helper definitions caused `budget_monitor_url: command not found`. | The user rejected direct wrapper manipulation. The direct installer was removed in commit `b54b4f84`; no further direct wrapper or Slurm-service action is permitted. |
| CC-004 | DYEC tests/docs | Add focused contract tests for create, launch propagation, and wrapper behavior; document the explicit no-default cost-center contract. | SUCCESS | contract_test | Gate 5 | Codex | README plus focused suite: `tests/test_workflow.py`, `test_sbatch_wrapper.py`, `test_cli_registry_v2.py`, `test_script_entrypoints.py`, `test_cost_centers.py`, and `test_repository_catalog.py`: `441 passed` |  | Published with the cost-center implementation. |
| CC-005 | Live `preval-hiomr2` | Create active `bjuice` registry and current-month usage entries using the approved cap and permitted submitters. | SUCCESS | config_or_startup_contract | Gate 2 | User + Codex | `aws budgets describe-budget` confirms `$700`; `dyec cost-centers show bjuice` confirms active `$700`, allowed user `ubuntu`, created `2026-07-26T10:15:38Z` |  | Registry and initial usage record were created. |
| CC-006 | Live `preval-hiomr2` | Do not make any further direct `/opt/slurm/bin/sbatch` changes; submit only through the DYEC workflow CLI. | SUCCESS | config_or_startup_contract | Gate 2 | User + Codex | User explicitly directed “you should not be hackinh sbatch”; cancellation was requested after the already-completed managed refresh. | The source-level direct-install attempt was removed immediately. | No further wrapper or Slurm-service action will be taken. |
| CC-007 | Live HIOMR2 workflow | Relaunch the existing five-shard HG003 HIOMR2 request through `dyec workflow launch --cost-center bjuice`; monitor only. | SUCCESS | active_product_contract | Gate 3 | User + Codex | Canonical fresh session `hiomr2_hg003_fivechrom_live7_20260726` completed with DYEC workflow `exit_code=0` at `2026-07-26T21:15:34Z`; it retained the six-manifest contract, `bjuice`, and DayOA commit `e2885d27` / tag `13.0.48`. | `live2` ended before submission; `live3` used invalid DNAscope `--gvcf`; `live5` had validator SIGPIPE; `live6` omitted concat provenance inputs. | All failed roots remain preserved. The generic DYEC canonical-artifact check is not satisfied for this scoped gVCF gate because it does not emit the standard MultiQC/evidence-manifest set; this caveat is recorded below. |

## Execution updates

- `live2` (`hiomr2_hg003_fivechrom_live2_20260726`) was terminal at `2026-07-26T10:34:27Z`, exit code `1`, before any Slurm submission. Its DYEC log reported the missing `daylily-omics-analysis` deploy-key reference.
- The missing repository reference was added through the supported `dyec headnode configure` interface using the separate DayOA deploy-key secret. No SSH, raw SSM, raw Snakemake, direct `sbatch`, Slurm service, partition, or node action was used.
- Before the successful retry, the DYEC CLI headnode/workflow/analysis/catalog contract was reviewed. Future headnode observation uses `dyec workflow status/logs`, `dyec analysis status`, and `dyec headnode jobs/dayoa-controllers`; arbitrary `dyec headnode run` is treated as mutating-capable and requires specific approval.
- `live3` cloned `codex/hiomr2-five-chrom-shards`, used the supplied six-manifest directory, and rendered a 10-job DAG: five chromosome-shard GVCFs plus preflight, SR/LR preparation, concatenation, and final target. The active controller and Slurm lifecycle remain under DayOA/DYEC; this task will not intervene in queue state.
- A task-scoped 20-minute heartbeat, `monitor-hg003-hiomr2-five-shard-workflow`, was created to monitor this exact session through terminal `rc=0`. It uses only DYEC status/log/controller/job commands; a nonzero terminal state triggers evidence collection and the user's approved, DYEC-only fix/relaunch workflow without direct Slurm or headnode manipulation.

## Recovery update — 2026-07-26T12:51Z

- `live3` became terminal at `2026-07-26T12:08:41Z` with exit code `1`. Its DYEC workflow log identified the source-backed failure precisely: `DNAscope: unrecognized option '--gvcf'`. The failed root is retained unchanged.
- DayOA commit `e4f8f642` replaces that unsupported raw-driver option with `--emit_mode gvcf`. The focused HIOMR2 core/runtime/Inflection tests passed (`23 passed`), and the clean, verified commit is published on `codex/hiomr2-five-chrom-shards` with annotated tag `13.0.43`.
- The fresh `live4` launch used a hash-validated snapshot of the exact six source manifests from `live3` rather than copying or replacing its analysis root. Its manifest payload used the configured DYEC S3 relay after the normal SSM document exceeded its 97 KiB limit; this is a supported `dyec workflow launch` transport path.
- At `2026-07-26T12:51Z`, `live4` was `RUNNING`: the DYEC controller was active, `sentdhiomr2_preflight` job `14` was `CONFIGURING`, zero failure markers were present, and the analysis filesystem reported 11.2 TiB free. The recurring monitor now follows `live4`, prints its exact state, and emits one two-sentence local `say` notification per cycle.

## Live7 terminal evidence — 2026-07-26T21:27Z

- `dyec --json workflow status` reports that
  `hiomr2_hg003_fivechrom_live7_20260726` completed at
  `2026-07-26T21:15:34Z` with `exit_code=0`. Its master log records all
  `10/10` steps complete, five successful shard gVCFs, successful concat, and
  no failure lines.
- `dyec analysis status full` reports controller inactive, no scoped Slurm
  jobs, no master-log failure markers, and all 17 parsed benchmark rows. It
  also correctly reports that `DAY_final_multiqc.html`,
  `dayoa_evidence_manifest.json`, and `multiqc_data.json` are absent. Those
  generic canonical artifacts are not produced by this scoped HIOMR2 gVCF
  first gate, so the analysis-status aggregate remains
  `INCOMPLETE_OR_UNKNOWN`; this is an explicit verification caveat, not an
  inferred success claim.
- The first gate used `--cost-center bjuice` throughout. No raw headnode,
  Slurm, or analysis-root action was taken. The later combined kitchen-sink /
  Inflection continuation is blocked until the owner supplies a persisted
  `seqone_delivery_batch_id`; no identifier was invented.

## Literal kitchen-sink and analytical package terminal evidence — 2026-07-27T02:10Z

- The owner supplied `seqone_delivery_batch_id=20260726-hiomr2-ks-ip`; DYEC
  then completed the literal kitchen-sink plus analytical-only Inflection
  continuation with `rc=0` under `bjuice`.
- The produced package manifest declares eleven materialized products,
  including both the scoped concat gVCF/TBI and a distinct hard-call VCF/TBI.
  It is analytical-only (`customer_release_eligible: false`); no customer
  identity was inferred or fabricated.
