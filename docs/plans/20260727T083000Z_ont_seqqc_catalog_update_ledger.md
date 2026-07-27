## Control Ledger

Controlling request: update DYEC's ONT SeqQC command-catalog profile to reproduce the composite ONT QC plus demultiplexed FASTQ-QC workflow.
Ledger path: `docs/plans/20260727T083000Z_ont_seqqc_catalog_update_ledger.md`

### Gate 0 baseline

- DYEC worktree: `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-ont-seqqc-catalog-20260727`, branch `codex/ont-seqqc-catalog-20260727`, based on `origin/main` `93dfb531`.
- Existing `ont_run_qc` used `produce_ont_run_qc`, `genome: hg38`, `jobs: 5`, and did not reproduce the active composite ONT-plus-demux target.
- DayOA immutable pin remains `13.0.56`; the live 127-thread/concurrency amendment is intentionally not represented as released/validated catalog behavior yet.

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Terminal Note |
|---|---|---|---|---|---|---|---|---|
| ONTCAT-01 | DYEC catalog | Launch composite ONT QC + demux-MultiQC target with `genome: hg38`, six controller jobs, and artifact producers | SUCCESS | feature_implementation | Gate 0 | Codex | Both catalog copies updated; user confirmed `hg38` is the required genome. | Runtime command matches the active workflow target shape. |
| ONTCAT-02 | DYEC tests | Prove catalog command rendering and packaged/source catalog parity | SUCCESS | contract_test | Gate 0 | Codex | `python -m pytest -q tests/test_repository_catalog.py tests/test_lsmc_bio_fork_contract.py tests/test_hiomrs_command_catalog.py tests/test_tests_runner.py` -> 51 passed. | Catalog parsing and launch rendering are verified. |
| ONTCAT-03 | Release pin | Represent the new 127-thread/concurrency DayOA source as a catalog release pin | BLOCKED | config_or_startup_contract | Gate 0 | Codex | DayOA source amendment is uncommitted and active run 136 is not terminal. | Requires a successful live result, committed DayOA release, then a new immutable catalog pin. |
