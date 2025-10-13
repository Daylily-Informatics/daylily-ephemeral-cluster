# Daylily Ephemeral Cluster
_(stable tagged release: see `config/daylily/daylily_cli_global.yaml`)_

Infrastructure-as-code to launch **transient AWS ParallelCluster** environments optimized for bioinformatics workloads. It creates and operates the compute fabric (VPC, head node, Slurm partitions, FSx for Lustre, optional PCUI). **Analysis workflows live elsewhere**: see [daylily-omics-analysis](https://github.com/Daylily-Informatics/daylily-omics-analysis).

---

## What this repo does
- Provisions a self-scaling Slurm cluster with FSx Lustre and S3 mirroring.
- Installs head‑node tooling (Daylily CLI bootstrap, `day-clone`, config files).
- Stages a region-scoped **references bucket** and links it to FSx.
- (Optional) Deploys **PCUI** for browser access to consoles and terminals.
- Ships helpers for **cost visibility** and **AZ/spot market scanning**.
- Provides teardown and cleanup helpers.

## What this repo does **not** do
- It does **not** ship analysis pipelines or Snakemake targets.
- It does **not** document `dy-a`, `dy-r`, sample/units TSVs, or smoke tests.
  - Those now live in **daylily-omics-analysis** docs.

---

## Prereqs (local workstation)
- macOS or Linux, Bash/Zsh, `tmux` recommended.
- `git`, `python3`, `wget`.
- **AWS CLI** configured with a profile (e.g., `daylily-service`).
- Ability to create IAM users/roles, EC2, VPC, FSx, and S3 resources.

Check minimum versions:
```bash
./bin/check_prereq_sw.sh
```

Configure AWS CLI (example):
```ini
# ~/.aws/config
[default]
region = us-west-2
output = json

[daylily-service]
region = us-west-2
output = json
```
```ini
# ~/.aws/credentials
[daylily-service]
aws_access_key_id = <ACCESS_KEY>
aws_secret_access_key = <SECRET_KEY>
```

---

## Install (workstation)
Clone a **tagged** release:
```bash
git clone -b "$(yq -r '.daylily.git_tag' config/daylily/daylily_cli_global.yaml)"   https://github.com/Daylily-Informatics/daylily-ephemeral-cluster.git
cd daylily-ephemeral-cluster
```

Install Miniconda and the Daylily CLI env:
```bash
./bin/install_miniconda
./bin/init_dayec
conda activate DAY-EC
```

---

## Prepare the references bucket (one‑time per region)
We use a read‑optimized S3 bucket that FSx mounts for shared reference data.

Clone the public references into **your** bucket name (`<PREFIX>-omics-analysis-<REGION>`):
```bash
export AWS_PROFILE=daylily-service
export REGION=us-west-2
export BUCKET_PREFIX=<yourprefix>

# dry‑run
./bin/create_daylily_omics_analysis_s3.sh --region "$REGION" --profile "$AWS_PROFILE"   --bucket-prefix "$BUCKET_PREFIX"

# execute
./bin/create_daylily_omics_analysis_s3.sh --region "$REGION" --profile "$AWS_PROFILE"   --bucket-prefix "$BUCKET_PREFIX" --disable-dryrun
```

---

## Pick an Availability Zone (cost/perf scan)
Scan spot markets to estimate per‑sample EC2 cost and stability by AZ:
```bash
export AWS_PROFILE=daylily-service
export REGION=us-west-2
./bin/check_current_spot_market_by_zones.py -o init_daylily_cluster.tsv --profile "$AWS_PROFILE"
```

---

## Create an Ephemeral Cluster
1. Ensure IAM prerequisites (service‑linked roles, quotas, cost tags) are set.
2. Launch cluster via provided `make` targets or helper scripts (see `config/day_cluster/`).
3. When complete, you’ll have:
   - Head node (Slurm controller)
   - FSx Lustre mounted at `/fsx`
   - Optional PCUI

Post‑create head‑node bootstrap (SSH via your `.pem`):
```bash
# from your workstation
bin/daylily-cfg-headnode    # guided: sets SSH key, installs tooling, DAY-EC, etc.
```

This installs:
- `~/projects/daylily-ephemeral-cluster` on the head node
- `./bin/install-daylily-headnode-tools` (adds `day-clone`, CLI config)
- Miniconda + `DAY-EC` env on the head node

---

## Operate
- **PCUI**: optional web console for Slurm and shell sessions.
- **Budgets & tags**: activate cost allocation tags; use budgets for guardrails.
- **Quotas**: ensure EC2, FSx and VPC quotas are sufficient for your target scale.
- **Teardown**: use the provided teardown helpers to remove cluster and FSx when done.

---

## Next: Run analyses
Workflows, CLI usage, profiles, and smoke tests now live in:
- **daylily-omics-analysis** → Quick Start & “first analysis on an ephemeral cluster”
  - https://github.com/Daylily-Informatics/daylily-omics-analysis

Use `day-clone` on the head node to fetch analysis repos into `/fsx/analysis_results/<user>/...`.

---

## Troubleshooting
- Missing service‑linked role for EC2 Spot can block compute node launches.
- If `conda` is not found, re‑run `./bin/install_miniconda` then `./bin/init_dayec`.
- Validate your AWS profile and region; many scripts honor `AWS_PROFILE`/`AWS_REGION`.

---

## License & Support
Open‑source. No bundled commercial licenses. Consulting available via https://www.dyly.bio.

