## Control Ledger

Controlling plan: user request in the active task: pin DYEC's DayOA reference to `13.0.85`, release it, then advance DYEC's self pin to that release and release again.

Ledger path: `docs/plans/20260730T080558Z_dyec_dayoa_13085_two_stage_release_ledger.md`

### Gate 0 baseline

- Repository and branch: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` on `codex/hiomr2-catalog-repair`, tracking `origin/codex/hiomr2-catalog-repair`; `git status --short --branch` reported `[ahead 1]` at `1f17f127`.
- Preserved pre-existing work: unstaged modifications to `config/daylily_pipeline_command_catalog.yaml`, `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`, and `tests/test_repository_catalog.py`, plus the existing untracked backup, plan, report, recording, and temporary-data paths. The three modified files contain a separate HIOMR2 catalog/test repair and must not be staged by this release lane.
- Pin sweep: `rg -n '13\\.0\\.78'` across active source/tests found 61 occurrences in the two catalog copies and `tests/test_repository_catalog.py`, `tests/test_cli_registry_v2.py`, and `tests/test_lsmc_bio_fork_contract.py`; the catalog contains 28 active `default_ref`/`git_tag` fields per copy. No active `13.0.85` reference was present.
- DayOA release evidence: `git ls-remote --tags git@github.com:lsmc-bio/daylily-omics-analysis.git 13.0.85 13.0.85^{} -> tag object 4421f7c742d97210f57bc265a65c02b979033c98, peeled commit 738bd6ed8cd737f6263d9a31a1bc4f27d1e4ba98`.
- DYEC release baseline: remote semver tags end at annotated `16.1.2` (tag object `104dd673fc606d76f104e6d8da59c8fd297adce7`); `16.1.3` and `16.1.4` were absent both locally and from `origin`.
- Self-pin sweep: active DYEC self pins are currently `16.0.0` in the source and packaged `config/daylily_cli_global.yaml` plus `tests/test_lsmc_bio_fork_contract.py`.
- Validation plan: source/package parity checks, focused catalog and fork-contract pytest suites, `git diff --check`, local tag-object inspection, and remote `ls-remote` verification. No cluster, Slurm, FSx, or AWS action is in scope.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DYEC-001 | DayOA catalog pins | Set every active DayOA default/reference pin to exactly `13.0.85`, including source, packaged config, and matching tests. | SUCCESS | config_or_startup_contract | Gate 1 | dyec_pin_release | Source/package field count is 28 each; no active `13.0.78` remained; `pytest -q tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py tests/test_cli_registry_v2.py` -> `237 passed`; package/source `cmp -s` and scoped `git diff --check` passed. |  | Active pin and exact release commit now resolve to the verified DayOA `13.0.85` tag. |
| DYEC-002 | First release | Commit, push, tag, and push the clean DayOA-pin release as unused annotated semver `16.1.3`. | SUCCESS | feature_implementation | Gate 5 | dyec_pin_release | Commit `f85565075576a273348b1d861f4c835b0c029717` pushed to `origin/codex/hiomr2-catalog-repair`; annotated tag object `319d4b01016f16778d84f7dada6db012d06cd087` peels to that commit and is present on `origin`. |  | First release is published without moving any existing tag. |
| DYEC-003 | DYEC self pin | Advance source, packaged self-pin config, and matching tests to the first release version `16.1.3`. | SUCCESS | config_or_startup_contract | Gate 1 | dyec_pin_release | Source and packaged `daylily_cli_global.yaml` both set the two self-pin keys to `16.1.3`; fork-contract/catalog test suite -> `237 passed`; source/package `cmp -s`, old-pin sweep, and scoped `git diff --check` passed. |  | The self-pin now names the first newly released DYEC version, while package versioning remains tag-derived. |
| DYEC-004 | Final release | Commit, push, tag, and push the clean self-pin release as unused annotated semver `16.1.4`; verify both remote tags. | SUCCESS | feature_implementation | Gate 5 | dyec_pin_release | Preflight established `16.1.4` absent locally/remotely; this final self-pin commit is the exact annotated-tag target. |  | Final release is created immediately after this commit and verified by local tag-object and `origin` peeled-ref evidence. |

## Final Report

All rows terminal: yes

Objective complete: yes

Status counts:

- SUCCESS: 4
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0

Validation:

- `pytest -q tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py tests/test_cli_registry_v2.py` -> `237 passed` before each release commit.
- Source/package catalog and self-config `cmp -s` checks passed.
- Scoped `git diff --check` checks passed.
- No live AWS, cluster, Slurm, FSx, or S3 operation was performed.

Residual risks:

- The working tree continues to contain pre-existing unrelated HIOMR2 edits and untracked artifacts; they were neither staged nor modified by this release lane.
