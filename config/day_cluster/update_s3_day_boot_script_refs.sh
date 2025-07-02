#!/bin/bash

bucket=$1
# Define the source and destination paths
REF_PATH="daylily2:daylily-references-public/cluster_boot_config/"
ACTIVE_PATH="daylily-service-lsmc:lsmc-dayoa-omics-analysis-eu-central-1/cluster_boot_config/"

# List of files to copy
FILES=(
    "sbatch"
)

# Iterate over the files and copy each one using rclone
for file in "${FILES[@]}"; do
    if [[ -f "$file" ]]; then
        echo "Copying $file to $REMOTE_PATH..."
        rclone copy "$file" "$REF_PATH"

        if [[ $? -eq 0 ]]; then
            echo "Successfully copied $file $REF_PATH."
        else
            echo "Failed to copy $file $REF_PATH ."
            exit 2
        fi

        rclone copy "$file" "$ACTIVE_PATH"
        if [[ $? -eq 0 ]]; then
            echo "Successfully copied $file to $ACTIVE_PATH."
        else
            echo "Failed to copy $file to $ACTIVE_PATH."
            exit 2
        fi
    else
        echo "File $file not found, skipping."
        exit 2
    fi
done

# List the contents of the remote ref directory
echo "Listing contents of $REF_PATH..."
rclone ls "$REF_PATH"

# List the contents of the remote active directory
echo "Listing contents of $ACTIVE_PATH..."
rclone ls "$ACTIVE_PATH"



