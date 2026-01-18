# daylily-ephemeral-cluster

**Infrastructure-as-code for ephemeral AWS ParallelCluster environments for bioinformatics.**

## Overview

Daylily Ephemeral Cluster provides tools for creating, managing, and tearing down AWS ParallelCluster environments optimized for genomics workloads. Key features:

- **Ephemeral Cluster Management** - Create and destroy ParallelCluster environments on demand
- **Spot Pricing Analysis** - Analyze EC2 spot pricing across availability zones
- **FSx Integration** - Export results from FSx Lustre to S3
- **Pipeline Factory** - YAML-based pipeline configuration and execution

## Installation

```bash
pip install daylily-ephemeral-cluster

# For development
pip install daylily-ephemeral-cluster[dev]

# With workset management integration
pip install daylily-ephemeral-cluster[workset]
```

## Quick Start

```bash
# Create an ephemeral cluster
daylily-create-ephemeral-cluster --config cluster-config.yaml

# SSH into the headnode
daylily-ssh-into-headnode --cluster my-cluster

# Run analysis on headnode
daylily-run-omics-analysis-headnode --samples manifest.tsv

# Export results to S3
daylily-export-fsx-to-s3 --cluster my-cluster --destination s3://my-bucket/results/

# Delete the cluster
daylily-delete-ephemeral-cluster --cluster my-cluster
```

## Architecture

```
daylib/
├── day_factory.py           # Pipeline factory for YAML config
├── day_cost_ec2.py          # EC2 spot pricing analysis
├── day_cost_components.py   # Abstract cost components
├── day_concrete_components.py # Task and DataArtifact classes
├── config.py                # Settings and configuration
└── exceptions.py            # Exception classes

bin/
├── daylily-create-ephemeral-cluster
├── daylily-delete-ephemeral-cluster
├── daylily-ssh-into-headnode
├── daylily-run-omics-analysis-headnode
├── daylily-export-fsx-to-s3
└── ...
```

## Configuration

Set environment variables or use a `.env` file:

```bash
AWS_REGION=us-east-1
AWS_PROFILE=my-profile
```

## Related Projects

- [daylily-ursa](https://github.com/Daylily-Informatics/daylily-ursa) - Workset management API for orchestrating genomics pipelines

## License

MIT

