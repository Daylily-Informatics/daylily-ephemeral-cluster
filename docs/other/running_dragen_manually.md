# Running DRAGEN Manually On The Standalone EC2 Instance

This is the quick guide for rerunning the standalone DRAGEN EC2 path that was
used for the NA19235 SMN12 pangenome validation. It is intentionally explicit:
missing instance IDs, keys, inputs, references, license credentials, or S3
destinations are hard blockers.

## Known Handles

- AWS profile: `lsmc`
- Region: `us-west-2`
- Instance: `i-0d75af02251c65b84`
- Name tag: `jem-dragen-x3`
- Instance type: `f2.6xlarge`
- AMI: `ami-044bef021cb86a54c`
- Login user: `ec2-user`
- SSH key: `~/.ssh/jem-dragen-jul.pem`
- Local license file: `~/.config/dragen/lic_creds.txt`
- Remote license file: `/home/ec2-user/.config/dragen/lic_creds.txt`
- Runtime disk: `/ephemeral`
- Preserved staging root: `/home/ec2-user/ephem_stg`
- Successful result root used previously:
  `s3://lsmc-dayoa-analysis-results-usw2/dragen/smn12_na19235_pangenome_20260706/ec2/`

Do not print license credential contents. Copy credentials by file transfer or
stdin-only scripts, and verify only owner, mode, size, and path.

## Start And Connect

Run these commands from the laptop.

```bash
cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate

aws --profile lsmc --region us-west-2 ec2 describe-instances \
  --instance-ids i-0d75af02251c65b84 \
  --query 'Reservations[].Instances[].{InstanceId:InstanceId,State:State.Name,Name:Tags[?Key==`Name`]|[0].Value,Type:InstanceType,PublicIp:PublicIpAddress,PrivateIp:PrivateIpAddress,ImageId:ImageId}' \
  --output table
```

If the instance is `stopped`, start it and wait for SSH readiness.

```bash
aws --profile lsmc --region us-west-2 ec2 start-instances \
  --instance-ids i-0d75af02251c65b84

aws --profile lsmc --region us-west-2 ec2 wait instance-running \
  --instance-ids i-0d75af02251c65b84

PUBLIC_IP=$(
  aws --profile lsmc --region us-west-2 ec2 describe-instances \
    --instance-ids i-0d75af02251c65b84 \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text
)

chmod 400 ~/.ssh/jem-dragen-jul.pem
ssh -i ~/.ssh/jem-dragen-jul.pem "ec2-user@${PUBLIC_IP}"
```

The correct login user is `ec2-user`, not `ubuntu` and not `root`.

## Initial Checks On The Instance

Run these after SSH login.

```bash
set -euo pipefail

hostname
whoami
/opt/edico/bin/dragen --version
df -h /ephemeral
du -sh /home/ec2-user/ephem_stg || true
stat -c 'license=%U:%G:%a:%s:%n' /home/ec2-user/.config/dragen/lic_creds.txt
```

Expected DRAGEN version for the validated AMI was:

```text
DRAGEN Host Software Version 4.5.4
dragen Version 13.031.818.4.5.4
```

If the remote license file is missing, copy the local file from the laptop:

```bash
PUBLIC_IP=$(
  aws --profile lsmc --region us-west-2 ec2 describe-instances \
    --instance-ids i-0d75af02251c65b84 \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text
)

ssh -i ~/.ssh/jem-dragen-jul.pem "ec2-user@${PUBLIC_IP}" \
  'mkdir -p ~/.config/dragen && chmod 700 ~/.config/dragen'

scp -i ~/.ssh/jem-dragen-jul.pem \
  ~/.config/dragen/lic_creds.txt \
  "ec2-user@${PUBLIC_IP}:/home/ec2-user/.config/dragen/lic_creds.txt"

ssh -i ~/.ssh/jem-dragen-jul.pem "ec2-user@${PUBLIC_IP}" \
  'chmod 600 ~/.config/dragen/lic_creds.txt && stat -c "license=%U:%G:%a:%s:%n" ~/.config/dragen/lic_creds.txt'
```

## Restore Runtime Inputs

The validated run restored one sample from `/home/ec2-user/ephem_stg` into
`/ephemeral`. This fails immediately if a required input is missing or if DRAGEN
is already running.

```bash
cat > /home/ec2-user/restore_na19235_runtime.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

SAMPLE=NA19235
STAGE_ROOT=/home/ec2-user/ephem_stg
RUNTIME_ROOT=/ephemeral
LOG_DIR=/home/ec2-user/dragen_na19235_ec2_logs
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOG_FILE="${LOG_DIR}/restore_${STAMP}.log"

mkdir -p "${LOG_DIR}"
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "restore_started_utc=${STAMP}"
echo "host=$(hostname)"
echo "user=$(whoami)"

if pgrep -a dragen >/dev/null 2>&1; then
  echo "ERROR: active DRAGEN process exists; refusing to alter runtime inputs." >&2
  pgrep -a dragen >&2
  exit 11
fi

required_paths=(
  "${STAGE_ROOT}/hg38-alt_masked.graph.cnv.hla.methyl_cg.rna_v6"
  "${STAGE_ROOT}/hg38_1000G_phase1.snps.high_confidence.vcf.gz"
  "${STAGE_ROOT}/smn12_samples/${SAMPLE}/${SAMPLE}.R1.fastq.gz"
  "${STAGE_ROOT}/smn12_samples/${SAMPLE}/${SAMPLE}.R2.fastq.gz"
  "/home/ec2-user/.config/dragen/lic_creds.txt"
)

for path in "${required_paths[@]}"; do
  if [ ! -e "${path}" ]; then
    echo "ERROR: missing required path ${path}" >&2
    exit 12
  fi
done

mkdir -p \
  "${RUNTIME_ROOT}/hg38-alt_masked.graph.cnv.hla.methyl_cg.rna_v6" \
  "${RUNTIME_ROOT}/smn12_samples/${SAMPLE}" \
  "${RUNTIME_ROOT}/output"

rsync -a --info=progress2 \
  "${STAGE_ROOT}/hg38-alt_masked.graph.cnv.hla.methyl_cg.rna_v6/" \
  "${RUNTIME_ROOT}/hg38-alt_masked.graph.cnv.hla.methyl_cg.rna_v6/"

rsync -a --info=progress2 \
  "${STAGE_ROOT}/smn12_samples/${SAMPLE}/${SAMPLE}.R1.fastq.gz" \
  "${STAGE_ROOT}/smn12_samples/${SAMPLE}/${SAMPLE}.R2.fastq.gz" \
  "${RUNTIME_ROOT}/smn12_samples/${SAMPLE}/"

rsync -a --info=progress2 \
  "${STAGE_ROOT}/hg38_1000G_phase1.snps.high_confidence.vcf.gz" \
  "${RUNTIME_ROOT}/"

chmod 600 /home/ec2-user/.config/dragen/lic_creds.txt

echo "runtime_inventory_begin"
df -h "${RUNTIME_ROOT}"
du -sh \
  "${RUNTIME_ROOT}/hg38-alt_masked.graph.cnv.hla.methyl_cg.rna_v6" \
  "${RUNTIME_ROOT}/smn12_samples/${SAMPLE}" \
  "${RUNTIME_ROOT}/hg38_1000G_phase1.snps.high_confidence.vcf.gz"
stat -c "license=%U:%G:%a:%s:%n" /home/ec2-user/.config/dragen/lic_creds.txt
ls -lh "${RUNTIME_ROOT}/smn12_samples/${SAMPLE}/"
echo "runtime_inventory_end"
echo "restore_finished_utc=$(date -u +%Y%m%dT%H%M%SZ)"
EOF

chmod +x /home/ec2-user/restore_na19235_runtime.sh
tmux new-session -d -s dragen_na19235_restore_manual 'bash -il'
tmux send-keys -t dragen_na19235_restore_manual '/home/ec2-user/restore_na19235_runtime.sh; exec bash -il' Enter
tmux capture-pane -pt dragen_na19235_restore_manual -S -200
```

## Run DRAGEN

Run the full pangenome/all-tool command in a persistent tmux session.

```bash
cat > /home/ec2-user/run_na19235_dragen.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

SAMPLE=NA19235
OUTDIR=/ephemeral/output/${SAMPLE}_pangenome_MA_VC_all_callers
LOG_DIR=/home/ec2-user/dragen_na19235_ec2_logs
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOG_FILE="${LOG_DIR}/run_${STAMP}.log"
EXIT_FILE="${LOG_DIR}/run_${STAMP}.exit"
LICENSE_FILE=/home/ec2-user/.config/dragen/lic_creds.txt
REF_DIR=/ephemeral/hg38-alt_masked.graph.cnv.hla.methyl_cg.rna_v6
R1=/ephemeral/smn12_samples/${SAMPLE}/${SAMPLE}.R1.fastq.gz
R2=/ephemeral/smn12_samples/${SAMPLE}/${SAMPLE}.R2.fastq.gz
POPVCF=/ephemeral/hg38_1000G_phase1.snps.high_confidence.vcf.gz

mkdir -p "${LOG_DIR}" "${OUTDIR}"
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "run_started_utc=${STAMP}"
echo "host=$(hostname)"
echo "user=$(whoami)"
/opt/edico/bin/dragen --version
df -h /ephemeral
stat -c "license=%U:%G:%a:%s:%n" "${LICENSE_FILE}"

for path in "${REF_DIR}" "${R1}" "${R2}" "${POPVCF}" "${LICENSE_FILE}"; do
  if [ ! -e "${path}" ]; then
    echo "ERROR: missing required path ${path}" >&2
    exit 21
  fi
done

set +e
/opt/edico/bin/dragen -f \
  -r "${REF_DIR}/" \
  -1 "${R1}" \
  -2 "${R2}" \
  --RGID "${SAMPLE}" \
  --RGSM "${SAMPLE}" \
  --enable-map-align true \
  --enable-map-align-output true \
  --enable-duplicate-marking true \
  --enable-variant-caller true \
  --vc-emit-ref-confidence GVCF \
  --vc-enable-vcf-output true \
  --enable-cnv true \
  --cnv-enable-self-normalization true \
  --cnv-population-b-allele-vcf "${POPVCF}" \
  --enable-sv true \
  --enable-targeted true \
  --enable-star-allele true \
  --repeat-genotype-enable true \
  --repeat-genotype-use-catalog default \
  --enable-hla true \
  --enable-mrjd true \
  --mrjd-enable-high-sensitivity true \
  --output-file-prefix "${SAMPLE}" \
  --output-directory "${OUTDIR}" \
  --lic-credentials "${LICENSE_FILE}"
rc=$?
set -e

echo "DRAGEN_EXIT_CODE=${rc}" | tee "${EXIT_FILE}"
echo "run_finished_utc=$(date -u +%Y%m%dT%H%M%SZ)"
find "${OUTDIR}" -maxdepth 2 -type f -printf '%s\t%p\n' | sort -nr | head -200 || true
exit "${rc}"
EOF

chmod +x /home/ec2-user/run_na19235_dragen.sh
tmux new-session -d -s dragen_na19235_run_manual 'bash -il'
tmux send-keys -t dragen_na19235_run_manual '/home/ec2-user/run_na19235_dragen.sh; exec bash -il' Enter
```

Monitor without disrupting the session:

```bash
tmux capture-pane -pt dragen_na19235_run_manual -S -200
pgrep -a dragen || true
tail -50 /home/ec2-user/dragen_na19235_ec2_logs/run_*.log
cat /home/ec2-user/dragen_na19235_ec2_logs/run_*.exit
```

The successful NA19235 run reported:

- `DRAGEN_EXIT_CODE=0`
- `DRAGEN finished normally`
- Runtime: `01:08:57.048`
- Average WGS coverage: `36.11x`
- CNV coverage: `33.82x`
- Sample sex: `FEMALE`
- Post-filter total small variants: `6,153,361`
- Post-filter SNPs: `4,992,914`

## Export Results

Use an explicit destination. Do not infer a bucket or prefix.

```bash
SAMPLE=NA19235
RUN_DIR=/ephemeral/output/${SAMPLE}_pangenome_MA_VC_all_callers
LOG_DIR=/home/ec2-user/dragen_na19235_ec2_logs
S3_ROOT=s3://lsmc-dayoa-analysis-results-usw2/dragen/smn12_na19235_pangenome_20260706/ec2

test -d "${RUN_DIR}"
test -d "${LOG_DIR}"

aws s3 sync "${RUN_DIR}/" "${S3_ROOT}/output/${SAMPLE}_pangenome_MA_VC_all_callers/" \
  --only-show-errors

aws s3 sync "${LOG_DIR}/" "${S3_ROOT}/logs/dragen_na19235_ec2_logs/" \
  --only-show-errors

aws s3 ls "${S3_ROOT}/" --recursive --summarize
```

If the instance does not have usable AWS credentials, do not write static
credentials to disk on the instance. Use a short-lived STS session passed over
SSH stdin, or export through the laptop after confirming the size/time tradeoff.

## Check Output Metrics

On the instance:

```bash
OUTDIR=/ephemeral/output/NA19235_pangenome_MA_VC_all_callers

cat "${OUTDIR}/NA19235.vc_metrics.csv"
cat "${OUTDIR}/NA19235.gvcf_metrics.csv"
tail -100 /home/ec2-user/dragen_na19235_ec2_logs/run_*.log
```

From the laptop against S3:

```bash
aws --profile lsmc s3 cp \
  s3://lsmc-dayoa-analysis-results-usw2/dragen/smn12_na19235_pangenome_20260706/ec2/output/NA19235_pangenome_MA_VC_all_callers/NA19235.vc_metrics.csv -

aws --profile lsmc s3 cp \
  s3://lsmc-dayoa-analysis-results-usw2/dragen/smn12_na19235_pangenome_20260706/ec2/logs/dragen_na19235_ec2_logs/run_20260707T071351Z.exit -
```

This manual DRAGEN run emits variant-call counts and DRAGEN QC metrics. It does
not by itself emit SNV F-score data. F-score requires a separate truth-set
comparison step such as `hap.py` or `rtg vcfeval`; if no benchmark/truth,
precision, recall, or f-score artifacts are present, report that F-score was not
returned.

## Benchmark With hap.py Or RTG vcfeval

Do not run an F-score benchmark unless the truth VCF and confident-region BED
match the same sample, genome build, and contig naming as the DRAGEN query VCF.
A GIAB HG002/HG003/HG004 truth set is not a truth set for `NA19235`.

If an explicit `NA19235` truth set becomes available, the command shape is:

```bash
QUERY_VCF=/ephemeral/output/NA19235_pangenome_MA_VC_all_callers/NA19235.hard-filtered.vcf.gz
TRUTH_VCF=/path/to/NA19235.truth.vcf.gz
TRUTH_BED=/path/to/NA19235.confident.bed
REF_FASTA=/ephemeral/hg38-alt_masked.graph.cnv.hla.methyl_cg.rna_v6/hash_table.fa
OUT_PREFIX=/home/ec2-user/dragen_na19235_ec2_logs/happy/NA19235.hard-filtered

test -s "${QUERY_VCF}"
test -s "${QUERY_VCF}.tbi"
test -s "${TRUTH_VCF}"
test -s "${TRUTH_VCF}.tbi"
test -s "${TRUTH_BED}"
test -s "${REF_FASTA}"

mkdir -p "$(dirname "${OUT_PREFIX}")"

hap.py "${TRUTH_VCF}" "${QUERY_VCF}" \
  -f "${TRUTH_BED}" \
  -r "${REF_FASTA}" \
  -o "${OUT_PREFIX}" \
  --engine=vcfeval \
  --threads=16

cat "${OUT_PREFIX}.summary.csv"
```

The equivalent RTG command shape is:

```bash
QUERY_VCF=/ephemeral/output/NA19235_pangenome_MA_VC_all_callers/NA19235.hard-filtered.vcf.gz
TRUTH_VCF=/path/to/NA19235.truth.vcf.gz
TRUTH_BED=/path/to/NA19235.confident.bed
RTG_SDF=/path/to/hg38.sdf
OUT_DIR=/home/ec2-user/dragen_na19235_ec2_logs/vcfeval/NA19235.hard-filtered

test -s "${QUERY_VCF}"
test -s "${QUERY_VCF}.tbi"
test -s "${TRUTH_VCF}"
test -s "${TRUTH_VCF}.tbi"
test -s "${TRUTH_BED}"
test -d "${RTG_SDF}"

rtg vcfeval \
  -b "${TRUTH_VCF}" \
  -c "${QUERY_VCF}" \
  -t "${RTG_SDF}" \
  -e "${TRUTH_BED}" \
  -o "${OUT_DIR}"

cat "${OUT_DIR}/summary.txt"
```

### NA19235 Benchmark Attempt On 2026-07-08

This was the direct check against the completed NA19235 DRAGEN run:

```bash
command -v hap.py || true
command -v vcfeval || true
command -v rtg || true
command -v bcftools || true
command -v tabix || true
command -v bgzip || true

find /home/ec2-user/ephem_stg /ephemeral -maxdepth 8 -type f \
  \( -iname "*NA19235*truth*" \
     -o -iname "*NA19235*.bed" \
     -o -iname "*NA19235*.vcf.gz" \
     -o -iname "*benchmark*" \
     -o -iname "*vcfeval*" \
     -o -iname "*hap.py*" \) \
  -printf "%s\t%p\n" 2>/dev/null | sort -k2 | head -200
```

Result:

```text
host=ip-172-31-23-91.us-west-2.compute.internal
user=ec2-user
tools_begin
hap.py=
vcfeval=
rtg=
bcftools=
tabix=
bgzip=
tools_end
candidate_files_begin
candidate_files_end
```

The project reference bucket check also found GIAB truth directories for
`HG001` through `HG007`, but no `NA19235` truth under:

```text
s3://lsmc-dayoa-references-usw2/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/
```

The directory listing there is:

```text
HG001/
HG002/
HG003/
HG004/
HG005/
HG006/
HG007/
HG2/
```

Conclusion: no SNV F-score was produced for the NA19235 DRAGEN VCF in this
attempt. The benchmark was blocked before execution because both required
benchmark software and a sample-matched `NA19235` truth VCF/confident BED were
absent from the checked runtime/reference locations. Installing `hap.py` or RTG
alone would not make the F-score meaningful without sample-matched truth data.

## HG002 Manual Rerun On 2026-07-08

This rerun used the already-running standalone DRAGEN EC2 instance
`i-0d75af02251c65b84` and the preserved staging root
`/home/ec2-user/ephem_stg`.

Original HG002 staging evidence on the instance was in:

```text
/home/ec2-user/ephem_stg/dragen_hg002_parallel_stage_20260702T102048Z.log
/home/ec2-user/ephem_stg/dragen_hg002_refdir_extract_20260702T104625Z.log
/home/ec2-user/ephem_stg/dragen_hg002_stage_20260702T100827Z.log
```

The original HG002 source URLs recorded in those logs were:

```text
https://ilmn-dragen-giab-samples.s3.us-east-1.amazonaws.com/WGS/precisionFDA_v2_HG002/HG002.novaseq.pcr-free.35x.R1.fastq.gz
https://ilmn-dragen-giab-samples.s3.us-east-1.amazonaws.com/WGS/precisionFDA_v2_HG002/HG002.novaseq.pcr-free.35x.R2.fastq.gz
https://webdata.illumina.com/downloads/software/dragen/resource-files/misc/hg38_1000G_phase1.snps.high_confidence.vcf.gz
https://webdata.illumina.com/downloads/software/dragen/resource-files/4.5/hash-tables/hg38-alt_masked.cnv.graph.hla.methyl_cg.rna-12-r6.0-1.tar.gz
```

The original `ec2-user` history also showed the runtime restore pattern from
`/home/ec2-user/ephem_stg` into `/ephemeral`:

```bash
SAMPLE=NA19235
STAGE_ROOT=/home/ec2-user/ephem_stg
RUNTIME_ROOT=/ephemeral
LOG_DIR=/home/ec2-user/dragen_na19235_ec2_logs

if pgrep -a dragen >/dev/null 2>&1; then
  echo "ERROR: active DRAGEN process exists; refusing to alter runtime inputs." >&2
  pgrep -a dragen >&2
  exit 11
fi

required_paths=(
  "${STAGE_ROOT}/hg38-alt_masked.graph.cnv.hla.methyl_cg.rna_v6"
  "${STAGE_ROOT}/hg38_1000G_phase1.snps.high_confidence.vcf.gz"
  "${STAGE_ROOT}/smn12_samples/${SAMPLE}/${SAMPLE}.R1.fastq.gz"
  "${STAGE_ROOT}/smn12_samples/${SAMPLE}/${SAMPLE}.R2.fastq.gz"
  "/home/ec2-user/.config/dragen/lic_creds.txt"
)

rsync -a --info=progress2 \
  "${STAGE_ROOT}/hg38-alt_masked.graph.cnv.hla.methyl_cg.rna_v6/" \
  "${RUNTIME_ROOT}/hg38-alt_masked.graph.cnv.hla.methyl_cg.rna_v6/"

rsync -a --info=progress2 \
  "${STAGE_ROOT}/smn12_samples/${SAMPLE}/${SAMPLE}.R1.fastq.gz" \
  "${STAGE_ROOT}/smn12_samples/${SAMPLE}/${SAMPLE}.R2.fastq.gz" \
  "${RUNTIME_ROOT}/smn12_samples/${SAMPLE}/"

rsync -a --info=progress2 \
  "${STAGE_ROOT}/hg38_1000G_phase1.snps.high_confidence.vcf.gz" \
  "${RUNTIME_ROOT}/"

chmod 600 /home/ec2-user/.config/dragen/lic_creds.txt
df -h "${RUNTIME_ROOT}"
du -sh \
  "${RUNTIME_ROOT}/hg38-alt_masked.graph.cnv.hla.methyl_cg.rna_v6" \
  "${RUNTIME_ROOT}/smn12_samples/${SAMPLE}" \
  "${RUNTIME_ROOT}/hg38_1000G_phase1.snps.high_confidence.vcf.gz"
stat -c "license=%U:%G:%a:%s:%n" /home/ec2-user/.config/dragen/lic_creds.txt
ls -lh "${RUNTIME_ROOT}/smn12_samples/${SAMPLE}/"
```

That history also contained an interactive command that would print the DRAGEN
license credentials. It is intentionally omitted here. Verify only path, owner,
mode, and size for credential files.

The HG002-specific restore script used on 2026-07-08 was:

```bash
cat > /home/ec2-user/restore_hg002_runtime_20260708.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

SAMPLE=HG002
STAGE_ROOT=/home/ec2-user/ephem_stg
RUNTIME_ROOT=/ephemeral
LOG_DIR=/home/ec2-user/dragen_hg002_ec2_logs
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOG_FILE="${LOG_DIR}/restore_${STAMP}.log"

mkdir -p "${LOG_DIR}"
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "restore_started_utc=${STAMP}"
echo "host=$(hostname)"
echo "user=$(whoami)"

if pgrep -a dragen >/dev/null 2>&1; then
  echo "ERROR: active DRAGEN process exists; refusing to alter runtime inputs." >&2
  pgrep -a dragen >&2
  exit 11
fi

required_paths=(
  "${STAGE_ROOT}/hg38-alt_masked.graph.cnv.hla.methyl_cg.rna_v6"
  "${STAGE_ROOT}/hg38_1000G_phase1.snps.high_confidence.vcf.gz"
  "${STAGE_ROOT}/${SAMPLE}.novaseq.pcr-free.35x.R1.fastq.gz"
  "${STAGE_ROOT}/${SAMPLE}.novaseq.pcr-free.35x.R2.fastq.gz"
  "${STAGE_ROOT}/concordance_refs/giab_hg2_clinvar_genes/${SAMPLE}.vcf.gz"
  "${STAGE_ROOT}/concordance_refs/giab_hg2_clinvar_genes/${SAMPLE}.vcf.gz.tbi"
  "${STAGE_ROOT}/concordance_refs/giab_hg2_clinvar_genes/${SAMPLE}.bed"
  "/home/ec2-user/.config/dragen/lic_creds.txt"
)

for path in "${required_paths[@]}"; do
  if [ ! -e "${path}" ]; then
    echo "ERROR: missing required path ${path}" >&2
    exit 12
  fi
done

mkdir -p \
  "${RUNTIME_ROOT}/hg38-alt_masked.graph.cnv.hla.methyl_cg.rna_v6" \
  "${RUNTIME_ROOT}/smn12_samples/${SAMPLE}" \
  "${RUNTIME_ROOT}/output" \
  "${RUNTIME_ROOT}/concordance_refs/giab_hg2_clinvar_genes"

rsync -a --info=progress2 \
  "${STAGE_ROOT}/hg38-alt_masked.graph.cnv.hla.methyl_cg.rna_v6/" \
  "${RUNTIME_ROOT}/hg38-alt_masked.graph.cnv.hla.methyl_cg.rna_v6/"

rsync -a --info=progress2 \
  "${STAGE_ROOT}/${SAMPLE}.novaseq.pcr-free.35x.R1.fastq.gz" \
  "${RUNTIME_ROOT}/smn12_samples/${SAMPLE}/${SAMPLE}.R1.fastq.gz"

rsync -a --info=progress2 \
  "${STAGE_ROOT}/${SAMPLE}.novaseq.pcr-free.35x.R2.fastq.gz" \
  "${RUNTIME_ROOT}/smn12_samples/${SAMPLE}/${SAMPLE}.R2.fastq.gz"

rsync -a --info=progress2 \
  "${STAGE_ROOT}/hg38_1000G_phase1.snps.high_confidence.vcf.gz" \
  "${RUNTIME_ROOT}/"

rsync -a --info=progress2 \
  "${STAGE_ROOT}/concordance_refs/giab_hg2_clinvar_genes/" \
  "${RUNTIME_ROOT}/concordance_refs/giab_hg2_clinvar_genes/"

chmod 600 /home/ec2-user/.config/dragen/lic_creds.txt

echo "runtime_inventory_begin"
df -h "${RUNTIME_ROOT}"
du -sh \
  "${RUNTIME_ROOT}/hg38-alt_masked.graph.cnv.hla.methyl_cg.rna_v6" \
  "${RUNTIME_ROOT}/smn12_samples/${SAMPLE}" \
  "${RUNTIME_ROOT}/hg38_1000G_phase1.snps.high_confidence.vcf.gz" \
  "${RUNTIME_ROOT}/concordance_refs/giab_hg2_clinvar_genes"
stat -c "license=%U:%G:%a:%s:%n" /home/ec2-user/.config/dragen/lic_creds.txt
find \
  "${RUNTIME_ROOT}/concordance_refs/giab_hg2_clinvar_genes" \
  "${RUNTIME_ROOT}/smn12_samples/${SAMPLE}" \
  -maxdepth 1 -type f -printf '%s\t%p\n' | sort
echo "runtime_inventory_end"
echo "restore_finished_utc=$(date -u +%Y%m%dT%H%M%SZ)"
EOF

chmod +x /home/ec2-user/restore_hg002_runtime_20260708.sh
tmux new-session -d -s dragen_hg002_restore_20260708 'bash -il'
tmux send-keys -t dragen_hg002_restore_20260708 \
  '/home/ec2-user/restore_hg002_runtime_20260708.sh; exec bash -il' Enter
```

Restore result:

```text
restore_started_utc=20260708T013140Z
restore_finished_utc=20260708T013932Z
/ephemeral: 876G total, 162G used, 714G available
/ephemeral/hg38-alt_masked.graph.cnv.hla.methyl_cg.rna_v6: 38G
/ephemeral/smn12_samples/HG002: 57G
/ephemeral/hg38_1000G_phase1.snps.high_confidence.vcf.gz: 1.8G
/ephemeral/concordance_refs/giab_hg2_clinvar_genes: 311M
```

The HG002 DRAGEN run script was:

```bash
cat > /home/ec2-user/run_hg002_dragen_20260708.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

SAMPLE=HG002
OUTDIR=/ephemeral/output/${SAMPLE}_pangenome_MA_VC_all_callers
LOG_DIR=/home/ec2-user/dragen_hg002_ec2_logs
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOG_FILE="${LOG_DIR}/run_${STAMP}.log"
EXIT_FILE="${LOG_DIR}/run_${STAMP}.exit"
LICENSE_FILE=/home/ec2-user/.config/dragen/lic_creds.txt
REF_DIR=/ephemeral/hg38-alt_masked.graph.cnv.hla.methyl_cg.rna_v6
R1=/ephemeral/smn12_samples/${SAMPLE}/${SAMPLE}.R1.fastq.gz
R2=/ephemeral/smn12_samples/${SAMPLE}/${SAMPLE}.R2.fastq.gz
POPVCF=/ephemeral/hg38_1000G_phase1.snps.high_confidence.vcf.gz

mkdir -p "${LOG_DIR}" "${OUTDIR}"
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "run_started_utc=${STAMP}"
echo "host=$(hostname)"
echo "user=$(whoami)"
/opt/edico/bin/dragen --version
df -h /ephemeral
stat -c "license=%U:%G:%a:%s:%n" "${LICENSE_FILE}"

if pgrep -a dragen >/dev/null 2>&1; then
  echo "ERROR: active DRAGEN process exists; refusing to launch a second run." >&2
  pgrep -a dragen >&2
  exit 20
fi

for path in "${REF_DIR}" "${R1}" "${R2}" "${POPVCF}" "${LICENSE_FILE}"; do
  if [ ! -e "${path}" ]; then
    echo "ERROR: missing required path ${path}" >&2
    exit 21
  fi
done

set +e
/opt/edico/bin/dragen -f \
  -r "${REF_DIR}/" \
  -1 "${R1}" \
  -2 "${R2}" \
  --RGID "${SAMPLE}" \
  --RGSM "${SAMPLE}" \
  --enable-map-align true \
  --enable-map-align-output true \
  --enable-duplicate-marking true \
  --enable-variant-caller true \
  --vc-emit-ref-confidence GVCF \
  --vc-enable-vcf-output true \
  --enable-cnv true \
  --cnv-enable-self-normalization true \
  --cnv-population-b-allele-vcf "${POPVCF}" \
  --enable-sv true \
  --enable-targeted true \
  --enable-star-allele true \
  --repeat-genotype-enable true \
  --repeat-genotype-use-catalog default \
  --enable-hla true \
  --enable-mrjd true \
  --mrjd-enable-high-sensitivity true \
  --output-file-prefix "${SAMPLE}" \
  --output-directory "${OUTDIR}" \
  --lic-credentials "${LICENSE_FILE}"
rc=$?
set -e

echo "DRAGEN_EXIT_CODE=${rc}" | tee "${EXIT_FILE}"
echo "run_finished_utc=$(date -u +%Y%m%dT%H%M%SZ)"
exit "${rc}"
EOF

chmod +x /home/ec2-user/run_hg002_dragen_20260708.sh
tmux new-session -d -s dragen_hg002_run_20260708 'bash -il'
tmux send-keys -t dragen_hg002_run_20260708 \
  '/home/ec2-user/run_hg002_dragen_20260708.sh; exec bash -il' Enter
```

Run result:

```text
run_started_utc=20260708T014046Z
DRAGEN Host Software Version 4.5.4
dragen Version 13.031.818.4.5.4
LICENSE_MSG| License server: https://license.dragen.illumina.com, connected ok
DRAGEN_EXIT_CODE=0
run_finished_utc=20260708T024811Z
Total runtime: 01:07:01.968
```

Key HG002 DRAGEN metrics:

```text
Average alignment coverage over genome: 34.05x
Average autosomal coverage over genome: 36.04x
Median autosomal coverage over genome: 37.00x
Aligned reads: 686,133,174
Variant caller post-filter total: 5,053,288
Variant caller post-filter SNPs: 4,081,371
Variant caller post-filter insertions: 470,808
Variant caller post-filter deletions: 475,690
Variant caller post-filter indels: 25,419
Hard-filtered VCF records counted directly: 5,062,498
SNV-like VCF records counted directly: 4,086,926
Non-SNV-like VCF records counted directly: 975,572
```

The `hap.py` container staged for HG002 was:

```bash
sudo -n docker pull quay.io/biocontainers/hap.py:0.3.14--py27h5c5a3ab_0
sudo -n docker run --rm quay.io/biocontainers/hap.py:0.3.14--py27h5c5a3ab_0 \
  bash -lc 'type -a hap.py; type -a qfy.py; type -a bcftools; type -a bgzip; type -a tabix'
```

The container included `hap.py`, `qfy.py`, `bcftools`, `bgzip`, and `tabix`.
It did not include a standalone `rtg` command, so this run uses `hap.py` with
the default `xcmp` engine rather than `rtg vcfeval`.

The `hap.py` reference staged for HG002 was:

```bash
S3_ROOT=s3://lsmc-dayoa-references-usw2/genomic_data/organism_references/H_sapiens/hg38/fasta_fai_minalt
STAGE_DIR=/home/ec2-user/ephem_stg/concordance_refs/reference
RUNTIME_DIR=/ephemeral/concordance_refs/reference
FASTA=GRCh38_no_alt_analysis_set.fasta

mkdir -p "${STAGE_DIR}" "${RUNTIME_DIR}"
aws s3 cp "${S3_ROOT}/${FASTA}" "${STAGE_DIR}/${FASTA}" --only-show-errors
aws s3 cp "${S3_ROOT}/${FASTA}.fai" "${STAGE_DIR}/${FASTA}.fai" --only-show-errors
rsync -a --info=progress2 "${STAGE_DIR}/${FASTA}" "${STAGE_DIR}/${FASTA}.fai" "${RUNTIME_DIR}/"
stat -c '%s %n' "${RUNTIME_DIR}/${FASTA}" "${RUNTIME_DIR}/${FASTA}.fai"
head -5 "${RUNTIME_DIR}/${FASTA}.fai"
```

Reference staging result:

```text
/ephemeral/concordance_refs/reference/GRCh38_no_alt_analysis_set.fasta: 3144230986 bytes
/ephemeral/concordance_refs/reference/GRCh38_no_alt_analysis_set.fasta.fai: 7804 bytes
First contigs: chr1, chr2, chr3, chr4, chr5
HG002 truth VCF/BED contigs: chr1, chr2, chr3, chr4, chr5...
```

After DRAGEN completes, run HG002 concordance with:

```bash
TRUTH_DIR=/ephemeral/concordance_refs/giab_hg2_clinvar_genes
REF_FASTA=/ephemeral/concordance_refs/reference/GRCh38_no_alt_analysis_set.fasta
QUERY_DIR=/ephemeral/output/HG002_pangenome_MA_VC_all_callers
OUT_DIR="${QUERY_DIR}/concordance/happy_giab_hg2_clinvar_genes"
OUT_PREFIX="${OUT_DIR}/HG002.hard-filtered"

test -s "${QUERY_DIR}/HG002.hard-filtered.vcf.gz"
test -s "${QUERY_DIR}/HG002.hard-filtered.vcf.gz.tbi"
test -s "${TRUTH_DIR}/HG002.vcf.gz"
test -s "${TRUTH_DIR}/HG002.vcf.gz.tbi"
test -s "${TRUTH_DIR}/HG002.bed"
test -s "${REF_FASTA}"
test -s "${REF_FASTA}.fai"

mkdir -p "${OUT_DIR}" "${OUT_DIR}/scratch"

sudo -n docker run --rm \
  -v /ephemeral:/ephemeral \
  quay.io/biocontainers/hap.py:0.3.14--py27h5c5a3ab_0 \
  hap.py \
    "${TRUTH_DIR}/HG002.vcf.gz" \
    "${QUERY_DIR}/HG002.hard-filtered.vcf.gz" \
    -f "${TRUTH_DIR}/HG002.bed" \
    -r "${REF_FASTA}" \
    -o "${OUT_PREFIX}" \
    --scratch-prefix "${OUT_DIR}/scratch" \
    --threads=16

cat "${OUT_PREFIX}.summary.csv"
```

This rerun initially failed before comparison because the scratch directory did
not exist. The corrected command above includes:

```bash
mkdir -p "${OUT_DIR}" "${OUT_DIR}/scratch"
```

HG002 `hap.py` result:

```text
happy_started_utc=20260708T025132Z
happy_finished_utc=20260708T030942Z
HAPPY_EXIT_CODE=0
```

Summary:

```csv
Type,Filter,TRUTH.TOTAL,TRUTH.TP,TRUTH.FN,QUERY.TOTAL,QUERY.FP,QUERY.UNK,FP.gt,FP.al,METRIC.Recall,METRIC.Precision,METRIC.Frac_NA,METRIC.F1_Score
INDEL,ALL,66729,66285,444,994697,40649,884830,38,5502,0.993346,0.630016,0.889547,0.771022
INDEL,PASS,66729,66285,444,993031,40487,883326,38,5497,0.993346,0.630947,0.889525,0.771719
SNP,ALL,401855,401039,816,3977499,49899,3526496,124,1815,0.997969,0.889360,0.886611,0.940540
SNP,PASS,401855,401029,826,3970979,49238,3520647,124,1812,0.997945,0.890663,0.886594,0.941257
```

The planned HG002 export prefix is:

```text
s3://lsmc-dayoa-analysis-results-usw2/dragen/hg002_pangenome_20260708/ec2/
```

Export after the DRAGEN and concordance commands finish:

```bash
SAMPLE=HG002
RUN_DIR=/ephemeral/output/${SAMPLE}_pangenome_MA_VC_all_callers
LOG_DIR=/home/ec2-user/dragen_hg002_ec2_logs
S3_ROOT=s3://lsmc-dayoa-analysis-results-usw2/dragen/hg002_pangenome_20260708/ec2

test -d "${RUN_DIR}"
test -d "${LOG_DIR}"

aws s3 sync "${RUN_DIR}/" "${S3_ROOT}/output/${SAMPLE}_pangenome_MA_VC_all_callers/" \
  --only-show-errors

aws s3 sync "${LOG_DIR}/" "${S3_ROOT}/logs/dragen_hg002_ec2_logs/" \
  --only-show-errors

aws s3 ls "${S3_ROOT}/" --recursive --summarize
```

Export result:

```text
export_started_utc=20260708T031416Z
caller_account=108782052779
export_finished_utc=20260708T031600Z
S3 root: s3://lsmc-dayoa-analysis-results-usw2/dragen/hg002_pangenome_20260708/ec2/
Total Objects: 127
Total Size: 65,172,195,136 bytes
```

Key exported evidence files include:

```text
s3://lsmc-dayoa-analysis-results-usw2/dragen/hg002_pangenome_20260708/ec2/output/HG002_pangenome_MA_VC_all_callers/HG002.hard-filtered.vcf.gz
s3://lsmc-dayoa-analysis-results-usw2/dragen/hg002_pangenome_20260708/ec2/output/HG002_pangenome_MA_VC_all_callers/HG002.hard-filtered.vcf.gz.tbi
s3://lsmc-dayoa-analysis-results-usw2/dragen/hg002_pangenome_20260708/ec2/output/HG002_pangenome_MA_VC_all_callers/HG002.vc_metrics.csv
s3://lsmc-dayoa-analysis-results-usw2/dragen/hg002_pangenome_20260708/ec2/output/HG002_pangenome_MA_VC_all_callers/concordance/happy_giab_hg2_clinvar_genes/HG002.hard-filtered.summary.csv
s3://lsmc-dayoa-analysis-results-usw2/dragen/hg002_pangenome_20260708/ec2/logs/dragen_hg002_ec2_logs/run_20260708T014046Z.log
s3://lsmc-dayoa-analysis-results-usw2/dragen/hg002_pangenome_20260708/ec2/logs/dragen_hg002_ec2_logs/happy_20260708T025132Z.log
```

## Cleanup And Stop Boundary

`/ephemeral` is instance-local runtime storage. Stopping the instance may lose
data that exists only under `/ephemeral`. Before stopping, verify that every
needed result and log is exported to S3 or copied back to durable EBS under
`/home/ec2-user/ephem_stg`.

After export verification, cleaning only the generated output directory is:

```bash
rm -rf /ephemeral/output/NA19235_pangenome_MA_VC_all_callers
df -h /ephemeral
```

Stopping the instance is a live AWS state change. Reconfirm the exact instance
ID and the `/ephemeral` data-loss boundary before doing it:

```bash
aws --profile lsmc --region us-west-2 ec2 stop-instances \
  --instance-ids i-0d75af02251c65b84

aws --profile lsmc --region us-west-2 ec2 wait instance-stopped \
  --instance-ids i-0d75af02251c65b84
```
