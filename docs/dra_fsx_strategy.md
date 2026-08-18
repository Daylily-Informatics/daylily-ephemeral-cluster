# DRA FSx Strategy

This is the current DayEC data-plane model. FSx for Lustre is the high-performance namespace attached to the cluster. S3 buckets remain the durable storage layer.

## Namespace Contract

| Purpose | Headnode path | FSx API path | S3 side | Lifecycle |
|---|---|---|---|---|
| Reference data | `/fsx/references/` | `/references/` | `reference_s3_uri` | Created with the cluster |
| Runtime assets | `/fsx/references/runtime_assets/` | `/references/runtime_assets/` | `reference_s3_uri/runtime_assets/` | Created with the reference DRA |
| Control/validation data | `/fsx/control_data/...` | `/control_data/...` | `control_data_s3_uri/...` | Created on demand |
| Staging | `/fsx/staging/staged_external_sequencing_data/...` | `/staging/staged_external_sequencing_data/...` | `<raw-seq-bucket>/staged_external_data/...` | Created on demand |
| Run inputs | `/fsx/run_dir_mounts/<mount_id>/` | `/run_dir_mounts/<mount_id>/` | selected run prefix | Created and deleted on demand |
| Workflow outputs | `/fsx/analysis_results/...` | `/analysis_results/...` | none by default | Local to the FSx filesystem until exported |
| Post-controller analysis export | `/fsx/analysis_results/<executing_entity>/<analysis_id>/` | `/analysis_results/<executing_entity>/<analysis_id>/` | Explicit empty `s3://bucket/prefix/<executing_entity>/<analysis_id>/` | Temporary output DRA after terminal controller success |

Run-directory DRAs are read-oriented by default. They configure AutoImport events and no AutoExport policy. Export DRAs are created directly on one completed analysis directory, run one explicit FSx export task, and are detached after the task completes.

## Cluster And Run Lifecycle

```mermaid
sequenceDiagram
  participant Op as Operator
  participant DyEC as dyec/daylily-ec
  participant PC as ParallelCluster
  participant FSx as FSx for Lustre
  participant Ref as Reference S3 URI
  participant Ctrl as Control-data S3 URI
  participant Stage as S3 raw-seq staged_external_data prefix
  participant Run as S3 run bucket
  participant DayOA as DayOA on headnode
  participant Out as S3 analysis bucket

  Op->>DyEC: preflight and create
  DyEC->>PC: render config and create cluster
  PC->>FSx: mount /fsx
  Ref-->>FSx: reference-data DRA /references/
  Op->>DyEC: samples stage
  Stage-->>FSx: staging DRA /staging/staged_external_sequencing_data/remote_stage_*/
  Op->>DyEC: mounts create s3://.../RUN_ID/
  Run-->>FSx: run DRA /run_dir_mounts/<mount_id>/
  Op->>DyEC: workflow launch
  DyEC->>DayOA: start tmux workflow
  DayOA->>FSx: read /fsx/references, /fsx/references/runtime_assets, staged data, and /fsx/run_dir_mounts
  DayOA->>FSx: write staged inputs under /fsx/staging
  DayOA->>FSx: write /fsx/analysis_results/<executing_entity>/<analysis_id>
  Op->>DyEC: export --source-path /fsx/analysis_results/<executing_entity>/<analysis_id>
  DyEC->>FSx: create temporary DRA at /analysis_results/<executing_entity>/<analysis_id>/
  FSx-->>Out: EXPORT_TO_REPOSITORY task to /<prefix>/<executing_entity>/<analysis_id>/
  DyEC->>FSx: detach export DRA
  Op->>DyEC: delete after receipt verification
```

## FSx And S3 Topology

```mermaid
flowchart LR
  subgraph S3["Durable S3"]
    Ref["Reference bucket including runtime_assets/"]
    Ctrl["Control data bucket"]
    Stage["Raw seq bucket staged_external_data/"]
    RunA["Run bucket prefix RUN_A"]
    RunB["Run bucket prefix RUN_B"]
    Analysis["Analysis bucket prefix /<executing_entity>/<analysis_id>/"]
  end

  subgraph Lustre["FSx for Lustre mounted at /fsx"]
    Data["/fsx/references"]
    Assets["/fsx/references/runtime_assets"]
    Control["/fsx/control_data/... on demand"]
    Staging["/fsx/staging/... on demand"]
    MntA["/fsx/run_dir_mounts/RUN_A"]
    MntB["/fsx/run_dir_mounts/RUN_B"]
    Results["/fsx/analysis_results/..."]
    Export["temporary DRA on /fsx/analysis_results/<executing_entity>/<analysis_id>"]
  end

  Ref -->|reference DRA| Data
  Data --> Assets
  Ctrl -->|on-demand DRA| Control
  Stage -->|on-demand DRA| Staging
  RunA -->|ephemeral read DRA| MntA
  RunB -->|ephemeral read DRA| MntB
  Data --> Results
  MntA --> Results
  MntB --> Results
  Results -->|exact completed analysis dir| Export
  Export -->|FSx export task| Analysis
```

## Pipeline Catalog Flow

`config/daylily_pipeline_command_catalog.yaml` defines repositories and launch
profiles. Its packaged copy under
`daylily_ec/resources/payload/config/` must remain identical. The active DayOA
repository and active command targets are pinned to `15.0.28`; older
`validated_version` values remain historical evidence and appear as
`validation_pending: true` when they differ from a current target.

Catalog `test_data_profile` entries make the source-mount contract explicit.
`default_mounted` profiles read from default cluster DRAs such as `/fsx/references`
or `/fsx/control_data`. `run_dra_required` profiles require the full
`run_context` `runs.tsv` schema, including `RUNID`, `RUN_DIR`, `SOURCE_S3_URI`,
and `MOUNT_ID`; DYEC must verify or create `/fsx/run_dir_mounts/<MOUNT_ID>/`
before launch. `none` profiles do not consume external source data. See the
[CLI reference](cli_reference.md#run-qc-catalog-commands) for the full header
set.

```mermaid
flowchart TB
  Catalog["Repository catalog v6"] --> Repo["daylily-omics-analysis @ 15.0.28"]
  Repo --> Sample["sample_analysis"]
  Repo --> Run["run_analysis"]

  Sample --> Contract["catalog input_contract"]
  Contract --> Six["six_manifest: --manifest-dir"]
  Contract --> Legacy["sample_manifest: explicit staged input"]
  Six --> LaunchA["catalog render/launch"]
  Legacy --> LaunchA

  Run --> Mount["dyec mounts create/verify"]
  Mount --> Runs["runs.tsv"]
  Runs --> LaunchB["catalog launch or workflow launch --input-contract run_context"]

  LaunchA --> DayOA["DayOA targets"]
  LaunchB --> DayOA
  DayOA --> Results["/fsx/analysis_results/..."]
```

## Export Rule

Export is not automatic writeback from the run mount or reference mount. The supported export flow is:

1. choose one completed directory under `/fsx/analysis_results/<executing_entity>/<analysis_id>`
2. record `dyec analysis visit --mode export` for that root without writing a marker into the destination prefix
3. run `dyec export --source-path /fsx/analysis_results/<executing_entity>/<analysis_id> --destination-s3-uri s3://bucket/prefix/<executing_entity>/<analysis_id>/ --output-dir ./export-receipts/<analysis-id> --wait --timeout-seconds 5400`
4. keep `fsx_export.yaml`
5. delete the cluster only after the receipt shows `status: success`, `task_lifecycle: SUCCEEDED`, and `detached: true`

The bucket and parent prefix are always explicit. The requested destination must
be empty before export; an S3 visit marker in that exact prefix causes the
fail-closed preflight to reject it. DayEC validates that the S3 key suffix
matches the normalized source analysis directory and writes FSx task reports
under `_daylily_monitor/fsx-export/...` inside the requested export prefix.
