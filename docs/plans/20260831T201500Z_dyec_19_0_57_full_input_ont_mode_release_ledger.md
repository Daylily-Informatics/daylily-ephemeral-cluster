# DYEC 19.0.57 full-input ONT mode release ledger

## Scope

Correct the public `dyec catalog config-bjuice-crosswalk-run` materializer so complete enumerated ONT inputs use DayOA's established blank-hour contract. The generated runtime YAML must omit `ont_fastq_hour_window_mode`; the six-manifest AU rows already carry blank start/stop hours. Preserve DayOA `16.0.39` and all catalog command pins.

## Ledger

| Row | Disposition | Evidence |
|---|---|---|
| BASE-001 | COMPLETE | Clean branch from annotated DYEC `19.0.56`; DayOA remains pinned to `16.0.39`. |
| BUG-001 | COMPLETE | Production dry preflight rejected generated `ont_fastq_hour_window_mode: full_input`; DayOA accepts only explicit `per_analysis_unit`, otherwise the key must be omitted. |
| FIX-001 | COMPLETE | Materializer omits the key and validates its absence for blank full-input ONT slicing. |
| TEST-001 | NOT_RUN_BY_USER_DIRECTION | No pytest or git-oriented test suite was run; production dry/live validation is the requested test. |
| REL-001 | PENDING | Commit, push, annotated tag, GitHub release, and tag verification. |
| OPS-001 | PENDING | Update operator checkout, force-configure both headnodes, regenerate exact configs, and relaunch fresh dry capsules. |
