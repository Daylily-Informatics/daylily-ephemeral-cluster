# Pip Install

The preferred development and operator path from a checkout is:

```bash
source ./activate
```

Use pip install only when building an external environment that will provide the same prerequisites.

## Install

```bash
python -m pip install --upgrade pip
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
- ParallelCluster CLI pinned by this repo: `aws-parallelcluster==3.15.0`
- Conda or another Python environment with the package dependencies installed

Verify:

```bash
dyec --json version
daylily-ec --json version
pcluster version
aws --version
session-manager-plugin
```

`pcluster version` must report `3.15.0`. Do not install `aws-parallelcluster` with an unpinned `--upgrade` or `latest` target.

## Catalog Resources

Installed packages use packaged resources under `daylily_ec/resources/payload/`.
The packaged repository catalog must match the source catalog. Current launch
targets are DayOA `15.0.27`; retained validation receipts can describe an earlier
`validated_version`, which catalog output marks with `validation_pending: true`
rather than rewriting the evidence.

For local development after changing catalog or resource files:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
dyec repositories commands --command-id illumina_run_qc
```
