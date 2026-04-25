# Quickest Start

This is the supported operator walkthrough with sanity checks after each stage. It is longer than [ultra_rapid_start.md](ultra_rapid_start.md), but it is the better first runbook for a fresh operator session.

## 1. Activate The Repo Environment

```bash
cd /path/to/daylily-ephemeral-cluster
source ./activate
daylily-ec version
daylily-ec runtime status
daylily-ec info
aws --version
pcluster version
session-manager-plugin
```

Expected:

- `daylily-ec` resolves successfully
- `dyec` resolves successfully as the short alias for the same CLI
- runtime backend is `day-ec-conda`
- `aws`, `pcluster`, and `session-manager-plugin` are available in the shell

## 2. Set The Working Variables

```bash
export AWS_PROFILE=daylily-service-lsmc
export REGION=us-west-2
export REGION_AZ=us-west-2d
export CLUSTER_NAME=day-demo-$(date +%Y%m%d%H%M%S)
export DAY_EX_CFG="$HOME/.config/daylily/daylily_ephemeral_cluster.yaml"
export REF_BUCKET=s3://lsmc-dayoa-omics-analysis-us-west-2
export ANALYSIS_SAMPLES=etc/analysis_samples_template.tsv
export STAGE_CFG_DIR="$PWD/tmp-stage-config/$CLUSTER_NAME"
export EXPORT_DIR="$PWD/tmp-export/$CLUSTER_NAME"
```

Sanity check:

```bash
aws sts get-caller-identity --profile "$AWS_PROFILE"
aws s3 ls "$REF_BUCKET" --profile "$AWS_PROFILE" --region "$REGION"
```

## 3. Run Preflight

```bash
daylily-ec preflight \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG"
```

What preflight is checking:

- local toolchain
- AWS identity
- IAM permissions
- config validity
- quota headroom
- bucket discovery/access
- baseline network resources and region policy selection

Do not skip this unless you enjoy slow failures later.

## 4. Create The Cluster

```bash
daylily-ec create \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG"
```

Important:

- this may take a long time
- `pcluster` success is not the final readiness point
- wait for the Daylily CLI to return successfully

Sanity checks after create:

```bash
daylily-ec cluster list --profile "$AWS_PROFILE" --region "$REGION"

daylily-ec headnode connect \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

Once connected, verify the login shell:

```bash
whoami
command -v day-clone
command -v tmux
command -v python3
exit
```

Expected:

- `whoami` prints `ubuntu`
- `day-clone` resolves on `PATH`

## 5. Stage The Analysis Inputs From The Laptop

```bash
daylily-ec samples stage "$ANALYSIS_SAMPLES" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --reference-bucket "$REF_BUCKET" \
  --config-dir "$STAGE_CFG_DIR"
```

This prints:

- the remote FSx stage directory
- the staged file list
- the generated manifest filenames

Manifest notes:

- start from `etc/analysis_samples_template.tsv`
- legacy Illumina rows still work with `R1_FQ` / `R2_FQ`
- ONT, Ultima, PacBio, Roche, and hybrid rows use the modality-specific columns on the same TSV header

Sanity checks:

```bash
ls -1 "$STAGE_CFG_DIR"
```

You should see one `*_samples.tsv` and one `*_units.tsv`.

## 6. Launch The Workflow

Use the exact remote stage directory printed by the staging helper:

```bash
daylily-ec workflow launch \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --stage-dir "/fsx/data/staged_sample_data/remote_stage_<timestamp>" \
  --destination dayoa
```

The launcher prints:

- `__DAYLILY_SESSION__`
- `__DAYLILY_RUN_DIR__`
- `__DAYLILY_REPO_PATH__`

Sanity checks:

```bash
daylily-ec --json workflow status \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --session <session>

daylily-ec workflow logs \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --session <session> \
  --lines 50
```

## 7. Export Results

```bash
daylily-ec export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster-name "$CLUSTER_NAME" \
  --target-uri analysis_results/ubuntu \
  --output-dir "$EXPORT_DIR"

cat "$EXPORT_DIR/fsx_export.yaml"
```

Expected:

- `status: success`
- an `s3_uri` pointing under the filesystem export root

## 8. Delete The Cluster

Delete only after export verification:

```bash
daylily-ec delete --dry-run \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster-name "$CLUSTER_NAME"

daylily-ec delete \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster-name "$CLUSTER_NAME"
```

If you want the longer debugging and monitoring playbook, continue with [operations.md](operations.md) and [monitoring_and_troubleshooting.md](monitoring_and_troubleshooting.md).
