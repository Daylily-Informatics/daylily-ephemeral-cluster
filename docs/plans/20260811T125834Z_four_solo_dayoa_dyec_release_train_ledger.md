# Four-solo DayOA and DYEC release-train ledger

Controlling request: after the four production solo kitchen-sink workflows
(ILMN, ONT, Ultima, and CG) all reach attributed rc=0 with full report and
artifact outputs, consolidate their proven code changes into one new DayOA
release. Then publish a new immutable DYEC command-catalog build pinned to that
DayOA release, followed by a second DYEC release that updates the DYEC self-pin.

The separately requested SQJX8366 personal CG analysis is held and is not a
release gate.

## Required command set for the new DYEC build

1. Illumina sequencing-directory QC, without BCL conversion.
2. ONT sequencing-directory QC, without basecalling.
3. Ultima sequencing-directory QC.
4. Illumina solo kitchen sink.
5. ONT solo kitchen sink.
6. Ultima solo kitchen sink.
7. Complete Genomics/CG solo kitchen sink.
8. Slim-data HIOMR2 kitchen-sink mega plus Inflection package.
9. A distinct BJuice HIOMR2 kitchen-sink mega plus Inflection package command.

All nine entries must pin the newly released DayOA version and live in a new
immutable DYEC build snapshot; the historic `16.1.81` shape must not change.

## Execution ledger

| ID | Gate | State | Evidence / next action |
|---|---|---|---|
| SOLO-ILMN | Production ILMN solo | SUCCESS | DayOA 13.4.30; dry and live rc=0; final MultiQC, evidence, artifacts/lineage, and rulegraph verified. |
| SOLO-ULTIMA | Production Ultima solo | SUCCESS | DayOA 13.4.30; dry and live rc=0; inferred sex, final MultiQC, evidence, artifacts/lineage, and rulegraph verified. |
| SOLO-ONT | Production ONT solo | SUCCESS_WITH_SCOPE_WAIVER | The repaired native-ONT contamination path and full 63/63 workflow reached rc=0 with final MultiQC and evidence outputs. The user then narrowed VEP to chr1-22/X/Y/M and explicitly waived another live VEP run; the release carries that standard-contig-only contract with excluded-nonstandard audit and focused test proof. |
| SOLO-CG | Production CG solo | RELEASE_WAIVER | Core targets reached rc=0. The missing final MultiQC was localized to the catalog omitting `produce_multiqc_all`; the new build adds that target. A fresh full-output live replay was not completed before the user's explicit ASAP release instruction, so this row is not represented as exact live acceptance evidence. |
| DAYOA-REL | Consolidated DayOA release | SUCCESS | PR #103 merged after green CodeQL checks. Annotated tag `13.4.31` was pushed and peels to merge commit `a6a7cd493eecd51e9e942215414a1822510cffa9`. |
| DYEC-CAT | Immutable catalog release | SUCCESS | PR #93 merged; annotated tag `16.1.82` was pushed and peels to merge commit `1b527cfdf5e3f6cc0b8d65e621eaa19a708bd5dd`. Its snapshot contains exactly nine production commands pinned to DayOA `13.4.31`; historic `16.1.81` remains exact. Focused release suite: 100 passed. |
| DYEC-SELF | DYEC self-pin release | SUCCESS | Both source and packaged DYEC bootstrap pins now select `16.1.82`; the merged self-pin commit is released as final annotated tag `16.1.83`. |

The already successful HIOMR2 mega-plus-Inflection validation root was revisited
read-only with a recorded analysis visit.  It contains nonempty
`analysis_artifacts.tsv` (29,963 bytes), `artifact_lineage.tsv` (207,199 bytes),
final MultiQC (10,538,743 bytes), evidence JSON (358,975 bytes), and rulegraph
PNG (1,780,984 bytes).  It was not exported; the next catalog build must leave
its optional validation-evidence S3 prefix blank rather than reuse older
cross-version evidence.

## Acceptance gates

- Every solo controller has an attributed terminal rc=0.
- Every solo root contains nonempty final MultiQC HTML, DayOA evidence manifest,
  `analysis_artifacts.tsv`, `artifact_lineage.tsv`, and a rulegraph PNG.
- DayOA fixes are proven first in their failed headnode roots under the analysis
  lock and then ported locally; no raw Snakemake invocation is allowed.
- New release tags are non-`v`, annotated, pushed, immutable, and peel to the
  reported commits.
- Source and packaged DYEC catalog payloads remain byte-identical.
- The first new DYEC release preserves historical build snapshots; the second
  changes only the self-pin/release metadata needed to point at the first.
