# DYEC 5.0.23 Dewey Export Link Release Ledger

Control time: 2026-05-28T20:15:15Z

## Summary

Release DYEC `5.0.23` so Ursa run-directory workers can invoke released DAY-EC CLI surfaces for export-time Dewey registration links.

This release includes:

- CLI options on `dyec export`, `dyec workflow launch`, and catalog-backed `dyec samples run` for exported analysis-directory Dewey external-object linking.
- Headnode auto-export propagation of those Dewey link options.
- Export registration that creates a Dewey external object for the exported DayOA analysis directory, creates a Dewey external object for the Ursa analysis job EUID, and creates Dewey external-object relations to the DayOA analysis artifact set and originating run artifact.
- Interactive S3 role candidate discovery on the cluster-create path, while retaining hard preflight validation for selected S3 role URIs.
- DYEC self pins updated to `5.0.23` in source and packaged global config.

## Gates

| Gate | Requirement | Status | Evidence |
|---|---|---|---|
| 0 | Confirm release base and next tag | SUCCESS | Highest non-`v` tag before release was `5.0.22`; branch is a fast-forward of `origin/main`. |
| 1 | Add CLI/export Dewey link support | SUCCESS | `daylily_ec/cli.py`, `daylily_ec/repositories.py`, `daylily_ec/workflow/export_data.py`, `daylily_ec/workflow/dewey_registration.py`, and headnode script updated. |
| 2 | Preserve cluster-create S3 role validation while adding operator discovery | SUCCESS | `daylily_ec/aws/s3.py` and `daylily_ec/workflow/create_cluster.py` updated; validation remains preflight-gated. |
| 3 | Validate | SUCCESS | `cmp -s config/daylily_cli_global.yaml daylily_ec/resources/payload/config/daylily_cli_global.yaml`; `python -m pytest -q tests/test_export.py tests/test_cli_registry_v2.py tests/test_repository_catalog.py tests/test_script_entrypoints.py tests/test_s3.py tests/test_workflow.py` -> 257 passed; `ruff check ...` -> passed; `git diff --check` -> passed. |
| 4 | Commit, push, tag, publish package | OPEN | Pending. |

## Notes

- Existing untracked `docs/end_to_end_5.0.22.md` was not swept into this release.
- No destructive AWS action is included in this release.
