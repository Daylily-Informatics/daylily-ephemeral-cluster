#!/usr/bin/env python3
"""Rerun Take222 focused tests with the headnode DAY-EC Python in the owner tmux."""

from __future__ import annotations

import shlex

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell


CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
ROOT = "/fsx/analysis_results/preval-hiomr2/take222"
SESSION = "dayoa_take222_hg003_hg004_smn12_20260803"
LOG = "/home/ubuntu/take222_13.4.3_release_tests_retry1.log"
RC = "/home/ubuntu/take222_13.4.3_release_tests_retry1.rc"


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    test_command = (
        "PYTHONDONTWRITEBYTECODE=1 /home/ubuntu/miniconda3/envs/DAY-EC/bin/python "
        "-m pytest -q -p no:cacheprovider "
        "tests/test_hiomr2_jasmine_rules.py tests/test_hiomr2_nicu_rules.py "
        "tests/test_hiomr2_nicu_sv.py tests/test_hiomr2_non_hg002_diagnostics.py "
        f">{LOG} 2>&1; printf '%s\\n' $? >{RC}"
    )
    script = f"""set -euo pipefail
test "$(tmux list-windows -t {shlex.quote(SESSION)} -F '#{{window_panes}}')" = 1
test "$(tmux list-panes -t {shlex.quote(SESSION)} -F '#{{pane_id}}' | wc -l | tr -d ' ')" = 1
test -z "$(squeue -h -u ubuntu)"
rg -q '"agent_id": "codex-take222-release-20260803"' {shlex.quote(ROOT + '/.dayoa_agent/write.lock/owner.json')}
test ! -e {shlex.quote(RC)}
tmux send-keys -t {shlex.quote(SESSION)} {shlex.quote(test_command)} Enter
for unused in $(seq 1 30); do
  test -e {shlex.quote(RC)} && break
  sleep 1
done
test -e {shlex.quote(RC)}
printf '%s' 'retry-test-rc='
cat {shlex.quote(RC)}
tail -n 80 {shlex.quote(LOG)}
test "$(cat {shlex.quote(RC)})" = 0
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=300,
        comment="Rerun Take222 focused tests with DAY-EC Python",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
