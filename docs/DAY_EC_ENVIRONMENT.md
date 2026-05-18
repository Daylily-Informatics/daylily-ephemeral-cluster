# DAY-EC Environment

`source ./activate` is the supported checkout entrypoint. It creates or repairs the `DAY-EC` Conda environment, installs this repository editable, and validates the local tools needed by DayEC.

## Expected Tools

After activation:

```bash
dyec version
daylily-ec version
dyec runtime status
aws --version
pcluster version
session-manager-plugin
```

`dyec` and `daylily-ec` are the same Python entrypoint.

## Package Contract

Python packaging is defined by `pyproject.toml`. The active package includes:

- `daylily_ec` Python modules
- resource payloads under `daylily_ec/resources/payload/`
- source and packaged repository catalogs
- CLI scripts `daylily-ec` and `dyec`

The repository catalog must remain synchronized between:

- `config/daylily_available_repositories.yaml`
- `daylily_ec/resources/payload/config/daylily_available_repositories.yaml`

Current DayOA catalog pins are `1.0.7`.

## Stale Editable Installs

If a command imports code from a different checkout, refresh the editable install:

```bash
python -m pip install -e .
dyec info
```

Use `dyec info` to confirm the project root.

## Headnode Environment

Headnode setup installs DayEC user-scoped tools for `ubuntu` and validates a login shell. The supported interactive path is:

```bash
dyec headnode connect \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

Expected on the headnode:

```bash
whoami
pwd
command -v day-clone
```

The supported user is `ubuntu`.

## Local Validation

```bash
dyec runtime check
dyec runtime explain
python -m pytest tests/test_environment_contract.py -q
```
