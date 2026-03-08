# Contributing

Contributions are welcome. Keep the current operator workflow accurate, keep the docs canonical, and avoid reintroducing stale commands or paths.

## Local Setup

From a repo checkout:

```bash
./bin/check_prereq_sw.sh
./bin/init_dayec
conda activate DAY-EC

python -m daylily_ec info
python -m daylily_ec --help
```

## Before Opening A Change

Run the checks that match your change:

```bash
pytest tests/
python -m daylily_ec --help
python -m daylily_ec info --help
python -m daylily_ec pricing snapshot --help
./bin/init_dayec --help
```

If you touched operator scripts, also run the relevant helper `--help` commands from `bin/`.

## Documentation Rules

- `README.md` is the public, operator-first landing page.
- `docs/quickest_start.md` is the canonical create-cluster runbook.
- `docs/operations.md` covers the live day-2 operator workflow.
- `docs/overview.md` carries the public narrative, architecture, and benchmark context.
- Historical material belongs in `docs/archive/`, not in the live docs tree.

When updating docs:

- prefer current command output over hard-coded version prose
- do not reference scripts that are not shipped in this repo
- fix links when moving content
- archive stale material instead of leaving duplicate live docs behind

## Code And Review Notes

- Prefer the Python control plane in `daylily_ec/` over growing new legacy shell behavior.
- Preserve backward-compatible wrappers in `bin/` when they are still part of the user-facing flow.
- Keep changes scoped and documented; if behavior changes, update the relevant operator doc in the same change.
