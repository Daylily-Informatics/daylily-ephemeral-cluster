# DYEC large remote-text transport execution ledger

- Created: 2026-08-26T14:48:47Z
- Repository: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-artifact-recovery-19.0.31`
- Branch: `codex/large-text-transport-19.0.32`
- Baseline HEAD: `4bdc0191a86183a87f345827b14aeac24c6f7237`
- Parent release: annotated tag `19.0.31`
- Controlling workflow ledger: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260825T093755Z_bjuiceval19024_bloodbridge_bjuice_inflection_ledger.md`

## Gate 0 inventory

The first BloodBridge recovery snapshot attempt did not reach the remote
`dyec analysis snapshot-artifacts` command. `write_remote_text` placed the
base64-encoded 352-artifact recovery specification in a single exported
environment value. The remote login shell subsequently failed to exec Python
with `Argument list too long` and response code 126. The failed analysis root,
recovery specification, FSx, Slurm, S3, and Slack were not mutated.

The transport already has a bounded large-script route in `run_shell`: stage
24-KiB chunks, reconstruct a mode-0700 remote script, verify its SHA-256, run
it under the supported login shell, and remove the staging directory. This
change routes encoded remote text through that existing mechanism and into the
writer over standard input, removing the single-environment-string boundary.

The later approved same-root recovery superseded the fresh-capsule artifact
snapshot. The bounded transport correction remained deferred until the
same-root workflow reached attributable controller/DayOA/Snakemake rc=0/0/0,
after which it was tested as a standalone DYEC patch without reviving the
rejected snapshot/hash design.

## Tracking

| ID | Area | Requirement | Status | Category | Approval gate | Evidence | Root cause | Terminal note |
|---|---|---|---|---|---|---|---|---|
| SSM-001 | transport | Remove large text from a single exported environment value | SUCCESS | feature_implementation | Gate 1 | `daylily_ec/aws/ssm.py`; `tests/test_ssm.py` | Linux per-argument/per-environment-string limit was exceeded before Python started | Encoded text now travels on standard input inside the existing chunkable, SHA-verified `run_shell` staging path; no oversized environment value remains |
| SSM-002 | live proof | Snapshot all 352 declared BloodBridge recovery artifacts | SUPERSEDED | contract_test | Gate 5 | BloodBridge controlling ledger | — | The user rejected the fresh-capsule snapshot/hash route and directed same-root Snakemake mtime recovery instead; it was not revived |
| SSM-003 | workflow | Reach attributable fresh-capsule controller/DayOA/Snakemake rc=0/0/0 | SUPERSEDED | contract_test | Gate 5 | Same-root attempt `c0b8870b-458b-4375-a0fc-8477dbc2a889` | — | Fresh-capsule work was superseded; the authorized same-root workflow reached attributable `0/0/0` before this deferred patch was tested |
| SSM-004 | release | Run focused/full tests, commit, tag, and push next available non-v patch release | READY_TO_RELEASE | feature_implementation | Gate 5 | Focused release set `48 passed`; full suite `2836 passed, 48 skipped, 74 unrelated failures`; `git diff --check` clean | — | Transport-specific `tests/test_ssm.py` passed all 39 cases; current build/catalog advanced to `19.0.32`; commit/tag/push pending |
