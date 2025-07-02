#!/usr/bin/env python

import subprocess
import statistics
import argparse
from copy import deepcopy
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
import json


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Insert spotprice max  into pcluster_config.yaml, with one of two strategies: median(spot)+BUMP_PRICE or median(dedicated)/2 .")
    parser.add_argument("-i", "--input", required=True, help="Input YAML configuration file path.")
    parser.add_argument("-b", "--bump-price", type=float, required=False, default=2.34, help="Price bump to add to the median spot price. default=1.81")
    parser.add_argument("-o", "--output", required=True, help="Output YAML configuration file path.")
    parser.add_argument("--az", required=True, help="Availability zone.")
    parser.add_argument("--profile", help="AWS CLI profile to use.")
    parser.add_argument("--avg-price-of", choices=['spot', 'dedicated'], default='spot', help="Type of price to calculate: spot or dedicated.")
    return parser.parse_args()

def run_aws_command(command):
    """Run an AWS CLI command and return the result as a string."""
    try:
        return subprocess.check_output(command, text=True).strip()
    except subprocess.CalledProcessError as e:
        print(f"Error executing {' '.join(command)}: {e}")
        return None

def get_instance_price(instance_type, az, profile, price_type):
    """Retrieve the price for an instance type in a specific AZ."""
    region = az[:-1]  # Derive region from AZ

    if price_type == 'spot':
        command = [
            "aws", "ec2", "describe-spot-price-history",
            "--instance-types", instance_type,
            "--availability-zone", az,
            "--region", region,
            "--product-description", "Linux/UNIX",
            "--query", "SpotPriceHistory[0].SpotPrice",
            "--output", "text",
        ]
        if profile:
            command.extend(["--profile", profile])

        try:
            result = run_aws_command(command)
        except Exception as e:
            print(f"Error executing {' '.join(command)}: {e}")
            print(f"\n\tCONFIRM INSTANCE TYPE: {instance_type} is valid in {az} .\n\n")
            raise e
        ret = 5.55
        try:
            ret = float(result)
        except Exception as e:
            print(f"Error converting result to float: {e}")
            print(f"\n\tCONFIRM INSTANCE TYPE: {instance_type} is valid in {az} .\n\n")

        return ret
    
    elif price_type == 'dedicated':
        pricing_region = 'us-east-1'  # Use a region where the Pricing API is available
        location = get_region_name(region)  # Get the full region name
        filters = [
            {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
            {"Type": "TERM_MATCH", "Field": "location", "Value": location},
            {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Dedicated"},
            {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
            {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
            {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"},
        ]
        filters_json = json.dumps(filters)
        command = [
            "aws", "pricing", "get-products",
            "--region", pricing_region,
            "--service-code", "AmazonEC2",
            "--filters", filters_json,
            "--query", "PriceList[0]",
            "--output", "text",
        ]
        if profile:
            command.extend(["--profile", profile])
        result = run_aws_command(command)

        if result:
            try:
                price_item = json.loads(result)
                # Extract the price from the pricing JSON
                for terms in price_item.get('terms', {}).get('OnDemand', {}).values():
                    for price_dimension in terms.get('priceDimensions', {}).values():
                        price_per_unit = price_dimension.get('pricePerUnit', {}).get('USD')
                        if price_per_unit:
                            return float(price_per_unit)
            except json.JSONDecodeError as e:
                print(f"JSON decoding error for instance {instance_type}: {e}")
        else:
            print(f"No pricing data returned for {instance_type}.")
        return None
def get_region_name(region_code):
    """Dynamically map AWS region codes to region names required by AWS Pricing API."""
    import json

    # Use the AWS Pricing API to get all available locations
    pricing_region = 'us-east-1'  # The Pricing API is available in specific regions
    command = [
        "aws", "pricing", "get-attribute-values",
        "--region", pricing_region,
        "--service-code", "AmazonEC2",
        "--attribute-name", "location",
        "--output", "json"
    ]

    result = run_aws_command(command)
    if result:
        locations = json.loads(result)
        location_list = [item['Value'] for item in locations.get('AttributeValues', [])]

        # Attempt to match the region code to the location name
        # We'll use a heuristic approach based on known patterns
        # IS THIS REALLY NOT EASY TO GET VIA AWS???

        # Common patterns for region names
        region_patterns = {
            'us-east-1': 'US East \\(N.*Virginia\\)',
            'us-east-2': 'US East \\(Ohio\\)',
            'us-west-1': 'US West \\(N.*California\\)',
            'us-west-2': 'US West \\(Oregon\\)',
            'af-south-1': 'Africa \\(Cape Town\\)',
            'ap-east-1': 'Asia Pacific \\(Hong Kong\\)',
            'ap-south-1': 'Asia Pacific \\(Mumbai\\)',
            'ap-northeast-3': 'Asia Pacific \\(Osaka\\)',
            'ap-northeast-2': 'Asia Pacific \\(Seoul\\)',
            'ap-southeast-1': 'Asia Pacific \\(Singapore\\)',
            'ap-southeast-2': 'Asia Pacific \\(Sydney\\)',
            'ap-northeast-1': 'Asia Pacific \\(Tokyo\\)',
            'ca-central-1': 'Canada \\(Central\\)',
            'eu-central-1': 'EU \\(Frankfurt\\)',
            'eu-west-1': 'EU \\(Ireland\\)',
            'eu-west-2': 'EU \\(London\\)',
            'eu-south-1': 'EU \\(Milan\\)',
            'eu-west-3': 'EU \\(Paris\\)',
            'eu-north-1': 'EU \\(Stockholm\\)',
            'me-south-1': 'Middle East \\(Bahrain\\)',
            'sa-east-1': 'South America \\(São Paulo\\)',
            # Add other regions as needed
        }

        import re

        # Find the matching region name
        pattern = region_patterns.get(region_code)
        if pattern:
            for location in location_list:
                if re.match(pattern, location):
                    return location

        print(f"Region code {region_code} not found in patterns. Using default mapping.")

    else:
        print("Could not retrieve locations from AWS Pricing API.")

    # Fallback to region code if no match is found
    return region_code


def calculate_partition_price(queue, az, profile, price_type, bump_price):
    """Calculate the median price for all instances in the partition."""
    all_prices = []
    for resource in queue.get('ComputeResources', []):
        for instance in resource.get('Instances', []):
            instance_type = instance.get('InstanceType')
            price = get_instance_price(instance_type, az, profile, price_type)
            if price is not None:
                all_prices.append(price)
    
    if all_prices:
        median_price = round(statistics.median(all_prices), 4)
        if price_type == 'dedicated':
            median_price = round(median_price / 2.0, 4)
        else:
            median_price = round(median_price + float(bump_price), 4)
        
        # Apply the median price to all resource groups in the partition
        for resource in queue.get('ComputeResources', []):
            resource['SpotPrice'] = median_price
            pap = "(median spot price)" if price_type == 'spot' else "(median on-demand/2)"
            resource.yaml_add_eol_comment(f'Calculated using {pap}.', key='SpotPrice', column=0)
    else:
        print(f"Could not retrieve {price_type} prices for instances in partition {queue.get('Name')}.")

def process_slurm_queues(config, az, profile, price_type, bump_price):
    """Process all Slurm queues to calculate and update prices."""
    for queue in config.get('Scheduling', {}).get('SlurmQueues', []):
        if not isinstance(queue, CommentedMap):
            queue = CommentedMap(queue)
        calculate_partition_price(queue, az, profile, price_type, bump_price)


def main():
    args = parse_arguments()

    az = args.az
    profile = args.profile
    price_type = args.avg_price_of

    with open(args.input, 'r') as f:
        yaml_loader = YAML()
        yaml_loader.preserve_quotes = True
        config = yaml_loader.load(f)

    process_slurm_queues(config, az, profile, price_type, float(args.bump_price))

    with open(args.output, 'w') as f:
        yaml_dumper = YAML()
        yaml_dumper.explicit_start = True
        yaml_dumper.explicit_end = True
        yaml_dumper.dump(config, f)

    print(f"Updated configuration saved to {args.output}.")

if __name__ == "__main__":
    main()
