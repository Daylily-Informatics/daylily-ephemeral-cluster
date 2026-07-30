# DayOA 13.0.94 / DYEC two-stage release train ledger

Created: 2026-07-30T13:42:08Z

## Scope and boundary

Advance the authoritative DYEC DayOA pin and catalog payload from DayOA 13.0.90 to the remotely verified annotated DayOA 13.0.94 tag, cut the next unused annotated DYEC release, then advance every authoritative DYEC self-pin and cut the next unused annotated follow-up release. This ledger covers only local source, tests, commits, pushes, and Git tags. It does not authorize or perform AWS, Slurm, headnode, or DayOA workflow actions.

## Gate 0: inventory freeze

- Canonical checkout intentionally left untouched: /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster on codex/hiomr2-catalog-repair at c55620fc7391c73e53f09801dbfb25b9d1e60383 had 3 tracked modifications and 65 untracked entries when inventoried. The tracked paths were config/daylily_pipeline_command_catalog.yaml, daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml, and tests/test_repository_catalog.py.
- Clean release worktree: /Users/jmajor/projects/lsmc/.codex-worktrees/dyec-13094-release-20260730T134208Z on codex/dyec-13094-release-20260730T134208Z, clean at annotated DYEC 16.1.9, tag object 8173eca6cff9c5c377b5568f9ccfbe39a6629705, peeled commit 812ca1654c2fa4f7fd9be3a22e55d1f99ea6c461.
- Origin remote verification: DayOA 13.0.94 tag object e75ada94f98bd82e1c90f4698fc112514c9f6144, peeled commit 9b8b13173b9cf442158de5cdb69401efcac81651. DYEC candidate tags 16.1.10 and 16.1.11 were absent from origin at Gate 0.
- Pin inventory: 28 source and 28 packaged catalog references to 13.0.90, plus the three active test constants (59 total textual 13.0.90 references). The DayOA highest-release commit assertion was 35b43ce46a52ef9d86d8653edfb87909f4e75764. Source and packaged catalogs were byte-identical; source and packaged self-pin YAML files were byte-identical.
- Baseline validation: source ./activate && python -m pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py tests/test_cli_registry_v2.py::test_root_json_is_global_for_info tests/test_cli_registry_v2.py::test_samples_run_stages_then_launches_catalog_command -q -> 20 passed in 1.28s.

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root cause | Terminal note |
|---|---|---|---|---|---|---|---|---|---|
| REL-001 | Release provenance | Verify remote DayOA 13.0.94 and base DYEC release lineage. | SUCCESS | contract_test | Gate 0 | Codex | Remote annotated tag objects and peeled commits recorded above. |  | Latest remote numeric DYEC release is 16.1.9; exact DayOA target exists. |
| REL-002 | Isolation | Preserve canonical dirty checkout and make a clean release worktree/branch. | SUCCESS | feature_implementation | Gate 0 | Codex | Clean worktree and canonical dirty inventory recorded above. |  | No canonical worktree files were edited. |
| REL-003 | DayOA pin | Update all authoritative DayOA defaults, catalog payload, and test/commit assertions to 13.0.94 / 9b8b13173b9cf442158de5cdb69401efcac81651. | SUCCESS | feature_implementation | Gate 1 | Codex | 60 exact replacements: 28 source catalog pins, 28 packaged catalog pins, three active tag constants, and the highest-release commit assertion. |  | All active DayOA default/pin surfaces now use the requested remote tag and peeled commit; historical validation-run provenance was retained. |
| REL-004 | DayOA validation | Prove catalog/source parity and focused DayOA pin behavior. | SUCCESS | contract_test | Gate 1 | Codex | Focused suite -> 20 passed in 1.24s; no 13.0.90 remains in authoritative surfaces; both catalog copies remain byte-identical; git diff --check passed. |  | Source/payload and test parity are proven before the first release commit. |
| REL-005 | Stage 1 release | Commit, push, and create/push the next unused annotated DYEC tag for REL-003/REL-004. | IN_PROGRESS | feature_implementation | Gate 1 | Codex | Candidate is recomputed and rechecked on origin only after the clean stage-one commit exists. |  |  |
| REL-006 | DYEC self-pin | Update every authoritative self-pin surface to the first new DYEC tag. | OPEN | feature_implementation | Gate 1 | Codex | Two global YAML copies and fork-contract test identified. |  |  |
| REL-007 | Self-pin validation | Prove source/payload parity and focused self-pin behavior. | OPEN | contract_test | Gate 1 | Codex | Focused suite and exact-reference sweep pending after REL-006. |  |  |
| REL-008 | Stage 2 release | Commit, push, and create/push the next unused annotated follow-up DYEC tag. | OPEN | feature_implementation | Gate 1 | Codex | Candidate 16.1.11 absent from origin at Gate 0. |  |  |
| REL-009 | Final proof | Verify branch, tag objects, peeled remote commits, clean release state, and terminal ledger report. | OPEN | contract_test | Gate 5 | Codex | Pending after both release tags are pushed. |  |  |

## Current status

All rows terminal: no

Objective complete: no

Status counts:

- SUCCESS: 4
- IN_PROGRESS: 1
- OPEN: 4
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0
