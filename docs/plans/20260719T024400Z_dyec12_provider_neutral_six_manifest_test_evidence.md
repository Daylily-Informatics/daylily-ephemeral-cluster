# DYEC 12 Provider-Neutral Six-Manifest Test Evidence

Generated: `2026-07-19T02:44:00Z`
Branch: `codex/bjuice-set1-closeout`
Base: `93154b47b9dd59f530aea673283b1d1c7931c405`

## Scope

This evidence covers the DYEC candidate implementation for:

- exact six-manifest validation and hash-preserving headnode staging;
- explicit sequencing-input `MODALITY`, `LAYOUT`, source-bundle, and join-role validation;
- local-only identity receipt validate/plan/apply/status/evidence commands;
- six-manifest analysis and per-analysis-unit status projections;
- removal of active provider-specific URL, registration, discovery, and UI behavior;
- provider-neutral immutable S3 export receipts;
- source/payload parity and static provider-boundary blockers.

It does not cover DayOA/DYEC version pin changes, releases, headnode refresh, or
live acceptance. Those remain A0/A8 work after the cross-repository release
candidate is integrated.

## Results

| Gate | Command | Result |
|---|---|---|
| Full suite | `source ./activate && pytest -q` | `2213 passed, 11 skipped` in `63.36s`; no failures. |
| Final collection reconciliation | `source ./activate && pytest --collect-only -q` | `2224 tests collected`; exactly reconciles `2213 passed + 11 skipped`. An earlier in-progress checkpoint of `2261` preceded the final provider-surface test cleanup and is not release evidence. |
| New-module coverage | `pytest -q tests/test_manifest_set_and_identities.py --cov=daylily_ec.manifest_set --cov=daylily_ec.identity_receipts --cov-report=term-missing --cov-fail-under=90` | `22 passed`; manifest validator `90%`, identity receipts `98%`, combined `93%`. |
| Focused integration | Provider boundary, six-manifest status, local identities, export, workflow, and cluster tests | `348 passed`; no failures. |
| Ruff | `ruff check daylily_ec tests` | `All checks passed!` |
| Compile | `python -m compileall -q daylily_ec` | Exit `0`. |
| Whitespace | `git diff --check` | Exit `0`. |
| Payload parity | `cmp` plus `tests/test_provider_neutral_boundary.py` | Source and packaged sbatch, cluster template, and command catalog are byte-identical. |
| Active provider scan | `rg -n -i 'dayhoff|ursa|bloom|tapdb|dewey|register-dewey|produce-ursa' daylily_ec config` | No active source/config matches. |

The eleven skips are the repository's pre-existing opt-in live staging tests;
they were not converted into passes and no live AWS operation was attempted.

An earlier pre-cleanup collection checkpoint reported 2,261 tests. The final
count is 2,224 because this lane added eight strict sequencing-input and
provider-boundary cases and removed 45 obsolete cases whose only subject was
the deleted provider-registration/network implementation: `2261 + 8 - 45 =
2224`. No surviving test was deselected, filtered, or converted into a skip.

## Contract proof

- Missing any one of the six files, legacy `units.tsv`, duplicate keys,
  orphaned FKs, cross-sample input selection, noncontiguous ordinals, invalid
  modality/layout, multiple source bundles, or role/modality disagreement fails
  before launch.
- Staging embeds all six validated files, writes the validation receipt, and
  verifies each staged SHA-256 before running DayOA.
- `Z-` and blank identities remain valid for analytical work and make the
  affected analysis unit customer-release ineligible.
- Owner receipts cannot contain `Z-` identifiers, overwrite a conflicting
  supplied identity, refer to an absent row, or survive source-hash drift.
- Identity modules import no AWS or network client and expose no URL/token CLI
  option.
- Removed provider options fail as unknown options; there is no compatibility
  alias or silent registration path.
- S3 export creates a local immutable receipt and never registers with a service
  or deletes data from FSx.
