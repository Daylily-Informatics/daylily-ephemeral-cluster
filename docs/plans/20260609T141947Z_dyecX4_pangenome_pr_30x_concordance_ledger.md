# dyecX4 Pangenome PR Evidence and 30x Concordance Ledger

Controlling plan: user-provided `dyecX4 Evidence Runbook, PR, and Fresh 30x Pangenome Concordance Plan`
Ledger path: `docs/plans/20260609T141947Z_dyecX4_pangenome_pr_30x_concordance_ledger.md`
Created: `2026-06-09T14:19:47Z`

## Gate 0 Baseline

- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DYEC branch/status: `jem-dev`, tracked clean; untracked local evidence artifacts under `docs/plans/`
- DYEC describe/version: `10.0.10`; `dyec --json version` -> `{"app":"Daylily Ephemeral Cluster","version":"10.0.10"}`
- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DayOA branch/status: `jem-dev`, clean
- DayOA describe: `10.0.2`
- Cluster: `dyecX4`, region `us-west-2`, profile `lsmc`
- Cluster state: `CREATE_COMPLETE`; compute fleet `RUNNING`; headnode `i-05815cdeec4a6dad8` / `r7i.8xlarge` / `10.0.0.45`
- Mounts: 5 managed DRAs observed; read-only run mounts for ONT, ILMN, and ULTIMA are present; control-data DRAs are read-only
- Existing pangenome evidence root: `s3://lsmc-dayoa-analysis-results-usw2/validation/dyecX4/command_catalog_results/jem-dev-20260609T130830Z/`
- Evidence root S3 inventory: 9,815 objects, 3,732,429,185 bytes; last modified `2026-06-09T14:05:22Z`
- Pangenome live exports:
  - `ccv_live_illumina_pangenome_snv_20260609T130830Z`: 1,668 objects, 675,079,481 bytes
  - `ccv_live_ultima_pangenome_snv_20260609T130830Z`: 1,679 objects, 702,074,292 bytes
- Existing all-command dry-run evidence:
  - `20260609T063015Z`: 19 dry-run phases, `rc=1`, 19 failed before fixes
  - `20260609T083613Z`: 19 dry-run phases, `rc=1`, 15 passed and 4 failed before final fixes
  - `20260609T101303Z`: targeted fix-validation dry run, 3 phases, `rc=0`, all passed
  - `20260609T125608Z`: pangenome dry run, 2 phases, `rc=0`, all passed
  - `20260609T130830Z`: pangenome warmup/dry-run/live, 6 phases, `rc=0`, all passed
- PR target: `jem-dev` -> `prod`; no existing PR found at Gate 0

## Cleanup Candidate Paths

Deletion is not approved yet. Before any deletion, print and reconfirm the exact paths below. Delete only paths that still exist and are listed here.

- `/fsx/analysis_results/ubuntu/ccv_warmup_illumina_pangenome_snv_20260609T130830Z`
- `/fsx/analysis_results/ubuntu/ccv_warmup_ultima_pangenome_snv_20260609T130830Z`
- `/fsx/analysis_results/ubuntu/ccv_dryrun_illumina_pangenome_snv_20260609T125608Z`
- `/fsx/analysis_results/ubuntu/ccv_dryrun_ultima_pangenome_snv_20260609T125608Z`
- `/fsx/analysis_results/ubuntu/ccv_dryrun_illumina_pangenome_snv_20260609T130830Z`
- `/fsx/analysis_results/ubuntu/ccv_dryrun_ultima_pangenome_snv_20260609T130830Z`
- `/fsx/analysis_results/ubuntu/ccv_live_illumina_pangenome_snv_20260609T130830Z`
- `/fsx/analysis_results/ubuntu/ccv_live_ultima_pangenome_snv_20260609T130830Z`
- `/fsx/analysis_results/ubuntu/pg_ilmn_sentpg_dryrun_20260609T103834Z`
- `/fsx/analysis_results/ubuntu/pg_ilmn_sentpg_dryrun_20260609T104016Z`
- `/fsx/analysis_results/ubuntu/pg_ilmn_sentpg_dryrun_20260609T104741Z`
- `/fsx/analysis_results/ubuntu/pg_ilmn_sentpg_live_20260609T105300Z`
- `/fsx/analysis_results/ubuntu/pg_ilmn_sentpg_live_20260609T110000Z`
- `/fsx/analysis_results/ubuntu/pg_ilmn_sentpg_live_20260609T111300Z`
- `/fsx/analysis_results/ubuntu/pg_ilmn_sentpg_live_20260609T113002Z`
- `/fsx/analysis_results/ubuntu/pg_ilmn_sentpg_live_20260609T114805Z`
- `/fsx/analysis_results/ubuntu/pg_ultima_ug_dryrun_20260609T104016Z`
- `/fsx/analysis_results/ubuntu/pg_ultima_ug_dryrun_20260609T104950Z`
- `/fsx/analysis_results/ubuntu/pg_ultima_ug_live_20260609T122243Z`

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Gate 0 | Record repo, cluster, mounts, tmux, evidence, and analysis inventory before mutation | SUCCESS | config_or_startup_contract | Gate 0 | agent-orchestrator | Commands: `git status`, `git describe`, `dyec --json version`, `dyec --json cluster describe`, `dyec --json mounts list`, S3 object inventories, SSM tmux/FSx inventory |  | Baseline recorded above; tracked DYEC files were clean and cluster was running. |
| EVID-001 | Evidence | Verify pangenome command-catalog live attempts are terminal and exported | SUCCESS | feature_implementation | Gate 0 | agent-evidence-pr | `docs/plans/20260609T130830Z_dyecX4_pangenome_catalog_live_logs/summary.json` -> 6 phases, all `exit_code=0`; S3 live export object counts above |  | Both live pangenome analyses exited 0 and exported to the evidence root. |
| EVID-002 | Evidence | Write command-catalog runbook markdown and upload it to the evidence root | SUCCESS | feature_implementation | Gate 1 | agent-evidence-pr | Local: `docs/plans/20260609T141947Z_dyecX4_10.0.10_command_catalog_runbook.md`; S3: `s3://lsmc-dayoa-analysis-results-usw2/validation/dyecX4/command_catalog_results/jem-dev-20260609T130830Z/20260609T141947Z_dyecX4_10.0.10_command_catalog_runbook.md`; `head-object` -> 7,688 bytes |  | Runbook written and uploaded to the evidence root. |
| PR-001 | PR | Create or update PR from `jem-dev` to `prod` with evidence/runbook comment naming Mike Kennemer and archived stderr path | OPEN | feature_implementation | Gate 1 | agent-evidence-pr | Gate 0 `gh pr list --base prod --head jem-dev --state all` -> no existing PR |  |  |
| CLEAN-001 | Cleanup | Delete only ledger-listed `/fsx/analysis_results/ubuntu/<analysis-id>` paths before fresh 30x runs | BLOCKED | legitimate_safety_handling | Destructive approval | agent-orchestrator | Cleanup candidate list above | Separate explicit destructive approval is required before deleting FSx analysis directories. | Blocked until the user explicitly approves deletion of the listed paths in this thread. |
| ILMN-001 | Fresh 30x | Run HG002 30x ILMN pangenome plus `produce_snv_concordances`, export via DRA, and verify VCF/concordance outputs | BLOCKED | feature_implementation | After cleanup | agent-ilmn-30x | Pending fresh launch after cleanup approval | Depends on `CLEAN-001`. | Blocked until cleanup gate is approved/completed. |
| ILMN-002 | Fresh 30x | Run HG003 30x ILMN pangenome plus `produce_snv_concordances`, export via DRA, and verify VCF/concordance outputs | BLOCKED | feature_implementation | After cleanup | agent-ilmn-30x | Pending fresh launch after cleanup approval | Depends on `CLEAN-001`. | Blocked until cleanup gate is approved/completed. |
| UG-001 | Fresh 30x | Inspect active staging/copy tmux context and select HG002/HG003 ULTIMA data under `lsmc-ssf-*` external staging | BLOCKED | feature_implementation | After cleanup | agent-ultima-30x | Gate 0 tmux list did not show an obvious `copy`/`ssf` session; full inspection pending | Depends on `CLEAN-001` sequencing in the accepted plan. | Blocked until cleanup gate is approved/completed. |
| UG-002 | Fresh 30x | Run selected HG002/HG003 ULTIMA pangenome plus `produce_snv_concordances`, export via DRA, and verify VCF/concordance outputs | BLOCKED | feature_implementation | After cleanup | agent-ultima-30x | Pending sample selection and fresh launch | Depends on `CLEAN-001` and `UG-001`. | Blocked until cleanup gate is approved/completed. |

## Final State Counts

- `OPEN`: 1
- `SUCCESS`: 3
- `BLOCKED`: 5
- `FAIL`: 0
