# HIOMR2 take6 HG003+HG004 five-shard kitchen-sink and Inflection-package launch ledger

## Objective

Create a fresh `take6` DayOA checkout at the just-released `13.0.67` tag, then
run the existing HG003+HG004 original-five-shard HIOMR2 kitchen-sink plus
Inflection analytical-package command on `hg38` under cost center `RnD`.

## Immutable execution contract

- Cluster/profile/region: `preval-hiomr2` / `lsmc` / `us-west-2`.
- DayOA source: annotated `13.0.67`, release commit
  `9d627b7bd8d6aac1ad75bcb92e464e340cdf86ec`.
- Clone request: `day-clone -t 13.0.67 -d take6`.
- Intended analysis workspace root:
  `/fsx/analysis_results/preval-hiomr2/take6`.
- Intended DayOA checkout:
  `/fsx/analysis_results/preval-hiomr2/take6/daylily-omics-analysis`.
- Controller shell: `ubuntu` interactive `bash -il` in tmux session
  `hiomr2_take6_hg003_hg004_20260728`.
- Input source: the exact seven staged take5 config/manifests under
  `/fsx/analysis_results/preval-hiomr2/hiomrks-take5/daylily-omics-analysis/config/`:
  `hiomr2_hg003_hg004_take5_full_chrom_shards.yaml`, `specimens.tsv`,
  `samples.tsv`, `libraries.tsv`, `sequencing_inputs.tsv`, `analysis_units.tsv`,
  and `analysis_unit_inputs.tsv`.
- Expected scope: both HG003 and HG004, each through five original shard
  groups (`1,2,3`; `4,5,6,7,8`; `9,10,11,12,13,14,15`;
  `16,17,18,19,20`; `21,22,23,24,25`), corresponding to chromosomes 1–22,
  X, Y, and MT.
- Runtime contract: `RnD`, batch `this-time-go`, `hg38`, `-j 300 -p -T 0`, no
  `-k`, `--rerun-triggers mtime --rerun-incomplete --keep-temp`.
- The active take5 HG003 retry is out of scope and must not be modified.

## Command

```bash
dy-r produce_sentdhiomr2_kitchensink produce_sentdhiomr2_inflection_analytical_package \
  -j 300 -p -T 0 \
  --configfile config/hiomr2_hg003_hg004_take5_full_chrom_shards.yaml \
  --config 'genome_build=hg38' 'aligners=["sentmm2ont"]' \
  'dedupers=["na"]' 'snv_callers=["sentdhiomr2"]' 'sv_callers=[]' \
  'htd_callers=["smn12"]' use_fq_data_starting_hrs=0 \
  use_fq_data_up_to_hrs=25 'seqone_delivery_batch_id=this-time-go' \
  'hiomr2_inflection_package_mode=analytical' \
  --rerun-triggers mtime --rerun-incomplete --keep-temp
```

First append `-n`. Proceed with the identical command without `-n` only if the
dry-run is RC 0 and scopes only the fresh intended HG003/HG004 work.

## Gate ledger

| ID | Gate | Status | Evidence |
| --- | --- | --- | --- |
| SRC-001 | Released source pin | COMPLETE | Annotated `13.0.67` release tag points to `9d627b7bd8d6aac1ad75bcb92e464e340cdf86ec`. |
| IN-001 | Exact take5 HG003+HG004 inputs identified | COMPLETE | Existing overlay and six manifest TSVs describe two AUs and five original chromosome shard groups. |
| CLONE-001 | Fresh `take6` clone | COMPLETE | `day-clone -t 13.0.67 -d take6` completed under the held write lock. The checkout is clean, detached at `9d627b7bd8d6aac1ad75bcb92e464e340cdf86ec`, and `git describe --tags --exact-match` is `13.0.67`. |
| STAGE-001 | Seven source inputs copied, backed up, and byte-verified | COMPLETE | Each source/staged/backup SHA-256 triplet matches. Overlay `d18a587f22434107dc0e47becd72ca8983944f573a1d08cf8ae61d31b35af1fd`; manifest SHA-256 values are preserved in the headnode validation receipt. |
| VALIDATE-001 | Manifest/config validation | COMPLETE | `dayoa manifests validate --manifest-dir ./config --receipt ./config/manifest_validation_receipt.json` succeeded: two specimens/samples/AUs, four libraries, eight sequencing inputs/AU-inputs, valid foreign keys and deterministic order; no identifiers created/rewritten and no network access. |
| LOCK-001 | New-root write lock | COMPLETE | `dyec analysis visit` recorded the new workspace and `dyec analysis lock acquire` succeeded before cloning. |
| PLAN-001 | Exact two-sample dry-run | COMPLETE | RC 0 at 2026-07-28 08:10 UTC. It plans 30 fresh jobs: 15 each for `HG003-jdv62j389vjyjz` and `HG004-zysr4zstg9p3vp` (SR/LR preparation, five shard gVCFs, concat, hard-VCF compatibility, CNVscope, LongReadSV, command manifest, package, and public targets). No completed or independent obsolete gVCF work is planned. The package receives the final hard `*.vcf.gz`/index for each AU. |
| RUN-001 | Live controller submission | COMPLETE | The reviewed identical command was launched without `-n` at 2026-07-28 08:12 UTC under the held `/fsx/analysis_results/preval-hiomr2/take6` write lock. |
| VERIFY-001 | Initial live controller and Slurm evidence | IN PROGRESS | Controller PID `2261939` is alive in the dedicated tmux pane. RnD preflight jobs `503` (HG003) and `504` (HG004) completed `0:0` in 26/23 seconds; SR/LR preparation jobs `505`–`508` are admitted and currently `CONFIGURING` on new `i192nvme` capacity. The rendered HG004 LR command uses the repaired escaped-tab RG form with `ID:HG004-zysr4zstg9p3vp-lr`, `SM:HG004-zysr4zstg9p3vp`, `LB:M-BNQ-12D`, `PL:ONT`, and `LR:1`. |
| SCOPE-001 | Specialty/QC kitchen-sink coverage | EXPOSED | The RC-0 take6 plan contains only preflight, SR/LR preparation, 10 shard gVCFs, concat, hard-VCF compatibility, CNVscope, LongReadSV, command manifests, and packages. It contains no Ganon2/metagenomics, SMN12 copy-number/HTD, peddy, relatedness, GATK/site-mix contamination, VEP, AlignStats, mitochondrial, SegDup, or MultiQC rules. The running target pair therefore does not yet deliver the broader HIOMR kitchen-sink QC/caller surface. |

## Boundaries

- Do not alter, cancel, or restart the active take5 controller or jobs.
- Do not use raw `snakemake`; all workflow execution uses `dy-r` from the
  initialized interactive DayOA shell.
- Preserve temporary five-shard artifacts via `--keep-temp`.

## Command-catalog comparison

At launch, the headnode DYEC catalog still declares the HIOMR2 kitchen-sink plus
analytical-Inflection target pair, but its entries are validated at `13.0.59` and
specify `hg38_broad`, `DAY_CONTAINERIZED=true`, `-k -j 200`, and an owner-issued
`SEQONE_DELIVERY_BATCH_ID` environment value. Its BJuice variant adds the `0,25`
ONT interval. Take6 intentionally follows the user's later explicit contract:
the fresh `13.0.67` clone, `hg38`, the reviewed two-sample take5 manifests,
`-j 300`, no `-k`, `--keep-temp`, and literal batch `this-time-go`.
