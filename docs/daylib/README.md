# daylib

`daylib/` contains legacy library code that still supports Daylily cost estimation and compatibility paths. It is no longer the primary operator interface.

## Current Role

`daylib/` remains useful for:

- cost and resource estimation helpers
- compatibility code still exercised by the test suite
- older scripts that have not yet been fully folded into `daylily_ec/`

For active operator workflows, use:

- [`../../README.md`](../../README.md)
- [`../quickest_start.md`](../quickest_start.md)
- [`../operations.md`](../operations.md)

## Local Setup

```bash
./bin/init_dayec
conda activate DAY-EC
```

## Sanity Checks

```bash
python -m pytest tests/ -k daylib
python - <<'PY'
import daylib
import daylily_ec
print(daylib.__name__, daylily_ec.__name__)
PY
```

## Related Code

- [`../../daylib/config.py`](../../daylib/config.py)
- [`../../daylib/day_factory.py`](../../daylib/day_factory.py)
- [`../../daylily_ec/`](../../daylily_ec/)
