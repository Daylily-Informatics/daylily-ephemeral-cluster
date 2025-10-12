import os
import subprocess
import sys
import time
from datetime import timedelta
from typing import Optional


def _colorize(text: str, color_code: str) -> str:
    """Wrap text in an ANSI color if stdout is a TTY."""
    if not sys.stdout.isatty():
        return text
    return f"\033[{color_code}m{text}\033[0m"


def _format_elapsed(start_time: float) -> str:
    """Format elapsed runtime since ``start_time`` in H:MM:SS."""
    return str(timedelta(seconds=int(time.time() - start_time)))


def _get_cluster_status(region: str, cluster_name: Optional[str]) -> Optional[str]:
    """Return the ParallelCluster status for ``cluster_name``.

    When ``cluster_name`` is provided we query the specific cluster so we can
    distinguish between the cluster disappearing (for example, being deleted)
    and the generic list-clusters view returning another cluster's status.
    If the describe command fails because the cluster no longer exists we
    return ``None``.
    """

    if cluster_name:
        describe_cmd = [
            "pcluster",
            "describe-cluster",
            "-n",
            cluster_name,
            "--region",
            region,
            "--query",
            "clusterStatus",
        ]
        proc = subprocess.run(describe_cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            # ``None`` signals that the cluster no longer exists or could not
            # be described (for example, it was deleted mid-creation).
            return None
        return proc.stdout.strip()

    # Fall back to the legacy behaviour of reading the first cluster status
    # when a name was not provided.
    ret_val = (
        os.popen(
            f"""pcluster list-clusters --region {region} | grep clusterStatus | cut -d '"' -f 4"""
        )
        .readline()
        .strip()
    )
    return ret_val or None


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: watch_cluster_status.py <region> [cluster_name]")

    region = sys.argv[1]
    cluster_name = sys.argv[2] if len(sys.argv) > 2 else None
    spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    start_time = time.time()
    frame_index = 0
    last_length = 0

    while True:
        ret_val = _get_cluster_status(region, cluster_name)

        elapsed = _format_elapsed(start_time)

        if ret_val == "CREATE_IN_PROGRESS":
            frame = spinner_frames[frame_index % len(spinner_frames)]
            status_line = f"{_colorize(frame, '34;1')} Cluster creating… elapsed {elapsed}"

            sys.stdout.write("\r" + status_line + " " * max(0, last_length - len(status_line)))
            sys.stdout.flush()
            last_length = len(status_line)
            frame_index += 1
            time.sleep(5)
            continue

        if last_length:
            sys.stdout.write("\r" + " " * last_length + "\r")
            last_length = 0

        if ret_val is None:
            color = "33;1"
            status = "UNKNOWN (cluster not found)"
            status_text = _colorize(f"Cluster Creation: {status}", color)
            print(f"{status_text} (elapsed {elapsed})")
            time.sleep(5)
            continue

        if ret_val == "CREATE_COMPLETE":
            color = "32;1"
            status_text = _colorize(f"Cluster Creation: {ret_val}", color)
            print(f"{status_text} (elapsed {elapsed})")
            return 0

        color = "31;1"
        status_text = _colorize(f"Cluster Creation: {ret_val}", color)
        print(f"{status_text} (elapsed {elapsed})")

        # Non-success statuses signal an error so the caller can stop
        # further configuration steps.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
