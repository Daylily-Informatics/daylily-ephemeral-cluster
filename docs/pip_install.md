# Pip Install

The preferred development and operator path from a checkout is:

```bash
source ./activate
```

Use pip install only when building an external environment that will provide the same prerequisites.

## Install

```bash
python -m pip install -e .
```

The package exposes:

- `daylily-ec`
- `dyec`

Both commands call `daylily_ec.cli:main`.

## External Prerequisites

The shell still needs:

- AWS CLI
- AWS Session Manager plugin
- ParallelCluster CLI compatible with this repo
- Conda or another Python environment with the package dependencies installed

Verify:

```bash
dyec version
daylily-ec version
pcluster version
aws --version
session-manager-plugin
```

## Catalog Resources

Installed packages use packaged resources under `daylily_ec/resources/payload/`. The packaged repository catalog must match the source catalog. Current DayOA pins are `1.0.16`.

For local development after changing catalog or resource files:

```bash
python -m pip install -e .
dyec repositories commands --command-id illumina_run_qc
```
