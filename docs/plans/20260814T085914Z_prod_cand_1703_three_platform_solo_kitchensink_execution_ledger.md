# prod-cand-1703 three-platform solo kitchen-sink execution ledger

Created: 2026-08-14T08:59:14Z

Controlling request: use the activated DYEC CLI to run the production command-
catalog solo kitchen-sink analyses for Illumina, ONT, and Ultima in parallel on
`prod-cand-1703` (`us-west-2`, profile `lsmc`), using the already-mounted
downsampled slim-data inputs. Monitor the catalog-owned controllers and Slurm
work. After an Ultima controller exits `rc=0`, export its exact analysis root
from FSx to S3, verify the detached export receipt and objects, then request a
second explicit approval before deleting that FSx analysis root. Send a new
Slack group-DM thread to Jhohn M and Mike K at start, Slurm submission, and
each terminal return code.

## Gate 0 baseline

- Controlling ledger: this file.
- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`.
  `git status --short --branch` at 2026-08-14T08:59Z reported detached `HEAD`
  and numerous pre-existing untracked files/directories. They are outside this
  task; this ledger is the only task-owned local write.
- Local activation: `source ./activate` -> `DAY-EC activated`; `dyec --version`
  -> `Daylily Ephemeral Cluster 17.0.14`.
- Catalog inventory: schema version 6 exposes
  `illumina_hg002_kitchensink_multiqc`, `ont_snv_alignstats_kitchensink`, and
  `ultima_snv_alignstats_kitchensink`; all are `prod` sample-analysis commands,
  use `default_reads_slim`, require the six-manifest contract, and pin DayOA
  `14.0.14`.
- Headnode: `i-0a19cb6b471874d56` (`10.0.0.22`, Ubuntu `ubuntu`) reports
  DYEC `17.0.14`; cluster status is `UPDATE_COMPLETE` with compute fleet
  `RUNNING`.
- Cost center: `prod-cand-1703-ccenter` is active for `ubuntu`, has a `$999`
  monthly cap, and the cluster's project tag is `prod-cand-1703`; no budget or
  cost-center mutation is needed.
- Headnode input presence was verified with `stat`:
  - ILMN 5x R1/R2 are readable regular files at the six-manifest-declared
    `/fsx/data/genomic_data/organism_reads_slim/.../downsampled/` paths
    (3,899,321,181 and 4,000,405,121 bytes).
  - ONT 3x CRAM/CRAI are readable regular files at the declared slim-data path
    (3,157,800,957 and 21,478 bytes).
  - Ultima 1x CRAM/CRAI are readable regular files at the declared slim-data
    path (1,677,722,640 and 38,027 bytes).
- Initial `dyec headnode jobs` showed unrelated HG002 HIOMR2 jobs `682`-`732`
  in `RUNNING`/`CONFIGURING` state. These are outside this task and will not be
  changed. No kitchen-sink session, controller, or Slurm job was found in this
  baseline.
- No raw Snakemake invocation, Slurm intervention, budget/cost-center change,
  DRA detach, or FSx/S3 deletion is authorized. Catalog launch must own the
  interactive `ubuntu`/`bash`/`tmux`/`dy-r` lifecycle.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| BASE-001 | Gate 0 | Freeze repository, activated CLI, exact catalog, cluster, slim-data inputs, cost center, and current controller/Slurm occupancy before a task-owned workflow write. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | Baseline above: active cluster/fleet, matching headnode/local DYEC `17.0.14`, active project/cost center, verified declared inputs, and unrelated-only existing Slurm occupancy. |  | Gate 0 recorded before the first task-owned catalog render/launch. |
| MSG-001 | Slack | Create one group-DM with Jhohn M and Mike K, then post start, Slurm-submission, and terminal-rc updates in that thread. | IN_PROGRESS | feature_implementation | Gate 1 | orchestrator | No existing exact two-recipient group-DM was present. A new conversation with `johnm@lsmc.com` (JEM, resolving “Jhohn M”) and Michael Kennemer (resolving “Mike K”) was opened; start `D0AQK8RB3D5/1786698093.048389`, live-controller-start `D0AQK8RB3D5/1786698606.635189`, task-owned-Slurm updates `D0AQK8RB3D5/1786698940.185869` and `D0AQK8RB3D5/1786699188.040229`, and Ultima terminal rc=0 `D0AQK8RB3D5/1786699845.493699` were sent in one thread. |  | Awaiting ILMN and ONT terminal controller rc values. |
| DRY-ILMN | Catalog dry launch | Render and launch a distinct Illumina dry root from the exact six-manifest slim-data input; require controller rc=0 and zero Slurm submissions. | SUCCESS | contract_test | Gate 1 | orchestrator | `pc1703-ilmn-solo-ks-17014-20260814-0900-dry`: attributed controller exit `0`, zero submitted/finished jobs, no failure markers. |  | Exact rendered ILMN catalog plan completed without compute submission. |
| DRY-ONT | Catalog dry launch | Render and launch a distinct ONT dry root from the exact six-manifest slim-data input; require controller rc=0 and zero Slurm submissions. | SUCCESS | contract_test | Gate 1 | orchestrator | The first parallel local render hit a resource-extraction race before cluster contact; the temporary path cleared without mutation. Serial re-render and `pc1703-ont-solo-ks-17014-20260814-0900-dry` then completed with attributed controller exit `0`, zero submitted/finished jobs, and no failure markers. |  | Exact rendered ONT catalog plan completed without compute submission. |
| DRY-ULT | Catalog dry launch | Render and launch a distinct Ultima dry root from the exact six-manifest slim-data input; require controller rc=0 and zero submitted/finished jobs. | SUCCESS | contract_test | Gate 1 | orchestrator | `pc1703-ultima-solo-ks-17014-20260814-0900-dry`: attributed controller exit `0`, zero submitted/finished jobs, no failure markers. |  | Exact rendered Ultima catalog plan completed without compute submission. |
| LIVE-ILMN | Catalog live launch | Render and launch a fresh Illumina kitchen-sink analysis; monitor to terminal controller state without Slurm intervention. | IN_PROGRESS | feature_implementation | Gate 1 | orchestrator | Catalog accepted `pc1703-ilmn-solo-ks-17014-20260814-0910`; attributed tmux controller is `RUNNING`, with 98 task-owned submissions, 15 `RUNNING`, and 126 of 155 steps complete at 2026-08-14T09:37Z. |  | Controller healthy; no Slurm action taken. |
| LIVE-ONT | Catalog live launch | Render and launch a fresh ONT kitchen-sink analysis; monitor to terminal controller state without Slurm intervention. | IN_PROGRESS | feature_implementation | Gate 1 | orchestrator | Catalog accepted `pc1703-ont-solo-ks-17014-20260814-0910`; attributed tmux controller is `RUNNING`; 18 task-owned submissions, 41 of 126 steps complete, and one task-owned `sent_snv_ont` Slurm job (`964`) remains `RUNNING` at the latest snapshot. |  | Controller healthy; no Slurm action taken. |
| LIVE-ULT | Catalog live launch | Render and launch a fresh Ultima kitchen-sink analysis; monitor to terminal controller state without Slurm intervention. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `pc1703-ultima-solo-ks-17014-20260814-0910` has attributed controller exit `0` from `/home/ubuntu/daylily-runs/pc1703-ultima-solo-ks-17014-20260814-0910/status.json#exit_code`, no failure markers, and 91 task-owned submissions at terminal. A read visit was recorded; final `DAY_final_multiqc.html` (7,641,767 bytes) and `dayoa_evidence_manifest.json` (314,072 bytes) exist under the exact checkout root. |  | Completed without Slurm intervention. |
| RELEASE-001 | DayOA source audit | Compare the exact tracked DayOA diffs from all three catalog worktrees, serially integrate genuine source changes, and tag only a validated final release. | BLOCKED | legitimate_safety_handling | Explicit fallback approval | orchestrator | All three worktrees start at `8bbf0fe0` / `14.0.14` and have the same two-file patch (`123710b88a5717198bdeb21d5935cbaab9871cf16d11e1cba425cd95e9fe667c`). DYEC's generated controller applied it before workflow execution. The RTG hunk duplicates an existing `14.0.14` output-directory guard; the VEP hunk changes an all-empty chromosome-chunk condition from hard failure to first-header-only-chunk continuation. Latest annotated upstream tag is `14.0.15`; a clean isolated audit checkout was created without altering the user's older local DayOA checkout. | The VEP hunk is an automatic fallback. Current source policy requires explicit approval of that specific behavior before it can be committed, pushed, or tagged. | Awaiting explicit approval or rejection of the VEP all-empty-chunk continuation; no DayOA source commit, push, merge, or tag has occurred. |
| EXPORT-ULT | FSx-to-S3 export | After LIVE-ULT returns rc=0, record an export visit, use `dyec export` from the exact Ultima analysis root, and verify success, complete, `SUCCEEDED`, detached receipt state and expected destination objects. | BLOCKED | legitimate_safety_handling | Destination-input gate | orchestrator | LIVE-ULT is rc=0 and final report/evidence artifacts were verified. Catalog contract requires `dyec export --destination-s3-uri "$DESTINATION_S3_URI"`; no current authoritative destination prefix was supplied, and there is no catalog default. | An explicit destination S3 URI is required; it will not be inferred from historical or unrelated paths. | Awaiting user-provided destination URI; export remains no-delete. |
| DELETE-ULT | FSx cleanup | Delete only the exact successfully exported Ultima analysis root after an additional explicit approval in this thread. | BLOCKED | legitimate_safety_handling | Destructive approval | orchestrator | User's initial delete request permits preparation only. | Destructive FSx deletion requires a separately restated effect and second explicit approval. | Awaiting a successful verified export and second approval. |
| ACCEPT-001 | Final acceptance | Record each controller's exact terminal rc, task-owned Slurm submission evidence, required report/artifact evidence, export state, Slack notifications, and remaining cleanup boundary. | OPEN | contract_test | Gate 5 | orchestrator | Pending live workflows. |  |  |

## 2026-08-14T09:44:18Z amendment: CG slim-data request and live re-baseline

- Current local activation is `DYEC 17.0.15.dev1+gdce224c31.d20260814`; the
  running headnode remains `DYEC 17.0.14`.  Any later CG catalog launch must
  pin the supported immutable `17.0.14` build and its declared DayOA
  `14.0.14` ref rather than reconfigure the headnode to the unreviewed local
  development build.
- The current catalog exposes one CG command,
  `complete_genomics_cg_snv_concordance`, not a separate CG kitchen-sink
  command.  Its targets include CG SNV, concordance, and final MultiQC.
- The requested mounted slim CG pair is present and readable at the declared
  `/fsx/references/genomic_data/organism_reads_slim/.../downsampled/` paths.
  The legacy `complete_genomics_mgi_hg003_candidate_blocked.tsv` describes
  those exact paths as `pass_through`, but it is not the required six-manifest
  launch contract.
- The catalog refuses a CG launch without a six-manifest directory containing
  a `staging_receipt.json` in `state: materialized`.  The packaged receipt is
  materialized only for a different full-source/staged pair, so it cannot be
  reused for the requested slim inputs.  No replacement receipt was invented.
- Fresh Slack inspection confirmed that the existing group DM `D0AQK8RB3D5`
  contains JEM (`johnm@lsmc.com`, resolving the requested “Jhohn M”) and
  Michael Kennemer.  A new parent thread will be posted there only if a new
  task-owned CG controller actually starts; no duplicate group DM will be
  created.

| AMEND-CG-001 | Catalog scope | Reconcile the requested CG solo/kitchen-sink wording with the current catalog. | SUCCESS | plan_amendment | Gate 0 | orchestrator | `dyec --json catalog show complete_genomics_cg_snv_concordance` at 2026-08-14T09:39Z. |  | One supported CG profile exists; it is not silently expanded into a nonexistent kitchen-sink variant. |
| CG-MANIFEST-001 | CG input contract | Obtain a materialized six-manifest receipt that binds the declared CG slim pair. | BLOCKED | config_or_startup_contract | Source-contract gate | orchestrator | Current command requires `CG_R1_FQ`, `CG_R2_FQ`, `six_manifest`, and `staging_receipt_required=true`; current slim paths appear only in the legacy pass-through manifest. | No materialized six-manifest receipt for the mounted slim pair was supplied or found. | Await a source-owned materialization receipt or explicit approval to create one through the supported staging contract. |
| LIVE-CG-001 | CG catalog launch | Dry-render, then launch and monitor the supported CG profile without Slurm intervention. | BLOCKED | feature_implementation | Gate 1 | orchestrator | Depends on `CG-MANIFEST-001`; the exact compatible command is `complete_genomics_cg_snv_concordance`. | Launch would otherwise need an invented receipt or an unauthorized full-source substitution. | Await materialized slim six-manifest receipt. |

## Final report

All rows terminal: no

Objective complete: no

Status counts:

- SUCCESS: 6
- OPEN: 1
- IN_PROGRESS: 3
- BLOCKED: 5

No workflow controller, DRA export, FSx cleanup, S3 deletion, or Slurm
intervention has been performed by this task at ledger creation.

No additional CG workflow controller, DRA export, FSx cleanup, or Slurm
intervention was performed by the 2026-08-14T09:44:18Z amendment.

## 2026-08-14T10:21:19Z CG slim materialization and controller-restart recovery

- The requested CG slim pair was materialized as a new local six-manifest
  bundle at
  `docs/plans/20260814T085914Z_prod_cand_1703_three_platform_solo_kitchensink_artifacts/cg_slim_six_manifest_20260814T100530Z/`.
  Its receipt records the exact mounted `/fsx/references` mates, sizes
  `10,251,454,933` and `10,405,048,250` bytes, gzip magic `1f8b`, and the
  headnode SSM verification command
  `5a47c98d-bac8-407a-b765-81c1df27e842`. No OWY-manager data was used.
- `pc1703-cg-solo-ks-17014-20260814-1008-dry` completed with an attributed
  controller `exit_code: 0`. An early status call raced the tmux/bootstrap
  receipt; `dyec workflow status` now waits a bounded 90 seconds for only the
  missing-controller/status-receipt startup condition.
- An in-place restart was attempted only through the supported
  `--reuse-existing-analysis-dir` path and stopped with `rc=8` because the
  completed DayOA checkout had tracked changes in `workflow/rules/rtg_vcfeval.smk`
  and `workflow/rules/vep.smk`. No FSx root was reset, replaced, or deleted.
- A fresh controller restart proof,
  `pc1703-cg-solo-ks-17014-20260814-1018-restart-proof`, reached attributed
  `exit_code: 0` at `2026-08-14T10:21:19Z`; its exact Snakemake log is
  `2026-08-14T102113.930200.snakemake.log` and it recorded zero Slurm
  submissions.

| CG-MANIFEST-001 | CG input contract | Materialize and validate an exact six-manifest bundle for the mounted CG slim pair. | SUCCESS | feature_implementation | Gate 1 | orchestrator | Receipt-bound bundle and identity validation above. |  | New bundle only; no old/full-input receipt reused. |
| DRY-CG-001 | Catalog dry launch | Render and run the one supported CG catalog profile with the receipt-bound slim bundle; require controller rc=0 and zero Slurm submissions. | SUCCESS | contract_test | Gate 1 | orchestrator | `pc1703-cg-solo-ks-17014-20260814-1008-dry` and fresh restart proof `pc1703-cg-solo-ks-17014-20260814-1018-restart-proof`, both attributed rc=0 and zero submissions. |  | The status-startup race is bounded in the CLI; the dirty completed root was preserved. |
| LIVE-CG-001 | CG catalog launch | Launch and monitor the supported CG profile from the receipt-bound slim bundle without Slurm intervention. | SUCCESS | feature_implementation | Gate 1 | orchestrator | The first fresh root `pc1703-cg-solo-ks-17014-20260814-1025` stopped at attributed `rc=1` before a task-owned Slurm admission because its implicit project-name lookup returned empty JSON. The active registry entry `prod-cand-1703-ccenter` was then supplied explicitly. Primary root `pc1703-cg-solo-ks-17014-20260814-1032` submitted jobs `1170`-`1173` and reached attributed `rc=0`; independently started duplicate root `pc1703-cg-solo-ks-17014-20260814-1035` submitted `1174`-`1177` and also reached attributed `rc=0`. Both terminal receipts are under their exact `/home/ubuntu/daylily-runs/<session>/status.json` paths. |  | Receipt-bound slim inputs, explicit active cost center, and both controllers completed; no cancellation, requeue, or other Slurm intervention occurred. |

## 2026-08-14T11:08:01Z CG live completion and terminal notification

- The supported catalog command `complete_genomics_cg_snv_concordance` now has
  live, attributed controller `rc=0` evidence for the exact mounted slim CG
  six-manifest contract. The primary run is
  `pc1703-cg-solo-ks-17014-20260814-1032`; the independently started duplicate
  `pc1703-cg-solo-ks-17014-20260814-1035` had already completed before any
  cancellation decision was needed.
- The primary terminal receipt is
  `/home/ubuntu/daylily-runs/pc1703-cg-solo-ks-17014-20260814-1032/status.json#exit_code`
  and the duplicate terminal receipt is
  `/home/ubuntu/daylily-runs/pc1703-cg-solo-ks-17014-20260814-1035/status.json#exit_code`;
  both report attributed `exit_code: 0`. Their active controller processes and
  task-owned Slurm jobs had exited by the terminal observation.
- The root cause of the earlier live failure was the catalog's implicit
  cost-center/project-name lookup returning empty JSON. Passing the already
  active, unchanged `prod-cand-1703-ccenter` explicitly admitted the primary
  Slurm batch; no budget, registry, Slurm, or cluster setting was changed.
- The required terminal Slack reply was sent to the existing JEM/Michael
  group-DM thread: `D0AQK8RB3D5/1786703258.407299`, message
  `1786705674.833329`.
- The CG-specific materialization, controller restart proof, live rerun, and
  terminal notification are complete. The separately blocked Ultima S3 export
  still needs an explicit destination URI, and FSx deletion remains a separate
  second-approval boundary.

## 2026-08-14T11:17:01Z primary CG DRA export attempt

- A headnode ubuntu/tmux export visit was recorded for the exact completed CG
  root /fsx/analysis_results/prod-cand-1703/pc1703-cg-solo-ks-17014-20260814-1032.
- The first no-delete dyec exports transfer target used
  s3://lsmc-ssf/derived/prod-cand-1703/pc1703-cg-solo-ks-17014-20260814-1032/
  with destination_analysis_id equal to the real analysis name; no EUID was
  generated or substituted.
- FSx rejected CreateDataRepositoryAssociation before creating a DRA because
  the lsmc-ssf bucket did not exist. No data transfer, S3 evidence URI,
  catalog update, or FSx cleanup occurred from that failed attempt.

| EXPORT-CG-001 | FSx-to-S3 export | Transfer the primary completed CG analysis through a temporary DRA to the supplied derived prefix, verify success, and detach without FSx deletion. | SUCCESS | feature_implementation | Gate 1 | orchestrator | A corrected headnode export visit targeted s3://lsmc-ssf-sequencing-data/derived/prod-cand-1703/pc1703-cg-solo-ks-17014-20260814-1032/. Temporary DRA dra-00f1368711631e73d reached AVAILABLE; task task-06adea4ad8e644e89 reached SUCCEEDED with 3,616 succeeded and 0 failed files. The DRA is detached, and the exact exported final MultiQC and evidence-manifest objects were read back from S3. | The initial lsmc-ssf bucket name was invalid. | Export completed without FSx deletion. |

## 2026-08-14T11:26:08Z primary CG export completion

- The corrected no-delete destination is
  s3://lsmc-ssf-sequencing-data/derived/prod-cand-1703/pc1703-cg-solo-ks-17014-20260814-1032/.
  It was empty before DRA attachment; the DRA created the cluster and analysis
  path through the export rather than a pre-created marker object.
- FSx task task-06adea4ad8e644e89 has Lifecycle SUCCEEDED,
  Type EXPORT_TO_REPOSITORY, SucceededCount 3616, and FailedCount 0.
  Its temporary DRA dra-00f1368711631e73d no longer appears in the association
  inventory, proving the required detach. No cleanup command was invoked.
- Verified exported success evidence:
  - s3://lsmc-ssf-sequencing-data/derived/prod-cand-1703/pc1703-cg-solo-ks-17014-20260814-1032/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc.html
    (7,298,938 bytes).
  - s3://lsmc-ssf-sequencing-data/derived/prod-cand-1703/pc1703-cg-solo-ks-17014-20260814-1032/daylily-omics-analysis/results/day/hg38/reports/dayoa_evidence_manifest.json
    (283,270 bytes).
- The live command provenance is immutable DYEC 17.0.14
  (96cec5a45993e706e8e075853ac0f5fe27b812ac) and DayOA 14.0.14
  (8bbf0fe0b45918a65cb2c884c5b435bab0582cb1) on prod-cand-1703 in us-west-2c.
