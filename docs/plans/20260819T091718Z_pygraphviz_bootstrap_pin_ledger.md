# PyGraphviz Bootstrap Pin and Immutable Boot-Config Publish Ledger

Date: 2026-08-19

## Objective

Pin the PyGraphviz pip installation used by the Ubuntu cluster bootstrap and
DAY-EC headnode rebuild to a release compatible with their declared Python
versions, validate the package payload, fast-forward the result to `main`, and
publish the resulting boot-config bundle to its content-addressed S3 release
prefix for the next cluster create.

## Gate 0: Inventory Freeze

- Baseline: `origin/main` at `d978c649acf5ab83a0902df7c0724c175a087227`.
- Ubuntu bootstrap uses system `python3` on Ubuntu 22.04; the failed create
  selected the `pygraphviz-2.0.1` CPython 3.10 wheel before receiving a PyPI
  HTTP 502.
- `environment.yaml` declares DAY-EC Python `3.11`; the headnode rebuild uses
  that environment's `python -m pip` path.
- The source bootstrap and packaged bootstrap payload are byte-identical before
  this change.
- The immutable S3 publisher is
  `daylily_ec.workflow.create_cluster.publish_cluster_boot_config`; it accepts
  only the deterministic `releases/sha256-...` prefix and writes with
  `IfNoneMatch="*"`.
- No cluster retry, resource deletion, cache mutation, or budget action is in
  scope.

## Execution Rows

| ID | Category | Status | Evidence / terminal note |
| --- | --- | --- | --- |
| G0 | config_or_startup_contract | SUCCESS | Inventory frozen as recorded above. |
| P1 | feature_implementation | SUCCESS | Both runtime pip paths now install `pygraphviz==2.0.1` and retain explicit import checks. |
| P2 | contract_test | SUCCESS | Exact-pin assertions added; source and packaged bootstrap equality remains covered. |
| P3 | contract_test | SUCCESS | Both shell copies pass `bash -n`; 31 focused tests pass. PyPI reports `Requires-Python >=3.10` with Linux CPython 3.10 and 3.11 wheels. |
| P4 | active_product_contract | SUCCESS | Commit `a450bd89059d7cc521e62f8219d20d018d8d55f1` fast-forwarded `origin/main` from `d978c649`; no force push. |
| P5 | config_or_startup_contract | SUCCESS | Published and read-back verified seven immutable objects at `s3://lsmc-dayoa-references-usw2/runtime_assets/cluster_boot_config/releases/sha256-7c3ef64e47e5c2c083d80e8815793ea07a72905ab86909c03e6aea2b03285b2e`. The Ubuntu script is SHA-256 `f9b2891e9ea83cbb07570dcf48ae01c906cad09f86927fa3c3dde391f116bbb1`; its body and `daylily-sha256` metadata both match source. |

## Acceptance

All rows must be terminal. The published S3 prefix must be a new immutable
content-addressed release whose Ubuntu bootstrap script contains the exact
PyGraphviz pin. The failed cluster is not retried by this work.

## Completion

All execution rows are terminal and successful. No cluster, FSx, DRA, cache,
budget, or Slurm resource was changed or retried.
