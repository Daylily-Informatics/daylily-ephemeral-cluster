# Pip Install Usage (Downstream Repos)

`daylily-ephemeral-cluster` can be installed with `pip` and used from **any**
working directory (no repo checkout layout required).

## Install

From a clean virtualenv:

```bash
python -m venv .venv
source .venv/bin/activate

# From a local checkout:
pip install /path/to/daylily-ephemeral-cluster

# Or from git (example):
# pip install "git+https://github.com/Daylily-Informatics/daylily-ephemeral-cluster.git@<tag>"
```

Verify:

```bash
python -m daylily_ec --help
daylily-ec --help
daylily-ec resources-dir
```

## Packaged Assets ("Resources")

Static repo assets (`config/`, `etc/`, and selected `bin/` helpers) are bundled
into the wheel and extracted at runtime to:

`~/.config/daylily/resources/<package-version>/`

Use this command to locate them:

```bash
daylily-ec resources-dir
```

Override extraction (useful for dev or custom templates):

```bash
export DAYLILY_EC_RESOURCES_DIR=/path/to/override-root
```

The override directory must contain at least:

- `config/`
- `etc/`
- `bin/`

## Running Legacy `bin/` Tools

`bin/` tools are shipped as packaged assets. To run them from anywhere:

```bash
RES_DIR="$(daylily-ec resources-dir)"
"$RES_DIR/bin/daylily-create-ephemeral-cluster" --help
```

## External Dependencies

These are **not** installed by pip and must be present on the host:

- `aws` (AWS CLI v2)
- `ssh`, `scp`
- `jq` (required by `check_aws_permissions.sh`)

Some scripts may also require standard Unix tools like `sed`, `awk`, and `perl`.

