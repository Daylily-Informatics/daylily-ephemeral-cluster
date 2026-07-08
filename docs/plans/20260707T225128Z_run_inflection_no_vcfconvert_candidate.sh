#!/usr/bin/env bash
set -euo pipefail

source ./activate

dyec tests command-catalog \
  --cluster cmdcat-103-all-20260707 \
  --profile lsmc \
  --region us-west-2 \
  --command-codes inflection-bjuice-product-v0.1 \
  --evidence-s3-uri s3://lsmc-ssf-sequencing-data/derived/command-catalog/dyec-10.0.103/dayoa-10.0.65-candidate/20260707T144453Z/ \
  --parallel 1 \
  --jobs 250 \
  --executing-entity ubuntu \
  --output-dir docs/plans/20260707T225128Z_dyec_tests_command_catalog_inflection_no_vcfconvert_candidate_logs \
  --stamp 20260707T225128Z \
  --timeout-minutes 720 \
  --poll-interval-seconds 60 \
  --catalog-config docs/plans/20260707T225128Z_dayoa7d519f9_inflection_no_vcfconvert_command_catalog.yaml
