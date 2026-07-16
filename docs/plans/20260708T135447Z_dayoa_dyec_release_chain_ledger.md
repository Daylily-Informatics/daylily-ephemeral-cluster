# DayOA And DYEC Jem-Dev Release Chain Ledger

Controlling request: push the DayOA `jem-dev` release, tag a new DayOA version, update DYEC DayOA pins in `pyproject.toml` and config surfaces, commit/push/tag DYEC on `jem-dev`, then update DYEC self-pins to the new DYEC tag and commit/push/tag again.

Ledger path: `docs/plans/20260708T135447Z_dayoa_dyec_release_chain_ledger.md`

## Gate 0 Baseline

- Timestamp: `20260708T135447Z`
- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DayOA branch/status: `jem-dev`, clean, aligned to `origin/jem-dev`.
- DayOA HEAD: `e2d7793`, already tagged `10.0.69`; latest numeric DayOA tag before this run: `10.0.69`.
- DayOA requested release decision: no dirty DayOA files exist in the canonical checkout, so do not create an artificial file commit; tag the clean `jem-dev` HEAD as `10.0.70` and push `jem-dev` plus the tag.
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DYEC branch/status: `jem-dev`, aligned to `origin/jem-dev`, dirty files before this run: `README.md`, `daylily_ec/cli.py`, `daylily_ec/tests_runner.py`, `docs/cli_reference.md`, `tests/test_tests_runner.py`.
- DYEC HEAD: `dd44741f`, tagged `10.0.116`; latest numeric DYEC tag before this run: `10.0.116`.
- DYEC current DayOA pin: `10.0.69` in `pyproject.toml`, `config/daylily_pipeline_command_catalog.yaml`, `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`, and `config/dragen_fix5_repo_overrides.txt`.
- DYEC current self-pin: `10.0.115` in `config/daylily_cli_global.yaml`, `daylily_ec/resources/payload/config/daylily_cli_global.yaml`, and `config/dragen_fix5_repo_overrides.txt`.
- Intended release sequence:
  - DayOA tag: `10.0.70`.
  - DYEC first tag after DayOA pin plus dirty command-catalog selector changes: `10.0.117`.
  - DYEC second tag after self-pin update to `10.0.117`: `10.0.118`.
- Remote preflight: `git ls-remote --tags origin 10.0.70`, `10.0.117`, and `10.0.118` returned no matches before tag creation.
- Safety boundaries: no force push, no tag movement, non-`v` annotated tags only.

## Control Ledger

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| GATE0-001 | Release baseline | Record current branches, dirty state, existing tags, intended versions, and safety boundaries. | SUCCESS | live_validation | Gate 0 | Codex | Gate 0 Baseline above. |  | Baseline captured before live tag or push operations. |
| DAYOA-001 | DayOA | Push `jem-dev`, create annotated tag `10.0.70`, push tag. | SUCCESS | live_release | Gate 1 | Codex | `git push origin jem-dev` -> everything up-to-date; `git tag -a 10.0.70 -m "Release 10.0.70"`; `git cat-file -t 10.0.70` -> `tag`; `git show --no-patch 10.0.70^{}` -> `e2d7793 Refresh DayOA current-state documentation`; `git push origin 10.0.70` -> new tag pushed. |  | DayOA `10.0.70` is an annotated tag on clean `jem-dev` HEAD; no DayOA file commit was created because the canonical checkout was clean. |
| DYEC-PIN-001 | DYEC | Update DayOA pins from `10.0.69` to `10.0.70` in `pyproject.toml` and config payloads. | SUCCESS | live_release | Gate 2 | Codex | Updated `pyproject.toml`, `config/daylily_pipeline_command_catalog.yaml`, `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`, `config/dragen_fix5_repo_overrides.txt`, and test blessed-tag constants; `rg` verified active DayOA pins now point to `10.0.70`. |  | DayOA pins and matching contract tests now reference DayOA `10.0.70`; DYEC self-pin remains `10.0.115` for the first DYEC release. |
| DYEC-RELEASE-001 | DYEC | Commit existing DYEC dirty command-catalog selector changes plus DayOA pin update, push `jem-dev`, tag and push `10.0.117`. | SUCCESS | live_release | Gate 3 | Codex | Validation before commit: `pytest tests/test_tests_runner.py tests/test_repository_catalog.py tests/test_lsmc_bio_fork_contract.py -q` -> `42 passed`; `pytest tests/test_cli_registry_v2.py -q` -> `144 passed`; `ruff check .` blocked by pre-existing lint in historical `docs/` and `docs/plans/` scripts unrelated to changed release surfaces; commit `5c330ef2 Add released command catalog selectors and pin DayOA 10.0.70`; `git push origin jem-dev` accepted with GitHub PR-rule bypass notice; `git cat-file -t 10.0.117` -> `tag`; `git push origin 10.0.117` -> new tag pushed. |  | DYEC `jem-dev` and annotated tag `10.0.117` are pushed. |
| DYEC-SELFPIN-001 | DYEC | Update DYEC self-pins to `10.0.117`, commit, push `jem-dev`, tag and push `10.0.118`. | OPEN | live_release | Gate 4 | Codex | Pending. |  |  |
| FINAL-001 | Release report | Verify pushed tags and report final tag versions. | OPEN | live_validation | Gate 5 | Codex | Pending. |  |  |
