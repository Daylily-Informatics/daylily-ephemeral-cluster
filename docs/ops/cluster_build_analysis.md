# `pcand-18022` cluster build analysis

## Outcome

The `pcand-18022` Intel cluster in `us-west-2c` completed the full `dyec create`
workflow in **42m 32s (2,552.2 seconds)**. This is the end-to-end command
duration reported after the headnode configuration, heartbeat, state snapshot,
and Slurm-accounting steps succeeded.

The ParallelCluster creation operation itself took **9m 22s** from submission to
`CREATE_COMPLETE`. It should not be used as the end-to-end build duration,
because it excludes the prerequisite storage, preflight, rendering, and
post-create configuration work.

## Timed build segments

| Segment | Observed duration | Share of total | Evidence boundary |
| --- | ---: | ---: | --- |
| PERSISTENT_2 FSx creation | 6m 45s (405s) | 15.9% | FSx create submitted to `AVAILABLE` |
| Reference data-repository association (DRA) creation | 10m 15s (615s) | 24.1% | DRA create submitted to `AVAILABLE` |
| Storage lifecycle waits, sequential total | 17m 00s (1,020s) | 40.0% | Sum of the two explicit AWS lifecycle waits |
| ParallelCluster creation | 9m 22s (562s) | 22.0% | Cluster create submitted to `CREATE_COMPLETE` |
| Other `dyec create` activity, not separately timed | about 16m 10s (970.2s) | 38.0% | Remainder after the explicit waits and ParallelCluster creation |

The remaining approximately 16 minutes covers the observed but individually
untimed phases: input/preflight handling, baseline CloudFormation readiness,
resource resolution, boot-config publication, budgets and cost-center setup,
YAML and spot-price rendering, dry-run validation, headnode SSM registration
and configuration, heartbeat setup, state capture, and Slurm accounting. The
terminal transcript does not provide a defensible per-step allocation within
that remainder.

## Cluster record

| Field | Value |
| --- | --- |
| Cluster | `pcand-18022` |
| DYEC run ID | `20260817054650` |
| DYEC ref | `18.0.22` |
| Cluster type | `intel` |
| Region / Availability Zone | `us-west-2` / `us-west-2c` |
| AWS account | `108782052779` |
| Headnode | `r7i.4xlarge`; observed SSM target `i-07c38ac3548d7f4c4` |
| FSx | `fs-09eb220d064d55d92`, `PERSISTENT_2`, 12,000 GiB, 500 MB/s/TiB, SSD, Lustre 2.15 |
| FSx lifecycle | DYEC-owned, cluster-bound, automatic metadata import |
| FSx client security group | `sg-0810b4602390d4c6d` |
| Reference DRA | `dra-0adba8261208342cd`, associating the reference bucket under `/references/` |
| Reference / control-data S3 | `s3://lsmc-dayoa-references-usw2/` / `s3://lsmc-dayoa-control-data-usw2/` |
| Staging / export S3 | `s3://lsmc-ssf-sequencing-data/staged_external_data/` / `s3://lsmc-ssf-sequencing-data/derived/` |
| Project cost center | `pcand-18022-ccenter`; monthly cap `$1,234` |
| Global and project budget inputs | `$1,234` each |
| Slurm accounting | enabled |
| Heartbeat | configured using the existing EventBridge Scheduler-to-SNS role |
| Idle hourly estimate | `$6.6986/hour` |

### Idle-cost composition

| Component | Estimated hourly cost |
| --- | ---: |
| `r7i.4xlarge` headnode | `$1.0584` |
| Root EBS gp3, 421 GiB | `$0.0461` |
| 12,000 GiB PERSISTENT_2 FSx at 500 MB/s/TiB | `$5.5890` |
| Public IPv4 | `$0.0050` |
| **Total** | **`$6.6986`** |

## Evidence and interpretation

- The source is the successful interactive command
  `dyec create --region-az us-west-2c --profile lsmc --cluster-type intel` and
  its generated resource/state/accounting receipts.
- The FSx and DRA waits were sequential in the transcript: the DRA submission
  began after the FSx reported `AVAILABLE`.
- The create monitor reported the cluster still creating at 8m 13s and complete
  at 9m 22s; the latter is the authoritative recorded cluster-creation duration.
- This record describes provisioning only. It is not a workflow-runtime,
  throughput, or workload-cost benchmark.

## Local receipt paths

The creation emitted these local records for follow-up inspection:

- `~/.config/daylily/resource_fsx-persistent2_pcand-18022_20260817054650.json`
- `~/.config/daylily/state_pcand-18022_20260817054650.json`
- `~/.config/daylily/slurm_accounting_pcand-18022_20260817054650_receipt.json`
