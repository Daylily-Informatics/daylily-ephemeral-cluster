# DAY-EC Environment

`DAY-EC` is the supported environment for working on this repo locally and for running the managed Daylily shell context on bootstrapped head nodes.

## Checkout Flow

From a repo checkout:

```bash
source ./activate
```

`source ./activate` is the supported entrypoint. It ensures the Conda environment from `environment.yaml` exists, installs this repo into that environment, and makes `daylily-ec`, `aws`, `pcluster`, and `session-manager-plugin` available in the current shell.

## Dependency Ownership

The current contract is:

- `environment.yaml`: Conda-managed operator tooling and `pip`
- `pyproject.toml`: Python package dependencies for `daylily-ec` and the supported Python scripts

For repo checkouts, the package is installed into `DAY-EC` as an editable install with the `dev` extras.

## Headnode Flow

On a supported head node, the managed login hook should do the equivalent of:

```bash
source ~/projects/daylily-ephemeral-cluster/activate
eval "$(daylily-ec headnode init --emit-shell --non-interactive --skip-project-check)"
```

That shell context is expected to expose:

- `CONDA_DEFAULT_ENV=DAY-EC`
- `daylily-ec`
- `day-clone`
- the standard Daylily environment variables such as `DAY_PROJECT` and `DAY_AWS_REGION`

## Useful Commands

```bash
daylily-ec version
daylily-ec info
daylily-ec resources-dir
daylily-ec runtime --help
daylily-ec env --help
```

## Rebuild From Scratch

```bash
conda env remove -n DAY-EC
source ./activate
```

## Tests

```bash
pytest tests/
pytest --collect-only -q tests
```

## Troubleshooting

If the shell is missing Daylily commands after activation:

```bash
source ./activate
daylily-ec info
```

If the head node shell is missing the managed context:

```bash
eval "$(daylily-ec headnode init --emit-shell --non-interactive --skip-project-check)"
```
