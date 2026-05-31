# Pipeline Manager Launches

DYEC owns cluster lifecycle, supported headnode access, FSx layout, repository
checkout, command launch, status capture, and export. The workflow manager inside
the checked-out repository remains repository-owned. A manager-specific launch is
valid only when it writes all durable outputs below:

```text
/fsx/analysis_results/<executing_entity>/<analysis_id>/
```

That exact analysis directory is the `dyec export --source-path` boundary. Input
DRAs under `/fsx/references`, `/fsx/control_data`, and `/fsx/run_dir_mounts` are
read-oriented inputs and are not export sources.

## Common Contract

Every manager should satisfy the same operational contract:

| Requirement | Contract |
|---|---|
| Repository checkout | Use `dyec workflow launch`, `dyec samples run`, or `day-clone` so the checkout is under `/fsx/analysis_results/<executing_entity>/<analysis_id>/`. |
| Inputs | Use staged sample manifests, `runs.tsv`, reference/control mounts, or explicit manager-native input files. Do not copy large mounted run folders into the result tree. |
| Outputs | Write manager logs, work state, reports, and final outputs below the analysis directory. |
| Monitoring | Use `dyec workflow status` and `dyec workflow logs` for `dyec workflow launch` sessions; use manager-native logs and `dyec headnode jobs` for direct headnode launches. |
| Export | Export the whole analysis directory with `dyec export`. Keep `fsx_export.yaml` as the mapping from FSx paths to S3 URIs. |
| Cleanup | Remove local FSx analysis scratch only after export success and receipt verification. |

## Snakemake 7 DayOA

DayOA is the first-class Snakemake 7 execution-plane repository in the DYEC
catalog. It is normally launched through catalog rows:

```bash
dyec samples run "$ANALYSIS_SAMPLES" \
  --command-id illumina_snv_alignstats \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --reference-s3-uri "$REF_S3_URI" \
  --control-data-s3-uri "$CONTROL_DATA_S3_URI" \
  --stage-s3-uri "$STAGE_S3_URI" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity ubuntu \
  --export-destination-s3-uri "$EXPORT_S3_URI" \
  --export-trigger on-success
```

For explicit DayOA commands, use `dyec workflow launch` with `bin/day_run` or the
catalog command string:

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity ubuntu \
  --repository daylily-omics-analysis \
  --git-tag "$DAYOA_TAG" \
  --samples-file ./samples.tsv \
  --units-file ./units.tsv \
  --dy-command "bin/day_run produce_alignstats -p -j 20 -k"
```

Inside a manual headnode tmux session, initialize DayOA as separate commands so
the shell functions and aliases exist before use:

```bash
source dyoainit
dy-a slurm hg38_broad
dy-r produce_alignstats -p -j 20 -k
```

Do not combine those three lines into one non-interactive shell command for a
manual DayOA launch.

## Snakemake 8 Repositories

DYEC can host a Snakemake 8 repository, but DayOA itself is a Snakemake 7
repository. Treat Snakemake 8 as a separate repository contract:

1. Add or select a repository catalog row for the Snakemake 8 project.
2. Ensure the repository owns its Snakemake 8 environment, profile, and executor
   settings.
3. Launch with a manager-native command that writes below the analysis root.
4. Use `dyec export` on the completed analysis directory.

Example command shape:

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity ubuntu \
  --repository my-snakemake8-repo \
  --git-tag "$PIPELINE_TAG" \
  --dy-command "snakemake --snakefile workflow/Snakefile --profile profiles/slurm --cores 192 --directory ."
```

The repository must fail hard if its Snakemake version, executor plugin,
container runtime, reference paths, or output directory are missing. Do not add
runtime compatibility aliases to make a Snakemake 7 profile look like a
Snakemake 8 profile.

## Nextflow

Nextflow workflows can run on the same cluster and use the same export boundary.
The validated pattern is the `daylily-sarek` direct headnode run documented in
`docs/running_nextflow_pipes.md` and `docs/running_nextflow_workflows.md`.

Use this pattern when the Nextflow pipeline has manager-native inputs rather than
DayOA `samples.tsv` and `units.tsv`:

```bash
day-clone --repository daylily-sarek --destination "$ANALYSIS_ID" --executing-entity ubuntu
cd "/fsx/analysis_results/ubuntu/$ANALYSIS_ID/sarek"
nextflow run . \
  -profile daylily_ephemeral_cluster \
  --input "/fsx/analysis_results/ubuntu/$ANALYSIS_ID/inputs/samplesheet.csv" \
  --outdir "/fsx/analysis_results/ubuntu/$ANALYSIS_ID/sarek/results"
```

For direct Nextflow launches, `dyec workflow status` is not authoritative unless
the command was launched by `dyec workflow launch`. Inspect `.nextflow.log`,
`nextflow log`, the tmux pane, and `dyec headnode jobs`.

## Cromwell Or WDL

Cromwell is not currently a first-class DYEC catalog manager. A Cromwell/WDL run
can still be made compatible with DYEC if the repository or launch script
explicitly satisfies the common contract:

```text
/fsx/analysis_results/<executing_entity>/<analysis_id>/
  cromwell/
    cromwell.conf
    workflow.wdl
    inputs.json
    metadata.json
    executions/
    outputs/
```

Minimum requirements before treating Cromwell as supported:

- pin the Cromwell jar or container image;
- write `call-caching`, `backend`, temp, and final output paths below the
  analysis directory;
- use explicit reference and input paths from mounted DYEC locations;
- record Cromwell metadata under the analysis directory;
- prove export maps all required outputs through `fsx_export.yaml`;
- add catalog/model/tests before advertising a Cromwell command as blessed.

Until those requirements are implemented, document Cromwell runs as
manager-native direct headnode runs, not as catalog-backed production commands.

## Export And Cleanup

The manager does not change export semantics:

```bash
dyec export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --source-path "/fsx/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID" \
  --destination-s3-uri "$EXPORT_S3_URI" \
  --output-dir "$EXPORT_DIR"
```

After export, inspect `fsx_export.yaml` and verify the expected manager-specific
outputs in S3. Only then remove the local analysis directory or rely on
`--delete-on-export-success`.
