#!/usr/bin/env python3
"""Send one explicit Take222 release-proof command to its initialized tmux."""

from __future__ import annotations

import argparse
import shlex

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell

CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
SESSION = "dayoa_take222_hg003_hg004_smn12_20260803"
ROOT = "/fsx/analysis_results/preval-hiomr2/take222"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("env", "identity", "acquire", "tests", "dry", "live", "release"))
    args = parser.parse_args()
    commands = {
        "env": "export DAY_PROJECT=RnD DAYLILY_COST_CENTER=RnD SEQONE_DELIVERY_BATCH_ID=take222",
        "identity": "printf 'AGENT=%s KIND=%s REQUESTOR=%s TMUX=%s LEDGER=%s\\n' \"${DAYOA_AGENT_ID:-}\" \"${DAYOA_AGENT_KIND:-}\" \"${DAYOA_HUMAN_REQUESTOR:-}\" \"${DAYOA_TMUX_SESSION:-}\" \"${DAYOA_LEDGER_PATH:-}\"",
        "acquire": f"dyec analysis lock acquire --analysis-root {ROOT} --operation write --intent 'Run exact Take222 DayOA 13.4.3 five-target live proof after RC 0 dry run'",
        "tests": (
            "conda run -n DAY-EC python -m pytest "
            "tests/test_hiomr2_jasmine_rules.py tests/test_hiomr2_nicu_rules.py "
            "tests/test_hiomr2_nicu_sv.py tests/test_hiomr2_non_hg002_diagnostics.py -q "
            ">/home/ubuntu/take222_13.4.3_release_tests.log 2>&1; "
            "printf '%s\\n' $? >/home/ubuntu/take222_13.4.3_release_tests.rc"
        ),
        "dry": "source ./take222_run_command_13.4.2.sh dry",
        "live": "source ./take222_run_command_13.4.2.sh live",
        "release": f"dyec analysis lock release --analysis-root {ROOT}",
    }
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    script = "\n".join(
        (
            "set -euo pipefail",
            f"test \"$(tmux list-windows -t {shlex.quote(SESSION)} -F '#{{window_panes}}')\" = 1",
            f"test \"$(tmux list-panes -t {shlex.quote(SESSION)} -F '#{{pane_id}}' | wc -l | tr -d ' ')\" = 1",
            f"tmux send-keys -t {shlex.quote(SESSION)} {shlex.quote(commands[args.action])} Enter",
        )
    )
    result = run_shell(target.instance_id, REGION, script, profile=PROFILE, as_user="ubuntu", timeout=300, comment=f"Continue Take222 release proof: {args.action}")
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
