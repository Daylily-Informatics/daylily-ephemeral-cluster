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
| PR-001 | PR | Create or update PR from `jem-dev` to `prod` with evidence/runbook comment naming Mike Kennemer and archived stderr path | SUCCESS | feature_implementation | Gate 1 | agent-evidence-pr | PR: `https://github.com/lsmc-bio/daylily-ephemeral-cluster/pull/4`; comment: `https://github.com/lsmc-bio/daylily-ephemeral-cluster/pull/4#issuecomment-4660761100` |  | Existing draft PR #4 was updated from stale 5.0.2 text to current 10.0.10 evidence content and commented with Mike Kennemer, the S3 root, runbook URI, ledger path, and archived stderr reference. |
| CLEAN-001 | Cleanup | Delete only ledger-listed `/fsx/analysis_results/ubuntu/<analysis-id>` paths before fresh 30x runs | SUCCESS | legitimate_safety_handling | Destructive approval | agent-orchestrator | User approved with `APPROVE DELETE the ledger-listed FSx analysis directories and start pangenome analysis`; SSM command `e2654b8d-3268-42fe-b0af-c2632fa0b51b` removed 19 listed dirs, missing 0, remaining_count 0 |  | Only ledger-listed paths were deleted; remaining listed path check returned 0. |
| INPUT-001 | Fresh 30x | Copy full HG002/HG003 30x ILMN FASTQs to additive SSF derived input prefix for non-overlapping read-only import | SUCCESS | feature_implementation | After cleanup | agent-ilmn-30x | S3 prefix: `s3://lsmc-ssf-sequencing-data/derived/dyecX4/10.0.10/PR-evidence/input/20260609T193111Z/illumina_30x/NovaSeqX_WHGS_TruSeqPF_HG002-007/`; four copied objects preserve source sizes: `23780603860`, `24464866197`, `23824886981`, `24640173395` bytes | Existing FSx DRA for `downsampled/` prevents mounting its parent source prefix directly. | Used additive S3 copy and a separate non-overlap import path instead of changing any existing read-only DRA. |
| MOUNT-001 | Fresh 30x | Create read-only FSx import mount for copied full 30x ILMN FASTQ prefix | SUCCESS | legitimate_safety_handling | After cleanup | agent-ilmn-30x | Mount `ssf_derived_ilmn_30x_20260609T193111Z`; DRA `dra-021b674814a92ea8f`; source `s3://lsmc-ssf-sequencing-data/derived/dyecX4/10.0.10/PR-evidence/input/20260609T193111Z/illumina_30x/NovaSeqX_WHGS_TruSeqPF_HG002-007/`; headnode path `/fsx/control_data/ssf_derived/dyecX4/10.0.10/PR-evidence/input/20260609T193111Z/illumina_30x/NovaSeqX_WHGS_TruSeqPF_HG002-007/`; read-only; auto-import `NEW,CHANGED`; auto-export none; lifecycle `AVAILABLE` |  | Created without changing any existing read-only import mount. |
| DAYOA-001 | Fresh 30x | Fix DayOA pangenome concordance deduper contract for `spmd` | SUCCESS | feature_implementation | Bugfix gate | agent-ultima-30x | DayOA commit `240eee6` (`Allow pangenome spmd concordance deduper`); annotated tag `10.0.3`; pushed `jem-dev` and tag; focused test `python3 -m pytest tests/test_workflow_target_aliases.py` -> 7 passed | DayOA `10.0.2` pangenome rules write VCFs under `{sample}/align/pangenome_{sr,ug}/spmd/snv/sentpg/`, but `workflow/rules/common.smk` rejected `dedupers=["spmd"]`, so `produce_snv_concordances` could not target the pangenome VCF path. | `spmd` is now a valid DayOA deduper config code for pangenome concordance expansion. |
| DYEC-001 | Fresh 30x | Update DYEC DayOA dependency/catalog pins to `10.0.3` and support explicit FSx-to-S3 validation maps for read-only submounts | IN_PROGRESS | feature_implementation | Bugfix gate | agent-orchestrator | Local DYEC files changed: `pyproject.toml`, `config/daylily_pipeline_command_catalog.yaml`, packaged catalog, pin tests, `daylily_ec/stage_samples.py`, `daylily_ec/cli.py`, and staging tests; focused tests under `source ./activate`: `python -m pytest tests/test_stage_samples_from_local_to_headnode.py::test_build_reference_uri_uses_explicit_fsx_s3_mapping_before_role_root tests/test_repository_catalog.py tests/test_cli_registry_v2.py tests/test_lsmc_bio_fork_contract.py` -> 124 passed | DayOA `10.0.2` is insufficient for pangenome concordance live runs; sample staging previously assumed a single `/fsx/control_data` S3 root and could not precheck the read-only SSF-derived DRA prefix. | Commit/tag/push pending after fresh launch metadata is recorded. |
| ILMN-001 | Fresh 30x | Run HG002 30x ILMN pangenome plus `produce_snv_concordances`, export via DRA, and verify VCF/concordance outputs | IN_PROGRESS | feature_implementation | After cleanup | agent-ilmn-30x | Manifest: `docs/plans/20260609T193111Z_dyecX4_fresh_30x_pangenome_concordance/illumina_30x_analysis_samples.tsv`; mapped precheck passed with 2 rows, 2 samples, 52 source objects, and 2 concordance directories; generated `illumina_config/20260609T200121Z_ef6d4b4a_samples.tsv` and `illumina_config/20260609T200121Z_ef6d4b4a_units.tsv`; live analysis/session `pg_ilmn_hg002_hg003_30x_pangenome_concordance_20260609T200121Z` launched with DayOA `10.0.3`; rendered pangenome command uses `/scratch/pangenome_sr_tmp_*`, `-t 128`, and submitted HG002 Slurm external job `11` on `i384nvme` |  | Running with export configured as `--export-trigger on-success`. |
| ILMN-002 | Fresh 30x | Run HG003 30x ILMN pangenome plus `produce_snv_concordances`, export via DRA, and verify VCF/concordance outputs | IN_PROGRESS | feature_implementation | After cleanup | agent-ilmn-30x | Manifest: `docs/plans/20260609T193111Z_dyecX4_fresh_30x_pangenome_concordance/illumina_30x_analysis_samples.tsv`; mapped precheck passed with 2 rows, 2 samples, 52 source objects, and 2 concordance directories; generated `illumina_config/20260609T200121Z_ef6d4b4a_samples.tsv` and `illumina_config/20260609T200121Z_ef6d4b4a_units.tsv`; live analysis/session `pg_ilmn_hg002_hg003_30x_pangenome_concordance_20260609T200121Z` launched with DayOA `10.0.3`; rendered pangenome command uses `/scratch/pangenome_sr_tmp_*`, `-t 128`, and submitted HG003 Slurm external job `10` on `i384nvme` |  | Running with export configured as `--export-trigger on-success`. |
| UG-001 | Fresh 30x | Inspect active staging/copy tmux context and select HG002/HG003 ULTIMA data under `lsmc-ssf-*` external staging | SUCCESS | feature_implementation | After cleanup | agent-ultima-30x | Local `tmux ls` had no server; headnode tmux list showed workflow sessions but no obvious copy/sync session; managed ULTIMA run mount `602221-20260417_2346` present from `lsmc-ssf-sequencing-data`; full 30x control CRAM visible under read-only control-data mount: `/fsx/control_data/genomic_data/organism_reads/H_sapiens/giab/agbt_2026/ug/HG003_30x.cleaned.cram` |  | Selected HG003 30x ULTIMA CRAM from the existing read-only control-data DRA because it is the validated HG003 30x pangenome input available on FSx. |
| UG-002 | Fresh 30x | Run selected HG002/HG003 ULTIMA pangenome plus `produce_snv_concordances`, export via DRA, and verify VCF/concordance outputs | IN_PROGRESS | feature_implementation | After cleanup | agent-ultima-30x | First live analysis `pg_ultima_hg003_30x_pangenome_concordance_20260609T193111Z`, tmux session same, DayOA `10.0.2`, exited `1` at `2026-06-09T19:35:51Z`; relaunch `pg_ultima_hg003_30x_pangenome_concordance_20260609T194248Z` with DayOA `10.0.3` started at `2026-06-09T19:43:20Z`; DAG built, conda env created, `pre_prep_ultima_cram` completed, and `sentieon_pangenome_ug` submitted as Slurm external job `9` on `i384nvme` with rendered `-t 128` by `2026-06-09T19:53Z` | DayOA `10.0.2` rejected `dedupers=["spmd"]` even though pangenome VCF path uses `spmd`; fixed in DayOA `10.0.3`. | Relaunch is running; export is configured with `--export-trigger on-success`. |

## Final State Counts

- `OPEN`: 0
- `IN_PROGRESS`: 4
- `ATTEMPTING_BUGFIX`: 0
- `SUCCESS`: 9
- `BLOCKED`: 0
- `FAIL`: 0
