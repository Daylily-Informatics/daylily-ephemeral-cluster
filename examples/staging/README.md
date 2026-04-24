# Staging Example Manifests

These examples are staging inputs for `daylily-ec samples stage`. Each
`analysis_samples_manifest.tsv` is derived from a working
`daylily-omics-analysis` fixture and rewrites source data to the mk-gotime3
reference bucket:

`s3://lsmc-dayoa-omics-analysis-us-west-2/data/...`

Every row uses `STAGE_DIRECTIVE=stage_data`, so raw reads, aligned artifacts,
and concordance data are copied into the timestamped remote stage before the
generated `samples.tsv` and `units.tsv` point at FSx paths.

Run commands from the repository root:

```bash
daylily-ec samples stage examples/staging/ilmn_solo/analysis_samples_manifest.tsv \
  --profile lsmc \
  --region us-west-2 \
  --reference-bucket s3://lsmc-dayoa-omics-analysis-us-west-2 \
  --config-dir tmp-stage-config/examples/ilmn_solo
```

```bash
daylily-ec samples stage examples/staging/ultima_solo/analysis_samples_manifest.tsv \
  --profile lsmc \
  --region us-west-2 \
  --reference-bucket s3://lsmc-dayoa-omics-analysis-us-west-2 \
  --config-dir tmp-stage-config/examples/ultima_solo
```

```bash
daylily-ec samples stage examples/staging/ont_solo/analysis_samples_manifest.tsv \
  --profile lsmc \
  --region us-west-2 \
  --reference-bucket s3://lsmc-dayoa-omics-analysis-us-west-2 \
  --config-dir tmp-stage-config/examples/ont_solo
```

```bash
daylily-ec samples stage examples/staging/hybrid_ilmn_ont/analysis_samples_manifest.tsv \
  --profile lsmc \
  --region us-west-2 \
  --reference-bucket s3://lsmc-dayoa-omics-analysis-us-west-2 \
  --config-dir tmp-stage-config/examples/hybrid_ilmn_ont
```

```bash
daylily-ec samples stage examples/staging/pacbio_solo/analysis_samples_manifest.tsv \
  --profile lsmc \
  --region us-west-2 \
  --reference-bucket s3://lsmc-dayoa-omics-analysis-us-west-2 \
  --config-dir tmp-stage-config/examples/pacbio_solo
```

```bash
daylily-ec samples stage examples/staging/roche_solo/analysis_samples_manifest.tsv \
  --profile lsmc \
  --region us-west-2 \
  --reference-bucket s3://lsmc-dayoa-omics-analysis-us-west-2 \
  --config-dir tmp-stage-config/examples/roche_solo
```

After staging, pass the exact printed `Remote FSx stage directory` to workflow
launch:

```bash
daylily-ec workflow launch --stage-dir <printed-remote-fsx-stage-directory>
```

Automated tests parse and mock-stage these examples. They do not copy live S3
data.

Optional live tests can stage every example on `mk-gotime3` and then validate
workflow consumption with dry-run launches. These tests are skipped unless the
live flag is passed:

```bash
pytest tests/test_staging_examples_live.py --run-live-staging-examples \
  --live-staging-profile daylily-service-lsmc \
  --live-staging-region us-west-2 \
  --live-staging-cluster mk-gotime3
```

To run full workflows instead of dry-runs, pass the explicit non-dry-run flag:

```bash
pytest tests/test_staging_examples_live.py --run-live-staging-examples \
  --live-staging-profile daylily-service-lsmc \
  --live-staging-region us-west-2 \
  --live-staging-cluster mk-gotime3 \
  --live-staging-non-dryrun \
  --live-staging-workflow-timeout-minutes 240
```

Live test evidence is written under
`tmp-stage-config/live-staging-examples/<run-id>/<analysis-type>/`. The tests
create staged data and workflow sessions; they do not delete or teardown AWS
resources.
