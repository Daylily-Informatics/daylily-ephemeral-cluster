# library/aws_genomics_costs.py

import statistics
import subprocess
from math import fsum, isnan
from typing import Any, Dict, List

import yaml  # type: ignore[import-untyped]


class ConfigLoader:
    """Handles loading and validation of YAML configuration files."""

    @staticmethod
    def load_config(file_path: str) -> Dict[Any, Any]:
        with open(file_path, "r") as file:
            result: Dict[Any, Any] = yaml.safe_load(file)
            return result


class SpotPriceFetcher:
    """Fetches and processes spot price data from AWS."""

    @staticmethod
    def get_spot_price(instance_type: str, zone: str, profile: str) -> float:
        """Fetch the spot price for a specific instance type and zone."""
        region = zone[:-1]
        try:
            cmd = [
                "aws", "ec2", "describe-spot-price-history",
                "--instance-types", instance_type,
                "--availability-zone", zone,
                "--product-description", "Linux/UNIX",
                "--query", "SpotPriceHistory[0].SpotPrice",
                "--output", "text",
                "--region", region
            ]
            
            if profile:
                cmd.extend(["--profile", profile])
            try:
                result = subprocess.check_output(cmd).decode().strip()
                print(f"Price for {instance_type} in {zone}: {result}")
                return float(result) if result else float("nan")
            
            except Exception as e:
                print(f"Error fetching price for {zone}: {e}")
                return float("nan")
            
        except subprocess.CalledProcessError:
            return float("nan")

    @staticmethod
    def collect_spot_prices(instance_types: List[str], zones: List[str], profile: str) -> Dict[str, Dict[str, float]]:
        """Fetch spot prices for all instance types and zones."""
        spot_data: Dict[str, Dict[str, float]] = {instance: {} for instance in instance_types}
        for instance_type in instance_types:
            for zone in zones:
                spot_data[instance_type][zone] = SpotPriceFetcher.get_spot_price(instance_type, zone, profile)
        return spot_data


class ZoneStat:
    """Represents statistics for an availability zone."""

    def __init__(self, zone_name: str):
        self.zone_name = zone_name
        self.prices: List[float] = []
        self.instances = 0
        self.median_price = float("nan")
        self.min_price = float("nan")
        self.max_price = float("nan")
        self.harmonic_price = float("nan")
        self.stability = float("nan")
        self.est_cost = float("nan")

    def calculate_statistics(self, spot_data: Dict[str, Dict[str, float]], n_vcpus: int, vcpu_mins: float, cost_model: str):
        """Calculate zone statistics based on spot price data."""
        self.prices = [spot_data[instance].get(self.zone_name, float("nan")) for instance in spot_data]
        self.prices = [p for p in self.prices if not isnan(p)]

        if self.prices:
            self.instances = len(self.prices)
            self.median_price = statistics.median(self.prices)
            self.min_price = min(self.prices)
            self.max_price = max(self.prices)
            self.harmonic_price = self._harmonic_mean(self.prices)
            self.stability = max(self.prices) - min(self.prices)

            # Calculate costs
            cost_per_vcpu_min = {
                "min": self.min_price / n_vcpus / 60,
                "max": self.max_price / n_vcpus / 60,
                "median": self.median_price / n_vcpus / 60,
                "harmonic": self.harmonic_price / n_vcpus / 60,
            }
            self.est_cost = vcpu_mins * cost_per_vcpu_min[cost_model]

    @staticmethod
    def _harmonic_mean(data: List[float]) -> float:
        """Calculate the harmonic mean of a list of numbers."""
        if not data or any(d == 0 for d in data):
            return float("nan")
        return len(data) / fsum(1 / d for d in data)


def calculate_vcpu_mins(x_coverage: float, align: float, snvcall: float, svcall: float, other: float) -> float:
    """Calculate total vCPU-minutes required for a genome analysis."""
    return x_coverage * (align + snvcall + svcall + other)


def display_statistics(zone_stats: List[ZoneStat], n_vcpus: int, cost_model: str):
    """Print statistics for each availability zone."""
    headers = ["Zone", "# Instances", "Median ($/hr)", "Min ($/hr)", "Max ($/hr)", "Harmonic ($/hr)", "Stability", "Estimated Cost ($)"]
    rows = [
        [
            z.zone_name,
            z.instances,
            z.median_price,
            z.min_price,
            z.max_price,
            z.harmonic_price,
            z.stability,
            z.est_cost
        ]
        for z in zone_stats
    ]
    from tabulate import tabulate  # type: ignore[import-untyped]
    print(tabulate(rows, headers=headers, floatfmt=".5f", tablefmt="fancy_grid"))


def extract_instances(config: dict, partition_name: str) -> List[str]:
    """Extract instance types for the given partition."""
    for queue in config.get("Scheduling", {}).get("SlurmQueues", []):
        if queue.get("Name") == partition_name:
            return [
                instance["InstanceType"]
                for resource in queue.get("ComputeResources", [])
                for instance in resource.get("Instances", [])
            ]
    raise ValueError(f"No instances found for partition: {partition_name}")
