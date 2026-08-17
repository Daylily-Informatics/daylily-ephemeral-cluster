# DYEC 18.0.22 pcand-18022 HG002 slim 5x+5x Bjuice and HIOMR2 runbook

Created: 2026-08-17

Control ledger: docs/plans/20260817T064328Z_slim5x5x_bjuice_hiomr2_execution_ledger.md

This is the dedicated record for the requested two catalog lanes:

1. Bjuice with the analytical Inflection package.
2. HIOMR2 with no Inflection package target or delivery-batch binding.

Both use the receipt-bound HG002 slim 5.862704556x Illumina plus
4.794169766x ONT FASTQ fixture on hg38. The selected DayOA tag is 15.0.11,
the highest pinned tag reported by DYEC 18.0.22.

## Mount and input boundary

The selected catalog entries declare requires_run_mount=false. No dyec mounts
create command applies: the exact fixture is already exposed by the reference
DRA. The following commands established that boundary.

~~~zsh
cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate
dyec --help
dyec --json mounts list --profile lsmc --region us-west-2 --cluster pcand-18022
dyec headnode run --profile lsmc --region us-west-2 --cluster pcand-18022 --remote-user ubuntu "test -r /fsx/references/genomic_data/organism_reads_slim/fastq/H_sapiens/giab/bjuice_preval_2026/HG002/illumina/HG002_BJUICEPREVAL_ILMN_5x_R1.fastq.gz && test -r /fsx/references/genomic_data/organism_reads_slim/fastq/H_sapiens/giab/bjuice_preval_2026/HG002/illumina/HG002_BJUICEPREVAL_ILMN_5x_R2.fastq.gz && test -r /fsx/references/genomic_data/organism_reads_slim/fastq/H_sapiens/giab/bjuice_preval_2026/HG002/ont/HG002_BJUICEPREVAL_ONT_5x.fastq.gz && dyec --version && echo slim_fixture_readable"
~~~

Observed: pcand-18022 was UPDATE_COMPLETE, its Ubuntu headnode reported
DYEC 18.0.22, and the three listed FASTQs were readable. The explicit
project/cost-center pair is pcand-18022 / pcand-18022-ccenter.

## Catalog contract

| Lane | Catalog ID | Required distinction |
|---|---|---|
| Bjuice | inflection-bjuice-product-v0.2 | Includes produce_sentdhiomr2_inflection_analytical_package, analytical package mode, and seqone_delivery_batch_id equal to the analysis ID. |
| HIOMR2 | hiomr2_slim_kitchensink_mega | Includes only produce_sentdhiomr2_slim_kitchensink_mega; no package target and no delivery-batch setting. |

The exact catalog scope is hg38 19-20. No full-coverage or alternate-input
override is authorized.

## Initial parallel dry controllers

~~~zsh
source ./activate
dyec --json catalog launch inflection-bjuice-product-v0.2 --analysis-id pcand18022-hg002-slim5x5x-bjuice-ifx-dry-20260817t0648z --executing-entity pcand-18022 --profile lsmc --region us-west-2 --cluster pcand-18022 --git-tag 15.0.11 --manifest-dir /Users/jmajor/.config/daylily/resources/18.0.22/examples/staging/hg002_bjuice_verified_5x5x_fastq --payload-staging-s3-uri s3://lsmc-ssf-sequencing-data/staged_external_data/pcand-18022/pcand18022-hg002-slim5x5x-bjuice-ifx-dry-20260817t0648z/ --remote-user ubuntu --session-name pcand18022-hg002-slim5x5x-bjuice-ifx-dry-20260817t0648z --project pcand-18022 --cost-center pcand-18022-ccenter --export-trigger none --dry-run
dyec --json catalog launch hiomr2_slim_kitchensink_mega --analysis-id pcand18022-hg002-slim5x5x-hiomr2-dry-20260817t0648z --executing-entity pcand-18022 --profile lsmc --region us-west-2 --cluster pcand-18022 --git-tag 15.0.11 --manifest-dir /Users/jmajor/.config/daylily/resources/18.0.22/examples/staging/hg002_bjuice_verified_5x5x_fastq --payload-staging-s3-uri s3://lsmc-ssf-sequencing-data/staged_external_data/pcand-18022/pcand18022-hg002-slim5x5x-hiomr2-dry-20260817t0648z/ --remote-user ubuntu --session-name pcand18022-hg002-slim5x5x-hiomr2-dry-20260817t0648z --project pcand-18022 --cost-center pcand-18022-ccenter --export-trigger none --dry-run
~~~

Both initial dry controllers reached attributable rc=1 before dy-r or Slurm
submission because concurrent dyoainit calls raced while creating the shared
DAYOA environment. No source change, cache deletion, or Slurm action occurred.

## Supported serial bootstrap and dry receipts

The catalog dry-run safeguard excludes dry controllers, so a fresh serial Bjuice
dry controller was used to establish the shared environment. The independently
rendered HIOMR2 dry controller then ran after it.

~~~zsh
source ./activate
dyec --json catalog launch inflection-bjuice-product-v0.2 --analysis-id pcand18022-hg002-slim5x5x-bjuice-ifx-dry2-20260817t0653z --executing-entity pcand-18022 --profile lsmc --region us-west-2 --cluster pcand-18022 --git-tag 15.0.11 --manifest-dir /Users/jmajor/.config/daylily/resources/18.0.22/examples/staging/hg002_bjuice_verified_5x5x_fastq --payload-staging-s3-uri s3://lsmc-ssf-sequencing-data/staged_external_data/pcand-18022/pcand18022-hg002-slim5x5x-bjuice-ifx-dry2-20260817t0653z/ --remote-user ubuntu --session-name pcand18022-hg002-slim5x5x-bjuice-ifx-dry2-20260817t0653z --project pcand-18022 --cost-center pcand-18022-ccenter --export-trigger none --dry-run
dyec --json catalog launch hiomr2_slim_kitchensink_mega --analysis-id pcand18022-hg002-slim5x5x-hiomr2-dry2-20260817t0700z --executing-entity pcand-18022 --profile lsmc --region us-west-2 --cluster pcand-18022 --git-tag 15.0.11 --manifest-dir /Users/jmajor/.config/daylily/resources/18.0.22/examples/staging/hg002_bjuice_verified_5x5x_fastq --payload-staging-s3-uri s3://lsmc-ssf-sequencing-data/staged_external_data/pcand-18022/pcand18022-hg002-slim5x5x-hiomr2-dry2-20260817t0700z/ --remote-user ubuntu --session-name pcand18022-hg002-slim5x5x-hiomr2-dry2-20260817t0700z --project pcand-18022 --cost-center pcand-18022-ccenter --export-trigger none --dry-run
~~~

Both fresh dry controllers reached attributable rc=0 with zero Slurm
submissions. Each used immutable DayOA commit
c113b6140b20a308c78c61bd035dde1bd48e0ed5 for tag 15.0.11.

## Live controllers submitted in parallel

Each was successfully rendered with catalog version 6 before launch. These
commands remove only the dry-run switch; no export trigger or deletion option
is present.

~~~zsh
source ./activate
dyec --json catalog launch inflection-bjuice-product-v0.2 --analysis-id pcand18022-hg002-slim5x5x-bjuice-ifx-20260817t0648z --executing-entity pcand-18022 --profile lsmc --region us-west-2 --cluster pcand-18022 --git-tag 15.0.11 --manifest-dir /Users/jmajor/.config/daylily/resources/18.0.22/examples/staging/hg002_bjuice_verified_5x5x_fastq --payload-staging-s3-uri s3://lsmc-ssf-sequencing-data/staged_external_data/pcand-18022/pcand18022-hg002-slim5x5x-bjuice-ifx-20260817t0648z/ --remote-user ubuntu --session-name pcand18022-hg002-slim5x5x-bjuice-ifx-20260817t0648z --project pcand-18022 --cost-center pcand-18022-ccenter --export-trigger none
dyec --json catalog launch hiomr2_slim_kitchensink_mega --analysis-id pcand18022-hg002-slim5x5x-hiomr2-20260817t0648z --executing-entity pcand-18022 --profile lsmc --region us-west-2 --cluster pcand-18022 --git-tag 15.0.11 --manifest-dir /Users/jmajor/.config/daylily/resources/18.0.22/examples/staging/hg002_bjuice_verified_5x5x_fastq --payload-staging-s3-uri s3://lsmc-ssf-sequencing-data/staged_external_data/pcand-18022/pcand18022-hg002-slim5x5x-hiomr2-20260817t0648z/ --remote-user ubuntu --session-name pcand18022-hg002-slim5x5x-hiomr2-20260817t0648z --project pcand-18022 --cost-center pcand-18022-ccenter --export-trigger none
~~~

The accepted controller roots are:

- /fsx/analysis_results/pcand-18022/pcand18022-hg002-slim5x5x-bjuice-ifx-20260817t0648z
- /fsx/analysis_results/pcand-18022/pcand18022-hg002-slim5x5x-hiomr2-20260817t0648z

## Read-only monitoring

Record the no-lock monitoring visits before direct worktree inspection, then use
the matching DYEC status receipts:

~~~zsh
source ./activate
dyec headnode run --profile lsmc --region us-west-2 --cluster pcand-18022 --remote-user ubuntu "dyec analysis visit --analysis-root /fsx/analysis_results/pcand-18022/pcand18022-hg002-slim5x5x-bjuice-ifx-20260817t0648z --mode monitor --intent 'monitor active Bjuice controller and read its status/log evidence without changing the workflow'"
dyec headnode run --profile lsmc --region us-west-2 --cluster pcand-18022 --remote-user ubuntu "dyec analysis visit --analysis-root /fsx/analysis_results/pcand-18022/pcand18022-hg002-slim5x5x-hiomr2-20260817t0648z --mode monitor --intent 'monitor active no-Inflection HIOMR2 controller and read its status/log evidence without changing the workflow'"
dyec --json workflow status --profile lsmc --region us-west-2 --cluster pcand-18022 --session pcand18022-hg002-slim5x5x-bjuice-ifx-20260817t0648z
dyec --json workflow status --profile lsmc --region us-west-2 --cluster pcand-18022 --session pcand18022-hg002-slim5x5x-hiomr2-20260817t0648z
~~~

The two required monitor visits were recorded. At this point HIOMR2 is
materializing its first-run workflow environments and Bjuice is alive at the
catalog-supported concurrency guard. No Slurm intervention is authorized.

### Initial live progress

At `2026-08-17T07:32Z`, both controllers were attributable, live, and had
begun their DAGs. HIOMR2 reported `3 of 269 steps (1%) done` with four
first-wave jobs running. Bjuice reported `3 of 271 steps (1%) done`, with two
jobs running and two still in Slurm `CONFIGURING` while capacity provisioned.
Neither controller had an attributable terminal exit code or a failure marker,
so no export has been initiated.

At `2026-08-17T07:52Z`, both controllers remained attributable and live.
Bjuice reported `81 of 271 steps (30%) done`, with six jobs running and one
pending; HIOMR2 reported `92 of 269 steps (34%) done`, with three jobs
running. Neither receipt contained a terminal exit code or failure marker.

At `2026-08-17T08:07Z`, Bjuice reported `120 of 271 steps (44%) done`, with
seven jobs running and one configuring; HIOMR2 reported `136 of 269 steps
(51%) done`, with fifteen jobs running. Both controllers remained attributable
and live, without a terminal exit code or failure marker.

At `2026-08-17T08:23Z`, HIOMR2 reported `255 of 269 steps (95%) done` with
two jobs running. Bjuice remained live with 259 recorded finished jobs and one
running Slurm job; its latest controller progress was the submission of
external job `669`. Neither controller had an attributable terminal exit code
or failure marker.

## Bjuice terminal success and no-delete export

At `2026-08-17T08:34Z`, the Bjuice controller reached attributable terminal
`rc=0` (`SUCCEEDED`) from
`/home/ubuntu/daylily-runs/pcand18022-hg002-slim5x5x-bjuice-ifx-20260817t0648z/status.json#exit_code`.
It had no failure markers. Its required export visit was recorded as `ubuntu`,
then DYEC's direct FSx DRA export was started to:

`s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022-hg002-slim5x5x-bjuice-ifx-20260817t0648z/`

The export retains the FSx root; it does not use `--delete-on-export`.

DYEC then wrote an error receipt at `2026-08-17T08:36Z`: `status=error`,
`phase=detach`, association `dra-0288dfcfcdb10e7e0`, `lifecycle=CREATING`,
and `detached=true`. The exact failure was an FSx
`DescribeDataRepositoryAssociations` `HttpTimeoutException` ("Timeout waiting
for reply"). There is no successful export-task or S3-object evidence for this
first attempt.

At `2026-08-17T09:08Z`, the user explicitly authorized one retry only. AWS
then reported the failed association absent, a new export visit was recorded as
`ubuntu`, and exactly one no-delete retry began to the same dedicated Bjuice
prefix. The original failed receipt is retained; the retry writes its receipt
to `docs/runbooks/18.0.22/receipts/pcand18022-hg002-slim5x5x-bjuice-ifx-20260817t0648z/retry1/fsx_export.yaml`.
The retry does not include `--delete-data-in-file-system`. At `2026-08-17T09:11Z`,
it attached DRA `dra-065329a4fceb729fd`; task `task-0a96f7581ba6ddc90`
transitioned from `PENDING` to `EXECUTING`.

The retry receipt then reached `status=success`, `phase=complete`,
`task_lifecycle=SUCCEEDED`, and `detached=true`, with
`delete_data_in_file_system=false`. The DRA detached with lifecycle `DELETED`.
The dedicated S3 prefix was listed and the following exact concordance object
was verified at `82,088` bytes:

`s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022-hg002-slim5x5x-bjuice-ifx-20260817t0648z/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc_data/multiqc_giab_concordance.txt`

The Bjuice FSx root remains retained; no Bjuice deletion is authorized or was
attempted.

## HIOMR2 terminal success and no-delete export

At `2026-08-17T08:36Z`, the no-Inflection HIOMR2 controller reached
attributable terminal `rc=0` (`SUCCEEDED`) from
`/home/ubuntu/daylily-runs/pcand18022-hg002-slim5x5x-hiomr2-20260817t0648z/status.json#exit_code`.
It had no failure markers. Its required export visit was recorded as `ubuntu`,
then DYEC's direct FSx DRA export was started to:

`s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022-hg002-slim5x5x-hiomr2-20260817t0648z/`

This export also retains the FSx root and does not use `--delete-on-export`.
At `2026-08-17T08:39Z`, DYEC attached export DRA `dra-099bf60af970a4503` and
its FSx task `task-07042d644f5dfb3fb` entered `EXECUTING`.

The HIOMR2 receipt then reached `status=success`, `phase=complete`,
`task_lifecycle=SUCCEEDED`, and `detached=true`, with
`delete_data_in_file_system=false`. Its report root is:

`s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022-hg002-slim5x5x-hiomr2-20260817t0648z/_daylily_monitor/fsx-export/20260817T083928Z/export-report/`

The exact 82,088-byte concordance object was also verified at:

`s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022-hg002-slim5x5x-hiomr2-20260817t0648z/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc_data/multiqc_giab_concordance.txt`

At `2026-08-17T09:10Z`, following the user's exact second approval for this
root only, a delete visit and write lock were recorded. The first guard call
was rejected before execution because its required `--intent` argument was
missing. The corrected guard then reported the root absent; a direct read-only
check confirmed that
`/fsx/analysis_results/pcand-18022/pcand18022-hg002-slim5x5x-hiomr2-20260817t0648z`
had already disappeared. Therefore no guarded `rm` from this session ran and
the FSx deletion cannot be attributed here. The corresponding S3 prefix was
confirmed to retain objects after this observation.

### Monitoring cadence

At the user's direction, the task-owned read-only monitor was changed to a
15-minute heartbeat. After the explicit one-time Bjuice retry began, it reads
only that retry receipt, records material terminal state, and stops on terminal
failure or after a terminal result. It does not create/retry any DRA, perform
Slurm intervention, update the catalog, or delete FSx data.

After both exports reached terminal success, the user directed that the
heartbeat be stopped; the scheduled monitor was deleted.

## Catalog concordance evidence

The DYEC command catalog records both verified S3 concordance objects above:

| Catalog command | Attributable rc=0 controller | S3 evidence |
|---|---|---|
| `inflection-bjuice-product-v0.2` | `pcand18022-hg002-slim5x5x-bjuice-ifx-20260817t0648z` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022-hg002-slim5x5x-bjuice-ifx-20260817t0648z/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc_data/multiqc_giab_concordance.txt` |
| `hiomr2_slim_kitchensink_mega` | `pcand18022-hg002-slim5x5x-hiomr2-20260817t0648z` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022-hg002-slim5x5x-hiomr2-20260817t0648z/daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc_data/multiqc_giab_concordance.txt` |

These are historical DayOA `15.0.11` validation records only; neither clears
the catalog's current DayOA `15.0.12` validation-pending state.

## Runtime-cache observation

The runtime-assets DRA is present at
/fsx/references/runtime_assets/cached_envs and contains persisted Conda entries,
but the current cluster-create contract provides an empty generation-scoped
Conda cache under /fsx/resources/environments/conda/ubuntu/pcand-18022-....
This is tracked with no code changes in:

https://github.com/lsmc-bio/daylily-ephemeral-cluster/issues/128

## No-delete export protocol after each live rc=0

Do not export until the matching controller receipt has an attributable rc=0.
First record the export visit on the headnode, then invoke DYEC's DRA export
locally. Replace only <ANALYSIS_ID>.

~~~zsh
# On pcand-18022 as ubuntu:
dyec analysis visit --analysis-root /fsx/analysis_results/pcand-18022/<ANALYSIS_ID> --mode export --intent "export completed pipeline results to s3://lsmc-ssf-sequencing-data/derived/pcand-18022/<ANALYSIS_ID>/ without FSx cleanup" --s3-visit-uri s3://lsmc-ssf-sequencing-data/derived/pcand-18022/<ANALYSIS_ID>/

# Locally:
source ./activate
dyec export --profile lsmc --region us-west-2 --cluster pcand-18022 --source-path /fsx/analysis_results/pcand-18022/<ANALYSIS_ID> --destination-s3-uri s3://lsmc-ssf-sequencing-data/derived/pcand-18022/<ANALYSIS_ID>/ --output-dir docs/runbooks/18.0.22/receipts/<ANALYSIS_ID> --wait --timeout-seconds 5400
~~~

Verify fsx_export.yaml records status=success, phase=complete,
task_lifecycle=SUCCEEDED, and detached=true, then verify expected objects at
the exact destination prefix. This protocol retains the FSx analysis root.

## FSx deletion boundary

The user gave a second exact approval for the HIOMR2 root only; its local FSx
path is now observed absent and its S3 delivery is retained. The Bjuice root
remains retained and no Bjuice deletion is authorized.

## Related Ultima mount cleanup

The completed Ultima Seq QC and solo kitchen-sink receipts were rechecked as
attributable `SUCCEEDED` / `rc=0` before the user gave the exact cleanup scope.
The following approved DRA detach was then run:

~~~zsh
source ./activate
dyec mounts delete --association-id dra-080f12613e5deb4e8 --profile lsmc --region us-west-2 --cluster pcand-18022 --wait
~~~

It returned `Lifecycle: DELETED` for `ultima-604834-20260717`. The local
projection was verified as the exact `84M`, `9,579`-file directory
`/fsx/run_dir_mounts/ultima-604834-20260717/`, with no nested mount. A first
`ubuntu` removal encountered imported-file permission errors; targeted
`sudo rm -rf -- /fsx/run_dir_mounts/ultima-604834-20260717` then removed only
that exact directory. Read-back confirmed `ROOT_ABSENT`; the backing prefix
`s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/RUN604834/2026/604834-20260717_2309/`
still lists objects. No S3 write, delete, or change was made.
