# Bjuice20 Inflection Deliverables Multiagent Ledger

Generated: `20260720T123613Z`

| Row | Agent | State | Evidence |
|---|---|---|---|
| A1 | Orchestrator | SUCCESS | Created report package and bounded evidence scope. |
| A2 | Source Inventory | SUCCESS | Generated 20-sample package inventory from checked-in manifests. |
| A3 | Package Inventory | PARTIAL | Package presence still uses checked-in package availability receipt; later explicit `--profile lsmc` S3 refresh inspected bounded NA raw/package call artifacts only. |
| A4 | Expected Matrix | SUCCESS | Generated 1,140-row expected-files matrix from 20 samples x 57 package roles. |
| A5 | Missing Data | SUCCESS | Recorded HG002, NA23687, terminal artifacts, and CRAM/CRAI repair boundaries. |
| A6 | Runtime | PARTIAL | Recorded HG003 local subset evidence and all-20 benchmark/controller evidence gap. |
| A7 | Truth/F-score | PARTIAL | Recorded GIAB/Coriell truth sources; refreshed NA expected-positive call support from S3 raw pre-package and package artifacts; GIAB F-scores remain unextracted. |
| A8 | Coriell Research | SUCCESS | Added public expected-positive matrix with source URLs. |
| A9 | Gap Analysis | SUCCESS | Compared source/crosswalk/runbook/package receipts and classified gaps. |
| A10 | QA/Report | SUCCESS | Generated report, ledger, TSV/JSON artifacts, Mermaid diagrams, and reproducible NA call-support refresh script. |

## Acceptance

- Expected universe: 20 samples, 40 libraries, 80 sequencing inputs, 20 analysis units.
- Produced-package receipt: 18 ready packages, 2 missing packages.
- Report explicitly records the original default-credential gap, the later explicit-profile NA raw/package call-support refresh, and does not claim terminal customer delivery.
- NA call-support refresh generated 13 rows: 6 direct called, 1 primary-SMN called with Sentieon discordance, 1 raw Turner QC support row, 1 supplemental NA23687 raw SMN12 support row, 2 qualitative FXN support rows, 1 partial chr9 support row, and 1 UPD8 out-of-scope row.
