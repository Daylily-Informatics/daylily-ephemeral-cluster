# DayOA 2.0.44 -> DYEC 5.1.33 Release Train Ledger

Created: 2026-06-03T16:32:50Z

## Objective

Publish the dirty DayOA CLI wrapper/link work as a new DayOA version, then update DYEC to pin that DayOA version across package and command-catalog surfaces before publishing a new DYEC tag.

## Gate 0 Inventory

- DayOA repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`
- DayOA branch: `codex/dayoa-bclconvert-tile-shards-20260601`
- DayOA prior tag: `2.0.43`
- DayOA release commit: `b0a25fc0bb414120f874a61f5bc787883062888f`
- DayOA release tag: `2.0.44`
- DYEC repo: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster`
- DYEC branch: `codex/dyec515-full-catalog-20260531`
- DYEC prior tag: `5.1.31`
- DYEC intermediate tag: `5.1.32`
- DYEC final tag: `5.1.33`
- DYEC `environment.yaml` check: no DayOA package pin present; DayOA package pin is in `pyproject.toml`.

## Ledger

| ID | Task | Evidence | Status |
| --- | --- | --- | --- |
| DAYOA-001 | Validate DayOA wrapper/link changes | `pytest -q tests/test_shell_wrapper_contracts.py` -> 16 passed; `bash tests/test_cli_commands.sh` -> 28 passed | done |
| DAYOA-002 | Commit and push DayOA dirty work | Commit `b0a25fc0bb414120f874a61f5bc787883062888f` pushed to `origin/codex/dayoa-bclconvert-tile-shards-20260601` | done |
| DAYOA-003 | Publish DayOA tag | Annotated tag `2.0.44` pushed; tag peels to `b0a25fc0bb414120f874a61f5bc787883062888f` | done |
| DYEC-001 | Update DYEC DayOA package pin | `pyproject.toml` changed from `daylily-omics-analysis==2.0.42` to `==2.0.44` | done |
| DYEC-002 | Update DYEC command catalog pins | `config/daylily_pipeline_command_catalog.yaml` and packaged payload copy changed from DayOA `2.0.42` to `2.0.44` for `default_ref`, `validated_version`, and `git_tag` | done |
| DYEC-003 | Update DYEC tests/current docs for catalog pin | Current docs and catalog tests updated from `2.0.42` to `2.0.44`; historical `docs/plans/` evidence left intact | done |
| DYEC-004 | Validate DYEC pin updates | `source ./activate && pytest -q tests/test_repository_catalog.py tests/test_cli_registry_v2.py tests/test_day_clone.py tests/test_packaged_defaults.py tests/test_resources_extraction.py` -> 136 passed | done |
| DYEC-005 | Commit, push, tag DYEC | Intermediate tag `5.1.32` was pushed on commit `b370b13dcfd957a05c04d28280c5cf0044825987`; late RUN-003 mount verification evidence appeared afterward, so the final no-dirty release commit is intended to be tagged as `5.1.33` with message `forkback candidate n3!` | done |

## Notes

- The DayOA version is derived from the annotated semver tag through `setuptools_scm`; no DayOA version constant was edited.
- Existing historical validation-run `dayoa_tag` / `dayoa_commit` records in the command catalogs were preserved because they describe prior validation provenance, not the current release pin.
- Pushed tags are not moved. Because `5.1.32` was already pushed before `docs/plans/20260603T151652Z_RUN-003_mount_verify.json` appeared, this release train advances to `5.1.33` for the final clean DYEC commit.
