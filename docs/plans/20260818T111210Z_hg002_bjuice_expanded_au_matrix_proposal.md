# HG002 Bjuice expanded native-SR × cumulative-ONT AU matrix proposal

UTC opened: 2026-08-18T11:12:10Z
State: PROPOSED — no workflow, cluster, Slurm, DRA, S3, or source-data mutation is authorized by this document.

## Decision and interpretation

The recommended next experiment is a coherent 9 × 9 factorial matrix: **81
new AUs**. It starts at the practical existing low-input anchor of nominal
0.5× Illumina with ONT cumulative input [0,1) (observed previously as
approximately 0.57× LR), and ends at full Illumina with cumulative ONT
[0,72).

[0,72) is an ONT input-time window, not an asserted 72× coverage. The
resulting LR coverage must be measured from the LR Mosdepth summary after
each run and must be the horizontal plotting coordinate. Likewise, the
Illumina plot coordinate remains native-SR Mosdepth coverage, not a requested
downsampling target or RSR coverage.

## AU design

Every pair in the following Cartesian product is one new analysis unit:

| Axis | Values | Input control |
| --- | --- | --- |
| Illumina nominal native-SR target | 0.5×, 1×, 2×, 5×, 10×, 15×, 20×, 30×, full | Deterministic SR read selection from the same full Illumina source. The pre-run planning denominator is the directly observed 43.73× full native-SR coverage. |
| ONT cumulative source window | [0,1), [0,2), [0,4), [0,8), [0,16), [0,24), [0,36), [0,48), [0,72) | Fixed start at zero; use the supported DayOA cumulative-hour input control and retain the exact input manifest. |

This includes the boundary and calibration cells:

| Required cell | Purpose |
| --- | --- |
| 0.5× ILMN × [0,1) ONT | Practical low-input corner. |
| full ILMN × [0,1) ONT | SR-saturated / LR-limited boundary. |
| 0.5× ILMN × [0,72) ONT | LR-saturated / SR-limited boundary. |
| full ILMN × [0,72) ONT | Full-input endpoint requested for the matrix. |
| Nine same-rank pairs | Diagonal dose-response anchors. |
| All remaining off-diagonal pairs | Separates SR- and LR-limited regimes and enables interaction estimation rather than a one-dimensional ladder. |

## Illumina planning fractions

These are planning fractions only, calculated from the known 43.73× full
native-SR baseline. The completed AU must report its measured native-SR
coverage instead.

| Nominal ILMN target | Source fraction |
| ---: | ---: |
| 0.5× | 0.011433798 |
| 1× | 0.022867597 |
| 2× | 0.045735193 |
| 5× | 0.114337983 |
| 10× | 0.228675966 |
| 15× | 0.343013949 |
| 20× | 0.457351932 |
| 30× | 0.686027898 |
| full | 1.000000000 |

## Required preflight and acceptance contract

1. Confirm that the authoritative ONT input manifest supports every requested
   cumulative endpoint through [0,72) and freeze the exact source-object
   inventory and hashes before rendering any workflow.
2. Create one in-clone AU config per Cartesian cell. Do not reuse E1's
   declared-fraction records: its native-SR evidence was full depth at every
   AU and is therefore not a valid SR downsampling matrix.
3. After each terminal workflow, retain native-SR, RSR-audit, and LR Mosdepth
   summaries plus the input manifest in the exported analysis clone.
4. Accept a matrix point only when its S3-exported clone contains the three
   summaries and the actual native-SR and LR values can be independently
   re-read. Use actual values in all figures; retain requested targets only in
   an audit table.
5. Add no fill-in values. A missing [0,end) input slice, failed analysis, or
   missing summary is an explicit missing cell, not an interpolated result.

## Execution boundary

This is an experiment proposal, not execution authority. A separate user
authorization must choose the exact DYEC catalog command, cluster, DayOA tag,
project/cost center, concurrency, export policy, and whether all 81 AUs or a
budgeted first wave should be launched.
