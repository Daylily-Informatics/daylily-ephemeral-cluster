# Solo kitchen-sink catalog launch ledger

## Gate 0: execution contract

- Cluster: `prod-cand-260809` (`us-west-2`, profile `lsmc`), observed `UPDATE_COMPLETE`.
- Cost center: `prod-cand-260809`, active and authorized for `ubuntu`; observed monthly cap `$777`.
- DayOA ref: explicit annotated tag `13.4.26`.
- Commands: `illumina_hg002_kitchensink_multiqc`, `ont_snv_alignstats_kitchensink`, and `ultima_snv_alignstats_kitchensink`.
- Inputs: their packaged `default_reads_slim` solo fixtures.
- Requested execution: one isolated analysis root per command; exact `dy-r` flags `-j 333 -p -T 0 -n`, no `-k`; remove only `-n` after reviewing that command's dry-run plan.

| ID | Phase | Status | Evidence |
| --- | --- | --- | --- |
| SOLO-001 | Generate immutable local six-manifest inputs from packaged slim-data fixtures via the explicit DayOA offline migrator. | COMPLETE | All three migration outputs validated as one analysis unit and one sequencing input. DayOA `13.4.24` accepts DYEC's blank `ULTIMA_SUBSAMPLE_PCT` only when blank. |
| SOLO-002 | Launch and inspect ILMN, ONT, and Ultima dry-run plans. | ATTEMPTING_BUGFIX | ILMN `solo-illumina-kitchensink-13426-20260811-r3-dry` succeeded at DayOA `13.4.26` with `-j 333 -T 0 -p -n` and no `-k` (zero Slurm submissions). Earlier ONT and Ultima controllers reached DayOA but entered with `aligners=[]` and failed in `produce_metagenomics` before sex-complement evaluation. The catalog repair now supplies explicit `aligners=["ont"]` or `aligners=["ug"]`; fresh dry proof remains required. |
| SOLO-003 | Launch approved live plans after all dry plans succeed. | PENDING | No new live launch is authorized until ILMN, ONT, and Ultima exact dry plans are all terminal success. |
| SOLO-004 | Prepare and dry-run the Complete Genomics/MGI slim-data catalog command at DayOA `13.4.26`. | BLOCKED | The only CG/MGI slim fixture is legacy two-manifest input at `examples/staging/complete_genomics_solo/analysis_samples_manifest.tsv`. No authoritative Complete/MGI topology map exists; the only located six-manifest set is unrelated full 20-subject Bjuice input. The strict migration contract prohibits fabricating topology or identities. |
