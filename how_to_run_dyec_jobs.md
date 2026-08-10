# DYEC: fresh cluster to completed, exported DayOA work

This runbook is an operator procedure, not a command to run as one large
script. Run each gate, record the resulting IDs and paths in the work ledger,
and stop on a failed command or a contract mismatch. Do not substitute a
guessed cluster, S3 prefix, DayOA revision, manifest, or fallback command.

The examples use the `lsmc` AWS profile, `us-west-2`, and the currently
observed ready HIOMR-family cluster `preval-hiomr2`. On 2026-07-27, that was the
only `hiomr*` match returned by the read-only cluster inventory. Treat that as
an example selection, not proof it is suitable for a new workload.

DayOA workflow execution is always through `dy-r` in a persistent `tmux` pane
as `ubuntu`. DYEC's supported launcher creates that controller; never invoke
raw `snakemake`.

## 0. Boundaries and variables

The normal sequence is:

```text
preflight/create -> configure headnode -> mount or stage inputs -> dry-run
-> live controller -> read-only monitoring -> successful completion
-> explicit FSx-to-S3 export -> receipt and parity verification
```

Cluster creation, a live workflow, and a DRA mount all change AWS or FSx state.
FSx deletion, job intervention, and cluster deletion are separate destructive
operations and are not part of this runbook. An export below is no-delete.

Start locally in an interactive shell:

```bash
cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate

export AWS_PROFILE=lsmc
export REGION=us-west-2
export REGION_AZ=us-west-2d
export CLUSTER=preval-hiomr2
export EXECUTING_ENTITY="$CLUSTER"
export DAYOA_TAG=13.0.59
export WORK_ROOT="$PWD/docs/plans/<utc-stamp>_<work-name>"
mkdir -p "$WORK_ROOT"

aws sts get-caller-identity --profile "$AWS_PROFILE"
dyec version
dyec cluster-info --profile "$AWS_PROFILE" --region "$REGION"
AWS_PROFILE="$AWS_PROFILE" pcluster describe-cluster \
  --cluster-name "$CLUSTER" --region "$REGION"
```

`pcluster` does **not** accept `--profile`; the `AWS_PROFILE=lsmc` environment
assignment is deliberate. Do not use `dyec --version`; the current command is
`dyec version`.

Use a unique, immutable analysis ID for every dry run and live run. The live
analysis root is:

```text
/fsx/analysis_results/<executing-entity>/<analysis-id>
```

Before a long-lived workflow controller, set the agent identity values required
by the analysis-root coordination contract:

```bash
export DAYOA_AGENT_ID="<stable-agent-id>"
export DAYOA_AGENT_KIND="operator"
export DAYOA_HUMAN_REQUESTOR="<human-requestor>"
export DAYOA_TMUX_SESSION="<analysis-id>"
export DAYOA_LEDGER_PATH="$WORK_ROOT/<utc-stamp>_<work-name>_ledger.md"
```

## 1. From a genuinely fresh cluster

Use this section only when no suitable ready cluster exists. It can incur AWS
costs, so first record the requested configuration, budget/cost-center
selection, reference URI, control-data URI, staging URI, and output URI in a
dated ledger under `docs/plans/`.

```bash
export DAYEC_CONFIG="$HOME/.config/daylily/daylily_ephemeral_cluster.yaml"

dyec preflight \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAYEC_CONFIG"

dyec create \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAYEC_CONFIG" \
  --non-interactive
```

Do not infer the created cluster name. Read it from the successful `dyec create`
output, assign it to `CLUSTER`, and then repeat Gate 0. A ParallelCluster status
alone is insufficient: wait for `dyec create` to finish successfully.

For either a new cluster or `preval-hiomr2`, refresh the supported headnode
environment before a launch:

```bash
dyec headnode configure \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"

dyec headnode connect \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
```

Inside the interactive headnode shell, verify the actual contract and then
exit. The user must be `ubuntu`.

```bash
whoami
command -v day-clone
command -v tmux
command -v squeue
exit
```

If bootstrap, `dyoainit`, `dy-a`, or `dy-r` is absent, stop and record the
exact failure. Do not replace it with raw Snakemake or a different checkout.

## 2. Example A: Illumina run QC from a run directory

`illumina_run_qc` reads pre-existing run metrics and does not run BCLConvert.
It requires an ILMN `runs.tsv` context and a readable run mount. The catalog is
pinned to DayOA `13.0.59`; pass the tag explicitly rather than using a default
branch.

### 2.1 Mount the authoritative run prefix

First obtain the authoritative source S3 URI from the sequencing delivery
record. Do not reuse a stale source URI merely because a mount name looks
similar. This is a no-writeback mount:

```bash
export RUN_ID=<illumina-run-id>
export RUN_SOURCE_S3_URI='s3://<authoritative-sequencing-bucket>/<run-prefix>/'

dyec mounts create "$RUN_SOURCE_S3_URI" \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --purpose run --platform ILMN --read-only --wait --timeout-seconds 5400
```

Save the returned mount ID as `MOUNT_ID`. A large Illumina DRA can remain in
`CREATING` for roughly 40 minutes; `5400` seconds intentionally exceeds that
window. Do not retry, duplicate, or delete it merely because it is still
creating before then.

```bash
export MOUNT_ID=<returned-mount-id>
dyec --json mounts verify \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --mount-id "$MOUNT_ID"
```

### 2.2 Create and validate `runs.tsv`

Create the run context locally in the ledger work directory. The fields are
explicit, including both the source URI and the mounted FSx directory:

```text
RUNID	PLATFORM	RUN_DIR	SOURCE_S3_URI	MOUNT_ID	SAMPLE_SHEET	BASECALLING_STATE	RUN_STATUS	OUTPUT_ROOT	REGION	PROFILE
<run-id>	ILMN	/fsx/run_dir_mounts/<mount-id>	s3://<authoritative-sequencing-bucket>/<run-prefix>/	<mount-id>	<sample-sheet-or-na>	COMPLETE	COMPLETE	results/runs/<run-id>	us-west-2	lsmc
```

For reference, the recent proven context shape was:

```text
20260514_LH01106_0008_A23TVNWLT4	ILMN	/fsx/run_dir_mounts/20260514_LH01106_0008_A23TVNWLT4-M-RGX-CSWQ		20260514_LH01106_0008_A23TVNWLT4-M-RGX-CSWQ	na	COMPLETE	COMPLETE	results/runs/20260514_LH01106_0008_A23TVNWLT4	us-west-2	lsmc
```

The blank `SOURCE_S3_URI` in that historical record is not a template for new
work: populate it with the authoritative URI for a new mount.

### 2.3 Render, dry-run, and launch

Use the catalog renderer first; it produces the exact `dyec workflow launch`
argv, including `run_context_file=config/runs.tsv` and the artifact-manifest
flags. Review the output and retain it in the ledger.

```bash
export RUN_QC_ID="<utc-stamp>_ilmn_run_qc"
export RUNS_TSV="$WORK_ROOT/runs.tsv"

dyec catalog render illumina_run_qc \
  --analysis-id "$RUN_QC_ID" \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --executing-entity "$EXECUTING_ENTITY" \
  --git-tag "$DAYOA_TAG" --run-context-file "$RUNS_TSV" --dry-run
```

Launch the rendered dry-run command unchanged. Its DayOA command must contain
`-n`. A successful dry run is a plan only; it does not prove that output files
exist. For the live launch, re-render without `--dry-run`, review the command,
and execute exactly that output. Do not remove only one `-n` from copied text.

The resulting controller must have a meaningful persistent tmux session, for
example `$RUN_QC_ID`. DYEC's launcher creates the `ubuntu` interactive-login
shell and runs the required sequence as separate setup actions:

```text
cd /fsx/analysis_results/<executing-entity>/<analysis-id>/daylily-omics-analysis
source dyoainit
dy-a slurm hg38
dy-r produce_illumina_run_qc ...
```

## 3. Example B: stage Illumina reads and run SNV concordance

This route starts with the documented `analysis_samples_manifest.tsv` shape,
generates the exact DayOA six-manifest contract, stages it, then launches the
catalog command `illumina_snv_alignstats`. That command requests these targets:

```text
produce_sent_align
produce_dmd_dedup_cram
produce_sentd_snv_vcf
produce_snv_concordances
produce_alignstats
```

### 3.1 Build an explicit input table

Start from the checked-in ILMN example, then replace every example value with
the reviewed input paths and metadata for the work. This example is HG003 5x
and uses two paired Illumina FASTQs plus the GIAB concordance/truth directory:

```bash
export ANALYSIS_SAMPLES="$WORK_ROOT/analysis_samples_manifest.tsv"
cp examples/staging/ilmn_hg003_5x_solo/analysis_samples_manifest.tsv \
  "$ANALYSIS_SAMPLES"
```

The input table must retain its complete header. At minimum, the catalog
requires nonempty `ILMN_R1_FQ` and `ILMN_R2_FQ`; the selected sample's
`PATH_TO_CONCORDANCE_DATA_DIR`, `CONCORDANCE_CONTROL_PATH`, and
`TRUTH_DATA_DIR` must name the reviewed controls. The checked-in example's
relevant row uses:

```text
RUN_ID=I2
SAMPLE_ID=HG003
SEQ_PLATFORM=ILMN
ILMN_R1_FQ=/fsx/data/.../HG003_5x_R1.fastq.gz
ILMN_R2_FQ=/fsx/data/.../HG003_5x_R2.fastq.gz
STAGE_DIRECTIVE=pass_through
STAGE_TARGET=/fsx/staging/staged_external_sequencing_data
```

Use a source path only after confirming how it is exposed on this cluster. For
S3-resident external input, use the explicit staging path and the approved
reference/control/staging buckets. Do not invent values for these three URIs:

```bash
export REF_S3_URI='s3://<approved-reference-root>/'
export CONTROL_DATA_S3_URI='s3://<approved-control-data-root>/'
export STAGE_S3_URI='s3://<approved-staging-root>/'
export SNV_ID="<utc-stamp>_ilmn_snv_concordance"
export STAGE_CONFIG="$WORK_ROOT/staged-manifests"
```

### 3.2 Validate and stage without launching

First validate the source table and generate only the precise manifests. This
is the review point for input identity and staging paths:

```bash
dyec samples stage "$ANALYSIS_SAMPLES" \
  --manifest-contract dayoa12 \
  --reference-s3-uri "$REF_S3_URI" \
  --control-data-s3-uri "$CONTROL_DATA_S3_URI" \
  --stage-s3-uri "$STAGE_S3_URI" \
  --config-dir "$STAGE_CONFIG" \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --config-only
```

The current DayOA contract is exactly six files:

```text
specimens.tsv
samples.tsv
libraries.tsv
sequencing_inputs.tsv
analysis_units.tsv
analysis_unit_inputs.tsv
```

After reviewing those files and their receipts, use `dyec samples run` to stage
and launch. It is the supported command because it performs the staging and
then passes the generated contract to the catalog-aware workflow launcher.

Dry run:

```bash
dyec samples run "$ANALYSIS_SAMPLES" \
  --command-id illumina_snv_alignstats \
  --analysis-id "${SNV_ID}_dryrun" \
  --executing-entity "$EXECUTING_ENTITY" \
  --reference-s3-uri "$REF_S3_URI" \
  --control-data-s3-uri "$CONTROL_DATA_S3_URI" \
  --stage-s3-uri "$STAGE_S3_URI" \
  --config-dir "$STAGE_CONFIG" \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --git-tag "$DAYOA_TAG" --session-name "${SNV_ID}_dryrun" \
  --dry-run
```

For a live run, use a new `SNV_ID` or the reviewed live ID; omit `--dry-run`,
keep the same explicit inputs and tag, and keep `--export-trigger` at its
default `none`. Export is performed only after the completion gate below.

### Observed renderer bug; do not work around it

On this checkout, the following read-only render attempt failed even though
`examples/staging/ilmn_hg003_5x_solo` is a six-manifest directory:

```bash
dyec catalog render illumina_snv_alignstats \
  --analysis-id example_ilmn_snv_concordance_20260727 \
  --profile lsmc --region us-west-2 --cluster preval-hiomr2 \
  --manifest-dir examples/staging/ilmn_hg003_5x_solo --dry-run
```

The observed error was: `requires --stage-dir or both --samples-file and
--units-file`. Do not add legacy manifests, aliases, or a fallback path to make
that command pass. Use `dyec samples run` above and record the renderer bug if
it blocks a required review workflow.

## 4. Monitor until terminal completion

Before monitoring, record a visit for the analysis root. Monitoring and log
review are read-only and do not require a write lock:

```bash
export ANALYSIS_ID="$RUN_QC_ID"  # or the live SNV ID
export ANALYSIS_ROOT="/fsx/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID"

dyec analysis visit --analysis-root "$ANALYSIS_ROOT" --mode monitor \
  --intent 'monitor active DayOA workflow' \
  --human-requestor "$DAYOA_HUMAN_REQUESTOR"
```

Use all of these surfaces together. There is no current `dyec monitor`
command; use the following read-only commands instead:

```bash
dyec workflow status \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --session "$ANALYSIS_ID"

dyec workflow logs \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --session "$ANALYSIS_ID" --stream controller --lines 200

dyec headnode jobs \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"

dyec headnode dayoa-controllers \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
```

For a direct, read-only Slurm accounting snapshot, connect as `ubuntu` and run
only inspection commands:

```bash
dyec headnode connect \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"

tmux list-windows -t "$ANALYSIS_ID"
tmux list-panes -t "$ANALYSIS_ID"
tmux capture-pane -pt "$ANALYSIS_ID" -S -200
squeue -u ubuntu
sacct -X --starttime today --format=JobID,JobName,State,Elapsed,AllocCPUS,ExitCode
exit
```

`CF`/`CONFIGURING` can legitimately last tens of minutes while spot compute is
created. A job exceeding three hours is a reason to report `needs
investigation`, not authorization to cancel, requeue, hold, drain, resume, or
restart anything. Do not manipulate Slurm or the controller without explicit
approval for that exact action.

Treat the workflow as complete only when all of the following agree:

- `workflow status` is terminal and successful;
- the controller log reports successful DayOA completion, not merely submission;
- the relevant Slurm jobs are terminal with successful exit codes;
- the requested results exist under the named analysis root; and
- for SNV work, the expected CRAM/CRAI, SNV VCF/index, alignstats, and
  concordance outputs are present; for run QC, the expected MultiQC report and
  `illumina_run_qc.json` are present.

If runtime or cost reporting is needed after completion, benchmark collection
writes into the analysis root and therefore needs the normal write lock:

```bash
dyec analysis lock acquire --analysis-root "$ANALYSIS_ROOT" --operation write \
  --intent 'collect DayOA benchmark summary after successful completion'

dyec workflow collect-benchmarks \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --analysis-root "$ANALYSIS_ROOT" --genome-build hg38 \
  --human-requestor "$DAYOA_HUMAN_REQUESTOR"

dyec analysis lock release --analysis-root "$ANALYSIS_ROOT"
```

## 5. Export completed FSx results to S3

Export only after the completion gate. First record an export visit; this
no-delete export does not require write-lock ownership:

```bash
export EXPORT_S3_URI='s3://<approved-results-bucket>/<approved-prefix>/'
export EXPORT_DIR="$WORK_ROOT/fsx_export"

dyec analysis visit --analysis-root "$ANALYSIS_ROOT" --mode export \
  --intent 'export completed DayOA results to approved S3 destination' \
  --human-requestor "$DAYOA_HUMAN_REQUESTOR" \
  --s3-visit-uri "$EXPORT_S3_URI"

dyec export \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --source-path "$ANALYSIS_ROOT" \
  --destination-s3-uri "$EXPORT_S3_URI" \
  --output-dir "$EXPORT_DIR" \
  --wait --timeout-seconds 5400
```

Do **not** add `--delete-data-in-file-system`. The result receipt is the
authoritative export result:

```bash
sed -n '1,240p' "$EXPORT_DIR/fsx_export.yaml"
```

Do not call an export a complete mirror solely because the DRA task says it
succeeded. The receipt must show at least `status: success`, `detached: true`,
and `delete_data_in_file_system: false`. Then reconcile the intended source
tree and destination prefix by relative key, object count, total bytes, and
per-object size (and checksums where available). Record missing, extra, or
size-different objects explicitly; do not silently call a partial/change-based
export complete.

Only after a separately approved cleanup plan, a successful receipt, and a
clean parity record may FSx deletion or cluster teardown be proposed. Those
actions are intentionally outside this runbook.

## 6. Evidence to retain in the work ledger

Record these rather than relying on terminal history:

- DYEC version/commit, explicit DayOA tag/commit, profile, region, AZ, and
  exact cluster name;
- preflight and cluster readiness output, plus headnode `ubuntu` verification;
- source S3 URI, mount ID/DRA ID, FSx mounted path, and `runs.tsv` or the six
  generated manifests with hashes;
- rendered dry-run command, dry-run terminal result, live analysis ID, session,
  analysis root, controller status, and Slurm job IDs;
- completion checks and required result paths;
- `fsx_export.yaml`, S3 destination, DRA task/association IDs, and the parity
  comparison; and
- any observed CLI bug or contract gap, exactly as reported, with no local
  workaround masquerading as a fix.
