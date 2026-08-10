#!/usr/bin/env python3
"""Initialize the existing Take222 tmux and start focused tests under its lock."""

from __future__ import annotations

import shlex

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell


CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
ROOT = "/fsx/analysis_results/preval-hiomr2/take222"
CHECKOUT = f"{ROOT}/daylily-omics-analysis"
SESSION = "dayoa_take222_hg003_hg004_smn12_20260803"
TEST_LOG = "/home/ubuntu/take222_13.4.3_release_tests.log"
TEST_RC = "/home/ubuntu/take222_13.4.3_release_tests.rc"


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    commands = (
        f"export DAYOA_AGENT_ID=codex-take222-release-20260803",
        "export DAYOA_AGENT_KIND=codex",
        "export DAYOA_HUMAN_REQUESTOR='John Major'",
        f"export DAYOA_TMUX_SESSION={SESSION}",
        "export DAYOA_LEDGER_PATH='/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260803T234000Z_dayoa_13_4_3_dyec_release_slack_ledger.md'",
        f"cd {CHECKOUT}",
        "source dyoainit",
        "dy-a slurm hg38",
        f"dyec analysis lock acquire --analysis-root {ROOT} --operation write --intent 'Run Take222 DayOA 13.4.3 focused tests and exact five-target proof'",
        (
            "PYTHONDONTWRITEBYTECODE=1 /home/ubuntu/miniconda3/envs/DAY-EC/bin/python "
            "-m pytest -p no:cacheprovider tests/test_hiomr2_jasmine_rules.py "
            "tests/test_hiomr2_nicu_rules.py tests/test_hiomr2_nicu_sv.py "
            f"tests/test_hiomr2_non_hg002_diagnostics.py -q >{TEST_LOG} 2>&1; "
            f"printf '%s\\n' $? >{TEST_RC}"
        ),
    )
    send_lines = [
        "set -euo pipefail",
        f"test \"$(tmux list-windows -t {shlex.quote(SESSION)} -F '#{{window_panes}}')\" = 1",
        f"test \"$(tmux list-panes -t {shlex.quote(SESSION)} -F '#{{pane_id}}' | wc -l | tr -d ' ')\" = 1",
        f"test -z \"$(squeue -h -u ubuntu)\"",
        f"test ! -e {shlex.quote(ROOT + '/.dayoa_agent/write.lock')}",
    ]
    for command in commands:
        send_lines.append(
            f"tmux send-keys -t {shlex.quote(SESSION)} {shlex.quote(command)} Enter"
        )
        send_lines.append("sleep 1")
    result = run_shell(
        target.instance_id,
        REGION,
        "\n".join(send_lines),
        profile=PROFILE,
        as_user="ubuntu",
        timeout=300,
        comment="Start Take222 13.4.3 release proof in existing tmux",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
