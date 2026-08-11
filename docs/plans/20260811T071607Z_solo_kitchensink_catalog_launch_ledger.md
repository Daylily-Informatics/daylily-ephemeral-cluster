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
| SOLO-002 | Launch and inspect three dry-run plans. | ATTEMPTING_BUGFIX | The Illumina dry plan succeeded with 155 planned jobs and no completed work. ONT and Ultima DayOA `13.4.26` dry controllers reached preflight but submitted zero Slurm jobs because DYEC catalog entries advertised the obsolete `sample_manifest` contract and therefore supplied legacy `config/units.tsv`. The repair changes all three solo kitchen-sink entries to the already-supported `six_manifest` contract and requires `--manifest-dir`. |
| SOLO-003 | Launch approved live plans in their existing interactive tmux sessions. | IN_PROGRESS | A fresh isolated Illumina live controller is running from the reviewed identical six-manifest plan. ONT and Ultima await the repaired catalog dry plans. |
