# DYEC 10.0.118 jul8itelx4 Intel Catalog Plus BJuice Runbook

Run started from `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` on
2026-07-08 with cluster `jul8itelx4`, profile `lsmc`, region `us-west-2`, and
DayOA tag `10.0.70`.

## Source Versions

```bash
cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate
dyec version
dyec info
git show -s --format='%H %D %ci' HEAD
git -C /Users/jmajor/projects/lsmc/daylily-omics-analysis show -s --format='%H %D %ci' HEAD
```

Observed:
- DYEC `10.0.118`, commit `3621b79b6b75625d209d840256f94cdce387e991`
- DayOA `10.0.70`, commit `e2d7793f6faf8d30524548ac693bf66c82e723e4`
- Catalog-selected DayOA tags: `10.0.70`

## Cluster Creation Reference

Original interactive form:

```bash
cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate
dyec create --profile lsmc --cluster-type intel --region-az us-west-2d
```

Replay form using saved next-run config:

```bash
cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate
dyec create --profile lsmc --cluster-type intel --region-az us-west-2d --config /Users/jmajor/.config/daylily/jul8itelx4_next_run_20260708114632.yaml --non-interactive
```

Cluster support files:

```text
/Users/jmajor/.config/daylily/jul8itelx4_cluster_20260708114632.yaml
/Users/jmajor/.config/daylily/jul8itelx4_cluster_20260708114632.yaml.init
/Users/jmajor/.config/daylily/jul8itelx4_next_run_20260708114632.yaml
/Users/jmajor/.config/daylily/state_jul8itelx4_20260708114632.json
/Users/jmajor/.config/daylily/preflight_jul8itelx4_20260708114632.json
/Users/jmajor/.config/daylily/jul8itelx4_spot_price_summary_20260708114632.json
```

## Durable Artifacts

```text
/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260708T142032Z_intel_catalog_bjuice_jul8itelx4_dyec_10_0_118_ledger.md
/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260708T142032Z_intel_catalog_bjuice_selected_commands.json
/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260708T142032Z_intel_catalog_bjuice_selected_commands.tsv
```

Evidence S3 root:

```text
s3://lsmc-ssf-sequencing-data/derived/jul8itelx4/command_catalog_results/10.0.70-20260708T142032Z/
```

## Commands Used

### Gate 0

```bash
cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate
AWS_PROFILE=lsmc aws sts get-caller-identity
AWS_PROFILE=lsmc pcluster describe-cluster --cluster-name jul8itelx4 --region us-west-2
dyec version
dyec info
git status --short --branch
git show -s --format='%H %D %ci' HEAD
git -C /Users/jmajor/projects/lsmc/daylily-omics-analysis status --short --branch
git -C /Users/jmajor/projects/lsmc/daylily-omics-analysis show -s --format='%H %D %ci' HEAD
```

### Headnode Refresh

Pending execution:

```bash
cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate
dyec headnode configure --profile lsmc --region us-west-2 --cluster jul8itelx4
```

### Launch Commands

The selected command plan is in
`docs/plans/20260708T142032Z_intel_catalog_bjuice_selected_commands.tsv`.
Each workflow launch must:

- use `--git-tag 10.0.70`
- create or use analysis IDs from the command plan
- execute the rendered `dy-r ... -j 300 -p -k -T 0` command
- avoid raw `snakemake`

### Export And Cleanup

For each successful live analysis, export first, verify object/byte parity, then
cleanup only that analysis root with `dyec analysis guard`.

No cleanup command is valid until its corresponding export verification is
recorded in the ledger.
