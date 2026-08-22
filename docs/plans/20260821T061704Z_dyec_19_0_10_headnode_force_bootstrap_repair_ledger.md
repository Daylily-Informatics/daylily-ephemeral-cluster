# DYEC 19.0.10 forced-headnode-bootstrap repair ledger

## Objective

Repair `dyec headnode configure --force` for `pclu-18045` without bypassing
the public DYEC/SSM route, then publish a new DYEC patch release and rerun the
same explicit-state configuration once.

## Gate 0 — recorded 2026-08-21

| Item | Evidence |
| --- | --- |
| Starting release | Annotated `19.0.9`, commit `81450bfe2f728756f556ad21d4e2d275dcfc937d` |
| Release branch | `codex/release-19.0.10-headnode-bootstrap-repair` |
| Local controller | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` |
| Target | `pclu-18045`, `lsmc`, `us-west-2` |
| Credential authority | `/Users/jmajor/.config/daylily/state_pclu-18045_20260818151928.json` |
| Prior failed configure receipt | SSM `b37bf80e-b1ae-4e9f-b043-f4f3172602e8` |
| Failure root cause | The first remote cache-namespace step sourced the broken `DAY-EC` environment and invoked its `aws` executable before the `--force` reset/rebuild step. Its interpreter was absent, so the reset was never reached. |

## Change contract

- Resolve `pcluster describe-cluster` and validate the exact CloudFormation
  stack identity locally in the DYEC controller.
- Derive the cache namespace locally and materialize it remotely without a
  remote `aws` invocation.
- Retain the remote namespace validation, force-reset sequence, and all
  explicit deploy-key/state authority requirements.
- Do not use raw AWS/SSM, direct headnode repair, or a DayOA workflow command.

## Verification and publish status

| Gate | Status | Evidence |
| --- | --- | --- |
| Focused source change | complete | `configure_headnode` now calls `_resolve_headnode_cluster_cache_namespace` before remote steps. |
| Test updates | complete, not executed | Existing headnode configure tests isolate the local authority resolver. |
| Pytest / git tests | intentionally not run | User explicitly requested no pytest or git tests. |
| Functional source commit | complete | `eb6fb3626bad2d2850b5ef2084f3174f35374771` (`Repair forced headnode bootstrap cache setup`). |
| Release evidence commit, branch, and tag | pending | This ledger finalization will be the annotated release commit. |
| Forced configuration rerun | pending | Must use only `dyec headnode configure --state-file … --force`. |

## Terminal record

Pending release publication and one serialized public-CLI configuration attempt.
