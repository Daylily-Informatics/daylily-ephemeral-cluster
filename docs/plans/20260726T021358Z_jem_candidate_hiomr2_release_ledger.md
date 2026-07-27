# DYEC JEM candidate HIOMR2 release ledger

Controlling request: create the DYEC `jem-candidate-260725` release train for
the integrated DayOA HIOMR/HIOMR2 candidate and preserve the explicit
two-version self-pin contract.

## Gate 0 — inventory freeze

- Candidate branch: `jem-candidate-260725`, created clean from
  `8c576b28c8d7bd9a6d52d6784fed387ca014a65c` (`14.0.9`).
- The source DYEC checkout was deliberately not used for commits because it
  has untracked export, report, temporary, and ledger artifacts.
- DayOA candidate is remote branch `jem-candidate-260725`, exact commit
  `39405bc3ca95631bd9b04b592edcf782c81d2822`, tagged with annotated `13.0.40`.
- Existing DYEC self configuration points to `14.0.8`; existing HIOMR-related
  catalog entries and contract tests point to DayOA `13.0.37`.
- Release sequence: `14.0.10` moves the HIOMR-related DayOA catalog pins to
  `13.0.40`; `14.0.11` changes source and payload self/release pins to
  `14.0.10` while retaining DayOA `13.0.40`.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0 | Inventory | Freeze clean candidate source and explicit source/payload pin surfaces | SUCCESS | feature_implementation | Gate 0 | Codex | Gate 0 inventory above; clean worktree status |  | No source-checkout operational artifacts can enter the release. |
| P1 | DayOA pin | Set source and payload HIOMR-related catalog refs plus contract tests to DayOA `13.0.40` | SUCCESS | feature_implementation | Gate 1 | Codex | Source/payload catalog parity check; `pytest -q tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py tests/test_packaged_defaults.py` passed |  | `default_ref` and all five HIOMR-related command `git_tag`/`validated_version` fields now use `13.0.40`. |
| T1 | DYEC release | Commit, validate, annotated-tag, and push the DayOA-pin milestone as `14.0.10` | SUCCESS | contract_test | Gate 5 | Codex | `cd1d65282f5ca71e9aa17ebccb9485f984d5a75d`; annotated `14.0.10` pushed |  | DayOA `13.0.40` pin milestone is immutable and remote. |
| P2 | DYEC self pin | Point source and payload self/release configuration and contract test to prior `14.0.10` | SUCCESS | config_or_startup_contract | Gate 2 | Codex | Source/payload config parity; `conda run -n DAY-EC python -m pytest -q tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py tests/test_packaged_defaults.py` (45 passed) |  | Both self/release fields and the blessed-tag contract use `14.0.10`; DayOA remains `13.0.40`. |
| T2 | DYEC release | Commit, validate, annotated-tag, and push the self-pin milestone as `14.0.11` | SUCCESS | contract_test | Gate 5 | Codex | `270bb1a83f6e8fcdcb9a5d21663edf185c25c231`; annotated `14.0.11` pushed |  | Release tag is immutable and points to the self-pin commit. |
| V1 | Cross-repo | Verify branches, source/payload pins, remote refs, tag type, and exact tag targets | SUCCESS | contract_test | Gate 5 | Codex | `13.0.40` -> `39405bc3`; `14.0.10` -> `cd1d6528`; `14.0.11` -> `270bb1a8`; all `tag` objects; remote candidate refs match |  | Legacy HG003 and HIOMR2 source branches, DayOA candidate, and DYEC candidate are all pushed and exact. |

## Final report

All rows terminal: yes

Objective complete: yes — release branches, annotated tags, and pin contracts are complete. Live HIOMR2 cluster proof is deliberately deferred to the user's new cluster.
