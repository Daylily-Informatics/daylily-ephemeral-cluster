"""Daylily Ephemeral Cluster - Python control plane.

Replaces the Bash monolith (bin/daylily-create-ephemeral-cluster) with a
structured Python package for creating and managing ephemeral AWS
ParallelCluster environments for bioinformatics workloads.
"""

try:
    from importlib.metadata import version

    __version__ = version("daylily-ephemeral-cluster")
except Exception:
    __version__ = "0.0.0.dev0"

__all__ = ["__version__"]

