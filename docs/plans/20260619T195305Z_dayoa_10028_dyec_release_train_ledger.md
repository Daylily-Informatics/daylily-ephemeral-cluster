# DayOA 10.0.28 And DYEC Release Train Ledger

Date opened: 2026-06-19T19:53:05Z

## Objective

Carry the requested chained release train through on `jem-dev`:

1. Move the validated DayOA dynamic partition state onto `jem-dev`, tag and push `10.0.28`.
2. Update DYEC DayOA pins to `10.0.28`, commit/push `jem-dev`, tag and push `10.0.48`.
3. Update DYEC self-pins to `10.0.48`, commit/push `jem-dev`, tag and push `10.0.49`.

## Gate 0 Baseline

| Item | Evidence |
|---|---|
| DayOA repo | `/Users/jmajor/projects/lsmc/daylily-omics-analysis` |
| DayOA starting branch | `codex/dynamic-partition-slim-validation`, clean, at `e4cacfb` |
| DayOA starting `jem-dev` | `72ee17b`, annotated tag `10.0.27` |
| DayOA next tag | `10.0.28`, selected after `git fetch origin jem-dev --tags --prune` |
| DYEC repo | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` |
| DYEC starting `jem-dev` | fast-forwarded to `origin/jem-dev` at `32bec4d7` before pin edits |
| DYEC starting tags | highest fetched tag `10.0.47`; next tags `10.0.48` and `10.0.49` |
| Pre-existing DYEC untracked files | AWS cost-report docs under `docs/`; not part of this release train |

## Rows

| ID | Area | Requirement | Status | Evidence | Terminal Note |
|---|---|---|---|---|---|
| DAYOA-001 | DayOA verification | Run focused dynamic partition tests before promoting to `jem-dev`. | SUCCESS | `conda run -n DAY-EC python -m pytest tests/test_dynamic_resource_helpers.py tests/test_slurm_caller_partitions.py tests/test_multiqc_qc_targets.py -q` -> `48 passed`. | Validated before branch promotion. |
| DAYOA-002 | DayOA release | Fast-forward `jem-dev` to the dynamic partition validation tip, annotate `10.0.28`, and push branch/tag. | SUCCESS | `git merge --ff-only codex/dynamic-partition-slim-validation`; `git push origin jem-dev`; `git push origin 10.0.28`; `git cat-file -t 10.0.28` -> `tag`. | DayOA `jem-dev`, tag target, and `HEAD` all resolve to `e4cacfb`. |
| DYEC-001 | DYEC DayOA pin | Update DYEC DayOA pin surfaces from `10.0.27` to `10.0.28`. | SUCCESS | `pyproject.toml`, both command catalog copies, and fork/catalog tests updated. `conda run -n DAY-EC python -m pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py -q` -> `15 passed`. | Pending commit, tag `10.0.48`, and push. |
| DYEC-002 | DYEC self-pin | After `10.0.48` is pushed, update source and payload self-pins to `10.0.48`. | OPEN | Pending `DYEC-001`. | Final release target will be `10.0.49`. |
| FINAL-001 | Final verification | Verify annotated tags, remote branch heads, and exact reported versions. | OPEN | Pending DYEC releases. |  |
