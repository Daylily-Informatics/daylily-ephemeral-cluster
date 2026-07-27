# DYEC CLI Reference

This document is the operator-facing reference for the current `dyec` command surface. It favors explicit commands and receipts over implicit state. `daylily-ec` may exist as a historical alias, but current docs and ledgers should use `dyec`.

## Conventions

Examples assume:

```bash
cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate

export AWS_PROFILE=lsmc
export REGION=us-west-2
export REGION_AZ=us-west-2d
export CLUSTER=ifx-p2-1000-120-0715
export PROJECT=RnD
export ANALYSIS_ID=<analysis-id>
export ANALYSIS_ROOT=/fsx/analysis_results/$CLUSTER/$ANALYSIS_ID
export STAGING_S3_URI=s3://<bucket>/<dyec-temporary-relay-prefix>/
```

General rules:

- Prefer `--json` for automation and agent use.
- Prefer `--cluster` for DYEC commands.
- Use exact DayOA tags. Do not rely on `day-clone` defaults for new analysis work.
- Use `dyec catalog render` before `dyec catalog launch` when the launch will cost time or money.
- Use `dyec workflow launch` only with an exact `--dy-command` and exact input paths.
- Use `dyec analysis visit` before reading an FSx analysis root, and use write locks/guards before protected writes.
- Do not invoke raw `snakemake` for DayOA work.
- Headnode-facing CLI commands default to `--remote-user auto`: Ubuntu/Intel DayOA headnodes resolve to `ubuntu`; DRAGEN/RHEL-style headnodes resolve to `ec2-user`. Unknown platform metadata fails hard.
- DYEC-created headnode shells run as bash login/interactive contexts and source `~/.bashrc`; do not wrap workflow launches in a noninteractive `bash -lc` path.

## Global command

```bash
dyec --help
dyec --json version
dyec info
dyec runtime status
dyec resources-dir
dyec env
dyec agent guidance
```

Global options:

| Option | Use |
|---|---|
| `--json` | Emit machine-readable payloads when the command supports JSON. |
| `--dry-run` | Plan without persistent changes when supported by that command. |
| `--no-color` | Disable ANSI styling. |
| `--debug` | Print debug diagnostics. |
| `--install-completion`, `--show-completion` | Shell completion setup. |

## Agent guidance

`dyec agent guidance` prints a compact operational contract for agents and automated operators:

```bash
dyec agent guidance
```

It covers:

- local activation;
- SSM/headnode access;
- DayOA controller rules;
- analysis-root visit/lock safety;
- headnode upload/download syntax;
- monitoring commands and Slurm queue format.

Use this when an operator or agent needs a concise reminder of the safe path.

## Cluster lifecycle

Preflight:

```bash
dyec preflight \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config ~/.config/daylily/daylily_ephemeral_cluster.yaml
```

Create:

```bash
dyec create \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config ~/.config/daylily/daylily_ephemeral_cluster.yaml
```

Inspect:

```bash
dyec cluster list \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --verbose

dyec --json cluster describe \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER"

dyec cluster wait \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER"
```

Tags:

```bash
dyec --json cluster tags \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER"

dyec cluster tags \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --set daylily-accept-jobs=false \
  --set operator-note=maintenance-window
```

Delete remains destructive:

```bash
dyec delete --dry-run \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER"
```

Run live deletion only after the exact destructive effect is approved.

## Headnode access and observability

Interactive shell:

```bash
dyec headnode connect \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER"
```

The supported user is `ubuntu` in a bash login shell. Use `root` only when explicitly approved for a specific operation.

Basic headnode inspection:

```bash
dyec --json headnode info --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
dyec headnode jobs --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
dyec --json headnode system-info --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
dyec --json headnode fsx-usage --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
dyec --json headnode analysis-roots --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
dyec --json headnode dayoa-controllers --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
```

Arbitrary headnode command:

```bash
dyec --json headnode run \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  'hostname; command -v aws; aws sts get-caller-identity --output json'
```

`headnode run` is intentionally explicit. It returns the SSM command id, response code, stdout, and stderr. It is marked as mutating-capable because the command string can mutate state.

File transfer through an explicit S3 relay:

```bash
dyec --json headnode upload -r ./local-config-dir \
  /tmp/dyec-config-dir \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --staging-s3-uri "$STAGING_S3_URI"

dyec --json headnode download -r \
  /fsx/analysis_results/$CLUSTER/$ANALYSIS_ID/daylily-omics-analysis/results/day/hg38/reports \
  ./reports \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --staging-s3-uri "$STAGING_S3_URI"
```

Important relay behavior:

- `--staging-s3-uri` is required.
- Both local credentials and the headnode instance role must be allowed to read/write the relay prefix.
- `-r` is required for directories.
- Relay objects are retained for audit; clean them up explicitly if desired.

Configure/repair the headnode:

```bash
dyec headnode configure \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER"
```

Run this after a DYEC upgrade when the headnode is missing new commands such as `dyec analysis status`, `dyec headnode run`, or current `dy-r` analysis-lock support.

## Analysis-root visits, locks, and status

Record a visit:

```bash
dyec analysis visit \
  --analysis-root "$ANALYSIS_ROOT" \
  --mode read \
  --intent "inspect run state"
```

Acquire a write lock before protected writes:

```bash
dyec analysis lock acquire \
  --analysis-root "$ANALYSIS_ROOT" \
  --operation write \
  --intent "restart failed reporting aggregator"

dyec analysis lock heartbeat --analysis-root "$ANALYSIS_ROOT"
dyec analysis lock status --analysis-root "$ANALYSIS_ROOT"
dyec analysis lock release --analysis-root "$ANALYSIS_ROOT"
```

Guard protected commands:

```bash
dyec analysis guard \
  --analysis-root "$ANALYSIS_ROOT" \
  --operation write \
  -- bash -lc 'touch "$ANALYSIS_ROOT"/operator_test.marker'
```

Takeover is token-based and must not be silent:

```bash
dyec analysis lock takeover \
  --analysis-root "$ANALYSIS_ROOT" \
  --request \
  --intent "recover stale failed controller"
```

Exact-root status:

```bash
dyec analysis status slim \
  --analysis-root "$ANALYSIS_ROOT" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER"

dyec analysis status full \
  --analysis-root "$ANALYSIS_ROOT" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --tail-lines 1000
```

`slim` is for quick controller/job/artifact progress. `full` tails relevant controller/job/rule logs, reports FSx usage, and includes richer per-analysis progress when available.

## Command-family progress

HIOMRS sample stats:

```bash
dyec --json command sample-stats hiomrs-kitchensink \
  --name bjuice20_hiomrs \
  --analysis-root "$ANALYSIS_ROOT" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --tail-lines 1000
```

Download a generated DAG PNG to an exact local filename:

```bash
dyec --json command sample-stats hiomrs-kitchensink \
  --name bjuice20_hiomrs \
  --analysis-root "$ANALYSIS_ROOT" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --dag-output ./tmp/bjuice20_hiomrs_dag.png
```

The DAG transfer is bounded, size-checked, and SHA-256 verified.

## Local identity manifest commands

These commands validate local manifest topology and produce local receipts. They do not call any identity service.

```bash
dyec --json identities validate --manifest-dir ./config > identities.validate.json
dyec --json identities status --manifest-dir ./config > identities.status.json
dyec --json identities plan --manifest-dir ./config --output identities.plan.json
dyec --json identities apply --manifest-dir ./config --plan identities.plan.json --output identities.apply.json
dyec --json identities evidence --manifest-dir ./config --output identities.evidence.json
```

Use them for:

- FK validation across six manifests;
- EUID presence/blank status;
- customer-release eligibility checks driven only by supplied files;
- hash-bound receipts.

Do not add service URLs or tokens to DYEC identity commands.

## Six-manifest sample analysis input

Current DayOA sample analysis expects exactly:

```text
specimens.tsv
samples.tsv
libraries.tsv
sequencing_inputs.tsv
analysis_units.tsv
analysis_unit_inputs.tsv
```

DYEC validates these files before launch and sends them byte-for-byte to the headnode. `units.tsv` is historical and only valid for explicitly legacy catalog commands.

Required topology:

```text
specimens.tsv            SPECIMEN_ID
samples.tsv              SAMPLEID -> SPECIMEN_ID
libraries.tsv            LIBRARY_ID -> SAMPLEID
sequencing_inputs.tsv    SEQUENCING_INPUT_UID -> LIBRARY_ID
analysis_units.tsv       ANALYSIS_UNIT_UID -> SAMPLEID
analysis_unit_inputs.tsv ANALYSIS_UNIT_UID + SEQUENCING_INPUT_UID + ROLE + INPUT_ORDINAL
```

`sequencing_inputs.tsv` must use explicit source columns for the selected layout and modality. `analysis_unit_inputs.tsv` determines the ordered SR/LR input selection for each analysis unit.

## Bjuice prevalence config helper

Purpose: generate exact six-manifest DayOA inputs for reviewed Bjuice prevalence sample subsets from reviewed evidence files.

```bash
dyec --json catalog config-bjuice-preval \
  --sample HG003 \
  --sample HG004 \
  --output-dir ./config-hg003-hg004-ds025 \
  --source-manifest-json /path/to/source_manifest_resolved.json \
  --run-evidence-json /path/to/run_evidence_v2.json \
  --library-run-matrix-tsv /path/to/bjuice_preval_library_run_matrix.tsv \
  --sample-metadata-tsv /path/to/legacy_samples.tsv \
  --legacy-units-tsv /path/to/legacy_units.tsv \
  --sr-subsample-pct 0.25 \
  --ont-subsample-pct 0.25 \
  --analysis-label BJUICEPREVAL \
  --profile "$AWS_PROFILE" \
  --region "$REGION"
```

Outputs:

```text
specimens.tsv
samples.tsv
libraries.tsv
sequencing_inputs.tsv
analysis_units.tsv
analysis_unit_inputs.tsv
bjuice_preval_config_receipt.json
```

The helper:

- requires explicit `--sample` values;
- requires an empty output directory unless the exact file creation is allowed by the implementation;
- maps reviewed S3 source groups into configured `/fsx/run_dir_mounts` paths;
- lists exact S3 FASTQs through AWS;
- populates SR/LR sequencing inputs and ordered analysis-unit inputs;
- writes a receipt with manifest hashes and row counts;
- fails on missing or ambiguous source metadata.

## Catalog discovery

List commands:

```bash
dyec catalog list
dyec --json catalog list
dyec --json catalog list --command-class sample_analysis
dyec --json catalog list --command-class run_analysis --type prod
```

Show one command:

```bash
dyec --json catalog show hybrid_ilmn_ont_hiomrs_kitchensink
dyec --json catalog show package_inflection_hybrid_data
dyec --json catalog show illumina_run_qc
```

The catalog exposes:

- command id and display name;
- command class (`sample_analysis`, `run_analysis`, or `utility`);
- repository and DayOA git tag;
- input contract;
- exact `dy-r` or `bin/day_run` command string;
- dry-run command string;
- targets, callers, aligners, dedupers, jobs, and keep-going settings;
- validated version metadata when present.

## Catalog render

Render the exact `dyec workflow launch` argv without starting a controller:

```bash
dyec --json catalog render hybrid_ilmn_ont_hiomrs_kitchensink \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$CLUSTER" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --manifest-dir ./config \
  --payload-staging-s3-uri "$STAGING_S3_URI" \
  --session-name "${ANALYSIS_ID}-dryrun" \
  --project "$PROJECT" \
  --dry-run
```

Useful options:

| Option | Meaning |
|---|---|
| `--analysis-id` | Name under `/fsx/analysis_results/<executing-entity>/`. |
| `--executing-entity` | First path segment under `/fsx/analysis_results`; defaults to cluster. |
| `--git-tag` | Override the catalog DayOA tag. Use only when intentionally testing a specific ref. |
| `--manifest-dir` | Local six-manifest directory. |
| `--payload-staging-s3-uri` | S3 relay for large launch payloads. |
| `--run-context-file` | Local run-context TSV for run-analysis commands. |
| `--stage-dir` | Existing headnode/FSx staging directory. |
| `--dy-config key=value` | Append one explicit DayOA/Snakemake config assignment. Repeatable. |
| `--export-destination-s3-uri` | Optional auto-export root/destination. |
| `--export-trigger none|on-success|always` | Auto-export trigger. |
| `--replace-existing-analysis-dir` | Forward explicit replacement intent to workflow launch. |

`--dy-config` accepts only explicit assignments like `key=value`; blank strings and free-form shell fragments fail.

Example with DayOA runtime overrides:

```bash
dyec --json catalog render hybrid_ilmn_ont_hiomrs_kitchensink \
  --analysis-id bjuice-hg003-hg004-ds025-ont0to6 \
  --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" \
  --manifest-dir ./config-hg003-hg004-ds025 \
  --payload-staging-s3-uri "$STAGING_S3_URI" \
  --project "$PROJECT" \
  --dry-run \
  --dy-config use_fq_data_starting_hrs=0 \
  --dy-config use_fq_data_up_to_hrs=6
```

DYEC passes these overrides through; DayOA defines their workflow meaning.

## Catalog launch and quick-launch

Launch a catalog-backed dry run:

```bash
dyec --json catalog launch hybrid_ilmn_ont_hiomrs_kitchensink \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$CLUSTER" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --manifest-dir ./config \
  --payload-staging-s3-uri "$STAGING_S3_URI" \
  --session-name "${ANALYSIS_ID}-dryrun" \
  --project "$PROJECT" \
  --dry-run
```

Launch live after the dry-run plan is reviewed:

```bash
dyec --json catalog launch hybrid_ilmn_ont_hiomrs_kitchensink \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$CLUSTER" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --manifest-dir ./config \
  --payload-staging-s3-uri "$STAGING_S3_URI" \
  --session-name "$ANALYSIS_ID" \
  --project "$PROJECT"
```

`catalog quick-launch` is an alias for `catalog launch`.

The JSON response includes the rendered command, effective `dy-r` command, staging URI, session name, run directory, and workflow launch metadata.

## Workflow launch

Use this lower-level command when there is no catalog row or when a catalog render has already been reviewed and converted into an explicit workflow launch:

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$CLUSTER" \
  --git-tag 13.0.19 \
  --manifest-dir ./config \
  --payload-staging-s3-uri "$STAGING_S3_URI" \
  --session-name "$ANALYSIS_ID" \
  --project "$PROJECT" \
  --dy-command "dy-r produce_hiomrs -j 100 -p -T 0 --rerun-triggers mtime --rerun-incomplete"
```

For large local input payloads, use `--payload-staging-s3-uri`. The launch helper uploads a tarball locally, then the headnode downloads it with `aws s3 cp`, expands it in the workflow run directory, and starts the controller from a staged script. The exact controller script is copied to `<analysis-root>/bin/dyec-controller-launch.sh` after `day-clone` succeeds.

### Continue an existing analysis root

Use `--reuse-existing-analysis-dir` only for a new controller that must consume
products already present in one exact analysis root. It is deliberately not a
replacement mode: it requires `--input-contract none` and `--no-input-staging`,
cannot accept manifests or bootstrap configuration, and cannot be combined with
`--replace-existing-analysis-dir`.

```bash
dyec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$CLUSTER" \
  --git-tag "$DAYOA_REF" \
  --input-contract none \
  --no-input-staging \
  --session-name "$CONTINUATION_SESSION" \
  --project "$PROJECT" \
  --cost-center "$COST_CENTER" \
  --reuse-existing-analysis-dir \
  --dy-command "dy-r <exact-target> -p -k -j 6"
```

Before creating the controller, DYEC records the analysis visit/lock, verifies
that the existing checkout is a clean Git work tree, fetches the explicit
`--git-tag` reference from `origin`, and checks out its exact fetched commit in
detached mode. It leaves the analysis root and its untracked runtime inputs
intact; a missing root, dirty tracked checkout, absent source ref, or checkout
mismatch fails closed.

Read status and logs:

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
  --lines 200
```

Collect benchmark summaries from a completed or partially completed DayOA root:

```bash
dyec --json workflow collect-benchmarks \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --analysis-root "$ANALYSIS_ROOT" \
  --genome-build hg38

dyec --json workflow benchmark-report \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --analysis-root "$ANALYSIS_ROOT" \
  --genome-build hg38
```

Stop a workflow controller only when approved:

```bash
dyec --json workflow stop \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --session "$ANALYSIS_ID"
```

Add `--cancel-slurm-jobs --job-name-pattern '<regex>'` only when the exact job cancellation is approved.

## Run-directory mounts

Create a read-only FSx DRA for a sequencing run:

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

Verify:

```bash
dyec --json mounts verify \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --mount-id <mount-id>
```

List/describe/delete:

```bash
dyec --json mounts list --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
dyec --json mounts describe <mount-id> --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
dyec mounts delete <mount-id> --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
```

Do not treat mount creation as timed out before 40 minutes; large DRAs can remain `CREATING`.

## Run-QC catalog commands

Run-QC commands use `input_contract: run_context`.

Example `runs.tsv`:

```tsv
RUN_ID	PLATFORM	RUN_MOUNT
20260722_LH00000_0001_AEXAMPLE	ILMN	/fsx/run_dir_mounts/20260722_LH00000_0001_AEXAMPLE
```

Render Illumina, ONT, and Ultima run QC:

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

The catalog rejects a run-context file whose `PLATFORM` does not match the command requirements.

## Inflection hybrid package command

The current command-catalog entry for packaging completed hybrid data is:

```bash
dyec --json catalog show package_inflection_hybrid_data
```

Render a bounded package-only plan against an existing analysis root:

```bash
dyec --json catalog render package_inflection_hybrid_data \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$CLUSTER" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --manifest-dir ./config \
  --payload-staging-s3-uri "$STAGING_S3_URI" \
  --session-name "${ANALYSIS_ID}-package-dryrun" \
  --project "$PROJECT" \
  --dry-run
```

The rendered DayOA target is `produce_inflection_delivery_set`. Review the dry-run plan before launching live packaging. It should not schedule alignment or core variant-calling work for an already-computed analysis root.

## Exports

Export one exact analysis root:

```bash
dyec export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --source-path "$ANALYSIS_ROOT" \
  --destination-s3-uri s3://<analysis-bucket>/<prefix>/$CLUSTER/$ANALYSIS_ID/ \
  --output-dir ./export-receipts/$ANALYSIS_ID
```

Use export helpers for existing receipts or bulk operation surfaces:

```bash
dyec exports --help
```

Verify `fsx_export.yaml`, object counts, and expected S3 outputs before cleanup.

## Cost and pricing helpers

Spot lifecycle logs:

```bash
dyec pricing spot-logs \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --output spot_prices.csv
```

Cost-center examples:

```bash
dyec cost-centers ensure-registry --profile "$AWS_PROFILE"
dyec cost-centers create project-a --monthly-cap-usd 200 --allowed-user ubuntu
dyec --json cost-centers show project-a
dyec --json cost-centers list --status active
dyec --json cost-centers usage project-a --month 2026-07
dyec --json cost-centers refresh-usage project-a \
  --cluster project-a \
  --month 2026-07 \
  --profile "$AWS_PROFILE" \
  --dry-run
```

Budget/cap changes require the workspace double-approval process before live mutation.

AWS readiness and quota helpers:

```bash
dyec aws --help
dyec pricing --help
```

Use these before live cluster creation or quota-heavy launches.

## Tests and validation helpers

Local tests:

```bash
dyec tests pytest
dyec tests pytest --coverage
python -m pytest tests/test_cli_registry_v2.py -q
```

Catalog validation:

```bash
dyec --json tests command-catalog \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --command-codes dyec-released-core \
  --evidence-s3-uri s3://<evidence-root>/ \
  --dry-run
```

Performance profile:

```bash
dyec --json tests command-catalog-performance \
  --benchmark-rows ./benchmark_rows.tsv \
  --output-dir ./command_catalog_performance
```

## Recommended full CLI-only launch sequence

1. Activate local DYEC:

   ```bash
   cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
   source ./activate
   ```

2. Verify cluster/headnode:

   ```bash
   dyec --json cluster describe --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER"
   dyec --json headnode run --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" 'hostname; command -v dyec; command -v aws'
   ```

3. Generate or validate the local config:

   ```bash
   dyec --json identities validate --manifest-dir ./config
   ```

4. Render the catalog command:

   ```bash
   dyec --json catalog render hybrid_ilmn_ont_hiomrs_kitchensink \
     --analysis-id "$ANALYSIS_ID" \
     --executing-entity "$CLUSTER" \
     --profile "$AWS_PROFILE" \
     --region "$REGION" \
     --cluster "$CLUSTER" \
     --manifest-dir ./config \
     --payload-staging-s3-uri "$STAGING_S3_URI" \
     --project "$PROJECT" \
     --dry-run
   ```

5. Launch the dry run:

   ```bash
   dyec --json catalog launch hybrid_ilmn_ont_hiomrs_kitchensink \
     --analysis-id "$ANALYSIS_ID" \
     --executing-entity "$CLUSTER" \
     --profile "$AWS_PROFILE" \
     --region "$REGION" \
     --cluster "$CLUSTER" \
     --manifest-dir ./config \
     --payload-staging-s3-uri "$STAGING_S3_URI" \
     --session-name "${ANALYSIS_ID}-dryrun" \
     --project "$PROJECT" \
     --dry-run
   ```

6. Inspect dry-run status/logs:

   ```bash
   dyec --json workflow status --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" --session "${ANALYSIS_ID}-dryrun"
   dyec workflow logs --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER" --session "${ANALYSIS_ID}-dryrun" --lines 200
   ```

7. Launch live only if the plan is correct:

   ```bash
   dyec --json catalog launch hybrid_ilmn_ont_hiomrs_kitchensink \
     --analysis-id "$ANALYSIS_ID" \
     --executing-entity "$CLUSTER" \
     --profile "$AWS_PROFILE" \
     --region "$REGION" \
     --cluster "$CLUSTER" \
     --manifest-dir ./config \
     --payload-staging-s3-uri "$STAGING_S3_URI" \
     --session-name "$ANALYSIS_ID" \
     --project "$PROJECT"
   ```

8. Monitor the exact analysis root:

   ```bash
   dyec analysis status full \
     --analysis-root "$ANALYSIS_ROOT" \
     --profile "$AWS_PROFILE" \
     --region "$REGION" \
     --cluster "$CLUSTER" \
     --tail-lines 1000
   ```

9. Export after success:

   ```bash
   dyec export \
     --profile "$AWS_PROFILE" \
     --region "$REGION" \
     --cluster "$CLUSTER" \
     --source-path "$ANALYSIS_ROOT" \
     --destination-s3-uri s3://<analysis-results-bucket>/<prefix>/$CLUSTER/$ANALYSIS_ID/ \
     --output-dir ./export-receipts/$ANALYSIS_ID
   ```

## Release conventions

Package releases use numeric annotated tags with no leading `v`:

```bash
git tag -a <next-version> -m "Release <next-version>"
git cat-file -t <next-version>
git push origin <next-version>
```

`git cat-file -t <tag>` must return `tag`, not `commit`.

Both source and packaged global config files must be kept in sync for self-pins:

```text
config/daylily_cli_global.yaml
daylily_ec/resources/payload/config/daylily_cli_global.yaml
```
