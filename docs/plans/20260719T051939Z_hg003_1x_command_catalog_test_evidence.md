# HG003 1x Command-Catalog Test Evidence

Generated: `2026-07-19T05:19:39Z`

Scope: DYEC command-catalog support for the released DayOA `13.0.1` HG003
HIOMRS 1x fixture. The two HG003 validation recipes stage the exact six-file
fixture. Production and customer-delivery recipes remain operator-manifest
driven and do not inherit test identities.

## Fixture contract

- 1 specimen, 1 sample, 1 physical library.
- Exact paired Illumina inputs:
  - `/fsx/references/genomic_data/organism_reads_slim/fastq/H_sapiens/giab/NovaSeqX_WHGS_TruSeqPF_HG002-007/downsampled/HG003_1x_R1.fastq.gz`
  - `/fsx/references/genomic_data/organism_reads_slim/fastq/H_sapiens/giab/NovaSeqX_WHGS_TruSeqPF_HG002-007/downsampled/HG003_1x_R2.fastq.gz`
- Exact primary-only ONT input:
  - `/fsx/references/genomic_data/organism_reads_slim/fastq/H_sapiens/giab/agbt_2026/ont/HG003_1x.cleaned.primary.fastq.gz`
- 4 analysis attempts and 8 ordered analysis-input links.
- Attempts 1-3 use full-depth inputs. Attempt 4 uses the existing
  `SUBSAMPLE_PCT=0.9` and `ONT_SUBSAMPLE_PCT=0.85` controls.
- Test EUIDs use the reserved `Z-` prefix.
- All six packaged TSVs are byte-identical to DayOA 13.0.1
  `.test_data/examples/slim-data/hg003-hiomrs-1x/`.

## Immutable hashes

```text
99ce482d1e428b3c0752bcb3413715a4ee2ef09b846269170b6341c0b414e997  analysis_unit_inputs.tsv
b5476fd47667e4e5ea97343f4cc4c4a07cc236bed1707c0b7c44d926986962da  analysis_units.tsv
071c714e0c4c36a1e25e2676c311b6ef3e1cd286eb1854ab2b7407f143eb934a  libraries.tsv
bc36cebf72b35e5c750b4ea44ccb2feb25e53b7da7d3685505cda1b0ee07e492  samples.tsv
88e65c993f2d5a1c15e1fa52643995d68f0c625225dbc6f06d9b1d6b59e92c7d  sequencing_inputs.tsv
60ba3d599d33e2de330183015796d111b9e1a31eaafd6ea7136e6f6f224b4939  specimens.tsv
```

The source and packaged catalog copies are byte-identical with SHA-256
`9b063d4ea45921f2f101168c931c6a15b451aada850ec245845de75d7556f885`.

## Test results

- Focused catalog/runner/schema suite: `90 passed in 3.14s`.
- Full DYEC suite: `2230 passed, 11 skipped in 82.24s`.
- Ruff on every changed Python/test module: pass.
- `python -m compileall -q daylily_ec`: pass.
- `python -m pip wheel . --no-deps`: pass.
- `git diff --check`: pass.

`python -m build` was unavailable because the active environment does not
install the `build` module's CLI entry point. No dependency was added; the
equivalent isolated PEP 517 wheel build through `pip wheel` completed
successfully.

No workflow, tmux controller, or Slurm job was launched by this validation.
