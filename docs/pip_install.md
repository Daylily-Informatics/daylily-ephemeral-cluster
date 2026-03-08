# Pip Install Usage

`daylily-ephemeral-cluster` can be installed with `pip` and used from any working directory. This is mainly useful for downstream repos, automation environments, or operator machines where you do not want to keep a full checkout around.

## Install

From a clean virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate

# From a local checkout
pip install /path/to/daylily-ephemeral-cluster

# Or from git
pip install "git+https://github.com/Daylily-Informatics/daylily-ephemeral-cluster.git@<ref>"
```

## Verify The Install

```bash
daylily-ec --help
daylily-ec version
daylily-ec info
daylily-ec resources-dir
```

## Packaged Resources

The wheel includes packaged repo assets such as `config/`, `etc/`, and selected `bin/` helpers. They are extracted at runtime under:

`~/.config/daylily/resources/<package-version>/`

Use this command to resolve the active resource directory:

```bash
daylily-ec resources-dir
```

Override the resource root when needed:

```bash
export DAYLILY_EC_RESOURCES_DIR=/path/to/override-root
```

The override directory must contain the Daylily `config/`, `etc/`, and `bin/` trees expected by the helper scripts.

## Running Bundled Helper Scripts

Some helper scripts are packaged alongside the Python CLI. Run them via the resolved resource directory:

```bash
RES_DIR="$(daylily-ec resources-dir)"

"$RES_DIR/bin/daylily-create-ephemeral-cluster" --help
"$RES_DIR/bin/daylily-stage-analysis-samples-headnode" --help
```

## Host Requirements

`pip` installs the Python dependencies, but some workflows still expect host tools or external configuration:

- AWS CLI v2 for commands that shell out to `aws`
- `ssh` and `scp` for remote helper flows
- a configured AWS profile when operating on real infrastructure
- standard Unix tools such as `sed`, `awk`, and `bash`

If you want the managed conda workflow instead, use [`DAY_EC_ENVIRONMENT.md`](DAY_EC_ENVIRONMENT.md).
