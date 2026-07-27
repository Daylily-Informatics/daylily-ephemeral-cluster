# Ultima RunQC catalog update — DayOA 13.0.58

Created: 2026-07-27T02:00:00Z
Branch: `codex/ultima-runqc-catalog-13058-20260727`

## Gate 0: baseline

The `ultima_run_qc` entry was pinned to DayOA `13.0.56` and injected legacy
`samples_table` and `units_table` runtime parameters. The historical validation
record shows that those parameters caused an early configuration failure. DayOA
`13.0.58` is the annotated tag at merged commit
`03cb2f3d941d2c26ef5476d5de90a836ebd7e8af`, which contains the standalone
Ultima RunQC implementation.

## Execution ledger

| ID | Acceptance item | State | Evidence / boundary |
| --- | --- | --- | --- |
| CAT-001 | Pin both catalog copies to the merged DayOA 13.0.58 release. | COMPLETE | `validated_version` and `git_tag` are `13.0.58` in the source catalog and packaged payload mirror. |
| CAT-002 | Remove obsolete Ultima manifest parameters without altering ONT or Illumina entries. | COMPLETE | Ultima now supplies only `run_context_file`; focused assertions reject emitted `samples_table` and `units_table` parameters. |
| CAT-003 | Preserve factual validation provenance. | COMPLETE | Historical failure is retained. The successful one-run direct-DYEC controller is recorded at source commit `44d326f9f4efe95be20d1027ff008b85e9bbadb1`; unavailable AZ/DYEC build facts are explicitly `unrecorded`, not inferred. |
| VAL-001 | Parse the catalog, verify source/payload identity, and render the Ultima launch command. | COMPLETE | `pytest -q tests/test_repository_catalog.py tests/test_hiomrs_command_catalog.py` passed 16 tests. `dyec catalog render ultima_run_qc ... --dry-run` resolves `13.0.58` and emits only `run_context_file=config/runs.tsv`, with no legacy manifest inputs. |
| PUB-001 | Commit, push, and merge the non-regressive catalog update. | PENDING | Requires successful validation and GitHub checks. |

## Scope boundary

This is a DYEC catalog release update only. It does not launch a DayOA workflow,
modify Slurm, change existing ONT/Illumina routing, or create/alter cloud
resources.
