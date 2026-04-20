# DAY-EC Environment

`DAY-EC` is the supported local engineering and operator environment for this repo.

The environment contract is intentionally split:

- `environment.yaml` owns the Conda/system layer
- `pyproject.toml` owns the Python package dependencies

## Source Of Truth

### `environment.yaml`

This file defines the Conda environment shape and the non-Python operator tooling, including:

- `python`
- `pip`
- `awscli`
- `aws-session-manager-plugin`
- `bash`
- `jq`
- `yq`
- `nodejs`
- `rclone`
- `parallel`
- `perl`
- `fd-find`

### `pyproject.toml`

This file owns the Python dependency graph for the package. In a repo checkout, `DAY-EC` installs this repo editable so the environment includes:

- runtime package dependencies
- test tooling
- lint/type tooling

That is the current supported engineering contract.

## The Supported Checkout Entry Point

From a repo checkout:

```bash
source ./activate
```

`activate` does the following:

1. resolves the repo root
2. ensures Conda is available
3. creates `DAY-EC` from `environment.yaml` if it does not exist
4. updates `DAY-EC` if runtime smoke tests fail
5. installs this repo into `DAY-EC` as an editable package
6. validates the local runtime by checking `daylily-ec`, `aws`, `pcluster`, `session-manager-plugin`, and `node`

If `source ./activate` completes cleanly, that is the supported shell for operator work and test execution.

## Explicit Bootstrap Helper

You can run the bootstrap directly:

```bash
./bin/init_dayec
```

Use this when:

- rebuilding `DAY-EC` explicitly
- bootstrapping from packaged resources
- diagnosing environment setup without sourcing the shell wrapper

`bin/init_dayec` uses `environment.yaml` from the resolved resources directory and, in a repo checkout, installs:

```bash
python -m pip install --editable "."
```

## Smoke Tests

After activation, these commands should work:

```bash
daylily-ec version
daylily-ec runtime status
aws --version
pcluster version
session-manager-plugin
```

Useful runtime inspection:

```bash
daylily-ec info
daylily-ec runtime check
daylily-ec runtime explain
```

## Rebuild Or Repair

If you want a clean rebuild:

```bash
conda env remove -n DAY-EC
source ./activate
```

If you want a repair without removing the environment first:

```bash
conda env update -n DAY-EC -f environment.yaml
conda run -n DAY-EC python -m pip install --editable "."
```

## What Is No Longer Active

These are not part of the active environment contract anymore:

- the old duplicate day-env YAML path
- the retired pre-`DAY-EC` installer flow
- duplicated bootstrap YAMLs that are now archive-only

Those materials live in archive/quarantine locations for historical reference only.
