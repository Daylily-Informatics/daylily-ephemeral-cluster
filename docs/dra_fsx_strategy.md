# DRA FSx Strategy

This is the current DayEC data-plane model. FSx for Lustre is the high-performance namespace attached to the cluster. S3 buckets remain the durable storage layer.

## Namespace Contract

| Purpose | Headnode path | FSx API path | S3 side | Lifecycle |
|---|---|---|---|---|
| Reference data | `/fsx/data/` | `/data/` | `<reference-bucket>/data/` | Created with the cluster |
| Run inputs | `/fsx/run_dir_mounts/<mount_id>/` | `/run_dir_mounts/<mount_id>/` | selected run prefix | Created and deleted on demand |
| Workflow outputs | `/fsx/analysis_results/...` | `/analysis_results/...` | none by default | Local to the FSx filesystem until exported |
| Direct analysis export | `/fsx/analysis_results/ubuntu/<analysis_dir>/` | `/analysis_results/ubuntu/<analysis_dir>/` | `s3://bucket/analysis_results/ubuntu/<analysis_dir>/` | Temporary output DRA |

Run-directory DRAs are read-oriented by default. They configure AutoImport events and no AutoExport policy. Export DRAs are created directly on one completed analysis directory, run one explicit FSx export task, and are detached after the task completes.

## Cluster And Run Lifecycle

```mermaid
sequenceDiagram
  participant Op as Operator
  participant DyEC as dyec/daylily-ec
  participant PC as ParallelCluster
  participant FSx as FSx for Lustre
  participant Ref as S3 reference bucket
  participant Run as S3 run bucket
  participant DayOA as DayOA on headnode
  participant Out as S3 analysis bucket

  Op->>DyEC: preflight and create
  DyEC->>PC: render config and create cluster
  PC->>FSx: mount /fsx
  Ref-->>FSx: reference-data DRA /data/
  Op->>DyEC: mounts create s3://.../RUN_ID/
  Run-->>FSx: run DRA /run_dir_mounts/<mount_id>/
  Op->>DyEC: workflow launch
  DyEC->>DayOA: start tmux workflow
  DayOA->>FSx: read /fsx/data and /fsx/run_dir_mounts
  DayOA->>FSx: write /fsx/analysis_results/ubuntu/<analysis_dir>
  Op->>DyEC: export --source-path /fsx/analysis_results/ubuntu/<analysis_dir>
  DyEC->>FSx: create temporary DRA at /analysis_results/ubuntu/<analysis_dir>/
  FSx-->>Out: EXPORT_TO_REPOSITORY task to /analysis_results/ubuntu/<analysis_dir>/
  DyEC->>FSx: detach export DRA
  Op->>DyEC: delete after receipt verification
```

## FSx And S3 Topology

```mermaid
flowchart LR
  subgraph S3["Durable S3"]
    Ref["Reference bucket /data/"]
    RunA["Run bucket prefix RUN_A"]
    RunB["Run bucket prefix RUN_B"]
    Analysis["Analysis bucket /analysis_results/ubuntu/<analysis_dir>/"]
  end

  subgraph Lustre["FSx for Lustre mounted at /fsx"]
    Data["/fsx/data"]
    MntA["/fsx/run_dir_mounts/RUN_A"]
    MntB["/fsx/run_dir_mounts/RUN_B"]
    Results["/fsx/analysis_results/..."]
    Export["temporary DRA on /fsx/analysis_results/ubuntu/<analysis_dir>"]
  end

  Ref -->|reference DRA| Data
  RunA -->|ephemeral read DRA| MntA
  RunB -->|ephemeral read DRA| MntB
  Data --> Results
  MntA --> Results
  MntB --> Results
  Results -->|exact completed analysis dir| Export
  Export -->|FSx export task| Analysis
```

## Pipeline Catalog Flow

`config/daylily_available_repositories.yaml` defines repositories and launch profiles. The DayOA repository and every DayOA command are pinned to `1.0.16`.

```mermaid
flowchart TB
  Catalog["Repository catalog v2"] --> Repo["daylily-omics-analysis @ 1.0.16"]
  Repo --> Sample["sample_analysis"]
  Repo --> Run["run_analysis"]

  Sample --> Manifest["analysis_samples.tsv"]
  Manifest --> Stage["dyec samples stage/run"]
  Stage --> TSV["samples.tsv + units.tsv"]
  TSV --> LaunchA["dyec workflow launch --stage-dir"]

  Run --> Mount["dyec mounts create/verify"]
  Mount --> Runs["runs.tsv"]
  Runs --> LaunchB["dyec workflow launch --run-context-file"]

  LaunchA --> DayOA["DayOA targets"]
  LaunchB --> DayOA
  DayOA --> Results["/fsx/analysis_results/..."]
```

## Export Rule

Export is not automatic writeback from the run mount or reference mount. The supported export flow is:

1. choose one completed directory under `/fsx/analysis_results/ubuntu/<analysis_dir>`
2. run `dyec export --source-path /fsx/analysis_results/ubuntu/<analysis_dir> --destination-s3-uri s3://bucket/analysis_results/ubuntu/<analysis_dir>/`
3. keep `fsx_export.yaml`
4. delete the cluster only after the receipt shows `status: success`, `task_lifecycle: SUCCEEDED`, and `detached: true`

The bucket is always explicit. DayEC validates that the S3 key suffix matches the normalized source analysis directory and writes FSx task reports outside the exported prefix under `daylily-monitor/fsx-export/<analysis_dir>/...`.
