# DYEC Controller Target Contract

`dyec workflow launch` emits a source-backed target for the controller it just
created. The contract is additive: all existing `__DAYLILY_*` launch markers
remain unchanged, and one compact JSON marker is added:

```text
__DYEC_CONTROLLER_TARGET__={"schema_version":"dyec.controller_target.v1","controller_id":"analysis-20260716","pid":4242,"cwd":"/fsx/analysis_results/owner/analysis-20260716/daylily-omics-analysis","log_path":"/fsx/analysis_results/owner/analysis-20260716/daylily-omics-analysis/.dyec/controller.log","dag_path":"/fsx/analysis_results/owner/analysis-20260716/daylily-omics-analysis/.dyec/controller-dag.png","analysis_root":"/fsx/analysis_results/owner/analysis-20260716"}
```

The identical payload is written atomically to:

```text
/home/ubuntu/daylily-runs/<session>/controller_target.json
```

## Fields

| Field | Contract |
|---|---|
| `schema_version` | Exact value `dyec.controller_target.v1`. |
| `controller_id` | Actual tmux session name created by this launch. It is an external controller identifier, not a TapDB EUID. |
| `pid` | Positive PID of the tmux pane's DYEC DayOA controller shell. The shell owns the launch lifecycle and remains the stable controller process while the workflow runs. |
| `cwd` | Canonical absolute DayOA checkout path configured by this launch. |
| `log_path` | Canonical stable controller log under `<cwd>/.dyec/`. |
| `dag_path` | Canonical stable concrete-DAG copy under `<cwd>/.dyec/`. |
| `analysis_root` | Canonical parent analysis directory under `/fsx/analysis_results/`. |

`cwd` must be within `analysis_root`; `log_path` and `dag_path` must be within
`cwd`; and the two evidence paths must differ. The launcher rejects malformed,
partial, duplicate, mismatched, non-canonical, or out-of-scope target data.

## Evidence Semantics

- The controller ID and PID come from the tmux launch DYEC created. They are not
  reconstructed from `ps`, a cluster scan, a session-name guess, or UI text.
- The controller log begins once the exact DayOA checkout exists and the
  controller changes into `cwd`. Bootstrap output remains in the existing
  `/home/ubuntu/daylily-runs/<session>/tmux.log`.
- The DAG target is populated only when exactly one new `dags/dag_*.png`
  appears relative to the freshly cloned checkout's pre-launch file set.
- No DAG means the target remains absent. Multiple new DAGs produce an explicit
  ambiguity error. A rulegraph is never used as a fallback.
- Consumers must verify the persisted PID and cwd against live SSM process
  evidence before reading the bounded log or DAG paths.

The receipt does not claim that the workflow is healthy or terminal. Runtime
state remains the responsibility of `dyec analysis status` and the reviewed
command-specific status contracts.
