#!/usr/bin/env python

import os
import sys

# Ensure DAY-EC conda environment is active
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "helpers"))
from ensure_dayec import ensure_dayec
ensure_dayec(quiet=True)

from daylib.day_cost_ec2 import AWSGenomicsAnalyzer

def main():
    analyzer = AWSGenomicsAnalyzer(
        config_path="config/day_cluster/prod_cluster.yaml",
        aws_profile="daylily",
        partition="i192",
        zones=["us-west-2a", "us-west-2b", "us-east-1a"],
        cost_model="harmonic"
    )

    # Fetch spot prices
    analyzer.fetch_spot_prices()

    # Calculate statistics
    stats = analyzer.calculate_statistics(
        x_coverage=30,
        align=307.2,
        snvcall=684.0,
        svcall=19.0,
        other=0.021
    )

    # Display results
    for stat in stats:
        print(f"Zone: {stat.zone_name}, {stat.instances} instances, {stat.stability:.2f} stability",
            f"(min: ${stat.min_price:.2f}, max: ${stat.max_price:.2f}, median: ${stat.median_price:.2f}, harmonic: ${stat.harmonic_price:.2f}",   
            f"Cost per vCPU-min: ${stat.cost_per_vcpu_min:.6f} , Estimated Cost: ${stat.est_cost:.2f}")


if __name__ == "__main__":
    main()
