#!/usr/bin/env bash
set -euo pipefail

source ./activate

dyec tests command-catalog \
  --cluster cmdcat-103-all-20260707 \
  --profile lsmc \
  --region us-west-2 \
  --command-codes hybrid_ilmn_ont_snv \
  --evidence-s3-uri s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.65-candidate/20260707T144453Z/ \
  --parallel 1 \
  --jobs 250 \
  --executing-entity ubuntu \
  --output-dir docs/plans/20260707T211600Z_dyec_tests_command_catalog_hybrid_snv_transfer_scratch_candidate_logs \
  --stamp 20260707T211600Z \
  --timeout-minutes 720 \
  --poll-interval-seconds 60 \
  --catalog-config docs/plans/20260707T203440Z_dayoa9c2d540_hybrid_transfer_scratch_command_catalog.yaml
