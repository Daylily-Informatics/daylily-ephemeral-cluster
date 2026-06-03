# Running Nextflow Pipelines With DAY-EC

This is a standalone operator runbook for running an nf-core/Nextflow pipeline on a DAY-EC cluster, exporting results through the DAY-EC DRA export path, verifying any already-approved public report link, and shutting the cluster down after export verification.

The validated example is `daylily-sarek` at ref `0.7.379`, which is nf-core/sarek 3.6.0. The same lifecycle applies to other Nextflow repositories, but do not assume their profile, samplesheet, reference, or Nextflow-version requirements are identical.

## Boundaries

- DAY-EC creates and deletes the ParallelCluster, manages run-data DRAs, exports completed analysis directories, and gives supported SSM access to the headnode.
- `daylily-sarek` is a repository catalog row, not a DAY-EC workflow command. Clone it with `day-clone` and launch `nextflow` directly on the headnode.
- Nextflow output must land under `/fsx/analysis_results/<executing_entity>/<analysis_id>/`.
- `dyec export` only exports a completed analysis directory whose source path is exactly `/fsx/analysis_results/<executing_entity>/<analysis_id>`.
- CloudFront publication is not a `dyec` subcommand. Public docs may link only to an already-approved no-auth URL that returns HTTP 200.
- Cluster deletion is destructive. Run `dyec delete --dry-run` first and do not run the live delete until the export receipt and any required public URL have been verified.

## 1. Activate The DAY-EC Checkout

```bash
cd /path/to/daylily-ephemeral-cluster
source ./activate

dyec --json version
dyec runtime status
dyec info
aws --version
pcluster version
session-manager-plugin
```

Expected:

- `dyec` and `daylily-ec` resolve to the same CLI.
- The runtime backend is the activated DAY-EC environment.
- AWS CLI, ParallelCluster CLI, and the Session Manager plugin are available.

## 2. Set Run Variables

Use explicit values. Do not rely on inferred AWS profile, region, bucket, or cluster names.

```bash
export AWS_PROFILE=<non-default-profile>
export AWS_REGION=us-west-2
export REGION=us-west-2
export REGION_AZ=us-west-2d

export CLUSTER_NAME=<cluster-name>
export DAY_EX_CFG="$HOME/.config/daylily/daylily_ephemeral_cluster.yaml"
export DAY_PROJECT_NAME="da-us-west-2d-$CLUSTER_NAME"

export REF_S3_URI=s3://<reference-bucket>
export CONTROL_DATA_S3_URI=s3://<control-data-bucket>
export STAGE_S3_URI=s3://<staging-bucket>/<prefix>
export ANALYSIS_RESULTS_S3_URI=s3://<analysis-results-bucket>/<prefix>

export EXECUTING_ENTITY=ubuntu
export ANALYSIS_ID=sarek-nextflow-$(date -u +%Y%m%dT%H%M%SZ)
export EXPORT_DIR="$PWD/tmp-export/$ANALYSIS_ID"
export EXPORT_S3_URI="$ANALYSIS_RESULTS_S3_URI/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID/"
```

Sanity checks:

```bash
aws sts get-caller-identity --profile "$AWS_PROFILE" --region "$REGION"
aws s3 ls "$REF_S3_URI/" --profile "$AWS_PROFILE" --region "$REGION"
aws s3 ls "$ANALYSIS_RESULTS_S3_URI/" --profile "$AWS_PROFILE" --region "$REGION"
```

## 3. Preflight And Create The Cluster

```bash
dyec preflight \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG"

dyec create \
  --profile "$AWS_PROFILE" \
  --region-az "$REGION_AZ" \
  --config "$DAY_EX_CFG"
```

Confirm the cluster and supported headnode access:

```bash
dyec cluster list \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --verbose

dyec headnode info \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"

dyec headnode connect \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

On the headnode:

```bash
whoami
pwd
command -v day-clone
command -v tmux
command -v sbatch
command -v squeue
exit
```

Expected user is `ubuntu`; expected working directory is `/home/ubuntu`.

## 4. Refresh The Headnode Catalog

Run this after creating a cluster from a checkout that contains newer catalog rows than the packaged runtime already on the headnode.

```bash
python - <<'PY'
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, write_remote_text

profile = "lsmc"
region = "us-west-2"
cluster = "CLUSTER_NAME_PLACEHOLDER"
target = resolve_headnode_instance_id(cluster, region, profile=profile)
catalog = Path("config/daylily_pipeline_command_catalog.yaml").read_text(encoding="utf-8")
result = write_remote_text(
    target.instance_id,
    region,
    "/home/ubuntu/.config/daylily/daylily_pipeline_command_catalog.yaml",
    catalog,
    profile=profile,
    as_user="ubuntu",
)
print(result.command_id)
PY
```

If you copy this block literally, replace `CLUSTER_NAME_PLACEHOLDER` or pass the environment into the Python snippet:

```bash
python - <<'PY'
import os
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, write_remote_text

profile = os.environ["AWS_PROFILE"]
region = os.environ["REGION"]
cluster = os.environ["CLUSTER_NAME"]
target = resolve_headnode_instance_id(cluster, region, profile=profile)
catalog = Path("config/daylily_pipeline_command_catalog.yaml").read_text(encoding="utf-8")
result = write_remote_text(
    target.instance_id,
    region,
    "/home/ubuntu/.config/daylily/daylily_pipeline_command_catalog.yaml",
    catalog,
    profile=profile,
    as_user="ubuntu",
)
print(result.command_id)
PY
```

Verify the remote Sarek catalog row:

```bash
python - <<'PY'
import os

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell

profile = os.environ["AWS_PROFILE"]
region = os.environ["REGION"]
cluster = os.environ["CLUSTER_NAME"]
target = resolve_headnode_instance_id(cluster, region, profile=profile)
script = r'''
set -euo pipefail
python3 - <<'REMOTE_PY'
import yaml
from pathlib import Path

catalog = yaml.safe_load(
    Path("/home/ubuntu/.config/daylily/daylily_pipeline_command_catalog.yaml").read_text()
)
row = catalog["repositories"]["daylily-sarek"]
print("default_ref=" + str(row["default_ref"]))
print("analysis_commands=" + repr(row["analysis_commands"]))
REMOTE_PY
'''
result = run_shell(target.instance_id, region, script, profile=profile, as_user="ubuntu")
print(result.stdout)
PY
```

Expected:

```text
default_ref=0.7.379
analysis_commands=[]
```

## 5. Headnode Preflight For Nextflow

```bash
python - <<'PY'
import os

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell

profile = os.environ["AWS_PROFILE"]
region = os.environ["REGION"]
cluster = os.environ["CLUSTER_NAME"]
target = resolve_headnode_instance_id(cluster, region, profile=profile)
script = r'''
set -euo pipefail
test "$(id -un)" = "ubuntu"

for path in /fsx /fsx/references /fsx/resources /fsx/run_dir_mounts /fsx/analysis_results; do
  test -e "$path" || { echo "Missing required path: $path" >&2; exit 2; }
done
mkdir -p /fsx/work/ubuntu

for cmd in bash git curl tmux sbatch squeue singularity apptainer conda day-clone; do
  command -v "$cmd" >/dev/null || { echo "Missing required command: $cmd" >&2; exit 2; }
done

test -e /fsx/references/genomic_data/organism_references/H_sapiens/hg38/fasta_fai_minalt/GRCh38_no_alt_analysis_set.fasta
test -e /fsx/references/genomic_data/organism_references/H_sapiens/hg38/fasta_fai_minalt/GRCh38_no_alt_analysis_set.fasta.fai
test -e /fsx/references/genomic_data/organism_references/H_sapiens/hg38/fasta_fai_minalt/GRCh38_no_alt_analysis_set.dict
test -e /fsx/references/genomic_data/organism_references/H_sapiens/hg38_broad/hg38_broad_core.bed
test -e /fsx/references/genomic_data/organism_annotations/H_sapiens/hg38/gatk/Homo_sapiens_assembly38.dbsnp138.vcf.gz
test -e /fsx/references/genomic_data/organism_annotations/H_sapiens/hg38/gatk/Homo_sapiens_assembly38.dbsnp138.vcf.gz.tbi
'''
result = run_shell(target.instance_id, region, script, profile=profile, as_user="ubuntu")
print(result.stdout)
PY
```

This must fail hard for missing paths or commands. Do not create `/fsx/data` symlinks or reference aliases.

## 6. Install Pinned Nextflow

Sarek `0.7.379` requires Nextflow `24.10.5` or newer by pipeline declaration, and the validated DAY-EC run pinned `24.10.5` with Java 21. Do not use a moving latest Nextflow or Java 25 for this Sarek ref.

```bash
python - <<'PY'
import os

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell

profile = os.environ["AWS_PROFILE"]
region = os.environ["REGION"]
cluster = os.environ["CLUSTER_NAME"]
target = resolve_headnode_instance_id(cluster, region, profile=profile)
script = r'''
set -euo pipefail
version=24.10.5
base=/fsx/resources/environments/nextflow
java_dir=$base/java-21
install_dir=$base/$version
launcher=$install_dir/nextflow-launcher
wrapper=$install_dir/nextflow

mkdir -p "$install_dir" /home/ubuntu/.local/bin
if [ ! -x "$java_dir/bin/java" ]; then
  conda create -y -p "$java_dir" -c conda-forge openjdk=21
fi
"$java_dir/bin/java" -version

if [ ! -s "$launcher" ]; then
  curl -fsSL https://get.nextflow.io -o "$launcher"
  chmod 755 "$launcher"
fi

cat > "$wrapper" <<'REMOTE_SH'
#!/usr/bin/env bash
set -euo pipefail
export JAVA_CMD=/fsx/resources/environments/nextflow/java-21/bin/java
export NXF_VER=24.10.5
if [ -z "${TERM:-}" ] || [ "${TERM:-}" = "unknown" ]; then
  export TERM=xterm
fi
exec /fsx/resources/environments/nextflow/24.10.5/nextflow-launcher "$@"
REMOTE_SH
chmod 755 "$wrapper"
ln -sfn "$wrapper" /home/ubuntu/.local/bin/nextflow

PATH="$install_dir:/home/ubuntu/.local/bin:$PATH" nextflow -version | tee /tmp/daylily-nextflow-version.txt
grep -F "version $version" /tmp/daylily-nextflow-version.txt
PATH="$install_dir:/home/ubuntu/.local/bin:$PATH" nextflow info | grep -F "Version: $version"
'''
result = run_shell(target.instance_id, region, script, profile=profile, as_user="ubuntu", timeout=900)
print(result.stdout)
PY
```

Stop if `nextflow -version` does not report `24.10.5`.

## 7. Stage Data

### Option A: Bundled Sarek Test FASTQs

The proof run uses Sarek's bundled samplesheet and test FASTQs after the repository is cloned:

```text
.test_data/data/test_samplesheet.csv
```

No DAY-EC data staging is needed for this proof input.

### Option B: Real FASTQs From S3 Through A Run DRA

Attach the exact S3 prefix needed for the run. Keep the mount read-only.

```bash
export RUN_MOUNT_ID=my-fastq-run
export RUN_FASTQ_S3_URI=s3://sequencer-run-bucket/runs/RUN123/

dyec --json mounts create "$RUN_FASTQ_S3_URI" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --mount-id "$RUN_MOUNT_ID" \
  --platform ILMN \
  --read-only \
  --wait \
  --timeout-seconds 3600

dyec --json mounts verify \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --mount-id "$RUN_MOUNT_ID"
```

After the mount verifies, make the Sarek samplesheet on the headnode. Use exact FASTQ paths under `/fsx/run_dir_mounts/<mount_id>/`; do not rely on file discovery in the pipeline command.

```bash
dyec headnode connect \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

On the headnode:

```bash
export ANALYSIS_ID=sarek-nextflow-YYYYMMDDTHHMMSSZ
export RUN_MOUNT_ID=my-fastq-run
mkdir -p "/fsx/analysis_results/ubuntu/$ANALYSIS_ID/inputs"
cat > "/fsx/analysis_results/ubuntu/$ANALYSIS_ID/inputs/sarek_samplesheet.csv" <<CSV
patient,sample,lane,fastq_1,fastq_2
patient1,sample1,L001,/fsx/run_dir_mounts/$RUN_MOUNT_ID/path/to/sample1_R1.fastq.gz,/fsx/run_dir_mounts/$RUN_MOUNT_ID/path/to/sample1_R2.fastq.gz
CSV
test -s "/fsx/analysis_results/ubuntu/$ANALYSIS_ID/inputs/sarek_samplesheet.csv"
exit
```

For direct Nextflow/Sarek runs, `dyec samples stage` is not the primary path because it writes DayOA `samples.tsv` and `units.tsv`, not an nf-core/sarek samplesheet. Use `dyec samples stage` for DAY-EC catalog workflow commands; use a run DRA and an explicit nf-core samplesheet for Sarek.

## 8. Clone And Patch The Pipeline Checkout

Clone through the DAY-EC catalog:

```bash
python - <<'PY'
import os

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell

profile = os.environ["AWS_PROFILE"]
region = os.environ["REGION"]
cluster = os.environ["CLUSTER_NAME"]
analysis_id = os.environ["ANALYSIS_ID"]
executing_entity = os.environ["EXECUTING_ENTITY"]
target = resolve_headnode_instance_id(cluster, region, profile=profile)
script = f'''
set -euo pipefail
day-clone --repository daylily-sarek --destination {analysis_id!r} --executing-entity {executing_entity!r}
repo=/fsx/analysis_results/{executing_entity}/{analysis_id}/sarek
test -d "$repo"
cd "$repo"
test "$(git rev-parse HEAD)" = "d776c68b2d3b6ea6f3d5318777142e936e2c7d6b"
'''
result = run_shell(target.instance_id, region, script, profile=profile, as_user="ubuntu", timeout=900)
print(result.stdout)
PY
```

Apply the run-local patches required by the validated Sarek `0.7.379` DAY-EC run. These changes are made only inside the cloned pipeline checkout.

```bash
python - <<'PY'
import os
import shlex

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell

profile = os.environ["AWS_PROFILE"]
region = os.environ["REGION"]
cluster = os.environ["CLUSTER_NAME"]
analysis_id = os.environ["ANALYSIS_ID"]
executing_entity = os.environ["EXECUTING_ENTITY"]
target = resolve_headnode_instance_id(cluster, region, profile=profile)
script = r'''
set -euo pipefail
analysis_id=ANALYSIS_ID_PLACEHOLDER
executing_entity=EXECUTING_ENTITY_PLACEHOLDER
repo=/fsx/analysis_results/$executing_entity/$analysis_id/sarek
cd "$repo"
python3 - <<'REMOTE_PY'
from pathlib import Path

def replace_once(path, old, new):
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit("Expected patch target not found in " + str(path) + ": " + repr(old))
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

replace_once(
    Path("conf/daylily_ephemeral_cluster.config"),
    "def dataRoot          = '/fsx/data'",
    "def dataRoot          = '/fsx/references'",
)

replace_once(
    Path("subworkflows/local/bam_variant_calling_somatic_muse/main.nf"),
    """    dbsnp      // channel: [mandatory] [ dbsnp ]""",
    """    dbsnp_ch   // channel: [mandatory] [ dbsnp ]""",
)
replace_once(
    Path("subworkflows/local/bam_variant_calling_somatic_muse/main.nf"),
    """    TABIX_MUSE(dbsnp.map { vcf -> [ [id: 'dbsnp'], vcf] })""",
    """    TABIX_MUSE(dbsnp_ch.map { vcf -> [ [id: 'dbsnp'], vcf] })""",
)
replace_once(
    Path("subworkflows/local/bam_variant_calling_somatic_muse/main.nf"),
    """    dbsnp_tbi = TABIX_MUSE.out.tbi""",
    """    dbsnp_tbi_ch = TABIX_MUSE.out.tbi""",
)
replace_once(
    Path("subworkflows/local/bam_variant_calling_somatic_muse/main.nf"),
    """    def ch_dbsnp_with_tbi = dbsnp.combine(dbsnp_tbi.map { _meta, tbi -> tbi }).map { vcf, tbi -> [[id: 'dbsnp'], vcf, tbi] }.collect()""",
    """    ch_dbsnp_with_tbi = dbsnp_ch.combine(dbsnp_tbi_ch.map { _meta, dbsnp_index -> dbsnp_index }).map { dbsnp_vcf, dbsnp_index -> [[id: 'dbsnp'], dbsnp_vcf, dbsnp_index] }.collect()""",
)

for old, new in [
    ("    def somatic_with_key = ", "    somatic_with_key = "),
    ("    def germline_with_key = ", "    germline_with_key = "),
    ("    def matching_pairs = ", "    matching_pairs = "),
    ("    def branched = ", "    branched = "),
]:
    replace_once(Path("subworkflows/local/vcf_varlociraptor_somatic/main.nf"), old, new)

bwa_old = r"""    INDEX=`find -L ./ -name "*.amb" | sed 's/\\.amb\$//'`"""
bwa_new = r"""    INDEXES=`find -L ./ -maxdepth 2 -name "*.amb" | sed 's/\\.amb\$//' | sort`
    INDEX_COUNT=`printf '%s\\n' "\$INDEXES" | sed '/^\$/d' | wc -l`
    if [ "\$INDEX_COUNT" -ne 1 ]; then
        printf 'Expected exactly one BWA index prefix at depth <=2, found %s:\\n%s\\n' "\$INDEX_COUNT" "\$INDEXES" >&2
        exit 1
    fi
    INDEX="\$INDEXES"
"""

for path in [
    Path("modules/nf-core/bwa/mem/main.nf"),
    Path("modules/nf-core/bwamem2/mem/main.nf"),
]:
    replace_once(path, bwa_old, bwa_new)
REMOTE_PY
git diff -- conf/daylily_ephemeral_cluster.config subworkflows/local/bam_variant_calling_somatic_muse/main.nf subworkflows/local/vcf_varlociraptor_somatic/main.nf modules/nf-core/bwa/mem/main.nf modules/nf-core/bwamem2/mem/main.nf
'''.replace("ANALYSIS_ID_PLACEHOLDER", shlex.quote(analysis_id)).replace(
    "EXECUTING_ENTITY_PLACEHOLDER", shlex.quote(executing_entity)
)
result = run_shell(target.instance_id, region, script, profile=profile, as_user="ubuntu", timeout=900)
print(result.stdout)
PY
```

## 9. Launch The nf-core Pipeline

Use the bundled proof samplesheet:

```bash
export SAREK_INPUT=.test_data/data/test_samplesheet.csv
```

For real staged FASTQs, use the samplesheet created under the analysis directory:

```bash
export SAREK_INPUT="/fsx/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID/inputs/sarek_samplesheet.csv"
```

Launch in `tmux` on the headnode:

```bash
python - <<'PY'
import os
import shlex

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell

profile = os.environ["AWS_PROFILE"]
region = os.environ["REGION"]
cluster = os.environ["CLUSTER_NAME"]
analysis_id = os.environ["ANALYSIS_ID"]
executing_entity = os.environ["EXECUTING_ENTITY"]
sarek_input = os.environ["SAREK_INPUT"]
day_project = os.environ["DAY_PROJECT_NAME"]
target = resolve_headnode_instance_id(cluster, region, profile=profile)
script = r'''
set -euo pipefail
analysis_id=ANALYSIS_ID_PLACEHOLDER
executing_entity=EXECUTING_ENTITY_PLACEHOLDER
sarek_input=SAREK_INPUT_PLACEHOLDER
day_project=DAY_PROJECT_PLACEHOLDER
repo=/fsx/analysis_results/$executing_entity/$analysis_id/sarek
outdir=/fsx/analysis_results/$executing_entity/$analysis_id/sarek/results
workdir=/fsx/work/$executing_entity/sarek/$analysis_id/work
session=sarek_$analysis_id

mkdir -p "$outdir/pipeline_info" "$workdir" /fsx/resources/environments/containers/$executing_entity
cd "$repo"

cat > launch_sarek.sh <<'REMOTE_SH'
#!/usr/bin/env bash
set -euo pipefail
analysis_id="ANALYSIS_ID_PLACEHOLDER"
executing_entity="EXECUTING_ENTITY_PLACEHOLDER"
sarek_input="SAREK_INPUT_PLACEHOLDER"
day_project="DAY_PROJECT_PLACEHOLDER"
repo="/fsx/analysis_results/$executing_entity/$analysis_id/sarek"
outdir="/fsx/analysis_results/$executing_entity/$analysis_id/sarek/results"
workdir="/fsx/work/$executing_entity/sarek/$analysis_id/work"
attempt="$(date -u +%Y%m%dT%H%M%SZ)"
cd "$repo"

export PATH=/fsx/resources/environments/nextflow/24.10.5:/home/ubuntu/.local/bin:$PATH
export JAVA_CMD=/fsx/resources/environments/nextflow/java-21/bin/java
export NXF_VER=24.10.5
export NXF_WORK="$workdir"
export NXF_ANSI_LOG=false
export TERM=xterm
export DAYLILY_SLURM_QUEUE=i128
export DAYLILY_QUEUE_SIZE=1
export DAY_PROJECT="$day_project"
export project="$day_project"

nextflow -version
nextflow run . \
  -resume \
  -profile daylily \
  -with-report "$outdir/pipeline_info/execution_report_${attempt}.html" \
  -with-trace "$outdir/pipeline_info/trace_${attempt}.txt" \
  -with-timeline "$outdir/pipeline_info/timeline_${attempt}.html" \
  -with-dag "$outdir/pipeline_info/dag_${attempt}.html" \
  --input "$sarek_input" \
  --outdir "$outdir" \
  --genome DAYLILY.GRCh38 \
  --intervals /fsx/references/genomic_data/organism_references/H_sapiens/hg38_broad/hg38_broad_core.bed \
  --chr_dir /fsx/references/genomic_data/organism_references/H_sapiens/hg38_broad \
  --skip_tools baserecalibrator
REMOTE_SH
chmod 755 launch_sarek.sh

cat > run_sarek_tmux.sh <<'REMOTE_SH'
#!/usr/bin/env bash
set -euo pipefail
set +e
./launch_sarek.sh > tmux.log 2>&1
rc=$?
set -e
echo "$rc" > exit_code
exit "$rc"
REMOTE_SH
chmod 755 run_sarek_tmux.sh

tmux new-session -d -s "$session" ./run_sarek_tmux.sh
tmux display-message -p -t "$session" "session=#S"
'''.replace("ANALYSIS_ID_PLACEHOLDER", shlex.quote(analysis_id)).replace(
    "EXECUTING_ENTITY_PLACEHOLDER", shlex.quote(executing_entity)
).replace("SAREK_INPUT_PLACEHOLDER", shlex.quote(sarek_input)).replace(
    "DAY_PROJECT_PLACEHOLDER", shlex.quote(day_project)
)
result = run_shell(target.instance_id, region, script, profile=profile, as_user="ubuntu", timeout=180)
print(result.stdout)
PY
```

## 10. Monitor The Pipeline

From the local machine:

```bash
dyec headnode jobs \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

Inspect logs through the supported headnode session:

```bash
dyec headnode connect \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

On the headnode:

```bash
cd "/fsx/analysis_results/ubuntu/$ANALYSIS_ID/sarek"
tmux has-session -t "sarek_$ANALYSIS_ID" && tmux capture-pane -pt "sarek_$ANALYSIS_ID" -S -200 || true
tail -n 120 tmux.log
test -f exit_code && cat exit_code || true
PATH=/fsx/resources/environments/nextflow/24.10.5:/home/ubuntu/.local/bin:$PATH \
JAVA_CMD=/fsx/resources/environments/nextflow/java-21/bin/java \
NXF_VER=24.10.5 \
nextflow log
squeue -u ubuntu -o '%i %P %j %u %t %M %D %R'
exit
```

For direct Nextflow runs, `dyec workflow status` and `dyec workflow logs` are not authoritative unless the run was launched through `dyec workflow launch`. Use `dyec headnode jobs`, `tmux.log`, `.nextflow.log`, `exit_code`, and `nextflow log`.

## 11. Review Results

After `exit_code` is `0`, collect the result inventory:

```bash
python - <<'PY'
import os

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell

profile = os.environ["AWS_PROFILE"]
region = os.environ["REGION"]
cluster = os.environ["CLUSTER_NAME"]
analysis_id = os.environ["ANALYSIS_ID"]
executing_entity = os.environ["EXECUTING_ENTITY"]
target = resolve_headnode_instance_id(cluster, region, profile=profile)
script = f'''
set -euo pipefail
repo=/fsx/analysis_results/{executing_entity}/{analysis_id}/sarek
cd "$repo"
echo EXIT_CODE=$(cat exit_code)
echo SAREK_COMMIT=$(git rev-parse HEAD)
echo NEXTFLOW_VERSION_BEGIN
PATH=/fsx/resources/environments/nextflow/24.10.5:/home/ubuntu/.local/bin:$PATH JAVA_CMD=/fsx/resources/environments/nextflow/java-21/bin/java NXF_VER=24.10.5 nextflow -version
echo NEXTFLOW_VERSION_END
echo PIPELINE_INFO
find results/pipeline_info -maxdepth 1 -type f -printf '%s %p\\n' | sort -k2
echo REPORTS
find results -maxdepth 4 -type f \\( -name '*.html' -o -name '*.txt' -o -name '*.json' -o -name '*.cram' -o -name '*.crai' \\) -printf '%s %p\\n' | sort -k2 | sed -n '1,240p'
'''
result = run_shell(target.instance_id, region, script, profile=profile, as_user="ubuntu", timeout=300)
print(result.stdout)
PY
```

Expected proof artifacts include:

- `/fsx/analysis_results/<executing_entity>/<analysis_id>/sarek/.nextflow.log`
- `sarek/results/pipeline_info/execution_report_*.html`
- `sarek/results/pipeline_info/trace_*.txt`
- `sarek/results/pipeline_info/timeline_*.html`
- `sarek/results/pipeline_info/dag_*.html`
- `sarek/results/multiqc/multiqc_report.html`

## 12. Export The Completed Analysis Directory Through DRA

Export the parent analysis directory, not the nested `sarek/results` directory:

```bash
dyec export \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --source-path "/fsx/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID" \
  --destination-s3-uri "$EXPORT_S3_URI" \
  --output-dir "$EXPORT_DIR"

cat "$EXPORT_DIR/fsx_export.yaml"
```

The receipt must show:

- `status: success`
- `detached: true`
- `delete_data_in_file_system: false`
- `source_path: /analysis_results/<executing_entity>/<analysis_id>/`
- `destination_s3_uri` ending in `<executing_entity>/<analysis_id>/`

Verify the exported S3 prefix:

```bash
aws s3 ls "$EXPORT_S3_URI" \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --recursive \
  --summarize

aws s3api head-object \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --bucket "${ANALYSIS_RESULTS_S3_URI#s3://}" \
  --key "analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID/sarek/results/multiqc/multiqc_report.html"
```

If the analysis-results S3 URI contains a parent prefix after the bucket name, set `EXPORT_BUCKET` and `EXPORT_KEY_PREFIX` explicitly before running S3 checks:

```bash
export EXPORT_BUCKET=<analysis-results-bucket>
export EXPORT_KEY_PREFIX="analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID"
aws s3api head-object \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --bucket "$EXPORT_BUCKET" \
  --key "$EXPORT_KEY_PREFIX/sarek/results/multiqc/multiqc_report.html"
```

## 13. Public Report Link

Do not create, mutate, or publish a CloudFront distribution from this runbook. Public docs may include a report URL only when an existing no-auth URL has already been approved for publication and verified with HTTP 200.

```bash
export REPORT_URL=https://<public-report-domain>/<path>/multiqc_report.html
curl -sS -I "$REPORT_URL" | sed -n '1,20p'
```

Acceptance for a public documentation link:

- unauthenticated request returns `HTTP/2 200` or `HTTP/1.1 200`
- no credentials, signed URL, Basic auth, private distribution id, or internal-only URL pattern is required
- the report is meant for public benchmark inspection
- the verified URL is recorded with the benchmark/export evidence

If no existing public no-auth 200 URL is available, record the link as blocked. Creating or repairing public CloudFront exposure requires a separate approval and belongs in an internal execution ledger, not in public operator docs.

## 14. Shut Down The Pipeline And Cluster

If the pipeline is still running and you intend to cancel it, stop the tmux session explicitly on the headnode. Do not do this for a run you still want to complete.

```bash
dyec headnode connect \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

On the headnode:

```bash
tmux has-session -t "sarek_$ANALYSIS_ID" && tmux kill-session -t "sarek_$ANALYSIS_ID" || true
squeue -u ubuntu -o '%i %P %j %u %t %M %D %R'
exit
```

If you attached a run DRA and the cluster will remain up, detach the run mount after the pipeline is done:

```bash
dyec --json mounts delete \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME" \
  --mount-id "$RUN_MOUNT_ID" \
  --wait \
  --timeout-seconds 3600
```

Before deleting the cluster, verify export and CloudFront one more time:

```bash
grep -E 'status:|detached:|delete_data_in_file_system:|destination_s3_uri:' "$EXPORT_DIR/fsx_export.yaml"

aws s3api head-object \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --bucket "$EXPORT_BUCKET" \
  --key "$CF_REPORT_PATH"

curl -sS -I "$CF_REPORT_URL" | sed -n '1,20p'
```

Prepare deletion:

```bash
dyec delete --dry-run \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

After the dry run shows the exact cluster and resources that will be removed, run the live delete only when the destructive action has been explicitly approved:

```bash
dyec delete \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --cluster "$CLUSTER_NAME"
```

Confirm the cluster is gone:

```bash
dyec cluster list \
  --profile "$AWS_PROFILE" \
  --region "$REGION" \
  --verbose
```

## Validated Sarek Proof Run

The validated run from `blahab44` used:

- Analysis id: `sarek-nextflow-20260527T052431Z`
- Sarek checkout: `/fsx/analysis_results/ubuntu/sarek-nextflow-20260527T052431Z/sarek`
- Work root: `/fsx/work/ubuntu/sarek/sarek-nextflow-20260527T052431Z/work`
- Sarek commit: `d776c68b2d3b6ea6f3d5318777142e936e2c7d6b`
- Nextflow: `24.10.5 build 5935`
- Final Nextflow row: `romantic_golick`, `OK`, `17m 21s`
- Main outputs: `.nextflow.log`, `results/pipeline_info/execution_report_20260527T064141Z.html`, `results/pipeline_info/trace_20260527T064141Z.txt`, `results/pipeline_info/timeline_20260527T064141Z.html`, `results/pipeline_info/dag_20260527T064141Z.html`, `results/multiqc/multiqc_report.html`, and `results/preprocessing/markduplicates/HG002/HG002.md.cram`

## Hard-Fail Conditions

Stop and fix the concrete cause instead of adding fallback behavior when any of these occur:

- `dyec preflight` fails.
- Headnode access is not `ubuntu`.
- Required FSx paths or reference files are missing.
- `daylily-sarek.default_ref` is not `0.7.379`.
- `nextflow -version` is not `24.10.5`.
- The Sarek checkout is not commit `d776c68b2d3b6ea6f3d5318777142e936e2c7d6b`.
- The run-local patch targets are missing or already changed.
- The Sarek samplesheet is missing, malformed, or points at nonexistent FASTQs.
- Slurm jobs disappear without `.exitcode` evidence in their Nextflow work directories.
- `exit_code` is absent or nonzero after tmux stops.
- `dyec export` receipt is not `status: success` and `detached: true`.
- Export destination does not end in `<executing_entity>/<analysis_id>/`.
- CloudFront authenticated verification returns anything other than `200` for the intended report.
