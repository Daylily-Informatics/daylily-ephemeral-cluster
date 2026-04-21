# Daylily Ephemeral Cluster

[![Latest release](https://img.shields.io/badge/dynamic/yaml?url=https%3A%2F%2Fraw.githubusercontent.com%2FDaylily-Informatics%2Fdaylily-ephemeral-cluster%2Fmain%2Fconfig%2Fdaylily_cli_global.yaml&query=%24.daylily.git_ephemeral_cluster_repo_release_tag&label=latest%20release&cacheSeconds=300&color=teal)](https://github.com/Daylily-Informatics/daylily-ephemeral-cluster/releases) [![Latest tag](https://img.shields.io/badge/dynamic/yaml?url=https%3A%2F%2Fraw.githubusercontent.com%2FDaylily-Informatics%2Fdaylily-ephemeral-cluster%2Fmain%2Fconfig%2Fdaylily_cli_global.yaml&query=%24.daylily.git_ephemeral_cluster_repo_tag&label=latest%20tag&color=pink&cacheSeconds=300)](https://github.com/Daylily-Informatics/daylily-ephemeral-cluster/tags)

Daylily stands up a short-lived AWS ParallelCluster, finishes the headnode configuration after `pcluster` itself reports success, gives the operator a validated Session Manager login shell as `ubuntu`, stages laptop-side inputs into the FSx-backed data plane, launches the workflow repo in tmux, exports results back to the backing S3 repository, and then tears the cluster down when the run is complete.

> The bucket is durable. The cluster is ephemeral. Export before delete.

## Supported Operator Contract

The supported path is:

1. `source ./activate`
2. `daylily-ec preflight`
3. `daylily-ec create`
4. `daylily-ec headnode connect`
5. `daylily-ec samples stage`
6. `daylily-ec workflow launch`
7. `daylily-ec export --target-uri analysis_results/ubuntu`
8. `daylily-ec delete --dry-run`
9. `daylily-ec delete`

Supported remote access is AWS Systems Manager Session Manager landing directly in the `ubuntu` login shell. The repo hard-checks the Session Manager document and the effective remote user before supported command payloads run.

> A cluster is not "ready" when CloudFormation or ParallelCluster first says the infrastructure exists. The supported readiness point is when `daylily-ec create` returns successfully after the post-create headnode configuration and bootstrap validation steps complete.

## One Copy-Pasteable Lifecycle

```bash
source ./activate

export AWS_PROFILE=daylily-service-lsmc
export REGION=us-west-2
export REGION_AZ=us-west-2d
export CLUSTER_NAME=day-demo-$(date +%Y%m%d%H%M%S)
export DAY_EX_CFG="$HOME/.config/daylily/daylily_ephemeral_cluster.yaml"
export REF_BUCKET=s3://lsmc-dayoa-omics-analysis-us-west-2
export ANALYSIS_SAMPLES=etc/analysis_samples_template.tsv
export STAGE_CFG_DIR="$PWD/tmp-stage-config/$CLUSTER_NAME"
export EXPORT_DIR="$PWD/tmp-export/$CLUSTER_NAME"

daylily-ec preflight \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG"

daylily-ec create \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG"

daylily-ec headnode connect \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"

daylily-ec samples stage \
  "$ANALYSIS_SAMPLES" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --reference-bucket "$REF_BUCKET" \
  --config-dir "$STAGE_CFG_DIR"

# Use the "Remote FSx stage directory" printed by the staging helper.
daylily-ec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --stage-dir "/fsx/data/staged_sample_data/remote_stage_<timestamp>" \
  --destination dayoa \
  --aligners sent \
  --dedupers dppl \
  --snv-callers sentd

daylily-ec export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster-name "$CLUSTER_NAME" \
  --target-uri analysis_results/ubuntu \
  --output-dir "$EXPORT_DIR"

cat "$EXPORT_DIR/fsx_export.yaml"

daylily-ec delete --dry-run \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster-name "$CLUSTER_NAME"

daylily-ec delete \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster-name "$CLUSTER_NAME"
```

`fsx_export.yaml` is the machine-readable export receipt. A successful run writes `status: success` and the resolved S3 destination.

## Architecture At A Glance

1. `daylily-ec` is the control-plane CLI. It handles preflight, create, cluster inspection, export, delete, environment introspection, runtime checks, and pricing snapshots.
2. The create flow renders the cluster configuration, calls ParallelCluster, then runs Daylily headnode configuration over Session Manager.
3. The durable data plane is the S3 bucket plus the FSx for Lustre filesystem attached to the cluster. Laptop-side staging writes into the bucket-backed FSx namespace.
4. The supported connect path is `daylily-ec headnode connect`, which opens Session Manager into the `ubuntu` login shell.
5. Workflow launch happens from the operator machine through `daylily-ec workflow launch`, which creates a run directory at `/home/ubuntu/daylily-runs/<session>/`, writes `launch.sh`, `tmux.log`, and `status.json`, and starts the run inside tmux.
6. Export uses the FSx data repository task API and writes `fsx_export.yaml` locally so the operator has a concrete export receipt before teardown.

## What This Repo Ships

- `environment.yaml` plus `pyproject.toml`: the `DAY-EC` environment contract
- `activate`: checkout bootstrap that creates or repairs `DAY-EC`, installs the repo editable, and validates the local toolchain
- `daylily-ec headnode connect`: interactive Session Manager shell launcher with `ubuntu`-only validation
- `daylily-ec headnode configure`: explicit headnode configuration helper for repair or manual reruns
- `daylily-ec headnode info`: full `pcluster describe-cluster` output for one cluster
- `daylily-ec headnode jobs`: Slurm queue output using the same format as the headnode `sq` alias
- `daylily-ec cluster list/describe/wait`: ParallelCluster inspection helpers
- `daylily-ec samples stage`: translator and staging helper that turns `analysis_samples.tsv` into workflow-ready `samples.tsv` and `units.tsv`
- `daylily-ec workflow launch/status/logs`: remote launcher and run-state inspection helpers
- `daylily-ec state list/show`: local state-file inspection helpers
- `daylily_ec/ssh_to_ssm_e2e_runner.py`: AWS-backed end-to-end runner that exercises the supported lifecycle through the repo CLI/helpers

## AWS And Local Prerequisites

At minimum, the operator account needs:

- a working named AWS profile
- permission for STS identity lookup, IAM inspection/bootstrap, Service Quotas reads, S3 bucket discovery/access, EC2/VPC inspection, FSx, SSM, and ParallelCluster operations
- a reference bucket in the target region that will back the cluster FSx filesystem
- Session Manager document `SSM-SessionManagerRunShell` configured to run shell sessions as `ubuntu` and source a login shell
- enough regional quota for the requested cluster shape

Local toolchain for the supported path:

- Conda
- `daylily-ec`
- `aws`
- `pcluster`
- `session-manager-plugin`
- `jq`, `yq`, `rclone`, `node`, and the rest of the `DAY-EC` Conda layer

If any of this is missing, cluster creation will fail in annoying ways. Run `daylily-ec preflight` first and read the failures instead of guessing.

## Cost, Time, And Failure Notes

- `daylily-ec create` can take a long time. The ParallelCluster build alone can take tens of minutes, and Daylily still has headnode bootstrap work to finish after that.
- The cluster is disposable; the export target is not. Do not delete until you have checked `fsx_export.yaml`.
- The supported remote user is `ubuntu`. Any path that would land you as another user is a defect, not a supported fallback.
- Session Manager misconfiguration is a hard stop. The repo does not tell operators to connect first and then switch users manually.

## Read This Next

- [docs/ultra_rapid_start.md](docs/ultra_rapid_start.md): the shortest happy path
- [docs/quickest_start.md](docs/quickest_start.md): a guided walkthrough with sanity checks
- [docs/operations.md](docs/operations.md): connect, stage, run, monitor, export, and delete
- [docs/aws_setup.md](docs/aws_setup.md): AWS prerequisites, IAM expectations, quotas, and Session Manager requirements
- [docs/cli_reference.md](docs/cli_reference.md): command reference grounded in current `--help` output
- [docs/testing_and_debugging.md](docs/testing_and_debugging.md): test commands, E2E runner usage, and failure triage
- [docs/monitoring_and_troubleshooting.md](docs/monitoring_and_troubleshooting.md): runtime and operational debugging
- [docs/DAY_EC_ENVIRONMENT.md](docs/DAY_EC_ENVIRONMENT.md): `DAY-EC` checkout environment contract
- [docs/pip_install.md](docs/pip_install.md): pip-install path and external prerequisites
- [docs/archive/README.md](docs/archive/README.md): historical material, pre-rewrite snapshot, and unsupported legacy appendix
 
