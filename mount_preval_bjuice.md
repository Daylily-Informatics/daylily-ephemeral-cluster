# Bjuice Preval-20 HIOMR2 mount helper

Scope: a new-cluster, **read-only** input-mount contract for a 20-sample
HIOMR2 (`sentdhiomr2`) experiment with full Illumina coverage and the ONT
elapsed-hour interval `[0,25)`. This note does not launch a workflow or create
a new manifest set.

## Required raw-data mounts

| Purpose | Source S3 URI | Required headnode path |
|---|---|---|
| Full Illumina, eight paired lanes for every sample | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/` | `/fsx/run_dir_mounts/20260618_LH01106_0011_A23MFMCLT3/` |
| All Bjuice ONT source cells | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/` | `/fsx/run_dir_mounts/pca100-2026/` |

The ONT parent mount is deliberate: the 20-sample manifest uses every
`20260615_ONT_Set{1..5}-FC{1..3}` child prefix. Mounting only Sets 3--5 covers
the historical 10-sample subset, not all 20 Preval samples.

```bash
source ./activate

dyec mounts create \
  --cluster <new-cluster> --region us-west-2 --profile lsmc \
  --purpose run --read-only \
  --mount-id 20260618_LH01106_0011_A23MFMCLT3 \
  --file-system-path /run_dir_mounts/20260618_LH01106_0011_A23MFMCLT3 \
  --wait --timeout-seconds 3600 \
  s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/

dyec mounts create \
  --cluster <new-cluster> --region us-west-2 --profile lsmc \
  --purpose run --read-only \
  --mount-id pca100-2026 \
  --file-system-path /run_dir_mounts/pca100-2026 \
  --wait --timeout-seconds 3600 \
  s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/
```

`--wait --timeout-seconds 3600` is intentional: a large DRA can remain in
`CREATING` for longer than the normal short timeout. Do not retry or create a
second mount while the first association is still creating.

Verify both mounts on the new cluster before staging manifests:

```bash
dyec mounts verify --cluster <new-cluster> --region us-west-2 --profile lsmc \
  --mount-id 20260618_LH01106_0011_A23MFMCLT3 --timeout-seconds 3600
dyec mounts verify --cluster <new-cluster> --region us-west-2 --profile lsmc \
  --mount-id pca100-2026 --timeout-seconds 3600
```

## Full-coverage and interval contract

- The 20 samples are `HG001`--`HG007`, `NA05067`, `NA10798`, `NA13189`,
  `NA14732`, `NA14733`, `NA15603`, `NA15848`, `NA15849`, `NA19235`,
  `NA20027`, `NA20230`, `NA20775`, and `NA23687`.
- Full Illumina means all `L001`--`L008` R1/R2 pairs: 320 FASTQs total across
  the 20 samples. Keep `SUBSAMPLE_PCT` blank.
- The source manifest contains 8,758 raw ONT FASTQs across the 15 mounted
  cells (`NA20775` has 436; the other samples have 438). The requested ONT
  slice is not a smaller mount; apply it after mounting with:

  ```text
  use_fq_data_starting_hrs=0
  use_fq_data_up_to_hrs=25
  ```

  This is the half-open elapsed-hour range `[0,25)`. Keep
  `ONT_SUBSAMPLE_PCT` blank and confirm the selected file count in the new
  HIOMR2 dry-run rather than assuming the historical 10-sample count applies.

## Manifest and provenance boundaries

The source-backed 20-sample path inventory is retained under:

`docs/plans/20260719T133324Z_majors_bjuiceprevalanalysis_complete_artifacts/manifests/`

Use its `samples.tsv`, `libraries.tsv`, `sequencing_inputs.tsv`,
`analysis_units.tsv`, and `analysis_unit_inputs.tsv` only as the raw-path and
identity basis. Its analysis-unit IDs are explicitly `HIOMRS`; create a new,
explicit HIOMR2 manifest/configuration rather than silently reusing those IDs.
HIOMR2 also requires its explicit `sentdhiomr2` sample/sex/model/scratch
contract and the normal mounted DayOA reference data; this note does not infer
or replace those requirements.

Do **not** use a `derived/` result export or an Inflection/SeqOne delivery
prefix as a source mount for this run. Those are prior output/package evidence,
not the raw ILMN+ONT inputs. In particular, include `NA23687` from the raw
mounts even though a historical Bjuice package was incomplete.

Live read-only S3 checks on 2026-07-26 found the BCLConvert prefix and all
fifteen Set1--Set5 ONT flow-cell prefixes present.
