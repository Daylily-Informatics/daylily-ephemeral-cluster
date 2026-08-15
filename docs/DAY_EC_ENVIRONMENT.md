# DAY-EC Environment

`source ./activate` is the supported checkout entrypoint. It creates or repairs the `DAY-EC` Conda environment, installs this repository editable, and validates the local tools needed by DayEC.

## Expected Tools

After activation:

```bash
dyec --json version
daylily-ec --json version
dyec runtime status
aws --version
pcluster version
session-manager-plugin
```

`dyec` and `daylily-ec` are the same Python entrypoint.

The checked-in CLI release baseline is `18.0.10`. Use `dyec --json version` to
identify the installed source before relying on any command example.

## ParallelCluster Target

This repo targets exactly:

```text
aws-parallelcluster==3.15.0
```

Refresh the checkout-managed environment with the existing install path:

```bash
source ./activate
python -m pip install --upgrade pip
python -m pip install -e .
pcluster version
```

`pcluster version` must report `3.15.0`. Do not use unpinned install commands such as `pip install --upgrade aws-parallelcluster`.

For safe config validation, use a rendered cluster YAML, not the unresolved `config/day_cluster/prod_cluster_v8.yaml` template:

```bash
pcluster validate-cluster-configuration --cluster-configuration <rendered-cluster.yaml> --region us-west-2
```

If the installed `pcluster` does not provide `validate-cluster-configuration`, record that as a tooling blocker. Do not substitute `pcluster create-cluster --dryrun true` without explicit approval, because even dry-run create is outside this upgrade pass.

## Package Contract

Python packaging is defined by `pyproject.toml`. The active package includes:

- `daylily_ec` Python modules
- resource payloads under `daylily_ec/resources/payload/`
- source and packaged repository catalogs
- CLI scripts `daylily-ec` and `dyec`

The repository catalog must remain synchronized between:

- `config/daylily_pipeline_command_catalog.yaml`
- `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`

The active DayOA catalog pin is `15.0.5`. Catalog output may retain an older
`validated_version`; `validation_pending: true` reports that honest difference
without rewriting historical validation evidence or blocking a launch.

## Stale Editable Installs

If a command imports code from a different checkout, refresh the editable install:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
dyec info
```

Use `dyec info` to confirm the project root.

## Headnode Environment

Headnode setup installs DayEC user-scoped tools for the cluster-appropriate remote user and validates a bash login/interactive shell. Ubuntu/Intel DayOA headnodes use `ubuntu`; DRAGEN/RHEL-style headnodes use `ec2-user`. The supported interactive path is:

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
day-clone --list
day-clone --check-auth --repository daylily-omics-analysis --git-tag <dayoa_version>
```

The supported user is selected by `--remote-user auto` on a headnode-facing
command such as `dyec headnode connect`. `day-clone --list` prints the clone
syntax and repository rows from `$HOME/.config/daylily/daylily_pipeline_command_catalog.yaml`; the authentication check must also succeed for the explicit DayOA ref. If either command fails, repair headnode configuration instead of guessing repository URLs, tags, or credentials.

## Project-local DYEC context

For DYEC commands only, the ignored `$PWD/.dyec.config.yaml` can hold
`aws_profile`, `aws_region`, `aws_region_az`, and `cluster_admin_email`. Create
or update it with `dyec set-vars`; clear fields with `dyec unset-vars`. It is
not an environment-variable shim: DYEC never reads or writes `DYEC_*` variables,
and direct `aws`/`pcluster` commands still require their normal profile and
region setup. See [cli_reference.md](cli_reference.md) for precedence and
strict-file validation rules.

## Local Validation

```bash
dyec runtime check
dyec runtime explain
python -m pytest tests/test_environment_contract.py -q
```
