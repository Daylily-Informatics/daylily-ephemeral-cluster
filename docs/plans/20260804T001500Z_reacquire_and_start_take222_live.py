#!/usr/bin/env python3
"""Reacquire the Take222 owner lock and start the proven five-target live command."""

from __future__ import annotations

import shlex

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell


CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
ROOT = "/fsx/analysis_results/preval-hiomr2/take222"
CHECKOUT = f"{ROOT}/daylily-omics-analysis"
SESSION = "dayoa_take222_hg003_hg004_smn12_20260803"
FAILED_LOG = f"{CHECKOUT}/take222_hg003_hg004_na19235_na20775_fullcov_13.4.2_live_20260803.log"
PRESERVED_LOG = f"{CHECKOUT}/take222_13.4.3_five_target_live_lock_guard_fail_20260804.log"
FAILED_RC = "/home/ubuntu/take222_hg003_hg004_na19235_na20775_fullcov_13.4.2_live_20260803.rc"
PRESERVED_RC = "/home/ubuntu/take222_13.4.3_five_target_live_lock_guard_fail_20260804.rc"


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    commands = (
        (
            f"dyec analysis lock acquire --analysis-root {ROOT} --operation write "
            "--intent 'Run exact Take222 DayOA 13.4.3 five-target live proof after RC0 dry run'"
        ),
        (
            f"dyec analysis guard --analysis-root {ROOT} --operation write "
            "--intent 'Preserve fail-closed pre-live lock-guard evidence' -- "
            f"cp {FAILED_LOG} {PRESERVED_LOG}"
        ),
        f"cp {FAILED_RC} {PRESERVED_RC}",
        "source ./take222_run_command_13.4.2.sh live",
    )
    lines = [
        "set -euo pipefail",
        f"test \"$(tmux list-windows -t {shlex.quote(SESSION)} -F '#{{window_panes}}')\" = 1",
        f"test \"$(tmux list-panes -t {shlex.quote(SESSION)} -F '#{{pane_id}}' | wc -l | tr -d ' ')\" = 1",
        "test -z \"$(squeue -h -u ubuntu)\"",
        "test -z \"$(ps -fu ubuntu | awk '/bin\\/day_run|snakemake/ && !/awk/ {print}')\"",
        f"test ! -e {shlex.quote(ROOT + '/.dayoa_agent/write.lock')}",
        f"test ! -e {shlex.quote(PRESERVED_LOG)}",
        f"test ! -e {shlex.quote(PRESERVED_RC)}",
    ]
    for command in commands:
        lines.append(
            f"tmux send-keys -t {shlex.quote(SESSION)} {shlex.quote(command)} Enter"
        )
        lines.append("sleep 1")
    lines.extend(
        [
            "sleep 3",
            f"tmux capture-pane -pt {shlex.quote(SESSION)} -S -45",
            f"test -e {shlex.quote(ROOT + '/.dayoa_agent/write.lock/owner.json')}",
            (
                "rg -q '\"agent_id\": \"codex-take222-release-20260803\"' "
                f"{shlex.quote(ROOT + '/.dayoa_agent/write.lock/owner.json')}"
            ),
            (
                "ps -fu ubuntu | awk "
                "'/bin\\/day_run|snakemake/ && !/awk/ {print}'"
            ),
        ]
    )
    result = run_shell(
        target.instance_id,
        REGION,
        "\n".join(lines),
        profile=PROFILE,
        as_user="ubuntu",
        timeout=300,
        comment="Reacquire Take222 lock and start five-target live proof",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
