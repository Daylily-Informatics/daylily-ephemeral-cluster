#!/usr/bin/env bash
set -euo pipefail

export AWS_PROFILE=lsmc
export AWS_REGION=us-east-1
bucket=lsmc-dayoa-control-data-use1

until aws s3api head-bucket --bucket "$bucket" 2>/dev/null; do
  sleep 30
done

aws s3api put-bucket-policy --bucket "$bucket" --policy '{"Version":"2012-10-17","Statement":[{"Sid":"AllowBioComputeBucketVisibility","Effect":"Allow","Principal":{"AWS":"arn:aws:iam::236749268816:root"},"Action":["s3:GetBucketLocation","s3:ListBucket","s3:ListBucketMultipartUploads"],"Resource":"arn:aws:s3:::lsmc-dayoa-control-data-use1","Condition":{"StringLike":{"aws:PrincipalArn":["arn:aws:iam::236749268816:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_BioCompute_*","arn:aws:iam::236749268816:role/aws-reserved/sso.amazonaws.com/*/AWSReservedSSO_BioCompute_*"]}}}]}'
aws s3api put-bucket-ownership-controls --bucket "$bucket" --ownership-controls '{"Rules":[{"ObjectOwnership":"BucketOwnerEnforced"}]}'
aws s3api put-bucket-tagging --bucket "$bucket" --tagging '{"TagSet":[{"Key":"aws-parallelcluster-project","Value":"dayoa-control-data"}]}'
