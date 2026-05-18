# Historical: LSMC Run Directory Mounting & Run-Level Analysis Specification

> Historical implementation specification. This file is preserved for design
> provenance and cross-repo context. It is no longer the current DayEC operator
> guide. Use `docs/dra_fsx_strategy.md`, `docs/operations.md`, and
> `docs/cli_reference.md` for current DRA, mount, export, and catalog behavior.

**Status:** implementation specification v0.1  
**Date:** 2026-05-17  
**Audience:** Codex Desktop multi-agent implementation team working across:

- `daylily-ephemeral-cluster` / **DayEC**
- `daylily-omics-analysis` / **DayOA**
- `ursa`

This specification adds read-oriented FSx/S3 run-directory mounts to the existing Daylily execution stack, while preserving the current sample-manifest staging behavior and the `samples.tsv` / `units.tsv` contract used by DayOA sample pipelines.

---

## 1. Executive decision

Use **Amazon FSx for Lustre Data Repository Associations** as the implementation mechanism for “mounting” an arbitrary S3 bucket prefix into an already-running FSx file system. The user-facing command can say “mount run directory,” but internally this is an **FSx DRA association** from:

```text
s3://some-run-bucket/path/to/run-dir/
```

to:

```text
FSx API path:       /run_dir_mounts/<mount_id>/
Headnode path:      /fsx/run_dir_mounts/<mount_id>/
Worker path:        /fsx/run_dir_mounts/<mount_id>/
```

The EC2 / ParallelCluster nodes continue to mount the FSx file system once. New run directories appear as additional directories within that mounted namespace.

### Primary goals

1. **Avoid unnecessary data movement.** Raw sequencing run directories should be read directly from S3 through FSx for run QC, demux/basecalling, and raw data inspection.
2. **Keep sample staging intact.** The existing `daylily-ec samples stage` behavior must continue to copy staged sample data to the reference bucket and generate `samples.tsv` / `units.tsv`.
3. **Add a mounted-input mode.** Sample manifests can point to files already visible under `/fsx/run_dir_mounts/...` and still produce valid `samples.tsv` / `units.tsv` without copying those files.
4. **Separate sample analysis from run analysis.** Command catalog, Ursa UI/API, and DayOA workflows should clearly distinguish sample-level WGS analysis from run-level QC/demux/basecalling workflows.
5. **Keep DayOA sample pipelines stable.** Existing sample-processing rules should require no semantic change when the generated `units.tsv` contains mounted local paths.
6. **Create a real run-analysis model.** Run-level DayOA outputs should live under `results/runs/<runid>/...`, not under sample-analysis result trees.

---

## 2. Architectural stance

### 2.1 Plane-aware placement

This feature sits in the **Execution Plane** and **Data Plane interface**:

- DayEC creates infrastructure links and launches execution.
- DayOA performs run-level and sample-level computational work.
- Ursa coordinates user actions and displays status.
- The S3 run directory remains data/artifact storage.
- Generated QC metrics, demux outputs, and run reports are evidence artifacts.

Neither DayEC nor DayOA should make release/QC disposition decisions. They emit evidence. Any pass/fail/release interpretation remains outside this implementation and belongs to the decision/release layer.

### 2.2 Read-only intent

A DRA is not a Linux read-only bind mount by itself. Enforce read-only semantics through policy and workflow design:

1. **No AutoExport by default.** The DRA must not export writes back to the source run bucket.
2. **Read-only S3 IAM.** The cluster role used for source run buckets should have `s3:GetObject`, `s3:ListBucket`, and related read/list permissions only.
3. **Write outputs elsewhere.** DayOA rules must never write inside `/fsx/run_dir_mounts/<mount_id>/`; all outputs go to DayOA result directories and configured export destinations.
4. **Optional POSIX hardening.** After DRA availability, DayEC may run a headnode-side permission hardening step, but this is secondary to IAM and output-path separation.
5. **CLI contract.** The default command should be named and documented as read-only. Any future read-write export behavior must be an explicit admin-only extension.

---

## 3. Current codebase observations

### 3.1 DayEC

Relevant files:

```text
daylily_ec/cli.py
daylily_ec/stage_samples.py
daylily_ec/repositories.py
config/daylily_available_repositories.yaml
```

Current behavior:

- `daylily-ec samples stage` is registered in `cli.py` and implemented by `stage_samples.py`.
- `samples stage` accepts a sample manifest and creates timestamped `samples.tsv` and `units.tsv`.
- Current staging directives are effectively:
  - blank / default staging
  - `stage_data`
  - `pass_through`
- `pass_through` currently expects inputs to be visible under `/fsx/data` or `/data`.
- `is_headnode_visible_path()` currently recognizes only:

```text
/fsx/data
/fsx/data/*
/data
/data/*
```

- The command catalog in `config/daylily_available_repositories.yaml` is v1 and consists of sample-analysis launch profiles.
- `AnalysisCommand` in `repositories.py` currently assumes launcher `workflow_launch` and has no command class/category.

### 3.2 DayOA

Relevant files:

```text
workflow/Snakefile
workflow/rules/common.smk
workflow/rules/bclconvert.smk
workflow/rules/run_qc_reports.smk
docs/workflows/bclconvert_bootstrap.md
docs/ops/multiqc_qc_targets.md
```

Current behavior:

- `workflow/rules/common.smk` loads `samples.tsv` and `units.tsv` from config and derives sample metadata from them.
- Existing sample rules can consume arbitrary file paths if `units.tsv` points to valid mounted paths.
- `workflow/rules/bclconvert.smk` already contains a BCL Convert bootstrap path with targets:
  - `produce_bclconvert_fastqs`
  - `produce_bclconvert_metrics`
  - `produce_bclconvert_multiqc`
  - `produce_bclconvert_fastqs_and_metrics`
- `workflow/rules/run_qc_reports.smk` already has run-QC targets:
  - `produce_illumina_run_qc`
  - `produce_ont_run_qc`
  - `produce_ultima_run_qc`
  - `produce_run_qc_reports`
- Current Illumina run QC is S3-fetch oriented: it copies selected run-folder metrics from a configured S3 URI into a local subset before running InterOp / CheckQC / MultiQC.
- Current run-QC outputs are under a sample-oriented layout such as `results/day/<build>/run_qc/...`; this should move or be bridged to `results/runs/<runid>/...` for run-level work.

### 3.3 Ursa

Relevant files:

```text
daylib_ursa/ephemeral_cluster/runner.py
daylib_ursa/analysis_commands.py
daylib_ursa/analysis_jobs.py
daylib_ursa/staging_jobs.py
daylib_ursa/resource_store.py
daylib_ursa/workset_api.py
```

Current behavior:

- `DaylilyEcClient` wraps `daylily-ec` commands and currently exposes cluster, workflow, repository, staging, and deletion flows.
- Ursa loads the DayEC command catalog for analysis command display and launch previews.
- Ursa staging jobs call `daylily-ec samples stage`, parse stdout for `Remote FSx stage directory:`, then use that stage dir for sample analysis.
- Ursa has linked-bucket resource/API concepts that can be reused for selecting S3 run prefixes.
- Ursa currently models sample staging and sample analysis jobs, but not run directory mounts or run analysis jobs.

---

## 4. Target user flows

### 4.1 Mount a run directory into a running cluster

Canonical command:

```bash
daylily-ec mounts create \
  --cluster lsmc-prod-wgs-01 \
  --region us-east-1 \
  --profile lsmc-prod \
  --s3-uri s3://sequencer-run-bucket/runs/250517_A00123_0456_AHFG7MDSX7/ \
  --mount-id 250517_A00123_0456_AHFG7MDSX7 \
  --platform ILMN \
  --read-only \
  --batch-import-metadata-on-create \
  --wait
```

Alias command for the requested mental model:

```bash
daylily-ec mount rundir \
  --cluster lsmc-prod-wgs-01 \
  --region us-east-1 \
  --profile lsmc-prod \
  --s3-uri s3://sequencer-run-bucket/runs/250517_A00123_0456_AHFG7MDSX7/ \
  --run-id 250517_A00123_0456_AHFG7MDSX7 \
  --platform ILMN \
  --wait
```

Expected text output:

```text
Run directory mounted: 250517_A00123_0456_AHFG7MDSX7
Association ID: dra-abc123
FSx file system: fs-0123456789abcdef0
FSx API path: /run_dir_mounts/250517_A00123_0456_AHFG7MDSX7/
Headnode path: /fsx/run_dir_mounts/250517_A00123_0456_AHFG7MDSX7/
Source S3 URI: s3://sequencer-run-bucket/runs/250517_A00123_0456_AHFG7MDSX7/
Lifecycle: AVAILABLE
```

JSON mode should return a stable object:

```json
{
  "mount_id": "250517_A00123_0456_AHFG7MDSX7",
  "run_id": "250517_A00123_0456_AHFG7MDSX7",
  "platform": "ILMN",
  "cluster_name": "lsmc-prod-wgs-01",
  "region": "us-east-1",
  "fsx_file_system_id": "fs-0123456789abcdef0",
  "association_id": "dra-abc123",
  "data_repository_path": "s3://sequencer-run-bucket/runs/250517_A00123_0456_AHFG7MDSX7/",
  "file_system_path": "/run_dir_mounts/250517_A00123_0456_AHFG7MDSX7/",
  "headnode_path": "/fsx/run_dir_mounts/250517_A00123_0456_AHFG7MDSX7/",
  "read_only": true,
  "auto_import_events": ["NEW", "CHANGED"],
  "auto_export_events": [],
  "batch_import_metadata_on_create": true,
  "lifecycle": "AVAILABLE",
  "created_at": "2026-05-17T00:00:00Z"
}
```

### 4.2 Run Illumina run QC directly on the mounted run directory

```bash
daylily-ec workflow launch \
  --cluster lsmc-prod-wgs-01 \
  --region us-east-1 \
  --profile lsmc-prod \
  --repository daylily-omics-analysis \
  --destination s3://lsmc-results/dayoa/ \
  --git-tag <dayoa-tag> \
  --dy-command "bin/day_run produce_illumina_run_qc --config run_context_file=config/runs.tsv -p -j 8 -k"
```

The generated run context should point DayOA to:

```text
/fsx/run_dir_mounts/250517_A00123_0456_AHFG7MDSX7/
```

Expected result layout:

```text
results/runs/250517_A00123_0456_AHFG7MDSX7/run_qc/illumina/
  interop_summary.csv
  interop_index_summary.csv
  checkqc.json
  summary.tsv
  summary.html
  multiqc_report.html
  versions.yml
```

### 4.3 Run BCL Convert directly on a mounted Illumina run folder

```bash
daylily-ec workflow launch \
  --cluster lsmc-prod-wgs-01 \
  --region us-east-1 \
  --profile lsmc-prod \
  --repository daylily-omics-analysis \
  --destination s3://lsmc-results/dayoa/ \
  --git-tag <dayoa-tag> \
  --dy-command "bin/day_run produce_bclconvert_fastqs_and_metrics --config run_context_file=config/runs.tsv -p -j 20 -k"
```

Expected result layout:

```text
results/runs/<runid>/bclconvert/
  fastqs/
  Reports/
  InterOp/
  tables/generated.units.tsv
  metrics/
  multiqc_report.html
```

The generated `units.tsv` may then be used as the input contract for sample-level DayOA processing.

### 4.4 Use mounted FASTQs/CRAMs in sample analysis without staging bytes

Manifest rows can point to local mounted files:

```tsv
RUN_ID	SAMPLE_ID	EXPERIMENTID	SAMPLE_TYPE	LIB_PREP	SEQ_VENDOR	SEQ_PLATFORM	LANE	SEQBC_ID	ILMN_R1_FQ	ILMN_R2_FQ	STAGE_DIRECTIVE	MOUNT_ID	MOUNT_SOURCE_S3_URI
RUN123	SAMPLE_A	EXP1	NORMAL	PCRFREE	ILMN	NOVASEQX	1	S1	/fsx/run_dir_mounts/RUN123/fastqs/SAMPLE_A_R1.fastq.gz	/fsx/run_dir_mounts/RUN123/fastqs/SAMPLE_A_R2.fastq.gz	mounted_readonly	RUN123	s3://sequencer-run-bucket/runs/RUN123/
```

`daylily-ec samples stage` should then:

- validate mounted paths syntactically;
- optionally verify them on the headnode if `--cluster` is provided;
- not copy FASTQ/CRAM/BAM bytes;
- still create `samples.tsv` and `units.tsv`;
- still upload config TSVs to the stage/config location as it does today.

---

## 5. DayEC implementation specification

### 5.1 New module layout

Add:

```text
daylily_ec/fsx.py
daylily_ec/run_mounts.py
daylily_ec/state/run_mounts.py     # optional if state store is separated
tests/test_run_mounts.py
```

`fsx.py` responsibilities:

- resolve FSx file system ID for a ParallelCluster cluster;
- call `aws fsx describe-data-repository-associations`;
- call `aws fsx create-data-repository-association`;
- call `aws fsx delete-data-repository-association`;
- poll DRA lifecycle status;
- detect overlapping file-system paths and S3 data repository paths;
- normalize S3 URIs with trailing slash.

`run_mounts.py` responsibilities:

- parse and validate mount requests;
- sanitize `mount_id` and `run_id`;
- compute FSx API path and headnode path;
- enforce read-only default policy;
- create/list/describe/delete mount records;
- render text and JSON outputs;
- optionally verify path availability on the headnode through existing SSM helpers.

### 5.2 Safe mount ID rules

`mount_id` must:

- match `^[A-Za-z0-9._-]+$`;
- not contain `/`, `..`, whitespace, shell metacharacters, or URL encoding ambiguity;
- be limited to a sane length, recommended max `128` characters;
- be unique per cluster/FSx file system while an active DRA exists.

If the user provides `--run-id` but not `--mount-id`, derive `mount_id` from `run_id` using the same sanitization rules.

### 5.3 Canonical path mapping

| Concept | Value |
|---|---|
| Mount root inside FSx API | `/run_dir_mounts/` |
| DRA file-system path | `/run_dir_mounts/<mount_id>/` |
| Local/headnode path | `/fsx/run_dir_mounts/<mount_id>/` |
| Manifest-visible path | `/fsx/run_dir_mounts/<mount_id>/...` |

Never pass `/fsx/run_dir_mounts/...` to the FSx API. The FSx API path is inside the FSx namespace and must be `/run_dir_mounts/<mount_id>/`.

### 5.4 CLI commands

Register new command group(s) in `daylily_ec/cli.py`.

Canonical group:

```text
daylily-ec mounts list
daylily-ec mounts create
daylily-ec mounts describe
daylily-ec mounts delete
daylily-ec mounts verify
```

Friendly alias:

```text
daylily-ec mount rundir
```

The alias should delegate to `mounts create` and should not duplicate implementation.

#### `mounts create`

Arguments/options:

```text
--cluster                         required unless --fsx-file-system-id provided
--fsx-file-system-id              optional explicit override
--region                          required
--profile                         optional, follows existing DayEC behavior
--s3-uri                          required, bucket or prefix
--mount-id                        optional, derived from run_id or S3 basename
--run-id                          optional metadata
--platform                        optional enum: ILMN, ONT, ULTIMA, PACBIO, OTHER
--file-system-path                optional override; default /run_dir_mounts/<mount_id>/
--read-only / --no-read-only      default read-only
--batch-import-metadata-on-create default true for completed run dirs
--auto-import                     default NEW,CHANGED; allow none|new|changed|deleted|all
--auto-export                     forbidden unless --allow-writeback-admin is set
--wait / --no-wait                default wait for interactive; no-wait okay for automation
--timeout-seconds                 default 900
--tag KEY=VALUE                   repeatable
--json                            existing global mode
```

Implementation policy:

- reject overlapping FSx paths;
- reject overlapping S3 paths;
- reject if active DRA count is already 8;
- reject `/` file-system path;
- reject AutoExport unless explicitly overridden by an admin-only flag;
- create DRA with `--batch-import-meta-data-on-create` by default unless disabled;
- persist mount record after create;
- if `--wait`, poll until lifecycle `AVAILABLE` or terminal failure.

#### `mounts list`

Must reconcile local state with AWS DRA state.

```bash
daylily-ec mounts list --cluster lsmc-prod-wgs-01 --region us-east-1 --profile lsmc-prod
```

Output columns:

```text
MOUNT_ID  RUN_ID  PLATFORM  LIFECYCLE  ASSOCIATION_ID  HEADNODE_PATH  SOURCE_S3_URI  CREATED_AT
```

#### `mounts describe`

Lookup by either `--mount-id` or `--association-id`.

#### `mounts delete`

```bash
daylily-ec mounts delete \
  --cluster lsmc-prod-wgs-01 \
  --region us-east-1 \
  --profile lsmc-prod \
  --mount-id 250517_A00123_0456_AHFG7MDSX7 \
  --wait
```

Default deletion behavior:

- delete the DRA;
- do not delete S3 objects;
- do not export anything;
- do not remove DayOA outputs;
- update mount record state to `DELETED`.

Add a separate explicitly dangerous option only if AWS deletion leaves FSx-local cached content that must be cleaned:

```text
--delete-fsx-cache
```

Default must be no destructive cleanup beyond DRA removal.

#### `mounts verify`

Use existing headnode SSM capability to run:

```bash
test -d /fsx/run_dir_mounts/<mount_id>
find /fsx/run_dir_mounts/<mount_id> -maxdepth 2 | head
```

For Illumina, also look for minimal run-folder markers:

```text
RunInfo.xml
RunParameters.xml or runParameters.xml
InterOp/
Data/Intensities/BaseCalls/ or BCL Convert-compatible directory
```

For ONT, look for at least one of:

```text
final_summary*.txt
sequencing_summary*.txt
*.pod5
*.fastq.gz
report*.html
```

For Ultima, keep this permissive initially and look for platform metrics CSV/JSON and FASTQ/CRAM outputs if present.

### 5.5 Mount record schema

Persist JSON records in the existing DayEC state area. Recommended logical key:

```text
run_mounts/<region>/<cluster_name>/<mount_id>.json
```

Schema:

```json
{
  "schema_version": 1,
  "mount_id": "RUN123",
  "run_id": "RUN123",
  "platform": "ILMN",
  "cluster_name": "lsmc-prod-wgs-01",
  "region": "us-east-1",
  "profile_hint": "lsmc-prod",
  "fsx_file_system_id": "fs-0123456789abcdef0",
  "association_id": "dra-abc123",
  "file_system_path": "/run_dir_mounts/RUN123/",
  "headnode_path": "/fsx/run_dir_mounts/RUN123/",
  "data_repository_path": "s3://sequencer-run-bucket/runs/RUN123/",
  "read_only": true,
  "auto_import_events": ["NEW", "CHANGED"],
  "auto_export_events": [],
  "batch_import_metadata_on_create": true,
  "lifecycle": "AVAILABLE",
  "created_at": "2026-05-17T00:00:00Z",
  "updated_at": "2026-05-17T00:00:00Z",
  "created_by": "local-username-or-aws-arn-if-available",
  "tags": {
    "lsmc:purpose": "run-dir-mount"
  }
}
```

---

## 6. DayEC `samples stage` extension

### 6.1 Preserve current behavior

Do not break existing manifests. Existing users should be able to continue using:

- blank staging behavior;
- `STAGE_DIRECTIVE=stage_data`;
- `STAGE_DIRECTIVE=pass_through` for `/fsx/data` and `/data` paths;
- current `samples.tsv` and `units.tsv` headers and contents.

### 6.2 Add explicit mounted-input directive

Add:

```text
STAGE_DIRECTIVE=mounted_readonly
```

Semantics:

- input bytes are already visible on the headnode/worker through `/fsx/run_dir_mounts/<mount_id>/...`;
- DayEC must not copy these bytes to the reference bucket;
- DayEC must still create `samples.tsv` and `units.tsv`;
- paths in `units.tsv` remain the mounted local paths;
- generated config files are still staged/uploaded as today.

This directive should be an alias of pass-through for data movement, but with stricter path validation and clearer audit metadata.

### 6.3 New manifest columns

Add to `ALLOWED_MANIFEST_FIELDS`:

```text
MOUNT_ID
MOUNT_SOURCE_S3_URI
MOUNT_FSX_PATH
DATA_LOCALITY
```

Recommended usage:

| Column | Required? | Description |
|---|---:|---|
| `STAGE_DIRECTIVE` | yes for mounted inputs | `mounted_readonly` |
| `MOUNT_ID` | yes for mounted inputs | DayEC mount identifier |
| `MOUNT_SOURCE_S3_URI` | recommended | Original S3 prefix used for the DRA |
| `MOUNT_FSX_PATH` | optional | Expected mount root, default `/fsx/run_dir_mounts/<MOUNT_ID>/` |
| `DATA_LOCALITY` | optional | `mounted_readonly`, `reference_staged`, `external_s3`, etc. Future-friendly. |

Do not add these fields to `samples.tsv` or `units.tsv` unless DayOA needs them. Prefer to keep sample-pipeline contracts stable.

### 6.4 Headnode-visible path expansion

Extend `is_headnode_visible_path()` to accept:

```text
/fsx/run_dir_mounts
/fsx/run_dir_mounts/*
/run_dir_mounts
/run_dir_mounts/*    # optional alias if any headnode scripts normalize this way
```

But generated `units.tsv` should use `/fsx/run_dir_mounts/...` paths for clarity.

### 6.5 Validation rules

For `STAGE_DIRECTIVE=mounted_readonly`:

- all populated source file fields must be under `/fsx/run_dir_mounts/<MOUNT_ID>/`;
- `MOUNT_ID` must pass safe ID rules;
- `MOUNT_SOURCE_S3_URI`, if present, must be a valid `s3://` URI;
- do not call `aws s3 cp` for source files;
- do not call `build_reference_uri()` for mounted source files;
- multi-lane fastq logic should remain compatible if each lane’s R1/R2 paths are mounted local paths.

### 6.6 Optional headnode validation

Add optional flags to `samples stage`:

```text
--cluster
--validate-mounted-paths / --no-validate-mounted-paths
```

If `--cluster` and `--validate-mounted-paths` are provided, use SSM to verify paths exist on the headnode before writing final TSVs. If omitted, perform syntactic validation only and print a clear warning.

---

## 7. Command catalog v2

### 7.1 Schema changes

Upgrade:

```yaml
command_catalog_version: 2
```

Add fields to `AnalysisCommand`:

```yaml
command_class: sample_analysis | run_analysis
input_contract: sample_manifest | run_context | none
requires_staging: true | false
requires_run_mount: true | false
runtime_parameters:
  - run_id
  - run_mount_path
  - platform
```

Backwards compatibility:

- If `command_catalog_version == 1`, treat all existing commands as:

```yaml
command_class: sample_analysis
input_contract: sample_manifest
requires_staging: true
requires_run_mount: false
```

Recommended command classes:

```text
sample_analysis
run_analysis
```

### 7.2 Catalog split

Existing commands remain `sample_analysis`.

Add run-analysis commands:

```yaml
- command_id: illumina_run_qc
  display_name: "Illumina Run QC"
  command_class: run_analysis
  input_contract: run_context
  requires_staging: false
  requires_run_mount: true
  datasource: Illumina
  targets:
    - produce_illumina_run_qc
  compatible_platforms: [ILMN]
  compatible_data_modes: [run_dir_mount]

- command_id: illumina_bclconvert
  display_name: "Illumina BCL Convert"
  command_class: run_analysis
  input_contract: run_context
  requires_staging: false
  requires_run_mount: true
  datasource: Illumina
  targets:
    - produce_bclconvert_fastqs_and_metrics
  compatible_platforms: [ILMN]
  compatible_data_modes: [run_dir_mount]

- command_id: ont_run_qc
  display_name: "ONT Run QC"
  command_class: run_analysis
  input_contract: run_context
  requires_staging: false
  requires_run_mount: true
  datasource: ONT
  targets:
    - produce_ont_run_qc
  compatible_platforms: [ONT]
  compatible_data_modes: [run_dir_mount]

- command_id: ultima_run_qc
  display_name: "Ultima Run QC"
  command_class: run_analysis
  input_contract: run_context
  requires_staging: false
  requires_run_mount: true
  datasource: Ultima
  targets:
    - produce_ultima_run_qc
  compatible_platforms: [ULTIMA]
  compatible_data_modes: [run_dir_mount]
```

### 7.3 Launch rendering

Avoid trying to encode every run-specific value into static `dy_command` strings. Implement either:

1. a `run_context_file` generated by DayEC/Ursa, or
2. a templated command renderer with `runtime_parameters`.

Recommended: **run context file**.

The catalog command remains stable:

```yaml
dy_command: "bin/day_run produce_illumina_run_qc --config run_context_file=config/runs.tsv -p -j 8 -k"
dryrun_dy_command: "bin/day_run produce_illumina_run_qc --config run_context_file=config/runs.tsv -p -j 8 -k -n"
```

DayEC/Ursa writes `config/runs.tsv` into the launch stage/config directory.

---

## 8. DayOA run-analysis model

### 8.1 Add `runs.tsv`

Add a run-analysis input contract:

```text
config/runs.tsv
```

Header:

```tsv
RUNID	PLATFORM	RUN_DIR	SOURCE_S3_URI	MOUNT_ID	SAMPLE_SHEET	BASECALLING_STATE	RUN_STATUS	OUTPUT_ROOT	REGION	PROFILE
```

Column meanings:

| Column | Description |
|---|---|
| `RUNID` | Stable run identifier used in output path |
| `PLATFORM` | `ILMN`, `ONT`, `ULTIMA`, `PACBIO`, `OTHER` |
| `RUN_DIR` | Local path, usually `/fsx/run_dir_mounts/<mount_id>/` |
| `SOURCE_S3_URI` | Original S3 run prefix |
| `MOUNT_ID` | DayEC mount ID |
| `SAMPLE_SHEET` | For Illumina demux, path to `SampleSheet.csv`; may be inside `RUN_DIR` |
| `BASECALLING_STATE` | `raw_bcl`, `basecalled_fastq`, `pod5`, `bam`, `cram`, `unknown` |
| `RUN_STATUS` | `complete`, `active`, `unknown` |
| `OUTPUT_ROOT` | Optional override, default `results/runs/<RUNID>` |
| `REGION` | AWS region, if needed by rules |
| `PROFILE` | AWS profile, if needed; avoid `default` in production configs |

For single-run jobs, DayOA reads the first row unless a `run_id` override is provided.

### 8.2 Result layout

Adopt:

```text
results/runs/<runid>/
  run_context/
    runs.tsv
    validation.json
  run_qc/
    illumina/
    ont/
    ultima/
  bclconvert/
    fastqs/
    Reports/
    tables/generated.units.tsv
    metrics/
    multiqc_report.html
  basecalling/
    # future ONT/PacBio/Ultima raw signal handling
  logs/
  versions/
```

Do not remove existing `results/day/<build>/...` outputs immediately. For backwards compatibility, either:

- keep old targets writing old paths and add new run targets, or
- write new run paths and symlink/copy compatibility outputs if tests expect old locations.

### 8.3 Illumina run QC

Current `produce_illumina_run_qc` should be refactored to accept two metric source modes:

```text
mounted
s3
```

Mounted mode:

- read directly from `RUN_DIR` in `runs.tsv`;
- copy or symlink a minimal metric subset into `results/runs/<runid>/run_qc/illumina/source_run_subset/`;
- run InterOp tools against the subset;
- run CheckQC if configured;
- run MultiQC on InterOp and CheckQC outputs;
- write summary TSV/HTML and versions.

S3 mode:

- preserve current S3-fetch behavior for backwards compatibility.

Required outputs:

```text
results/runs/<runid>/run_qc/illumina/interop_summary.csv
results/runs/<runid>/run_qc/illumina/interop_index_summary.csv
results/runs/<runid>/run_qc/illumina/checkqc.json
results/runs/<runid>/run_qc/illumina/summary.tsv
results/runs/<runid>/run_qc/illumina/summary.html
results/runs/<runid>/run_qc/illumina/multiqc_report.html
```

### 8.4 BCL Convert

Existing BCL Convert rules should be moved or parameterized so outputs are run-scoped:

```text
results/runs/<runid>/bclconvert/...
```

Inputs:

- `RUN_DIR` from `runs.tsv`;
- `SAMPLE_SHEET` from `runs.tsv`, falling back to `<RUN_DIR>/SampleSheet.csv`;
- optional `samples.tsv` if sample metadata is already available.

Outputs:

- demultiplexed FASTQs;
- BCL Convert native reports;
- generated `units.tsv` at:

```text
results/runs/<runid>/bclconvert/tables/generated.units.tsv
```

This generated `units.tsv` becomes the bridge into sample analysis.

### 8.5 ONT run QC

Create/extend `produce_ont_run_qc` with an actual mounted-run implementation.

Input candidates under `RUN_DIR`:

```text
final_summary*.txt
sequencing_summary*.txt
report*.json
report*.html
*.pod5
*.fastq.gz
```

Recommended first implementation:

1. Parse `final_summary*.txt` and `sequencing_summary*.txt` if present.
2. Run long-read QC tools only when required inputs are present.
3. Generate a normalized `summary.tsv` containing:
   - run ID;
   - flowcell ID if known;
   - total reads;
   - total bases;
   - estimated/observed N50;
   - median/mean read length;
   - median/mean Q score if available;
   - active pore / mux metrics if available;
   - acquisition duration if available.
4. Generate a focused MultiQC report if parser modules/input outputs are available.

Do not require FASTQ generation for basic run QC if ONT native run summaries are sufficient.

### 8.6 Ultima run QC

Keep the first implementation conservative:

- support a `RUN_DIR` containing Ultima-native metrics CSV/JSON and/or already-produced FASTQ/CRAM files;
- normalize available metrics into `summary.tsv`;
- run MultiQC only where supported by the actual generated logs/reports;
- do not overclaim a full Ultima run-QC framework until real run folder examples are added to tests.

Expected output:

```text
results/runs/<runid>/run_qc/ultima/summary.tsv
results/runs/<runid>/run_qc/ultima/summary.html
results/runs/<runid>/run_qc/ultima/multiqc_report.html    # optional when supported
```

### 8.7 Sample analysis remains unchanged

Existing sample analysis rules continue to consume `samples.tsv` and `units.tsv`.

If `units.tsv` points to:

```text
/fsx/run_dir_mounts/<mount_id>/fastqs/...
```

then DayOA should process those paths directly. No DayOA sample-rule changes should be necessary unless a rule incorrectly assumes `/fsx/data` or `/data` prefixes.

---

## 9. Ursa refactor specification

### 9.1 New resource types

Add records to `resource_store.py` or equivalent persistence layer.

#### `RunDirectoryMountRecord`

Fields:

```text
euid
mount_id
run_id
platform
cluster_name
region
source_s3_uri
fsx_file_system_id
association_id
headnode_path
file_system_path
lifecycle
read_only
created_at
updated_at
created_by
workset_euid
metadata
```

#### `RunAnalysisJobRecord`

Fields:

```text
euid
job_name
workset_euid
run_mount_euid
analysis_command_id
cluster_name
region
destination
session_name
status
stdout_tail
stderr_tail
created_at
updated_at
metadata
```

Keep existing `StagingJobRecord` and `AnalysisJobRecord` for sample analysis.

### 9.2 New API endpoints

Add to `workset_api.py`.

```text
GET    /api/v1/run-mounts
POST   /api/v1/run-mounts
GET    /api/v1/run-mounts/{euid}
DELETE /api/v1/run-mounts/{euid}
POST   /api/v1/run-mounts/{euid}/verify

GET    /api/v1/run-analysis-commands
POST   /api/v1/run-analysis-commands/{command_id}/preview
POST   /api/v1/run-analysis-jobs
GET    /api/v1/run-analysis-jobs
GET    /api/v1/run-analysis-jobs/{euid}
GET    /api/v1/run-analysis-jobs/{euid}/logs
```

Request body for creating a run mount:

```json
{
  "workset_euid": "WS123",
  "cluster_name": "lsmc-prod-wgs-01",
  "region": "us-east-1",
  "source_s3_uri": "s3://sequencer-run-bucket/runs/RUN123/",
  "run_id": "RUN123",
  "mount_id": "RUN123",
  "platform": "ILMN",
  "read_only": true,
  "batch_import_metadata_on_create": true,
  "wait": true
}
```

Request body for creating a run-analysis job:

```json
{
  "workset_euid": "WS123",
  "run_mount_euid": "RM123",
  "analysis_command_id": "illumina_run_qc",
  "job_name": "RUN123 Illumina Run QC",
  "cluster_name": "lsmc-prod-wgs-01",
  "region": "us-east-1",
  "destination": "s3://lsmc-results/dayoa/",
  "project": "run-qc",
  "dry_run": false
}
```

### 9.3 DaylilyEcClient additions

Add methods in `daylib_ursa/ephemeral_cluster/runner.py`:

```python
def run_mount_create(...): ...
def run_mount_list(...): ...
def run_mount_describe(...): ...
def run_mount_delete(...): ...
def run_mount_verify(...): ...
def run_analysis_launch(...): ...  # or reuse workflow_launch after preparing runs.tsv
```

Use `run_json()` for mount lifecycle commands because the GUI should not parse free text.

### 9.4 UI behavior

Add a Run Operations section, separated from Sample Analysis.

Screens/panels:

1. **Run Directory Mounts**
   - select cluster/region;
   - select linked bucket and prefix;
   - enter or derive run ID;
   - choose platform;
   - create mount;
   - show association lifecycle and headnode path;
   - verify;
   - unmount.

2. **Run Analysis Launcher**
   - choose an existing mount;
   - choose run-analysis command;
   - preview DayEC/DayOA command;
   - launch;
   - monitor workflow session/logs.

3. **Sample Analysis Launcher**
   - unchanged, but manifest builder should allow mounted paths under `/fsx/run_dir_mounts/...` and set `STAGE_DIRECTIVE=mounted_readonly`.

### 9.5 Command display split

Ursa should display the command catalog in two sections:

```text
Sample analysis
Run analysis
```

Filtering rule:

- `command_class == sample_analysis` appears under sample analysis.
- `command_class == run_analysis` appears under run analysis.
- v1 catalog commands with no `command_class` default to sample analysis.

---

## 10. Operational safety and edge cases

### 10.1 DRA limits

There can be only a small number of DRAs per file system. Implement guardrails:

- warn at 6 active mounts;
- hard fail at AWS limit;
- provide `mounts list` and `mounts delete` prominently;
- encourage unmount after run-level workflows finish.

### 10.2 Non-overlap rules

Before creating a DRA, query active DRAs and reject:

- `/run_dir_mounts/RUN123/` if `/run_dir_mounts/RUN123/subdir/` exists;
- `/run_dir_mounts/` if any child exists;
- `s3://bucket/runs/RUN123/` if `s3://bucket/runs/RUN123/subdir/` exists;
- `s3://bucket/runs/` if a child run prefix is active.

### 10.3 Active sequencer runs

Run directories may still be growing. Add a clear policy:

- default `RUN_STATUS=complete`;
- if run appears incomplete, require `--allow-incomplete-run` for mount verification or run analysis;
- QC-only commands may be allowed on incomplete runs if explicitly requested;
- demux/basecalling should require completion markers unless overridden.

### 10.4 Cross-region behavior

If automatic import is enabled, the S3 bucket and FSx file system must be in the same region. If not, either:

- disable automatic import and rely on explicit metadata import if supported; or
- reject with a clear message.

For production, prefer same-region run buckets for run directory mounts.

### 10.5 Source bucket permissions

Required read permissions include at minimum:

```text
s3:ListBucket
s3:GetObject
s3:GetObjectVersion    # if versioned buckets are used
```

Do not require `s3:PutObject` for read-only run mounts.

### 10.6 Output separation

DayOA must write outputs to:

```text
results/runs/<runid>/...
```

and eventual exported destination buckets. It must not write into:

```text
/fsx/run_dir_mounts/<mount_id>/...
```

### 10.7 Auditability

Every mount/create/delete and run-analysis launch should be logged as a structured record. At minimum capture:

- actor;
- timestamp;
- cluster;
- FSx file system ID;
- source S3 URI;
- mount path;
- command invoked;
- AWS DRA association ID;
- lifecycle result.

---

## 11. Testing specification

### 11.1 DayEC unit tests

Add tests for:

- S3 URI normalization and trailing slash behavior;
- safe `mount_id` validation;
- FSx path mapping;
- overlap detection for FSx paths;
- overlap detection for S3 prefixes;
- DRA command construction;
- DRA lifecycle polling with botocore stubs or mocked AWS CLI responses;
- read-only policy rejects AutoExport by default;
- `mounts create --json` response shape;
- `mounts delete --json` response shape.

### 11.2 DayEC staging tests

Add fixture manifests with:

- mounted Illumina paired FASTQs;
- mounted CRAM/BAM;
- mixed staged + mounted rows;
- invalid mounted path outside `/fsx/run_dir_mounts`;
- `MOUNT_ID` mismatch;
- existing `pass_through` manifest to confirm no regression.

Assertions:

- mounted rows do not trigger `aws s3 cp` for source files;
- `samples.tsv` and `units.tsv` are still written;
- mounted local paths are preserved in `units.tsv`;
- existing stage modes still pass.

### 11.3 DayOA tests

Add or update tests for:

- reading `config/runs.tsv`;
- `snakemake -n produce_illumina_run_qc --config run_context_file=config/runs.tsv`;
- mounted-mode Illumina run QC path construction;
- S3-mode Illumina run QC remains compatible;
- BCL Convert output path under `results/runs/<runid>/bclconvert/`;
- generated `units.tsv` path under `results/runs/<runid>/bclconvert/tables/`;
- ONT run QC dry-run with fixture summary files;
- Ultima run QC dry-run with placeholder/fixture metrics.

### 11.4 Ursa tests

Add API tests for:

- create run mount request validation;
- run mount list/describe/delete;
- run-analysis command filtering;
- run-analysis preview;
- run-analysis job creation;
- existing sample staging and sample analysis flows still pass.

### 11.5 End-to-end smoke test

Using mocked AWS or a designated non-production cluster:

1. Create DRA to a small test run prefix.
2. Verify `/fsx/run_dir_mounts/<mount_id>/` on headnode.
3. Launch `produce_illumina_run_qc` dry-run.
4. Launch `samples stage` with mounted FASTQ manifest.
5. Confirm generated `samples.tsv` and `units.tsv` include mounted paths.
6. Delete mount.
7. Confirm mount lifecycle records are retained.

---

## 12. Implementation plan for Codex multi-agent

### Agent A — DayEC mount/DRA implementation

Scope:

- implement `daylily_ec/fsx.py`;
- implement `daylily_ec/run_mounts.py`;
- register `mounts` and `mount rundir` commands in `cli.py`;
- implement JSON/text outputs;
- implement local state records;
- implement tests.

Acceptance:

- unit tests pass without live AWS;
- CLI help shows new commands;
- mocked `mounts create/list/describe/delete` flows produce stable JSON.

### Agent B — DayEC staging extension

Scope:

- add manifest fields;
- add `STAGE_DIRECTIVE=mounted_readonly`;
- expand visible path validation;
- ensure no data-copy path runs for mounted rows;
- optionally add `--cluster` mounted-path verification;
- preserve existing `samples.tsv` / `units.tsv` contract.

Acceptance:

- existing staging tests pass;
- new mounted fixture tests pass;
- mixed staged/mounted manifest produces correct TSVs.

### Agent C — Command catalog v2

Scope:

- upgrade repository schema with backwards-compatible defaults;
- add `command_class`, `input_contract`, `requires_staging`, `requires_run_mount`;
- add run-analysis commands;
- update `repositories commands` JSON output;
- update tests and docs.

Acceptance:

- v1 catalog remains loadable or a migration path is explicit;
- run-analysis commands are distinguishable by API/Ursa;
- existing sample commands still render launch argv unchanged.

### Agent D — DayOA run-context and run-output refactor

Scope:

- implement `config/runs.tsv` loading;
- refactor run-QC outputs to `results/runs/<runid>/...`;
- support mounted mode for Illumina run QC;
- preserve S3 mode;
- parameterize BCL Convert to run-scoped outputs;
- improve ONT/Ultima run-QC placeholders to real input/output contracts.

Acceptance:

- DayOA dry-runs pass for Illumina run QC and BCL Convert using run context;
- existing sample-analysis dry-runs pass;
- tests assert new output paths.

### Agent E — Ursa run operations

Scope:

- add `RunDirectoryMountRecord` and `RunAnalysisJobRecord`;
- add API endpoints;
- add DaylilyEcClient methods;
- split command views into sample/run;
- add Run Directory Mounts and Run Analysis UI flow;
- keep existing sample staging/analysis unchanged.

Acceptance:

- API tests pass;
- run-analysis command preview works;
- existing sample job flows pass;
- UI can create/list/delete mount records and launch run analysis.

### Agent F — Integration/docs/QA

Scope:

- update CLI docs;
- update Ursa user docs;
- update DayOA run-QC docs;
- add examples:
  - mount Illumina run dir;
  - run Illumina run QC;
  - run BCL Convert;
  - stage sample manifest with mounted FASTQs;
  - unmount run dir.

Acceptance:

- documentation examples match implemented CLI;
- smoke-test script exists;
- no undocumented breaking changes.

---

## 13. Open decisions

1. **Read-only hardening depth.** Should DayEC run a POSIX permission hardening command after DRA creation, or rely on IAM + no AutoExport + output separation?
2. **Run completion verification.** Which platform-specific completion markers should be required before demux/basecalling? Illumina is straightforward; ONT/Ultima need real run-folder examples.
3. **Single-run vs multi-run context.** `runs.tsv` supports multiple rows, but first implementation can operate on one run at a time.
4. **BCL Convert license/container policy.** Existing DayOA uses `docker://nfcore/bclconvert:4.0.3`; confirm production licensing and image provenance.
5. **Ultima run-QC inputs.** Need one or more real Ultima run directories to formalize the parser and metrics contract.
6. **State source of truth.** AWS DRA state is authoritative for mount existence; local DayEC/Ursa state is an operational projection. Reconciliation behavior must be explicit.

---

## 14. Minimal acceptance definition

The implementation is acceptable when:

1. A user can mount a non-overlapping S3 run prefix into a running ParallelCluster FSx file system under `/fsx/run_dir_mounts/<mount_id>/`.
2. The CLI can list, describe, verify, and delete that mount.
3. The default mount behavior is read-only by policy: no AutoExport and no writes to the source bucket.
4. A sample manifest can reference mounted FASTQ/CRAM/BAM paths, skip byte staging, and still generate valid `samples.tsv` and `units.tsv`.
5. Existing sample analysis commands still work.
6. The command catalog exposes separate sample-analysis and run-analysis command classes.
7. DayOA can run at least Illumina run QC from a mounted run directory and place outputs under `results/runs/<runid>/run_qc/illumina/`.
8. DayOA can run BCL Convert from a mounted Illumina run directory and produce generated `units.tsv` for downstream sample analysis.
9. Ursa can create/delete run mounts and launch run-analysis jobs without overloading the existing sample staging job model.
10. Dry-run and unit test coverage exists for DayEC, DayOA, and Ursa.
