#!/usr/bin/env python3
"""
DAY-EC Conda Environment Checker

This module provides a function to ensure the DAY-EC conda environment is active.
Import and call ensure_dayec() at the top of any script that requires DAY-EC.

Usage:
    from helpers.ensure_dayec import ensure_dayec
    ensure_dayec()
"""

import os
import subprocess
import sys


def ensure_dayec(quiet: bool = False) -> None:
    """
    Ensure the DAY-EC conda environment is active.

    If DAY-EC is not active, attempts to check if it exists and provides
    activation instructions. If activation cannot be verified, exits with error.

    Args:
        quiet: If True, suppress the success message when DAY-EC is active.

    Raises:
        SystemExit: If DAY-EC is not active and cannot be activated.
    """
    env_name = "DAY-EC"
    current_env = os.environ.get("CONDA_DEFAULT_ENV", "")

    if current_env == env_name:
        if not quiet:
            print(f"✓ {env_name} conda environment is active.", file=sys.stderr)
        return

    # DAY-EC is not active - check if it exists
    conda_prefix = os.environ.get("CONDA_PREFIX", "")
    conda_exe = os.environ.get("CONDA_EXE", "conda")

    # Try to find conda
    if not conda_prefix:
        # Check common conda locations
        for path in [
            os.path.expanduser("~/miniconda3"),
            os.path.expanduser("~/anaconda3"),
            "/opt/conda",
            "/usr/local/miniconda3",
        ]:
            if os.path.exists(path):
                conda_exe = os.path.join(path, "bin", "conda")
                break

    # Check if DAY-EC environment exists
    env_exists = False
    try:
        result = subprocess.run(
            [conda_exe, "env", "list"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.strip().startswith(env_name + " ") or line.strip() == env_name:
                    env_exists = True
                    break
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # Provide helpful error message
    sys.stderr.write("\n" + "=" * 60 + "\n")
    sys.stderr.write(f"ERROR: The {env_name} conda environment is not active.\n")
    sys.stderr.write("=" * 60 + "\n\n")

    if env_exists:
        sys.stderr.write(f"The {env_name} environment exists. Activate it with:\n\n")
        sys.stderr.write(f"    conda activate {env_name}\n\n")
        sys.stderr.write("Then re-run this script.\n")
    else:
        sys.stderr.write(f"The {env_name} environment does not exist.\n\n")
        sys.stderr.write("Create it by running:\n\n")
        sys.stderr.write("    ./bin/init_dayec\n\n")
        sys.stderr.write(f"Then activate with:\n\n")
        sys.stderr.write(f"    conda activate {env_name}\n\n")
        sys.stderr.write("And re-run this script.\n")

    sys.stderr.write("\n")
    sys.exit(1)


if __name__ == "__main__":
    # Allow running directly to test
    ensure_dayec()
    print("DAY-EC environment check passed!")

