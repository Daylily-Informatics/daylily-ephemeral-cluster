#!/usr/bin/env python3
"""List relevant remote tmux sessions and panes."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from daylily_ec.aws.ssm import SsmCommandFailedError, run_shell  # noqa: E402


SCRIPT = r"""
set -euo pipefail
echo "tmux_sessions:"
tmux list-sessions 2>/dev/null || true
for session in $(tmux list-sessions -F '#S' 2>/dev/null | grep -E 'hybonly_ilmn|haplocheck96' || true); do
  echo "SESSION=$session"
  tmux list-windows -t "$session" || true
  tmux list-panes -t "$session" || true
  tmux capture-pane -pt "$session" -S -80 || true
done
"""


def main() -> int:
    try:
        result = run_shell(
            "i-05374380b57fad901",
            "us-west-2",
            SCRIPT,
            profile="lsmc",
            as_user="ubuntu",
            timeout=120,
            comment="inspect remote tmux sessions",
        )
    except SsmCommandFailedError as exc:
        print(exc.result.stdout, end="")
        print(exc.result.stderr, end="", file=sys.stderr)
        return exc.result.response_code or 1

    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.response_code


if __name__ == "__main__":
    raise SystemExit(main())
