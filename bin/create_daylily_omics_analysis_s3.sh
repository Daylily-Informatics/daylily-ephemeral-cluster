#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'USAGE'
Usage: ./bin/create_daylily_omics_analysis_s3.sh [OPTIONS]

Wrapper around the `daylily-omics-references` CLI that clones the
Daylily omics analysis reference bucket into your account.

Options:
  --daylily-s3-version <version>  Reference data version to clone (default: 0.7.131c)
  --region <region>               AWS region for the new bucket (required)
  --bucket-prefix <prefix>        Prefix for the target bucket (required)
  --disable-dryrun                Execute the clone instead of performing a dry-run
  --disable-warn                  Acknowledge that the operation will create resources
  --exclude-hg38-refs             Skip cloning hg38 references and annotations
  --exclude-b37-refs              Skip cloning b37 references and annotations
  --exclude-giab-reads            Skip cloning GIAB concordance reads
  --profile <profile>             AWS profile to use (defaults to AWS_PROFILE env var)
  --log-file <path>               File to capture AWS CLI output from the clone
  --use-acceleration              Enable the S3 accelerate endpoint during cloning
  -h, --help                      Show this message and exit
USAGE
}

require_reference_cli() {
    if ! command -v daylily-omics-references >/dev/null 2>&1; then
        cat <<'ERR' >&2
Error: 'daylily-omics-references' was not found in PATH.
Install version 0.1.0 or newer with:

    pip install "git+https://github.com/Daylily-Informatics/daylily-omics-references.git@0.1.0"

The dependency is installed automatically when you create the DAY-EC
conda environment; please ensure that environment is active.
ERR
        exit 2
    fi
}

resolve_aws_profile() {
    local provided_profile="$1"
    local final_profile=""

    if [[ -n "$provided_profile" ]]; then
        final_profile="$provided_profile"
    elif [[ -n "${AWS_PROFILE:-}" ]]; then
        final_profile="$AWS_PROFILE"
    else
        echo "Error: AWS_PROFILE is not set. Please export AWS_PROFILE or use --profile." >&2
        exit 1
    fi

    if command -v aws >/dev/null 2>&1; then
        local available_profiles
        if ! available_profiles=$(aws configure list-profiles 2>/dev/null); then
            echo "Error: Unable to list AWS profiles. Ensure the AWS CLI is installed and configured." >&2
            exit 1
        fi
        if ! grep -Fxq "$final_profile" <<<"$available_profiles"; then
            echo "Error: AWS profile '$final_profile' not found. Please set AWS_PROFILE to a valid profile." >&2
            exit 1
        fi
    else
        echo "Error: AWS CLI was not detected in PATH. Install and configure the AWS CLI before proceeding." >&2
        exit 1
    fi

    export AWS_PROFILE="$final_profile"

    if [[ "$AWS_PROFILE" == "default" ]]; then
        echo "WARNING: AWS_PROFILE is set to 'default'. Sleeping for 1 second..."
        sleep 1
    else
        echo "Using AWS profile: $AWS_PROFILE"
    fi
}

reference_version="0.7.131c"
region=""
bucket_prefix=""
profile_arg=""
log_file=""
exclude_hg38=false
exclude_b37=false
exclude_giab=false
execute_clone=false
disable_warn=false
use_acceleration=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --daylily-s3-version)
            reference_version="$2"
            shift 2
            ;;
        --region)
            region="$2"
            shift 2
            ;;
        --bucket-prefix)
            bucket_prefix="$2"
            shift 2
            ;;
        --disable-dryrun)
            execute_clone=true
            shift
            ;;
        --disable-warn)
            disable_warn=true
            shift
            ;;
        --exclude-hg38-refs)
            exclude_hg38=true
            shift
            ;;
        --exclude-b37-refs)
            exclude_b37=true
            shift
            ;;
        --exclude-giab-reads)
            exclude_giab=true
            shift
            ;;
        --profile)
            profile_arg="$2"
            shift 2
            ;;
        --log-file)
            log_file="$2"
            shift 2
            ;;
        --use-acceleration)
            use_acceleration="yes"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown parameter: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [[ "$disable_warn" != true ]]; then
    echo ""
    echo "Warning: This command will create a new S3 bucket and clone reference data." >&2
    echo "Re-run with --disable-warn if you understand and accept these actions." >&2
    exit 1
fi

if [[ -z "$region" ]]; then
    echo "Error: --region is required." >&2
    usage >&2
    exit 1
fi

if [[ -z "$bucket_prefix" ]]; then
    echo "Error: --bucket-prefix is required." >&2
    usage >&2
    exit 1
fi

require_reference_cli
resolve_aws_profile "$profile_arg"

profile="$AWS_PROFILE"

if [[ -z "$log_file" ]]; then
    mkdir -p ./logs
    log_file="./logs/create_daylily_s3_${region}.log"
fi
mkdir -p "$(dirname "$log_file")"

if [[ -z "$use_acceleration" ]]; then
    read -r -p "Use S3 acceleration endpoint? (y/N): " accel_response || accel_response=""
    if [[ "$accel_response" =~ ^[Yy]$ ]]; then
        use_acceleration="yes"
    else
        use_acceleration="no"
    fi
fi

if [[ "$execute_clone" == true ]]; then
    echo "Executing clone operation (dry-run disabled)."
else
    echo "Running in dry-run mode. Pass --disable-dryrun to perform the actual clone."
fi

cmd=(daylily-omics-references)
[[ -n "$profile" ]] && cmd+=(--profile "$profile")
[[ -n "$region" ]] && cmd+=(--region "$region")
cmd+=(clone --bucket-prefix "$bucket_prefix" --region "$region" --version "$reference_version")
[[ "$execute_clone" == true ]] && cmd+=(--execute)
[[ "$use_acceleration" == "yes" ]] && cmd+=(--use-acceleration)
[[ "$exclude_hg38" == true ]] && cmd+=(--exclude-hg38)
[[ "$exclude_b37" == true ]] && cmd+=(--exclude-b37)
[[ "$exclude_giab" == true ]] && cmd+=(--exclude-giab)
[[ -n "$log_file" ]] && cmd+=(--log-file "$log_file")

echo "Invoking: ${cmd[*]}"
"${cmd[@]}"

echo "Clone command completed. Review $log_file for AWS CLI output if needed."
