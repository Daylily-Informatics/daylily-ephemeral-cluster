# Inflection DayOA to DYEC release-train ledger

Created: 2026-07-17T09:30:53Z

## Objective

After the exact Batch 1 full-coverage Inflection package and Ursa registry
contract pass live validation, repeat the target against the authoritative Batch 2
inputs, validate and export the complete Batch 2 delivery to the explicitly resolved
shared S3 destination, and send the requested v1 results notice to J Major, Michael
Kennemer, and Andrew Geller. Then reconcile the proven v1 behavior onto the most
advanced published DayOA line, publish the next annotated DayOA release, advance
DYEC's active DayOA pins and publish the next annotated DYEC release, then advance
the DYEC self-pin and publish its follow-up release. Preserve the branches currently
checked out.

## Gate 0 inventory and version reconciliation

- DayOA checkout:
  `/Users/jmajor/projects/lsmc/daylily-omics-analysis-inflection-delivery`, branch
  `codex/inflection-hiomrs-delivery-v1`, feature base `18296a2e4cba487f80957e8a159224567e971300`.
- The independently published annotated DayOA tag `11.0.25` resolves to
  `d0b2aa2fe811accfa84106bd67c9bef1b643fb13`.
- A release-readiness refresh at `2026-07-17T11:11Z` found that DayOA 12 was
  subsequently released and merged: annotated tag `12.0.0` resolves to
  `70b770d5393bcc8ff570955df3795306c664f499`, while `origin/main` is
  `eefaa1c29c372c4b1efa0170275548f68b82f95e`. It already includes a separate
  three-manifest Inflection delivery implementation. The proved v1 feature must
  be reconciled onto this line without reverting DayOA 12 or reintroducing its
  prohibited runtime legacy-manifest fallback. The stale tentative `11.0.26`
  version is withdrawn; the intended next DayOA release is `12.0.1`, subject to
  a final free-version check.
- DYEC checkout: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch
  `main`, local tip `2e417e1144da5822ca6c8883a22e86089a5ef59e` at annotated
  tag `10.3.30`, now three commits behind `origin/main`.
- Annotated DYEC tag `11.0.0` and `origin/main` resolve to
  `650f073c47bcc925c5d7de20858d5d91b42d97e9`; that release pins DayOA 12 and
  carries the strict three-manifest orchestration. The intended pin and self-pin
  follow-up releases are therefore `11.0.1` and `11.0.2`, subject to final
  free-version checks.
- Tags are non-`v`, annotated, created only after a clean commit, and never
  moved or overwritten. No branch switch, force-push, PR, or merge to another
  branch is authorized.

## Ordered contract

1. Complete the Batch 1 live ledger
   `daylily-omics-analysis-inflection-delivery/docs/plans/20260717T072058Z_inflection_batch1_fullcov_live_ledger.md`.
2. Resolve the authoritative Batch 2 analysis root and configured shared S3
   destination without inference; run the same target through `dy-r`, validate it,
   export it with receipts, and send the requested v1 results notice.
3. Reconcile the proved v1 feature tree with current `origin/main` on the current
   DayOA branch, retaining the released DayOA 12 three-manifest and Inflection
   contracts, run the full suite, push the branch, annotate `12.0.1`, and push the tag.
4. Fast-forward DYEC `main` to its current upstream lineage; add the distinct
   `inflection-hiomrs-delivery-v1` dev command for the additive DayOA target with
   exact v1 evidence-manifest registration policy; retain the existing native
   DayOA 12 `inflection-bjuice-product-v0.2` command; update source, packaged,
   and tested DayOA pins to `12.0.1`; validate the complete current tree, commit
   and push `main`, annotate `11.0.1`, and
   push the tag.
5. Update both DYEC self-pin configuration copies and their contract test to
   the just-published intermediate release `11.0.1`; validate, commit and push
   `main`, annotate the follow-up release `11.0.2`, and push the tag.
6. Verify local and remote branch tips, annotated tag objects and peeled
   commits, exact pin parity, and clean worktrees.

## DayOA 12 reconciliation contract

- Preserve the released DayOA 12 native `produce_inflection_delivery_set`
  implementation and its strict `specimens.tsv` / `samples.tsv` / `libraries.tsv`
  runtime. The v1 prototype-compatible target is additive and remains
  `produce_hiomrs_inflection_delivery`; it must not replace or weaken the native
  customer-release contract.
- Namespace the prototype-compatible Python implementation separately during
  the merge so the released DayOA 12 `inflection_delivery.py` keeps sole
  ownership of the native package/set schemas.
- The v1 target may consume legacy `samples.tsv` and `units.tsv` only from the
  mandatory, explicit `inflection_delivery_source_analysis_root`. Those files
  are pinned inputs to this migration/package rule, not a DayOA 12 runtime
  fallback. The exact source `analysis_unit_uid` remains the v1 identity; no
  specimen, sample, library, delivery, or TapDB EUID is inferred.
- Preserve the v1 selected-VCF transforms, abnormal-only SMN fold, metrics,
  transform map, validation, evidence aggregate, and experimental exclusions.
  Reconcile its terminal receipt into the DayOA 12 Ursa v2 emitter as
  importable v1 evidence with `customer_release=false`; blank unknown EUIDs must
  remain blank. Native DayOA 12 packages remain the separate surface for
  customer-release eligibility with persisted three-level EUID lineage.
- Every nonlocal v1 rule uses a single `shell:` block, declares `log:`,
  `benchmark:`, and pinned `conda:`, selects only NVMe partitions, fails unless
  `/scratch` is the local mount, creates write-heavy intermediates and local
  logs there, and atomically publishes only validated finals to FSx.

## Control ledger

| ID | Repo | Requirement | Status | Gate | Evidence | Terminal note |
|---|---|---|---|---|---|---|
| GATE0-001 | both | Freeze branches, dirty scope, upstream releases, free versions, pin surfaces, and live-proof dependency. | SUCCESS | Gate 0 | Initial DayOA `11.0.25` and DYEC `10.3.29`/`10.3.30` inventory was superseded by the `2026-07-17T11:11Z` refresh: current released lines are DayOA `12.0.0` and DYEC `11.0.0`. Intended next versions are `12.0.1`, `11.0.1`, and `11.0.2`, pending the final pre-publication free-version check. | Existing pushed tags are preserved; no release is based on stale version assumptions. |
| LIVE-001 | DayOA | Complete Batch 1 package, evidence aggregate, Ursa registry reconciliation, and lock release. | FAIL | Gate 1 | Exact tested remote commit/tag `3e81301554b0960ec72aa41a928c261a24f446ee` / `inflection-batch1-fullcov-20260717-scratchnvme1`. Full mtime dry-run rc `0` planned exactly 12 packaging jobs and no upstream work. Live controller rc `1`; jobs `3272`-`3281` all failed `1:0` in `00:01:37`-`00:03:14`; queue empty; lock auto-released; outputs `0` receipts, `0` packages, `0` evidence. HG002 has prohibited `sentieon_dnascope_svsolver_short_read_fallback`; the other nine source SNV VCFs have FORMAT `GT,AD,DP,LAD,SAD,SB` but no INFO SOR. After explicit approval to use an HG002-only true LR-SV alternate, read-only exhaustive inspection found no long-read SV VCF/index in that unit; the expected `sentdhiomr` pair is absent and only short-read HIOMRS/TIDDIT pairs exist. | Terminal live failure blocks every release action. No alternate code, short-read/truth substitution, DayOA or DYEC release commit, push, or tag was produced. |
| BATCH2-001 | DayOA/DYEC | Resolve and run authoritative Batch 2, validate outputs, and export to the exact configured shared S3 prefix with receipts. | IN_PROGRESS | Gate 1 | Authoritative root is `/fsx/analysis_results/ifx-p2-1000-120-0715/second-half-preval`; exact 10-unit manifest set recorded. The four missing EH collections and their focused report are now repaired as recorded in `BATCH2-EH-001`. A full `produce_hiomrs produce_multiqc_all` mtime dry-run returned rc `0` but planned 249 jobs, including 10 short-read alignments, 10 markdup jobs, and 70 SegDup jobs, so it was not launched as a missing-only recovery. Configured shared export root is `s3://lsmc-ssf-sequencing-data/derived/`; exact destinations are `s3://lsmc-ssf-sequencing-data/derived/ifx-p2-1000-120-0715/bjuice-preval-hg001-007-smn3-hiomrs-11010-20260716T014729Z/` and `s3://lsmc-ssf-sequencing-data/derived/ifx-p2-1000-120-0715/second-half-preval/`. Prior read-only S3 checks returned `KeyCount=0` for both. | EH recovery is complete. Broader Set 2 final-report, package, validation, and S3-export work remains active and must not use the 249-job full-target DAG without a separately bounded plan. |
| BATCH2-EH-001 | DayOA | Recover the four failed Set 2 HIOMRS ExpansionHunter collections with the biological-sample-id fix and publish the focused aggregate/report without rerunning completed analysis. | SUCCESS | Gate 1 | Initial live submission failed closed before Slurm on a 40.10-hour stale cost-center snapshot. Supported `dyec cost-centers refresh-usage` dry-run and live refresh both read 568 authoritative CUR rows and wrote `$396.95389998100000000002787` through `2026-07-16T22:00:00Z` without changing the `$800` cap. The exact four-output dry-run planned only four 48-thread `hiomrs_expansionhunter_collect` jobs and showed `--biological-sample-id` values `NA05067`, `NA14732`, `NA14733`, and `NA15849`. Live jobs `3282`-`3285` all completed `0:0` on `i128nvme` in `00:01:27`-`00:02:01`; controller rc `0`. All six EH artifact types are now `10/10`. A second bounded dry-run planned only `expansionhunter_gather` and `expansionhunter_multiqc`; its live controller returned rc `0`, producing a 951-line/10-SampleID aggregate and 21,162,112-byte HTML report. Final queue and controller checks are empty and the analysis root is unlocked. | Published branch `codex/feat-multiqc-integrity-release-11.0.24`, commit `d0b2aa2fe811accfa84106bd67c9bef1b643fb13`, annotated tag `11.0.25`; the three installed headnode fix files are byte-identical to that release despite unavailable headnode GitHub credentials. |
| NOTICE-001 | Slack | Send the verified v1 results to J Major, Michael Kennemer, and Andrew Geller. | PENDING | Gate 1 | Exact Slack identities resolved without sending: JEM/J Major `U08TN63K73M` (`johnm@lsmc.com`), Michael Kennemer `U0AQXA08V6Z` (`michael.kennemer@lsmc.com`), Andrew Geller `U0ADESEKP1U` (`andrew.geller@lsmc.com`). | Send three direct messages only after Batch 2 validation and export are terminal; explicitly label the results as v1. |
| DAYOA-001 | DayOA | Reconcile and validate the complete v1 feature on the released DayOA 12 line without weakening the strict three-manifest contract. | SUCCESS | Gate 2 | Feature commit `0d8ea13a` reconciled locally with `origin/main` at `eefaa1c29c372c4b1efa0170275548f68b82f95e`. Native v2 and strict three-manifest behavior remain separate; v1 is namespaced, uses only explicit pinned legacy manifests, and registers as non-customer-release evidence. Mike's optional-SOR behavior is explicit; no SB-to-SOR derivation exists. The later explicit backup policy validates the producer's failed-LongReadSV/successful-SVSolver provenance, packages the selected VCF unchanged, records it in metrics/manifest, and counts it only as short-read CNV support. Focused Inflection/Ursa/evidence suite: `82` passed. Complete suite: `948` passed in `36.41s`; Ruff and diff checks pass. | Local reconciliation is green but intentionally uncommitted and unpublished because Gate 1/live proof failed. |
| DAYOA-002 | DayOA | Push current branch and annotated tag `12.0.1`; verify remote objects. | BLOCKED | Gate 2 | No push or tag performed. | Blocked by `LIVE-001=FAIL`. |
| DYEC-PIN-001 | DYEC | Fast-forward current `main`; add and test distinct `inflection-hiomrs-delivery-v1` source/payload catalog entries with the exact target, config, explicit source-root parameter, v1 evidence classifications, and no `-k`; retain native v0.2; update all DayOA pins to `12.0.1`; validate. | BLOCKED | Gate 3 | Current upstream already contains native `inflection-bjuice-product-v0.2`; DYEC was not mutated. | Blocked because DayOA `12.0.1` was not released. |
| DYEC-PIN-002 | DYEC | Commit/push `main`, annotate/push `11.0.1`, and verify. | BLOCKED | Gate 3 | No commit, push, or tag performed. | Blocked by `LIVE-001=FAIL`. |
| DYEC-SELF-001 | DYEC | Update source/payload/test self-pin to `11.0.1` and validate. | BLOCKED | Gate 4 | DYEC self-pin unchanged. | Blocked because `11.0.1` was not released. |
| DYEC-SELF-002 | DYEC | Commit/push `main`, annotate/push `11.0.2`, and verify. | BLOCKED | Gate 4 | No commit, push, or tag performed. | Blocked by predecessor release gates. |
| FINAL-001 | both | Verify clean trees, remote branch tips, tag types/peeled commits, exact pins, and terminal ledgers. | BLOCKED | Gate 5 | Release train intentionally stopped before all remote mutations. | Objective incomplete; the local optional-SOR and provenance-declared HG002 backup policies still require live Batch 1 proof, while Set 2 remains 6/10 ExpansionHunter complete behind a stale foreign lock. |

## Completion contract

Completion requires every row to be terminal, the live controller and package
validators to exit zero, the Ursa registry to contain the exact nonexperimental
contract inventory for all ten analysis units, both repositories to be clean,
and all three new annotated tags to resolve remotely to the reported commits.
