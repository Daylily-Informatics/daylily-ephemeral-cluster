# DYEC workflow launch dry-run and rerun-trigger ledger

**Opened:** 2026-08-23T06:31:25Z  
**Feature branch:** `codex/dryrun-rerun-trigger-temp-20260823`  
**Baseline:** annotated DYEC `19.0.19`, peeled commit `8616d89d3fb03559a11cb9c0c9eb9ea55a80bc8d`

## Objective

Make the public `dyec workflow launch --dry-run` contract add `-n` to the
effective `dy-r` command even when callers supply `--dy-command`, and expose
an explicit validated `--rerun-triggers` controller option.  Preserve the
existing controller-only execution boundary; this change does not launch or
modify a DayOA workflow.

## Gate 0 inventory

| Item | Status | Evidence |
| --- | --- | --- |
| Isolated worktree | complete | `/Users/jmajor/.codex-worktrees/dyec-dryrun-rerun-trigger-temp-20260823` |
| Baseline release | complete | `19.0.19` is an annotated tag; its peeled commit is `8616d89d3fb03559a11cb9c0c9eb9ea55a80bc8d` |
| Next tag availability | complete | `git ls-remote --tags origin 19.0.20` returned no matching tag before work began |
| Reproduction | complete | In `daylily_run_omics_analysis_headnode.main`, custom `args.dy_command` was normalized but bypassed `build_default_command(... dry_run=True)`, the only `-n` insertion path |
| Scope | complete | DYEC controller argument construction, focused regression tests, and this ledger only |

## Execution rows

| Row | Gate | Status | Evidence |
| --- | --- | --- | --- |
| Enforce dry-run in effective custom/default `dy-r` command | implementation | complete | `apply_workflow_execution_options` injects one `-n` in the unique `dy-r` command segment when the public flag is present |
| Add validated `--rerun-triggers` public/controller forwarding | implementation | complete | Repeatable public/controller option accepts `code`, `input`, `mtime`, `params`, or `software-env`; it rejects an embedded duplicate declaration |
| Regression tests and CLI help inspection | verification | complete | `pytest tests/test_script_entrypoints.py tests/test_cli_registry_v2.py -k 'apply_workflow_execution_options or workflow_launch_calls_python_launch_entrypoint' -q`: 3 passed; `dyec workflow launch --help` lists both options; `python -m py_compile` and `git diff --check` passed |
| Commit and push temporary feature branch | publish | pending | pending |
| Cherry-pick to a release branch based at `19.0.19` | release | pending | pending |
| Commit, push, annotate, and push next semver tag | release | pending | pending |

## Safety boundary

The previously unintended controller was stopped before any job submission.
This code-only release does not start, stop, inspect, or change any active
controller, Slurm job, DayOA checkout, FSx root, DRA, or S3 evidence.
