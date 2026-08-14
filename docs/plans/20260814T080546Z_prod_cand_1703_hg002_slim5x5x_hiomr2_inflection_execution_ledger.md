# prod-cand-1703 HG002 slim 5x+5x HIOMR2 mega + Inflection execution ledger

Created: `2026-08-14T08:05:46Z`

## Objective

Run the current production DYEC command-catalog entry
`inflection-bjuice-product-v0.2` on `prod-cand-1703` for the verified HG002
slim-data 5x Illumina plus 5x ONT fixture. Monitor through controller terminal
state, notify Mike K and John M after the first Slurm jobs are observed and at
controller `rc=0`, then export the completed analysis root through DYEC's DRA
path. FSx deletion is intentionally outside the currently authorized execution
boundary until a second explicit approval names the exact root and S3 prefix.

## Fixed execution contract

- Local DYEC: `17.0.14`, activated with `source ./activate`.
- Profile / region / cluster: `lsmc` / `us-west-2` / `prod-cand-1703`.
- Catalog command: `inflection-bjuice-product-v0.2`, catalog version `6`,
  type `prod`, DayOA tag `14.0.14`, genome `hg38`, `-j 333`.
- Catalog targets: `produce_sentdhiomr2_slim_kitchensink_mega` and
  `produce_sentdhiomr2_inflection_analytical_package`.
- Default catalog scope: chr19-20. It is retained because no full 1-25 scope
  override was requested.
- Fixture: `/Users/jmajor/.config/daylily/resources/17.0.14/examples/staging/hg002_bjuice_verified_5x5x_fastq`.
  The declared exact inputs are 5.862704556x Illumina and 4.794169766x ONT;
  full-coverage input substitution is prohibited by the catalog receipt.
- Dry analysis ID: `prod-cand-1703-hg002-slim5x5x-hiomr2-ifx-bjuice-v02-dry-20260814T080546Z`.
- Live analysis ID: `prod-cand-1703-hg002-slim5x5x-hiomr2-ifx-bjuice-v02-20260814T080546Z`.
- Executing entity: `prod-cand-1703`; live root will be
  `/fsx/analysis_results/prod-cand-1703/prod-cand-1703-hg002-slim5x5x-hiomr2-ifx-bjuice-v02-20260814T080546Z`.
- Monitor cadence: every 10 minutes; stop at terminal controller state. Escalate
  to the user at six hours if still non-terminal.
- Export boundary: record `dyec analysis visit --mode export`, use a fresh
  explicit non-overlapping S3 prefix and `dyec export --wait`; do not pass
  `--delete-data-in-file-system` without the required second approval.

## Gate 0 inventory freeze

- Repo baseline: detached `HEAD` at `96cec5a45993e706e8e075853ac0f5fe27b812ac`
  with extensive pre-existing untracked user files. They are not owned by this
  run and will not be changed, staged, or removed.
- Cluster status: `UPDATE_COMPLETE`; headnode instance
  `i-0a19cb6b471874d56` as `ubuntu`.
- Controller baseline at `2026-08-14T08:06:01Z`: 0 controllers and 0 Slurm
  jobs. Existing tmux panes and stale receipts belong to prior analyses and are
  out of scope.
- Current managed run mounts are `AVAILABLE`, but this catalog entry explicitly
  uses the receipt-bound FSx reference slim-data fixture and does not require a
  run mount.
- No new analysis root with either planned identifier was present in the bounded
  headnode inventory.
- The fresh dry catalog render completed at `2026-08-14T08:10Z`; its exact
  wrapper carries the fixed tag, explicit local six-manifest directory, Ubuntu
  remote user, `hg38`, chr19-20 scope, `-j 333`, and no export trigger.
- The fresh dry catalog launch was accepted at `2026-08-14T08:13Z`. Attributed
  workflow status reported live controller PID `1380969`, session
  `pc1703-hg002-slim5x5x-ifx-bjuice-v02-dry-20260814t080546z`, expected fresh
  root, zero Slurm submissions, and no terminal exit code yet.
- Bounded heartbeat automation:
  `monitor-prod-cand-1703-hg002-slim-5x5x-hiomr2-inflection`; active every 10
  minutes, stops at terminal workflow state or after reporting a terminal
  failure, and asks for direction at six hours.
- A headnode `dyec analysis visit --mode monitor` was recorded for the dry
  root before status/monitoring access. Slack recipients resolved live as JEM
  (`U08TN63K73M`) and Michael Kennemer (`U0AQXA08V6Z`); no exact two-recipient
  existing group DM was found, so a fresh group DM will be created only if the
  first-live-job notification milestone is reached.
- The fresh dry controller reached attributable `rc=0` at `2026-08-14T08:14Z`
  with zero Slurm submissions and no failure markers. Its log recorded only the
  expected configuration overlays and working-directory unlock.
- The fresh live render at `2026-08-14T08:15Z` exactly preserved the catalog
  target/configuration shape and differs from dry only by removal of `-n` /
  `--dry-run` and the fresh live analysis/session identifiers. The live catalog
  launch was accepted at `2026-08-14T08:17Z`; immediate status receipt absence
  occurred during controller bootstrap and is not classified as a workflow
  failure.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Inventory | Freeze catalog, cluster, fixture, mount, controller, and repository baseline | SUCCESS | legitimate_safety_handling | Gate 0 | Codex | Fixed contract and Gate 0 above |  | Exact production catalog and fresh roots selected without substitution. |
| RUN-001 | Render | Render exact fresh dry catalog argv with explicit tag, fixture, cluster, profile, region, and Ubuntu user | SUCCESS | contract_test | Gate 1 | Codex | Render JSON at `2026-08-14T08:10Z` |  | Exact catalog shape is frozen; no export destination or delete flag was rendered. |
| RUN-002 | Dry run | Launch the distinct dry controller and require `rc=0` with no Slurm submission | SUCCESS | contract_test | Gate 1 | Codex | Attributable `rc=0`, zero submitted jobs, zero failure markers |  | Distinct dry root retained. |
| RUN-003 | Live run | Render then launch the byte-equivalent fresh live catalog analysis after dry success | FAILED | feature_implementation | Gate 1 | Codex | Attributable terminal receipt at `2026-08-14T08:24Z`: `status.json#exit_code=1`; controller log at `08:23:18Z` | DYEC `sbatch` enforcement reported `cost-center registry lookup returned empty JSON`, then `sbatch failed with rc=1` / `Error submitting jobscript (exit code 2)`. | No controller retry or Slurm intervention was performed. |
| REC-001 | Recovery diagnosis | Identify the terminal submission blocker and verify a supported non-destructive recovery input | SUCCESS | legitimate_safety_handling | User authorized recovery | Codex | `prod-cand-1703` is absent from `dayec-cost-centers`; active `prod-cand-1703-ccenter` has cap `999` and allows `ubuntu`; original controller had `COST_CENTER_VALUE=`. | The former launch allowed DayOA's cluster-name fallback rather than passing the provisioned submit cost center. | No registry mutation, headnode configuration, Slurm intervention, or source-code change is required. |
| REC-002 | Recovery dry plan | Relaunch the existing exact root through DYEC with the active explicit cost center and `--rerun-triggers mtime -n` | SUCCESS | contract_test | User authorized recovery | Codex | Attributable session `pc1703-hg002-slim5x5x-ifx-bjuice-v02-recovery-dry-20260814t083652z` reached `rc=0`, zero Slurm submissions, and reported `269` planned jobs. | Only `missing output files` and `input files updated by another job` were reported; there is no code-change or mtime-triggered completed-rule rerun reason. | The retained root was not replaced; the DYEC lock was released. |
| REC-003 | Recovery live continuation | Remove only `-n` and continue the same root if REC-002 is clean | SUCCESS | feature_implementation | User authorized recovery | Codex | At `2026-08-14T09:52Z`, attributable DYEC status is `SUCCEEDED`, `exit_code=0`, source `/home/ubuntu/daylily-runs/pc1703-hg002-slim5x5x-ifx-bjuice-v02-recovery-live-20260814t084403z/status.json#exit_code`; controller PID `1461915` is no longer live. | Attributable Slurm state is empty and all 269 steps completed. | The live command differed from REC-002 only by removal of `-n`; `git diff` and `git diff --cached` are empty at `8bbf0fe0b45918a65cb2c884c5b435bab0582cb1`, so no release was made. |
| MON-001 | Monitoring | Monitor controller and Slurm state every 10 minutes until terminal | SUCCESS | legitimate_safety_handling | Gate 5 | Codex | Monitor visit recorded; terminal `dyec workflow status`; `dyec workflow logs --stream controller`; controller inventory and jobs checked at `2026-08-14T08:24Z` |  | The terminal state is attributable `FAILED`, `rc=1`; no active attributed jobs. |
| MON-002 | Recovery monitoring | Monitor the authorized recovery controller and queue until terminal | SUCCESS | legitimate_safety_handling | User authorized recovery | Codex | A monitor visit preceded the terminal status/log/controller/jobs check at `2026-08-14T09:52Z`; DYEC reported `SUCCEEDED` / attributable `rc=0`, no controller process, zero active attributed jobs, and no failure markers. | `dyec headnode jobs` was empty and controller inventory reported `slurm_job_count=0`. | No Slurm intervention occurred. |
| SLK-001 | Slack | Send first-job and controller-rc0 notifications in one Mike K / John M analysis thread | SKIPPED | feature_implementation | Gate 5 | Codex | Status receipt shows zero submitted attributable job IDs; global job `657` is unrelated `ultima_run_qc_collect_json_metrics-604834-20260717_2309`. | First-live-job and `rc=0` milestones never occurred. | No Slack thread or message was sent. |
| SLK-002 | Slack | Send recovery first-job and controller-rc0 notifications in one Mike K / John M analysis thread | SUCCESS | feature_implementation | User authorized recovery | Codex | Exact recipient DM `D0AQK8RB3D5`; parent `1786697331.111039`; terminal reply `1786701274.238129`; https://lsmchq.slack.com/archives/D0AQK8RB3D5/p1786701274238129?thread_ts=1786697331.111039&cid=D0AQK8RB3D5 | One parent and one terminal reply were sent in the same analysis thread. | No duplicate parent was sent. |
| EXP-001 | Export | Resolve fresh exact S3 destination, record export visit, and run no-delete DRA export after rc0 | SUCCESS | feature_implementation | User authorized standard derived prefix | Codex | Receipt `docs/plans/20260814T080546Z_prod_cand_1703_hg002_slim5x5x_hiomr2_inflection_export/fsx_export.yaml`: `status=success`, `phase=complete`, task `task-0ed9c6b1e8492244a=SUCCEEDED`, DRA `dra-0031790513f4fa0ec` detached `DELETED`, `delete_data_in_file_system=false`. |  | The package manifest and Inflection MultiQC HTML were verified at the exact S3 prefix. |
| EXP-002 | Cleanup | Enable FSx source deletion only after second explicit approval and successful export evidence | SUCCESS | feature_implementation | Gate 5 | Codex | User's exact second approval named `/fsx/analysis_results/prod-cand-1703/prod-cand-1703-hg002-slim5x5x-hiomr2-ifx-bjuice-v02-20260814T080546Z` and `s3://lsmc-ssf-sequencing-data/derived/prod-cand-1703/prod-cand-1703-hg002-slim5x5x-hiomr2-ifx-bjuice-v02-20260814T080546Z/`; guarded DYEC cleanup association `dra-039abdb74c3b10a25` completed. | Post-cleanup DYEC headnode proof returned `deleted`; `head-object` still verifies the retained S3 package manifest (174,220 bytes). | No unrelated FSx root, DRA, or Slurm job was altered. |
| CAT-001 | Catalog evidence | Record this successful catalog execution with its verified S3 evidence | SUCCESS | feature_implementation | User requested completion evidence | Codex | Current `inflection-bjuice-product-v0.2` alias now has a validated `validation_runs` record with its exact S3 prefix in `stage_or_context` and exported `package_manifest.json` in `report_path`. `dyec catalog show` parsed and returned the record. |  | The separate `validation_evidence_s3_uri_prefix` field remains unset because it requires command-catalog-test `command_registry.json` and `summary.json` receipts, which this completed analysis export does not claim to be. |

## Current status

All rows terminal: `yes`

Objective complete: `yes` — analysis, DRA export, catalog evidence, and the separately approved FSx cleanup are complete.

Current counts: `SUCCESS=12`, `FAILED=1`, `IN_PROGRESS=0`, `OPEN=0`, `SKIPPED=1`, `BLOCKED=0`.

## Authorized recovery diagnosis — 2026-08-14T08:36Z

- The user authorized a headnode recovery sequence: diagnose the `rc=1`, first
  run the exact continuation with `--rerun-triggers mtime -n`, and remove only
  `-n` if that plan preserves completed work. They also authorized commit/push/
  a new tag only if source code must change and the recovered controller reaches
  `rc=0`.
- The launch-specific root cause is established without modifying AWS state:
  the failed controller had `COST_CENTER_VALUE=` and its DayOA submission used
  the cluster-name fallback `prod-cand-1703`. Read-only DYEC lookup proves that
  name does not exist in the registry. The provisioned active record
  `prod-cand-1703-ccenter` is explicitly for this cluster, has the matching
  `$999` cap, and permits `ubuntu`; a headnode DynamoDB read confirms that exact
  active record.
- The retained DayOA checkout is exactly tag `14.0.14` at commit
  `8bbf0fe0b45918a65cb2c884c5b435bab0582cb1`. It has generated/untracked
  workflow artifacts but no tracked source change to commit. The recovery will
  reuse the exact root through `dyec workflow launch` with
  `--reuse-existing-analysis-dir --input-contract none --no-input-staging`,
  `--reuse-local-git-ref`, and the immutable local commit; it will not replace
  the analysis root or rewrite its manifest inputs.
- The recovery dry controller was launched at `2026-08-14T08:40Z` with the
  explicit active cost center and the precise requested mtime dry command. It
  reached attributable `rc=0` at `2026-08-14T08:42Z`, submitted no Slurm jobs,
  and planned `269` jobs. Its reason summary contains only missing outputs and
  inputs updated by planned downstream work, so it does not ask to rerun prior
  completed rules for mtime or code-change reasons. The user-directed live
  continuation is therefore authorized to remove only `-n`.
- The live recovery controller was accepted at `2026-08-14T08:45Z` and first
  submitted attributable jobs at `2026-08-14T08:47Z`: Slurm `668` through `672`
  (all `CONFIGURING` at observation). The wrapper reports active cost-center
  admission for `prod-cand-1703-ccenter`. A fresh exact Mike K/John M DM was
  created as `D0AQK8RB3D5`, and its single parent message timestamp is
  `1786697331.111039`; all terminal communication must reply to that thread.

## Terminal evidence

- At the `2026-08-14T08:21Z` scheduled check, an analysis-root monitor visit was
  recorded before root access. `dyec workflow status` initially still showed the
  attributed live controller PID `1398643` and zero submitted jobs; the sole
  visible cluster job was unrelated to this analysis.
- The catalog-owned controller log then recorded failed `sbatch` attempts because
  DYEC cost-center registry lookup returned empty JSON. It exited at
  `2026-08-14T08:23:18Z` with `RETURN CODE: 1`, released the catalog-owned lock,
  and reported `Workflow exited with status 1`.
- Follow-up attributed `dyec workflow status` reported `state=FAILED`, terminal
  `exit_code=1`, with source
  `/home/ubuntu/daylily-runs/pc1703-hg002-slim5x5x-ifx-bjuice-v02-20260814t080546z/status.json#exit_code`,
  zero submitted/finished attributable job IDs, and zero active attributed Slurm
  states. `dyec headnode dayoa-controllers` found the tmux session/root but no
  receipted live controller process; the current shell is not treated as a
  workflow controller.
- No notification was sent because neither requested Slack trigger occurred:
  there were no confirmed attributable Slurm jobs and the controller did not
  reach `rc=0`. No export or FSx deletion was attempted.
- The authorized recovery controller subsequently reached attributable
  `SUCCEEDED` / `rc=0`; its terminal receipt is
  `/home/ubuntu/daylily-runs/pc1703-hg002-slim5x5x-ifx-bjuice-v02-recovery-live-20260814t084403z/status.json#exit_code`.
  A final DYEC workflow-status check, headnode jobs check, and controller
  inventory at `2026-08-14T09:52Z` all show zero active attributable jobs.
- The existing Mike K/John M group-DM thread received its terminal reply as
  message `1786701274.238129`. Verified result paths include the analytical
  delivery package directory
  `results/day/hg38/deliveries/inflection_hiomr2_analytical_callsets_vcf_gvcf/prod-cand-1703-hg002-slim5x5x-hiomr2-ifx-bjuice-v02-20260814T080546Z/HG002-Z-HG002-ANALYSIS-UNIT-5X5X/`,
  its `package_manifest.json`, and the Inflection MultiQC validation JSON.
- The recovery checkout remains at `8bbf0fe0b45918a65cb2c884c5b435bab0582cb1`
  with no tracked or staged source changes; no commit, push, or release tag
  was created.

## Export execution — 2026-08-14T10:21Z

- The user selected the established derived export root and the exact fresh
  destination is
  `s3://lsmc-ssf-sequencing-data/derived/prod-cand-1703/prod-cand-1703-hg002-slim5x5x-hiomr2-ifx-bjuice-v02-20260814T080546Z/`.
  A read-only S3 `list-objects-v2 --max-keys 1` preflight returned
  `KeyCount=0` before launch.
- A headnode `dyec analysis visit --mode export` preceded root access. The
  no-delete DYEC export attached temporary DRA `dra-0031790513f4fa0ec` and
  started FSx task `task-0ed9c6b1e8492244a`, observed `PENDING` at
  `2026-08-14T10:23Z`. The invocation omits
  `--delete-data-in-file-system`; FSx source data is preserved during this
  export.
- The durable receipt will be written to
  `docs/plans/20260814T080546Z_prod_cand_1703_hg002_slim5x5x_hiomr2_inflection_export/fsx_export.yaml`.
  Catalog evidence may be updated only after that receipt reports successful,
  detached export and the required S3 objects are verified.

## Export completion and catalog evidence — 2026-08-14T10:25Z

- Receipt `fsx_export.yaml` reports `status: success`, `phase: complete`,
  `task_lifecycle: SUCCEEDED`, `detached: true`, and
  `delete_data_in_file_system: false`; the temporary association's detach
  lifecycle is `DELETED`. The source root therefore remains on FSx.
- `head-object` verified the exported analytical delivery
  `package_manifest.json` (174,220 bytes) and
  `reports/HG002.inflection.multiqc.html` (42,153,146 bytes) at the selected
  S3 prefix.
- The current catalog alias `inflection-bjuice-product-v0.2` was updated with
  a `validation_runs` success record: DayOA `14.0.14` commit
  `8bbf0fe0b45918a65cb2c884c5b435bab0582cb1`, DYEC `17.0.19` commit
  `35531ab8ba0224932ba9f6a921b4779a7182862d`, and the exact S3 prefix in
  `stage_or_context`. `dyec catalog show` successfully parses that record.
- The existing Mike K/John M analysis Slack thread received the requested
  export-completion reply at `1786703441.442879`:
  https://lsmchq.slack.com/archives/D0AQK8RB3D5/p1786703441442879?thread_ts=1786697331.111039&cid=D0AQK8RB3D5

## Approved FSx cleanup — 2026-08-14T10:45Z

- After the user gave the required second explicit approval for the exact FSx
  root and the already-verified S3 destination, a `mode=delete` analysis visit
  was recorded and the cleanup agent acquired the root delete lock.
- `dyec exports cleanup --confirm-fsx-delete` completed for the exact root using
  cleanup association `dra-039abdb74c3b10a25`. DYEC reported `S3 objects
  preserved` and no change outside the approved analysis root.
- A post-cleanup Ubuntu-headnode check returned `deleted` for the exact FSx
  path. A fresh S3 `head-object` verified the exported package manifest at
  the recorded `report_path` (174,220 bytes; ETag
  `462bac701a650a676595875cc5359610`). The source-root lock directory was
  removed together with the approved root, so no separate lock-release command
  is applicable.
