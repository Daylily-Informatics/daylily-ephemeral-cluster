"""Daylily Ephemeral Cluster - Python control plane.

Replaces the Bash monolith (bin/daylily-create-ephemeral-cluster) with a
structured Python package for creating and managing ephemeral AWS
ParallelCluster environments for bioinformatics workloads.
"""

from daylily_ec.versioning import get_version

__version__ = get_version()

from daylily_ec.create import create_cluster

__all__ = ["__version__", "create_cluster"]
