# DYEC Benchmark Collector CLI Ledger

Created: 2026-07-03T07:53:11Z

## Gate 0 Inventory Freeze

- Controlling request: add a DYEC CLI ability to reach into an `/fsx/analysis_results/**` controller run directory and run the DayOA benchmark aggregation script so benchmark files are collected to `results/day/<genome-build>/report`/reports using `bin/util/benchmarks/collect_day_benchmark_data.sh <hg38|hg38_broad|b37>`.
- Required DayOA execution contract from repo instructions: run from the DayOA cloned root directory, initialize with `source dyoainit`, then `dy-a local <genome-build>`, then run `bash bin/util/benchmarks/collect_day_benchmark_data.sh <genome-build>`.
- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch `jem-dev`, starting head `ceee014c`, remote branch `origin/jem-dev`.
- Baseline dirty state before this feature: modified `config/day_cluster/prod_cluster_dragen_native_ami_rhel8.yaml`, `config/day_cluster/prod_cluster_dragen_pcluster_image_rhel8.yaml`, `config/imagebuilder/dragen_el8_4_5_4_pcluster315.yaml`, `daylily_ec/workflow/create_cluster.py`, and `tests/test_triplets.py`. These are pre-existing and out of scope for this feature.
- Instruction files read: `AGENTS.md`, `/Users/jmajor/.codex/AGENTS-HOW-TO-RUN-DAYOA.md`, `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`.
- Source sweeps:
  - `rg -n "DayOA Benchmark Collection|collect_day_benchmark_data|dy-a|dayoainit" AGENTS.md daylily_ec tests docs` confirmed the existing benchmark contract lives in `AGENTS.md`.
  - `rg -n "register_group_commands|resolve_headnode_instance_id|run_shell" daylily_ec/cli.py daylily_ec/aws/ssm.py tests/test_cli_registry_v2.py tests/test_script_entrypoints.py` identified CLI registration and headnode SSM patterns.
- Live-system boundary: no live headnode SSM command, Slurm job submission, workflow run, AWS resource mutation, or cluster creation is approved or needed for local implementation.

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| BENCH-001 | CLI command | Add a DYEC CLI command for collecting DayOA benchmark summaries from an analysis run directory on the headnode. | SUCCESS | feature_implementation | Gate 2 | orchestrator | Added `dyec workflow collect-benchmarks` in `daylily_ec/cli.py`; registered under the `workflow` group with JSON, mutating, long-running policy. |  | Command is available as `dyec workflow collect-benchmarks`. |
| BENCH-002 | Remote script contract | Command must validate genome build, require a DayOA cloned root or resolve it under the controller run directory, run from the DayOA root, execute `source dyoainit`, `dy-a local <genome-build>`, and `bash bin/util/benchmarks/collect_day_benchmark_data.sh <genome-build>`. | SUCCESS | feature_implementation | Gate 2 | orchestrator | Remote SSM payload validates `/fsx/analysis_results/<owner>/<analysis_id>`, derives `<analysis-root>/daylily-omics-analysis`, acquires/releases a DYEC analysis write lock, runs `source dyoainit`, `dy-a local "$GENOME_BUILD"`, and `bash "$COLLECTOR" "$GENOME_BUILD"`. |  | Payload writes `results/day/<genome-build>/reports/benchmarks_summary.tsv` and emits `__DAYLILY_BENCHMARK_COLLECTION__` JSON. |
| BENCH-003 | Tests | Add regression tests for command registration, SSM payload shape, genome validation, and failure behavior. | SUCCESS | contract_test | Gate 5 | orchestrator | Updated `tests/test_cli_registry_v2.py` with registry policy coverage plus SSM payload, invalid genome, invalid analysis root, and remote-failure tests. |  | Local mocked tests cover behavior without a live headnode. |
| BENCH-004 | Docs | Document the command, supported genome builds, and expected output path. | SUCCESS | feature_implementation | Gate 5 | orchestrator | Updated `docs/cli_reference.md` and `docs/operations.md` with command example and expected output path. |  | Docs use current `dyec` spelling and `--cluster` flag. |
| BENCH-005 | Validation | Run focused local tests and whitespace checks without touching live headnodes. | SUCCESS | contract_test | Gate 5 | orchestrator | `source ./activate && python -m py_compile daylily_ec/cli.py`; `source ./activate && pytest tests/test_cli_registry_v2.py -q -> 120 passed`; `source ./activate && pytest tests/test_analysis_lock.py tests/test_headnode_readiness.py -q -> 7 passed`; `git diff --check`; `dyec workflow collect-benchmarks --help`; local negative validation for DayOA clone path exited 2 before SSM. |  | No live SSM command, Slurm job, cluster creation, or AWS mutation was run. |

## Final Terminal Report

- Rows terminal: 5/5.
- Changed owned files: `daylily_ec/cli.py`, `tests/test_cli_registry_v2.py`, `docs/cli_reference.md`, `docs/operations.md`, and this ledger.
- Pre-existing dirty files preserved and not intentionally changed: `config/day_cluster/prod_cluster_dragen_native_ami_rhel8.yaml`, `config/day_cluster/prod_cluster_dragen_pcluster_image_rhel8.yaml`, `config/imagebuilder/dragen_el8_4_5_4_pcluster315.yaml`, `daylily_ec/workflow/create_cluster.py`, and `tests/test_triplets.py`.
- Validation remained local/mocked only; no live headnode SSM command, Slurm job, workflow run, AWS resource mutation, or cluster creation was performed.
