# DayOA `dy-r` safeguard release and live-proof ledger

- **Created (UTC):** 2026-07-28T00:21:59Z
- **Authority:** operator authorization in this task for feature-branch
  releases, annotated tags, an `lsmc` non-production proof, and a follow-up
  staggered-controller check.
- **Release sequence:** DayOA `13.0.61` first; DYEC DayOA-pin `15.0.13`;
  DYEC self-pin `15.0.14`.
- **Safety boundary:** no merge to `main`, no production launch, no Slurm
  intervention, and no deletion except exact Conda environment paths proven
  to have been created by the authorized test.

## Gate 0

| Checkout | Starting SHA | Starting tag context | Status |
| --- | --- | --- | --- |
| DayOA `daylily-omics-analysis-main` | `c148f3c7b9fdea0cb813b8c08b5d9bfeb623eaab` | `13.0.59`; remote already had unrelated `13.0.60` | clean baseline recorded in the DayOA safeguard ledger |
| DYEC `daylily-ephemeral-cluster` | `61455f444ffdd41b15866550241fb3ced7789c24` | `15.0.12-2-g61455f44` | clean detached baseline; feature branch created for this release |

Tag availability was checked before release: `13.0.61`, `15.0.13`, and
`15.0.14` did not exist on `origin`.

## Control rows

| ID | Gate | Requirement | Status | Evidence / next condition |
| --- | --- | --- | --- | --- |
| REL-01 | R1 | Publish DayOA safeguard feature branch and annotated `13.0.61`. | SUCCESS | `13.0.61` is an annotated tag to `97b764596bbf0f6d25380bc9fb79953ca64d7874`; branch `codex/dyr-concurrent-safeguard` is pushed. |
| REL-02 | R2 | Pin both active DayOA catalog copies and exact test contracts to `13.0.61`; publish annotated `15.0.13`. | SUCCESS | Annotated `15.0.13` is remotely verified at `865b28d2169376ddd672242f926f5b9259bcfde9`; historical validation facts were preserved. |
| REL-03 | R3 | Advance only DYEC bootstrap/self-pin copies to `15.0.13`; publish annotated `15.0.14`. | IN_PROGRESS | REL-02 is remotely verified; source/payload global configuration and exact fork-contract assertion are being advanced in a separate commit. |
| LIVE-01 | R4 | On an `lsmc` non-production cluster, create `test-dyoa-clash-1` with exact tag `13.0.61` and complete the smallest catalog-owned 1x Illumina slim-data proof. | OPEN | Requires release train completion and exact compatible catalog/input selection. |
| CLEANUP-01 | R5 | Baseline and remove only Conda environments proven to be created by LIVE-01. | OPEN | No shared or pre-existing cache path may be removed. |
| RACE-01 | R6 | Create the requested fresh clone(s), launch two controllers seconds apart, and preserve evidence that the later controller emits safeguard wait output. | OPEN | Requires CLEANUP-01 success and explicit unique test-root identities. |
| CLOSE-01 | R7 | Record terminal row count, remote tag verification, test evidence, changed files, and residual risks. | OPEN | Pending all prior rows. |

## Input-contract finding

The catalog's exact HG003 1x profile is
`hg003_hiomrs_1x_raw_fastq`: paired Illumina HG003 1x FASTQs plus an ONT FASTQ.
It currently backs only hybrid ILMN+ONT commands. The small
`illumina_snv_alignstats` route is ILMN-only but is cataloged as
`default_reads_slim`, not the exact 1x six-manifest profile. Before LIVE-01,
the operator intent must be satisfied by an existing compatible catalog
contract; no new manifest or input-path inference will be introduced just to
make the launch fit.
