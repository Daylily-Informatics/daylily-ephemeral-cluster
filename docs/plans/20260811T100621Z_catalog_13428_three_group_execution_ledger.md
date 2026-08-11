# DYEC catalog 13.4.28 three-group execution ledger

## Gate 0: baseline

- DYEC checkout: exact annotated release `16.1.80`; `source ./activate; dyec version` reported `16.1.80`.
- DayOA release: annotated `13.4.28` confirmed on origin.
- Cluster contract: `prod-cand-260809`, profile `lsmc`, region `us-west-2`.
- Execution contract: catalog render/dry-run before live launch; DayOA work only through `dy-r` in an interactive `ubuntu` tmux session on the headnode. No raw Snakemake or BCL/basecalling path.
- Existing unrelated untracked work is preserved. This ledger owns only the rows below.

| ID | Group | Requirement | Status | Owner | Evidence / terminal note |
| --- | --- | --- | --- | --- | --- |
| QCDIR-001 | Directory QC | ILMN mounted-run QC, no BCL conversion | SUCCESS | seq_dir_qc | Exact mount `bjuicepreval-20260618-ilmn`; dry `prodcand_ilmn_runqc_13428_r1_dry` rc=0 and live `prodcand_ilmn_runqc_13428_r1_live` rc=0. FSx report: `results/runs/20260618_LH01106_0011_A23MFMCLT3/run_qc/illumina/multiqc_report.html`; required Ursa records `analysis_artifacts.tsv` / `artifact_lineage.tsv` and `dags/rulegraph_20260811T101635Z.png` exist. No S3 export was requested or run (catalog requires separate explicit DYEC export). |
| QCDIR-002 | Directory QC | ONT mounted-run QC, no basecalling | SUCCESS | seq_dir_qc | Exact mount `bjuicepreval-20260615-ont-set4-fc1`; dry `prodcand_ont_runqc_13428_r1_dry` rc=0 and live `prodcand_ont_runqc_13428_r1_live` rc=0. Runtime clone receipt reports DayOA `13.4.28`; FSx reports `results/runs/20260615_ONT_Set4-FC1/run_qc/ont/multiqc_report.html` and `ont_demux_fastq.multiqc.html`, Ursa records `analysis_artifacts.tsv` / `artifact_lineage.tsv`, and `dags/rulegraph_20260811T102024Z.png` exist. No basecalling or S3 export was requested or run (catalog requires separate explicit DYEC export). |
| QCDIR-003 | Directory QC | Ultima mounted-run QC | SUCCESS | seq_dir_qc | Exact mount `ultima-602202-20260512`; dry `prodcand_ultima_runqc_13428_r1_dry` rc=0 and live `prodcand_ultima_runqc_13428_r1_live` rc=0. DayOA clone receipt reports `Reference : 13.4.28`; FSx report `results/runs/602202-20260512_1805/run_qc/ultima/ultima_native.multiqc.html`, Ursa records `analysis_artifacts.tsv` / `artifact_lineage.tsv`, and `dags/rulegraph_20260811T101746Z.png` exist. No S3 export was requested or run (catalog requires separate explicit DYEC export). |
| SOLO-001 | Solo kitchen sinks | ILMN slim-data kitchen sink | RETRY_PENDING | ilmn_solo_rc0 | The 13.4.28 live attempt failed only when Slurm job 1747 lost Spot node `i192nvme-dy-mem192nvme-11`; the backing Spot request closed `instance-terminated-no-capacity`. Fresh six-manifest 13.4.30 render is clean and awaits DYEC 16.1.81 release. |
| SOLO-002 | Solo kitchen sinks | ONT slim-data kitchen sink | RETRY_PENDING | nicu_recoverability_split | A 13.4.28 dry preflight exposed native-ONT evidence-manifest expansion through `legacy_cram_compat_bam`. The required artifact/rulegraph targets remain intact; fresh six-manifest 13.4.30 render is clean and awaits DYEC 16.1.81 release before current-version reproduction. |
| SOLO-003 | Solo kitchen sinks | Ultima slim-data kitchen sink | RETRY_PENDING | ultima_solo_rc0 | Live `solo-ultima-kitchensink-13428-20260811-g2-live` reached 93/134 then lost Spot node `i192nvme-dy-mem192nvme-11`. Slurm jobs 1746, 1748, and 1749 ended simultaneously with `ExitCode=0:15`; ParallelCluster maps the node to EC2 `i-05755d218516f4ee6`, Spot request `sir-738fhydq`, closed as `instance-terminated-no-capacity`. This is not a VEP defect. Fresh 13.4.30 retry awaits DYEC 16.1.81. |
| SOLO-004 | Solo kitchen sinks | Complete slim-data kitchen sink | RETRY_PENDING | root | DRA `dra-052c1ac91907a5f7c` is AVAILABLE and exact staged HG003 CG R1/R2 paths were verified. The six-manifest fixture records `ORDER_TYPE=RESEARCH`, the materialized DRA receipt, and reserved test-only `Z-` specimen/sample/library identities. DayOA 13.4.30 contains the non-customer identity regression; fresh live execution awaits DYEC 16.1.81. |
| HIOMR2-001 | HIOMR2 + Inflection | HG002 5x ILMN + 5x ONT slim kitchen-sink mega and analytical Inflection package | SUCCESS | hiomr2_inflection | Live `dayoa_prodcand_hg002_5x5x_hiomr2_13428_r1_live` terminal rc=0. Verified `analysis_artifacts.tsv`, rulegraph PNG, final MultiQC, evidence manifest, core gVCF/CRAM/CNV/SV artifacts, Jasmine output, and the 39-artifact analytical Inflection package. No S3 export was requested or run. |

## Failure rule

For any nonzero controller result, record concrete root cause, reproduce and test the smallest repair on the headnode through the supported tmux/`dy-r` path, and commit/push only a proven shared repair. A missing authoritative manifest contract is `BLOCKED`, never a prompt to synthesize one.

## Follow-up release gate

- DayOA `13.4.30` is the exact follow-up release. It retains the NICU research aggregate and Truvari outputs while moving only `sentdhiomr2_nicu_fastq_recoverability` behind its standalone research target.
- DYEC `16.1.81` introduces command-catalog version 4, a build-scoped command snapshot pinned to DayOA `13.4.30`, exactly eight production commands, per-command validation-evidence S3 prefixes, and read-only `catalog validation-compare` support.
- The four solo rows must be rerun from fresh 16.1.81/13.4.30 analysis IDs and reach controller rc=0 plus final MultiQC, `analysis_artifacts.tsv`, `artifact_lineage.tsv`, and a rulegraph PNG before their terminal status becomes `SUCCESS`.
