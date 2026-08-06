# Remaining-BJuice SeqOne v2 repackage and export ledger

Created: 2026-08-05T23:24:54Z
Human requestor: John Major
Cluster: `preval-hiomr2` (`lsmc`, `us-west-2`)
Analysis root: `/fsx/analysis_results/preval-hiomr2/remaining-bjuice-1345`
Status: pre-Jasmine SeqOne v2 package, release train, reconciled export, and authorized handoff complete; integrated Jasmine remains a separate open boundary

## Objective

Reuse the completed 15-analysis-unit HIOMR2 results without rerunning variant
callers, produce a strict `seqone_v2` Inflection package under a new delivery
batch/output tree, prove the package and release stamp, and export the new
package to a distinct S3 prefix. Preserve the existing analytical package and
the previously reconciled full-root export.

## Gate 0 baseline

- The preserved FSx analysis root existed and had about 898 GiB free at
  inventory time.
- No active `dy-r`/Snakemake controller and no queued Slurm work were observed.
- DayOA release provenance at entry was annotated tag `13.4.6`, commit
  `79141e8d8861d9ac6b96a11c753dde72471ed921`.
- The earlier analytical export remained complete and separate. This ledger
  authorizes no deletion of the analysis root or prior package.

## Control ledger

| ID | Requirement | Status | Evidence / terminal note |
|---|---|---|---|
| SV2-001 | Inventory ExpansionHunter, singleton SV, and composite SV outputs for all 15 analysis units | SUCCESS | 15/15 ExpansionHunter VCF/JSON/TSV; 15/15 normalized Manta, Dysgu, LongReadSV, Severus, Sniffles2, and TIDDIT; 15/15 SURVIVOR merged VCFs. Caller execution was complete; the defect was package inclusion. |
| SV2-002 | Inventory SeqOne v2 prerequisites, especially integrated-Jasmine route, release identity snapshot, and exact six manifests | FAILED | Integrated root had no `complete.json` or reconciliation; the earlier four-hour job timed out after Jasmine itself completed. Existing SeqOne v2 was hard-gated on absent integrated-Jasmine publication and directly omitted Manta, Dysgu, Severus, SURVIVOR, and OctopuSV. |
| SV2-003 | Stage an explicit new SeqOne v2 delivery batch and config without changing the historical analytical package | SUCCESS | Batch `remaining-bjuice-1345-seqone-v2-prejasmine-20260805`; explicit config-scoped release snapshot; historical package untouched. |
| SV2-004 | Run focused validation and exact `dy-r ... --rerun-triggers mtime -n` in a persistent one-pane Ubuntu tmux | SUCCESS | Final local and headnode focused suites passed 41 tests. Final exact mtime dry run passed RC 0 with two jobs. Its rendered command declared 569 QC sources, all of which were materialized regular files. |
| SV2-005 | Run the identical SeqOne v2 packaging command without `-n` and reach terminal RC 0 | SUCCESS | All 15 units were built. Final collector external job `8147` completed `0:0`; `dy-r` completed two of two steps and returned RC 0 at 2026-08-06T01:54Z. |
| SV2-006 | Verify all 15 unit manifests and batch/global manifests | SUCCESS | 15 unit manifests, 15 unique external sample IDs, 132 artifacts per unit, and 1,980 batch artifacts. Every unit includes ExpansionHunter, tagged SNV, CRAM, raw and experimental Manta, Dysgu, Severus, SURVIVOR, OctopuSV, Sniffles2, TIDDIT, CNVscope, LongReadSV, and Sniffles1/Iris roles. |
| SV2-007 | Preserve the bounded pre-Jasmine eligibility contract | SUCCESS | All unit and batch documents declare `INCOMPLETE_JASMINE_PENDING`, `customer_release_eligible=false`, `submission_allowed=false`, canonical completeness false, and seven exact missing Jasmine roles. HG002 records one explicit SMN12 `NO_CALL`; no copy number was fabricated. |
| SV2-008 | Release the live-proven DayOA code | SUCCESS | Commit `2d18fd1b`; branch `codex/13.4.7-remaining-bjuice-seqone-v2`; pushed annotated tag `13.4.7`. |
| SV2-009 | Default the three requested DYEC catalog commands to SeqOne v2 with no returned results | SUCCESS | `package_inflection_hybrid_data`, `hybrid_ilmn_ont_hiomr2_kitchensink_inflection_analytical`, and `inflection-bjuice-product-v0.2` use `hiomr2_inflection_package_mode=seqone_v2`, require explicit config/batch identity, and set `return_results: false`. Source and payload catalogs are byte-identical; 298 focused catalog tests passed. |
| SV2-010 | Release the DYEC catalog pin and self-pin | SUCCESS | Commit `9a919987`, annotated tag `16.1.35`; self-pin commit `5abd79cc`, annotated tag `16.1.36`; branch and tags pushed. |
| SV2-011 | Export the new SeqOne v2 tree to a distinct reconciled S3 prefix without deleting FSx data | SUCCESS | Dedicated staging root contains 2,847 regular files and 232,120,467,710 bytes; relative paths, inodes, and sizes match the source package exactly. No-delete task `task-086dce274f818cfc1` completed `SUCCEEDED` with 588/588 transferred and zero failed files. Temporary DRA `dra-0e4c1be691d7d219d` detached normally. Export root: `s3://lsmc-ssf-sequencing-data/derived/remaining-bjuice-1345-seqone-v2-prejasmine-20260806T015946Z/preval-hiomr2/remaining-bjuice-1345-seqone-v2-prejasmine-export-20260806T015946Z/`. |
| SV2-012 | Reconcile S3 objects and post the authorized Slack handoff | SUCCESS | Exact package subtree reconciled to 232,120,467,710 bytes. `batch_manifest.json`, `provider_neutral_artifact_manifest.json`, `external_registration_bundle.json`, and `complete.json` were HEAD-verified. Posted only to the existing AG, Mike Kennemer, and John Major group DM at `https://lsmchq.slack.com/archives/C0ATKCY450U/p1785982193746239`; the message names the pre-Jasmine eligibility boundary and the separately running HG002 Truvari work. |
| SV2-013 | Repair or resize the integrated-Jasmine post-processing bottleneck and retry separately | OPEN | Preserve all sources and zero-loss reconciliation. The earlier job allocated 192 cores but its Python post-processing used one core and timed out at four hours; DayOA `13.4.7` includes bounded parallelization improvements, but the incomplete package must not wait on or disguise this separate boundary. |

## Safety and execution contract

- Record all analysis-root visits and acquire the normal write lock before any
  config/output mutation or live `dy-r` command.
- Use only `dy-r` inside one persistent, meaningfully named, one-pane tmux
  running an interactive Ubuntu bash login shell.
- Preserve `DAY_PROJECT=RnD` and `DAYLILY_COST_CENTER=RnD` after activation.
- Do not invoke raw Snakemake, administer Slurm, create a duplicate controller,
  overwrite the analytical delivery, invent identity data, or delete FSx data.
- `customer_release_eligible` may become true only through the exact clean
  annotated release-stamp workflow; it must never be edited directly.
