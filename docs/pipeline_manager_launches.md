# Pipeline Manager Launches

DYEC owns cluster lifecycle, supported headnode access, FSx layout, repository checkout, command launch, status capture, and export. The workflow manager inside the checked-out repository remains repository-owned. DYEC is not a dogma-locked workflow manager; it can run DayOA/Snakemake, nf-core/Nextflow, or another repository-managed engine when the run satisfies the same analysis-root and export contract.

The durable output boundary is always:

```text
/fsx/analysis_results/<executing_entity>/<analysis_id>/
```

That exact analysis directory is the `dyec export --source-path` boundary. Input DRAs under `/fsx/references`, `/fsx/control_data`, and `/fsx/run_dir_mounts` are read-oriented inputs and are not export sources.

## Common Contract

Every manager should satisfy the same operational contract:

| Requirement | Contract |
|---|---|
| Repository checkout | Use `dyec workflow launch`, `dyec samples run`, or `day-clone` so the checkout is under `/fsx/analysis_results/<executing_entity>/<analysis_id>/`. |
| Inputs | Use staged sample manifests, `runs.tsv`, reference/control mounts, run mounts, or explicit manager-native input files. Do not copy large mounted run folders into the result tree. |
| Outputs | Write manager logs, work state, reports, benchmarks, and final outputs below the analysis directory. |
| Monitoring | Use `dyec workflow status` and `dyec workflow logs` for DYEC-launched sessions; use manager-native logs and read-only Slurm inspection for direct headnode launches. |
| Export | Export the whole analysis directory with `dyec export`. Keep `fsx_export.yaml` as the mapping from FSx paths to S3 URIs. |
| Failure behavior | Missing profiles, references, containers, credentials, licenses, or output paths must fail clearly. |
| Cleanup | Remove local FSx analysis scratch only after export success and receipt verification. |

## DayOA And Snakemake 7

DayOA is the first-class Snakemake 7 execution-plane repository in the DYEC catalog. Catalog-backed sample launches use `dyec samples run`:

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
  --export-trigger on-success \
  --dry-run
```

Manual DayOA commands inside a headnode `tmux` session use the DayOA wrapper. Run setup commands separately:

```bash
source dyoainit
dy-a slurm hg38_broad
dy-r produce_alignstats -p -j 20 -k
```

Agent/headnode workflow instructions must not invoke `snakemake` directly for DayOA. `dy-r` passes targets and flags through after applying DayOA profile setup.

## Other Snakemake Repositories

DYEC can host another Snakemake repository, including a Snakemake 8 repository, when the repository owns its own environment, profile, executor settings, and output layout.

Minimum requirements:

1. Add or select a repository catalog row for the project.
2. Pin the repository ref.
3. Ensure the repository owns its Snakemake environment and profile.
4. Launch with a manager-native command that writes below the analysis root.
5. Use `dyec export` on the completed analysis directory.

Example command shape:

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity ubuntu \
  --repository my-snakemake-repo \
  --git-tag "$PIPELINE_TAG" \
  --no-default-activation \
  --dy-command "<repo-owned launch command>"
```

The repository must fail hard if its workflow-manager version, executor plugin, container runtime, reference paths, or output directory are missing. Do not add runtime compatibility aliases to make one manager version look like another.

## Nextflow And nf-core/Sarek

Nextflow workflows can run on the same cluster and use the same export boundary. The catalog includes `daylily-sarek` with default ref `0.7.379`; that repository carries the nf-core/Sarek pipeline integration used for DYEC validation.

Use this pattern when the Nextflow pipeline has manager-native inputs rather than DayOA `samples.tsv` and `units.tsv`:

```bash
day-clone --repository daylily-sarek --destination "$ANALYSIS_ID" --executing-entity ubuntu
cd "/fsx/analysis_results/ubuntu/$ANALYSIS_ID/sarek"
nextflow run . \
  -profile daylily_ephemeral_cluster \
  --input "/fsx/analysis_results/ubuntu/$ANALYSIS_ID/inputs/samplesheet.csv" \
  --outdir "/fsx/analysis_results/ubuntu/$ANALYSIS_ID/sarek/results"
```

For direct Nextflow launches, `dyec workflow status` is not authoritative unless the command was launched by `dyec workflow launch`. Inspect `.nextflow.log`, `nextflow log`, the tmux pane, and read-only Slurm status. The active HG003 benchmark plan records that `nextflow` must be present or installed explicitly before nf-core/Sarek can run on a cluster.

## Cromwell Or WDL

Cromwell is not currently a first-class DYEC catalog manager. A Cromwell/WDL run can still be made compatible with DYEC if the repository or launch script explicitly satisfies the common contract:

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

- pin the Cromwell jar or container image
- write backend, temp, metadata, and final output paths below the analysis directory
- use explicit reference and input paths from mounted DYEC locations
- record Cromwell metadata under the analysis directory
- prove export maps all required outputs through `fsx_export.yaml`
- add catalog/model/tests before advertising a Cromwell command as blessed

Until those requirements are implemented, document Cromwell runs as manager-native direct headnode runs, not as catalog-backed production commands.

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

After export, inspect `fsx_export.yaml` and verify the expected manager-specific outputs in S3. Only then remove the local analysis directory or rely on `--delete-on-export-success`.
