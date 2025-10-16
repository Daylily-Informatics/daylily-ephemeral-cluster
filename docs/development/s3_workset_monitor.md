# Daylily S3 Workset Monitor

This document proposes and describes the `bin/daylily-monitor-worksets` orchestration
utility.  The monitor watches an S3 prefix for new `workset_<timestamp>` folders
and automatically drives the Daylily staging and pipeline workflow on an
ephemeral cluster.

## High-level goals

* **Hands-off ingestion** – dropping a prepared workset folder into S3 is enough
to start the pipeline.
* **Safe concurrency** – sentinel files gate each stage and avoid double work.
* **Cluster lifecycle** – reuse a healthy cluster when possible and create a new
  ephemeral cluster when necessary.
* **Accurate audit trail** – S3 sentinel files are always up to date and
  aggregate sentinel indexes show all active directories in each state.
* **Recoverability** – any unexpected condition surfaces in `daylily.error` and
  the monitor keeps a descriptive reason in the file body.

## Directory contract

Each workset directory must contain the following entries:

```
workset_20240213T120000Z/
├── daylily_info.yaml
├── daylily_work.yaml
├── sample_data/
├── stage_samples.tsv
└── daylily.<sentinel>
```

Sentinel files encode the workflow state.  The monitor honours the following
states:

* `daylily.ready` – workset is ready to claim.
* `daylily.lock` – optimistic lock, written just before the monitor claims the
  workset.
* `daylily.in_progress` – monitor is actively staging and running the pipeline.
* `daylily.error` – terminal failure.
* `daylily.complete` – processing finished successfully.
* `daylily.ignore` – monitor must ignore the directory (manual intervention).

If a folder contains none of the sentinel files the monitor logs the condition
and continues without acting on the directory.

## Sentinel lock choreography

1. When a `daylily.ready` file exists and no terminal sentinel is present, the
   monitor writes `daylily.lock` containing an ISO-8601 timestamp.
2. The monitor waits 30 seconds and re-reads the directory to detect contention.
   If any new sentinel (other than the lock it just wrote) appears, the monitor
   immediately writes `daylily.error` noting the contention.
3. If no new sentinel appears, the monitor transitions to
   `daylily.in_progress` and proceeds.

During every poll the monitor generates aggregated listings in the same prefix:
`daylily.ready.log`, `daylily.in_progress.log`, etc.  Each log contains the
relative workset name and the timestamp written inside the sentinel, making it
simple to answer questions such as “Which worksets have been running for more
than 2 hours?”.

## Workflow outline

Once a workset is acquired the monitor performs the following steps:

1. **Validation**
   * Confirm the presence of `stage_samples.tsv`, `daylily_work.yaml`,
     `daylily_info.yaml`, and `sample_data/`.
   * Parse `stage_samples.tsv` and verify that every referenced S3 object exists
     and that all relative paths resolve inside the workset’s `sample_data`
     folder.
2. **Cluster preparation**
   * Reuse a running cluster when one is present in the configured region/AZ via
     `bin/daylily-get-ephemperal-cluster-deets`.
   * Otherwise create a new cluster using `bin/daylily-create-ephemeral-cluster`
     and the template specified in the monitor configuration.
3. **Staging & cluster warm-up (in parallel)**
   * Fire `./bin/daylily-stage-samples-from-local-to-headnode` in the background
     targeting the chosen cluster.
   * Poll for cluster readiness with `bin/daylily-get-ephemperal-cluster-deets`.
4. **Pipeline preparation**
   * Run `day-clone` with the arguments from `daylily_work.yaml` as the
     `ubuntu` user. The monitor launches the command within a login bash shell
     and parses the `Location` line in the output to discover the working
     directory that Daylily created.
   * Copy the staged `stage_samples.tsv` and optional `units.tsv` into the
     `<working-directory>/config/` folder reported by `day-clone`.
5. **Pipeline execution**
   * Launch a detached tmux session on the head node that runs `source
     ~/.bashrc && cd <working-directory> && source dyinit && source
     bin/day_activate slurm hg38 remote && DAY_CONTAINERIZED=true ./bin/day_run
     <rest from yaml>; bash`.  The trailing `bash` keeps the session alive for
     inspection after the workflow finishes.
   * Monitor command exit status.  Failure raises an exception that ends in
     `daylily.error`.
6. **Export**
   * When an `export_uri` is defined in `daylily_work.yaml`, run
     `./bin/daylily-export-fsx-to-s3` to publish the results back to S3.
7. **Sentinel completion**
   * On success write `daylily.complete` with the finish timestamp.
   * On failure write `daylily.error` and include the reason in the file body.

Cluster teardown honours the repository’s existing tooling.  By default the
monitor leaves clusters running for manual shutdown, but it can be configured to
trigger `bin/daylily-delete-ephemeral-cluster` when the job queue is empty and
no new data appears under `/fsx/data/` for 20 minutes.

## Configuration

Copy `config/daylily-workset-monitor.yaml` and update the values for your
account.  The configuration file covers:

* AWS region/profile (and optional session duration refresh).
* Monitored bucket/prefix and poll cadence.
* Location for aggregated sentinel log files.
* Preferred cluster template and AZ.
* Whether to reuse an existing cluster or force creation.
* Paths/commands for staging, cloning, running, and exporting data.

Run the monitor with:

```bash
./bin/daylily-monitor-worksets config/my-monitor.yaml --verbose
```

Use `--once` to perform a single scan or `--dry-run` to exercise the decision
logic without touching S3 or running commands.

## Logging

The monitor logs to stdout using the Python logging module.  Each decision
point (skipped directory, validation warning, state transition, command
execution) is recorded.  Additional detail (such as command stdout) is available
when running with `--verbose`.

The aggregated sentinel index files ensure there is a top-level record of every
workset that is currently ready, locked, in-progress, errored, or complete.  The
file format is TSV: `<workset-name>\t<timestamp>` per line.

## Extensibility

Future enhancements that fit naturally into this structure include:

* Integrating CloudWatch metrics/alarms for long-running worksets.
* Using the Daylily metadata database to map clusters to active worksets.
* Streaming pipeline stdout/stderr to S3 for long-term retention.
* Exposing a lightweight REST endpoint for real-time status dashboards.

The implementation purposefully keeps S3, sentinel, and command interactions in
isolated helper methods so that the workflow can be unit tested by injecting
mocks or by running the monitor in `--dry-run` mode.
