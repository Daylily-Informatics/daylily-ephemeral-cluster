# Take13 HIOMR2 HG003 1x Launch Ledger

## Objective

Create a new `take13` DayOA checkout on the non-Ursa `preval-hiomr2`
cluster from exact tag `13.0.77`, configure it with the packaged
`hg003_hiomrs_1x_raw_fastq` six-manifest fixture, and launch the `hiomr2`
catalog workflow for HG003 1x paired Illumina plus HG003 primary-only ONT 1x.

## Gate 0

- Cluster: `preval-hiomr2`
- AWS profile/region: `lsmc`, `us-west-2`
- Remote user: `ubuntu`
- Exact DayOA tag: `13.0.77`
- Destination: `/fsx/analysis_results/preval-hiomr2/take13`
- Catalog command: `hiomr2`
- Test data profile: `hg003_hiomrs_1x_raw_fastq`
- Input contract: packaged six-manifest fixture; no inferred inputs
- Workflow execution: persistent named tmux, `source dyoainit`, `dy-a slurm hg38`,
  then the catalog's exact `dy-r` command
- Existing Take10 and other analysis roots are out of scope.

## Execution Ledger

| ID | Action | Status | Evidence |
|---|---|---|---|
| RUN-001 | Resolve the requested command and exact slim-data fixture | SUCCESS | No `hiomr10` code exists; `hiomr2` selects `hg003_hiomrs_1x_raw_fastq`. |
| RUN-002 | Record write visit and acquire the Take13 analysis-root lock | OPEN | |
| RUN-003 | Run `day-clone -t 13.0.77 -d take13` and verify exact clean tag | OPEN | |
| RUN-004 | Install and validate the packaged HG003 six-manifest fixture | OPEN | |
| RUN-005 | Initialize DayOA in a persistent tmux and launch exact `hiomr2` command | OPEN | |
| RUN-006 | Verify controller/process and initial Slurm state | OPEN | |

## Completion Contract

The launch is complete when the exact tagged checkout and manifest hashes are
recorded, the `dy-r` controller is alive in the named tmux session, and the
initial workflow/Slurm state is captured. The workflow itself may remain
running after launch; its analysis-root write lock must remain owned while the
controller is active.
