# DYEC Ultima single-run QC — 604395-20260717_2011

Created: 2026-07-26T23:15:53Z  
Request: run one mounted Ultima sequencing directory on the existing `ursa-*` cluster, produce a terminal `rc=0` DayOA controller, match the supplied native Ultima MultiQC section contract, and retain core outputs as deliverable artifacts. The user explicitly redirected execution to direct DYEC launch before any Ursa configuration revision or run was created.

## Scope and acceptance

| ID | Acceptance item | State | Evidence / boundary |
| --- | --- | --- | --- |
| INV-001 | Exact one Ultima run input is mounted and readable on the target cluster. | COMPLETE | Run/mount `604395-20260717_2011`; `/fsx/run_dir_mounts/604395-20260717_2011/`; source `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/RUN604395/2026/604395-20260717_2011/`; DRA `dra-06f75a6d90b12f2b3`; `dyec mounts verify` passed. |
| INV-002 | Source has the native metric inputs needed by the supplied-report contract. | COMPLETE | 17 FlowQ, 17 SNVQ, 1,867 trimmer statistics, 1,867 trimmer failure-code CSVs, 16 `selfSM`, 18 unmatched CSVs, root LibraryInfo/SequencingInfo/Upload receipts. |
| INV-003 | Target cluster and mounts are reusable; no new storage or cluster provisioning is needed. | COMPLETE | `ursa-m-rgx-fssq` / real Ursa cluster EUID `M-RGX-FSTN`, `UPDATE_COMPLETE`; reference and run-dir access plan both `ACCESSIBLE`, using existing mounts. |
| CFG-001 | Direct-DYEC launch context binds one verified mount, one source URI, and a native nonempty JSON metrics receipt. | COMPLETE | [`20260726T231553Z_ursa_ultima_604395_seq_qc_runs.tsv`](20260726T231553Z_ursa_ultima_604395_seq_qc_runs.tsv) uses the mounted `604395_SequencingInfo.json` as the generic target's explicit `METRICS_PATH`; it is source-native, read-only, and does not invent metric values. |
| RUN-001 | Record the initial direct-DYEC controller attempt without treating its nonzero preflight as successful execution. | COMPLETE | Session `dyec_ultima_604395_20260717_2011_20260726T232149Z` / analysis `ultima_604395_20260717_2011_20260726T232149Z` ended `rc=2` at `2026-07-26T23:23:05Z`; the DYEC catalog injected stale legacy `units.tsv`, which DayOA 13.0.47 rejected before formal Snakemake/Slurm execution. |
| RUN-002 | Record the first standalone-Ultima controller attempt without treating its nonzero parse result as workflow execution. | COMPLETE | Session `dyec_ultima_604395_20260717_2011_20260726T233208Z` / analysis `ultima_604395_20260717_2011_20260726T233208Z` ended `rc=2` at `2026-07-26T23:33:36Z`; it passed the run-context contract then failed during DAG parsing because `prep_results_dirs` mixed aggregate outputs with wildcarded log/benchmark paths. No Slurm work was submitted. |
| RUN-003 | Direct-DYEC controller executes the corrected single-run target and reaches terminal `rc=0`. | COMPLETE | Session `dyec_ultima_604395_20260717_2011_dryrun_20260726T233525Z` / analysis `ultima_604395_20260717_2011_dryrun_20260726T233525Z` started `2026-07-26T23:36:20Z`, ran Slurm job `19`, and completed `rc=0` at `2026-07-26T23:43:12Z`. The requested `--dry-run` did not propagate because an explicit `--dy-command` was supplied; the resulting live execution remained within the user-requested one-run scope and was not cancelled. |
| RUN-004 | Record the attempted native-report reuse controller without treating its source-ref refresh failure as workflow execution. | COMPLETE | Session `dyec_ultima_604395_20260717_2011_native_20260726T234615Z` ended `rc=8` at `2026-07-26T23:46:51Z` before DayOA execution; `--reuse-existing-analysis-dir` attempted `git fetch` through unavailable headnode SSH credentials and emitted `existing_analysis_ref_fetch_failed`. No Slurm work was submitted. |
| RUN-005 | DYEC creates a fresh root at the native-report source ref, runs the one verified mount, and reaches terminal `rc=0`. | COMPLETE | Session `dyec_ultima_604395_20260717_2011_native_20260726T234751Z` completed `rc=0` at `2026-07-27T00:38:12Z`. Job 21 rendered the native tables; job 22 rendered the native MultiQC report. |
| TUNE-001 | Apply the user's explicit report-I/O contract: mounted `/fsx` inputs remain reads, report writes occur on local `/scratch`, final artifacts are staged back to FSx, and supported tool parallelism is raised 4x. | COMPLETE | Baseline job 21: 1 CPU, `00:37:55` elapsed, `00:10.586` CPU, `608.22M` reads. Optimized job 24: 4 CPUs, `00:00:18` elapsed, `00:10.449` CPU; live rule receipt has `tmpdir=/scratch`, `threads=4`, `vcpu=4`, NVMe partitions, `/fsx` run input, and scratch table output. MultiQC v1.36.dev0 exposes no threads option and ran intentionally at 1 CPU. |
| RUN-006 | Launch one fresh direct-DYEC controller from the scratch-staged, four-thread source ref and verify its terminal state and Slurm allocations. | COMPLETE | Session `dyec_ultima_604395_20260717_2011_scratch4x_20260727T004812Z` at source commit `44d326f9` completed `rc=0` at `2026-07-27T00:56:48Z`. Slurm jobs: 23 summary `00:00:12`/1 CPU; 24 native tables `00:00:18`/4 CPUs; 25 MultiQC `00:00:19`/1 CPU. |
| PLAN-001 | Rerun gate amendment | COMPLETE | The user first requested a `dy-r -n` gate, then explicitly instructed: “complete the test run w/out -n.” That later direction superseded the dry-run gate; no source, input, target, or export scope changed. |
| RUN-007 | User-requested fresh direct-DYEC live validation of the exact one-run target, using `dy-r` without `-n`. | COMPLETE | Session `dyec_ultima_604395_20260717_2011_artifactlive_20260727T012253Z` ran `dy-r produce_ultima_run_qc -p -j 5 -k --config run_context_only=true` and completed `rc=0` at `2026-07-27T01:31:42Z`. Slurm jobs 26/27/28 completed: summary 13s/1 CPU; native tables 18s/4 CPUs; native MultiQC 19s/1 CPU. The fresh `analysis_artifacts.tsv` records terminal summary HTML/TSV and native MultiQC HTML; all ten native tables are nonempty but remain unannotated as individual manifest artifacts. `--export-trigger none` was explicit, so this fresh FSx root was not exported. |
| PLAN-002 | User-requested post-controller delivery amendment. | COMPLETE | The user subsequently requested a no-delete export of the fresh `RUN-007` root and registration of its exported result prefix on an Ursa Analysis Execution. The export and Ursa-registration scopes are now tracked separately so a direct-DYEC execution is not misrepresented as an Ursa-created execution. |
| EXP-001 | Export the fresh `RUN-007` FSx root to S3 without deleting FSx source data. | COMPLETE | Required remote export visit was recorded first. An initial validation-only attempt rejected a noncanonical `analysis_results/` S3 segment before creating any DRA/task ([`fsx_export.yaml`](20260726T231553Z_ursa_ultima_604395_seq_qc_artifactlive_export_20260727T014714Z/fsx_export.yaml)). The corrected exact prefix `s3://lsmc-ssf-sequencing-data/derived/ursa-m-rgx-fssq/ultima_604395_20260717_2011_artifactlive_20260727T012253Z/` completed through FSx task `task-020c76198a2d94158` with temporary DRA `dra-0c6c1a089e83645c2`; receipt records `SUCCEEDED`, `detached: true`, `detach_lifecycle: DELETED`, and `delete_data_in_file_system: false` ([`fsx_export.yaml`](20260726T231553Z_ursa_ultima_604395_seq_qc_artifactlive_export_20260727T014740Z/fsx_export.yaml)). S3 verification found 2,412 objects / 620,487,369 bytes, all 10 nonempty native TSVs, the 3.65 MB native MultiQC HTML, summaries, `analysis_artifacts.tsv`, and `artifact_lineage.tsv`. |
| URS-001 | Register the exact fresh S3 result prefix as an artifact on the matching Ursa Analysis Execution. | BLOCKED | Authenticated Ursa search at `/analysis-executions?q=604395` returned zero persisted Analysis Executions. The direct-DYEC launch intentionally created no Ursa submission/execution, and the current Ursa v2 surface exposes read/download/evidence-export operations only, not a manual attach or execution-create control. | Requires explicit user direction to create a normal Ursa Analysis Run/Execution (which is a new orchestration scope) or an owner-approved supported registration interface for externally run controllers. No existing execution, including unrelated `M-RGX-FVFA`, was used. |
| RPT-001 | Generated report contains the supplied native section set for one run: inventory, trimmer stats/failures, FlowQ, SNVQ, coverage, Picard/basic metrics, contamination/sample swap, upload status, and unmatched outputs. | COMPLETE | `ultima_native.multiqc.html` contains all eleven requested headings; all ten native `*_mqc.tsv` tables are nonempty. The report is scoped to `604395-20260717_2011` only. |
| DEL-001 | Core terminal outputs and manifests are exported to the established derived-output root with a durable DayOA artifact manifest and lineage. | COMPLETE | FSx task `task-0d76f9f65776f4331` reached `SUCCEEDED` for the exact derived prefix; the temporary DRA `dra-0625904b712d7748a` was automatically detached with `delete_data_in_file_system=false`. S3 confirms the native HTML, ten native tables, `analysis_artifacts.tsv`, and `artifact_lineage.tsv`. Reconciled receipt: [`fsx_export_reconciled.yaml`](20260726T231553Z_ursa_ultima_604395_seq_qc_deliverables_final/fsx_export_reconciled.yaml). |

## Controller baseline

At the beginning of this run, the target headnode had zero DayOA controllers and zero Slurm jobs associated with this request. This record does not authorize cancellation, requeue, scheduler administration, mount changes, or deletion. The initial Ursa browser form was prepared only locally and was never submitted.

## Report contract

The supplied example report contains these native custom-content sections (the example has two runs; this task must contain only `604395-20260717_2011`):

1. General Statistics
2. Ultima Run Inventory
3. Ultima Trimmer Stats
4. Ultima Trimmer Failure Codes
5. Ultima FlowQ Summary
6. Ultima SNVQ Summary
7. Ultima Coverage Summary
8. Ultima Picard / Basic Run Metrics
9. Ultima Contamination / Sample Swap
10. Ultima Upload Status
11. Ultima Unmatched Outputs

## Execution controls

- Create no cluster or mount. Use direct DYEC against `ursa-m-rgx-fssq`, retaining the verified mount and exact S3 source URI.
- Run DayOA only through DYEC's supported controller path (`dy-r` in its persistent `ubuntu` tmux/login-shell session); never invoke raw Snakemake.
- Preserve analysis-root visit/lock evidence through the supported controller path. Do not make direct filesystem writes outside its guarded scope.
- Treat only a terminal controller record with `rc=0`, report inspection, and DayOA artifact-manifest/lineage evidence as completion. Direct DYEC does not create an Ursa submission record.
- Per the explicit follow-up instruction, `/fsx` remains the read-only mounted input for native Ultima data; generated report material must be written on verified local `/scratch` on NVMe partitions, then staged back to FSx only after successful completion. There is no `/scratch` fallback.

## Direct launch receipt

The final native-report controller used normal `dyec workflow launch --input-contract run_context`, retaining the exact single-row run context and source URI. It ran `dy-r produce_ultima_run_qc -p -j 5 -k --config run_context_only=true` at `codex/ultima-run-qc-standalone` commit `44d326f9`. The active `ursa-v2-acceptance` cost center remained at its existing `200 USD` monthly cap; no budget change or exception was used. The first export invocation correctly failed validation because it was pointed at the derived root rather than the exact required suffix. The corrected direct-DYEC flow created the temporary association/task, exported successfully, and cleaned up the association without deleting FSx data.

## Final state

The fresh direct-DYEC live controller exited `rc=0`, used Slurm jobs 26/27/28 on the NVMe profile, and produced the report plus artifact manifest at `/fsx/analysis_results/ursa-m-rgx-fssq/ultima_604395_20260717_2011_artifactlive_20260727T012253Z`. It is now exported at `s3://lsmc-ssf-sequencing-data/derived/ursa-m-rgx-fssq/ultima_604395_20260717_2011_artifactlive_20260727T012253Z/` with a no-delete receipt and independent S3 object verification. The requested Ursa registration remains blocked because a direct-DYEC launch did not create a matching Ursa Analysis Execution and the authenticated v2 surface has no supported manual-attachment control. All rows are terminal (`COMPLETE` or `BLOCKED`); the export objective is complete, while the combined export-plus-Ursa-registration objective is not complete pending the user-approved execution/registration path.
