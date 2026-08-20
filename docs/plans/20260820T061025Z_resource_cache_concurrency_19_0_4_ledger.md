# DYEC 19.0.4 Resource Cache Concurrency Ledger

## Control Ledger

Controlling request: fix the concurrent local versioned-resource extraction race observed while two `dyec headnode configure --force` commands used `~/.config/daylily/resources/19.0.3`, release the fix as `19.0.4`, update the local DYEC checkout/environment, and complete both requested headnode configurations.

Ledger path: `docs/plans/20260820T061025Z_resource_cache_concurrency_19_0_4_ledger.md`

Gate 0 baseline:

- Release worktree: `/Users/jmajor/.codex-worktrees/dyec-resource-cache-concurrency`, branch `codex/resource-cache-concurrency`, clean at annotated tag `19.0.3` / commit `d4a6380cf5f95617ee5a1c27db4e9217404d58ec`.
- Primary checkout: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, detached at `19.0.3`; existing untracked analysis and ledger artifacts belong to the user and will remain untouched.
- Remote occupancy checks: no `origin/codex/resource-cache-concurrency` branch and no `19.0.4` tag existed at Gate 0.
- Source sweep: `rg -n "mkdtemp|TemporaryDirectory|os\\.replace|Path\\.replace|rename\\(|resources_root|resource_path|\\.tmp-" daylily_ec/resources daylily_ec tests` identified `daylily_ec/resources/__init__.py` as the failing version-cache publisher and `tests/test_resources_extraction.py` as its focused test surface.
- Reproduced live failure: concurrent local `19.0.3` configure startup raised `[Errno 66] Directory not empty` while renaming a sibling `19.0.3.tmp-*` directory to `~/.config/daylily/resources/19.0.3`; the failing `pclu-18045` process stopped before remote headnode mutation.
- Validation boundary: by explicit user direction, do not run pytest or Git test suites. Run only a focused local concurrent extraction smoke check and release/provenance/runtime checks.
- Live limits: no Slurm intervention or destructive infrastructure changes. `--force` is explicitly authorized for the two already-running clusters, with DYEC's active-controller guard retained.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| RC-001 | DYEC resources | Serialize one version cache's validation, refresh, extraction, and atomic publish across local processes; recheck after lock acquisition | SUCCESS | feature_implementation | Gate 2 | orchestrator | `daylily_ec/resources/__init__.py` now takes an exclusive `flock` on stable sibling `.<version>.lock` before the cache recheck and holds it through atomic publication |  | Concurrent callers wait, then reuse the completed cache instead of deleting or renaming over another process's work |
| RC-002 | DYEC resources | Preserve strict cache validation and cleanup without accepting partial or stale output | SUCCESS | legitimate_safety_handling | Gate 4 | orchestrator | Existing marker/content refresh checks, destination replacement, temp-directory cleanup, atomic rename, and final `_validate_resources_dir` remain inside the serialized critical section |  | No partial-cache acceptance, retry fallback, or alternate cache path was introduced |
| RC-003 | Validation | Exercise concurrent cold-cache and reuse behavior without invoking pytest or Git tests | SUCCESS | contract_test | Gate 5 | orchestrator | Corrected standalone smoke: 8 simultaneous cold callers, 1 unique writer process, 8 successful paths, complete marker present, no temp dirs; 8 warm callers added 0 writers; result `PASS`. Regression test added but not invoked. | First smoke instrumentation wrapped recursive `shutil.copytree`, so one writer emitted multiple same-PID audit rows | The corrected unique-writer assertion passed; no pytest or Git test suite was run, per user direction |
| REL-001 | DYEC catalog/release | Preserve `19.0.3` as the immutable `current` catalog because `19.0.4` is a code-only bootstrap patch, matching the prior `19.0.2` code-only release convention | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Catalogs have no diff from `19.0.3`, remain byte-identical, and share SHA-256 `b98bfe4f26aa7ee49ed09001f82af3b32ab2106a06ee8c77b752e6a90d3ae67d` |  | `19.0.4` changes bootstrap code only; command definitions and DayOA `16.0.3` pins remain untouched |
| REL-002 | DYEC release | Commit cleanly, push feature branch, create and push annotated non-v tag `19.0.4`, and verify tag provenance | OPEN | feature_implementation | Gate 5 | orchestrator | Remote branch/tag unoccupied at Gate 0 |  |  |
| LOCAL-001 | Local DYEC | Update `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` and its `DAY-EC` environment to exact `19.0.4` while preserving user artifacts | OPEN | config_or_startup_contract | Gate 2 | orchestrator | Local update pending |  |  |
| LIVE-001 | `bjuice-v09` | Finish/verify the already-started forced configure, then ensure the final installed DYEC version is `19.0.4` | IN_PROGRESS | config_or_startup_contract | Gate 2 | orchestrator | Preflight DYEC `18.0.58`; forced `19.0.3` configure completed; post-check DYEC `19.0.3`, authoritative controllers `0`, Slurm jobs `0`; final `19.0.4` configure pending |  |  |
| LIVE-002 | `pclu-18045` | Run forced configure sequentially and verify the final installed DYEC version is `19.0.4` | OPEN | config_or_startup_contract | Gate 2 | orchestrator | Preflight DYEC `19.0.1`, controllers `0`, Slurm jobs `0`; first local launch failed before remote mutation |  |  |
