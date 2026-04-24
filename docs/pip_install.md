# Pip Install

The supported operator path for a repo checkout is still:

```bash
source ./activate
```

That path gives you the full `DAY-EC` Conda environment and installs this repo editable.

This document covers the other path: installing the Python package directly.

## What Pip Installation Owns

`pyproject.toml` is the Python dependency source of truth. A pip install gives you:

- `daylily-ec`
- `dyec`, a shorter alias for the same CLI entrypoint
- the package runtime dependencies
- `aws-parallelcluster`, which provides `pcluster`

For an editable checkout install:

```bash
python -m pip install --editable "."
```

For a non-editable install:

```bash
python -m pip install .
```

## What Pip Installation Does Not Own

The pip install path does not provide the non-Python operator tooling that `environment.yaml` carries. Most importantly, you still need:

- `aws`
- `session-manager-plugin`
- a shell environment in which those tools are available

If you want the fully supported local operator environment, use the Conda path instead.

## Minimal Example

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --editable "."
daylily-ec version
dyec version
pcluster version
```

If `pcluster version` fails in that environment, your Python install path is incomplete.

Then verify the external tools:

```bash
aws --version
session-manager-plugin
```

## When To Use This Path

Use pip installation when you:

- are developing on a custom Python environment
- want package-only inspection without Conda bootstrapping
- are integrating the CLI into an existing environment you already control

Do not use it if you want the least-friction supported operator shell. In that case, use `source ./activate`.
