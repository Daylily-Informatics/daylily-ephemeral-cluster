# DRAGEN HG002 Manual EC2 Run Ledger

Created: 2026-07-08T01:29:47Z
Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
Branch: `jemdev10`
Instance: `i-0d75af02251c65b84` (`jem-dragen-x3`, `f2.6xlarge`, `us-west-2`)
Remote user: `ec2-user`
Guide: `docs/other/running_dragen_manually.md`

## Objective

Run `HG002` manually on the standalone DRAGEN EC2 instance, calculate concordance/F-score against the available HG2/HG002 reference VCF/BED, export run and benchmark outputs to S3, update the manual DRAGEN guide with concrete commands/results, and stop the instance after export verification and explicit `/ephemeral` data-loss confirmation.

## Gate 0 Baseline

| Item | Evidence |
|---|---|
| Repo branch | `jemdev10` |
| Existing repo state | Dirty worktree before this task, with unrelated changes in command catalog/code/tests and many `docs/plans/20260707T144453Z_*` artifacts; this task owns only `docs/other/running_dragen_manually.md` and this ledger unless explicitly expanded. |
| EC2 instance state | `i-0d75af02251c65b84`, `jem-dragen-x3`, `f2.6xlarge`, public IP `54.202.83.81`, state `running`, AMI `ami-044bef021cb86a54c`. |
| Runtime disk | `/ephemeral` is 876G total, 105G used, 771G available at baseline. |
| HG002 staged input | `/home/ec2-user/ephem_stg/HG002.novaseq.pcr-free.35x.R1.fastq.gz` (`29911262422` bytes) and `/home/ec2-user/ephem_stg/HG002.novaseq.pcr-free.35x.R2.fastq.gz` (`31043207981` bytes). |
| Reference staging | `/home/ec2-user/ephem_stg/hg38-alt_masked.graph.cnv.hla.methyl_cg.rna_v6` and `/ephemeral/hg38-alt_masked.graph.cnv.hla.methyl_cg.rna_v6` exist. |
| Concordance truth/evidence | `/home/ec2-user/ephem_stg/concordance_refs/giab_hg2_clinvar_genes/HG002.{vcf.gz,vcf.gz.tbi,bed}` and `HG2.{vcf.gz,vcf.gz.tbi,bed}` copied from `s3://lsmc-dayoa-references-usw2/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG2/clinvar_genes/`. |
| Available tools | DRAGEN exists at `/opt/edico/bin/dragen`; Docker exists at `/usr/bin/docker`; native `hap.py`, `rtg`, `vcfeval`, `bcftools`, `tabix`, and `bgzip` are absent on PATH. |
| EC2 history evidence | `~/.bash_history` contains the original NA19235 restore command sequence using `rsync` from `/home/ec2-user/ephem_stg` to `/ephemeral`; no credential contents were captured in this ledger. |
| S3 output target | `s3://lsmc-dayoa-analysis-results-usw2/dragen/hg002_pangenome_20260708/ec2/` |

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| GATE0 | Baseline | Record repo, instance, inputs, references, tools, output target, and scope. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | Gate 0 table above. |  | Baseline recorded before runtime changes. |
| DOC-HISTORY | Documentation | Add original `/ephemeral` staging commands from `ec2-user` history to the guide without exposing secrets. | SUCCESS | historical_docs_only | Gate 5 | orchestrator | `docs/other/running_dragen_manually.md` HG002 section now includes the safe `ec2-user` history restore commands and explicitly omits the credential-printing history command. |  | Original restore pattern and HG002 source URLs recorded. |
| HG002-STAGE | EC2 runtime | Stage HG002 FASTQs/reference/population VCF/license into `/ephemeral` with explicit paths. | SUCCESS | legitimate_safety_handling | Gate 1 | orchestrator | Restore tmux `dragen_hg002_restore_20260708`; log `/home/ec2-user/dragen_hg002_ec2_logs/restore_20260708T013140Z.log`; finished `20260708T013932Z`. |  | `/ephemeral`: 162G used, 714G free; HG002 FASTQs, DRAGEN reference, population VCF, license metadata, and GIAB HG002/HG2 truth files staged. |
| HG002-DRAGEN | EC2 runtime | Run full DRAGEN pangenome command for HG002 in persistent tmux. | SUCCESS | feature_implementation | Gate 1 | orchestrator | tmux `dragen_hg002_run_20260708`; script `/home/ec2-user/run_hg002_dragen_20260708.sh`; run started `20260708T014046Z`; exit file `/home/ec2-user/dragen_hg002_ec2_logs/run_20260708T014046Z.exit`. |  | `DRAGEN_EXIT_CODE=0`; finished `20260708T024811Z`; total runtime `01:07:01.968`; hard-filtered VCF/index produced. |
| HG002-CONCORD | Benchmark | Calculate HG002 concordance/F-score using explicit HG2/HG002 VCF/BED and a declared benchmark tool. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `/home/ec2-user/run_hg002_happy_20260708.sh`; output `/ephemeral/output/HG002_pangenome_MA_VC_all_callers/concordance/happy_giab_hg2_clinvar_genes/HG002.hard-filtered.summary.csv`. |  | `HAPPY_EXIT_CODE=0`; finished `20260708T030942Z`; SNP PASS F1 `0.941257`, SNP ALL F1 `0.940540`; INDEL PASS F1 `0.771719`, INDEL ALL F1 `0.771022`. |
| HG002-EXPORT | Export | Export DRAGEN outputs, logs, and concordance results to the explicit S3 prefix and verify object counts/bytes. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `/home/ec2-user/export_hg002_results_20260708.sh`; export target `s3://lsmc-dayoa-analysis-results-usw2/dragen/hg002_pangenome_20260708/ec2/`; local S3 verification matched export summary. |  | Export finished `20260708T031600Z`; `127` objects; `65,172,195,136` bytes. |
| DOC-RESULTS | Documentation | Update `running_dragen_manually.md` with HG002 staging/run/benchmark/export commands and results. | SUCCESS | historical_docs_only | Gate 5 | orchestrator | `docs/other/running_dragen_manually.md` includes HG002 staging provenance, restore/run/benchmark/export commands, DRAGEN counts, F-scores, S3 result location, object count, and byte total. |  | Documentation updated before commit. |
| EC2-STOP | AWS state | Stop the DRAGEN EC2 instance after export verification and explicit `/ephemeral` loss-boundary confirmation. | BLOCKED | legitimate_safety_handling | Gate 5 | orchestrator | User requested stop, but workspace safety requires spelling out `/ephemeral` loss boundary and receiving explicit confirmation before stopping a DRAGEN host with staged data. | Stop approval pending after export verification. | Awaiting explicit confirmation at the end. |

## Progress Log

- 2026-07-08T01:29:47Z: Ledger created after Gate 0 inventory. No `/ephemeral` mutation for HG002 yet.
- 2026-07-08T01:31:40Z: Launched restore tmux `dragen_hg002_restore_20260708` with script `/home/ec2-user/restore_hg002_runtime_20260708.sh`.
- 2026-07-08T01:39:32Z: HG002 restore completed. Runtime inventory: `/ephemeral` 876G total, 162G used, 714G available; `/ephemeral/hg38-alt_masked.graph.cnv.hla.methyl_cg.rna_v6` 38G; `/ephemeral/smn12_samples/HG002` 57G; `/ephemeral/hg38_1000G_phase1.snps.high_confidence.vcf.gz` 1.8G; `/ephemeral/concordance_refs/giab_hg2_clinvar_genes` 311M.
- 2026-07-08T01:40:46Z: Launched HG002 DRAGEN run in tmux `dragen_hg002_run_20260708` with script `/home/ec2-user/run_hg002_dragen_20260708.sh`. Initial log reported `dragen Version 13.031.818.4.5.4`, host software `4.5.4`, and license server connected.
- 2026-07-08T01:43:00Z: Started staging no-alt GRCh38 FASTA and `.fai` for `hap.py` from `s3://lsmc-dayoa-references-usw2/genomic_data/organism_references/H_sapiens/hg38/fasta_fai_minalt/`.
- 2026-07-08T01:41:50Z: `hap.py` reference staging finished. Runtime files: `/ephemeral/concordance_refs/reference/GRCh38_no_alt_analysis_set.fasta` (`3144230986` bytes) and `.fai` (`7804` bytes). First `.fai` contigs are `chr1`, `chr2`, `chr3`, `chr4`, `chr5`, matching the HG002 truth VCF/BED.
- 2026-07-08T01:46:35Z: DRAGEN still running. Log showed FASTQs opened, insert statistics detected, B-allele loci read, and sort intermediates spilling to disk. `/ephemeral` was 276G used, 601G available.
- 2026-07-08T01:50:00Z: Updated `docs/other/running_dragen_manually.md` with HG002 source URLs, safe `ec2-user` restore-history commands, 2026-07-08 restore command/results, live DRAGEN command/status, prepared `hap.py` command, and planned export prefix.
- 2026-07-08T01:49:58Z: DRAGEN still running. `/ephemeral` was 400G used, 476G available. Latest run log still showed sort intermediate spilling and no exit file yet.
- 2026-07-08T01:52:58Z: DRAGEN still running. Latest log reached `Variant Caller Execution` and `Streaming reads using generated callable regions...`; `/ephemeral` was 366G used, 510G available.
- 2026-07-08T01:53:00Z: Staged strict `hap.py` benchmark script `/home/ec2-user/run_hg002_happy_20260708.sh`; it is not launched until the expected DRAGEN query VCF and index exist.
- 2026-07-08T01:55:05Z: DRAGEN still running but final artifacts were appearing, including `HG002.hard-filtered.vcf.gz`, `HG002.hard-filtered.gvcf.gz`, `HG002.bam`, HLA outputs, targeted VCF, repeat VCF, and personalization outputs. File sizes were not yet final.
- 2026-07-08T02:01:00Z: Staged strict export script `/home/ec2-user/export_hg002_results_20260708.sh`; it requires credential environment variables, run/log directories, and helper scripts before syncing to S3.
- 2026-07-08T02:05:27Z: DRAGEN still running. Output BAM/gVCF/VCF were still growing; `/ephemeral` was 349G used, 527G available.
- 2026-07-08T02:30:37Z: DRAGEN still running. `HG002.hard-filtered.vcf.gz` and `.tbi` existed, but DRAGEN had moved into SV discovery from BAM and had scanned 7.5% of 3,870 genome segments. `/ephemeral` was 293G used, 583G available.
- 2026-07-08T02:48:11Z: DRAGEN completed normally with `DRAGEN_EXIT_CODE=0` and total runtime `01:07:01.968`. `/ephemeral` was 226G used, 650G available at the next monitor tick.
- 2026-07-08T02:51:08Z: First `hap.py` launch failed immediately with `HAPPY_EXIT_CODE=1` because `${OUT_DIR}/scratch` did not exist. Fixed `/home/ec2-user/run_hg002_happy_20260708.sh` to create the scratch directory explicitly before invoking `hap.py`.
- 2026-07-08T02:51:32Z: Relaunched `hap.py`; process advanced into comparison and emitted an overlapping-record warning at `chr6:29747433`.
- 2026-07-08T03:09:42Z: `hap.py` completed with `HAPPY_EXIT_CODE=0`. SNP PASS F1 `0.941257`; SNP ALL F1 `0.940540`; INDEL PASS F1 `0.771719`; INDEL ALL F1 `0.771022`.
- 2026-07-08T03:14:16Z: Started S3 export with `/home/ec2-user/export_hg002_results_20260708.sh`; caller account verified as `108782052779`.
- 2026-07-08T03:16:00Z: S3 export finished. Local verification of `s3://lsmc-dayoa-analysis-results-usw2/dragen/hg002_pangenome_20260708/ec2/` reported `127` objects and `65,172,195,136` bytes.
- 2026-07-08T03:17:00Z: Updated `docs/other/running_dragen_manually.md` with final HG002 DRAGEN counts, `hap.py` F-scores, export prefix, and S3 verification summary.
