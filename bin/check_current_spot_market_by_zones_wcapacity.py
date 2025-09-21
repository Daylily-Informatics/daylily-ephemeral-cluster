#!/usr/bin/env python

import argparse
import os
import re
import statistics
import subprocess
import sys
import time

import yaml
from colr import color
from math import isnan, fsum
from tabulate import tabulate

# Define ANSI colors for different modes
COLORS = {
    'dark': {
        'zone': (135, 206, 235),
        'teal': (0, 255, 222),
        'orange': (255, 140, 0),
        'gray': (211, 211, 211),
        'dim': (169, 169, 169),
        'yellow': (255, 255, 0),
        'highlight': (0, 255, 0),
        'header': (255, 255, 255)
    },
    'light': {
        'zone': (0, 0, 139),
        'teal': (0, 128, 128),
        'orange': (255, 69, 0),
        'gray': (169, 169, 169),
        'dim': (105, 105, 105),
        'yellow': (255, 215, 0),
        'highlight': (0, 128, 0),
        'header': (0, 0, 0)
    },
    'loud': {
        'zone': (255, 0, 255),
        'teal': (0, 255, 0),
        'orange': (0, 255, 255),
        'gray': (255, 20, 147),
        'dim': (199, 21, 133),
        'yellow': (255, 255, 0),
        'highlight': (0, 255, 0),
        'header': (0, 0, 0)
    },
    'neon': {
        'zone': (255, 0, 255),
        'teal': (57, 255, 20),
        'orange': (255, 0, 0),
        'gray': (200, 200, 200),
        'dim': (169, 169, 169),
        'yellow': (0, 255, 255),
        'highlight': (0, 255, 0),
        'header': (255, 255, 255)
    }
}

TRANSFER_RATES = {
    'internet': 0.09,  # $/G to internet
    'within_region': 0.01,  # $/G within region
    'cross_region': 0.02  # $/G across regions
}

STORAGE_COSTS = {'standard': 0.023, 'glacier': 0.004}  # $/G/month

def apply_color(value, best=None, worst=None, highlight=False, dim=False, mode='dark'):
    """Colorize values based on thresholds using the selected mode."""
    colors = COLORS[mode]
    # Choose the appropriate color based on value comparison
    if highlight:
        color_value = colors['highlight']
    elif dim:
        color_value = colors['dim']
    elif best is not None and value == best:
        color_value = colors['teal']
    elif worst is not None and value == worst:
        color_value = colors['orange']
    else:
        color_value = colors['gray']

    # Return the value wrapped in the color using the colr module
    return color(f"{value}", fore=color_value)

def harmonic_mean(data):
    """Calculate the harmonic mean of a list of numbers."""
    if not data or any(d == 0 for d in data):
        return float('nan')  # Avoid division by zero
    return len(data) / fsum(1 / d for d in data)

def stability_metric(prices):
    """Calculate the volatility as the difference between the max and min prices."""
    if not prices:
        return float('nan')
    return max(prices) - min(prices)

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Calculate genomic workflow costs. Default costs all drawn from actual AWS run analysis, see: https://docs.google.com/spreadsheets/d/1x5RlXYAq3lTNChs6mVnP9NLytLkCT3a8OAtJfgUyWRg/edit?gid=480568932#gid=480568932 ")
    
    # Add arguments with default values and %(default)s in help string
    parser.add_argument(
        "-i", "--input", 
        default="config/day_cluster/prod_cluster.yaml", 
        help="YAML config path (default: %(default)s)."
    )
    
    parser.add_argument(
        "-o", "--output", 
        required=True, 
        help="Output TSV file path (required)."
    )
    
    parser.add_argument(
        "--profile",
        help="AWS CLI profile to use (defaults to AWS_PROFILE environment variable)."
    )
    
    parser.add_argument(
        "--partition", 
        default="i192", 
        help="Partition name, the naming pattern for daylily partitions is (hardware)(#vcpu), so intel 192vcpu is 'i192', the vcpu is stripped from the partition name to derive the # vcpus (default: %(default)s)."
    )
    
    parser.add_argument(
        "--zones", 
        default="us-west-2a,us-west-2b,us-west-2c,us-west-2d,us-east-1a,us-east-1b,us-east-1c,us-east-1d,ap-south-1a,ap-south-1b,ap-south-1c,ap-south-1d,eu-central-1a,eu-central-1b,eu-central-1c,ca-central-1a,ca-central-1b,ca-central-1c",
        help="Comma-separated zones (default: %(default)s).\n ALLZONES: ap-south-2a,ap-south-2b,ap-south-2c,ap-south-1a,ap-south-1b,ap-south-1c,"
            "eu-south-1a,eu-south-1b,eu-south-1c,eu-south-2a,eu-south-2b,eu-south-2c,me-central-1a,me-central-1b,me-central-1c,il-central-1a,il-central-1b,il-central-1c,"
            "ca-central-1a,ca-central-1b,ca-central-1d,eu-central-1a,eu-central-1b,eu-central-1c,eu-central-2a,eu-central-2b,eu-central-2c,"
            "us-west-1a,us-west-1b,us-west-2a,us-west-2b,us-west-2c,us-west-2d,af-south-1a,af-south-1b,af-south-1c,eu-north-1a,eu-north-1b,eu-north-1c,"
            "eu-west-3a,eu-west-3b,eu-west-3c,eu-west-2a,eu-west-2b,eu-west-2c,eu-west-1a,eu-west-1b,eu-west-1c,"
            "ap-northeast-3a,ap-northeast-3b,ap-northeast-3c,ap-northeast-2a,ap-northeast-2b,ap-northeast-2c,ap-northeast-2d,me-south-1a,me-south-1b,me-south-1c,"
            "ap-northeast-1a,ap-northeast-1b,ap-northeast-1c,ap-northeast-1d,sa-east-1a,sa-east-1b,sa-east-1c,ap-east-1a,ap-east-1b,ap-east-1c,"
            "ca-west-1a,ca-west-1b,ca-west-1c,ap-southeast-1a,ap-southeast-1b,ap-southeast-1c,ap-southeast-2a,ap-southeast-2b,ap-southeast-2c,"
            "ap-southeast-3a,ap-southeast-3b,ap-southeast-3c,ap-southeast-4a,ap-southeast-4b,ap-southeast-4c,us-east-1a,us-east-1b,us-east-1c,us-east-1d,us-east-1e,us-east-1f,"
            "ap-southeast-5a,ap-southeast-5b,ap-southeast-5c,us-east-2a,us-east-2b,us-east-2c."
    )

    
    parser.add_argument(
        "--x-coverage", 
        type=float, 
        default=30.0, 
        help="Coverage for analysis (e.g., 30x, this all assumes illumina 2x150) ( default: %(default)s)."
    )    
    
    parser.add_argument(
        "--vcpu-min-per-x-to-align", 
        type=float, 
        default=307.2, 
        help="vCPU-minutes per 1X coverage to align, sort and dedup. bwa mem2: 307.2, sentieon bwa: 384, strobealigner: 172.8  (default: %(default)s)."
    )
        
    parser.add_argument(
        "--vcpu-min-per-x-to-snvcall", 
        type=float, 
        default=684.0, 
        help="vCPU-minutes per X coverage to SNV call. deepvariant: 684.0, Sentieon DNAscope: 70.4  ( default: %(default)s)."
    )
    
    parser.add_argument(
        "--vcpu-min-per-x-to-svcall", 
        type=float, 
        default=19.0, 
        help="vCPU-minutes per X coverage to SV call. tiddit: 19.0, manta: ??, svaba: ??   ( default: %(default)s)."
    )
    
    parser.add_argument(
        "--vcpu-min-per-x-to-other", 
        type=float, 
        default=0.021, 
        help="vCPU-minutes per X coverage, other costs (ie, Fsx active use cost, head node overhead when running to manage compute nodes). These are often fixed costs which do not scale with X coverage, but am modeling it like the others for now. default: 0.021 (rdefault: %(default)s)."
    )
    
    # File size flags
    parser.add_argument(
        "--bam-size-per-x", 
        type=float, 
        default=1.3, 
        help="BAM size per X coverage (GB) (default: %(default)s)."
    )
    
    parser.add_argument(
        "--cram-size-per-x", 
        type=float, 
        default=0.44, 
        help="CRAM size per X coverage (GB) (default: %(default)s)."
    )
    
    parser.add_argument(
        "--snv-vcf-size-per-x", 
        type=float, 
        default=0.004, 
        help="snv VCF.tgz size per X coverage (GB) (default: %(default)s)."
    )
    
    parser.add_argument(
        "--snv-gvcf-size-per-x", 
        type=float, 
        default=0.04, 
        help="snv gVCF.tgz size per X coverage (GB) (default: %(default)s)."
    )
    
    parser.add_argument(
        "--sv-vcf-size-per-x", 
        type=float, 
        default=0.004, 
        help="sv VCF.tgz size per X coverage (GB) (default: %(default)s)."
    )
    
    parser.add_argument(
        "--other-size-per-x", 
        type=float, 
        default=0.0001, 
        help="other total file size per X coverage (GB) (default: %(default)s)."
    )
    
    parser.add_argument(
        "--qc-size-per-x", 
        type=float, 
        default=0.0015, 
        help="QC data size per X coverage (GB) (default: %(default)s)."
    )
    
    parser.add_argument(
        "--mode", 
        choices=['dark', 'light', 'neon', 'loud'], 
        default='dark', 
        help="Color mode (default: %(default)s)."
    )
    
    parser.add_argument(
        "--input-data-size-per-x", 
        type=float, 
        default=1.65, 
        help="Input FASTQ size per X coverage (GB) (default: %(default)s)."
    )
    
    parser.add_argument(
        "--ec2-cost-model", 
        choices=['min', 'max', 'harmonic', 'median'], 
        default='harmonic', 
        help="EC2 cost model (use min, max, median or harmonic mean for spot prices) (default: %(default)s)."
    )
    
    return parser.parse_args()


def resolve_aws_profile(profile_argument):
    """Determine which AWS profile to use and ensure it is valid."""

    profile = profile_argument or os.environ.get('AWS_PROFILE')
    if not profile:
        print("Error: AWS_PROFILE is not set. Please export AWS_PROFILE or supply --profile.", file=sys.stderr)
        sys.exit(1)

    try:
        result = subprocess.run(
            ["aws", "configure", "list-profiles"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print("Error: AWS CLI is not installed or not found in PATH.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        print(f"Error listing AWS profiles: {message}", file=sys.stderr)
        sys.exit(1)

    available_profiles = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if profile not in available_profiles:
        print(f"Error: AWS profile '{profile}' not found. Please set AWS_PROFILE to a valid profile.", file=sys.stderr)
        sys.exit(1)

    os.environ['AWS_PROFILE'] = profile

    if profile == 'default':
        print("WARNING: AWS_PROFILE is set to 'default'. Sleeping for 1 second...")
        time.sleep(1)
    else:
        print(f"Using AWS profile: {profile}")

    return profile


def calculate_vcpu_mins(args):
    """Calculate total vCPU-minutes based on coverage."""
    return (
        (args.x_coverage * args.vcpu_min_per_x_to_align)
        + (args.x_coverage * args.vcpu_min_per_x_to_snvcall)
        + (args.x_coverage * args.vcpu_min_per_x_to_other)
        + (args.x_coverage * args.vcpu_min_per_x_to_svcall)
    )

def calculate_storage_costs(size_gb, storage_type):
    """Calculate monthly storage costs for a given size."""
    return size_gb * STORAGE_COSTS[storage_type]

def calculate_transfer_costs(size_gb, transfer_type):
    """Calculate transfer costs based on the type."""
    return size_gb * TRANSFER_RATES[transfer_type]

def dry_run_launch(instance_type, zone, profile, count):
    """Attempt a dry-run spot instance request (request-spot-instances) and return True/False."""
    region = zone[:-1]  # 'us-west-2a' -> 'us-west-2'
    cmd = [
        "aws", "ec2", "request-spot-instances", "--dry-run",
        "--instance-count", str(count),
        "--launch-specifications",
        f'[{{"InstanceType": "{instance_type}", "Placement": {{"AvailabilityZone": "{zone}"}}}}]',
        "--region", region,
        "--profile", profile
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True  # Dry-run succeeded
    except subprocess.CalledProcessError:
        return False  # Dry-run failed

def calculate_launch_success(instance_types, zones, profile):
    """
    For each zone, track total '25' successes/attempts and '100' successes/attempts across ALL instance_types.
    Returns a dict of shape:
      {
        zone: {
          '25': {'success_sum': X, 'attempt_sum': Y},
          '100': {'success_sum': X, 'attempt_sum': Y},
        },
        ...
      }
    """
    launch_data = {}
    for zone in zones:
        launch_data[zone] = {
            '25': {'success_sum': 0, 'attempt_sum': 0},
            '100': {'success_sum': 0, 'attempt_sum': 0}
        }

    for itype in instance_types:
        for zone in zones:
            # Launch 25
            success_25 = dry_run_launch(itype, zone, profile, 25)
            launch_data[zone]['25']['attempt_sum'] += 25
            if success_25:
                launch_data[zone]['25']['success_sum'] += 25

            # Launch 100
            success_100 = dry_run_launch(itype, zone, profile, 100)
            launch_data[zone]['100']['attempt_sum'] += 100
            if success_100:
                launch_data[zone]['100']['success_sum'] += 100

    return launch_data

def get_spot_price(instance_type, zone, profile):
    """Retrieve a single spot price for an instance_type in a given zone."""
    region = zone[:-1]
    cmd = [
        "aws", "ec2", "describe-spot-price-history",
        "--instance-types", instance_type,
        "--availability-zone", zone,
        "--product-description", "Linux/UNIX",
        "--query", "SpotPriceHistory[0].SpotPrice",
        "--output", "text", "--region", region,
    ]
    if profile:
        cmd.extend(["--profile", profile])
    try:
        print("running:", cmd)
        result = subprocess.check_output(cmd).decode().strip()
        print("result:", result)
        return float('nan') if result in [None, 'None', ''] else float(result)
    except subprocess.CalledProcessError as e:
        print(f"Failed to fetch price for {zone}: {e}")
        return float('nan')

def collect_spot_prices(instance_types, zones, profile):
    """Fetch spot prices for each instance type in the given zones."""
    spot_data = {}
    for instance_type in instance_types:
        spot_data[instance_type] = {}
        for zone in zones:
            price = get_spot_price(instance_type, zone, profile)
            spot_data[instance_type][zone] = price if not isnan(price) else float('nan')
    return spot_data

def extract_instances(config, partition_name):
    """Extract instance types from the given partition in the YAML configuration."""
    instances = []
    for queue in config.get('Scheduling', {}).get('SlurmQueues', []):
        if queue.get('Name') == partition_name:
            for resource in queue.get('ComputeResources', []):
                for instance in resource.get('Instances', []):
                    instances.append(instance.get('InstanceType'))
    if not instances:
        raise ValueError(f"No instances found for partition: {partition_name}")
    return instances

def get_best_worst(stats, attr):
    """Extract the best (min) and worst (max) values for a specific numeric attribute in zone_stats."""
    values = [getattr(z, attr) for z in stats if not isnan(getattr(z, attr))]
    if not values:
        return float('nan'), float('nan')  # Handle case where all values are NaN
    return min(values), max(values)

class ZoneStat:
    def __init__(self, zone_name):
        self.zone_name = zone_name
        self.instances = 0
        self.prices = []
        self.median_price = float('nan')
        self.min_price = float('nan')
        self.max_price = float('nan')
        self.harmonic_price = float('nan')
        self.stability = float('nan')
        self.cost_per_vcpu_min = float('nan')
        self.est_cost = float('nan')
        self.bam_size = float('nan')
        self.cram_size = float('nan')
        self.snv_vcf_size = float('nan')
        self.snv_gvcf_size = float('nan')
        self.sv_vcf_size = float('nan')
        self.other_size = float('nan')
        self.fastq_size = float('nan')
        self.qc_size = float('nan')

        # New fields for our dry-run success calculations:
        self.launch_25_success_perc = 0.0
        self.launch_100_success_perc = 0.0

    def calculate_statistics(self, spot_data, vcpu_mins, args, n_vcpus):
        """Compute pricing stats, derived cost, and file sizes for this zone."""
        self.prices = [spot_data[instance].get(self.zone_name, float('nan')) for instance in spot_data]
        self.prices = [p for p in self.prices if not isnan(p)]
        if self.prices:
            self.instances = len(self.prices)
            self.median_price = statistics.median(self.prices)
            self.min_price = min(self.prices)
            self.max_price = max(self.prices)
            self.harmonic_price = harmonic_mean(self.prices)
            self.stability = stability_metric(self.prices)
            self.cost_per_vcpu_median_min = float(self.median_price / n_vcpus / 60.0) 
            self.cost_per_vcpu_min_min = float(self.min_price / n_vcpus / 60.0)
            self.cost_per_vcpu_max_min = float(self.max_price / n_vcpus / 60.0)
            self.cost_per_vcpu_harmonic_min = float(self.harmonic_price / n_vcpus / 60.0)

            if args.ec2_cost_model == "min":
                self.est_cost = float(vcpu_mins) * self.cost_per_vcpu_min_min
                self.cost_per_vcpu_min = self.cost_per_vcpu_min_min
            elif args.ec2_cost_model == "max":
                self.est_cost = float(vcpu_mins) * self.cost_per_vcpu_max_min
                self.cost_per_vcpu_min = self.cost_per_vcpu_max_min
            elif args.ec2_cost_model == "harmonic":
                self.est_cost = float(vcpu_mins) * self.cost_per_vcpu_harmonic_min
                self.cost_per_vcpu_min = self.cost_per_vcpu_harmonic_min
            elif args.ec2_cost_model == "median":
                self.est_cost = float(vcpu_mins) * self.cost_per_vcpu_median_min
                self.cost_per_vcpu_min = self.cost_per_vcpu_median_min
            else:
                raise Exception("Invalid ec2_cost_model, must be one of min, max, harmonic, median")

            # Use args to calculate sizes
            self.bam_size = args.x_coverage * args.bam_size_per_x if args.bam_size_per_x else 0
            self.cram_size = args.x_coverage * args.cram_size_per_x if args.cram_size_per_x else 0
            self.snv_vcf_size = args.x_coverage * args.snv_vcf_size_per_x if args.snv_vcf_size_per_x else 0
            self.snv_gvcf_size = args.x_coverage * args.snv_gvcf_size_per_x if args.snv_gvcf_size_per_x else 0
            self.sv_vcf_size = args.x_coverage * args.sv_vcf_size_per_x if args.sv_vcf_size_per_x else 0
            self.other_size = args.x_coverage * args.other_size_per_x if args.other_size_per_x else 0
            self.fastq_size = args.x_coverage * args.input_data_size_per_x if args.input_data_size_per_x else 0
            self.qc_size = args.x_coverage * args.qc_size_per_x if args.qc_size_per_x else 0

def strip_ansi(string):
    """Remove ANSI escape sequences from a string."""
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', string)

def display_statistics(zone_stats, args):
    """Display the statistics with proper colorizing, including new Launch 25/100 columns."""
    padding = " " * (len(args.ec2_cost_model) - 7)
    headers = [
        "Region AZ", "#       \nInstance\nTypes   ",
        "Median\nSpot $", "Min \nSpot\n$   ",
        "Max \nSpot\n$   ", "Harmonic\nMean    \nSpot $  ",
        "Spot \nStab-\nility", "Launch 25\nSuccess %", "Launch 100\nSuccess %",
        "FASTQ\n(GB) ", "BAM \n(GB)", "CRAM\n(GB)",
        "snv \nVCF \n(GB)", "snv \ngVCF\n(GB)", "sv  \nVCF \n(GB)",
        "Other\n(GB) ",
        f"$ per\nvCPU min\n{args.ec2_cost_model}",
        f"~ EC2 ${padding}\n\n{args.ec2_cost_model}"
    ]

    # Map headers to corresponding ZoneStat attributes for min/max colorizing
    attr_keys = {
        'Median\nSpot $': 'median_price',
        'Min \nSpot\n$   ': 'min_price',
        'Max \nSpot\n$   ': 'max_price',
        'Harmonic\nMean    \nSpot $  ': 'harmonic_price',
        'Spot \nStab-\nility': 'stability',
        'FASTQ\n(GB) ': 'fastq_size',
        'BAM \n(GB)': 'bam_size',
        'CRAM\n(GB)': 'cram_size',
        'snv \nVCF \n(GB)': 'snv_vcf_size',
        'snv \ngVCF\n(GB)': 'snv_gvcf_size',
        'sv  \nVCF \n(GB)': 'sv_vcf_size',
        'Other\n(GB) ': 'other_size',
        f'$ per\nvCPU min\n{args.ec2_cost_model}': 'cost_per_vcpu_min',
        f'~ EC2 ${padding}\n\n{args.ec2_cost_model}': 'est_cost'
    }

    # Identify best/worst for numeric columns
    best_worst = {key: get_best_worst(zone_stats, attr_keys[key]) for key in attr_keys}

    # Minimum total cost for color highlight
    cost_values = [z.est_cost for z in zone_stats if not isnan(z.est_cost)]
    min_cost = min(cost_values) if cost_values else float('nan')

    # Build table
    table = []
    for idx, z in enumerate(zone_stats, 1):
        # For Region AZ, highlight if it has the min cost
        if not isnan(z.est_cost) and z.est_cost == min_cost:
            zone_name_colored = color(f"{idx}. {z.zone_name}", fore=COLORS[args.mode]['highlight'])
        else:
            zone_name_colored = color(f"{idx}. {z.zone_name}", fore=COLORS[args.mode]['zone'])

        row = [
            zone_name_colored,  # Region AZ
            z.instances,        # # Instance Types
            apply_color(z.median_price, *best_worst['Median\nSpot $'], mode=args.mode),
            apply_color(z.min_price, *best_worst['Min \nSpot\n$   '], mode=args.mode),
            apply_color(z.max_price, *best_worst['Max \nSpot\n$   '], mode=args.mode),
            apply_color(
                z.harmonic_price,
                *best_worst['Harmonic\nMean    \nSpot $  '],
                highlight=(z.harmonic_price == best_worst['Harmonic\nMean    \nSpot $  '][0]),
                mode=args.mode
            ),
            apply_color(z.stability, *reversed(best_worst['Spot \nStab-\nility']), mode=args.mode),
            f"{z.launch_25_success_perc:.2f}%",  # Launch 25 Success %
            f"{z.launch_100_success_perc:.2f}%", # Launch 100 Success %
            z.fastq_size, z.bam_size, z.cram_size,
            z.snv_vcf_size, z.snv_gvcf_size, z.sv_vcf_size,
            z.other_size,
            apply_color(z.cost_per_vcpu_min, *best_worst[f'$ per\nvCPU min\n{args.ec2_cost_model}'], mode=args.mode),
            apply_color(z.est_cost, min_cost, min_cost, highlight=(z.est_cost == min_cost), mode=args.mode)
        ]
        table.append(row)

    # Title
    title = (f"{args.x_coverage}-cov genome @ vCPU-min per x align: {args.vcpu_min_per_x_to_align} "
             f"vCPU-min per x snvcall: {args.vcpu_min_per_x_to_snvcall} "
             f"vCPU-min per x other: {args.vcpu_min_per_x_to_other} "
             f"vCPU-min per x svcall: {args.vcpu_min_per_x_to_svcall}")
    print(color(title, fore=COLORS[args.mode]['header']))
    print(tabulate(table, headers=headers, floatfmt=".5f", tablefmt="fancy_grid"))

    # Write TSV (stripped of ANSI colors)
    with open(args.output, 'w') as f:
        table_plain = [[strip_ansi(str(cell)) for cell in row] for row in table]
        f.write(tabulate(table_plain, headers=headers, floatfmt=".5f", tablefmt="tsv"))

def main():
    args = parse_arguments()

    n_vcpus = float(args.partition[1:])
    
    # Load YAML configuration
    with open(args.input, 'r') as f:
        config = yaml.safe_load(f)

    # Extract instances from the specified partition
    try:
        instance_types = extract_instances(config, args.partition)
    except ValueError as e:
        print(e)
        return

    profile = resolve_aws_profile(args.profile)

    zones = args.zones.split(',')

    # 1) Calculate Spot Prices
    spot_data = collect_spot_prices(instance_types, zones, profile)

    # 2) Calculate Dry-run Launch Success for 25 & 100 across all instance types
    launch_data = calculate_launch_success(instance_types, zones, profile)

    # 3) Calculate vCPU-mins for entire workflow
    vcpu_mins = calculate_vcpu_mins(args)

    # 4) Build stats objects
    zone_stats = []
    for zone in zones:
        z_stat = ZoneStat(zone)
        z_stat.calculate_statistics(spot_data, vcpu_mins, args, n_vcpus)

        # After we have a ZoneStat, fill in the 25/100 success from launch_data
        # success_rate_25 = (launch_data[zone]['25']['success_sum'] / launch_data[zone]['25']['attempt_sum'])
        # success_rate_100 = (launch_data[zone]['100']['success_sum'] / launch_data[zone]['100']['attempt_sum'])
        # Check for zero denominator to avoid zero-division:
        if launch_data[zone]['25']['attempt_sum'] > 0:
            z_stat.launch_25_success_perc = (launch_data[zone]['25']['success_sum']
                                             / launch_data[zone]['25']['attempt_sum']) * 100.0
        else:
            z_stat.launch_25_success_perc = 0.0

        if launch_data[zone]['100']['attempt_sum'] > 0:
            z_stat.launch_100_success_perc = (launch_data[zone]['100']['success_sum']
                                              / launch_data[zone]['100']['attempt_sum']) * 100.0
        else:
            z_stat.launch_100_success_perc = 0.0

        zone_stats.append(z_stat)

    # 5) Display final table
    display_statistics(zone_stats, args)

    # Prompt user to select a zone by number
    try:
        selected_index = int(input("\nSelect the availability zone by number: ")) - 1
        selected_zone_stat = zone_stats[selected_index]
    except (IndexError, ValueError):
        print("Invalid selection. Exiting.")
        return

    # Alignment output options
    alignment_options = ['bam', 'cram']
    print("\nSelect alignment output:")
    for idx, opt in enumerate(alignment_options, 1):
        print(f"{idx}. {opt}")
    try:
        alignment_choice = int(input("Enter choice number: ")) - 1
        alignment_output = alignment_options[alignment_choice]
    except (IndexError, ValueError):
        print("Invalid selection. Defaulting to 'bam'.")
        alignment_output = 'bam'

    # SNV Variant output options
    snv_variant_options = ['snv vcf', 'snv gvcf']
    print("\nSelect SNV output:")
    for idx, opt in enumerate(snv_variant_options, 1):
        print(f"{idx}. {opt}")
    try:
        snv_variant_choice = int(input("Enter choice number: ")) - 1
        snv_variant_output = snv_variant_options[snv_variant_choice]
    except (IndexError, ValueError):
        print("Invalid selection. Defaulting to 'vcf'.")
        snv_variant_output = 'snv vcf'

    # SV Variant output options
    sv_variant_options = ['sv vcf']
    print("\nSelect SV output:")
    for idx, opt in enumerate(sv_variant_options, 1):
        print(f"{idx}. {opt}")
    try:
        sv_variant_choice = int(input("Enter choice number: ")) - 1
        sv_variant_output = sv_variant_options[sv_variant_choice]
    except (IndexError, ValueError):
        print("Invalid selection. Defaulting to 'vcf'.")
        sv_variant_output = 'sv vcf'

    # Assign the appropriate size variables based on user selection
    if alignment_output == 'cram':
        alignment_size = selected_zone_stat.cram_size
    else:
        alignment_size = selected_zone_stat.bam_size

    if snv_variant_output == 'snv vcf':
        snv_variant_size = selected_zone_stat.snv_vcf_size
    elif snv_variant_output == 'snv gvcf':
        snv_variant_size = selected_zone_stat.snv_gvcf_size

    sv_variant_size = selected_zone_stat.sv_vcf_size
    other_variant_size = selected_zone_stat.other_size

    # Transfer scheme options
    transfer_options = ['internet', 'within_region', 'cross_region']
    print("\nSelect input transfer scheme:")
    for idx, opt in enumerate(transfer_options, 1):
        print(f"{idx}. {opt}")
    try:
        input_transfer_choice = int(input("Enter choice number: ")) - 1
        input_transfer = transfer_options[input_transfer_choice]
    except (IndexError, ValueError):
        print("Invalid selection. Defaulting to 'internet'.")
        input_transfer = 'internet'

    print("\nSelect output transfer scheme:")
    for idx, opt in enumerate(transfer_options, 1):
        print(f"{idx}. {opt}")
    try:
        output_transfer_choice = int(input("Enter choice number: ")) - 1
        output_transfer = transfer_options[output_transfer_choice]
    except (IndexError, ValueError):
        print("Invalid selection. Defaulting to 'internet'.")
        output_transfer = 'internet'

    # Ensure sizes are numeric
    alignment_size = alignment_size if alignment_size else 0
    snv_variant_size = snv_variant_size if snv_variant_size else 0
    sv_variant_size = sv_variant_size if sv_variant_size else 0
    other_variant_size = other_variant_size if other_variant_size else 0
    qc_size = selected_zone_stat.qc_size or 0
    fastq_size = selected_zone_stat.fastq_size or 0

    total_transfer_cost = (calculate_transfer_costs(fastq_size, input_transfer) +
                           calculate_transfer_costs(alignment_size, output_transfer) +
                           calculate_transfer_costs(snv_variant_size, output_transfer) +
                           calculate_transfer_costs(sv_variant_size, output_transfer) +
                           calculate_transfer_costs(other_variant_size, output_transfer) +
                           calculate_transfer_costs(qc_size, output_transfer))

    # Prompt for FASTQ retention
    print("\nRetain FASTQ files?")
    print("1. Yes")
    print("2. No")
    try:
        retain_choice = int(input("Enter choice number: "))
        if retain_choice == 1:
            retain_fastq = True
        else:
            retain_fastq = False
    except ValueError:
        print("Invalid selection. Defaulting to 'No'.")
        retain_fastq = False

    # Prompt user to select monthly storage approach
    print("\nSelect monthly storage approach:")
    storage_options = ['Not Retaining', 'S3 Standard', 'S3 Glacier']
    for idx, opt in enumerate(storage_options, 1):
        print(f"{idx}. {opt}")
    try:
        storage_choice = int(input("Enter choice number: ")) - 1
        storage_approach = storage_options[storage_choice]
    except (IndexError, ValueError):
        print("Invalid selection. Defaulting to 'Not Retaining'.")
        storage_approach = 'Not Retaining'

    # Prepare file types and sizes for storage
    file_types = ['Input FASTQ', 'BAM', 'CRAM', 'SNV VCF', 'SNV GVCF', 'SV VCF', 'Other', 'QC Data']
    sizes = [
        fastq_size if retain_fastq else 0,
        selected_zone_stat.bam_size,
        selected_zone_stat.cram_size,
        selected_zone_stat.snv_vcf_size,
        selected_zone_stat.snv_gvcf_size,
        selected_zone_stat.sv_vcf_size,
        selected_zone_stat.other_size,
        qc_size
    ]
    file_size_dict = dict(zip(file_types, sizes))

    # Highlight user's selected file types
    selected_files = []
    if retain_fastq:
        selected_files.append('Input FASTQ')
    selected_files.append(alignment_output.upper())
    selected_files.append(snv_variant_output.upper())
    selected_files.append(sv_variant_output.upper())
    selected_files.append('Other')
    selected_files.append('QC Data')

    # Build storage cost table
    storage_approaches = ['Not Retaining', 'S3 Standard', 'S3 Glacier']
    storage_headers = ['Storage Approach'] + file_types
    storage_table = []

    for approach in storage_approaches:
        row = [color(approach, fore=COLORS[args.mode]['header'])]
        for ft in file_types:
            size = file_size_dict[ft]
            if approach == 'Not Retaining':
                cost = 0.0
            else:
                storage_class_key = 'standard' if approach == 'S3 Standard' else 'glacier'
                cost = calculate_storage_costs(size, storage_class_key)
            if ft in selected_files and approach == storage_approach:
                value = apply_color(f"${cost:.5f}\n({size:.4f} GB)", highlight=True, mode=args.mode)
            else:
                value = apply_color(f"${cost:.5f}\n({size:.4f} GB)", dim=True, mode=args.mode)
            row.append(value)
        storage_table.append(row)

    total_storage_cost = 0.0
    if storage_approach != 'Not Retaining':
        storage_class_key = 'standard' if storage_approach == 'S3 Standard' else 'glacier'
        for ft in file_types:
            size = file_size_dict[ft]
            cost = calculate_storage_costs(size, storage_class_key)
            total_storage_cost += cost

    # Display storage cost table
    title = (f"{args.x_coverage}-cov genome @ vCPU-min per x align: {args.vcpu_min_per_x_to_align} "
             f"vCPU-min per x snvcall: {args.vcpu_min_per_x_to_snvcall} "
             f"vCPU-min per x other: {args.vcpu_min_per_x_to_other} "
             f"vCPU-min per x svcall: {args.vcpu_min_per_x_to_svcall}")
    print(color(f"\n{title}", fore=COLORS[args.mode]['header']))
    print("\nSTORAGE COST / MONTH")
    print(tabulate(storage_table, headers=[color(h, fore=COLORS[args.mode]['header']) for h in storage_headers], tablefmt="fancy_grid"))

    # Prepare EC2 costs table
    total_transfer_cost = round(total_transfer_cost, 4)
    est_cost = round(selected_zone_stat.est_cost, 4)
    ec2_headers = ['EC2 Costs', 'Value']

    def _ret_fmtd(val, vtype, selected_zone_stat, args):
        vval = round(val, 4)
        # Very simplistic approach to highlight only if it matches the chosen cost model
        if vtype == args.ec2_cost_model:
            return apply_color(vval, highlight=True, mode=args.mode)
        else:
            return vval

    ec2_data = [
        ['AZ Selected', apply_color(selected_zone_stat.zone_name, highlight=True, mode=args.mode)],
        [
            'Max / Min / Median / Harmonic Mean Spot ($/hr)',
            f"{_ret_fmtd(selected_zone_stat.max_price, 'max', selected_zone_stat, args)} / "
            f"{_ret_fmtd(selected_zone_stat.min_price, 'min', selected_zone_stat, args)} / "
            f"{_ret_fmtd(selected_zone_stat.median_price, 'median', selected_zone_stat, args)} / "
            f"{_ret_fmtd(selected_zone_stat.harmonic_price, 'harmonic', selected_zone_stat, args)}"
        ],
        [
            'Compute Cost / Cost per vCPU per min',
            f"{apply_color(est_cost, highlight=True, mode=args.mode)} / {selected_zone_stat.cost_per_vcpu_min:.5f}"
        ],
        [
            'Data Transfer Cost / Data Size (GB)',
            f"{apply_color(total_transfer_cost, highlight=True, mode=args.mode)} / "
            f"{(alignment_size + snv_variant_size + sv_variant_size + other_variant_size + qc_size):.4f}"
        ],
        ['Other Costs', apply_color("0.0", highlight=True, mode=args.mode)]
    ]

    print("\nEC2 COSTS")
    print(tabulate(ec2_data, headers=[color(h, fore=COLORS[args.mode]['header']) for h in ec2_headers], tablefmt="fancy_grid"))

    # Final cost calculations
    total_analysis_cost = selected_zone_stat.est_cost + total_transfer_cost
    print(f"\nCost to analyze {args.x_coverage}-cov genome: {apply_color(f'${total_analysis_cost:.3f}', highlight=True, mode=args.mode)}")
    print(f"Monthly storage cost: {apply_color(f'${total_storage_cost:.3f}', highlight=True, mode=args.mode)}")

    # Show relevant arguments in condensed format
    print("\nParameters Used:")
    relevant_args = {
        'x_coverage': args.x_coverage,
        'vcpu_min_per_x_to_align': args.vcpu_min_per_x_to_align,
        'vcpu_min_per_x_to_snvcall': args.vcpu_min_per_x_to_snvcall,
        'vcpu_min_per_x_to_svcall': args.vcpu_min_per_x_to_svcall,
        'vcpu_min_per_x_to_other': args.vcpu_min_per_x_to_other,
        'alignment_output': alignment_output,
        'snv_variant_output': snv_variant_output,
        'sv_variant_output': sv_variant_output,
        'input_transfer': input_transfer,
        'output_transfer': output_transfer,
        'retain_fastq': retain_fastq,
        'storage_approach': storage_approach,
        'availability_zone': selected_zone_stat.zone_name,
        'qc_size_per_x': args.qc_size_per_x
    }
    params_line = ', '.join([f"{key}={value}" for key, value in relevant_args.items()])
    print(color(params_line, fore=COLORS[args.mode]['header']))

if __name__ == "__main__":
    main()
