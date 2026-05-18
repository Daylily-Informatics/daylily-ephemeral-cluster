# DRA FSx Strategy

This is the current DayEC data-plane model. FSx for Lustre is the high-performance namespace attached to the cluster. S3 buckets remain the durable storage layer.

## Namespace Contract

| Purpose | Headnode path | FSx API path | S3 side | Lifecycle |
|---|---|---|---|---|
| Reference data | `/fsx/data/` | `/data/` | `<reference-bucket>/data/` | Created with the cluster |
| Run inputs | `/fsx/run_dir_mounts/<mount_id>/` | `/run_dir_mounts/<mount_id>/` | selected run prefix | Created and deleted on demand |
| Workflow outputs | `/fsx/analysis_results/...` | `/analysis_results/...` | none by default | Local to the FSx filesystem until exported |
| Export staging | `/fsx/exports/<export_id>/` | `/exports/<export_id>/` | selected analysis bucket/prefix | Temporary output DRA |

Run-directory DRAs are read-oriented by default. They configure AutoImport events and no AutoExport policy. Export DRAs are created only for selected output payloads and are detached after the FSx export task completes.

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
  Op->>DyEC: mounts create --s3-uri run prefix
  Run-->>FSx: run DRA /run_dir_mounts/<mount_id>/
  Op->>DyEC: workflow launch
  DyEC->>DayOA: start tmux workflow
  DayOA->>FSx: read /fsx/data and /fsx/run_dir_mounts
  DayOA->>FSx: write /fsx/analysis_results
  Op->>FSx: copy selected outputs to /fsx/exports/<export_id>
  Op->>DyEC: export --destination-s3-uri
  FSx-->>Out: EXPORT_TO_REPOSITORY task
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
    Analysis["Analysis bucket /exports/<export_id>/"]
  end

  subgraph Lustre["FSx for Lustre mounted at /fsx"]
    Data["/fsx/data"]
    MntA["/fsx/run_dir_mounts/RUN_A"]
    MntB["/fsx/run_dir_mounts/RUN_B"]
    Results["/fsx/analysis_results/..."]
    Export["/fsx/exports/<export_id>"]
  end

  Ref -->|reference DRA| Data
  RunA -->|ephemeral read DRA| MntA
  RunB -->|ephemeral read DRA| MntB
  Data --> Results
  MntA --> Results
  MntB --> Results
  Results -->|operator-selected copy| Export
  Export -->|FSx export task| Analysis
```

## Pipeline Catalog Flow

`config/daylily_available_repositories.yaml` defines repositories and launch profiles. The DayOA repository and every DayOA command are pinned to `1.0.7`.

```mermaid
flowchart TB
  Catalog["Repository catalog v2"] --> Repo["daylily-omics-analysis @ 1.0.7"]
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

1. choose the outputs under `/fsx/analysis_results/...`
2. copy them into `/fsx/exports/<export_id>/...`
3. run `dyec export --source-path /exports/<export_id>/... --destination-s3-uri s3://...`
4. keep `fsx_export.yaml`
5. delete the cluster only after the receipt shows `status: success` and `detached: true`
