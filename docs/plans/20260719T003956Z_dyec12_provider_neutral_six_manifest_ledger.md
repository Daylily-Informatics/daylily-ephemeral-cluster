# DYEC 12 Provider-Neutral Six-Manifest Ledger

Created: 2026-07-19T00:39:56Z
Status: A5 IMPLEMENTATION COMPLETE; RELEASE AND LIVE PROOF PENDING
Branch: `codex/bjuice-set1-closeout`
Base: `origin/main` at `93154b47b9dd59f530aea673283b1d1c7931c405`

This is the DYEC execution companion to DayOA's controlling Bjuice Set 1
closeout ledger:

`docs/plans/20260719T005422Z_bjuice_set1_closeout_completion_v3_ledger.md`

## Architecture boundary

DYEC is a standalone provider-neutral cluster and workflow CLI. It receives
explicit local manifests and receipts from a human or any upstream system. It
does not import, name, query, authenticate to, register with, or otherwise
understand Dayhoff, Ursa, Bloom, TapDB, Dewey, or another metadata/identity
service. No service URL, bearer token, SDK, endpoint, service-specific default,
or network discovery belongs in the DayOA 13 / DYEC 12 workflow contract.

Ordinary execution permits blank EUID fields. Customer packaging consumes only
owner-issued identifiers already present in supplied files. Artificial EUIDs
must use the reserved `Z-` prefix and are always ineligible for customer release.

No Dayhoff service or TapDB change is authorized. A discovered upstream gap is
reported to the user and requires two explicit approvals before any upstream
implementation work.

## Gate 0

- The primary DYEC checkout is behind origin and contains two unrelated
  untracked ledgers; this clean worktree preserves it unchanged.
- Latest fetched DYEC release line is `11.0.7`; `12.0.0` and `12.0.1` are
  unclaimed.
- Current catalog defaults to DayOA `12.0.5`; HIOMRS validated version remains
  `12.0.2`.
- Current active source has 17 files containing service-specific names or
  integrations, including Ursa UI URLs/tags/manifests and Dewey post-export
  registration. These are incompatible with the clarified boundary.
- The user requires new work to launch into a new exact-tag result root. Existing
  Set 1 and Set 2 data are read-only and must not be edited or relaunched.

## Required public behavior

- `dyec workflow launch --manifest-dir DIR --git-tag TAG` stages exactly:
  `specimens.tsv`, `samples.tsv`, `libraries.tsv`, `sequencing_inputs.tsv`,
  `analysis_units.tsv`, and `analysis_unit_inputs.tsv`.
- No fallback to legacy `units.tsv` or the overloaded three-manifest contract.
- `dyec identities validate|plan|apply|status|evidence` are local file
  operations only. `apply` means applying a reviewed provider-neutral identity
  receipt to a new manifest directory; it never calls a service.
- Workflow producer surfaces use `analysis_artifacts.tsv` and
  `analysis_artifact_manifest.v3`, not an upstream service name.
- Export ends with immutable S3 receipts. An upstream system may later consume
  those receipts independently; DYEC performs no service registration.
- DayOA `13.0.0` is the exact candidate pin/default for DYEC `12.0.0`.
  `validated_version` remains the last proven tag until HG003 1x succeeds.
- After live proof, DYEC `12.0.1` updates the validated version and self pin.

## Execution rows

| ID | Requirement | State | Evidence / next action |
|---|---|---|---|
| D0 | Preserve dirty primary checkout and establish clean origin/main baseline. | PASS | Worktree and commit recorded above. |
| D1 | Add provider-neutral and `Z-` EUID rules to AGENTS/docs. | PASS | AGENTS/README define standalone operation, blank and `Z-` analytical validity, and customer-release ineligibility. |
| D2 | Add strict six-file `--manifest-dir` staging and reject legacy files. | PASS | Exact names, hashes, FKs, `sr|lr`, exact layout/source bundle, ordered joins, and staged SHA verification. |
| D3 | Add local-only identities validate/plan/apply/status/evidence. | PASS | Hash-bound local receipts; no URL, token, SDK, or network import. |
| D4 | Replace Ursa-named artifact producer options/manifests with generic v3. | PASS | DYEC producer flag is `--produce-analysis-artifact-manifest`; old alias is rejected. DayOA owns v3 contents. |
| D5 | Remove active Ursa/Dewey/Dayhoff registration, URL, tag, and discovery behavior. | PASS | Registration module/CLI removed; create, launch, export, sbatch, and FSx tags are provider-neutral. |
| D6 | Update catalog/source payload/default DayOA pin to 13.0.0. | PENDING | Validated version stays 12.0.2 until live proof. |
| D7 | Add static service-boundary and no-network regression blockers. | PASS | `tests/test_provider_neutral_boundary.py`. |
| D8 | Run focused and full DYEC suites plus source/payload parity checks. | PASS | `20260719T024400Z_dyec12_provider_neutral_six_manifest_test_evidence.md`: 2213 passed, 11 opt-in live skips, new modules 93% combined. |
| D9 | Merge and tag clean DYEC 12.0.0 release. | PENDING | Non-v annotated tag; never move. |
| D10 | Refresh exact target headnode and verify explicit DayOA 13 clone support. | PENDING | No workflow launch until release is proven. |
| D11 | Publish DYEC 12.0.1 after HG003 1x controller rc 0 and final evidence. | PENDING | Update validated version and self pin only after proof. |

The early collection checkpoint reported 2,261 tests. During provider cleanup,
eight new strict bundle/role and boundary cases were added and 45 obsolete
provider-registration/network cases were removed with the deleted integration,
for a net reduction of 37. The final exact full-suite command collected 2,224
tests and terminalized all of them as 2,213 passed plus 11 explicit live-test
skips.

## Terminal contract

This ledger completes only when provider-neutral source/tests/docs are merged,
DYEC 12.0.0 is published, the headnode is refreshed, exact DayOA 13.0.0 HG003
1x acceptance succeeds from a new root, and DYEC 12.0.1 records that proof.
