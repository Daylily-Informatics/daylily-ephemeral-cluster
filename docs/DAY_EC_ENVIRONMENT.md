# DAY-EC Environment

`DAY-EC` is the standard local environment for this repo and the environment installed on bootstrapped head nodes.

## Create Or Update The Environment

From a repo checkout:

```bash
source ./activate
```

`source ./activate` is the supported checkout-friendly entrypoint. It bootstraps or activates `DAY-EC`, prepends [`../bin/`](../bin/) to `PATH`, and makes `daylily-ec` available in the current shell.

If you need to force a rebuild or run the lower-level bootstrap helper directly, use `./bin/init_dayec` explicitly.

On bootstrapped headnodes, the managed login shell should source `~/projects/daylily-ephemeral-cluster/activate` and then evaluate `daylily-ec headnode init --emit-shell --non-interactive` to populate the headnode shell context.

Useful `init_dayec` environment variables:

- `DAYLILY_EC_INIT_DAYEC_PIP_SPEC`: install from a specific pip target when not running from a repo checkout
- `DAYLILY_EC_RESOURCES_DIR`: override packaged resource lookup

## Core Diagnostics

```bash
daylily-ec version
daylily-ec info
daylily-ec resources-dir
daylily-ec pricing snapshot --help
```

These commands are the fastest way to confirm that the CLI, packaged resources, and runtime directories are available.

## What The Environment Includes

The exact dependency set lives in [`../config/day/daycli.yaml`](../config/day/daycli.yaml). At a high level it includes:

- Python 3.11
- AWS CLI v2
- `aws-parallelcluster`
- `daylily-omics-references`
- `pytest`, `mypy`, and related dev tooling
- common operator utilities such as `jq`, `yq`, and `rclone`

## Running Tests

```bash
source ./activate

pytest tests/
pytest --cov=daylily_ec --cov=daylib tests/
pytest --collect-only -q tests
```

Avoid hard-coding expected test counts into docs; use `pytest --collect-only` when you want the current count.

## Troubleshooting

### Conda Is Missing

```bash
./bin/install_miniconda
source ./activate
```

`install_miniconda` auto-detects Apple Silicon, Intel macOS, Linux x86_64, and Linux ARM hosts. It prefers `curl` and falls back to `wget`.

### AWS Credentials Are Missing

```bash
export AWS_PROFILE=daylily-service
daylily-ec info
aws sts get-caller-identity
```

### Packaged Resources Are Not Resolving

```bash
daylily-ec resources-dir
```

If you need to point the CLI at a custom resource tree:

```bash
export DAYLILY_EC_RESOURCES_DIR=/path/to/override-root
```

### The Reference CLI Is Missing

If `daylily-omics-references` is not available after activation, re-run:

```bash
source ./activate
```

## Common Environment Variables

- `AWS_PROFILE`
- `AWS_REGION`
- `AWS_DEFAULT_REGION`
- `DAY_CONTACT_EMAIL`
- `DAY_DISABLE_AUTO_SELECT`
- `DAY_BREAK`
