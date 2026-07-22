# DYEC CLI Workflow Launch And Headnode Helper Pull-In Ledger

Created: 2026-07-22T12:15:43Z

## Objective

Make the existing public DYEC CLI path support routine DayOA launches without
manual SSM/headnode work:

- `dyec workflow launch` must create the headnode tmux controller and run the
  current DayOA contract: `source dyoainit`, `dy-a ...`, `dy-r ...`.
- `dyec catalog` must expose command-catalog list/show/render helpers and a
  quick-launch shortcut that routes catalog entries through the same workflow
  launch implementation.
- Untracked semantic headnode helper work already present in this checkout must
  be pulled into the branch scope instead of ignored.

## Scope

- Local source and tests only unless explicitly requested later.
- No live workflow launch, Slurm mutation, AWS mutation, or budget change is
  authorized by this ledger.
- Preserve unrelated dirty/untracked plans, reports, and user work.

## Gate 0

| Item | Evidence |
|---|---|
| Repository | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` |
| Branch | `codex/dyec-inflection-command-headnode-helpers-20260722` |
| Existing issue | `dyec workflow launch` exists, but default command still used `bin/day_run` and activation still used `. bin/day_activate ... remote` |
| Existing untracked helper work | `daylily_ec/headnode_control.py`, `daylily_ec/headnode_observability.py`, `tests/test_headnode_control.py`, `tests/test_headnode_observability.py`, plus ledger/report artifacts |

## Work Ledger

| ID | Requirement | Status | Evidence | Terminal Note |
|---|---|---|---|---|
| CLI-001 | Pull semantic headnode helper modules/tests into branch scope | DONE | `daylily_ec/headnode_control.py`, `daylily_ec/headnode_observability.py`, `tests/test_headnode_control.py`, `tests/test_headnode_observability.py` are now part of the scoped working diff | Pulled in only the helper modules/tests, not unrelated report/archive artifacts |
| CLI-002 | Expose helper modules through bounded DYEC CLI commands | DONE | `daylily_ec/cli.py` registers `headnode system-info`, `fsx-usage`, `analysis-roots`, `dayoa-controllers`, `dayoa-controller-action`, `slurm-job-action`, `slurm-drain`, and `workflow benchmark-report` | Mutating helper commands retain required JSON policy |
| CLI-003 | Add command-catalog interaction and quick-launch commands | DONE | `dyec catalog list/show/render/launch/quick-launch` registered; `catalog launch` and `quick-launch` call the rendered `workflow launch` argv, not a second launcher | Sample-manifest catalog launch requires explicit staged/generated inputs unless `--allow-stage-discovery` is explicitly passed |
| LAUNCH-001 | Change default workflow command from `bin/day_run` to `dy-r` | DONE | `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py::build_default_command` now emits `dy-r`; targeted entrypoint test asserts this | No raw Snakemake path added |
| LAUNCH-002 | Change default activation from `. bin/day_activate ... remote` to `source dyoainit` plus `dy-a slurm <genome>` | DONE | Generated controller script sources `dyoainit` and then runs `dy-a slurm <genome>` before `run_dy_command "$DY_COMMAND"` | Old `bin/day_activate` path is not used by default launch |
| LAUNCH-003 | Record analysis visit and acquire live write lock around workflow writes | DONE | Generated controller script creates the empty clone root, records `dyec analysis visit`, acquires `dyec analysis lock acquire`, then calls `day-clone`; release trap calls `dyec analysis lock release` | Lock acquisition intentionally precedes `day-clone`; `day-clone` supports locked empty roots |
| TEST-001 | Update and run focused tests for launcher and pulled-in helpers | DONE | `python -m py_compile ...`; `python -m pytest tests/test_headnode_control.py tests/test_headnode_observability.py tests/test_headnode_semantic_cli.py -q`; `python -m pytest tests/test_script_entrypoints.py -k 'build_default_command_includes_requested_flags or main_launches_workflow_session' -q`; `python -m pytest tests/test_cli_registry_v2.py -k 'headnode or workflow_launch or catalog' -q` | 135 helper/semantic CLI tests, 2 launcher tests, and 28 CLI registry/catalog tests passed |

## Acceptance

- `dyec workflow launch --help` remains available and explicit about its tmux
  launch behavior.
- The generated headnode controller script uses `dy-r` and `dy-a`, not the
  retired `bin/day_run`/`bin/day_activate` path.
- Public DYEC CLI exposes the pulled-in headnode helper operations with bounded
  JSON output.
- Public DYEC CLI exposes catalog list/show/render/launch/quick-launch. Render
  is non-mutating; launch and quick-launch are mutating JSON-capable wrappers
  around workflow launch.
- Focused tests pass for the launcher and helper modules.
