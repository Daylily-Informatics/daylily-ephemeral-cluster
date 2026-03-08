# Overview

Daylily is an operator-focused framework for standing up short-lived AWS ParallelCluster environments around durable reference data and repeatable workflow launch paths. The goal is simple: make large Slurm-backed bioinformatics clusters easy to create, use, inspect, and destroy without turning the cluster itself into a permanent pet.

## Why Ephemeral Clusters

Daylily assumes the durable assets are the data, references, manifests, and workflow definitions - not the running compute fleet. That pushes the design toward:

- preflight validation before any expensive mutation happens
- region-scoped reference buckets that survive cluster turnover
- FSx for Lustre for shared cluster-time performance
- lightweight, repeatable head-node bootstrap
- explicit export and delete workflows once the run is complete

This keeps the operator workflow close to "create, validate, run, export, tear down" instead of "tune and babysit a permanent cluster".

## System Model

The Daylily stack has three layers:

1. Control plane: `daylily_ec` validates prerequisites, renders cluster YAML, applies spot pricing, creates the cluster, and records state.
2. Data plane: a region-specific S3 bucket whose name includes `omics-analysis` is exposed through FSx for Lustre so references and staged data are shared across nodes.
3. Workflow plane: repository metadata in [`../config/daylily_available_repositories.yaml`](../config/daylily_available_repositories.yaml) tells the head node what workflow repos exist, where to clone them from, and which default ref to use.

## Operator Story

The intended operator loop is:

1. Prepare the AWS identity, key pair, and reference bucket for a region.
2. Run `python -m daylily_ec preflight` to catch quota, IAM, or bucket problems before provisioning.
3. Create the cluster and let Daylily bootstrap the head node.
4. Stage sample metadata and inputs from a laptop or directly on the head node.
5. Launch a workflow through the head node helpers and monitor the run in Slurm and tmux.
6. Export results to S3, check for drift if needed, and delete the cluster.

That operational sequence is the main reason Daylily ships both the Python CLI and the supporting `bin/` helper scripts.

## Pluggable Workflow Catalog

The repo already carries a small workflow registry:

- `daylily-omics-analysis`: primary whole-genome and multiomics workflows
- `rna-seq-star-deseq2`: RNA-seq alignment and differential expression workflows
- `daylily-sarek`: a Sarek-based workflow entry

Those entries live in [`../config/daylily_available_repositories.yaml`](../config/daylily_available_repositories.yaml), and `day-clone` uses them on the head node.

## Cost And Performance Context

Daylily is opinionated about cost visibility:

- preflight can stop before a bad cluster launch
- budgets and heartbeat notifications are part of the lifecycle model
- the CLI includes raw pricing inspection helpers
- the repo keeps benchmark and cost context alongside the operator docs

Illustrative artifacts already shipped in the repo:

![Spot pricing example](images/cost_est_table.png)

![Tagged cost tracking example](images/assets/day_aws_tagged_costs_by_hour_project.png)

## Filesystem And Results Story

The shared filesystem layout is part of the operator value proposition. References, staged inputs, workflow repos, and analysis results land in predictable places so the cluster can stay ephemeral while the run outputs remain easy to export and inspect.

![Example results tree](images/assets/daylily_tree.png)

## Benchmark Reference Material

The repo keeps benchmark notes under [`benchmarks/`](benchmarks/). These are reference material, not the operator quickstart:

- [`benchmarks/FS_performance.md`](benchmarks/FS_performance.md)
- [`benchmarks/aligner_benchmarks.md`](benchmarks/aligner_benchmarks.md)
- [`benchmarks/deduplication_benchmarks.md`](benchmarks/deduplication_benchmarks.md)
- [`benchmarks/snv_calling.md`](benchmarks/snv_calling.md)
- [`benchmarks/sv_calling.md`](benchmarks/sv_calling.md)

## Where To Go Next

- [quickest_start.md](quickest_start.md) for the install and create flow
- [operations.md](operations.md) for the day-2 operator workflow
- [archive/README.md](archive/README.md) for historical material that is preserved but no longer canonical
