#!/bin/bash

set -e  # Exit on any error

# Check if the script is being sourced
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    echo "Error: This script is being sourced, not executed. Please execute this script."
    return 3  # Return with error if sourced
fi

# Default values
s3_reference_data_version="0.7.131c"
region=""
disable_dryrun=false # Default to true
exclude_hg38_refs=false
exclude_b37_refs=false
exclude_giab_reads=false
profile="setme"
LOGFILE=""

# Usage function
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --daylily-s3-version <version>       Set the Daylily S3 version ( default: 0.7.131c )"
    echo "  --region <region>                    Region to CREATE the new bucket in ( required )"
    echo "  --disable-dryrun                     Disable dry-run mode ( default: run in dry-run mode )"
    echo "  --bucket-prefix <prefix>             Set the S3 bucket prefix ( required )"
    echo "  --disable-warn                       Disable warnings ( default: run with warnings )"
    echo "  --exclude-hg38-refs                  Skip copying hg38 references and annotations ( default: false )"
    echo "  --exclude-b37-refs                   Skip copying b37 references and annotations ( default: false )"
    echo "  --exclude-giab-reads                 Skip copying GIAB reads ( default: false )"
    echo "  --profile                             AWS profile to use, must match AWS_PROFILE ( required )"
    echo "  --log-file                            Log file to write to ( default: ./create_daylily_s3_REGION.log )"
    echo "  --help                               Show this help message"
    exit 1
}

# Parse command-line arguments
while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --daylily-s3-version) s3_reference_data_version="$2"; shift 2;;
        --region) region="$2"; shift 2;;
        --disable-dryrun) disable_dryrun=true; shift 1;;
        --bucket-prefix) bucket_prefix="$2"; shift 2;;
        --disable-warn) disable_warn=true; shift 1;;
        --exclude-hg38-refs) exclude_hg38_refs=true; shift 1;;
        --exclude-b37-refs) exclude_b37_refs=true; shift 1;;
        --exclude-giab-reads) exclude_giab_reads=true; shift 1;;
        --profile) profile="$2"; shift 2;;
        --log-file) LOGFILE="$2"; shift 2;;
        --help) usage;;
        *) echo "Unknown parameter: $1"; usage;;
    esac
done

if [ "$LOGFILE" == "" ]; then
    LOGFILE="./logs/create_daylily_s3_${region}.log"
fi

if [ "$disable_warn" != true ]; then
    echo ""
    echo "Usage: $0 [--bucket-prefix <prefix> [ --daylily-s3-version <version> (default 0.7.131c) ] [ --region <region> (default us-west-2) ] [ --disable-dryrun ] [ --help ] [ --disable-warn ]"
    echo ""
    echo "Warning: This script will create a new S3 bucket and copy data from the Daylily reference data bucket."
    echo "The new bucket will be created with the prefix specified by the --bucket-prefix argument."
    echo "ACCELERATED TRANSFER WILL BE USED. "
    echo  ""
    echo "--disable-warn flag is not set. If you are sure you want to proceed, please re-run the script with the --disable-warn flag."
    exit 1
fi

if [[ "$s3_reference_data_version" != "0.7.131c" ]]; then
    echo "Error: Only version '0.7.131c' is supported. Exiting."
    exit 1
else
    echo "Using Daylily S3 reference data version: $s3_reference_data_version"
    source_bucket="daylily-omics-analysis-references-public"
fi


if [[ "$AWS_PROFILE" == "" ]]; then
    echo "Please set AWS_PROFILE to continue"
    exit 1
fi

if [[ "$region" == "" ]]; then
    echo "Please provide a region to create the new bucket in."
    exit 1
fi

if [[ "$bucket_prefix" == "" ]]; then
    echo "Please provide a bucket prefix."
    exit 1
fi

if [[ "$profile" == "setme" || "$AWS_PROFILE" != "$profile"  ]]; then
    echo "Please set AWS_PROFILE and specify the matching string with --profile to continue. AWS_PROFILE: $AWS_PROFILE, --profile: $profile ."
    exit 1
fi

echo ""
echo ""
echo " >  >>   >>> AWS_PROFILE: $AWS_PROFILE is being used."
echo ""
sleep 2

new_bucket="${bucket_prefix}-omics-analysis-${region}"
echo "Creating bucket: $new_bucket"

accel_enabled="--endpoint-url https://s3-accelerate.amazonaws.com"
# Prompt user to use acceleration endpoint or not
read -p "Use S3 acceleration endpoint? (y/n): " use_accel

if [[ "$use_accel" == "y" || "$use_accel" == "Y" ]]; then
    accel_endpoint=$accel_enabled
else
    accel_endpoint=''
fi

echo "Using acceleration ( $use_accel ): '$accel_endpoint'"


# Check if the bucket with the specified prefix already exists
check_bucket_exists() {
    if aws s3api head-bucket --bucket "$1" --region "$region" 2>/dev/null; then
        echo "Error: Bucket '$1' already exists. Exiting."
        exit 1
    fi
}

# Create the new bucket
create_bucket() {
    echo "Creating bucket '$new_bucket'..."
    if [ "$disable_dryrun" = false ]; then
        echo "[Dry-run] Skipping bucket creation."
    else

        echo "Creating bucket '$new_bucket' in region '$region'..."
        if [ "$region" = "us-east-1" ]; then
            aws s3api create-bucket --bucket "$new_bucket" --region "$region"
        else
            aws s3api create-bucket --bucket "$new_bucket" --region "$region" --create-bucket-configuration LocationConstraint="$region"
        fi
        echo "Bucket '$new_bucket' created successfully."
        aws s3api put-bucket-accelerate-configuration --bucket ${new_bucket} --accelerate-configuration Status=Enabled 

    fi
}


# Check if the bucket already exists
echo "Checking if bucket '$new_bucket' exists..."
check_bucket_exists "$new_bucket"

# Create the bucket if it does not exist
create_bucket

# Compose bucket creation commands

# Core dirs to copy
ver_info_file="config/day_cluster/daylily_reference_version_$s3_reference_data_version.info"
echo "$s3_reference_data_version" > $ver_info_file
cmd_version="aws s3 cp $ver_info_file  s3://${new_bucket}/s3_reference_data_version.info"
cmd_cluster_boot_config="aws s3 cp s3://${source_bucket}/cluster_boot_config s3://${new_bucket}/cluster_boot_config --recursive  --request-payer requester $accel_endpoint --metadata-directive REPLACE "
cmd_cached_envs="aws s3 cp s3://${source_bucket}/data/cached_envs s3://${new_bucket}/data/cached_envs --recursive --request-payer requester $accel_endpoint --metadata-directive REPLACE "
cmd_libs="aws s3 cp s3://${source_bucket}/data/lib s3://${new_bucket}/data/lib --recursive --request-payer requester  $accel_endpoint --metadata-directive REPLACE "
cmd_tool_specific_resources="aws s3 cp s3://${source_bucket}/data/tool_specific_resources s3://${new_bucket}/data/tool_specific_resources --recursive --request-payer requester $accel_endpoint --metadata-directive REPLACE "
cmd_budget="aws s3 cp s3://${source_bucket}/data/budget_tags s3://${new_bucket}/data/budget_tags --recursive --request-payer requester $accel_endpoint --metadata-directive REPLACE "

# b37 references
cmd_b37_ref="aws s3 cp s3://${source_bucket}/data/genomic_data/organism_references/H_sapiens/b37 s3://${new_bucket}/data/genomic_data/organism_references/H_sapiens/b37 --recursive --request-payer requester $accel_endpoint --metadata-directive REPLACE "
cmd_b37_annotations="aws s3 cp s3://${source_bucket}/data/genomic_data/organism_annotations/H_sapiens/b37 s3://${new_bucket}/data/genomic_data/organism_annotations/H_sapiens/b37 --recursive --request-payer requester $accel_endpoint --metadata-directive REPLACE "

# hg38 references
cmd_hg38_ref="aws s3 cp s3://${source_bucket}/data/genomic_data/organism_references/H_sapiens/hg38 s3://${new_bucket}/data/genomic_data/organism_references/H_sapiens/hg38 --recursive --request-payer requester $accel_endpoint --metadata-directive REPLACE "
cmd_hg38_annotations="aws s3 cp s3://${source_bucket}/data/genomic_data/organism_annotations/H_sapiens/hg38 s3://${new_bucket}/data/genomic_data/organism_annotations/H_sapiens/hg38 --recursive --request-payer requester $accel_endpoint --metadata-directive REPLACE "

# Concordance Reads
cmd_giab_reads="aws s3 cp s3://${source_bucket}/data/genomic_data/organism_reads s3://${new_bucket}/data/genomic_data/organism_reads --recursive --request-payer requester $accel_endpoint --metadata-directive REPLACE "

# CRAMS
## cmd_giab_crams="aws s3 cp s3://${source_bucket}/data/cram_data s3://${new_bucket}/data/cram_data --recursive --request-payer requester $accel_endpoint --metadata-directive REPLACE "


if [ "$disable_dryrun" = false ]; then
    echo "[Dry-run] Skipping S3 COPY commands, which would be:"
    echo "$cmd_version"
    echo "$cmd_cluster_boot_config"
    echo "$cmd_cached_envs"
    echo "$cmd_libs"
    echo "$cmd_tool_specific_resources"
    echo "$cmd_budget"
    
    if [ "$exclude_hg38_refs" = true ]; then
        echo ">>>> THESE TO BE EXCLUDED"
        echo "$cmd_hg38_ref"
        echo "$cmd_hg38_annotations"
    else
        echo "THESE WILL BE INCLUDED"
        echo "$cmd_hg38_ref"
        echo "$cmd_hg38_annotations"
    fi

    if [ "$exclude_b37_refs" = true ]; then
        echo ">>>> THESE TO BE EXCLUDED"
        echo "$cmd_b37_ref"
        echo "$cmd_b37_annotations"
    else
        echo "THESE WILL BE INCLUDED"
        echo "$cmd_b37_ref"
        echo "$cmd_b37_annotations"
    fi

    if [ "$exclude_giab_reads" = true ]; then
        echo ">>>> THESE TO BE EXCLUDED"
        echo "$cmd_giab_reads"
        #echo "$cmd_giab_crams"
    else
        echo "THESE WILL BE INCLUDED"
        echo "$cmd_giab_reads"
        #echo "$cmd_giab_crams"
    fi
else

    # These are core dirs that need to be copied first
    echo "Running the following commands serially"

    echo ""
    echo "NOW RUNNING 1 of 12"
    echo "...$cmd_version"
    $cmd_version >> $LOGFILE 2>&1  && echo "success" || echo ">>>FAILED<<< will be fatal"
    

    echo " "
    echo "NOW RUNNING 2 of 12"
    echo "...$cmd_cluster_boot_config"
    $cmd_cluster_boot_config  >> $LOGFILE 2>&1 && echo "success" || echo ">>>FAILED<<< will be fatal"
    

    echo "NOW RUNNING 3 of 12"
    echo "... $cmd_cached_envs"
    $cmd_cached_envs >> $LOGFILE 2>&1 && echo "success" || echo ">>>FAILED<<< prob ok, but unexpected"
  
    echo "NOW RUNNING 4 of 12"
    echo "...$cmd_libs"
    $cmd_libs >> $LOGFILE 2>&1  && echo "success" || echo ">>>FAILED<<< will be fatal"

    echo "NOW RUNNING 5 of 12"
    echo "...$cmd_tool_specific_resources"
    $cmd_tool_specific_resources  >> $LOGFILE 2>&1  && echo "success" || echo ">>>FAILED<<< will be fatal"

    echo "NOW RUNNING 6 of 12"
    echo "...$cmd_budget"
    $cmd_budget  >> $LOGFILE 2>&1  && echo "success" || echo ">>>FAILED<<< will be fatal"
    

    # Execute commands based on flags
    if [ "$exclude_hg38_refs" = true ]; then
        echo "Skipping hg38 references and annotations copy:"
        echo "$cmd_hg38_ref"
        echo "$cmd_hg38_annotations"
    else
        echo "NOW RUNNING 7 of 12"
        echo "...$cmd_hg38_ref"
        $cmd_hg38_ref  >> $LOGFILE 2>&1  && echo "success" || echo ">>>FAILED<<< will be fatal if hg38 is needed" 

        echo "NOW RUNNING 8 of 12"
        echo "...$cmd_hg38_annotations"
        $cmd_hg38_annotations >> $LOGFILE 2>&1  && echo "success" || echo ">>>FAILED<<< will be fatal if hg38 is needed" 

    fi

    if [ "$exclude_b37_refs" = true ]; then
        echo "Skipping b37 references and annotations copy:"
        echo "$cmd_b37_ref"
        echo "$cmd_b37_annotations"
    else
        echo "NOW RUNNING 9 of 12"
        echo "...$cmd_b37_ref"
        $cmd_b37_ref  >> $LOGFILE 2>&1   && echo "success" || echo ">>>FAILED<<< will be fatal if b37 is needed" 

        echo "NOW RUNNING 10 of 12"
        echo "...$cmd_b37_annotations"
        $cmd_b37_annotations >> $LOGFILE 2>&1 && echo "success" || echo ">>>FAILED<<< will be fatal if b37 is needed" 

    fi

    if [ "$exclude_giab_reads" = true ]; then
        echo "Skipping GIAB reads copy:"
        echo "$cmd_giab_reads"

        echo "Skipping GIAB crams copy:"
        echo "$cmd_giab_crams"

    else
        echo "NOW RUNNING 11 of 12"
        echo "...$cmd_giab_reads"
        $cmd_giab_reads >> $LOGFILE 2>&1 && echo "success" || echo ">>>FAILED<<< will be fatal if GIAB reads are needed" 

        #echo "NOW RUNNING 12 of 12"
        #echo "...$cmd_giab_crams"
        #$cmd_giab_crams >> $LOGFILE 2>&1 && echo "success" || echo ">>>FAILED<<< will be fatal #if GIAB crams are needed"    
    fi


fi

if [ "$disable_dryrun" = false ]; then
    echo "[Dry-run] Bucket setup for '$new_bucket' would complete successfully. set --disable-dryrun to proceed."
    exit 0
else
    echo "Bucket setup for '$new_bucket' completed successfully."
fi


echo ""
echo "Cloning of daylily-references-public to '$new_bucket' completed, check the log for more"
echo "... see $LOGFILE for details"
