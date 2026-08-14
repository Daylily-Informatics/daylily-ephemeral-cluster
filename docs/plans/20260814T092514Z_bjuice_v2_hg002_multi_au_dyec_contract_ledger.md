# Bjuice v2 HG002 multi-AU DYEC contract ledger

Created: 2026-08-14T09:25:14Z
Owner: DYEC catalog agent
Scope: local DYEC source, packaged catalog payload, documentation, and tests only. No cluster launch, Slack post, DRA export, or FSx deletion is authorized in this ledger.

## Gate 0 — source boundary

| Check | State | Evidence |
|---|---|---|
| Isolated clean worktree | PASS | `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-bjuice-v2-multiau-20260814` on `codex/bjuice-v2-hg002-multiau-20260814`; the shared detached/dirty checkout was not touched. |
| DayOA release pin | PASS | Annotated DayOA tag `14.0.15`, commit `8781a14abb48e5e17892e4b1d872f8ffa1e54173`, supplied by the release orchestrator. |
| Live operations boundary | PASS | No DYEC cluster/API launch, controller, Slack, DRA export, or delete operation was issued from this worktree. |

## DYEC contract rows

| ID | Deliverable | State | Evidence |
|---|---|---|---|
| DYEC-001 | Fixed HG002 seven-AU generator with direct-only coverage receipt | PASS | `daylily_ec/bjuice_v2_hg002_multi_au_config.py` defines the immutable AU matrix, terminal direct-receipt validation, and Decimal `ROUND_DOWN` fractions. |
| DYEC-002 | Blank live EUID output / test-only duplicate `Z-*` handling | PASS | Generator writes blank nullable EUID fields; persistent duplicate `Z-*` fixture coverage remains explicitly test-only in `tests/test_manifest_set_and_identities.py`. |
| DYEC-003 | Explicit CLI command | PASS | `catalog config-bjuice-v2-hg002-multi-au` accepts no EUID-generation option and requires direct coverage evidence. |
| DYEC-004 | Literal full-prevalence catalog command | PASS | New direct command pins DayOA `14.0.15`, scopes HIOMR2 to `1-25`, uses `ont_fastq_hour_window_mode=per_analysis_unit`, and omits global ONT-hour settings. |
| DYEC-005 | Immutable DYEC release snapshot | PASS | New `17.0.15` snapshot mirrors `current`; parsed semantic comparison confirms historical `17.0.14` is unchanged. |
| DYEC-006 | Source/payload parity, docs, and focused regression evidence | PASS | Source and packaged catalogs match byte-for-byte; focused suite passed 357 tests. |

## Required operational handoff

The operations lane must use the catalog command only after its separate Gate 0 confirms the named cluster, region/profile, two existing Bjuice run mounts, a fresh analysis root/export prefix, and one terminal direct Illumina coverage receipt. The generator intentionally refuses inferred total or hybrid coverage. FSx deletion remains a separate second-approval action after a successful export.

## Completion evidence

- Source and packaged catalog SHA-256: `fdd543213631a45d25bfd678838438000b2ed48bdcc01ae15129b16b529cae2a`.
- Focused regression command: `pytest -q tests/test_bjuice_v2_hg002_multi_au_config.py tests/test_manifest_set_and_identities.py tests/test_repositories_additional_coverage.py tests/test_repository_catalog.py tests/test_repository_catalog_aliases.py tests/test_lsmc_bio_fork_contract.py tests/test_cli_registry_v2.py` — `357 passed in 79.82s`.
- Static/CLI evidence: `python -m py_compile daylily_ec/bjuice_v2_hg002_multi_au_config.py daylily_ec/cli.py daylily_ec/repositories.py`; local `dyec --json catalog list` resolves the new literal command and its `14.0.15` pin.
- Local commit and release handoff follow this ledger update. No DYEC tag or push is performed by this lane.
