# DYEC 16.1.73 included dirty-work ledger

Updated: 2026-08-11T05:03:42Z

## Objective

Include the coherent newly dirty DYEC planning/source artifacts requested after
the immutable `16.1.72` tag was pushed, without moving that tag or adding
generated caches, backups, recordings, temporary files, or export receipts.

## Gate 0 baseline

- Branch: `codex/seqqc-16.1.66-retry`
- Previous immutable release: annotated tag `16.1.72` at
  `e101de5e2904a84e8f8e8fbde9215939fa7a8f6e`
- New patch release: `16.1.73`
- Included dirty set is limited to the four source/ledger files listed below.

## Execution ledger

| ID | State | Evidence |
| --- | --- | --- |
| DIRTY-001 | SUCCESS | Include the VEP chr1-25 array update that requires the pre-pulled local VEP 114.2 SIF. |
| DIRTY-002 | SUCCESS | Include the VEP chr7 prewarm job and chr1-25 merge/count/hash validator. |
| DIRTY-003 | SUCCESS | Include the DayOA 13.4.15 jemalloc chr19-20 execution ledger. |
| DIRTY-004 | SUCCESS | Both shell files pass `bash -n`; the merge module compiles; credential-pattern scan is empty. |
| DIRTY-005 | SUCCESS | DYEC self-pin and packaged mirror advance to `16.1.73`; focused pin/mirror tests pass. |
| DIRTY-006 | SUCCESS | Commit `a1e3932941e3068e2da0fb66e74d7008d9fc12ae` pushed to `origin/codex/seqqc-16.1.66-retry`. |
| DIRTY-007 | SUCCESS | Annotated tag `16.1.73` pushed and verified to dereference to `a1e3932941e3068e2da0fb66e74d7008d9fc12ae`. |

## Included files

- `docs/plans/20260810T164600Z_johnmajor_vep_chr1_25_array.sbatch`
- `docs/plans/20260810T164600Z_johnmajor_vep_chr7_prewarm.sbatch`
- `docs/plans/20260810T164600Z_johnmajor_vep_chr1_25_merge.py`
- `docs/plans/20260810T191606Z_jemalloc_test_dayoa_13415_chr19_20_ledger.md`

## Excluded generated material

Untracked nested repositories, backups, recordings, `reports/fsx_exports/`,
and `tmp/` are not package source and are not included in the release.
