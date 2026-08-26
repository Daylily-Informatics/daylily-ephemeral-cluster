# DYEC 19.0.31 explicit artifact-recovery release ledger

Controlling request: add a public, provider-neutral artifact snapshot and
fresh-capsule recovery interface for the BloodBridge 23-AU DayOA 16.0.7
recovery, with no source discovery, fallback, overwrite, AU exclusion, or FSx
or S3 deletion.

## Gate 0 inventory

- Clean isolated worktree:
  `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-artifact-recovery-19.0.31`.
- Branch: `codex/artifact-recovery-19.0.31`.
- Base: annotated tag `19.0.30`, commit
  `27984661852b1bd75a4e38f1321e653889d350fa`.
- The shared DYEC checkout contains user-owned changes and was excluded from
  all writes.
- `19.0.31` was absent from local and remote tag inventories before release
  preparation and must be rechecked immediately before tagging.
- The immutable 19.0.30 catalog snapshot is retained byte-for-byte.

## Interface and safety contract

1. `dyec analysis snapshot-artifacts` accepts one exact source root and one
   operator-supplied `dyec.analysis_recovery_spec/1.0`; it never discovers
   artifacts. It rejects partial files, symlinks, unsafe paths, duplicate path
   or role ownership, recomputed-AU ownership, missing required roles, and
   hash drift.
2. The emitted `dyec.analysis_recovery_source/1.0` binds every role and stable
   AU owner to its canonical relative path, positive byte size, SHA-256, and
   explicit completeness state.
3. `--artifact-recovery-manifest` is valid only for a fresh absent capsule with
   an explicit staged six-manifest input contract. The headnode verifies source
   bytes, copies with `shutil.copy2`, rehashes staged and committed bytes,
   refuses existing destinations, and writes a bounded materialization receipt.
4. A same-capsule live continuation does not reconsume the source manifest; it
   uses the ordinary exact-ref/exact-commit reuse route and differs from its
   accepted dry command only by removal of `-n`.
5. Catalog command
   `bloodbridge-bjuice-inflection-artifact-recovery` pins DayOA `16.0.7`,
   requires the recovery manifest, retains all 23 AUs, uses `-j 444 -T 1 -p
   -k --rerun-triggers mtime`, and targets Bjuice plus analytical Inflection
   closure.

## Control ledger

| ID | Requirement | Status | Evidence | Terminal note |
|---|---|---|---|---|
| API-001 | Public snapshot command and strict schema | READY | Registry exposes JSON-capable `analysis snapshot-artifacts`; focused CLI and schema tests pass | No internal-module integration is required by callers |
| COPY-001 | Transactional source verification and materialization | READY | Source/staged/destination hashes, no symlinks, no overwrite, committed-file rollback, explicit receipt | Copying is deliberate recovery materialization, not a fallback path |
| LAUNCH-001 | Fresh-capsule-only launch integration | READY | CLI, repository catalog argv, and headnode payload tests enforce six-manifest/fresh-root requirements | Existing analysis roots cannot consume the initial recovery option |
| CATALOG-001 | Immutable 19.0.31 catalog snapshot and DayOA 16.0.7 pin | READY | Source/payload catalogs are byte-identical; 19.0.30 remains unchanged; release-specific tests pass | Dry/live parity is explicit |
| TEST-001 | Focused and broader local validation | SUCCESS | New-file Ruff and legacy fatal-rule Ruff checks pass; focused release/recovery suite `18 passed`; earlier combined registry/entrypoint run reached `319 passed` and exposed only known unrelated baseline fixtures after the historical 19.0.30-current assertion was corrected | Baseline fixture failures concern resources/pricing, credential-authority tests, benchmark CLI tests, and old configure-entrypoint expectations, not recovery code |
| RELEASE-001 | Commit and publish annotated non-v tag `19.0.31` only if still free | READY | Clean diff check and release ledger complete; final remote tag recheck, commit, push, annotated tag, and peeled-commit verification remain the release action | Never move or overwrite a pushed tag |

## Final report

All implementation/test rows terminal: yes.

Release objective complete: no — source is ready for the final tag-availability
check, release commit, branch push, annotated tag, and tag verification. No AWS,
headnode, FSx, S3, Slurm, or Slack mutation is claimed by this source ledger.
