# dyecX4 4NA HiOMR SMN12 Validation Ledger

Objective: validate the newest DayOA HiOMR SMN12 caller set on `dyecX4`: first a positive `NA00232` smoke run with 20x ILMN plus ONT chip1+chip2, then the full 4NA x two chip-pair matrix after smoke success.

Controlling plan: user-provided plan in the 2026-06-11 Codex thread.

Ledger path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260611T164617Z_dyecX4_4na_hiomr_smn12_validation_ledger.md`

## Gate 0: Inventory Freeze

- Timestamp: `20260611T164617Z`
- Cluster: `dyecX4`
- Profile/region: `lsmc` / `us-west-2`
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DayOA baseline: `## jem-dev...origin/jem-dev`; `git describe --tags --always --dirty` -> `10.0.4`
- DYEC baseline: `## jem-dev...origin/jem-dev`; `git describe --tags --always --dirty` -> `10.0.13-2-g5ab91a32-dirty`
- DYEC local CLI: `dyec --json version` -> `10.0.11`
- Cluster status: `CREATE_COMPLETE`; compute fleet `RUNNING`; headnode `i-05815cdeec4a6dad8`
- Queue cleanup command: SSM command `7cbbd462-fd0a-4a6c-aff0-ae2b9cc9874b`
- Queue cleanup result: no matching analysis tmux sessions, no `ubuntu` Slurm jobs, no persistent `dy-r` / `day_run` / `snakemake` / `dyec export` processes.
- Current `/fsx/analysis_results/ubuntu/*` inventory: 53 directories from prior work; prior export log has 31 receipt-success rows and 22 not-yet-success rows.
- Current analysis-results DRA of note: `dra-08aaca7f88d3546c1` maps `/analysis_results/ubuntu/ccv_dryrun_pacbio_snv_alignstats_20260609T063015Z/` to `s3://lsmc-ssf-sequencing-data/derived/analysis_results/hyb-only/ubuntu/ccv_dryrun_pacbio_snv_alignstats_20260609T063015Z/`.
- 2026-06-11 re-check: `dra-08aaca7f88d3546c1` is still `AVAILABLE`; AWS CLI supports `delete-data-repository-association --no-delete-data-in-file-system`.
- Cleanup scope: only `/fsx/analysis_results/ubuntu/*` plus new ledger-owned analysis directories; non-`ubuntu` roots are out of scope.
- Destructive cleanup status: not approved yet for this ledger; exact paths must be printed before deletion.
- Workflow execution contract: headnode DayOA commands must run in persistent `ubuntu` tmux login shells as separate `source dyoainit`, `dy-a slurm hg38_broad`, then `dy-r ...`; never raw `snakemake`.

## Agent Rows

| ID | Agent | Area | Requirement | Status | Category | Approval Gate | Evidence | Root Cause | Terminal Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SMNVAL-001 | agent-orchestrator | Ledger | Own ledger, Gate 0, approvals, final counts. | IN_PROGRESS | feature_implementation | Gate 0/Gate 5 | This ledger; Gate 0 recorded. |  |  |
| SMNVAL-002 | agent-queue-cleaner | Runtime | Clear analysis tmux/controllers/jobs before new work. | SUCCESS | legitimate_safety_handling | Gate 0 | SSM `7cbbd462-fd0a-4a6c-aff0-ae2b9cc9874b`: no tmux sessions, no jobs, no workflow/export processes. |  | Analysis execution was already stopped; no jobs required cancellation. |
| SMNVAL-003 | agent-export-cleanup | Export/Cleanup | Export existing `/fsx/analysis_results/ubuntu/*`, then delete only approved exact paths. | BLOCKED | feature_implementation | Export gate/destructive approval | Retry with `max-workers=1` skipped 31 existing successes and failed the remaining 22. First failure: source path overlaps `dra-08aaca7f88d3546c1`; subsequent failures: FSx DRA limit reached. Re-check confirms export table has 31 `skipped_existing_success` rows and 22 `failed` rows. | Temporary export DRA `dra-08aaca7f88d3546c1` remains attached at `/analysis_results/ubuntu/ccv_dryrun_pacbio_snv_alignstats_20260609T063015Z/`, and the FSx filesystem is at its DRA limit. | Requires explicit approval to detach the temporary analysis-results DRA with `delete_data_in_file_system=false` using `aws fsx delete-data-repository-association --association-id dra-08aaca7f88d3546c1 --no-delete-data-in-file-system`; no FSx or S3 data deletion is requested for this detach. |
| SMNVAL-004 | agent-dayoa-resource | DayOA resources | Ensure SMN12 caller rules request 192 vCPU and 250G memory. | SUCCESS | contract_test | Gate 1 | DayOA files `config/day_profiles/slurm/templates/rule_config.yaml`, `config/day_profiles/local/templates/rule_config.yaml`, `config/global.yaml`, `tests/test_htd_callers_contract.py`, `tests/test_sentdhiomr_resource_tuning.py`; focused pytest -> `20 passed`. |  | SMNCopyNumberCaller, SMAca, sma-finder, HapSMA, and Sentieon HiOMR segdup use requested slurm resources in the Slurm profile; HapSMA coverage gate is now 4 for the requested two-chip smoke. |
| SMNVAL-005 | agent-hiomr-config | DayOA/Runtime | Restrict Sentieon segdup to SMN only and verify current ONT model usage. | SUCCESS | config_or_startup_contract | Gate 1/runtime | Smoke dry-run log `logs/dryrun_smn12_orthogonal_20260611T224352Z.log` rendered `segdup-caller --genes SMN1`, `--lr_model /fsx/references/runtime_assets/cached_envs/sentieon-genomics-202503.02/bundles/DNAscopeONT2.3.bundle`, and `--sr_model .../SentieonIlluminaWGS2.2.bundle`. |  | Sentieon HiOMR segdup is restricted to SMN1 for this validation and uses the current ONT model. |
| SMNVAL-006 | agent-hapsma-runtime | DayOA/Runtime | Provide explicit HapSMA runtime config/assets with no fallback. | SUCCESS | config_or_startup_contract | Runtime gate | DayOA now ports HapSMA `bam_single_remap` into native `workflow/rules/hapsma.smk` instead of launching Nextflow; `workflow/envs/hapsma_v0.1.yaml` now declares component tools and pins `minimap2 =2.31`; focused pytest `tests/test_htd_callers_contract.py tests/test_tool_catalog_docs.py` -> `22 passed`; one-time hg38_broad map-ont `.mmi` created with minimap2 `2.31-r1302`, uploaded to `s3://lsmc-dayoa-references-usw2/genomic_data/organism_references/H_sapiens/hg38_broad/Homo_sapiens_assembly38.map-ont.mmi`, and visible at `/fsx/references/genomic_data/organism_references/H_sapiens/hg38_broad/Homo_sapiens_assembly38.map-ont.mmi`; SHA-256 `61b55fabf5caf8a5c5f29ba81936f7edbbe0ee28f296a1259e710d5ddaa879ac`. HapSMA support BEDs uploaded and visible under `/fsx/references/runtime_assets/tool_specific_resources/hapsma/hg38_broad/`; smoke runtime patch sets explicit `ploidy`, SMN regions, support BEDs, Clair3 model, `.mmi`, minimap params, coverage gate `4`, and 192-thread/250G resources. |  | The reference DRA `/references/ -> s3://lsmc-dayoa-references-usw2` already had auto-import `NEW/CHANGED/DELETED`; the `.mmi` and support BEDs appeared automatically after S3 upload. Temporary exact-key headnode role policies `TemporaryHapSmaHg38BroadMmiUpload20260611` and `TemporaryHapSmaSupportBedUpload20260611` were attached only for uploads and removed after verification. |
| SMNVAL-007 | agent-inputs | Inputs | Generate mounted FASTQ sample/unit configs for smoke plus 8 full units. | BLOCKED | feature_implementation | Runtime gate | Input staging completed at `/fsx/analysis_inputs/ubuntu/4na_hiomr_smn12_20260611T220404Z`; 20x ILMN has all 8 FASTQs; ONT chip1/chip2/chip4 have barcode18/19/20/21; ONT chip3 has only barcode19. | Exact requested chip3+chip4 rows are missing chip3 data for `NA00232`/barcode18, `NA03986`/barcode20, and `NA05164`/barcode21. | Can run exact rows only for chip1+chip2 for all four samples and chip3+chip4 for `NA09677`. Requires user approval to substitute chip4-only for the missing chip3+chip4 rows. |
| SMNVAL-008 | agent-smoke | Smoke run | Run `NA00232` 20x ILMN + ONT chip1+chip2 and verify all five SMN12 evidence sources. | SUCCESS | feature_implementation | Runtime gate | Headnode checkout source-patched to DayOA `d1ed88c`; smoke dry-run `dy-r produce_smn12_orthogonal_calls produce_htd_calls produce_sentdhiomr_segdup -p -T 0 -k -j 500 --rerun-triggers mtime -n` returned `0`; final live retry `logs/live_retry_hapsma_regionref_20260612T005928Z.log` returned `0`. Five evidence sources produced terminal outputs: SMNCopyNumberCaller, SMAca, sma-finder, HapSMA, and Sentieon HiOMR segdup SMN1. Aggregate reports `results/day/hg38_broad/other_reports/htd_calls_mqc.tsv` and `results/day/hg38_broad/other_reports/smn12_orthogonal_calls_mqc.tsv` were written. |  | HapSMA is `dev_exploratory`; for this 2-chip smoke it records explicit `no_call_no_phase_set` with mean SMN-region ONT coverage `7.713221`, not a copy-number call. |
| SMNVAL-009 | agent-full-4na | Full run | Run all eight 4NA hybrid units after smoke pass. | BLOCKED | feature_implementation | Runtime gate | Smoke passed. Exact input availability rechecked: chip1+chip2 has barcode18/19/20/21 for all four NAs; chip3+chip4 is complete only for barcode19/NA09677 because chip3 contains barcode19 only. | Exact requested chip3+chip4 rows are missing chip3 data for `NA00232`/barcode18, `NA03986`/barcode20, and `NA05164`/barcode21. | Can run exact rows only for chip1+chip2 for all four samples and chip3+chip4 for `NA09677`. Requires user approval to substitute chip4-only for the missing chip3+chip4 rows. |
| SMNVAL-010 | agent-evidence | Evidence | Export successful new analyses and write final evidence summary. | OPEN | feature_implementation | Export gate | No new analyses launched yet. |  |  |

## Validation Evidence

Local DayOA focused validation after resource updates:

```text
python -m pytest -q tests/test_htd_callers_contract.py tests/test_sentdhiomr_resource_tuning.py tests/test_workflow_catalog.py tests/test_multiqc_qc_targets.py tests/test_workflow_target_aliases.py tests/test_tool_catalog_docs.py
65 passed in 0.46s

python -m compileall -q workflow/scripts/htd_calls_mqc.py workflow/scripts/smn12_orthogonal_calls_mqc.py
exit_code=0

python -m pytest -q tests/test_htd_callers_contract.py tests/test_sentdhiomr_resource_tuning.py
20 passed in 0.32s
```

## Pending Gates

- Export the remaining current `/fsx/analysis_results/ubuntu/*` directories through DRA, using receipts as authority.
- Print the exact cleanup path list and request second destructive approval before deleting any FSx analysis directory.
- Monitor the live `NA00232` two-chip smoke run to terminal status.
- After smoke success, generate and run the exact full rows that have input support. The requested chip3+chip4 rows remain blocked for `NA00232`, `NA03986`, and `NA05164` until missing chip3 barcode data is supplied or the user explicitly approves a labeled chip4-only substitute.

## 20260611T230650Z Smoke Live Monitor

- Active analysis: `/fsx/analysis_results/ubuntu/hiomr_smn12_smoke_na00232_chip12_20260611T223200Z/daylily-omics-analysis`
- Active tmux session: `dayoa_smn12_smoke_na00232_20260611T223200Z`
- Live command: `dy-r produce_smn12_orthogonal_calls produce_htd_calls produce_sentdhiomr_segdup -p -T 0 -k -j 500 --rerun-triggers mtime`
- Current state: Slurm job `246` is running `sentmm2ont_align_sort` on `i384nvme-dy-price384nvme-1`.
- Resource evidence: Slurm submit requested `--cpus-per-task=192`; the compute node is `m8idn.96xlarge`; minimap2/samtools/mbuffer/gzip are active.
- Scratch evidence: rule created `/scratch/sentmm2ont_tmp_20260611225813_13710` on the NVMe `/scratch` filesystem.
- No intervention performed; monitoring remains read-only.

## 20260611T233407Z Clair3 Model Runtime Asset

- HapSMA failed before variant calling because the explicit runtime config pointed to a non-existent conda-local model directory: `${CONDA_PREFIX}/bin/models/r1041_e82_400bps_sup_v500`.
- Created the missing Clair3 model as a one-time reference asset from the upstream Clair3 PyTorch model directory.
- Source: `https://www.bio8.cs.hku.hk/clair3/clair3_models_pytorch/r1041_e82_400bps_sup_v500/`
- S3 root: `s3://lsmc-dayoa-references-usw2/runtime_assets/tool_specific_resources/clair3/models/r1041_e82_400bps_sup_v500/`
- FSx root: `/fsx/references/runtime_assets/tool_specific_resources/clair3/models/r1041_e82_400bps_sup_v500/`
- Files:
  - `pileup.pt`, SHA-256 `d84d9f1a1da0a68204404cac1817724ada4d15363d8a62d87703b6ed56c4a4ff`
  - `full_alignment.pt`, SHA-256 `320f7083ae1b8eeba390471fbbeb6fbefb93dab079300ce2605a7222d7d65388`
  - `SHA256SUMS`
  - `README.provenance.txt`
- Smoke analysis runtime config updated to use the FSx model root above in `config/day_profiles/slurm/rule_config.yaml` and `config/patch_smn12_runtime.py`.

## 20260611T222618Z HapSMA Minimap Index Asset

- Built once on dyecX4 under `/fsx/scratch/hapsma_hg38_broad_mmi_20260611T222400Z/` using Bioconda `minimap2 2.31-r1302`.
- Input FASTA: `/fsx/references/genomic_data/organism_references/H_sapiens/hg38_broad/Homo_sapiens_assembly38.fasta`
- Build command: `minimap2 -x map-ont -d Homo_sapiens_assembly38.map-ont.mmi Homo_sapiens_assembly38.fasta`
- S3 object: `s3://lsmc-dayoa-references-usw2/genomic_data/organism_references/H_sapiens/hg38_broad/Homo_sapiens_assembly38.map-ont.mmi`
- Sidecars:
  - `s3://lsmc-dayoa-references-usw2/genomic_data/organism_references/H_sapiens/hg38_broad/Homo_sapiens_assembly38.map-ont.mmi.sha256`
  - `s3://lsmc-dayoa-references-usw2/genomic_data/organism_references/H_sapiens/hg38_broad/Homo_sapiens_assembly38.map-ont.mmi.provenance.txt`
- FSx visible path: `/fsx/references/genomic_data/organism_references/H_sapiens/hg38_broad/Homo_sapiens_assembly38.map-ont.mmi`
- SHA-256 from scratch build and `/fsx/references` import: `61b55fabf5caf8a5c5f29ba81936f7edbbe0ee28f296a1259e710d5ddaa879ac`
- Upload note: headnode initially lacked `s3:PutObject`; temporary exact-key inline policy `TemporaryHapSmaHg38BroadMmiUpload20260611` was attached to `dyecX4-RoleHeadNode-MnfdTOlVjuad`, used only for `Homo_sapiens_assembly38.map-ont.mmi*`, and deleted after S3 and FSx verification.

## 20260611T222838Z HapSMA Support BED Assets

- S3 root: `s3://lsmc-dayoa-references-usw2/runtime_assets/tool_specific_resources/hapsma/hg38_broad/`
- FSx root: `/fsx/references/runtime_assets/tool_specific_resources/hapsma/hg38_broad/`
- SMN-only target BED: `SMN_region_38.smn_only.bed`
  - Source: first four SMN rows from DayOA `workflow/resources/smn12/SMN_region_38.bed`.
  - SHA-256: `dece4a69067371b581130ce2d228681ac1d8ef712c27a7e1622761d263560fdc`
- Homopolymer BED: `hg38_broad_smn_100kb_pad_homopolymer_run3.bed`
  - Source FASTA: `/fsx/references/genomic_data/organism_references/H_sapiens/hg38_broad/Homo_sapiens_assembly38.fasta`
  - Interval: `chr5:69949522-71054173` using 0-based half-open coordinates, i.e. SMN1/SMN2 target span padded 100 kb.
  - Rule: A/C/G/T homopolymer runs with length `>=3`.
  - Rows: `73848`
  - SHA-256: `3e63f7fd4879a6dd69c6bd028e2431015bc0066bb9959f2522b0f8686b3fa689`
- Provenance file: `README.provenance.txt`
  - SHA-256: `7cb650da2bdcd3b5519c1eaa556d8335b1cc040dc04e3b607234c0ea85945ca6`
- Upload note: temporary exact-key inline policy `TemporaryHapSmaSupportBedUpload20260611` was attached to `dyecX4-RoleHeadNode-MnfdTOlVjuad`, used only for `runtime_assets/tool_specific_resources/hapsma/hg38_broad/*`, and deleted after S3 and FSx verification.

## 20260612T010205Z Smoke Result And Full-Input Gate

- Smoke analysis: `/fsx/analysis_results/ubuntu/hiomr_smn12_smoke_na00232_chip12_20260611T223200Z/daylily-omics-analysis`
- tmux session: `dayoa_smn12_smoke_na00232_20260611T223200Z`
- Final smoke command: `dy-r produce_smn12_orthogonal_calls produce_htd_calls produce_sentdhiomr_segdup -p -T 0 -k -j 500 --rerun-triggers mtime`
- Final smoke log: `logs/live_retry_hapsma_regionref_20260612T005928Z.log`
- Final smoke exit: `RETURN CODE: 0`
- One-time minimap index used by HapSMA:
  - S3: `s3://lsmc-dayoa-references-usw2/genomic_data/organism_references/H_sapiens/hg38_broad/Homo_sapiens_assembly38.map-ont.mmi`
  - FSx: `/fsx/references/genomic_data/organism_references/H_sapiens/hg38_broad/Homo_sapiens_assembly38.map-ont.mmi`
  - SHA-256: `61b55fabf5caf8a5c5f29ba81936f7edbbe0ee28f296a1259e710d5ddaa879ac`
- Smoke evidence sources:
  - SMNCopyNumberCaller: `.../htd/smn12/*.smn12.summary.tsv`, `isSMA=True`, `isCarrier=False`, `SMN1_CN=0`, `SMN2_CN=1`
  - sma-finder: `.../htd/sma_finder/*.sma_finder.summary.tsv`, `sma_status=has SMA`, `confidence_score=13`
  - SMAca: `.../htd/smaca/*.smaca.summary.tsv`, completed with copied caller table
  - HapSMA: `.../htd/hapsma/*.hapsma.summary.tsv`, completed as `dev_exploratory` with `bed_phase_status=no_call_no_phase_set`, `region_phase_status=no_call_no_phase_set`, mean SMN region coverage `7.713221`
  - Sentieon HiOMR segdup SMN1: `.../segdup/sentdhiomr/results/SMN1/*.SMN1.yaml` and `*.SMN1.result.vcf.gz`, with SMN-only done markers
- Aggregate reports:
  - `results/day/hg38_broad/other_reports/htd_calls_mqc.tsv`
  - `results/day/hg38_broad/other_reports/smn12_orthogonal_calls_mqc.tsv`
- Exact ONT input counts for requested full matrix:

```text
chip1 barcode18 73
chip1 barcode19 73
chip1 barcode20 73
chip1 barcode21 73
chip2 barcode18 73
chip2 barcode19 73
chip2 barcode20 73
chip2 barcode21 73
chip3 barcode18 0
chip3 barcode19 9
chip3 barcode20 0
chip3 barcode21 0
chip4 barcode18 73
chip4 barcode19 73
chip4 barcode20 73
chip4 barcode21 73
```

- Exact full 4NA request status:
  - Runnable exactly: chip1+chip2 for `NA00232`, `NA09677`, `NA03986`, `NA05164`
  - Runnable exactly: chip3+chip4 for `NA09677` only
  - Blocked exactly: chip3+chip4 for `NA00232`, `NA03986`, `NA05164` because chip3 barcode18/20/21 FASTQs are absent

## Proposed HapSMA Runtime Config Candidate

This is not approved or applied yet. It is the current explicit candidate for resolving `SMNVAL-006`.

DayOA `config.hapsma` candidate:

| Key | Proposed value | Basis |
| --- | --- | --- |
| `nextflow_command` | `nextflow` | DayOA `workflow/envs/hapsma_v0.1.yaml` installs Nextflow. |
| `workflow_path` | `resources/hapsma/HapSMA-v1.1.0` or an absolute deployed copy of that path | Pinned upstream `UMCUGenetics/HapSMA` tag `v1.1.0`, commit `f23300379aa656550578e85c5a1e6d71a6fadea9`. |
| `config_path` | `resources/hapsma/HapSMA-v1.1.0/dayoa_hg38_broad.SMA.config` | LSMC hg38_broad config to be generated explicitly. |
| `email` | `johnm@lsmc.com` | User plan corrected `johnm@lsmc.ccom` typo. |
| `ploidy` | `1` for `NA00232`, `NA09677`, `NA03986`, and `NA05164` | Prior 4NA SMN report has total SMN1+SMN2 CN of 1 for all four samples, despite NA05164 caller discordance on which gene has the copy. |
| `start` | `bam_single_remap` | HapSMA recommended mode for a single BAM path with remapping. |
| `single_bam_type` | `path` | DayOA passes one extracted SMN-region BAM path. |
| `smn_region` | `chr5:69949523-71054173` | DayOA `SMN_region_38.bed` SMN1/SMN2 rows only, converted/padded 100 kb. |
| `min_smn_region_mean_coverage` | `4` | User requested two-chip smoke with expected ~8x ONT coverage and a 4x gate. Applied in DayOA global, local-profile, Slurm-profile, and rule fallback surfaces. |
| `clair3model` | `/opt/models/r1041_e82_400bps_sup_v500` | Candidate for modern ONT R10.4.1 SUP data; replaces upstream R9.4.1 default. |
| `extra_args` | empty | No unreviewed extra HapSMA args. |
| `container` | explicit Snakemake `container:` image if HapSMA is containerized | User instruction: any containerized HapSMA execution must be through the DayOA/Snakemake container directive, not an unmanaged nested Nextflow container pull. No image is approved yet. |
| `threads` / `mem_mb` / `partition` | `192` / `250000` / `i192hugenvme,i192nvme,i384nvme` | Already applied in DayOA Slurm template and tested. |

HapSMA `dayoa_hg38_broad.SMA.config` candidate:

| Key | Proposed value | Basis |
| --- | --- | --- |
| `genome_fasta` | `/fsx/references/genomic_data/organism_references/H_sapiens/hg38_broad/Homo_sapiens_assembly38.fasta` | Active DayOA `hg38_broad` supporting file. |
| `genome_mapping_index` | same FASTA plus `.mmi`, optional for the selected mode | HapSMA upstream says `.mmi` is only needed for Guppy re-basecalling. DayOA is using `bam_single_remap`, where HapSMA remapping uses the FASTA directly. Read-only S3 check found the FASTA present and `.mmi` absent at the expected hg38_broad reference key. If generated, build under `/fsx/scratch` and copy to the reference bucket backing the read-only import. |
| `calling_target_bed` | generated SMN-only BED copied from the first four SMN rows of DayOA `workflow/resources/smn12/SMN_region_38.bed` | Avoids including SMNCopy normalization loci. |
| `calling_target_region` | `chr5:69949523-71054173` | Same padded SMN1/SMN2 interval. |
| `phaseset_region` | `chr5:69949523-71054173` | Conservative first guess; HapSMA will choose the dominant phase set in this interval or fail hard if ambiguous. |
| `homopolymer_bed` | generated hg38_broad SMN-region homopolymer BED, same padded interval | No existing DayOA homopolymer BED found; deterministic generated asset is cleaner than using simple repeats as a proxy. Upstream example names a `3homopolymer` BED, but the exact run-length threshold remains an explicit config decision. |
| `clair3model` | `/opt/models/r1041_e82_400bps_sup_v500` | Mirrors DayOA `hapsma.clair3model`. |
| `single_bam_type` | `path` | Matches DayOA call. |
| `platform` / `minimap_param` | `ONT` / `-y -ax map-ont` | Upstream ONT defaults. |
| `singularity` or `apptainer` | disabled inside Nextflow if a Snakemake container is used | HapSMA modules declare containers, but user instruction requires containerization through Snakemake. A compliant setup needs either a single Snakemake-managed HapSMA image with all module tools on `$PATH`, or a non-container conda/module runtime. |
| `executor` | local | Run Nextflow inside the already allocated Snakemake Slurm job; do not submit nested Slurm jobs. |
| `mail.smtp.host` | `localhost` | Upstream configs use localhost; needed because HapSMA calls `sendMail` on completion. |
