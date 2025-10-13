

export AWS_PROFILE=YOURADMINUSERPROFILE

aws iam create-policy \\n  --policy-name DaylilyCostRead \\n  --policy-document file://config/aws/generate_cluster_report.json

aws iam attach-user-policy \\n  --user-name daylily-service \\n  --policy-arn arn:aws:iam::108782052779:policy/DaylilyCostRead

export AWS_PROFILE=<daylily-service>