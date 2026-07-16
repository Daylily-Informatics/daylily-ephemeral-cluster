# DYEC Controller Detail Contract

`dyec command sample-stats hiomrs-kitchensink` emits the source contract used by
Ursa's controller-detail view. Collect it for one exact analysis root:

```bash
dyec --json command sample-stats hiomrs-kitchensink \
  --name <report-name> \
  --profile lsmc \
  --region us-west-2 \
  --cluster <cluster> \
  --analysis-root /fsx/analysis_results/<owner>/<analysis-id>
```

The report schema is `dyec.command_sample_stats.v2`. It retains every v1 field
and adds terminal, scheduler, milestone, runtime, cost, and artifact evidence.
The required report name remains the sole top-level JSON key.

## Evidence Rules

- Controller `SUCCESS` requires controller return code `0`, complete Snakemake
  progress, no active exact-root controller, an available and empty exact-root
  Slurm query, and all three strict artifacts.
- The strict artifacts are `DAY_final_multiqc.html`,
  `DAY_final_multiqc_data/multiqc_data.json`, and
  `dayoa_evidence_manifest.json`.
- Missing scheduler evidence cannot prove success. An empty or unavailable
  queue is never interpreted as workflow completion.
- Job counts retain their source. DAG completion/still-to-run comes from the
  current Snakemake master log. Running, pending, and dependency-blocked counts
  come from exact-`WorkDir` `squeue`/`scontrol`. Failed allocation counts come
  from exact-`WorkDir` `sacct -X`. Retry counts require explicit retry or Slurm
  restart evidence.
- A milestone reports the exact scheduler job ID/name, matched rule, scheduler
  state/reason, elapsed time, explicit ETA text when present, first observed
  error in an exact matched log, restart count, log paths, and terminal
  accounting evidence. Unobserved values remain null.

## Unit Runtime And Cost

Per-library `full_wall` time is available only after every configured milestone
artifact exists and the controller start is observed from process elapsed time
or encoded in the master-log name. It spans that source-backed start to the
latest required unit artifact timestamp. A timestamp that predates the observed
start is reported as inconsistent; a directory modification time is not
accepted as a controller start for this calculation.

`dag_critical_path_no_wait` remains null unless DayOA emits task dependency and
timing evidence. Benchmark duration sums are not treated as a critical path.

Exact unit task cost is the sum of `task_cost` for rows whose `sample` equals
the authoritative `ANALYSIS_UNIT_UID` in
`results/day/<build>/reports/benchmarks_summary.tsv`. The value is withheld if
any matched row lacks a finite `task_cost`.

## Specialized Evidence

- Observed-sex evidence is a list of values read from the unit's emitted
  `*.sex_complement.json` files. DYEC does not collapse discordant values into
  an inferred consensus.
- Hybrid-SV provenance is read from the emitted
  `<unit>.hiomrs_sr.na.hiomrs.sv.provenance.json`, including the selected
  callset and whether short-read fallback ran.
- DAG download still requires an explicit new destination. DYEC verifies byte
  count and SHA-256 and refuses overwrite.

Collection is read-only apart from the required analysis visit audit record.
No identities, terminal states, costs, or completion claims are invented from
queue absence, sample-name heuristics, or an unavailable source.
