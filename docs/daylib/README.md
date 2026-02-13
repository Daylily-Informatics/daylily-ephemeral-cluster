# daylib

`./daylib` holds the library code which supports daylily-ephemeral-cluster infrastructure-as-code management.

> **Note**: The primary control plane is now `daylily_ec/` (the Python control plane added in the CP-001 through CP-019 refactor). `daylib/` remains for cost estimation and legacy configuration support. See the [main README](../../README.md#daylily-ec-cli-reference) for the `daylily-ec` CLI reference.

## Core Components

### Configuration Management
- **config.py**: Centralized Pydantic-based configuration for AWS resources and cluster settings
- **exceptions.py**: Custom exception hierarchy for infrastructure operations

## Making libs available

```bash
conda activate DAY-EC
cd ~/projects/daylily-ephemeral-cluster
pip install -e .
```

## Run a test
_assuming your aws credentials are in place, and `AWS_PROFILE=<something>`.

```bash
calc_daylily_aws_cost_estimates
```