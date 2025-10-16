# Daylily Workset Monitor

The workset monitor is a long-running service that watches an S3 prefix for
folders containing pipeline inputs and sentinel files.  When a workset is ready,
the monitor stages data to a headnode, creates an ephemeral cluster, runs the
Daylily analysis pipeline, and exports the results back to S3.

## Directory structure

The monitor expects a root S3 URI containing the following layout:

```
s3://<bucket>/<root>/
    ready/
    in_flight/
    complete/
    error/
    ignore/
```

Each workset lives inside one of these sub-folders and contains:

* `stage_samples.tsv` – manifest of staged reads and/or BAM/CRAM files.
* `daylily_work.yaml` – configuration for staging, cluster creation, and
  pipeline commands.
* `daylily_info.yaml` – optional metadata produced by previous runs.
* `sample_data/` – staged fastq or cram/bam files referenced by the samples TSV.
* Sentinel files: `daylily.lock`, `daylily.ready`, `daylily.in_progress`,
  `daylily.complete`, `daylily.error`, `daylily.ignore`.

A workset is eligible for processing when `daylily.ready` exists and no other
terminal sentinel is present.  The monitor writes `daylily.lock` and waits 30
seconds to detect contention, then continues with processing.

## Workset configuration (`daylily_work.yaml`)

```yaml
aws:
  profile: research
  region: us-east-1

stage:
  samples_tsv: stage_samples.tsv
  units_tsv: stage_units.tsv            # optional
  pem_key: research-key.pem             # optional
  extra_args: []                        # optional args for staging script

cluster:
  name: research-hg38-20240401
  template: etc/cluster-templates/hg38.yaml
  create_args: []                       # optional args for daylily-create-ephemeral-cluster
  destroy_on_completion: true
  allow_existing: false

pipeline:
  day_clone:
    - --template
    - etc/day-clone-templates/rna-seq.yaml
  run_directory: pipelines/rna-seq
  samples_config_path: config/samples.tsv
  units_config_path: config/units.tsv
  dy_a_args: [slurm, hg38]
  dy_r_command: "rna-seq --full"
  environment:
    PIPELINE_ENV: production
```

## Running the monitor

```bash
./bin/daylily-monitor-worksets \
  s3://research-data/daylily/worksets \
  --aws-profile research \
  --aws-region us-east-1 \
  --poll-seconds 120 \
  --local-root /data/worksets \
  --log-file /var/log/daylily/workset-monitor.log
```

Use `--run-once` to process only currently ready worksets.  The monitor downloads
each workset to the local root, validates manifests, stages data, orchestrates
cluster creation, runs the pipeline, uploads results to either `complete/` or
`error/`, and writes the appropriate sentinel file.

## Sentinel behaviour

* Missing sentinel files – logged and skipped.
* `daylily.ignore` – skipped silently.
* `daylily.complete`, `daylily.error`, `daylily.in_progress` – logged and
  skipped.
* `daylily.ready` – processed. The monitor writes `daylily.lock`, waits 30
  seconds for competing sentinels, and if none appear writes
  `daylily.in_progress` and begins work.  Errors write `daylily.error`, success
  writes `daylily.complete`.

## Notes

* Sample manifests are validated locally; S3 URIs are checked with `HEAD`
  requests.  Any missing files raise a `MonitorError`.
* Cluster creation and deletion is delegated to existing Daylily scripts.
* Pipelines run via `. dyoainit && dy-a <args> && dy-r <command>` inside the
  cloned pipeline directory.
* Completed worksets are uploaded back to `complete/`; failed runs are mirrored
  to `error/` for later inspection.
