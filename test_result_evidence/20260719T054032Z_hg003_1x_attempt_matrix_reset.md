# HG003 1x HIOMRS packaged-fixture matrix reset

Generated: `2026-07-19T05:40:32Z`

The packaged `hg003_hiomrs_1x_raw_fastq` command-catalog fixture now stages
four analysis attempts over the same exact paired Illumina and ONT FASTQ
inputs: two full-depth attempts, one `0.90` SR/ONT attempt, and one `0.75`
SR/ONT attempt. It retains one specimen, one sample, one physical library, two
sequencing inputs, four analysis units, and eight ordered input links.

Validation evidence:

- Focused DYEC catalog/staging tests: `32 passed`.
- Full DYEC suite: `2230 passed, 11 skipped in 82.53s`.
- Ruff and `git diff --check`: pass.
- All six packaged manifest files are byte-identical to the DayOA source
  fixture.
- `analysis_units.tsv` SHA-256:
  `896fea5a94ae55f3a3627b8711a778a5158e6c5b83000021c8520d81cb0fe720`.
- `analysis_unit_inputs.tsv` SHA-256:
  `1e07a045c166ce9aeae82516d1698562e1dd33eb6b220ff06d3f0fb467f13ea7`.

This evidence covers packaged fixtures and local tests only. No headnode was
modified, no controller was started, and no live analysis root was changed.
