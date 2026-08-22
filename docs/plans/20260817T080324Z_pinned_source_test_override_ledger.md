# Pinned DayOA source test override ledger

Created: 2026-08-17T08:03:24Z

## Objective

Make the specific human-approved case of testing an already-modified, exact
pinned DayOA checkout possible without weakening normal catalog, live, export,
or cleanup safety.

## Gate 0

- The former blanket policy is in `AGENTS.md` under **Pinned DayOA Source
  Immutability**.
- The executable enforcement is
  `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py` in
  `verify_pinned_dayoa_checkout`, called before dispatch and after workflow
  return.
- The user explicitly requested a durable relaxation for the original ILMN
  controller test case. No active controller, Slurm job, FSx root, or DayOA
  checkout is changed by this source-only work.

## Change contract

- Add a reasoned `--pinned-source-test-override` only to `dyec workflow launch`.
- Require an existing exact root, local ref and 40-character commit, no input
  staging, `--dry-run`, an effective `dy-r ... -n` command, and no export or
  delete options.
- Preserve ref/HEAD verification and write before/after status, worktree diff,
  index diff, and untracked-path evidence outside the DayOA checkout.
- In the override path, do not reset or check out the existing DayOA worktree:
  verify its current HEAD against the requested local commit instead.
- Keep normal catalog and live-controller immutability unchanged.

## Verification boundary

- Regression assertions were updated but, per the active user instruction, no
  test suite was run.
- `git diff --check` is the only planned static verification before handoff.
