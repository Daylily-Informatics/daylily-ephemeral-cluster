# Running Nextflow Workflows On DAY-EC

This runbook covers Nextflow workflows registered in the DAY-EC repository catalog and launched from a DAY-EC ParallelCluster headnode.

## Catalog Entries

The source catalog is `config/daylily_pipeline_command_catalog.yaml`. The packaged copy at `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml` must be byte-for-byte identical.

- `illumina_bclconvert` and `illumina_run_qc_bclconvert` are nf-core BCL Convert command rows that run through the DAY-EC workflow launcher.
- `daylily-sarek` is a repository row. It intentionally has `analysis_commands: []`; clone it with `day-clone` and run Nextflow directly.
- `daylily-sarek.default_ref` is pinned to `0.7.379`, which resolves to Sarek commit `d776c68b2d3b6ea6f3d5318777142e936e2c7d6b`.

## Local Activation And AWS Context

Run local DAY-EC commands from the repo root:

```bash
source ./activate
export AWS_PROFILE=lsmc
export AWS_REGION=us-west-2
export CLUSTER_NAME=blahab44
```

All headnode commands must run through DAY-EC SSM helpers as `ubuntu` or through `dyec headnode connect`, which lands in an `ubuntu` bash login shell. Do not use raw SSH, root shells, or ad hoc `aws ssm send-command` payloads.

Refresh the headnode repository catalog before cloning from an existing cluster:

```bash
python - <<'PY'
from pathlib import Path

from daylily_ec.aws.ssm import resolve_headnode_instance_id, write_remote_text

profile = "lsmc"
region = "us-west-2"
cluster = "blahab44"
target = resolve_headnode_instance_id(cluster, region, profile=profile)
content = Path("config/daylily_pipeline_command_catalog.yaml").read_text(encoding="utf-8")
write_remote_text(
    target.instance_id,
    region,
    "/home/ubuntu/.config/daylily/daylily_pipeline_command_catalog.yaml",
    content,
    profile=profile,
    as_user="ubuntu",
)
print(target.instance_id)
PY
```

## Headnode Preflight

Run this read-only preflight before installing or launching anything:

```bash
python - <<'PY'
from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell

profile = "lsmc"
region = "us-west-2"
cluster = "blahab44"
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

This must fail hard for missing paths or commands. Do not create `/fsx/data` symlinks or rely on inferred reference locations.

## Install Pinned Nextflow

Sarek `0.7.379` declares `nextflowVersion = !>=24.10.5`. Install Nextflow `24.10.5` explicitly and run it with Java 21; Java 25 was too new for this Sarek/Groovy compile path.

```bash
python - <<'PY'
from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell

profile = "lsmc"
region = "us-west-2"
cluster = "blahab44"
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

If `nextflow -version` reports anything other than `24.10.5`, stop and fix the install directly.

## Clone And Patch Sarek

Create a unique run id:

```bash
export RUN_ID=sarek-nextflow-$(date -u +%Y%m%dT%H%M%SZ)
```

Clone through the corrected catalog and apply only run-local patches in the cloned Sarek checkout:

```bash
python - <<'PY'
import os

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell

profile = "lsmc"
region = "us-west-2"
cluster = "blahab44"
run_id = os.environ["RUN_ID"]
target = resolve_headnode_instance_id(cluster, region, profile=profile)
script = r'''
set -euo pipefail
run_id="RUN_ID_PLACEHOLDER"
day-clone --repository daylily-sarek --destination "$run_id" --executing-entity ubuntu
repo=/fsx/analysis_results/ubuntu/$run_id/sarek
test -d "$repo"
cd "$repo"
test "$(git rev-parse HEAD)" = "d776c68b2d3b6ea6f3d5318777142e936e2c7d6b"
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
'''.replace("RUN_ID_PLACEHOLDER", run_id)
result = run_shell(target.instance_id, region, script, profile=profile, as_user="ubuntu", timeout=900)
print(result.stdout)
PY
```

These patches are run-local. Do not commit them in the Sarek checkout, and do not add compatibility aliases such as `/fsx/data`.

## Launch Sarek

The proof run uses the bundled Sarek test samplesheet:

```text
.test_data/data/test_samplesheet.csv
```

Launch in `tmux` so the SSM command can return while Nextflow runs:

Set both `DAY_PROJECT` and lowercase `project`. The Sarek profile reads `DAY_PROJECT`, while the DAY-EC Slurm budget wrapper reads lowercase `project` before falling back to parsing `sbatch --comment`.
Use `DAYLILY_QUEUE_SIZE=1` for this proof run so missing `i128` dynamic capacity does not fan out multiple BWA jobs onto nodes that cannot start.

```bash
python - <<'PY'
import os

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell

profile = "lsmc"
region = "us-west-2"
cluster = "blahab44"
run_id = os.environ["RUN_ID"]
target = resolve_headnode_instance_id(cluster, region, profile=profile)
script = r'''
set -euo pipefail
run_id="RUN_ID_PLACEHOLDER"
repo=/fsx/analysis_results/ubuntu/$run_id/sarek
outdir=/fsx/analysis_results/ubuntu/$run_id/sarek/results
workdir=/fsx/work/ubuntu/sarek/$run_id/work
session=sarek_$run_id
mkdir -p "$outdir/pipeline_info" "$workdir" /fsx/resources/environments/containers/ubuntu
cd "$repo"
cat > launch_sarek.sh <<'REMOTE_SH'
#!/usr/bin/env bash
set -euo pipefail
run_id="RUN_ID_PLACEHOLDER"
repo="/fsx/analysis_results/ubuntu/$run_id/sarek"
outdir="/fsx/analysis_results/ubuntu/$run_id/sarek/results"
workdir="/fsx/work/ubuntu/sarek/$run_id/work"
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
export DAY_PROJECT=da-us-west-2d-blahab44
export project=da-us-west-2d-blahab44
nextflow -version
nextflow run . \
  -resume \
  -profile daylily \
  -with-report "$outdir/pipeline_info/execution_report_${attempt}.html" \
  -with-trace "$outdir/pipeline_info/trace_${attempt}.txt" \
  -with-timeline "$outdir/pipeline_info/timeline_${attempt}.html" \
  -with-dag "$outdir/pipeline_info/dag_${attempt}.html" \
  --input .test_data/data/test_samplesheet.csv \
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
'''.replace("RUN_ID_PLACEHOLDER", run_id)
result = run_shell(target.instance_id, region, script, profile=profile, as_user="ubuntu", timeout=180)
print(result.stdout)
PY
```

## Monitor, Resume, And Collect Artifacts

Monitor Slurm and the session:

```bash
dyec headnode jobs --profile "$AWS_PROFILE" --region "$AWS_REGION" --cluster "$CLUSTER_NAME"
dyec headnode connect --profile "$AWS_PROFILE" --region "$AWS_REGION" --cluster "$CLUSTER_NAME"
```

Inside the headnode shell:

```bash
cd /fsx/analysis_results/ubuntu/$RUN_ID/sarek
tail -n 100 tmux.log
tmux has-session -t "sarek_$RUN_ID" && tmux capture-pane -pt "sarek_$RUN_ID" -S -200
test -f exit_code && cat exit_code
nextflow log
find results/pipeline_info -maxdepth 1 -type f -print | sort
```

Resume only after fixing the concrete failure:

```bash
cd /fsx/analysis_results/ubuntu/$RUN_ID/sarek
export PATH=/fsx/resources/environments/nextflow/24.10.5:/home/ubuntu/.local/bin:$PATH
export JAVA_CMD=/fsx/resources/environments/nextflow/java-21/bin/java
export NXF_VER=24.10.5
export NXF_WORK=/fsx/work/ubuntu/sarek/$RUN_ID/work
export DAYLILY_SLURM_QUEUE=i128
export DAYLILY_QUEUE_SIZE=1
export DAY_PROJECT=da-us-west-2d-blahab44
export project=da-us-west-2d-blahab44
attempt=$(date -u +%Y%m%dT%H%M%SZ)
nextflow run . -resume -profile daylily \
  -with-report "results/pipeline_info/execution_report_${attempt}.html" \
  -with-trace "results/pipeline_info/trace_${attempt}.txt" \
  -with-timeline "results/pipeline_info/timeline_${attempt}.html" \
  -with-dag "results/pipeline_info/dag_${attempt}.html" \
  --input .test_data/data/test_samplesheet.csv \
  --outdir /fsx/analysis_results/ubuntu/$RUN_ID/sarek/results \
  --genome DAYLILY.GRCh38 \
  --intervals /fsx/references/genomic_data/organism_references/H_sapiens/hg38_broad/hg38_broad_core.bed \
  --chr_dir /fsx/references/genomic_data/organism_references/H_sapiens/hg38_broad \
  --skip_tools baserecalibrator
```

Successful proof requires:

- `exit_code` contains `0`.
- `.nextflow.log` is present.
- `results/pipeline_info/` contains the execution report, trace, timeline, DAG, and nf-core software version files.
- The Sarek checkout resolves to commit `d776c68b2d3b6ea6f3d5318777142e936e2c7d6b`.

## Validated Proof Run

The `blahab44` validation run completed successfully with these handles:

- Run id: `sarek-nextflow-20260527T052431Z`
- Sarek checkout: `/fsx/analysis_results/ubuntu/sarek-nextflow-20260527T052431Z/sarek`
- Work root: `/fsx/work/ubuntu/sarek/sarek-nextflow-20260527T052431Z/work`
- Sarek commit: `d776c68b2d3b6ea6f3d5318777142e936e2c7d6b`
- Nextflow version: `24.10.5 build 5935`
- Final Nextflow row: run name `romantic_golick`, status `OK`, duration `17m 21s`
- Key artifacts: `.nextflow.log`, `results/pipeline_info/execution_report_20260527T064141Z.html`, `results/pipeline_info/trace_20260527T064141Z.txt`, `results/pipeline_info/timeline_20260527T064141Z.html`, `results/pipeline_info/dag_20260527T064141Z.html`, `results/multiqc/multiqc_report.html`, and `results/preprocessing/markduplicates/HG002/HG002.md.cram`

## Hard-Fail Policy

Stop instead of patching around these conditions:

- `daylily-sarek.default_ref` does not resolve to `0.7.379`.
- The headnode command is not running as `ubuntu`.
- `nextflow -version` does not report `24.10.5`.
- Java is not the pinned Java 21 runtime used by the wrapper.
- Required reference files are missing under `/fsx/references`.
- The samplesheet is missing or malformed.
- The Sarek profile no longer contains the exact `/fsx/data` line expected by the run-local patch.
- The run-local source patch targets are missing or already changed.
- The target clone directory already exists.

## Upstream References

- [Nextflow install](https://docs.seqera.io/nextflow/install)
- [Nextflow version selection](https://docs.seqera.io/nextflow/updating-nextflow)
- [nf-core/sarek 3.6.0](https://nf-co.re/sarek/3.6.0/)
- [Sarek usage](https://nf-co.re/sarek/dev/docs/usage)
