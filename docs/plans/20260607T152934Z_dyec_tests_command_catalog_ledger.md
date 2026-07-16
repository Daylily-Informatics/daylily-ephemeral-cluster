# DYEC Tests CLI And Command-Catalog Runner Ledger

Controlling plan: chat request, 2026-06-07
Ledger path: `docs/plans/20260607T152934Z_dyec_tests_command_catalog_ledger.md`
Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`

## Gate 0: Inventory Freeze

- Branch/status: `git status --short --branch` -> `## jem-dev...origin/jem-dev`; pre-existing untracked `.cf`, `.may11cf`, hybrid/export artifacts, and `docs/plans/20260607T131724Z_dyec_cli_exhaustive_prep_test_logs/`.
- Instructions read: repo `AGENTS.md`; `/Users/jmajor/.codex/AGENTS.md`; `/Users/jmajor/.codex/AGENTS-HOW-TO-RUN-DAYOA.md`; `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`; `/Users/jmajor/.agents/AGENTS.md`; `/Users/jmajor/.agents/AGENTS-HOW-TO-RUN-DAYOA.md`; active `/Users/jmajor/.augment/rules/*.md`.
- Runtime baseline: `source ./activate && python --version && python -m pip --version && command -v dyec && dyec --json version && command -v pcluster && pcluster version && command -v aws && aws --version` -> Python 3.11.15, pip 26.1.2, DYEC 8.0.0, pcluster 3.15.0, aws-cli 2.34.29.
- Collection baseline: `source ./activate && python -m pytest --collect-only -q` -> 1042 tests collected.
- Test baseline: `source ./activate && python -m pytest -q` -> 1035 passed, 7 skipped.
- Safety boundary: no `pcluster create-cluster`, `pcluster update-cluster`, `pcluster delete-cluster`, live `dyec create`, live `dyec delete`, raw DayOA `snakemake`, Slurm job control, mount deletion, or cluster lifecycle mutation is part of this implementation run.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Inventory | Record repo state, versions, instructions, baseline tests, and no-mutation boundary. | SUCCESS | plan_amendment | Gate 0 | Agent 1 | Gate 0 section above. |  | Baseline captured before tracked source edits. |
| CLI-001 | CLI | Register `dyec tests`, `dyec tests pytest`, and `dyec tests command-catalog`. | SUCCESS | feature_implementation | Gate 1 | Agent 2 | `source ./activate && dyec tests --help`; `source ./activate && dyec tests command-catalog --help`; `tests/test_cli_registry_v2.py`. |  | New group and subcommands render with required options. |
| PYTEST-001 | CLI | Implement pytest runner with optional branch-aware coverage mode and pass-through args. | SUCCESS | feature_implementation | Gate 1 | Agent 3 | `dyec tests pytest -- --collect-only -q` -> 1070 collected; `tests/test_tests_runner.py`. |  | Runner uses active Python and propagates pytest rc. |
| CAT-001 | Catalog | Parse exact command-code strings plus `all`; reject unknown and duplicate IDs. | SUCCESS | feature_implementation | Gate 1 | Agent 4 | `tests/test_tests_runner.py::test_command_code_parser_exact_all_duplicate_and_unknown`. |  | Default dyec800 command string contains the requested 11 catalog IDs. |
| RENDER-001 | Command rendering | Normalize catalog `dy_command` flags to `-j 150 -p -k -T 0`; add `-n` for dry-run and `--conda-create-envs-only` for warmup. | SUCCESS | feature_implementation | Gate 1 | Agent 5 | `tests/test_tests_runner.py::test_render_dy_command_normalizes_flags_and_warmup`; typo grep for `build-conda-envs-onyl` -> no new hits. |  | Rendering is shlex-based and does not add raw `snakemake` commands. |
| DATA-001 | Inputs | Use catalog slim sample data profiles for sample-analysis and generated `runs.tsv` for run-analysis commands. | SUCCESS | feature_implementation | Gate 1 | Agent 6 | `tests/test_tests_runner.py::test_run_command_catalog_dry_run_only_renders_and_exports`; manifest conversion tests. |  | Sample commands use existing staging config generation; run commands use generated `runs.tsv`. |
| DRA-001 | Run mounts | Preflight existing mounts, reuse matching run DRAs, and create only missing unique run-directory DRAs when explicitly requested. | SUCCESS | feature_implementation | Gate 1 | Agent 6 | `tests/test_tests_runner.py::test_prepare_run_mounts_blocks_then_creates_missing`. |  | Missing run DRAs fail unless `--create-missing-mounts` is passed; create request is read-only and waits up to 3600s. |
| RUN-001 | Execution | Enforce kitchen-sink warmup ordering, dry-run gating, and bounded parallelism for later phases. | SUCCESS | feature_implementation | Gate 1 | Agent 7 | `tests/test_tests_runner.py::test_run_command_catalog_live_only_runs_kitchen_sinks_after_dryrun`; dry-run failure gate tests. |  | Kitchen sinks warm first one at a time; live phases are gated by dry-run success. |
| EXPORT-001 | Evidence | Require `--evidence-s3-uri`; render/export successful evidence below `<root>/<cluster>/command_catalog_results/<dayoa-version>-<UTCSTAMP>/`. | SUCCESS | feature_implementation | Gate 1 | Agent 8 | `tests/test_tests_runner.py` evidence-prefix assertions; README docs. |  | Evidence prefix is deterministic and uses DayOA git tag, cluster, and UTC stamp. |
| TEST-001 | Tests/docs | Add focused tests, run full tests and branch coverage gate, update docs/help where appropriate. | SUCCESS | contract_test | Gate 5 | Agent 9/10 | `python -m pytest -q` -> 1063 passed, 7 skipped; coverage gate -> 80.47%; README update. |  | All acceptance tests passed locally. |

## Status Reports

- Initial: 1 `SUCCESS`, 9 `OPEN`, 0 `BLOCKED`, 0 `FAIL`.
- Final: 10 `SUCCESS`, 0 `OPEN`, 0 `BLOCKED`, 0 `FAIL`.

## Final Verification

- `source ./activate && python -m pytest -q` -> 1070 collected; 1063 passed, 7 skipped.
- `source ./activate && python -m pytest --cov=daylily_ec --cov-branch --cov-fail-under=80 -q` -> 1063 passed, 7 skipped; total branch-aware coverage 80.47%.
- `source ./activate && dyec tests --help` -> registered `pytest` and `command-catalog`.
- `source ./activate && dyec tests pytest -- --collect-only -q` -> 1070 tests collected through the new CLI.
- `source ./activate && dyec tests command-catalog --help` -> required `--cluster`, `--profile`, `--region`, `--command-codes`, and `--evidence-s3-uri`; optional `--dry-run`, `--create-missing-mounts`, `--parallel`, and `--jobs`.
- Safety grep over new surfaces found no generated `pcluster create/update/delete`, live `dyec create/delete`, raw DayOA `snakemake`, or misspelled `build-conda-envs-onyl` command path.

## Next Safe Command

```bash
source ./activate && dyec tests command-catalog \
  --cluster dyec800 \
  --profile lsmc \
  --region us-west-2 \
  --command-codes "illumina_snv_alignstats,illumina_hg002_kitchensink_multiqc,ultima_snv_alignstats,ultima_snv_alignstats_kitchensink,ont_snv_alignstats,ont_snv_alignstats_kitchensink,hybrid_ilmn_ont_snv,hybrid_ilmn_ont_snv_kitchensink,illumina_run_qc,ont_run_qc,ultima_run_qc" \
  --evidence-s3-uri "s3://<evidence-root>/" \
  --dry-run
```

Do not remove `--dry-run` until the dry-run evidence is reviewed and a live workflow run is explicitly approved.
