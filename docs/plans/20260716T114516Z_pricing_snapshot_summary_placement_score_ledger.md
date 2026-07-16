# Pricing Snapshot Summary And Spot Placement Score Ledger

Controlling request: replace raw `--table-view` rows with per-partition/AZ pricing summaries and add a real EC2 Spot Placement Score tied to an explicit target capacity while retaining raw points in JSON.

## Gate 0 Baseline

- Ledger: `docs/plans/20260716T114516Z_pricing_snapshot_summary_placement_score_ledger.md`
- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch/HEAD: `codex/local-release-10.3.24` at `cac55384d462a6011953aa866658d555eedab430`
- Dirty state before this follow-up: five modified files from the immediately preceding `--table-view` implementation: `daylily_ec/aws/pricing_snapshots.py`, `daylily_ec/cli.py`, `docs/cli_reference.md`, `tests/test_cli_registry_v2.py`, and `tests/test_pricing_snapshots.py`.
- Baseline validation: `pytest -q tests/test_pricing_snapshots.py tests/test_cli_registry_v2.py` -> `182 passed`; targeted Ruff and `git diff --check` passed.
- AWS API contract: installed botocore exposes `GetSpotPlacementScores` with explicit `InstanceTypes` (maximum 1000), `TargetCapacity` (1 through 2,000,000,000), `TargetCapacityUnitType=vcpu`, `SingleAvailabilityZone`, `RegionNames`, and paginated `SpotPlacementScores` containing `AvailabilityZoneId` and integer `Score`.
- Live limit: live validation is read-only and may use the configured `lsmc` profile; no cluster, job, budget, or infrastructure mutation is authorized or required.
- Assumption: target capacity is explicitly expressed as total vCPUs through `--target-capacity-vcpus`; no default or inferred target is permitted.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| PRICE-001 | pricing model | Produce one per-partition/AZ summary with priced/configured count, coverage percent, min, median, harmonic mean, max, and spread while retaining raw points | SUCCESS | feature_implementation | Gate 1 | orchestrator | `daylily_ec/aws/pricing_snapshots.py`; deterministic summary test proves 100% and 66.67% coverage plus exact statistics; live JSON retained 64 raw `i8` points and four summaries |  | Summary contract is implemented without replacing raw points |
| PRICE-002 | AWS capacity signal | Collect separately labelled EC2 Spot Placement Scores per partition/AZ for an explicit target vCPU capacity | SUCCESS | feature_implementation | Gate 4 | orchestrator | Paginated fake API test proves AZ-ID mapping; live 384-vCPU `i8` scores were `2a=9`, `2b=9`, `2c=8`, `2d=9` |  | Scores come from `GetSpotPlacementScores`, not price presence or dry-run launches |
| CLI-001 | CLI contract | Require `--target-capacity-vcpus` for `--table-view`; preserve raw JSON and reject conflicting/malformed output contracts before AWS calls | SUCCESS | config_or_startup_contract | Gate 4 | orchestrator | `dyec pricing snapshot --help`; negative CLI tests reject missing target and `--json`/`--table-view` conflict before collection |  | Explicit target required; JSON may request scores while retaining raw points |
| TEST-001 | tests | Cover summary math, missing-price coverage, placement-score pagination/AZ mapping, CLI flag propagation, and negative contracts | SUCCESS | contract_test | Gate 5 | orchestrator | Initial whitespace-coupled assertion failed at 8 passed/1 failed; padding-independent bugfix applied; final `pytest -q tests/test_pricing_snapshots.py tests/test_cli_registry_v2.py` -> 184 passed; Ruff passed |  | Required bugfix attempt succeeded and the full relevant suite is green |
| DOC-001 | docs | Document summary columns, explicit capacity semantics, score range, and raw JSON preservation | SUCCESS | feature_implementation | Gate 5 | orchestrator | `docs/cli_reference.md` documents command, cross-sectional statistics, spread semantics, score scale, target requirement, and JSON fields |  | User-facing contract is documented |
| LIVE-001 | live verification | Run a bounded read-only live table smoke check with `AWS_PROFILE=lsmc` and an explicit target vCPU capacity | SUCCESS | contract_test | Gate 5 | orchestrator | Live `i8`, `us-west-2`, 384-vCPU table at `2026-07-16T11:50:01Z` rendered four AZ rows; live JSON reported `summary_count=4`, `raw_point_count=64`, and four placement scores |  | Read-only live proof passed; no AWS state was mutated |

## Final Report

All rows terminal: yes

Objective complete: yes

Status counts:

- SUCCESS: 6
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0

Changed files:

- `daylily_ec/aws/pricing_snapshots.py`
- `daylily_ec/cli.py`
- `tests/test_pricing_snapshots.py`
- `tests/test_cli_registry_v2.py`
- `docs/cli_reference.md`
- `docs/plans/20260716T114516Z_pricing_snapshot_summary_placement_score_ledger.md`

Validation:

- `ruff check daylily_ec/aws/pricing_snapshots.py daylily_ec/cli.py tests/test_pricing_snapshots.py tests/test_cli_registry_v2.py` -> passed
- `pytest -q tests/test_pricing_snapshots.py tests/test_cli_registry_v2.py` -> 184 passed
- Complete repository suite after rebasing onto the pushed `10.3.24` closeout tip: `python -m pytest -q` -> 2,224 passed, 11 skipped, one dependency deprecation warning in 80.71 seconds.
- `git diff --check -- <owned files>` -> passed
- Live table and JSON smoke checks with `--profile lsmc --region us-west-2 --partition i8 --target-capacity-vcpus 384` -> passed

Non-success terminal rows: none.

Residual risks:

- Spot prices and Spot Placement Scores are point-in-time AWS observations and will change.
- Price coverage means current price points returned for configured instance types; it is deliberately not labelled as capacity availability.
