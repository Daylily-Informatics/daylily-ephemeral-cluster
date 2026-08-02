# HG002 5x/5x HIOMR2 kitchen-sink, mega, and Inflection analytical-package runbook

## Proven execution

- Cluster: `preval-hiomr2` in `us-west-2`, AWS profile `lsmc`
- Headnode user: `ubuntu`
- Analysis root: `/fsx/analysis_results/preval-hiomr2/13-4-0`
- DayOA checkout: `/fsx/analysis_results/preval-hiomr2/13-4-0/daylily-omics-analysis`
- Persistent one-pane tmux: `dayoa_hg002_5x5x_1340_20260802`
- Live-proven release: annotated non-v tag `13.4.1`
- Release commit: `9d8d1a52ae84bb38c1e9fca8c037ee4d2b4c18ec`
- Config overlay: `config/hg002_bjuice_true5x5x_hiomr2_13_4_0.yaml`
- Final workflow result: controller `RC=0`; Slurm job `3369 multiqc_final_wgs` completed `0:0`
- Final MultiQC: `daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc.html`
- Inflection package: `daylily-omics-analysis/results/day/hg38/deliveries/inflection_hiomr2_analytical_callsets_vcf_gvcf/hg002-bjuice-5x5x-1340-20260802/HG002-gy7skbxt0rc9h2/`

The immutable release was created after the final live proof. The final MultiQC banner therefore retains the initialized base metadata `TAG:13.4.0` and `HASH:3bf5b417` even though the live-proven 20-file repair delta was subsequently committed and tagged exactly as DayOA `13.4.1` at `9d8d1a52...`. Use the tag/commit above as the released-code identity and preserve this banner caveat in downstream reports.

## Required operator contracts

1. Read the current DayOA operator instructions before beginning:
   `/Users/jmajor/.codex/AGENTS-HOW-TO-RUN-DAYOA.md`.
2. Run as `ubuntu` in an interactive Bash login shell on the headnode.
3. Use one persistent, meaningfully named, one-pane tmux. Do not launch a controller with SSM Run Command.
4. Never invoke `snakemake` directly. Use `dy-r`; it passes the target and flag arguments through.
5. Execute initialization as separate commands in the tmux pane: `source dyoainit`, then `dy-a slurm hg38`, then `dy-r ...`.
6. Record an analysis visit before reading or writing `/fsx/analysis_results/**`. Own the analysis-root write lock for configuration changes and every live or dry-run `dy-r` invocation. Never take over another owner silently.
7. Preserve the explicit approved RnD launch context:
   `DAY_PROJECT=RnD` and `DAYLILY_COST_CENTER=RnD`.
8. Do not cancel, requeue, hold, release, drain, resume, or administer Slurm as part of normal workflow execution.

## Recreate a fresh exact-tag checkout

From an interactive `ubuntu` Bash login shell on the headnode:

```bash
export DAYOA_AGENT_ID=<stable-agent-id>
export DAYOA_AGENT_KIND=codex
export DAYOA_HUMAN_REQUESTOR=jmajor
export DAYOA_TMUX_SESSION=<meaningful-session-name>
export DAYOA_LEDGER_PATH=<durable-ledger-path>

dyec analysis visit \
  --analysis-root /fsx/analysis_results/preval-hiomr2/<fresh-analysis-id> \
  --mode write \
  --intent "Prepare exact DayOA 13.4.1 HIOMR2 validation"

dyec analysis lock acquire \
  --analysis-root /fsx/analysis_results/preval-hiomr2/<fresh-analysis-id> \
  --operation write \
  --intent "Create exact-tag DayOA checkout and run HIOMR2"

tmux new-session -d -s <meaningful-session-name> 'exec bash -l'
tmux send-keys -t <meaningful-session-name>:0.0 'day-clone -t 13.4.1 -d <fresh-analysis-id>' C-m
```

Wait for `day-clone` to return to the persistent prompt. In the same pane, send these as separate commands:

```bash
cd /fsx/analysis_results/preval-hiomr2/<fresh-analysis-id>/daylily-omics-analysis
source dyoainit
dy-a slurm hg38
export DAY_PROJECT=RnD
export DAYLILY_COST_CENTER=RnD
```

Prove the release before staging inputs:

```bash
git status --short --untracked-files=no
git rev-parse HEAD
git rev-parse '13.4.1^{}'
git cat-file -t 13.4.1
```

The tracked checkout must be clean, `HEAD` and `13.4.1^{}` must both equal `9d8d1a52ae84bb38c1e9fca8c037ee4d2b4c18ec`, and `git cat-file -t` must print `tag`.

## Input and configuration contract

The proven run used exactly six provider-neutral manifests under `config/`:

- `specimens.tsv`
- `samples.tsv`
- `libraries.tsv`
- `sequencing_inputs.tsv`
- `analysis_units.tsv`
- `analysis_unit_inputs.tsv`

The validation receipt is `config/hg002_bjuice_true5x5x_manifest_validation_receipt.json`. It records one specimen, one sample, two libraries, two sequencing inputs, one analysis unit, and two analysis-unit inputs with valid foreign keys and deterministic order.

The sequencing inputs are:

- Illumina paired FASTQs, 60,277,137 reads per mate and measured 5.862704556x:
  - `/fsx/references/genomic_data/organism_reads_slim/fastq/H_sapiens/giab/NovaSeqX_WHGS_TruSeqPF_HG002-007/downsampled/HG002_5x_R1.fastq.gz`
  - `/fsx/references/genomic_data/organism_reads_slim/fastq/H_sapiens/giab/NovaSeqX_WHGS_TruSeqPF_HG002-007/downsampled/HG002_5x_R2.fastq.gz`
- Deterministic seed-1340 ONT FASTQ, 1,963,980 reads and approximately 5x:
  - `/fsx/references/genomic_data/organism_reads_slim/fastq/H_sapiens/giab/bjuice_preval_2026/HG002/ont/downsampled/HG002_BJUICEPREVAL_ONT_5x.seqkit-sample-seed1340.fastq.gz`

Do not infer full coverage or depth from a filename. Validate identity, file type, gzip integrity, read counts, bytes, hashes, and receipt agreement before launching.

The overlay `config/hg002_bjuice_true5x5x_hiomr2_13_4_0.yaml` enables the NICU research lane, analytical Inflection packaging, retained stage artifacts, and PASS-only Truvari 5.4.0 benchmarking with `--sizemin 50 --sizefilt 50 --sizemax -1 --refdist 500 --pctsize 0.7 --pctseq 0.7 --pctovl 0 --pick single`.

## Exact target closure

There is no guessed `mega` alias. The literal kitchen-sink, mega-adjacent validation, and Inflection analytical-package closure is:

```text
produce_sentdhiomr2_kitchensink
produce_sentdhiomr2_nicu_research
produce_sentdhiomr2_jasmine_sentieon_validation
produce_sentdhiomr2_jasmine_sharded_per_sample
produce_sentdhiomr2_truvari_sv_benchmarks
produce_sentdhiomr2_jasmine_le50_rtg_concordance
produce_sentdhiomr2_inflection_analytical_package
results/day/hg38/reports/DAY_final_multiqc.html
```

Use `sv_callers=[]`; the HIOMR2-owned TIDDIT path is already inside this closure and must not be duplicated through the unrelated legacy generic-SV selector.

## Dry run and live run

The proven dry-run command was:

```bash
dy-r \
  produce_sentdhiomr2_kitchensink \
  produce_sentdhiomr2_nicu_research \
  produce_sentdhiomr2_jasmine_sentieon_validation \
  produce_sentdhiomr2_jasmine_sharded_per_sample \
  produce_sentdhiomr2_truvari_sv_benchmarks \
  produce_sentdhiomr2_jasmine_le50_rtg_concordance \
  produce_sentdhiomr2_inflection_analytical_package \
  results/day/hg38/reports/DAY_final_multiqc.html \
  -j 300 -p -T 0 -k --rerun-triggers mtime -n \
  --configfile config/hg002_bjuice_true5x5x_hiomr2_13_4_0.yaml \
  --config \
    genome_build=hg38 \
    'aligners=["sentmm2ont"]' \
    'dedupers=["na"]' \
    'snv_callers=["sentdhiomr2"]' \
    'sv_callers=[]' \
    'htd_callers=["smn12"]'
```

Inspect the generated commands, target closure, selected config, job count, threads, partitions, and reasons. Only after the dry run returns `RC=0`, repeat the identical command with only `-n` removed.

## Monitoring and recovery

- Monitor the tmux pane, controller PID/log, `squeue`, `sacct`, rule logs, receipts, and output publication read-only.
- `-T 0` means the 5x/5x proof did not automatically retry lost-node failures. For a new run using `-T 1`, allow its one workflow retry to handle a proven lost-node event.
- Do not diagnose a rule as a source defect solely from a pending/configuring state, temporary absence from a filtered queue view, or a point-in-time compute-node sample.
- After controller exit nonzero, inventory every failed job and confirm the workflow released its lock. Reacquire the analysis-root write lock normally before any repair or retry.
- Repair only a proven source contract. Run focused tests, then the exact `--rerun-triggers mtime -n` command. Only if that is clean may the identical live command be resubmitted.
- Versioned environment YAMLs are immutable. Create the next numbered YAML and update explicit references/tests; never modify an existing version in place.
- Commit the live-proven repair, push its `codex/` branch, then create and push the next annotated non-v semver tag. Never move an existing pushed tag.

## Completion checks

A dry run, a focused test, a completed caller, or a tag is not full-workflow completion. Require all of the following:

1. Controller terminal `RC=0`.
2. Empty workflow Slurm queue and no unexpected terminal failures in accounting.
3. Workflow-released analysis-root write lock.
4. Nonempty final MultiQC HTML and data JSON.
5. Nonempty evidence manifest and final benchmark summary.
6. Inflection package manifest with every declared artifact present.
7. Exact hashes recorded in the durable ledger.
8. Any accepted diagnostic warnings and data gaps stated explicitly rather than replaced with fabricated metrics.

For this proof, the final MultiQC SHA-256 is `a5ba27d9d2207b30b759389fd23b51fc9c269781f1e486abef9240cb94e5af05`, and the final evidence-manifest SHA-256 is `2e49a88de2b4d854c3d10634cbf9bb1ed5ce2913cdcc7237536c59f126a32b3d`.
