#!/usr/bin/env bash
set -euo pipefail

export AWS_PROFILE=lsmc
export AWS_REGION=us-east-1

create_private_bucket() {
  local bucket="$1"
  aws s3api create-bucket --bucket "$bucket" --region us-east-1
  aws s3api put-bucket-encryption --bucket "$bucket" --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"},"BucketKeyEnabled":false}]}'
  aws s3api put-public-access-block --bucket "$bucket" --public-access-block-configuration '{"BlockPublicAcls":true,"IgnorePublicAcls":true,"BlockPublicPolicy":true,"RestrictPublicBuckets":true}'
}

create_private_bucket lsmc-dayoa-references-use1
aws s3 sync s3://lsmc-dayoa-references-usw2/ s3://lsmc-dayoa-references-use1/ --only-show-errors

create_private_bucket lsmc-dayoa-control-data-use1
aws s3 sync s3://lsmc-dayoa-control-data-usw2/ s3://lsmc-dayoa-control-data-use1/ --only-show-errors
