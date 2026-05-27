# Goodole3 DAY-EC Command Catalog Report Ledger

Created: 2026-05-27T15:57:36Z
Last updated: 2026-05-27T16:10:28Z

## Objective

Create a durable report for the Goodole3 DAY-EC/DayOA command-catalog validation work.

- Control ledger: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/plans/20260527T155736Z_goodole3_dayec_command_catalog_report_ledger.md`
- Final report: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/dayec-5.0.9-command-catalog-tests.md`
- Source artifacts:
  - `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/plans/20260526T223700Z_goodole3_dayoa_dyec_release_catalog_ledger.md`
  - `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/plans/20260527T020500Z_goodole3_serial_kitchensink_driver.py`
  - `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/plans/20260527T032100Z_goodole3_serial_kitchensink_v206_runs.jsonl`
  - `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/plans/20260527T032100Z_goodole3_serial_kitchensink_v206_logs/`

No cluster deletion, prefix deletion, bucket deletion, DRA deletion, or other destructive AWS cleanup is in scope.

## Worker Assignment

| Agent | Worker ID | Role | Terminal result |
|---|---|---|---|
| Agent 1 | `019e6a2e-2444-7db2-ae77-7fe62b801e39` | Release and cluster provenance | Completed read-only provenance pass. |
| Agent 2 | `019e6a2e-3f3e-7391-a56a-08d73197d908` | Successful catalog command evidence | Completed read-only success-row pass. |
| Agent 3 | `019e6a2e-54e4-79f1-a502-e21f35d66c79` | Failed, blocked, and not-run evidence | Completed read-only failure/blocker pass. |
| Orchestrator | parent thread | Ledger, integration, final validation | Created ledger and integrated report. |

## Gate 0: Inventory Freeze

| Surface | Evidence |
|---|---|
| Repo path | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| Branch | `codex/running-nextflow-pipes-doc` tracking `origin/codex/running-nextflow-pipes-doc` |
| HEAD | `681a3c88b78862569e7b9d0bc93ab043e093ed91` |
| Git describe | `5.0.9-3-g681a3c88-dirty` |
| Recent log | `681a3c88 Add DAY-EC Nextflow pipeline runbook`; `1f834ea2 Record blahab44 first kitchensink success`; `67f81c70 Record blahab44 0313 kitchensink status`; `61cef3d2 tag: 5.0.9`; `56b01450 tag: 5.0.8` |
| Dirty state | Pre-existing modified config, headnode readiness, tests, Goodole3 ledger/logs, Blahab44 logs, plus untracked Goodole3 report artifacts. This report work only intentionally edits the report and this ledger. |
| DYEC self-pins | Source and packaged `git_ephemeral_cluster_repo_tag=5.0.9`, `git_ephemeral_cluster_repo_release_tag=5.0.9`. |
| Local activated DYEC version | `5.0.7.dev0+g104fadf31.d20260527` from worker readback. |
| Headnode DYEC version | `5.0.4`. |
| Catalog parity | Source and packaged repository catalog matched; source and packaged global configs matched. |
| Catalog count | 17 commands total: 12 `sample_analysis`, 5 `run_analysis`, all `workflow_launch`. |
| Catalog DayOA pin | Source and packaged DayOA `default_ref=2.0.5`; all 17 command `git_tag` values are `2.0.5`. |
| Validation DayOA tag | v206 launches explicitly used `--git-tag 2.0.6`; DayOA remote tags were present through `2.0.8` during worker readback. |
| AWS identity | `AWS_PROFILE=lsmc`; account `108782052779`; ARN `arn:aws:iam::108782052779:root`. |
| Cluster | `goodole3`, `CREATE_COMPLETE`, ParallelCluster `3.13.2`, Slurm scheduler, compute fleet `RUNNING`. |
| Headnode | `i-0bd631af238bfac56`, `r7i.2xlarge`, private IP `10.0.0.144`, public IP `44.242.81.64`, state `running`. |
| FSx | `fs-03509c3c3fcf86610`, mount name `iafjtb4v`, size `4800 GiB`, lifecycle `AVAILABLE`. |
| FSx mount readback | `/fsx` is `4.4T` size, `104G` used, `4.3T` available, `3%` used. |
| Slurm readback | `squeue` returned headers only at `2026-05-27T16:08:01Z`; no queued or running jobs. |
| Headnode tools | `dyec`, `day-clone`, `tmux`, and `squeue` found; `tmux 3.2a`; `slurm 24.05.8`. |
| DRA inventory | Five `AVAILABLE` associations on `fs-03509c3c3fcf86610`: `/references/` plus four Goodole3 staging prefixes. |
| S3 export root | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/` has `37,183` objects and `93,999,879,684` bytes. |
| Cluster request | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/plans/20260526T223700Z_goodole3_cluster_request.yaml`; cluster `goodole3`, `region_az=us-west-2d`, headnode `r7i.2xlarge`, FSx `4800`, budget enforcement `skip`. |

## Gate Status

| Gate | Requirement | Status | Evidence |
|---|---|---|---|
| Gate 0 | Inventory freeze | SUCCESS | Baseline table above. |
| Gate 1 | Report skeleton | SUCCESS | Report contains cluster creation, staging, launch, monitoring, success, failed/blocked, export, and blocker sections. |
| Gate 2 | Successful command matrix | SUCCESS | Nine successful exported rows recorded with commands, analysis IDs, stats, and S3 prefixes. |
| Gate 3 | Failed/blocked command matrix | SUCCESS | Roche, hybrid Ultima+ONT, CG/MGI, and run-context rows documented with root cause and next action. |
| Gate 4 | Validation | SUCCESS | Report includes copyable command shapes, exact S3 export locations, current config/version notes, and no destructive delete command. |
| Gate 5 | Terminal report | SUCCESS | All report rows are terminal; final status counts are below. |

## Report Ledger Rows

| ID | Owner | Requirement | Status | Gate | Evidence | Terminal note |
|---|---|---|---|---|---|---|
| RPT-001 | Orchestrator | Create ledger with Gate 0 inventory and row table | SUCCESS | 0 | This file. | Ledger created with Gate 0 inventory and terminal rows. |
| RPT-002 | Agent 1 | Document DYEC `5.0.9`, DayOA explicit run tag `2.0.6`, config pins, dirty state | SUCCESS | 0 | Report `Version And Cluster Context`; Agent 1 readback. | Current repo state and source/runtime version split are documented. |
| RPT-003 | Agent 1 | Document `goodole3` create/preflight/verify commands and cluster details | SUCCESS | 1 | Report `Cluster Creation And Readback Commands`. | Cluster creation command family and cluster fields are documented. |
| RPT-004 | Agent 1 | Document live non-destructive cluster checks | SUCCESS | 1 | Report `/fsx`, `squeue`, DRA, and tool readbacks. | Cluster is still running; no jobs are queued. |
| RPT-005 | Agent 2 | Document canonical data staging commands and generated TSV provenance | SUCCESS | 2 | Report `Data Staging Commands` and per-row samples/units paths. | Both general `dyec samples stage` and v206 pass-through staging are documented. |
| RPT-006 | Agent 2 | Document canonical `dyec workflow launch` and exact `day-clone -t 2.0.6` usage | SUCCESS | 2 | Report `Launch And Monitoring Commands` plus per-row launch commands. | Launch shape and DayOA tag override are documented. |
| RPT-007 | Agent 2 | Document successful sample-analysis commands and final S3 exports | SUCCESS | 2 | Nine successful rows and export summary. | Every successful row has command, stats, and final S3 location. |
| RPT-008 | Agent 2 | Document monitor commands | SUCCESS | 2 | Report includes `dyec workflow status/logs`, `dyec headnode jobs`, `squeue`, `df -h /fsx`, and `aws s3 ls --summarize`. | Monitoring commands are copyable. |
| RPT-009 | Agent 3 | Document failed Roche rows | SUCCESS | 3 | Roche first attempt and retry sections; S3 empty-prefix proof. | Cache failure and private Roche image blocker are documented. |
| RPT-010 | Agent 3 | Document failed hybrid Ultima/ONT row | SUCCESS | 3 | Hybrid Ultima/ONT first attempt and retry sections; blocker table. | Sentieon HybridStage1 assertion, license refused evidence, and truncated BAM are documented. |
| RPT-011 | Agent 3 | Document not-run QC/BCL catalog commands | SUCCESS | 3 | Report `Commands Not Represented In The v206 Goodole3 Driver`. | All not-run rows have catalog commands and next actions. |
| RPT-012 | Orchestrator | Integrate agent drafts into final report and normalize command formatting | SUCCESS | 4 | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/dayec-5.0.9-command-catalog-tests.md`. | Agent findings were integrated. |
| RPT-013 | Orchestrator | Validate every successful row has final exported S3 location and stats | SUCCESS | 4 | S3 export summary table; per-row S3 stats. | Nine success prefixes and four empty failed prefixes are recorded. |
| RPT-014 | Orchestrator | Record terminal ledger status counts and final report path | SUCCESS | 5 | Final status section below. | Ledger is terminal for the report objective. |

## Catalog Validation Terminal Matrix

| Command ID | Analysis ID | Terminal status | Export S3 prefix | Objects | Bytes | Root cause or note |
|---|---|---:|---|---:|---:|---|
| `illumina_snv_alignstats` | `gd3v206-ilmnbase5x` | SUCCESS | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ilmnbase5x/` | `2,145` | `6,135,243,305` | Completed and exported. |
| `illumina_snv_alignstats_relatedness_vep_multiqc` | `gd3v206-ilmn5x` | SUCCESS | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ilmn5x/` | `3,794` | `9,283,078,998` | Completed and exported. |
| `ultima_snv_alignstats` | `gd3v206-ugbase5x` | SUCCESS | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ugbase5x/` | `2,104` | `2,593,534,795` | Completed and exported. |
| `ultima_snv_alignstats_kitchensink` | `gd3v206-ug5x` | SUCCESS | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ug5x/` | `3,266` | `5,394,481,804` | Completed and exported. |
| `ont_snv_alignstats` | `gd3v206-ontbase5x` | SUCCESS | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ontbase5x/` | `2,086` | `2,348,353,425` | Completed and exported. |
| `ont_snv_alignstats_kitchensink` | `gd3v206-ont5x` | SUCCESS | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ont5x/` | `3,345` | `4,981,980,903` | Completed and exported. |
| `pacbio_snv_alignstats` | `gd3v206-pbbase5x` | SUCCESS | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-pbbase5x/` | `2,088` | `4,306,320,965` | Completed and exported. |
| `hybrid_ilmn_ont_snv` | `gd3v206-hiobase5x` | SUCCESS | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-hiobase5x/` | `6,415` | `22,393,495,692` | Exported prefix verified; local workflow status is stale after delete-on-export-success removed the FSx analysis dir. |
| `hybrid_ilmn_ont_snv_kitchensink` | `gd3v206-hio5x` | SUCCESS | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-hio5x/` | `8,130` | `27,276,240,588` | Exported prefix verified; local workflow status is stale after delete-on-export-success removed the FSx analysis dir. |
| `roche_snv_alignstats` | `gd3v206-rcbase5x` | FAIL | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-rcbase5x/` | `0` | `0` | ATTEMPTING_BUGFIX led to retry with writable cache. First failure was Apptainer temp/cache permission error. |
| `roche_snv_alignstats_retry1` | `gd3v206-rcbase5xr1` | FAIL | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-rcbase5xr1/` | `0` | `0` | Retry bypassed cache issue but failed on private/unavailable `docker://roche/sbxd-small-variant-caller:latest`. |
| `hybrid_ultima_ont_snv` | `gd3v206-huobase5x` | FAIL | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-huobase5x/` | `0` | `0` | ATTEMPTING_BUGFIX led to thread-reduced retry. First failure was Sentieon HybridStage1 assertion and truncated `stage1_hap.bam`. |
| `hybrid_ultima_ont_snv_retry1` | `gd3v206-huobase5xr1` | FAIL | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-huobase5xr1/` | `0` | `0` | Thread-reduced retry still failed with license-server refused connections, same assertion, and missing EOF on `stage1_hap.bam`. |
| `complete_genomics_mgi_snv_concordance` | not launched | BLOCKED | none | `0` | `0` | Verified CG/MGI mate pair was unavailable; no substitute was authorized. |
| `illumina_run_qc` | not launched | BLOCKED | none | `0` | `0` | Run-context command outside v206 sample-analysis driver; needs separate mounted-run validation. |
| `illumina_bclconvert` | not launched | BLOCKED | none | `0` | `0` | Run-context command outside v206 sample-analysis driver; needs separate mounted-run validation. |
| `illumina_run_qc_bclconvert` | not launched | BLOCKED | none | `0` | `0` | Run-context command outside v206 sample-analysis driver; needs separate mounted-run validation. |
| `ont_run_qc` | not launched | BLOCKED | none | `0` | `0` | Run-context command outside v206 sample-analysis driver; needs separate mounted-run validation. |
| `ultima_run_qc` | not launched | BLOCKED | none | `0` | `0` | Run-context command outside v206 sample-analysis driver; needs separate mounted-run validation. |

## Final Status Counts

Report ledger rows:

| Status | Count |
|---|---:|
| SUCCESS | 14 |
| OPEN | 0 |
| IN_PROGRESS | 0 |
| ATTEMPTING_BUGFIX | 0 |
| FAIL | 0 |
| BLOCKED | 0 |

Catalog validation rows represented in the report:

| Status | Count |
|---|---:|
| SUCCESS | 9 |
| FAIL | 4 |
| BLOCKED | 6 |
| OPEN | 0 |
| IN_PROGRESS | 0 |
| ATTEMPTING_BUGFIX | 0 |

Changed files for this report objective:

- `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/dayec-5.0.9-command-catalog-tests.md`
- `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/plans/20260527T155736Z_goodole3_dayec_command_catalog_report_ledger.md`

No destructive AWS action was performed. The Goodole3 cluster remains running.
