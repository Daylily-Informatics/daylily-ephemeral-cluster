#!/bin/bash

echo -e "\n\n\t ALERT 1:::>>> You will need valid AWS credentials in your ~/.aws directory in order to proceed.\n\n"
echo -e "\n\n\tALERT 2:::>>> Please also be sure to have created a key pair in the AWS console which is ed25519 type & saved the resulting .pem file (chmod 400 it). This will be needed for creating the cluster after this step completes.\n\n... pausing"

echo -e "\n\n\t... continuing\n\n"

# Function to display usage information
function usage() {
  echo "Usage: $0 TEMPLATE_FILE RESOURCE_PREFIX AVAILABILITY_ZONE"
  echo
  echo "Arguments:"
  echo "  TEMPLATE_FILE      Full path to the CloudFormation template file (e.g., ./config/day_cluster/pcluster_env.yml)"
  echo "  RESOURCE_PREFIX    A prefix for all resources created by the stack (alphabets and dashes only)"
  echo "  AVAILABILITY_ZONE  The AWS availability zone (e.g., us-west-2a)"
  echo "  REGION             The AWS region (e.g., us-west-2)"
  echo " PROFILE            The AWS profile to use (e.g., default)"
  echo "Options:"
  echo "  --help             Display this help message and exit"
}

# Check if help is requested
if [[ "$1" == "--help" ]]; then
  usage
  exit 0
fi

# Check for missing arguments
if [[ -z "$1" || -z "$2" || -z "$3" || -z "$4" || -z "$5" ]]; then
  echo "Error: Missing required arguments."
  usage
  exit 1
fi

TEMPLATE_FILE=$1      # Full path to the CloudFormation template file
RESOURCES_PREFIX=$2   # A prefix for all resources created by the stack
AVAILABILITY_ZONE=$3  # Availability zone, e.g., us-west-2a
REGION=$4  # Extract region from AZ by removing the trailing letter
STACK_NAME="pcluster-vpc-stack-"$(echo $3 | cut -d '-' -f 3) # DO NOT CHANGE THIS!! 
AWS_PROFILE=$5

VPC_CIDR="10.0.0.0/16"
PUBLIC_SUBNET_CIDR="10.0.0.0/24"
PRIVATE_SUBNET_CIDR="10.0.1.0/24"

# Validate if the template file exists
if [[ ! -f "$TEMPLATE_FILE" ]]; then
  echo "Error: The template file $TEMPLATE_FILE does not exist."
  exit 1
fi

# Validate resource prefix: only allow alphabets and dashes
if [[ ! "$RESOURCES_PREFIX" =~ ^[a-zA-Z-]+$ ]]; then
  echo "Error: The resource prefix can only contain alphabets and dashes: $RESOURCES_PREFIX."
  exit 1
fi

# Validate that the availability zone starts with the region
if [[ "$AVAILABILITY_ZONE" != "$REGION"* ]]; then
  echo "Error: Availability zone ($AVAILABILITY_ZONE) does not match the region ($REGION)."
  exit 1
fi

POLICY_NAME="pclusterTagsAndBudget"
# Check if the IAM policy already exists
POLICY_EXISTS=$(aws iam list-policies --query "Policies[?PolicyName=='${POLICY_NAME}'] | length(@)" --region $REGION --profile $AWS_PROFILE)

CREATE_POLICY="true"
if [[ $POLICY_EXISTS -eq 0 ]]; then
  CREATE_POLICY="true"
  echo "Policy does not exist, will create a new policy."
else
  CREATE_POLICY="false"
  echo "Policy already exists, will not create a new policy."
fi

echo RP: $RESOURCES_PREFIX AZ: $AVAILABILITY_ZONE REGION: $REGION STACK_NAME: $STACK_NAME VPC_CIDR: $VPC_CIDR PUBLIC_SUBNET_CIDR: $PUBLIC_SUBNET_CIDR PRIVATE_SUBNET_CIDR: $PRIVATE_SUBNET_CIDR POLICY_EXISTS: $POLICY_EXISTS CREATE_POLICY: $CREATE_POLICY 
echo "onwards"
echo ""
#echo "aws cloudformation create-stack --stack-name $STACK_NAME --template-body file://$TEMPLATE_FILE --region $REGION --profile $AWS_PROFILE --parameters ParameterKey=EnvironmentName,ParameterValue=$RESOURCES_PREFIX ParameterKey=VpcCIDR,ParameterValue=$VPC_CIDR ParameterKey=PublicSubnetCIDR,ParameterValue=$PUBLIC_SUBNET_CIDR ParameterKey=PrivateSubnetCIDR,ParameterValue=$PRIVATE_SUBNET_CIDR ParameterKey=AvailabilityZone,ParameterValue=$AVAILABILITY_ZONE ParameterKey=CreatePolicy,ParameterValue=$CREATE_POLICY --capabilities CAPABILITY_NAMED_IAM"  

# Create the CloudFormation Stack
aws cloudformation create-stack \
  --stack-name $STACK_NAME \
  --template-body file://$TEMPLATE_FILE \
  --region $REGION --profile $AWS_PROFILE \
  --parameters ParameterKey=EnvironmentName,ParameterValue=$RESOURCES_PREFIX \
               ParameterKey=VpcCIDR,ParameterValue=$VPC_CIDR \
               ParameterKey=PublicSubnetCIDR,ParameterValue=$PUBLIC_SUBNET_CIDR \
               ParameterKey=PrivateSubnetCIDR,ParameterValue=$PRIVATE_SUBNET_CIDR \
               ParameterKey=AvailabilityZone,ParameterValue=$AVAILABILITY_ZONE \
               ParameterKey=CreatePolicy,ParameterValue=$CREATE_POLICY \
  --capabilities CAPABILITY_NAMED_IAM

# Wait for the stack to finish creating (success or failure)
echo "Waiting for stack creation to complete..."
aws cloudformation wait stack-create-complete --stack-name $STACK_NAME --region $REGION --profile $AWS_PROFILE 

# Check if stack creation succeeded or failed
STACK_STATUS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query "Stacks[0].StackStatus" --output text --profile $AWS_PROFILE )

if [[ "$STACK_STATUS" == "CREATE_COMPLETE" ]]; then
  echo "Stack creation succeeded."

  # Get the Policy ARN, Public Subnet ID, and Private Subnet ID
  POLICY_ARN=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query "Stacks[0].Outputs[?OutputKey=='PclusterPolicy'].OutputValue" --output text --profile $AWS_PROFILE )
  PUBLIC_SUBNET_ID=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query "Stacks[0].Outputs[?OutputKey=='PublicSubnets'].OutputValue" --output text --profile $AWS_PROFILE )
  PRIVATE_SUBNET_ID=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query "Stacks[0].Outputs[?OutputKey=='PrivateSubnet'].OutputValue" --output text --profile $AWS_PROFILE )

  echo "Policy ARN: $POLICY_ARN"
  echo "Public Subnet ID: $PUBLIC_SUBNET_ID"
  echo "Private Subnet ID: $PRIVATE_SUBNET_ID"

else
  echo "Stack creation failed with status: $STACK_STATUS"

  # Get the stack events to show failure reason
  aws cloudformation describe-stack-events --profile $AWS_PROFILE --stack-name $STACK_NAME --region $REGION --query "StackEvents[?ResourceStatus=='CREATE_FAILED'].{Resource:LogicalResourceId,Reason:ResourceStatusReason}" --output table
fi
