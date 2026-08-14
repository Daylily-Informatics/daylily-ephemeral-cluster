# Daylily Ephemeral Cluster

Daylily Ephemeral Cluster, usually called DYEC or DayEC, is the CLI control plane for short-lived AWS ParallelCluster bioinformatics work. It creates and configures clusters, mounts sequencing-run data into FSx, launches pinned workflow repositories on the headnode, monitors exact analysis roots, moves files between local and headnode storage, and exports finished results to S3 with receipts.

DYEC is not an identity service and not a workflow engine. It does not call Dayhoff, Ursa, Bloom, TapDB, Dewey, or a metadata service. It consumes explicit local configuration, explicit manifests, explicit S3 paths, and explicit command-catalog entries. DayOA owns its workflow rules and `dy-r` execution. DYEC owns cluster/headnode orchestration and the launch/export envelope.

## Current operator model

Most work follows this shape:

```bash
cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate

export AWS_PROFILE=lsmc
export REGION=us-west-2
export CLUSTER=ifx-p2-1000-120-0715
export STAGING_S3_URI=s3://<bucket>/<temporary-dyec-payload-prefix>/
export ANALYSIS_ID=<analysis-id>
```

Inspect the installed CLI before mutating anything:

```bash
dyec --json version
dyec --help
dyec agent guidance
dyec --json catalog list
```

Use `--cluster` for DYEC commands. Keep `--cluster-name` for tools such as `pcluster` that require that spelling.

## Safety contracts

- Use `dyec`; do not launch DayOA by invoking raw `snakemake`.
- New DayOA checkouts must be explicit-tag checkouts.
- A DYEC controller never mutates a pinned DayOA release: no runtime rule/script/environment/config patches, source overlays, or generated helpers in the checkout. It verifies the selected ref is clean before dispatch and after the workflow returns. Missing behavior is a hard error that must be fixed and released in DayOA, never repaired on the headnode.
- Headnode work uses a cluster-appropriate remote user selected by platform: Ubuntu/Intel DayOA headnodes use `ubuntu`; DRAGEN/RHEL-style headnodes use `ec2-user`.
- DYEC-created headnode shells must be bash login/interactive contexts and source `~/.bashrc`; workflow controllers still run in persistent `tmux` panes.
- DYEC CLI launch helpers create the supported headnode controller for you; they do not require an interactive SSM session for standard catalog launches.
- Missing files, missing credentials, unsafe identity fields, malformed manifests, unexpected legacy input shapes, and insufficient staging permissions fail hard.
- S3 relay prefixes for upload/download and staged workflow launch must be readable/writable by both the local operator credentials and the headnode instance role.
- `/fsx/analysis_results/**` workflow writes, unlocks, deletes, restarts, and kills require analysis-root write-lock ownership.
- Headnode inspection commands are supported; Slurm/node administration is not implied by inspection.

## Command groups

Run `dyec --help` for the live list. Current major groups are:

| Group | Purpose |
|---|---|
| `version`, `info`, `runtime`, `env`, `resources-dir`, `state` | Local/runtime introspection. |
| `preflight`, `create`, `drift`, `delete` | Cluster lifecycle. |
| `cluster`, `cluster-info` | ParallelCluster inspection and tag helpers. |
| `headnode` | SSM-backed headnode connection, command execution, file transfer, and observability. |
| `mounts`, `mount` | FSx run-directory Data Repository Associations. |
| `workflow` | Standard DayOA/workflow clone, launch, status, logs, benchmark collection, and stop helpers. |
| `catalog` | Command-catalog discovery, exact command rendering, and quick launch. |
| `samples` | Older sample staging/launch helpers for catalog contracts that still use them. |
| `identities` | Provider-neutral local manifest validation and receipt handling; no network service calls. |
| `analysis` | Analysis-root visit logging, status reporting, lock ownership, and guarded commands. |
| `command` | Command-family progress views such as HIOMRS sample stats and DAG download. |
| `export`, `exports` | FSx analysis export through explicit S3 receipts. |
| `pricing`, `cost-centers`, `aws`, `slurm-accounting` | Cost, quota, AWS readiness, and accounting support. |
| `tests` | Local pytest and catalog validation helpers. |

Detailed examples live in [docs/cli_reference.md](docs/cli_reference.md).

## Quick cluster and queue checks

Use the aggregate read-only view to see which clusters are ready and how many
Slurm jobs each has. A provisioning or teardown cluster is shown as
`CLUSTER_NOT_READY`, not as an idle queue.

```bash
dyec cluster jobs --profile "$AWS_PROFILE" --region "$REGION"
```

For the exact job list on one cluster, use the drill-down command:

```bash
dyec headnode jobs --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
```

## CLI-first catalog launch

Catalog launch is the preferred path for known DayOA commands because it renders the exact `dyec workflow launch` command before it starts anything. Use `--project` for DayOA initialization and `--cost-center` for the explicit Slurm submission account; DYEC validates the latter without inferring one.

Render first:

```bash
dyec --json catalog render hybrid_ilmn_ont_hiomr_kitchensink \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$CLUSTER" \
  --manifest-dir ./config \
  --payload-staging-s3-uri "$STAGING_S3_URI" \
  --session-name "${ANALYSIS_ID}-dryrun" \
  --project RnD \
  --cost-center "$COST_CENTER" \
  --dry-run
```

Launch the rendered dry run:

```bash
dyec --json catalog launch hybrid_ilmn_ont_hiomr_kitchensink \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$CLUSTER" \
  --manifest-dir ./config \
  --payload-staging-s3-uri "$STAGING_S3_URI" \
  --session-name "${ANALYSIS_ID}-dryrun" \
  --project RnD \
  --dry-run
```

If the dry-run plan is bounded and correct, launch the same catalog command without `--dry-run` and use a new session name:

```bash
dyec --json catalog launch hybrid_ilmn_ont_hiomr_kitchensink \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$CLUSTER" \
  --manifest-dir ./config \
  --payload-staging-s3-uri "$STAGING_S3_URI" \
  --session-name "$ANALYSIS_ID" \
  --project RnD \
  --cost-center "$COST_CENTER"
```

For DayOA runtime config, pass explicit `key=value` overrides. DYEC appends them to the `dy-r ... --config` section and does not reinterpret their workflow-specific meaning:

```bash
dyec --json catalog render hybrid_ilmn_ont_hiomr_kitchensink \
  --analysis-id hg003-hg004-ds025-ont0to6 \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --manifest-dir ./config \
  --payload-staging-s3-uri "$STAGING_S3_URI" \
  --dry-run \
  --dy-config use_fq_data_starting_hrs=0 \
  --dy-config use_fq_data_up_to_hrs=6 \
  --dy-config global_sr_subsample_pct=0.25 \
  --dy-config global_ont_subsample_pct=0.25
```

Large local payloads are staged through S3 with `--payload-staging-s3-uri`. DYEC uploads a tarball containing input manifests, a payload manifest, and the controller launch script. The headnode downloads and expands that tarball into the workflow run directory, starts the tmux controller, and then saves the exact executed script under `<analysis-root>/bin/dyec-controller-launch.sh` after `day-clone` creates the analysis root. This avoids SSM document-size limits without pre-creating the analysis root.

### Current and released command shapes

Catalog version 6 uses `dyec_builds.current` for every command-catalog action
unless `--dyec-version` explicitly selects an immutable numeric release
snapshot. When a new DYEC release is created, copy `current` to that release's
numeric key before changing `current`; never edit an existing numeric snapshot:

```bash
dyec --json catalog list --type prod
dyec --json catalog list --dyec-version 16.1.81 --type prod
dyec --json catalog render <command-id> --dyec-version 16.1.81 ...
```

A build may also declare one-hop, same-build aliases. An alias inherits one
direct command, applies typed metadata overrides, and either extends its DayOA
targets/config or supplies a complete replacement of `targets`, `dy_command`,
and `dryrun_dy_command`. Alias chains, cycles, cross-build references, missing
bases, duplicate IDs, mixed extension/replacement modes, and partial command
replacements fail catalog validation. Existing catalog APIs return aliases as
fully resolved `AnalysisCommand` records.

Each command may declare an explicit `validation_evidence_s3_uri_prefix`. The
prefix must contain `command_registry.json` and `summary.json` from a successful
`dyec tests command-catalog` run. Compare it read-only with:

```bash
dyec --json catalog validation-compare <command-id> \
  --dyec-version 16.1.81 --profile "$AWS_PROFILE" --region "$REGION"
```

The comparison fails hard when no prefix is declared, the receipts are missing,
the captured DayOA pin differs, or the recorded command phase did not succeed.

## Workflow launch without the catalog shortcut

Use `dyec workflow launch` when you already know the exact DayOA command string or are launching a non-catalog repository command:

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$CLUSTER" \
  --git-tag 13.0.20 \
  --manifest-dir ./config \
  --payload-staging-s3-uri "$STAGING_S3_URI" \
  --session-name "$ANALYSIS_ID" \
  --project RnD \
  --cost-center "$COST_CENTER" \
  --dy-command "dy-r produce_sentdhiomr_snv_vcf produce_sentdhiomr_sv produce_sentdhiomr_cnv -j 100 -p -T 0 --rerun-triggers mtime --rerun-incomplete"
```

Dry-run first by using the DayOA wrapper command’s dry-run flag inside `--dy-command`, or by launching through `dyec catalog ... --dry-run` when the command is catalog-backed.

## Six-manifest DayOA inputs

Current DayOA sample-analysis launches use exactly six manifest files:

```text
specimens.tsv
samples.tsv
libraries.tsv
sequencing_inputs.tsv
analysis_units.tsv
analysis_unit_inputs.tsv
```

Validate them locally before launch:

```bash
dyec --json identities validate --manifest-dir ./config
dyec --json identities status --manifest-dir ./config
```

The identity commands are local and provider-neutral. They never create or resolve production identities. EUID fields may be blank for ordinary analysis. Test-only EUID-like values must use the reserved `Z-` prefix and are not valid customer-release identities.

## Bjuice prevalence manifest helper

`dyec catalog config-bjuice-preval` builds a six-manifest directory from reviewed Bjuice evidence files. It is deliberately specific to that reviewed evidence contract; it is not a general identity resolver.

```bash
dyec --json catalog config-bjuice-preval \
  --sample HG003 \
  --sample HG004 \
  --output-dir ./config-hg003-hg004 \
  --source-manifest-json /path/to/source_manifest_resolved.json \
  --run-evidence-json /path/to/run_evidence_v2.json \
  --library-run-matrix-tsv /path/to/bjuice_preval_library_run_matrix.tsv \
  --sample-metadata-tsv /path/to/samples.tsv \
  --legacy-units-tsv /path/to/units.tsv \
  --sr-subsample-pct 0.25 \
  --ont-subsample-pct 0.25 \
  --profile "$AWS_PROFILE" \
  --region "$REGION"
```

The helper writes the six manifest TSVs plus `bjuice_preval_config_receipt.json`, validates the manifest set, and records file hashes. It fails if reviewed sample metadata, legacy unit metadata, S3 listings, or expected ILMN/ONT source groups are absent or ambiguous.

## Bjuice v2 HG002 full-prevalence multi-AU helper

`dyec catalog config-bjuice-v2-hg002-multi-au` is a separate, fixed contract for the seven HG002 analysis units `p5xp5`, `1x1`, `3x3`, `5x5`, `10x5`, `15x5`, and `15x10`. It accepts one direct Illumina coverage denominator and requires a matching terminal receipt; it never derives coverage from total or hybrid evidence.

```bash
dyec --json catalog config-bjuice-v2-hg002-multi-au \
  --output-dir ./config-hg002-bjuice-v2 \
  --source-manifest-json /path/to/source_manifest_resolved.json \
  --run-evidence-json /path/to/run_evidence_v2.json \
  --library-run-matrix-tsv /path/to/bjuice_preval_library_run_matrix.tsv \
  --sample-metadata-tsv /path/to/samples.tsv \
  --legacy-units-tsv /path/to/units.tsv \
  --direct-ilmn-coverage-x "$C_ILMN" \
  --direct-ilmn-coverage-evidence /path/to/direct_ilmn_terminal_receipt.json \
  --profile "$AWS_PROFILE" \
  --region "$REGION"
```

The receipt must use `dyec.bjuice_v2_direct_ilmn_coverage_receipt.v1`, identify `HG002`, have terminal status, and provide a matching `ilmn_direct_coverage_x`. The output has blank nullable live EUID fields, writes per-AU `ONT_FQ_START_HOUR`/`ONT_FQ_END_HOUR`, and calculates `SUBSAMPLE_PCT = target_x / C_ILMN` at 12 decimal places with `ROUND_DOWN`. It fails before writing output if the receipt is missing or ambiguous, coverage is non-positive, or a requested target exceeds the verified denominator.

## Headnode commands and transfer

Open a full interactive shell when you need one:

```bash
dyec headnode connect \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER"
```

Run a bounded command non-interactively and get stdout/stderr back:

```bash
dyec --json headnode run \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  'hostname; command -v aws; aws sts get-caller-identity --output json'
```

Copy files through an explicit S3 relay:

```bash
dyec --json headnode upload -r ./config \
  /tmp/dyec-staged-config \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --staging-s3-uri "$STAGING_S3_URI"

dyec --json headnode download -r \
  /fsx/analysis_results/"$CLUSTER"/"$ANALYSIS_ID"/daylily-omics-analysis/results/day/hg38/reports \
  ./downloaded-reports \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --staging-s3-uri "$STAGING_S3_URI"
```

The relay prefix is intentionally explicit and auditable. DYEC does not delete relay objects automatically.

## Monitoring exact analyses

For a workflow launched by DYEC, inspect the exact run-state receipt, controller
target, active Snakemake log, progress, submitted/finished jobs, and current
Slurm states together:

```bash
dyec --json workflow status \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --session "$ANALYSIS_ID"

dyec workflow logs \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --session "$ANALYSIS_ID" \
  --stream snakemake \
  --lines 200
```

`workflow status` emits exactly one derived `state`: `RUNNING`, `SUCCEEDED`,
`FAILED`, or `UNKNOWN`. `SUCCEEDED` and a terminal exit code require the
matching DYEC `status.json`; a successful status-inspection command is never
the workflow exit code. `CONFIGURING` and `RUNNING` Slurm jobs are ongoing
work, and an empty queue is never success. Failure detection uses anchored
Snakemake terminal markers and deliberately ignores generic `ERROR` text and
printed shell bodies.

The Snakemake stream attributes and reads the log in one remote probe. Its
requested tail is compressed, integrity-checked, and decoded locally, avoiding
a second SSM round trip. If a requested tail cannot fit the bounded SSM
transport, DYEC fails clearly and asks for fewer `--lines`.

For a controller started manually during recovery, provide its identity
explicitly; DYEC does not discover a checkout or guess the newest log:

```bash
dyec --json workflow status \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --repo-path /fsx/analysis_results/<owner>/<analysis-id>/daylily-omics-analysis \
  --controller-pid <pid> \
  --session <exact-tmux-session>
```

If the controller is no longer live or descriptor correlation is unavailable,
add the exact
`--snakemake-log <repo-path>/.snakemake/log/<timestamp>.snakemake.log`.
Manual inspection can prove `RUNNING` or a high-signal `FAILED` state, but it
cannot prove `SUCCEEDED` or invent a terminal RC without a matching DYEC launch
receipt.

DYEC-launched controllers redirect output directly to the regular
`.dyec/controller.log` file; they never put `dy-r` behind `tee`. Immediately
after `dy-r` returns, the launcher atomically records `workflow_completed_at`
and `workflow_exit_code` in the matching `status.json`, before DAG evidence,
export, or other post-processing. Final controller `completed_at`/`exit_code`
fields take precedence if later post-processing changes the launch outcome.
For an exceptional manual recovery, likewise redirect `dy-r` directly to a
regular file and follow it from a separate `tail -f` process. Do not use
`dy-r ... | tee ...`: orphaned workflow helpers can inherit the pipe and delay
the shell from persisting its RC. A manual printed `RETURN CODE` remains
non-authoritative to `workflow status`; use the standard DYEC launcher when a
terminal success receipt is required.

Record visits before analysis-root reads:

```bash
dyec analysis visit \
  --analysis-root /fsx/analysis_results/"$CLUSTER"/"$ANALYSIS_ID" \
  --mode read \
  --intent "status check"
```

Use the exact-root status reporter:

```bash
dyec analysis status slim \
  --analysis-root /fsx/analysis_results/"$CLUSTER"/"$ANALYSIS_ID" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER"

dyec analysis status full \
  --analysis-root /fsx/analysis_results/"$CLUSTER"/"$ANALYSIS_ID" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --tail-lines 1000
```

For HIOMR command-family progress and optional DAG PNG download:

```bash
dyec --json command sample-stats hiomr-kitchensink \
  --name hg003_hiomrs \
  --analysis-root /fsx/analysis_results/"$CLUSTER"/"$ANALYSIS_ID" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --dag-output ./tmp/hg003_hiomrs_dag.png
```

Queue emptiness is never success. Success requires controller exit code plus expected terminal artifacts for the workflow.

## Run-directory QC commands

Run QC catalog entries are run-context commands. Mount the run directory first, then pass a run-context TSV to `catalog render` or `catalog launch`.

```bash
dyec --json mounts create s3://<sequencing-run-bucket>/<run-prefix>/ \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --platform ILMN \
  --read-only \
  --wait \
  --timeout-seconds 5400
```

Example run-context file:

```tsv
RUN_ID	PLATFORM	RUN_MOUNT
20260722_LH00000_0001_AEXAMPLE	ILMN	/fsx/run_dir_mounts/20260722_LH00000_0001_AEXAMPLE
```

Render each supported run-QC catalog command before launching it:

```bash
dyec --json catalog render illumina_run_qc \
  --analysis-id ilmn-runqc-20260722 \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --run-context-file ./runs.tsv \
  --dry-run

dyec --json catalog render ont_run_qc \
  --analysis-id ont-runqc-20260722 \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --run-context-file ./runs.tsv \
  --dry-run

dyec --json catalog render ultima_run_qc \
  --analysis-id ultima-runqc-20260722 \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --run-context-file ./runs.tsv \
  --dry-run
```

The catalog enforces each command’s required `PLATFORM` value.

## Export

Export one completed analysis directory:

```bash
dyec analysis visit \
  --analysis-root /fsx/analysis_results/"$CLUSTER"/"$ANALYSIS_ID" \
  --mode export \
  --intent "export completed pipeline results to $DESTINATION_S3_URI without FSx cleanup" \
  --s3-visit-uri "$DESTINATION_S3_URI"

dyec export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --source-path /fsx/analysis_results/"$CLUSTER"/"$ANALYSIS_ID" \
  --destination-s3-uri "$DESTINATION_S3_URI" \
  --output-dir ./export-receipts/"$ANALYSIS_ID"
```

`dyec catalog list`, `show`, and `render` expose the same `result_export`
contract. DayOA never exports: after the controller succeeds, run the displayed
DYEC visit and DRA export commands from the analysis root.
`dyec export` records a local receipt and uses an explicit DRA/export path.
Verify `status=success`, `phase=complete`, `task_lifecycle=SUCCEEDED`,
`detached=true`, and the expected S3 objects. FSx data is preserved unless a
separately approved destructive option is explicitly supplied.

## Development and tests

Use the repo environment:

```bash
cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate
python -m pytest tests/test_cli_registry_v2.py -q
git diff --check
```

Release tags are numeric, annotated semver tags with no leading `v`. Do not move pushed tags. For a breaking CLI/docs release after `13.x`, cut the next unclaimed `14.x` tag on a clean release commit.
