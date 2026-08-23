# DYEC 19.0.20 workflow launch release ledger

**Opened:** 2026-08-23T06:31:25Z  
**Release branch:** `codex/release-19.0.20-dryrun-rerun-20260823`  
**Release baseline:** annotated `19.0.19`, peeled commit `8616d89d3fb03559a11cb9c0c9eb9ea55a80bc8d`

## Release scope

Cherry-pick the isolated dry-run/rerun-trigger feature commit
`f3f085cef1c1916e26054aae4e7da4b3b19014c1` onto the exact `19.0.19`
baseline, then publish DYEC `19.0.20` without changing historical catalog
snapshots.

## Gate 0

| Item | Status | Evidence |
| --- | --- | --- |
| Private release worktree | complete | `/Users/jmajor/.codex-worktrees/dyec-release-19.0.20-dryrun-rerun-20260823` |
| Release ancestry | complete | Branch begins at peeled `19.0.19` commit `8616d89d3fb03559a11cb9c0c9eb9ea55a80bc8d` |
| Feature provenance | complete | `f3f085ce` was pushed on `codex/dryrun-rerun-trigger-temp-20260823`; release cherry-pick `023e185e` retains `-x` provenance |
| New tag availability | complete | `19.0.20` was absent from `origin` before release work |

## Release rows

| Row | Status | Evidence |
| --- | --- | --- |
| Apply public dry-run command control | complete | Custom and default `dy-r` commands pass through one effective-command control that appends `-n` only when absent |
| Add public rerun-trigger control | complete | `--rerun-triggers mtime` is forwarded and injected into the effective command; duplicate embedded control fails clearly |
| Advance current immutable catalog snapshot | complete | `CURRENT_DYEC_BUILD=19.0.20`; source and payload YAML add an equal `dyec_builds.19.0.20` snapshot while retaining `19.0.19` |
| Verify candidate | complete | `pytest ... -k 'apply_workflow_execution_options or workflow_launch_calls_python_launch_entrypoint or 19_0_19 or 19_0_20' -q`: 5 passed; `python -m py_compile` passed; source/payload `cmp -s` passed; `git diff --check` passed; `dyec catalog list --dyec-version 19.0.20 --command-class utility` parsed the new snapshot |
| Commit, push, annotate, and verify tag | pending | pending |

## Non-goals

No cluster, controller, DayOA workflow, Slurm job, FSx root, DRA, S3 evidence,
or GitHub Release is created or changed by this release.
