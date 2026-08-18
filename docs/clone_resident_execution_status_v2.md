# Clone-resident execution status v2

DYEC 18.0.29 consumes DayOA's canonical execution record only from:

```text
<analysis-root>/daylily-omics-analysis/status.json
```

There is no supported reader, migration, or fallback for the retired
`/home/ubuntu/daylily-runs/<session>/status.json` receipt.

## Controller attribution

The controller writes `controller_target.json` under its run directory using
`dyec.controller_target.v2`. The target identifies the exact clone, analysis
root, controller session/PID, and `status_attempt_id` created after cloning.
Every launched-status/log/SSM reader uses that target to resolve the canonical
clone path and select exactly that append-only v2 attempt. It does not select a
latest attempt by guesswork.

Missing or malformed clone-root status, a mismatched analysis identity, an
unsupported schema, or a target attempt that is absent all fail with a clear
clone-resident v2 error. Historic home-run records are rejected explicitly.

## Status JSON results

Workflow observability, catalog status, SSM E2E status, and analysis status
expose three non-interchangeable fields:

```text
controller_exit_code
day_run_exit_code
snakemake_exit_code
```

A zero controller code alone is not workflow success. A terminal controller
attempt is accepted only when its DayOA wrapper and Snakemake child results are
also present and zero. This preserves a visible divergence such as
`snakemake_exit_code=0` with `day_run_exit_code=7`.

The controller finalizes its own result only after the DayOA return and DYEC's
post-run immutable-source/DAG checks. A failure before `day_run` starts is
retained as a controller attempt with both child states `not_started`.

## Pinned checkout runtime artifacts

The pinned-source verifier allows only these status-v2 runtime artifacts in a
DayOA clone:

```text
status.json
.dyec/status.json.lock
.dyec/status.json.tmp-*
```

It does not allow arbitrary untracked clone-root paths.

## Export evidence acceptance

Full analysis exports remain unchanged by default. To require evidence for a
new v2 analysis, use either `dyec export` or `dyec exports transfer` with:

```text
--require-clone-status-v2-evidence
```

After the FSx export task succeeds, DYEC reads exactly:

```text
<destination>/daylily-omics-analysis/status.json
```

It validates the strict `daylily.analysis_status.v2` record against the source
clone identity and requires at least one retained attempt. The export receipt
then includes `clone_status_v2_evidence` with the S3 URI, schema version,
attempt count, and latest attempt ID. Evidence failure prevents an optional
FSx delete-on-success path; it does not mutate S3 or retry the DRA.

The option deliberately rejects nested exports because a nested export cannot
prove that it retained the clone-root status file. Historical exports remain
available without the option.
