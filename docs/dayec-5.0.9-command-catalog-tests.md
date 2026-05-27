# DayEC 5.0.9 Goodole3 Command Catalog Tests

Generated: 2026-05-27T16:10:28Z

## Summary

This report records the Goodole3 DayOA command-catalog validation performed on a
DayEC split-bucket cluster in the LSMC account.

The cluster `goodole3` was created in `us-west-2d` with the one-startup-DRA
contract: references mounted at `/fsx/references`. The live sample-analysis
validation used DayOA tag `2.0.6`, exported successful analysis directories to
`s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/<analysis-id>/`,
and requested delete-on-export-success for each workflow launch.

Nine sample-analysis workflows completed and exported successfully. Roche and
hybrid Ultima+ONT remained failed or blocked by upstream runtime/tool issues.
Run-context catalog commands were not represented in the Goodole3 v206 sample
driver.

Current S3 readback for the Goodole3 export root reported `37,183` objects and
`93,999,879,684` bytes under
`s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/`.

## Version And Cluster Context

| Field | Value |
|---|---|
| DayEC repo | `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster` |
| Local branch during report | `codex/running-nextflow-pipes-doc` |
| Local git describe during report | `5.0.9-3-g681a3c88-dirty` |
| Local HEAD during report | `681a3c88b78862569e7b9d0bc93ab043e093ed91` |
| DayEC cluster-create release | `5.0.4` |
| DayEC export/IAM fixes referenced by report | `5.0.8`, `5.0.9` |
| Live headnode DAY-EC package | `5.0.4` |
| Local activated `dyec --json version` during worker readback | `5.0.7.dev0+g104fadf31.d20260527` |
| DayOA workflow tag | `2.0.6` |
| DayOA remote tags during worker readback | Present through `2.0.8`; v206 validation intentionally used `2.0.6` |
| Source catalog DayOA pin at report time | `2.0.5` in source and packaged `daylily_available_repositories.yaml`; v206 launches explicitly overrode this with `--git-tag 2.0.6` |
| Catalog parity | Source and packaged repository catalogs matched; source and packaged global configs matched |
| DayOA clone commit observed in logs | `a073f31c6be04b88cc3f70dcfac77940f54e9282` |
| AWS profile | `lsmc` |
| AWS account | `108782052779` |
| Region / AZ | `us-west-2` / `us-west-2d` |
| Cluster | `goodole3` |
| ParallelCluster version | `3.13.2` |
| Cluster status at readback | `CREATE_COMPLETE` |
| Compute fleet status at readback | `RUNNING` |
| Headnode | `i-0bd631af238bfac56`, `r7i.2xlarge`, private IP `10.0.0.144`, public IP `44.242.81.64` |
| FSx filesystem | `fs-03509c3c3fcf86610` |
| Requested FSx size | `4800` GiB |
| `/fsx` readback | `4.4T` size, `104G` used, `4.3T` available, `3%` used |
| Slurm readback | `squeue` empty at `2026-05-27T16:08:01Z`; all configured partitions idle or idle-pending |
| State file | `/Users/jmajor/.config/daylily/state_goodole3_20260527002251.json` |
| Rendered cluster config | `/Users/jmajor/.config/daylily/goodole3_cluster_20260527002251.yaml` |
| Next-run config | `/Users/jmajor/.config/daylily/goodole3_next_run_20260527002251.yaml` |

Live DRA readback for `fs-03509c3c3fcf86610`:

| FSx path | S3 URI | Lifecycle | Purpose |
|---|---|---|---|
| `/references/` | `s3://lsmc-dayoa-references-usw2` | `AVAILABLE` | Startup references DRA |
| `/staging/staged_external_sequencing_data/remote_stage_20260527T005134Z_24befe61/` | `s3://lsmc-ssf-sequencing-data/staged_external_data/remote_stage_20260527T005134Z_24befe61/` | `AVAILABLE` | Prior on-demand staging DRA |
| `/staging/staged_external_sequencing_data/remote_stage_20260527T005612Z_88ed9201/` | `s3://lsmc-ssf-sequencing-data/staged_external_data/remote_stage_20260527T005612Z_88ed9201/` | `AVAILABLE` | Prior on-demand staging DRA |
| `/staging/staged_external_sequencing_data/remote_stage_20260527T011805Z_f9c19233/` | `s3://lsmc-ssf-sequencing-data/staged_external_data/remote_stage_20260527T011805Z_f9c19233/` | `AVAILABLE` | Prior on-demand staging DRA |
| `/staging/staged_external_sequencing_data/remote_stage_20260527T013344Z_bedd5b66/` | `s3://lsmc-ssf-sequencing-data/staged_external_data/remote_stage_20260527T013344Z_bedd5b66/` | `AVAILABLE` | Prior on-demand staging DRA |

Cluster config values:

| Setting | Value |
|---|---|
| `reference_s3_uri` | `s3://lsmc-dayoa-references-usw2/` |
| `control_data_s3_uri` | `s3://lsmc-dayoa-control-data-usw2/` |
| `stage_s3_uri` | `s3://lsmc-ssf-sequencing-data/staged_external_data/` |
| `budget_email` | `johnm@lsmc.com` |
| `headnode_instance_type` | `r7i.2xlarge` |
| `fsx_fs_size` | `4800` |
| `max_count_8I` | `1` |
| `max_count_128I` | `1` |
| `max_count_192I` | `1` |
| `auto_delete_fsx` | `Delete` |

## Cluster Creation And Readback Commands

Activation:

```bash
cd /Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster
source ./activate
```

Preflight:

```bash
AWS_PROFILE=lsmc dyec preflight \
  --profile lsmc \
  --region-az us-west-2d \
  --config docs/plans/20260526T223700Z_goodole3_cluster_request.yaml \
  --non-interactive
```

Cluster create:

```bash
AWS_PROFILE=lsmc dyec create \
  --profile lsmc \
  --region-az us-west-2d \
  --config docs/plans/20260526T223700Z_goodole3_cluster_request.yaml \
  --non-interactive
```

Cluster and FSx readback:

```bash
AWS_PROFILE=lsmc pcluster describe-cluster \
  --cluster-name goodole3 \
  --region us-west-2

AWS_PROFILE=lsmc aws fsx describe-data-repository-associations \
  --region us-west-2 \
  --filters Name=file-system-id,Values=fs-03509c3c3fcf86610
```

Headnode readback was performed through DayEC SSM helpers as `ubuntu`:

```bash
df -h /fsx
squeue
sinfo
source /home/ubuntu/miniconda3/etc/profile.d/conda.sh
conda activate DAY-EC
python -c 'import daylily_ec; print(daylily_ec.__version__)'
```

## Command Catalog Driver

Driver path:

```text
docs/plans/20260527T020500Z_goodole3_serial_kitchensink_driver.py
```

Evidence paths:

```text
docs/plans/20260527T032100Z_goodole3_serial_kitchensink_v206_runs.jsonl
docs/plans/20260527T032100Z_goodole3_serial_kitchensink_v206_logs/
```

Driver constants:

| Constant | Value |
|---|---|
| `CLUSTER` | `goodole3` |
| `PROFILE` | `lsmc` |
| `REGION` | `us-west-2` |
| `EXECUTING_ENTITY` | `ubuntu` |
| `GIT_TAG` | `2.0.6` |
| `GENOME` | `hg38_broad` |
| `REMOTE_BASE` | `/home/ubuntu/ds/gd3serialksv206` |
| `EXPORT_ROOT` | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu` |
| Initial concurrency | `3` active live workflows |
| Bump policy | allow `4` after first three complete if `/fsx` has at least `1024` GiB free and at most `80%` used |

The launch driver copied pre-generated pass-through `samples.tsv` and
`units.tsv` files to `/home/ubuntu/ds/gd3serialksv206/<analysis-id>/` and then
called `dyec workflow launch`.

## Data Staging Commands

The general external-data staging CLI shape for the Goodole3 cluster is:

```bash
dyec samples stage <manifest.tsv> \
  --reference-s3-uri s3://lsmc-dayoa-references-usw2 \
  --control-data-s3-uri s3://lsmc-dayoa-control-data-usw2 \
  --stage-s3-uri s3://lsmc-ssf-sequencing-data/staged_external_data \
  --stage-target /fsx/staging/staged_external_sequencing_data \
  --config-dir <generated-config-dir> \
  --profile lsmc \
  --region us-west-2 \
  --cluster goodole3 \
  --staging-mount-timeout-seconds <seconds>
```

The v206 sample-analysis driver did not create new staging DRAs for the final
matrix. It reused generated pass-through configs whose paths point at mounted
reference data, then copied those configs to the headnode with the DayEC SSM
helpers:

```python
write_remote_text(
    "i-0bd631af238bfac56",
    "us-west-2",
    "/home/ubuntu/ds/gd3serialksv206/<analysis-id>/a_samples.tsv",
    samples_tsv_text,
    profile="lsmc",
)
write_remote_text(
    "i-0bd631af238bfac56",
    "us-west-2",
    "/home/ubuntu/ds/gd3serialksv206/<analysis-id>/a_units.tsv",
    units_tsv_text,
    profile="lsmc",
)
```

Each remote stage directory was verified before launch:

```bash
test -s /home/ubuntu/ds/gd3serialksv206/<analysis-id>/a_samples.tsv
test -s /home/ubuntu/ds/gd3serialksv206/<analysis-id>/a_units.tsv
```

## Launch And Monitoring Commands

Exact launch shape:

```bash
dyec workflow launch \
  --repository daylily-omics-analysis \
  --analysis-id <analysis-id> \
  --executing-entity ubuntu \
  --git-tag 2.0.6 \
  --genome hg38_broad \
  --dy-command '<bin/day_run command>' \
  --profile lsmc \
  --region us-west-2 \
  --cluster goodole3 \
  --stage-dir /home/ubuntu/ds/gd3serialksv206/<analysis-id> \
  --session-name <analysis-id> \
  --skip-project-check \
  --export-destination-s3-uri s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/<analysis-id>/ \
  --export-trigger on-success \
  --delete-on-export-success
```

The effective `day-clone` command rendered inside the headnode tmux session was:

```bash
day-clone \
  --destination <analysis-id> \
  --executing-entity ubuntu \
  --repository daylily-omics-analysis \
  --git-tag 2.0.6
```

After cloning, DayEC copied the staged config into the clone:

```bash
cp "$STAGE_SAMPLES" config/samples.tsv
cp "$STAGE_UNITS" config/units.tsv
```

Per-run monitoring commands:

```bash
dyec --json workflow status \
  --profile lsmc \
  --region us-west-2 \
  --cluster goodole3 \
  --session <analysis-id>

dyec workflow logs \
  --profile lsmc \
  --region us-west-2 \
  --cluster goodole3 \
  --session <analysis-id> \
  --lines 260

dyec headnode jobs \
  --profile lsmc \
  --region us-west-2 \
  --cluster goodole3
```

Headnode and export monitoring commands used for final readback:

```bash
squeue -o '%i|%P|%C|%t|%N|%m|%M|%j'
df -h /fsx
AWS_PROFILE=lsmc aws s3 ls <export-prefix> --recursive --summarize
```

Final live readback at report generation:

```text
/fsx: 4.4T size, 104G used, 4.3T available, 3% used
squeue: header only, no queued or running jobs
```

## Successful Catalog Commands

The S3 object and byte counts below are over each full exported analysis prefix,
including the cloned DayOA repository, run logs, monitor files, and workflow
results. The feature-specific counts are substring or extension counts within
that exported prefix.

### `illumina_snv_alignstats`

| Field | Value |
|---|---|
| Analysis ID | `gd3v206-ilmnbase5x` |
| Samples TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/illumina_snv_alignstats/20260526T232522Z_18359bf2_samples.tsv` |
| Units TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/illumina_snv_alignstats/20260526T232522Z_18359bf2_units.tsv` |
| Remote stage dir | `/home/ubuntu/ds/gd3serialksv206/gd3v206-ilmnbase5x` |
| `day-clone` | `day-clone --destination gd3v206-ilmnbase5x --executing-entity ubuntu --repository daylily-omics-analysis --git-tag 2.0.6` |
| `bin/day_run` | `bin/day_run produce_sent_align produce_dmd_dedup_cram produce_sentd_snv_vcf produce_snv_concordances produce_alignstats -p -k -j 20` |
| Started / completed | `2026-05-27T05:26:46Z` / `2026-05-27T05:56:09Z` |
| Runtime | 29m23s |
| Exit code | `0` |
| Export task | `task-060b20193f369bb64`, `SUCCEEDED` |
| Export DRA | `dra-03d36b87768d5369a`, detached as `DELETED` |
| Final S3 export | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ilmnbase5x/` |
| S3 stats | `2145` objects, `6,135,243,305` bytes; `2` CRAM, `160` VCF, `35` alignstats matches, `439` concordance matches |

Exact launch command:

```bash
dyec workflow launch --repository daylily-omics-analysis --analysis-id gd3v206-ilmnbase5x --executing-entity ubuntu --git-tag 2.0.6 --genome hg38_broad --dy-command 'bin/day_run produce_sent_align produce_dmd_dedup_cram produce_sentd_snv_vcf produce_snv_concordances produce_alignstats -p -k -j 20' --profile lsmc --region us-west-2 --cluster goodole3 --stage-dir /home/ubuntu/ds/gd3serialksv206/gd3v206-ilmnbase5x --session-name gd3v206-ilmnbase5x --skip-project-check --export-destination-s3-uri s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ilmnbase5x/ --export-trigger on-success --delete-on-export-success
```

### `illumina_snv_alignstats_relatedness_vep_multiqc`

| Field | Value |
|---|---|
| Analysis ID | `gd3v206-ilmn5x` |
| Samples TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/illumina_snv_alignstats_relatedness_vep_multiqc/20260526T232930Z_768f9811_samples.tsv` |
| Units TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/illumina_snv_alignstats_relatedness_vep_multiqc/20260526T232930Z_768f9811_units.tsv` |
| Remote stage dir | `/home/ubuntu/ds/gd3serialksv206/gd3v206-ilmn5x` |
| `day-clone` | `day-clone --destination gd3v206-ilmn5x --executing-entity ubuntu --repository daylily-omics-analysis --git-tag 2.0.6` |
| `bin/day_run` | `bin/day_run produce_sent_align produce_dmd_dedup_cram produce_sentd_snv_vcf produce_alignstats produce_snv_concordances produce_relatedness produce_vep produce_multiqc_all --config 'multiqc_qc={"enable_tools":["vep"]}' -p -j 100 -k` |
| Started / completed | `2026-05-27T03:23:36Z` / `2026-05-27T04:00:16Z` |
| Runtime | 36m40s |
| Exit code | `0` |
| Export task | `task-0f19b0e256839a19a`, `SUCCEEDED` |
| Export DRA | `dra-0903b18856b09cd25`, detached as `DELETED` |
| Final S3 export | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ilmn5x/` |
| S3 stats | `3794` objects, `9,283,078,998` bytes; `2` CRAM, `211` VCF, `37` alignstats matches, `441` concordance matches, `214` MultiQC matches, `474` VEP matches, `69` relatedness matches |

Exact launch command:

```bash
dyec workflow launch --repository daylily-omics-analysis --analysis-id gd3v206-ilmn5x --executing-entity ubuntu --git-tag 2.0.6 --genome hg38_broad --dy-command 'bin/day_run produce_sent_align produce_dmd_dedup_cram produce_sentd_snv_vcf produce_alignstats produce_snv_concordances produce_relatedness produce_vep produce_multiqc_all --config '"'"'multiqc_qc={"enable_tools":["vep"]}'"'"' -p -j 100 -k' --profile lsmc --region us-west-2 --cluster goodole3 --stage-dir /home/ubuntu/ds/gd3serialksv206/gd3v206-ilmn5x --session-name gd3v206-ilmn5x --skip-project-check --export-destination-s3-uri s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ilmn5x/ --export-trigger on-success --delete-on-export-success
```

### `ultima_snv_alignstats`

| Field | Value |
|---|---|
| Analysis ID | `gd3v206-ugbase5x` |
| Samples TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/ultima_snv_alignstats/20260526T233155Z_1a22f74d_samples.tsv` |
| Units TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/ultima_snv_alignstats/20260526T233155Z_1a22f74d_units.tsv` |
| Remote stage dir | `/home/ubuntu/ds/gd3serialksv206/gd3v206-ugbase5x` |
| `day-clone` | `day-clone --destination gd3v206-ugbase5x --executing-entity ubuntu --repository daylily-omics-analysis --git-tag 2.0.6` |
| `bin/day_run` | `bin/day_run produce_alignstats produce_na_dedup_cram produce_sentdug_snv_vcf produce_snv_concordances -p -j 20 -k` |
| Started / completed | `2026-05-27T05:36:29Z` / `2026-05-27T06:15:18Z` |
| Runtime | 38m49s |
| Exit code | `0` |
| Export task | `task-04c27e464d23665ce`, `SUCCEEDED` |
| Export DRA | `dra-05d255adb9754e460`, detached as `DELETED` |
| Final S3 export | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ugbase5x/` |
| S3 stats | `2104` objects, `2,593,534,795` bytes; `2` CRAM, `160` VCF, `27` alignstats matches, `439` concordance matches |

Exact launch command:

```bash
dyec workflow launch --repository daylily-omics-analysis --analysis-id gd3v206-ugbase5x --executing-entity ubuntu --git-tag 2.0.6 --genome hg38_broad --dy-command 'bin/day_run produce_alignstats produce_na_dedup_cram produce_sentdug_snv_vcf produce_snv_concordances -p -j 20 -k' --profile lsmc --region us-west-2 --cluster goodole3 --stage-dir /home/ubuntu/ds/gd3serialksv206/gd3v206-ugbase5x --session-name gd3v206-ugbase5x --skip-project-check --export-destination-s3-uri s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ugbase5x/ --export-trigger on-success --delete-on-export-success
```

### `ultima_snv_alignstats_kitchensink`

| Field | Value |
|---|---|
| Analysis ID | `gd3v206-ug5x` |
| Samples TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/ultima_snv_alignstats_kitchensink/20260526T233423Z_7f724d71_samples.tsv` |
| Units TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/ultima_snv_alignstats_kitchensink/20260526T233423Z_7f724d71_units.tsv` |
| Remote stage dir | `/home/ubuntu/ds/gd3serialksv206/gd3v206-ug5x` |
| `day-clone` | `day-clone --destination gd3v206-ug5x --executing-entity ubuntu --repository daylily-omics-analysis --git-tag 2.0.6` |
| `bin/day_run` | `bin/day_run produce_alignstats produce_na_dedup_cram produce_sentdug_snv_vcf produce_snv_concordances produce_relatedness produce_vep produce_multiqc_all --config 'multiqc_qc={"enable_tools":["vep"]}' -p -j 100 -k` |
| Started / completed | `2026-05-27T04:01:40Z` / `2026-05-27T04:33:52Z` |
| Runtime | 32m12s |
| Exit code | `0` |
| Export task | `task-09ec78aca28507a30`, `SUCCEEDED` |
| Export DRA | `dra-0b277cbee8929b3af`, detached as `DELETED` |
| Final S3 export | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ug5x/` |
| S3 stats | `3266` objects, `5,394,481,804` bytes; `2` CRAM, `211` VCF, `29` alignstats matches, `441` concordance matches, `170` MultiQC matches, `474` VEP matches |

Exact launch command:

```bash
dyec workflow launch --repository daylily-omics-analysis --analysis-id gd3v206-ug5x --executing-entity ubuntu --git-tag 2.0.6 --genome hg38_broad --dy-command 'bin/day_run produce_alignstats produce_na_dedup_cram produce_sentdug_snv_vcf produce_snv_concordances produce_relatedness produce_vep produce_multiqc_all --config '"'"'multiqc_qc={"enable_tools":["vep"]}'"'"' -p -j 100 -k' --profile lsmc --region us-west-2 --cluster goodole3 --stage-dir /home/ubuntu/ds/gd3serialksv206/gd3v206-ug5x --session-name gd3v206-ug5x --skip-project-check --export-destination-s3-uri s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ug5x/ --export-trigger on-success --delete-on-export-success
```

### `ont_snv_alignstats`

| Field | Value |
|---|---|
| Analysis ID | `gd3v206-ontbase5x` |
| Samples TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/ont_snv_alignstats/20260526T233649Z_58971985_samples.tsv` |
| Units TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/ont_snv_alignstats/20260526T233649Z_58971985_units.tsv` |
| Remote stage dir | `/home/ubuntu/ds/gd3serialksv206/gd3v206-ontbase5x` |
| `day-clone` | `day-clone --destination gd3v206-ontbase5x --executing-entity ubuntu --repository daylily-omics-analysis --git-tag 2.0.6` |
| `bin/day_run` | `bin/day_run produce_alignstats produce_sentdont_snv_vcf produce_snv_concordances -p -j 5 -k` |
| Started / completed | `2026-05-27T05:37:18Z` / `2026-05-27T06:47:51Z` |
| Runtime | 1h10m33s |
| Exit code | `0` |
| Export task | `task-01059c18233789a9d`, `SUCCEEDED` |
| Export DRA | `dra-0f8ac4fe1e2fb479b`, detached as `DELETED` |
| Final S3 export | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ontbase5x/` |
| S3 stats | `2086` objects, `2,348,353,425` bytes; `2` CRAM, `161` VCF, `27` alignstats matches, `439` concordance matches |

Exact launch command:

```bash
dyec workflow launch --repository daylily-omics-analysis --analysis-id gd3v206-ontbase5x --executing-entity ubuntu --git-tag 2.0.6 --genome hg38_broad --dy-command 'bin/day_run produce_alignstats produce_sentdont_snv_vcf produce_snv_concordances -p -j 5 -k' --profile lsmc --region us-west-2 --cluster goodole3 --stage-dir /home/ubuntu/ds/gd3serialksv206/gd3v206-ontbase5x --session-name gd3v206-ontbase5x --skip-project-check --export-destination-s3-uri s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ontbase5x/ --export-trigger on-success --delete-on-export-success
```

### `ont_snv_alignstats_kitchensink`

| Field | Value |
|---|---|
| Analysis ID | `gd3v206-ont5x` |
| Samples TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/ont_snv_alignstats_kitchensink/20260526T233916Z_6c2b7b02_samples.tsv` |
| Units TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/ont_snv_alignstats_kitchensink/20260526T233916Z_6c2b7b02_units.tsv` |
| Remote stage dir | `/home/ubuntu/ds/gd3serialksv206/gd3v206-ont5x` |
| `day-clone` | `day-clone --destination gd3v206-ont5x --executing-entity ubuntu --repository daylily-omics-analysis --git-tag 2.0.6` |
| `bin/day_run` | `bin/day_run produce_alignstats produce_sentdont_snv_vcf produce_snv_concordances produce_relatedness produce_vep produce_multiqc_all --config 'multiqc_qc={"enable_tools":["vep"]}' -p -j 5 -k` |
| Started / completed | `2026-05-27T04:38:48Z` / `2026-05-27T05:33:06Z` |
| Runtime | 54m18s |
| Exit code | `0` |
| Export task | `task-0f5b38cfe84d4eda1`, `SUCCEEDED` |
| Export DRA | `dra-05adcb82861873ac6`, detached as `DELETED` |
| Final S3 export | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ont5x/` |
| S3 stats | `3345` objects, `4,981,980,903` bytes; `2` CRAM, `212` VCF, `29` alignstats matches, `441` concordance matches, `167` MultiQC matches, `474` VEP matches |

Exact launch command:

```bash
dyec workflow launch --repository daylily-omics-analysis --analysis-id gd3v206-ont5x --executing-entity ubuntu --git-tag 2.0.6 --genome hg38_broad --dy-command 'bin/day_run produce_alignstats produce_sentdont_snv_vcf produce_snv_concordances produce_relatedness produce_vep produce_multiqc_all --config '"'"'multiqc_qc={"enable_tools":["vep"]}'"'"' -p -j 5 -k' --profile lsmc --region us-west-2 --cluster goodole3 --stage-dir /home/ubuntu/ds/gd3serialksv206/gd3v206-ont5x --session-name gd3v206-ont5x --skip-project-check --export-destination-s3-uri s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ont5x/ --export-trigger on-success --delete-on-export-success
```

### `pacbio_snv_alignstats`

| Field | Value |
|---|---|
| Analysis ID | `gd3v206-pbbase5x` |
| Samples TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/pacbio_snv_alignstats/20260526T234141Z_53f941a8_samples.tsv` |
| Units TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/pacbio_snv_alignstats/20260526T234141Z_53f941a8_units.tsv` |
| Remote stage dir | `/home/ubuntu/ds/gd3serialksv206/gd3v206-pbbase5x` |
| `day-clone` | `day-clone --destination gd3v206-pbbase5x --executing-entity ubuntu --repository daylily-omics-analysis --git-tag 2.0.6` |
| `bin/day_run` | `bin/day_run produce_sentmm2_align produce_na_dedup_cram produce_sentdpb_snv_vcf produce_alignstats produce_snv_concordances -p -j 2 -k -T 1` |
| Started / completed | `2026-05-27T05:58:26Z` / `2026-05-27T07:40:50Z` |
| Runtime | 1h42m24s |
| Exit code | `0` |
| Export task | `task-033a4a26c1ffac67f`, `SUCCEEDED` |
| Export DRA | `dra-0a37e82a8050f85d6`, detached as `DELETED` |
| Final S3 export | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-pbbase5x/` |
| S3 stats | `2088` objects, `4,306,320,965` bytes; `2` CRAM, `161` VCF, `27` alignstats matches, `439` concordance matches |

Exact launch command:

```bash
dyec workflow launch --repository daylily-omics-analysis --analysis-id gd3v206-pbbase5x --executing-entity ubuntu --git-tag 2.0.6 --genome hg38_broad --dy-command 'bin/day_run produce_sentmm2_align produce_na_dedup_cram produce_sentdpb_snv_vcf produce_alignstats produce_snv_concordances -p -j 2 -k -T 1' --profile lsmc --region us-west-2 --cluster goodole3 --stage-dir /home/ubuntu/ds/gd3serialksv206/gd3v206-pbbase5x --session-name gd3v206-pbbase5x --skip-project-check --export-destination-s3-uri s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-pbbase5x/ --export-trigger on-success --delete-on-export-success
```

### `hybrid_ilmn_ont_snv`

| Field | Value |
|---|---|
| Analysis ID | `gd3v206-hiobase5x` |
| Samples TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/hybrid_ilmn_ont_snv/20260526T234631Z_e9e804ff_samples.tsv` |
| Units TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/hybrid_ilmn_ont_snv/20260526T234631Z_e9e804ff_units.tsv` |
| Remote stage dir | `/home/ubuntu/ds/gd3serialksv206/gd3v206-hiobase5x` |
| `day-clone` | `day-clone --destination gd3v206-hiobase5x --executing-entity ubuntu --repository daylily-omics-analysis --git-tag 2.0.6` |
| `bin/day_run` | `bin/day_run produce_snv_concordances produce_sentdhiomr_sv produce_sentdhiomr_snv_vcf --config 'dedupers=["dmd"]' -p -j 100 -k` |
| Started / completed | `2026-05-27T06:50:42Z` / `2026-05-27T09:47:30Z` |
| Runtime | 2h56m48s |
| Exit code | `0` |
| Export task | `task-00d2cfdff8779a04f`, `SUCCEEDED` |
| Export DRA | `dra-0f8d5de1c2c892c88`, detached as `DELETED` |
| Final S3 export | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-hiobase5x/` |
| S3 stats | `6415` objects, `22,393,495,692` bytes; `1` CRAM, `2` BAM, `180` VCF, `11` alignstats matches, `439` concordance matches |

Exact launch command:

```bash
dyec workflow launch --repository daylily-omics-analysis --analysis-id gd3v206-hiobase5x --executing-entity ubuntu --git-tag 2.0.6 --genome hg38_broad --dy-command 'bin/day_run produce_snv_concordances produce_sentdhiomr_sv produce_sentdhiomr_snv_vcf --config '"'"'dedupers=["dmd"]'"'"' -p -j 100 -k' --profile lsmc --region us-west-2 --cluster goodole3 --stage-dir /home/ubuntu/ds/gd3serialksv206/gd3v206-hiobase5x --session-name gd3v206-hiobase5x --skip-project-check --export-destination-s3-uri s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-hiobase5x/ --export-trigger on-success --delete-on-export-success
```

### `hybrid_ilmn_ont_snv_kitchensink`

| Field | Value |
|---|---|
| Analysis ID | `gd3v206-hio5x` |
| Samples TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/hybrid_ilmn_ont_snv_kitchensink/20260526T234857Z_77cd0b7a_samples.tsv` |
| Units TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/hybrid_ilmn_ont_snv_kitchensink/20260526T234857Z_77cd0b7a_units.tsv` |
| Remote stage dir | `/home/ubuntu/ds/gd3serialksv206/gd3v206-hio5x` |
| `day-clone` | `day-clone --destination gd3v206-hio5x --executing-entity ubuntu --repository daylily-omics-analysis --git-tag 2.0.6` |
| `bin/day_run` | `bin/day_run produce_snv_concordances produce_sentdhiomr_sv produce_sentdhiomr_snv_vcf produce_relatedness produce_vep produce_multiqc_all --config 'dedupers=["dmd"]' 'multiqc_qc={"enable_tools":["vep"]}' -p -j 100 -k` |
| Started / completed | `2026-05-27T05:21:44Z` / `2026-05-27T08:51:26Z` |
| Runtime | 3h29m42s |
| Exit code | `0` |
| Export task | `task-0dc9b577e86f6ac65`, `SUCCEEDED` |
| Export DRA | `dra-001287a7f6f4ec634`, detached as `DELETED` |
| Final S3 export | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-hio5x/` |
| S3 stats | `8130` objects, `27,276,240,588` bytes; `3` CRAM, `2` BAM, `231` VCF, `37` alignstats matches, `441` concordance matches, `207` MultiQC matches, `472` VEP matches, `69` relatedness matches |

Exact launch command:

```bash
dyec workflow launch --repository daylily-omics-analysis --analysis-id gd3v206-hio5x --executing-entity ubuntu --git-tag 2.0.6 --genome hg38_broad --dy-command 'bin/day_run produce_snv_concordances produce_sentdhiomr_sv produce_sentdhiomr_snv_vcf produce_relatedness produce_vep produce_multiqc_all --config '"'"'dedupers=["dmd"]'"'"' '"'"'multiqc_qc={"enable_tools":["vep"]}'"'"' -p -j 100 -k' --profile lsmc --region us-west-2 --cluster goodole3 --stage-dir /home/ubuntu/ds/gd3serialksv206/gd3v206-hio5x --session-name gd3v206-hio5x --skip-project-check --export-destination-s3-uri s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-hio5x/ --export-trigger on-success --delete-on-export-success
```

## Failed Or Blocked Commands

### `roche_snv_alignstats`, first attempt

| Field | Value |
|---|---|
| Analysis ID | `gd3v206-rcbase5x` |
| Samples TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/roche_snv_alignstats/20260526T234406Z_7b96a4d4_samples.tsv` |
| Units TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/roche_snv_alignstats/20260526T234406Z_7b96a4d4_units.tsv` |
| Remote stage dir | `/home/ubuntu/ds/gd3serialksv206/gd3v206-rcbase5x` |
| `day-clone` | `day-clone --destination gd3v206-rcbase5x --executing-entity ubuntu --repository daylily-omics-analysis --git-tag 2.0.6` |
| `bin/day_run` | `bin/day_run produce_alignstats produce_na_dedup_cram produce_rochehc_snv_vcf -p -j 5 -k` |
| Started / completed | `2026-05-27T06:17:21Z` / `2026-05-27T06:38:51Z` |
| Exit code | `1` |
| Requested S3 export | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-rcbase5x/` |
| S3 stats | `0` objects, `0` bytes; export did not run because workflow failed |

Failure summary: Roche failed before successful image materialization. The first
attempt was reported as a cache/temp/container setup failure around the Roche
container path.

Exact launch command:

```bash
dyec workflow launch --repository daylily-omics-analysis --analysis-id gd3v206-rcbase5x --executing-entity ubuntu --git-tag 2.0.6 --genome hg38_broad --dy-command 'bin/day_run produce_alignstats produce_na_dedup_cram produce_rochehc_snv_vcf -p -j 5 -k' --profile lsmc --region us-west-2 --cluster goodole3 --stage-dir /home/ubuntu/ds/gd3serialksv206/gd3v206-rcbase5x --session-name gd3v206-rcbase5x --skip-project-check --export-destination-s3-uri s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-rcbase5x/ --export-trigger on-success --delete-on-export-success
```

### `roche_snv_alignstats`, retry with writable cache

| Field | Value |
|---|---|
| Analysis ID | `gd3v206-rcbase5xr1` |
| Samples TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/roche_snv_alignstats/20260526T234406Z_7b96a4d4_samples.tsv` |
| Units TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/roche_snv_alignstats/20260526T234406Z_7b96a4d4_units.tsv` |
| Remote stage dir | `/home/ubuntu/ds/gd3serialksv206/gd3v206-rcbase5xr1` |
| `day-clone` | `day-clone --destination gd3v206-rcbase5xr1 --executing-entity ubuntu --repository daylily-omics-analysis --git-tag 2.0.6` |
| `bin/day_run` | `mkdir -p /fsx/tmp/apptainer_cache/ubuntu/${HOSTNAME}/containers/gd3v206-rcbase5xr1 /fsx/scratch/dayoa_apptainer_tmp/ubuntu/gd3v206-rcbase5xr1 && export APPTAINER_CACHEDIR=/fsx/tmp/apptainer_cache/ubuntu/${HOSTNAME} SINGULARITY_CACHEDIR=/fsx/tmp/apptainer_cache/ubuntu/${HOSTNAME} APPTAINER_TMPDIR=/fsx/scratch/dayoa_apptainer_tmp/ubuntu/gd3v206-rcbase5xr1 SINGULARITY_TMPDIR=/fsx/scratch/dayoa_apptainer_tmp/ubuntu/gd3v206-rcbase5xr1 && bin/day_run produce_alignstats produce_na_dedup_cram produce_rochehc_snv_vcf -p -j 5 -k --singularity-prefix /fsx/tmp/apptainer_cache/ubuntu/${HOSTNAME}/containers/gd3v206-rcbase5xr1` |
| Started / completed | `2026-05-27T06:45:57Z` / `2026-05-27T06:46:20Z` |
| Exit code | `1` |
| Requested S3 export | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-rcbase5xr1/` |
| S3 stats | `0` objects, `0` bytes; export did not run because workflow failed |

Failure summary: the retry got past the writable-cache setup and then failed
because the Roche image is private or unavailable:

```text
Failed to pull singularity image from docker://roche/sbxd-small-variant-caller:latest
requested access to the resource is denied
```

### `hybrid_ultima_ont_snv`, first attempt

| Field | Value |
|---|---|
| Analysis ID | `gd3v206-huobase5x` |
| Samples TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/hybrid_ultima_ont_snv/20260526T235123Z_54761b1c_samples.tsv` |
| Units TSV | `docs/plans/20260526T224018Z_blahab44_inputs/generated/hybrid_ultima_ont_snv/20260526T235123Z_54761b1c_units.tsv` |
| Remote stage dir | `/home/ubuntu/ds/gd3serialksv206/gd3v206-huobase5x` |
| `day-clone` | `day-clone --destination gd3v206-huobase5x --executing-entity ubuntu --repository daylily-omics-analysis --git-tag 2.0.6` |
| `bin/day_run` | `bin/day_run produce_sentdhuomr_snv_vcf produce_alignstats produce_snv_concordances -p -j 100 -k` |
| Started / completed | `2026-05-27T06:51:31Z` / `2026-05-27T08:15:55Z` |
| Exit code | `1` |
| Requested S3 export | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-huobase5x/` |
| S3 stats | `0` objects, `0` bytes; export did not run because workflow failed |

Failure summary: Sentieon HybridStage1 failed and produced a truncated
`stage1_hap.bam`. The live triage identified an internal assertion around
`ReadSequenceKmerGraphBuilder.h:101: kmerSize >= 1`.

Exact launch command:

```bash
dyec workflow launch --repository daylily-omics-analysis --analysis-id gd3v206-huobase5x --executing-entity ubuntu --git-tag 2.0.6 --genome hg38_broad --dy-command 'bin/day_run produce_sentdhuomr_snv_vcf produce_alignstats produce_snv_concordances -p -j 100 -k' --profile lsmc --region us-west-2 --cluster goodole3 --stage-dir /home/ubuntu/ds/gd3serialksv206/gd3v206-huobase5x --session-name gd3v206-huobase5x --skip-project-check --export-destination-s3-uri s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-huobase5x/ --export-trigger on-success --delete-on-export-success
```

### `hybrid_ultima_ont_snv`, retry with patched threads

| Field | Value |
|---|---|
| Analysis ID | `gd3v206-huobase5xr1` |
| Remote run script | `/home/ubuntu/ds/gd3serialksv206/gd3v206-huobase5xr1_patch_and_run.sh` |
| Started / completed | `2026-05-27T08:23:01Z` / `2026-05-27T09:18:42Z` |
| Exit code | `1` |
| Requested S3 export | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-huobase5xr1/` |
| S3 stats | `0` objects, `0` bytes; export did not run because workflow failed |

Failure summary: the retry patched run-local `sentdhuomr.threads=128` and
`sentdhuomr.use_threads=120`, but still failed. Live evidence showed Sentieon
license-server connection failures or refused connections, the same internal
HybridStage1 assertion, and the missing EOF block on `stage1_hap.bam`.

### Commands Not Represented In The v206 Goodole3 Driver

The v206 Goodole3 driver was a sample-analysis kitchen-sink/base matrix using
pass-through slim GIAB reads under `/fsx/references/genomic_data/organism_reads_slim`.
It did not include the run-analysis command family or the unresolved CG/MGI
candidate.

| Command ID | Catalog `bin/day_run` command | Status in this report | Reason |
|---|---|---|---|
| `complete_genomics_mgi_snv_concordance` | `bin/day_run produce_sentcg_align produce_dmd_dedup_cram produce_cgt7p_snv_vcf produce_alignstats produce_snv_concordances -p -j 20 -k -T 1 --retries 0 --rerun-incomplete --keep-incomplete` | Not run | Valid CG/MGI mate-pair input was not verified; prior evidence showed inconsistent candidate mate sizes, and no silent substitution was authorized. |
| `illumina_run_qc` | `bin/day_run produce_illumina_run_qc -p -j 5 -k` | Not run in v206 | Run-context commands were outside the v206 sample-analysis driver. |
| `illumina_bclconvert` | `bin/day_run produce_bclconvert_fastqs_and_metrics -p -j 20 -k` | Not run in v206 | Run-context commands were outside the v206 sample-analysis driver. |
| `illumina_run_qc_bclconvert` | `bin/day_run produce_illumina_run_qc_and_bclconvert -p -j 20 -k` | Not run in v206 | Run-context commands were outside the v206 sample-analysis driver. |
| `ont_run_qc` | `bin/day_run produce_ont_run_qc_and_demux_multiqc -p -j 5 -k` | Not run in v206 | Run-context commands were outside the v206 sample-analysis driver. |
| `ultima_run_qc` | `bin/day_run produce_ultima_run_qc -p -j 5 -k` | Not run in v206 | Run-context commands were outside the v206 sample-analysis driver. |

## Exports And Cleanup

Every successful v206 workflow launch included:

```bash
--export-trigger on-success
--delete-on-export-success
```

The live export receipts all reported:

```yaml
status: success
phase: complete
detached: true
task_lifecycle: SUCCEEDED
detach_lifecycle: DELETED
delete_data_in_file_system: false
```

`delete_data_in_file_system` is the FSx DRA detach option from the export task,
not the DayEC workflow launch flag. The workflow launches requested
`--delete-on-export-success`; the export DRAs themselves were detached without
using FSx `DeleteDataInFileSystem`.

Successful export destinations:

| Analysis ID | Final S3 URI | Objects | Bytes |
|---|---|---:|---:|
| `gd3v206-ilmnbase5x` | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ilmnbase5x/` | `2,145` | `6,135,243,305` |
| `gd3v206-ilmn5x` | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ilmn5x/` | `3,794` | `9,283,078,998` |
| `gd3v206-ugbase5x` | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ugbase5x/` | `2,104` | `2,593,534,795` |
| `gd3v206-ug5x` | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ug5x/` | `3,266` | `5,394,481,804` |
| `gd3v206-ontbase5x` | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ontbase5x/` | `2,086` | `2,348,353,425` |
| `gd3v206-ont5x` | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-ont5x/` | `3,345` | `4,981,980,903` |
| `gd3v206-pbbase5x` | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-pbbase5x/` | `2,088` | `4,306,320,965` |
| `gd3v206-hiobase5x` | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-hiobase5x/` | `6,415` | `22,393,495,692` |
| `gd3v206-hio5x` | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-hio5x/` | `8,130` | `27,276,240,588` |

Failed or blocked export destinations:

| Analysis ID | Requested S3 URI | Objects | Bytes |
|---|---|---:|---:|
| `gd3v206-rcbase5x` | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-rcbase5x/` | `0` | `0` |
| `gd3v206-rcbase5xr1` | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-rcbase5xr1/` | `0` | `0` |
| `gd3v206-huobase5x` | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-huobase5x/` | `0` | `0` |
| `gd3v206-huobase5xr1` | `s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/gd3v206-huobase5xr1/` | `0` | `0` |

No cluster teardown, bucket deletion, prefix deletion, or destructive AWS cleanup
is recorded in this report. The final live readback had an empty Slurm queue and
the cluster still running.

## Remaining Blockers

| Command | Blocker | Required next action |
|---|---|---|
| `roche_snv_alignstats` | First run hit Apptainer temp/cache permission failure; retry with writable FSx cache then hit Docker access denial for `docker://roche/sbxd-small-variant-caller:latest`. | Provide an authorized Roche container image or approved mirror, then rerun the Roche row. |
| `hybrid_ultima_ont_snv` | First run and thread-reduced retry both failed in Sentieon HybridStage1. Evidence included `ReadSequenceKmerGraphBuilder.h:101` assertion, refused license-server connections during retry, and truncated `stage1_hap.bam` missing EOF. | Stabilize Sentieon licensing on the cluster, then isolate/vendor-triage the HybridStage1 assertion on the Ultima+ONT input. |
| `complete_genomics_mgi_snv_concordance` | Candidate mate pair was not credible: `_386_1` was `90,600,002,744` bytes while `_386_2` was `10,794,018,984` bytes; nearby `_388_2` was `97,844,317,264` bytes but was not an authorized substitute. | Obtain a verified CG/MGI mate pair and rerun this catalog row. |
| Run-context rows | `illumina_run_qc`, `illumina_bclconvert`, `illumina_run_qc_bclconvert`, `ont_run_qc`, and `ultima_run_qc` were outside the v206 sample-analysis driver. | Run a separate Goodole3 run-context validation with explicit mounted run directories and per-command samples/units. |

## Verification Commands For This Report

The report was assembled from the live readbacks and artifacts above. The
non-mutating verification commands were:

```bash
git status --short --branch
git describe --tags --dirty --always

AWS_PROFILE=lsmc pcluster describe-cluster \
  --cluster-name goodole3 \
  --region us-west-2

AWS_PROFILE=lsmc aws fsx describe-data-repository-associations \
  --region us-west-2 \
  --filters Name=file-system-id,Values=fs-03509c3c3fcf86610

AWS_PROFILE=lsmc aws s3 ls \
  s3://lsmc-dayoa-analysis-results-usw2/validation/goodole3/ubuntu/ \
  --recursive \
  --summarize
```

Headnode evidence was read through `daylily_ec.aws.ssm.run_shell` as `ubuntu`,
not by ad hoc root SSM commands.
