# Bjuice validation bundle handoff

This is an operator handoff for one example bundle, `bundle1a`. It explains the checked-in
source and configuration artifacts and the future DYEC command-catalog sequence for DRA
mounting, sequencing-run QC, and Bjuice plus Inflection packaging.

Nothing in the preparation of this handoff created a DRA, attached a mount, started a
controller, submitted a Slurm job, or wrote to S3. The current receipts say
`LAUNCH_BLOCKED` because every candidate canonical source prefix is missing `OOW.done`.
`CopyComplete.txt`, ONT final summaries, and object presence are useful readiness evidence,
but they do not replace OWY's publication sentinel.

## Released baseline and artifacts

Use released DYEC `18.0.43`, its immutable `dyec_builds.18.0.43` catalog snapshot, and
DayOA `15.0.24`.

| Artifact | Purpose |
|---|---|
| `docs/jem/Bjuice_guidance.md` | Full five-bundle inventory, exclusions, hashes, mount projections, and future manual DayOA dry-run sequence. |
| `docs/plans/20260818T105011Z_bjuice_validation_source_config_ledger.md` | Execution ledger and terminal configuration state. |
| `docs/jem/bjuice_validation/source_spec.json` | Reviewed bundle topology and exact source/mount roots. |
| `docs/jem/bjuice_validation/source_inventory.json` | Read-only S3 inventory and readiness snapshot. |
| `docs/jem/bjuice_validation/sample_crosswalk.tsv` | Workbook-derived aliases, pairing state, Set, chip, position, and barcode. |
| `docs/jem/bjuice_validation/configs/bundle1a/` | Six DayOA manifests, Bundle 1a runtime YAML, and generation receipt. |

The Bundle 1a capsule contains:

- 28 biological samples and 32 analysis units; HG001 and NA10684 technical replicates are
  distinct AUs.
- 64 sequencing inputs and 64 AU/input links: exactly one ILMN and one ONT input per AU.
- Four positive-control samples: HG001, HG002, HG003, and HG004.
- Full available Illumina lane coverage, ONT `[0,24)` hours, numeric chromosomes `1-25`,
  slim consensus, and analytical Inflection packaging.
- No invented EUIDs.

The hybrid capsule does **not** contain `NTC`, `Undetermined`, or one-sided workbook rows.
Run-level QC below still covers their files because it operates on complete mounted run
directories. Bjuice cannot safely analyze an NTC until a reviewed ILMN+ONT pairing (or a
separately approved single-modality AU contract) is added; do not invent an ONT mate.

## Bundle 1a topology

```text
Illumina run
s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260624_LH01106_0012_A23WW3CLT4/
  -> /fsx/run_dir_mounts/20260624_LH01106_0012_A23WW3CLT4/

ONT Set1 through Set8
s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260626_ONT_BGS_ValR1_Set{1..8}/
  via one parent DRA:
s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/
  -> /fsx/run_dir_mounts/pca100-2026/
```

The ONT parent DRA exposes all eight Set directories. Do not create eight overlapping ONT
DRAs. DRAs belong to a particular FSx filesystem, so repeat the read-only inventory and
mount procedure for each target cluster if SeqQC and Bjuice use different clusters.

## Gate 0: read-only checks

Set explicit operator-owned values; do not guess them:

```bash
export AWS_PROFILE=lsmc
export AWS_REGION=us-west-2
export DYEC_VERSION=18.0.43
export DAYOA_TAG=15.0.24
export CLUSTER=<target-cluster>
export EXECUTING_ENTITY=<operator-or-service-identity>
export PROJECT=<approved-project>
export COST_CENTER=<active-approved-cost-center>
export BUNDLE_DIR=<absolute-path-to-reviewed-bundle1a-directory>
```

Confirm identity, immutable catalog state, cluster/FSx resolution, existing DRAs, and OWY
publication evidence before any mutation:

```bash
aws sts get-caller-identity --profile "$AWS_PROFILE" --region "$AWS_REGION"
dyec --version
dyec --json catalog show illumina_run_qc --dyec-version "$DYEC_VERSION"
dyec --json catalog show ont_run_qc --dyec-version "$DYEC_VERSION"
dyec --json catalog show bjuice-v2-hg002-custom-multi-analysis-unit-hiomr2-kitchensink-mega --dyec-version "$DYEC_VERSION"
dyec --json mounts list --cluster "$CLUSTER" --profile "$AWS_PROFILE" --region "$AWS_REGION"
```

Check `OOW.done` at the exact Illumina prefix and at each of the eight exact ONT Set
prefixes. If any check returns `404`, stop; that is the current recorded state. Inspect the
existing DRA list for exact or overlapping S3 prefixes and reuse an exact usable association
instead of creating a duplicate.

The `18.0.43` catalog pins DayOA `15.0.24`, but `catalog show` currently reports
`validation_pending: true` for the two RunQC entries because their last recorded live proof
used DayOA `15.0.9`. Record explicit operator acceptance or new validation evidence before
using them at `15.0.24`.

## Create or attach the two read-only DRAs

These commands are future mutation templates. Run them only after Gate 0 passes and the
operator has explicitly authorized mount creation. The long timeout is intentional: a new
FSx association may remain `CREATING` for about 40 minutes.

```bash
export ILMN_RUN=20260624_LH01106_0012_A23WW3CLT4
export ILMN_S3=s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260624_LH01106_0012_A23WW3CLT4/
export ONT_MOUNT=pca100-2026
export ONT_PARENT_S3=s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/

dyec --json mounts create "$ILMN_S3" \
  --purpose run \
  --cluster "$CLUSTER" \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --mount-id "$ILMN_RUN" \
  --run-id "$ILMN_RUN" \
  --platform ILMN \
  --file-system-path "/run_dir_mounts/$ILMN_RUN" \
  --read-only \
  --batch-import-metadata-on-create \
  --auto-import NEW,CHANGED \
  --wait \
  --timeout-seconds 5400

dyec --json mounts create "$ONT_PARENT_S3" \
  --purpose run \
  --cluster "$CLUSTER" \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --mount-id "$ONT_MOUNT" \
  --run-id "$ONT_MOUNT" \
  --platform ONT \
  --file-system-path "/run_dir_mounts/$ONT_MOUNT" \
  --read-only \
  --batch-import-metadata-on-create \
  --auto-import NEW,CHANGED \
  --wait \
  --timeout-seconds 5400
```

Do not set `--auto-export`, `--no-read-only`, or a writeback override. Capture the returned
association IDs, then verify both headnode paths:

```bash
dyec --json mounts verify --mount-id "$ILMN_RUN" --cluster "$CLUSTER" --platform ILMN --profile "$AWS_PROFILE" --region "$AWS_REGION" --timeout-seconds 900
dyec --json mounts verify --mount-id "$ONT_MOUNT" --cluster "$CLUSTER" --platform ONT --profile "$AWS_PROFILE" --region "$AWS_REGION" --timeout-seconds 900
```

Do not delete or rotate a DRA as part of this handoff. That needs a separate, exact teardown
decision after downstream work is terminal.

## Run-level SeqQC for every run-folder occupant

Create one run-context TSV for the Illumina run and one for each ONT Set. These jobs inspect
the complete run directories, so their reports cover ordinary samples, positive controls,
NTC, Undetermined, and other run-folder content. They do not use the hybrid six-manifest
filter.

The TSV header is:

```tsv
RUNID	PLATFORM	RUN_DIR	SOURCE_S3_URI	MOUNT_ID	SAMPLE_SHEET	BASECALLING_STATE	RUN_STATUS	OUTPUT_ROOT	REGION	PROFILE
```

The Illumina row is:

```tsv
20260624_LH01106_0012_A23WW3CLT4	ILMN	/fsx/run_dir_mounts/20260624_LH01106_0012_A23WW3CLT4/	s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260624_LH01106_0012_A23WW3CLT4/	20260624_LH01106_0012_A23WW3CLT4	/fsx/run_dir_mounts/20260624_LH01106_0012_A23WW3CLT4/SampleSheet.csv	basecalled_fastq	complete	results/runs/20260624_LH01106_0012_A23WW3CLT4	us-west-2	lsmc
```

For ONT Set `N`, use one file containing this row with `N` replaced by `1` through `8`:

```tsv
20260626_ONT_BGS_ValR1_SetN	ONT	/fsx/run_dir_mounts/pca100-2026/20260626_ONT_BGS_ValR1_SetN/	s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260626_ONT_BGS_ValR1_SetN/	pca100-2026		basecalled_fastq	complete	results/runs/20260626_ONT_BGS_ValR1_SetN	us-west-2	lsmc
```

Render first. Rendering is read-only and should show DayOA `15.0.24`, the exact run-context
file, and the expected target. Example for Illumina:

```bash
export ILMN_CONTEXT=<absolute-path-to-illumina-runs.tsv>
export ANALYSIS_ID=bjuice-val-bundle1a-ilmn-runqc-<timestamp>

dyec --json catalog render illumina_run_qc \
  --dyec-version "$DYEC_VERSION" \
  --git-tag "$DAYOA_TAG" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$EXECUTING_ENTITY" \
  --cluster "$CLUSTER" \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --remote-user ubuntu \
  --project "$PROJECT" \
  --run-context-file "$ILMN_CONTEXT" \
  --session-name "$ANALYSIS_ID" \
  --dry-run
```

After review, the future dry-run controller uses the same arguments with `catalog launch`.
This is a controller launch even though the DayOA command contains `-n`, so it still needs
explicit authorization:

Re-run the exact reviewed command after changing only `catalog render` to
`catalog launch`; retain `--dry-run`.

For each Set `1..8`, repeat with a unique analysis ID and context file:

```bash
dyec --json catalog render ont_run_qc \
  --dyec-version "$DYEC_VERSION" \
  --git-tag "$DAYOA_TAG" \
  --analysis-id "bjuice-val-bundle1a-ont-set${SET}-runqc-<timestamp>" \
  --executing-entity "$EXECUTING_ENTITY" \
  --cluster "$CLUSTER" \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --remote-user ubuntu \
  --project "$PROJECT" \
  --run-context-file "<absolute-path-to-ont-set${SET}-runs.tsv>" \
  --session-name "bjuice-val-bundle1a-ont-set${SET}-runqc-<timestamp>" \
  --dry-run
```

Only after a dry-run controller is terminal with exit code `0` and zero Slurm submissions
may an operator request a live continuation using the same analysis root, checkout, inputs,
and controller context with only dry-run mode removed. This handoff does not authorize it.

## Bjuice plus Inflection: command-catalog blocker

Do **not** launch Bundle 1a with
`bjuice-v2-hg002-custom-multi-analysis-unit-hiomr2-kitchensink-mega` as currently released.
Although its targets and flags match, the immutable entry is explicitly HG002-specific and
hardcodes:

```text
--configfile config/hg002_bjuice_v2_multi_analysis_unit_hiomr2.yaml
```

The Bundle 1a capsule instead requires:

```text
docs/jem/bjuice_validation/configs/bundle1a/bjuice_validation_bundle1a_hiomr2.yaml
```

`--manifest-dir` stages only the six manifests; it does not replace that hardcoded runtime
YAML. A direct catalog launch would therefore apply the wrong overlay to a mixed-sample
cohort. Do not use it as a fallback.

The next safe command-catalog implementation must add a generic, released entry (or a
schema-validated runtime-config materialization interface) that:

- accepts the exact six Bundle 1a manifests and the bundle runtime YAML;
- copies the content-addressed YAML inside the fresh DayOA clone and passes it with
  `--configfile`;
- pins DayOA `15.0.24` and the two targets
  `produce_sentdhiomr2_slim_kitchensink_mega` and
  `produce_sentdhiomr2_inflection_analytical_package`;
- preserves `-j 345 -T 1 -p -k`, per-AU ONT `[0,24)`, chromosome scope `1-25`, raw FASTQ
  mode, slim consensus, and analytical Inflection packaging;
- requires the exact Bundle 1a receipt/manifests, an active cost center, verified mounts,
  and terminal SeqQC evidence; and
- remains hybrid-only unless a separately reviewed NTC AU contract is approved.

Once such a command is released, its safe invocation shape is:

```bash
export BJUICE_COMMAND=<released-generic-bjuice-command-id>
export ANALYSIS_ID=bjuice-val-bundle1a-<timestamp>

dyec --json catalog render "$BJUICE_COMMAND" \
  --dyec-version <release-containing-the-generic-command> \
  --git-tag "$DAYOA_TAG" \
  --analysis-id "$ANALYSIS_ID" \
  --executing-entity "$EXECUTING_ENTITY" \
  --cluster "$CLUSTER" \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --remote-user ubuntu \
  --project "$COST_CENTER" \
  --cost-center "$COST_CENTER" \
  --manifest-dir "$BUNDLE_DIR" \
  --session-name "$ANALYSIS_ID" \
  --dry-run
```

For a large manifest payload, an explicit `--payload-staging-s3-uri` may be required. That
relay writes to S3 and must be separately authorized and recorded. Never enable stage
discovery or substitute a different manifest directory.

## Operator completion record

Record, at minimum: AWS identity; DYEC/tag/commit and DayOA tag/commit; cluster and FSx ID;
the two DRA association IDs and verified paths; all nine RunQC analysis IDs, rendered
commands, dry-run/live exit codes, and report URIs; Bundle 1a manifest/runtime hashes; the
generic Bjuice catalog command and release; cost center; Bjuice analysis ID; controller exit
code; and final Inflection package/report URIs.

Until OWY publication evidence is restored and the generic mixed-sample catalog contract is
released, configuration production is complete but live launch remains blocked.
