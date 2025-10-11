#!/usr/bin/env bash

# Ensure AWS_PROFILE is defined and valid before proceeding
if [[ -z "${AWS_PROFILE:-}" ]]; then
  echo "ERROR: AWS_PROFILE environment variable is not set. Please set AWS_PROFILE before running this script."
  exit 1
fi

PROFILE_FOUND=false
if [[ -f "$HOME/.aws/credentials" ]] && grep -Fqx "[$AWS_PROFILE]" "$HOME/.aws/credentials"; then
  PROFILE_FOUND=true
fi

if [[ -f "$HOME/.aws/config" ]]; then
  if grep -Fqx "[profile $AWS_PROFILE]" "$HOME/.aws/config" || grep -Fqx "[$AWS_PROFILE]" "$HOME/.aws/config"; then
    PROFILE_FOUND=true
  fi
fi

if [[ "$PROFILE_FOUND" == false ]]; then
  echo "ERROR: AWS profile '$AWS_PROFILE' was not found in $HOME/.aws/credentials or $HOME/.aws/config."
  echo "Please run 'aws configure --profile $AWS_PROFILE' to create the profile and try again."
  exit 1
fi

# Function to display usage information
print_help() {
  echo "Usage: $0 -p <project_name> -a <amount> -r <region> -e <email> -t <thresholds> -c <cluster_name> [-h]"
  echo ""
  echo "Options:"
  echo "  -p    Project name (required)"
  echo "  -a    Budget amount in USD (required)"
  echo "  -r    AWS region (required)"
  echo "  -e    Email address for budget alerts (required)"
  echo "  -t    Comma-separated alert thresholds (required, e.g., 50,80,100)"
  echo "  -c    Cluster name (required)"
  echo "  -u    csv of users allowed to run with budget"
  echo "  -z    AWS AZ"
  echo "  -b    S3 bucket Name Tags are stored in (s3://<bucket-name>/data/budget_tags/<project_name>-tags.tsy)"
  echo "  -h    Display this help message"
  echo ""
  echo "Example:"
  echo "  $0 -p my-project -a 300 -r us-west-2 -e user@example.com -t 25,50,75,100"
}


# Default values
USERS=''  # Default USERS to an empty string
EMAIL='none@specified.com'  # Default EMAIL to an empty string

# Parse command-line options
while getopts "p:a:r:e:t:c:u:z:b:h" opt; do
  case ${opt} in
    p) PROJECT_NAME=$OPTARG ;;
    a) AMOUNT=$OPTARG ;;
    r) REGION=$OPTARG ;;
    e) EMAIL=$OPTARG ;;
    t) THRESHOLDS=$OPTARG ;;
    c) CLUSTER_NAME=$OPTARG ;;
    u) USERS=$OPTARG ;;
    z) AZ=$OPTARG ;;
    b) S3_BUCKET_URL=$OPTARG ;; # Parse -b option correctly
    h) 
      print_help
      exit 0
      ;;
    *)
      print_help
      exit 1
      ;;
  esac
done


# Check if all required parameters are provided
if [[ -z "$PROJECT_NAME" || -z "$AMOUNT" || -z "$REGION" || -z "$EMAIL" || -z "$THRESHOLDS" || -z "$CLUSTER_NAME" ]]; then
  echo "ERROR: Project name, amount, region, email, and thresholds are required."
  print_help
  exit 1
fi



# Ensure S3_BUCKET_URL is set
if [[ -z "$S3_BUCKET_URL" ]]; then
  echo "ERROR: S3 bucket URL is required (-b)."
  print_help
  exit 1
fi


# Function to write or append tags to the S3 file# Function to write or append tags to the S3 file
write_or_append_tags_to_s3() {
  # Ensure S3_BUCKET_URL ends with a proper path
  S3_BUCKET_PATH="${S3_BUCKET_URL}/data/budget_tags/pcluster-project-budget-tags.tsv"

  # Temporary local file for manipulation
  TEMP_LOCAL_FILE=$(mktemp)

  echo "Checking if S3 file exists: $S3_BUCKET_PATH"

  echo "Writing or appending tags to S3 file: $S3_BUCKET_PATH" url: $S3_BUCKET_URL
  # Check if the file exists in S3
  if aws s3 ls "$S3_BUCKET_PATH" --profile $AWS_PROFILE > /dev/null 2>&1; then
    echo "File exists. Downloading the existing file."
    aws s3 cp "$S3_BUCKET_PATH" "$TEMP_LOCAL_FILE" --region "$REGION" --profile $AWS_PROFILE

    if [[ $? -ne 0 ]]; then
      echo "ERROR: Failed to download existing file from S3."
      rm -f "$TEMP_LOCAL_FILE"
      return 1
    fi
  else
    echo "File does not exist. Creating a new file."
    touch "$TEMP_LOCAL_FILE"
  fi

  # Append the new tag to the local file
  echo -e "$PROJECT_NAME\tubuntu,$USERS" >> "$TEMP_LOCAL_FILE"

  # Upload the updated file back to S3
  echo "Uploading updated file to S3..."
  aws s3 cp "$TEMP_LOCAL_FILE" "$S3_BUCKET_PATH" --region "$REGION" --profile $AWS_PROFILE

  if [[ $? -eq 0 ]]; then
    echo "Successfully updated S3 file: $S3_BUCKET_PATH"
  else
    echo "ERROR: Failed to upload updated file to S3."
  fi

  # Clean up the temporary local file
  rm -f "$TEMP_LOCAL_FILE"
}





# Define the budget JSON template
BUDGET_TEMPLATE='{
    "BudgetLimit": {
        "Amount": "<amount>",
        "Unit": "USD"
    },
    "BudgetName": "<budget_name>",
    "BudgetType": "COST",
    "CostFilters": {
        "TagKeyValue": [
            "user:aws-parallelcluster-project$<project_name>",
            "user:aws-parallelcluster-clustername$<cluster_name>"
        ]
    },
    "CostTypes": {
        "IncludeCredit": true,
        "IncludeDiscount": true,
        "IncludeOtherSubscription": true,
        "IncludeRecurring": true,
        "IncludeRefund": true,
        "IncludeSubscription": true,
        "IncludeSupport": true,
        "IncludeTax": true,
        "IncludeUpfront": true,
        "UseBlended": false
    },
    "TimeUnit": "MONTHLY"
}'

# Replace placeholders with input values
BUDGET_JSON=$(echo "$BUDGET_TEMPLATE" | \
    sed "s/<amount>/$AMOUNT/g" | \
    sed "s/<cluster_name>/$CLUSTER_NAME/g" | \
    sed "s/<budget_name>/$PROJECT_NAME/g" | \
    sed "s/<project_name>/$PROJECT_NAME/g")

# Save budget JSON to a temporary file
TEMP_BUDGET_JSON=$(mktemp)
echo "$BUDGET_JSON" > "$TEMP_BUDGET_JSON"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile $AWS_PROFILE)

# Create the budget using AWS CLI
echo "Creating budget for project: $PROJECT_NAME with amount: $AMOUNT USD in region: $REGION"
aws budgets create-budget --account-id "$ACCOUNT_ID" \
    --budget file://"$TEMP_BUDGET_JSON" --region "$REGION" --profile $AWS_PROFILE

# Check if the budget creation succeeded
if [[ $? -eq 0 ]]; then
  echo "Successfully created budget for project: $PROJECT_NAME"

  # Create budget alerts using the correct AWS CLI syntax
  echo "Creating budget alerts..."
  IFS=',' read -ra THRESHOLD_ARRAY <<< "$THRESHOLDS"
  for threshold in "${THRESHOLD_ARRAY[@]}"; do
    echo P:$PROJECT_NAME T:$threshold E:$EMAIL R:$REGION A:$AMOUNT AI:$ACCOUNT_ID 
    aws budgets create-notification --account-id "$ACCOUNT_ID" --profile $AWS_PROFILE \
      --budget-name "$PROJECT_NAME" \
      --notification '{"ComparisonOperator":"GREATER_THAN","NotificationType":"ACTUAL","Threshold":'"$threshold"',"ThresholdType":"PERCENTAGE"}' \
      --region "$REGION"   --subscribers '[{"Address":"'"$EMAIL"'","SubscriptionType":"EMAIL"}]' 

    if [[ $? -eq 0 ]]; then
      echo "Successfully created alert for threshold: $threshold%"
    else
      echo "ERROR: Failed to create alert for threshold: $threshold%. Please check your AWS credentials and permissions."
    fi
  done

  echo "You will need to add this budget name to the projects file found in the s3:*-omics-analysis/cluster_boot_config/projects_list.conf so it will be included in new clusters. For already running clusters, you will need to edit the file found in /opt/slurm/etc/projects_list.conf as well."
else
  echo "ERROR: Failed to create budget. Please check your AWS credentials, permissions, and region."
fi


# Call this function after creating the budget
write_or_append_tags_to_s3

# Clean up temporary JSON file
rm "$TEMP_BUDGET_JSON"
