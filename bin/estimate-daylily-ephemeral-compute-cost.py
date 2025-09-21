#!/usr/bin/env python

import argparse
from daylib.day_factory import PipelineFactory
from daylib.day_cost_ec2 import SpotPriceFetcher, ZoneStat
from tabulate import tabulate
import yaml


def parse_arguments():
    parser = argparse.ArgumentParser(description="Calculate task and storage costs dynamically.")
    parser.add_argument("--config", required=True, help="Path to the YAML configuration file.")
    parser.add_argument("--output", required=True, help="Path to the output TSV file.")
    parser.add_argument("--cost-model", choices=["min", "max", "median", "harmonic"], default="harmonic",
                        help="EC2 cost model to use for calculations.")
    return parser.parse_args()



def extract_partition_instance_types(cluster_config_path: str, partition_name: str) -> list:
    """
    Extracts the instance types for the specified partition from the cluster configuration YAML.

    Args:
        cluster_config_path (str): Path to the cluster configuration YAML.
        partition_name (str): Name of the partition (e.g., 'i192').

    Returns:
        list: A list of instance types in the specified partition.
    """
    with open(cluster_config_path, 'r') as file:
        cluster_config = yaml.safe_load(file)

    # Navigate to the specified partition in SlurmQueues
    slurm_queues = cluster_config.get("Scheduling", {}).get("SlurmQueues", [])
    for queue in slurm_queues:
        if queue.get("Name") == partition_name:
            instance_types = []
            for resource in queue.get("ComputeResources", []):
                for instance in resource.get("Instances", []):
                    instance_types.append(instance["InstanceType"])
            return instance_types

    # If the partition is not found, raise an error
    raise ValueError(f"Partition '{partition_name}' not found in cluster configuration.")


def calculate_task_and_storage_costs(factory, cluster_config_path, partition, zones, profile, cost_model, genome_coverage):
    # Extract instance types for the specified partition
    instance_types = extract_partition_instance_types(cluster_config_path, partition)
    # Extract the number of vCPUs from the partition name
    n_vcpus = 0
    try:
        n_vcpus = int(partition[1:])  # Assuming partition name is of the form 'i192', 'i128', etc.
    except ValueError:
        raise ValueError(f"Invalid partition name '{partition}'. Expected format like 'i192', 'i128', etc.")

    # Fetch spot prices for the extracted instance types
    spot_prices = SpotPriceFetcher.collect_spot_prices(instance_types, zones, profile)

    # Calculate zone statistics
    zone_stats = {zone: ZoneStat(zone) for zone in zones}
    for zone, stat in zone_stats.items():
        stat.calculate_statistics(spot_prices, n_vcpus, 0, cost_model)  # Example n_vcpus = 192

    # Per-task cost estimation
    pipeline = factory.create_pipeline()
    task_estimates = []
    for task in pipeline:
        task_costs = []
        for zone, stat in zone_stats.items():
            vcpu_mins = task.vcpu_min_per_x_cov * genome_coverage
            task_cost = {
                "Task": task.name,
                "Zone": zone,
                "Median Cost ($/hr)": stat.median_price,
                "Max Cost ($/hr)": stat.max_price,
                "Min Cost ($/hr)": stat.min_price,
                "Harmonic Cost ($/hr)": stat.harmonic_price,
                "Median Cost ($/vCPU/min)": stat.median_price / 60,
                "Max Cost ($/vCPU/min)": stat.max_price / 60,
                "Min Cost ($/vCPU/min)": stat.min_price / 60,
                "Harmonic Cost ($/vCPU/min)": stat.harmonic_price / 60,
                "Estimated Task Cost (Min)": vcpu_mins * (stat.min_price / 60),
                "Estimated Task Cost (Median)": vcpu_mins * (stat.median_price / 60),
                "Estimated Task Cost (Max)": vcpu_mins * (stat.max_price / 60),
                "Estimated Task Cost (Harmonic)": vcpu_mins * (stat.harmonic_price / 60),
            }
            task_costs.append(task_cost)
        task_estimates.extend(task_costs)

    return task_estimates, zone_stats



def display_task_costs(task_costs):
    headers = [
        "Task", "Zone", "Median Cost ($/hr)", "Max Cost ($/hr)", "Min Cost ($/hr)", "Harmonic Cost ($/hr)",
        "Median Cost ($/vCPU/min)", "Max Cost ($/vCPU/min)", "Min Cost ($/vCPU/min)", "Harmonic Cost ($/vCPU/min)",
        "Estimated Task Cost (Min)", "Estimated Task Cost (Median)", "Estimated Task Cost (Max)", "Estimated Task Cost (Harmonic)"
    ]

    table = []
    for cost in task_costs:
        table.append([
            cost["Task"], cost["Zone"],
            cost["Median Cost ($/hr)"], cost["Max Cost ($/hr)"], cost["Min Cost ($/hr)"], cost["Harmonic Cost ($/hr)"],
            cost["Median Cost ($/vCPU/min)"], cost["Max Cost ($/vCPU/min)"], cost["Min Cost ($/vCPU/min)"], cost["Harmonic Cost ($/vCPU/min)"],
            cost["Estimated Task Cost (Min)"], cost["Estimated Task Cost (Median)"], cost["Estimated Task Cost (Max)"], cost["Estimated Task Cost (Harmonic)"],
        ])

    print(tabulate(table, headers=headers, floatfmt=".6f", tablefmt="fancy_grid"))



def main():
    args = parse_arguments()

    # Load configuration
    with open(args.config, 'r') as file:
        config = yaml.safe_load(file)

    factory = PipelineFactory(args.config)
    cluster_config_path = config["cluster_config_yaml"]
    partition = config["partition"]
    zones = config.get("zones", [])
    profile = config.get("aws_profile", "default")

    # Calculate costs
    task_costs, zone_stats = calculate_task_and_storage_costs(
        factory, cluster_config_path, partition, zones, profile, args.cost_model, genome_coverage=30
    )

    # Display costs
    display_task_costs(task_costs)

    # Write results to a TSV file
    with open(args.output, "w") as f:
        headers = [
            "Task", "Zone", "Median Cost ($/hr)", "Max Cost ($/hr)", "Min Cost ($/hr)", "Harmonic Cost ($/hr)",
            "Median Cost ($/vCPU/min)", "Max Cost ($/vCPU/min)", "Min Cost ($/vCPU/min)", "Harmonic Cost ($/vCPU/min)",
            "Estimated Task Cost (Min)", "Estimated Task Cost (Median)", "Estimated Task Cost (Max)", "Estimated Task Cost (Harmonic)"
        ]
        f.write("\t".join(headers) + "\n")
        for cost in task_costs:
            row = [
                cost["Task"], cost["Zone"],
                cost["Median Cost ($/hr)"], cost["Max Cost ($/hr)"], cost["Min Cost ($/hr)"], cost["Harmonic Cost ($/hr)"],
                cost["Median Cost ($/vCPU/min)"], cost["Max Cost ($/vCPU/min)"], cost["Min Cost ($/vCPU/min)"], cost["Harmonic Cost ($/vCPU/min)"],
                cost["Estimated Task Cost (Min)"], cost["Estimated Task Cost (Median)"], cost["Estimated Task Cost (Max)"], cost["Estimated Task Cost (Harmonic)"],
            ]
            f.write("\t".join(map(str, row)) + "\n")


if __name__ == "__main__":
    main()
