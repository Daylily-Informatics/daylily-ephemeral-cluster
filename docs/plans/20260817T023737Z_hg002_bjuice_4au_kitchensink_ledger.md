# HG002 Bjuice four-AU HIOMR2 kitchensink-mega execution ledger

Created: 2026-08-17T02:37:37Z

Objective: launch one new HG002 analysis containing four explicit coverage combinations through full-chromosome HIOMR2 kitchensink mega and final MultiQC, deliberately excluding all Inflection packaging targets.

## Gate 0 baseline

- Cluster: `prod-cand-1703`; region `us-west-2`; profile `lsmc`; remote user `ubuntu`.
- Cluster state at inventory: `UPDATE_COMPLETE`; attributable Slurm jobs: zero.
- DYEC source: current `origin/main` base `6516e1064d91c84615f84553a1e5a09a35e298a8` plus the ledgered custom-plan/catalog change on `codex/hg002-bjuice-4au-kitchensink-20260816`.
- DayOA pin: exact tag `15.0.10`.
- Direct Illumina denominator: `43.73x`, from `direct_ilmn_coverage_receipt.json` and source metric SHA-256 `5db712bdee30b383422f5729ea73497896aca01fd2db749b39a1b829c6484f80`.
- Input mounts: existing ILMN DRA `dra-0b789d77240836540` and ONT DRA `dra-0281455160baf94c5`.
- Source ONT input contains 73 hourly chunks per flowcell; `[0,36)` is within the declared input range.
- Project and cost center: `prod-cand-1703-ccenter`.
- No export or FSx deletion is included in this request.

## Requested matrix

| AU | ILMN target | SUBSAMPLE_PCT | ONT target | ONT interval |
| --- | ---: | ---: | ---: | --- |
| `20xby15x` | 20x | `0.457351932311` | 15x | `[0,36)` |
| `30xby15x` | 30x | `0.686027898467` | 15x | `[0,36)` |
| `10xby10x` | 9.85x | `0.225245826663` | 9.67x | `[0,19)` |
| `12xby12x` | 12.71x | `0.290647152984` | 11.43x | `[0,24)` |

Fractions are `ROUND_DOWN(target / 43.73, 12 places)` and are all `>0` and `<=1`. ONT 19-hour and 24-hour endpoints are direct completed-experiment measurements; the 36-hour endpoint is the nearest integer from the previously fitted cumulative aligned-yield curve for 15x.

## Control rows

| ID | Requirement | Status | Evidence / terminal note |
| --- | --- | --- | --- |
| G0-001 | Verify cluster, source pins, no job collision, inputs, denominator, and attainable intervals. | SUCCESS | Gate 0 baseline above. |
| SRC-001 | Add explicit custom AU-plan support without changing the fixed seven-AU default. | SUCCESS | Focused generator suite: `14 passed`; default and custom matrices both covered. |
| CAT-001 | Add literal no-Inflection custom multi-AU kitchensink-mega catalog command and packaged parity. | SUCCESS | Command `bjuice-v2-hg002-custom-multi-analysis-unit-hiomr2-kitchensink-mega`; catalog/CLI suite `265 passed`; source/payload SHA-256 `04acb3feaf78cbfe0132138d217f262d4774f376a116225c94d8f90a6a14abbd`. |
| MAN-001 | Generate and validate exactly four six-manifest AU rows with blank nullable live EUIDs. | SUCCESS | `docs/plans/20260817T023737Z_hg002_bjuice_4au_manifests/`; 4 AU rows, 16 AU-input rows, 4 sequencing inputs, and all nullable live EUID fields blank. |
| DRY-001 | Render and run catalog dry controller with exactly four AUs, no packaging target, zero Slurm jobs, and rc=0. | SUCCESS | Session `prod-cand-1703-hg002-bjuice-4au-kitchensink-dry-20260817T024600Z`; 1,033 planned jobs; terminal `rc=0`; zero Slurm submissions. |
| LIVE-001 | Launch the fresh live controller through DYEC catalog on `prod-cand-1703`. | SUCCESS | Initial session exited `rc=1` on the exhausted `1500 USD` cluster budget. After exact double approval, DYEC raised both `prod-cand-1703` and `prod-cand-1703-ccenter` from `1500` to `2500 USD` and verified both. Same-root recovery session `prod-cand-1703-hg002-bjuice-4au-kitchensink-budget-retry-20260817T031039Z` is running. |
| MON-001 | Record initial controller and attributable Slurm state. | IN_PROGRESS | Recovery controller is attributed and `RUNNING`; first DYEC observation recorded 11 submitted Slurm jobs, all `CONFIGURING` (`5523`-`5533`). |

## Execution boundary

- Use activated DYEC only for cluster/headnode/catalog/controller operations.
- Never invoke raw Snakemake; catalog controllers use `dy-r` in persistent tmux as `ubuntu`.
- The only workflow target is `produce_sentdhiomr2_slim_kitchensink_mega`; the rendered command must not contain `inflection`, `package`, or `seqone_delivery_batch_id`.
- A dry-run root and live root are distinct and fresh.
- No export, delete, release, PR, or tag is authorized by this ledger.
