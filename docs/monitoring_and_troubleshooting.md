# Monitoring And Troubleshooting

Use this when a current DayEC cluster exists but behavior is unclear or failing.

## 1. Local Runtime

```bash
source ./activate
dyec runtime status
dyec runtime check
dyec runtime explain
dyec info
dyec -v --json info
```

If the local runtime points at the wrong editable checkout, refresh it:

```bash
python -m pip install -e .
```

## 2. Cluster State

```bash
dyec cluster list --profile "$AWS_PROFILE" --region "$REGION" --verbose
pcluster describe-cluster --region "$REGION" --cluster-name "$CLUSTER_NAME"
```

The trailing `cluster list --verbose` expands that command's table columns. Use
root `dyec -v` before a subcommand when the project-local context diagnostic is
also needed.

Infrastructure existence is not the final readiness point. DayEC readiness is when `dyec create` has returned after headnode configuration and validation.

## 3. Headnode Access

```bash
dyec headnode connect \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

Expected:

```bash
whoami
pwd
command -v day-clone
day-clone --list
```

`whoami` must match the resolved remote user: normally `ubuntu` for
Ubuntu/Intel DayOA headnodes, or `ec2-user` for DRAGEN/RHEL-style headnodes.

If the shell is incomplete:

```bash
dyec headnode configure \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

If DayOA `dy-r` reports `No such command 'analysis'`, the headnode DYEC command surface is stale. Re-run `dyec headnode configure --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"` from the activated local DYEC checkout, reconnect, and verify `dyec analysis --help` before any workflow write.

## 4. Reference DRA

The cluster template creates `/fsx/references` from `reference_s3_uri`. If reference files are missing, check:

```bash
dyec headnode connect --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
ls -lah /fsx/references
```

Bootstrap waits for required reference entries and hard-fails if the DRA never becomes visible.

## 5. Run DRA Mounts

List and verify run mounts:

```bash
dyec --json mounts list --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec --json mounts verify --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME" --mount-id RUN123
```

Common failures:

- source S3 prefix overlaps an active DRA
- FSx path overlaps an active DRA
- filesystem was created with incompatible repository configuration
- headnode path under `/fsx/run_dir_mounts/<mount_id>` is not usable

## 6. Workflow State

```bash
dyec --json workflow status \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --session <session>

dyec workflow logs \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --session <session> \
  --stream snakemake \
  --lines 100
```

Interpret the combined status as follows:

- `RUNNING`: the exact controller PID is live and attributed to the expected
  checkout/tmux tree. Slurm `CONFIGURING` and `RUNNING` records are ongoing
  work.
- `SUCCEEDED`: the exact DYEC launch receipt is complete with exit code `0`.
- `FAILED`: the exact receipt has a nonzero exit code, or a dead attributed
  manual invocation has an anchored high-signal Snakemake terminal marker.
- `UNKNOWN`: no terminal receipt and no live attributed controller or
  high-signal terminal failure. Queue emptiness does not change this state.

The current master log is selected only when exactly one matching file is open
by the controller/descendant process tree, or when an exact invocation log was
persisted in the DYEC receipt. Multiple candidates are reported as ambiguous.
Generic `ERROR` strings, printed shell command bodies, stale tmux-pane RC text,
and the status inspection command's RC are never treated as workflow RCs.

Manual recovery syntax is explicit and provider-neutral:

```bash
dyec --json workflow status \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME" \
  --repo-path /fsx/analysis_results/<owner>/<analysis-id>/daylily-omics-analysis \
  --controller-pid <pid> \
  --session <exact-tmux-session>
```

If exact open-file correlation is unavailable, add
`--snakemake-log <repo-path>/.snakemake/log/<exact-name>.snakemake.log` to status
or `workflow logs --stream snakemake`. DYEC fails clearly on a missing,
out-of-root, or ambiguous log and never guesses the newest one. Manual runs
without a matching DYEC status receipt cannot prove success or a terminal RC.
The Snakemake stream attributes and reads the exact tail in one SSM probe and
validates its byte count and SHA-256 after local decompression. If the tail is
too large for bounded SSM output, retry with fewer `--lines`; DYEC does not
silently truncate or issue an unattributed second read.

For recovery shells, never capture the controller as `dy-r ... | tee ...` when
an immediate RC receipt matters. Slurm polling or lock helpers can inherit the
pipe, leaving `tee` alive after Snakemake prints its return code. Redirect
`dy-r` directly to a regular file, capture `$?` immediately, and follow the log
from a separate process. DYEC's generated launcher applies this contract and
atomically stores `workflow_exit_code`; generic or printed `RETURN CODE` text is
still not terminal evidence.

On the headnode:

```bash
tmux ls
tmux attach -t <session>
squeue
sacct | tail -n 20
```

Run-state files live under the resolved remote user's
`$HOME/daylily-runs/<session>/`.

## 7. Export Failures

Export reads from one completed analysis directory and writes through an explicit temporary output DRA.

```bash
dyec export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --source-path "/fsx/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID" \
  --destination-s3-uri "$EXPORT_S3_URI" \
  --output-dir "$EXPORT_DIR"

cat "$EXPORT_DIR/fsx_export.yaml"
```

If the export failed, `fsx_export.yaml` records the phase, failure message,
source path, destination S3 URI, task id when available, detach state, and the
explicit `fsx_root` to `s3_root` mapping when it could be derived. The
`dyec export` surface is provider-neutral; it does not accept metadata-service
URL or token options.

## 8. Delete Checks

Before deletion:

- run mounts that are no longer needed should be detached
- selected results should be exported
- `fsx_export.yaml` should show `status: success` and `detached: true`

```bash
dyec delete --dry-run --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec delete --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
```

## 9. Escalation Order

1. local runtime checks
2. `dyec preflight --debug`
3. `dyec cluster list` and `pcluster describe-cluster`
4. Session Manager document verification
5. run mount list/verify
6. workflow `status.json` and `tmux.log`
7. `fsx_export.yaml`
