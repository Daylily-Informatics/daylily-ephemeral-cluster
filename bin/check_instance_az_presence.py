#!/usr/bin/env python

import subprocess
import sys
import os
import csv

# Ensure DAY-EC conda environment is active
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "helpers"))
from ensure_dayec import ensure_dayec
ensure_dayec(quiet=True)


def get_all_regions():
    """Retrieve all available AWS regions."""
    try:
        command = ["aws", "ec2", "describe-regions", "--query", "Regions[*].RegionName", "--output", "text"]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return result.stdout.strip().split()
    except subprocess.CalledProcessError as e:
        print(f"Error fetching regions: {e.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
def get_spot_price(instance_type, region):
    """Fetch the recent spot price for the given instance type."""
    try:
        command = [
            "aws", "ec2", "describe-spot-price-history",
            "--instance-types", instance_type,
            "--product-description", "Linux/UNIX",
            "--region", region,
            "--start-time", "2024-10-20T00:00:00Z",
            "--query", "SpotPriceHistory[0].SpotPrice",
            "--output", "text", "--profile", os.environ['AWS_PROFILE']
        ]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        spot_price_str = result.stdout.strip()

        if not spot_price_str or spot_price_str.lower() == 'none':
            print(f"No spot price available for {instance_type} in {region}.")
            return None

        return float(spot_price_str)
    except ValueError as ve:
        print(f"Invalid spot price value for {instance_type} in {region}: {ve}")
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error fetching spot price: {e.stderr.strip()}", file=sys.stderr)
        return None

def get_dedicated_price(instance_type):
    """Fetch the on-demand (dedicated) hourly price for the given instance type."""
    dedicated_prices = {
        "c7i.48xlarge": 8.5680, "c7i.metal-48xl": 8.5680, 
        # Add more instance types as needed
    }
    return dedicated_prices.get(instance_type)

def calculate_spot_discount(dedicated_price, spot_price):
    """Calculate the percentage discount between spot and dedicated prices."""
    if dedicated_price and spot_price:
        return round(((dedicated_price - spot_price) / dedicated_price) * 100, 2)
    return None

def calculate_per_vcpu_cost(price, vcpus):
    """Calculate the per-vCPU cost."""
    return round(price / vcpus, 4) if price and vcpus else None

def parse_instance_types(file_path):
    """Parse unique instance types from the input file."""
    try:
        with open(file_path, 'r') as file:
            return list(line.strip() for line in file if line.strip())
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.", file=sys.stderr)
        sys.exit(1)

def check_spot_availability(instance_type, region):
    """Check spot availability by querying the AWS API."""
    try:
        command = [
            "aws", "ec2", "describe-spot-price-history",
            "--instance-types", instance_type,
            "--product-description", "Linux/UNIX",
            "--region", region,
            "--start-time", "2024-10-20T00:00:00Z",
            "--query", "SpotPriceHistory[*].AvailabilityZone",
            "--output", "text", "--profile", os.environ['AWS_PROFILE']
        ]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return set(result.stdout.strip().split()) if result.stdout.strip() else None
    except subprocess.CalledProcessError as e:
        print(f"Error checking spot availability: {e.stderr.strip()}", file=sys.stderr)
        return None

def write_to_tsv(data, filename="spot_availability.tsv"):
    """Write the results to a TSV file."""
    with open(filename, mode="w", newline="") as file:
        writer = csv.writer(file, delimiter="\t")
        writer.writerow([
            "InstanceType", "Region", "AvailabilityZone", "Available", 
            "RecentSpotPrice", "DedicatedPrice", "SpotDiscountPercent", 
            "SpotPerVCPU", "DedicatedPerVCPU"
        ])
        for row in data:
            writer.writerow(row)

def write_to_pcluster_queue(instance_types, filename="pcluster_queue.txt"):
    """Write the instance types to a pcluster queue text file."""
    with open(filename, mode="w") as file:
        for instance_type in instance_types:
            file.write(f"  - InstanceType: {instance_type}\n")
 
def parse_vcpus(instance_type):
    """Extract the number of vCPUs from the instance type."""
    try:
        # Check if the instance type ends with "metal"
        if "metal" in instance_type:
            # Assume the full size, for example, 48xlarge corresponds to 192 vCPUs
            base = instance_type.split('-')[0]  # e.g., "m7i"
            size = base.split('.')[1]  # e.g., "48xlarge"
            return int(size.split('x')[0]) * 4  # Adjust as needed based on AWS instance types

        # For non-metal instances
        size = instance_type.split('.')[1]  # e.g., "48xlarge"
        return int(size.split('x')[0]) * 4  # Adjust multiplier if needed
    except (IndexError, ValueError) as e:
        print(f"Error parsing vCPUs for {instance_type}: {e}", file=sys.stderr)
        return None  # Return None to indicate parsing failed

def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <instance_file>", file=sys.stderr)
        sys.exit(1)

    instance_file = sys.argv[1]
    instance_types = parse_instance_types(instance_file)

    regions = get_all_regions()
    data = []

    for instance_type in instance_types:
        print(f"\nChecking spot availability for {instance_type}...")
        dedicated_price = get_dedicated_price(instance_type)
        vcpus = 192

        if vcpus is None:
            print(f"Skipping {instance_type} due to vCPU parsing error.")
            continue
        print(regions)
        for region in regions:
            azs = check_spot_availability(instance_type, region)
            spot_price = get_spot_price(instance_type, region)
            spot_discount = calculate_spot_discount(dedicated_price, spot_price)
            spot_per_vcpu = calculate_per_vcpu_cost(spot_price, vcpus)
            dedicated_per_vcpu = calculate_per_vcpu_cost(dedicated_price, vcpus)

            if azs:
                for az in azs:
                    data.append([
                        instance_type, region, az, "Yes", spot_price, 
                        dedicated_price, spot_discount, spot_per_vcpu, 
                        dedicated_per_vcpu
                    ])
                print(f"  Region: {region} - Available in: {', '.join(azs)}")
            else:
                data.append([
                    instance_type, region, "N/A", "No", spot_price, 
                    dedicated_price, spot_discount, spot_per_vcpu, 
                    dedicated_per_vcpu
                ])
                print(f"  Region: {region} - Not available.")

    write_to_tsv(data)
    write_to_pcluster_queue(instance_types)


if __name__ == "__main__":
    main()
