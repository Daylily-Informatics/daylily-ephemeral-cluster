# DYEC 19.0.36 headnode force-repair ledger

## Objective

Release and deploy the narrow startup-transport repair required for
`dyec headnode configure --force` to rebuild a broken or absent DAY-EC
environment without first invoking the stale managed shell bootstrap.

## Gate 0 evidence

- Base release: annotated DYEC `19.0.35`, commit
  `46088e12710620491f60931172032059d205bf23`.
- Target cluster: `bjuiceval-19024` in `us-west-2`, state file
  `/Users/jmajor/.config/daylily/state_bjuiceval-19024_20260824000053.json`.
- Preflight: zero active DayOA controllers. Slurm job `17071`,
  `ganon2_food_resume96r2`, is unrelated and remains untouched.
- Failed configure SSM command:
  `cd8e93cb-63e2-486b-8749-3f7edbf4df9b`. The repair-mode transport still
  entered `sudo -iu ubuntu`, which sourced the stale headnode bootstrap before
  the configure payload and raced the DAY-EC reset/rebuild.
- Pinned headnode source was not patched. The failed operation left the old
  DYEC `19.0.30` and DayOA `16.0.13` refs in place and no bootstrap receipt.

## Control ledger

| ID | Work | Status | Terminal evidence |
|---|---|---|---|
| FIX-001 | Make `require_startup_success=False` execute as `ubuntu` in an interactive login Bash that explicitly suppresses profile and bashrc startup. | SUCCESS | Read-only SSM proof returned `REPAIR_PAYLOAD_OK user=ubuntu home=/home/ubuntu` with `aws`, `git`, and `python3` available and no managed bootstrap output. |
| CAT-001 | Publish `19.0.36` as a code-only DYEC release while retaining the already immutable `19.0.35` command-catalog build, DayOA `16.0.23`, and all command shapes. | SUCCESS | No catalog content changes; source/payload catalogs remain byte-identical and public build `19.0.35` resolves DayOA `16.0.23`. |
| REL-001 | Commit, push, and annotate DYEC `19.0.36`. | IN_PROGRESS | Exact clean release commit and annotated tag required. |
| LOCAL-001 | Merge the new release into the dirty operator checkout without losing user changes. | IN_PROGRESS | `19.0.36` must be an ancestor of the operator branch; existing dirty paths remain. |
| DEPLOY-001 | Rerun the exact public `dyec headnode configure --force` command from released `19.0.36`. | IN_PROGRESS | Configure rc=0 and exact remote DYEC `19.0.36` / DayOA `16.0.23` refs and bootstrap receipt. |

## Boundaries

- Do not patch pinned source on the headnode.
- Do not cancel, requeue, reprioritize, or otherwise manipulate Slurm job
  `17071`.
- Do not modify analysis roots, export data, clean FSx, or alter cluster
  capacity.
- Per operator direction, do not run pytest or generic git test suites. Use
  direct transport-contract checks and the exact live configure operation.
