import os
import sys
import time
from datetime import timedelta


def _colorize(text: str, color_code: str) -> str:
    """Wrap text in an ANSI color if stdout is a TTY."""
    if not sys.stdout.isatty():
        return text
    return f"\033[{color_code}m{text}\033[0m"


def _format_elapsed(start_time: float) -> str:
    """Format elapsed runtime since ``start_time`` in H:MM:SS."""
    return str(timedelta(seconds=int(time.time() - start_time)))


def main() -> None:
    region = sys.argv[1]
    spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    start_time = time.time()
    frame_index = 0
    last_length = 0

    while True:
        ret_val = (
            os.popen(
                f"""pcluster list-clusters --region {region} | grep clusterStatus | cut -d '"' -f 4"""
            )
            .readline()
            .strip()
        )

        elapsed = _format_elapsed(start_time)

        if ret_val != "CREATE_IN_PROGRESS":
            if last_length:
                sys.stdout.write("\r" + " " * last_length + "\r")
            color = "32;1" if ret_val == "CREATE_COMPLETE" else "31;1"
            status_text = _colorize(f"Cluster Creation: {ret_val}", color)
            print(f"{status_text} (elapsed {elapsed})")
            break

        frame = spinner_frames[frame_index % len(spinner_frames)]
        status_line = f"{_colorize(frame, '34;1')} Cluster creating… elapsed {elapsed}"

        sys.stdout.write("\r" + status_line + " " * max(0, last_length - len(status_line)))
        sys.stdout.flush()
        last_length = len(status_line)
        frame_index += 1
        time.sleep(5)


if __name__ == "__main__":
    main()
