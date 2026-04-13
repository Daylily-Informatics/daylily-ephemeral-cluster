# Pip Install

The supported development flow is still a repo checkout plus `source ./activate`, but the Python dependency source is now `pyproject.toml`.

## When To Use Pip Directly

Use a direct pip install when you want the Python package and CLI in an existing environment without the full checkout-managed Conda bootstrap.

```bash
python -m pip install .
```

For editable local development:

```bash
python -m pip install --editable ".[dev]"
```

## What Pip Does And Does Not Provide

`pyproject.toml` provides the Python package dependencies for:

- `daylily-ec`
- the packaged Python workflow helpers
- the dev and test extras used from a repo checkout

Direct pip install does not supply the non-Python operator tooling from `environment.yaml`. For full operator workflows you still need the external tools that the supported commands rely on, including:

- `aws`
- `pcluster`
- `session-manager-plugin`

If you want the repo’s full operator environment, use `source ./activate` instead of managing those pieces manually.

## Repo Checkout vs Pip Install

- Repo checkout: `source ./activate` builds `DAY-EC`, installs this repo as editable with `dev` extras, and is the supported contributor path.
- Pip install: useful for package consumption, lightweight CLI use, or embedding the Python package into an already-managed environment.
