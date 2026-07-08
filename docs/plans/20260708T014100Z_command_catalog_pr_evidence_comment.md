## Recreate Command-Catalog Evidence

These are the DYEC helper commands for reproducing the validation path: create the catalog cluster, prepare required inputs, run the production command catalog, and export completed analysis roots back to S3. The current `all` command set means all non-research commands; `illumina_bclconvert` and `illumina_run_qc_bclconvert` are intentionally excluded from the production/default run.

```bash
cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate

RUN_ID=20260707T144453Z
CLUSTER=cmdcat-103-all-20260707
PROFILE=lsmc
REGION=us-west-2
REGION_AZ=us-west-2c
CONFIG=config/daylily_ephemeral_cluster_cmdcat_10_0_103_all_20260707.yaml
CATALOG_CONFIG=config/daylily_pipeline_command_catalog.yaml
EVIDENCE_BASE=s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64
CATALOG_LOG_ROOT=docs/plans/${RUN_ID}_dyec_tests_command_catalog_logs

dyec preflight \
  --profile "${PROFILE}" \
  --region-az "${REGION_AZ}" \
  --config "${CONFIG}" \
  --non-interactive

dyec create \
  --profile "${PROFILE}" \
  --region-az "${REGION_AZ}" \
  --config "${CONFIG}" \
  --non-interactive \
  --create-slurm-accounting-db

dyec cluster wait \
  --profile "${PROFILE}" \
  --region "${REGION}" \
  --cluster "${CLUSTER}" \
  --status CREATE_COMPLETE \
  --timeout 7200

dyec headnode configure \
  --profile "${PROFILE}" \
  --region "${REGION}" \
  --cluster "${CLUSTER}"
```

If the catalog runner is allowed to prepare inputs, `--create-missing-mounts` creates any missing run-directory DRAs with a 3600-second wait and the runner calls `dyec samples stage --config-only` for sample-manifest commands. To pre-create the same input mounts explicitly:

```bash
cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate

CLUSTER=cmdcat-103-all-20260707
PROFILE=lsmc
REGION=us-west-2

dyec --json mounts create "s3://lsmc-dayoa-control-data-usw2/" \
  --profile "${PROFILE}" \
  --region "${REGION}" \
  --cluster "${CLUSTER}" \
  --purpose control-data \
  --mount-id control_data \
  --file-system-path /control_data/ \
  --platform OTHER \
  --read-only \
  --wait \
  --timeout-seconds 3600

dyec --json mounts create "s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0009_B23TVLGLT4/" \
  --profile "${PROFILE}" \
  --region "${REGION}" \
  --cluster "${CLUSTER}" \
  --platform ILMN \
  --mount-id illumina_20260514_LH01106_0009_B23TVLGLT4 \
  --read-only \
  --wait \
  --timeout-seconds 3600

dyec --json mounts create "s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260513_ONT_HG003/" \
  --profile "${PROFILE}" \
  --region "${REGION}" \
  --cluster "${CLUSTER}" \
  --platform ONT \
  --mount-id ont_20260513_HG003 \
  --read-only \
  --wait \
  --timeout-seconds 3600

dyec --json mounts create "s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/RUN602221/2026/602221-20260417_2346/" \
  --profile "${PROFILE}" \
  --region "${REGION}" \
  --cluster "${CLUSTER}" \
  --platform ULTIMA \
  --mount-id ultima_602221_20260417_2346 \
  --read-only \
  --wait \
  --timeout-seconds 3600

for MOUNT_ID in \
  control_data \
  illumina_20260514_LH01106_0009_B23TVLGLT4 \
  ont_20260513_HG003 \
  ultima_602221_20260417_2346
do
  dyec --json mounts verify \
    --profile "${PROFILE}" \
    --region "${REGION}" \
    --cluster "${CLUSTER}" \
    --mount-id "${MOUNT_ID}" \
    --timeout-seconds 300
done
```

Run the production command catalog and let DYEC write local command evidence plus S3 evidence for successful phases:

```bash
cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate

RUN_ID=20260707T144453Z
CLUSTER=cmdcat-103-all-20260707
PROFILE=lsmc
REGION=us-west-2
EVIDENCE_BASE=s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64
CATALOG_CONFIG=config/daylily_pipeline_command_catalog.yaml
CATALOG_LOG_ROOT=docs/plans/${RUN_ID}_dyec_tests_command_catalog_logs

dyec tests command-catalog \
  --profile "${PROFILE}" \
  --region "${REGION}" \
  --cluster "${CLUSTER}" \
  --command-codes all \
  --evidence-s3-uri "${EVIDENCE_BASE}" \
  --create-missing-mounts \
  --parallel 10 \
  --jobs 200 \
  --timeout-minutes 720 \
  --poll-interval-seconds 30 \
  --stamp "${RUN_ID}" \
  --output-dir "${CATALOG_LOG_ROOT}" \
  --catalog-config "${CATALOG_CONFIG}"

cat "${CATALOG_LOG_ROOT}/command_registry.json"
cat "${CATALOG_LOG_ROOT}/run_mounts.json"
cat "${CATALOG_LOG_ROOT}/summary.json"
```

The export loop below reproduces the exact S3 export receipts referenced in this PR comment from the completed FSx analysis roots:

```bash
cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate

RUN_ID=20260707T144453Z
CLUSTER=cmdcat-103-all-20260707
PROFILE=lsmc
REGION=us-west-2
S3_ROOT=s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64/${RUN_ID}
LOG_ROOT=docs/plans/${RUN_ID}_success_exports
mkdir -p "${LOG_ROOT}"

exports=(
  "simple-test ccv_live_simple-test_20260707T190607Z"
  "illumina_snv_alignstats ccv_live_illumina_snv_alignstats_20260707T165057Z"
  "illumina_snv_alignstats_relatedness_vep_multiqc ccv_live_illumina_snv_alignstats_relatedness_vep_multiqc_20260707T165057Z"
  "illumina_hg002_kitchensink_multiqc ccv_live_illumina_hg002_kitchensink_multiqc_20260707T185605Z"
  "illumina_pangenome_snv ccv_live_illumina_pangenome_snv_20260707T190607Z"
  "ultima_snv_alignstats ccv_live_ultima_snv_alignstats_20260707T190607Z"
  "ultima_snv_alignstats_kitchensink ccv_live_ultima_snv_alignstats_kitchensink_20260707T190607Z"
  "ultima_pangenome_snv ccv_live_ultima_pangenome_snv_20260707T190607Z"
  "ont_snv_alignstats ccv_live_ont_snv_alignstats_20260707T165057Z"
  "ont_snv_alignstats_kitchensink ccv_live_ont_snv_alignstats_kitchensink_20260707T165057Z"
  "pacbio_snv_alignstats ccv_live_pacbio_snv_alignstats_20260707T190607Z"
  "roche_snv_alignstats ccv_live_roche_snv_alignstats_20260707T190607Z"
  "hybrid_ilmn_ont_snv ccv_live_hybrid_ilmn_ont_snv_20260707T211600Z"
  "hybrid_ilmn_ont_snv_kitchensink ccv_live_hybrid_ilmn_ont_snv_kitchensink_20260707T203440Z"
  "complete_genomics_mgi_snv_concordance ccv_live_complete_genomics_mgi_snv_concordance_20260707T165057Z"
  "illumina_run_qc ccv_live_illumina_run_qc_20260707T165057Z"
  "ont_run_qc ccv_live_ont_run_qc_20260707T170900Z"
  "ultima_run_qc ccv_live_ultima_run_qc_20260707T171700Z"
)

for export_row in "${exports[@]}"; do
  command_id="${export_row%% *}"
  session="${export_row#* }"
  outdir="${LOG_ROOT}/${command_id}"
  source_path="/fsx/analysis_results/ubuntu/${session}"
  dest="${S3_ROOT}/ubuntu/${session}/"
  mkdir -p "${outdir}"
  {
    date -u
    printf 'command_id=%s\n' "${command_id}"
    printf 'session=%s\n' "${session}"
    printf 'source_path=%s\n' "${source_path}"
    printf 'destination_s3_uri=%s\n' "${dest}"
    dyec export \
      --profile "${PROFILE}" \
      --region "${REGION}" \
      --cluster "${CLUSTER}" \
      --source-path "${source_path}" \
      --destination-s3-uri "${dest}" \
      --output-dir "${outdir}" \
      --timeout-seconds 7200
    date -u
  } 2>&1 | tee "${outdir}/export.log"
done

find "${LOG_ROOT}" -name fsx_export.yaml -print | sort
```

## Command Catalog Export Evidence

Successful exports available so far from the command-catalog validation run:

- Validation run root: `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64/20260707T144453Z/`
- Local receipt source: `docs/plans/20260707T144453Z_success_exports/*/fsx_export.yaml`
- Receipt condition for every item below: `status: success`, `task_lifecycle: SUCCEEDED`

Exported command evidence:

- `complete_genomics_mgi_snv_concordance`: `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64/20260707T144453Z/ubuntu/ccv_live_complete_genomics_mgi_snv_concordance_20260707T165057Z/`
- `hybrid_ilmn_ont_snv`: `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64/20260707T144453Z/ubuntu/ccv_live_hybrid_ilmn_ont_snv_20260707T211600Z/`
- `hybrid_ilmn_ont_snv_kitchensink`: `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64/20260707T144453Z/ubuntu/ccv_live_hybrid_ilmn_ont_snv_kitchensink_20260707T203440Z/`
- `illumina_hg002_kitchensink_multiqc`: `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64/20260707T144453Z/ubuntu/ccv_live_illumina_hg002_kitchensink_multiqc_20260707T185605Z/`
- `illumina_pangenome_snv`: `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64/20260707T144453Z/ubuntu/ccv_live_illumina_pangenome_snv_20260707T190607Z/`
- `illumina_run_qc`: `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64/20260707T144453Z/ubuntu/ccv_live_illumina_run_qc_20260707T165057Z/`
- `illumina_snv_alignstats`: `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64/20260707T144453Z/ubuntu/ccv_live_illumina_snv_alignstats_20260707T165057Z/`
- `illumina_snv_alignstats_relatedness_vep_multiqc`: `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64/20260707T144453Z/ubuntu/ccv_live_illumina_snv_alignstats_relatedness_vep_multiqc_20260707T165057Z/`
- `ont_run_qc`: `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64/20260707T144453Z/ubuntu/ccv_live_ont_run_qc_20260707T170900Z/`
- `ont_snv_alignstats`: `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64/20260707T144453Z/ubuntu/ccv_live_ont_snv_alignstats_20260707T165057Z/`
- `ont_snv_alignstats_kitchensink`: `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64/20260707T144453Z/ubuntu/ccv_live_ont_snv_alignstats_kitchensink_20260707T165057Z/`
- `pacbio_snv_alignstats`: `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64/20260707T144453Z/ubuntu/ccv_live_pacbio_snv_alignstats_20260707T190607Z/`
- `roche_snv_alignstats`: `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64/20260707T144453Z/ubuntu/ccv_live_roche_snv_alignstats_20260707T190607Z/`
- `simple-test`: `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64/20260707T144453Z/ubuntu/ccv_live_simple-test_20260707T190607Z/`
- `ultima_pangenome_snv`: `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64/20260707T144453Z/ubuntu/ccv_live_ultima_pangenome_snv_20260707T190607Z/`
- `ultima_run_qc`: `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64/20260707T144453Z/ubuntu/ccv_live_ultima_run_qc_20260707T171700Z/`
- `ultima_snv_alignstats`: `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64/20260707T144453Z/ubuntu/ccv_live_ultima_snv_alignstats_20260707T190607Z/`
- `ultima_snv_alignstats_kitchensink`: `s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.64/20260707T144453Z/ubuntu/ccv_live_ultima_snv_alignstats_kitchensink_20260707T190607Z/`

Omitted because they are not exported successfully yet:

- `inflection-bjuice-product-v0.1`: still running as `ccv_live_inflection-bjuice-product-v0.1_20260707T225128Z`; latest read-only status showed `completed_at: null`, `exit_code: null`, with Slurm jobs `5364` and `5371` still running on `i384nvme`.
- `illumina_bclconvert`: still non-terminal; lane jobs pending on `i192hugenvme`.
- `illumina_run_qc_bclconvert`: still non-terminal; lane jobs pending on `i192hugenvme`.
