#!/usr/bin/env bash
set -euo pipefail

source ./activate

dyec tests command-catalog \
  --cluster cmdcat-103-all-20260707 \
  --profile lsmc \
  --region us-west-2 \
  --command-codes simple-test,illumina_pangenome_snv,ultima_snv_alignstats,ultima_snv_alignstats_kitchensink,ultima_pangenome_snv,pacbio_snv_alignstats,roche_snv_alignstats,hybrid_ilmn_ont_snv,hybrid_ilmn_ont_snv_kitchensink,inflection-bjuice-product-v0.1 \
  --evidence-s3-uri s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.65-candidate/20260707T144453Z/ \
  --parallel 10 \
  --jobs 250 \
  --executing-entity ubuntu \
  --output-dir docs/plans/20260707T190607Z_dyec_tests_command_catalog_remaining_samples_candidate_logs \
  --stamp 20260707T190607Z \
  --timeout-minutes 720 \
  --poll-interval-seconds 60 \
  --catalog-config docs/plans/20260707T190607Z_dayoa035f4dc_remaining_sample_command_catalog.yaml
