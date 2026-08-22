# Bjuice Prevalence Remaining-14 Dry-Run Ledger

Created: `2026-08-17T12:56:17Z`

## Objective and boundary

Prepare one rerunnable DayOA analysis directory for the 14 Bjuice prevalence
samples not present in the six-AU controller, then prove Bjuice v0.9-equivalent
HIOMR2 analytical targets with `hg38`, numeric chromosomes `1-25`, full ILMN,
ONT elapsed hours `[0,24)`, `-j 444 -T 1 -p -k -n`.

This objective ends at dry-run success. No live run of this 14-AU directory was
requested or launched. If a live run is later authorized, it must reuse this
exact analysis root, checkout, and in-clone config, changing only removal of
`-n` from the verified command.

## Frozen analysis identity

- Cluster: `pcand-18022` (`lsmc`, `us-west-2`).
- Analysis root: `/fsx/analysis_results/pcand-18022/pcand18022-bjuice-preval14-15014-dry-20260817t121402z`.
- DayOA checkout: `<analysis-root>/daylily-omics-analysis`.
- DayOA ref: `15.0.14`; pinned observed commit:
  `3c33a7fc30fbd9c364f009ad68e8f45987edde28`.
- Analysis config: `config/bjuice_preval14_hiomr2.yaml` inside that checkout.
- Config SHA-256:
  `72894e3da1d263489e7405e782a2eef5366604f1217cc510ccb8204392877f65`.
- The temporary former external config path is absent. Analysis-specific
  controller config is not stored outside the cloned DayOA directory.
- Topology: 14 specimens, 14 samples, 28 libraries, 56 sequencing inputs,
  14 analysis units, and 56 AU-input joins. `ANALYSIS_UNIT_EUID` is blank;
  unique local AU UIDs are used without inventing owner-issued EUIDs.

## Cohort and truth routing

| Samples | GIAB SNV/RTG concordance | Truvari SV truth/query |
|---|---|---|
| HG001, HG005, HG006, HG007 | Yes. Each sample uses `/fsx/references/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/<sample>/`. | No. None has an explicitly configured sample-specific SV truth set. |
| NA05067, NA10798, NA13189, NA14732, NA14733, NA15603, NA15848, NA15849, NA20027, NA20230 | No truth set configured. | No. None has an explicitly configured sample-specific SV truth set. |

The unmodified initial dry plan exposed the defect: the global HG002 SV truth
was incorrectly projected onto this cohort, yielding 56
`sentdhiomr2_slim_truvari_query` jobs. Only after that direct `dy-r` evidence
was a named-root, dry-run-only pinned-source test override applied. The focused
remote test set passed `59 passed in 0.47s`; `git diff --check` passed. The
controller recorded identical commit and dirty-source evidence before dispatch
and after return. This override is not authorization for a live run, export,
or production release.

## Corrected dry-run evidence

- Controller session:
  `pcand18022-bjuice-preval14-truvari-gate-dry-20260817t1249z`.
- Terminal state: `SUCCEEDED`.
- Attributable workflow exit code: `0` from the controller `status.json`.
- Planned jobs: `3,034`.
- Submitted Slurm jobs: `0`; Slurm state set was empty, as required for `-n`.
- All 14 ONT inputs retained `144/438` FASTQs for half-open interval `[0,24)`.
- Concordance selection in the plan was exactly HG001, HG005, HG006, HG007.
- GIAB plan retained:
  `prep_for_concordance_check=4`,
  `prep_for_hiomr2_cli_gvcf_concordance_check=4`,
  `rtg_vcfeval_roi=38`,
  `rtg_vcfeval_hiomr2_cli_gvcf_roi=38`,
  `parse_vcfeval_summary_roi=38`,
  `parse_vcfeval_hiomr2_cli_gvcf_summary_roi=38`, and
  `produce_snv_concordances=1`.
- `sentdhiomr2_slim_truvari_query` is absent from both corrected dry-plan
  sections: executable Truvari query count is zero.
- `sentdhiomr2_slim_truvari_aggregate=14` remains only to materialize explicit
  per-AU `NOT_APPLICABLE` receipts; it does not invoke Truvari.
- The final controller output states: `This was a dry-run (flag -n)`.
- Local DYEC still reports `Daylily Ephemeral Cluster 18.0.25`; no version was
  changed during this work.

## Ledger

| ID | Requirement | State | Evidence |
|---|---|---|---|
| MAN-001 | Exact remaining 14 AUs, full ILMN, ONT `[0,24)` | COMPLETE | Topology and controller input-filter output above. |
| CFG-001 | All analysis-specific config lives inside the clone | COMPLETE | In-clone path and hash above; former external path absent. |
| GIAB-001 | Run GIAB/RTG only for HG001/5/6/7 | COMPLETE | Exact four-sample concordance selection and retained rule counts above. |
| TRUVARI-001 | Run no Truvari query without explicit per-sample SV truth | COMPLETE | Corrected plan has zero query-rule occurrences; 14 explicit not-applicable receipts. |
| DRY-001 | Exact `-j 444 -T 1 -p -k -n` dry run | COMPLETE | Controller terminal `SUCCEEDED`, attributable `rc=0`, 3,034-job plan. |
| SLURM-001 | Dry run submits no Slurm jobs | COMPLETE | DYEC status `submitted_count=0`; empty Slurm states. |

All dry-run rows terminal: yes.
Dry-run objective complete: yes.
Live 14-AU execution launched: no.
