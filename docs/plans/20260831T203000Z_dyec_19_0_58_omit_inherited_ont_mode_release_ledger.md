# DYEC 19.0.58 omit inherited full-input ONT mode release ledger

## Scope

Complete the narrow `19.0.57` crosswalk materializer correction. The shared Bjuice runtime template supplies `ont_fastq_hour_window_mode: per_analysis_unit`; complete enumerated crosswalk inputs must explicitly remove that inherited key so DayOA uses its established global/full-input contract. Preserve DayOA `16.0.39` and all command catalog pins.

## Ledger

| Row | Disposition | Evidence |
|---|---|---|
| BASE-001 | COMPLETE | Clean branch from annotated DYEC `19.0.57`; published tags are not moved. |
| BUG-001 | COMPLETE | Public 19.0.57 materialization rejected its inherited `per_analysis_unit` value while validating the required omitted-key contract. |
| FIX-001 | COMPLETE | The crosswalk materializer removes `ont_fastq_hour_window_mode` after constructing the shared runtime mapping; its existing validation and focused regression require absence. |
| TEST-001 | NOT_RUN_BY_USER_DIRECTION | No pytest or git-oriented test suite was run; the public materialization command and production dry/live capsules are the requested validation. |
| REL-001 | PENDING | Commit, push, annotated tag, GitHub release, and tag verification. |
| OPS-001 | PENDING | Update operator checkout, force-configure both headnodes, regenerate exact configs, and relaunch fresh dry capsules. |
