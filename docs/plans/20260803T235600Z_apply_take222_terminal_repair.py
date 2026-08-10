#!/usr/bin/env python3
"""Acquire the Take222 lock, install its five-target harness, and test the repair."""

from __future__ import annotations

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell


CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
ROOT = "/fsx/analysis_results/preval-hiomr2/take222"
CHECKOUT = f"{ROOT}/daylily-omics-analysis"
SESSION = "dayoa_take222_hg003_hg004_smn12_20260803"
STAGE = "/home/ubuntu/take222_stage_20260803/remove-diagnostic-gates"
EXPECTED = {
    "daylily_omics_analysis/hiomr2_jasmine_rtg.py": "7ad0bfe04cdb616f203ac46b304f2ec807df376807398e5d19963d42f79cba94",
    "daylily_omics_analysis/hiomr2_nicu_sv.py": "265889611c72ff7d0237ff5715da0a1051b8df72fab256fc7563529677fc2e3f",
    "daylily_omics_analysis/hiomr2_truvari.py": "b998d6f101da5ba63336a8aa350fe77a2451d5cc51b5acbccd109f541ebcf18f",
    "tests/test_hiomr2_jasmine_rules.py": "d9e165bffd59dc5ac8d417c92970400f97234210377923843b362683b0c4c332",
    "tests/test_hiomr2_nicu_rules.py": "dbd0bef1144c10e8079eca3fff9f9c2150172e7da3ebb1b72a0b71b524e19d1c",
    "tests/test_hiomr2_nicu_sv.py": "99a9de00b4832d33709cee103997ca302d3ff6571b8cde529ca90ba5d0646c2f",
    "tests/test_hiomr2_non_hg002_diagnostics.py": "6410c366fd8f80e6f7764fc9708685cee40a9cb51b87e6eb6f456aee14408670",
    "workflow/rules/hiomr2_nicu_research.smk": "29f743861959afa161dea08949b6f655c84606d3467b014bfcd8bef20303edb5",
    "workflow/rules/hiomr2_truvari.smk": "cf325fb7736d07edffd9eb5ac24b31e8ae051760e9688e2e0ec316e913c556e3",
    "workflow/rules/multiqc_final_wgs.smk": "70d2d75d8f22beee200760888a05ac5d02c4db1309c9faf75b799f931d3b2157",
}
HARNESS_SHA256 = "8bcdf42fbed7898aa48cbc3b53d596f1bab3db047706fcef420b9e72ae80ce9a"


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    checks = "\n".join(
        "test \"$(sha256sum "
        + repr(f"{CHECKOUT}/{path}")
        + " | awk '{print $1}')\" = "
        + repr(expected)
        + f"\nprintf '%s\\n' 'verified {path} {expected}'"
        for path, expected in EXPECTED.items()
    )
    script = rf"""set -euo pipefail
export DAYOA_AGENT_ID=codex-take222-20260803
export DAYOA_AGENT_KIND=codex
export DAYOA_HUMAN_REQUESTOR='John Major'
export DAYOA_TMUX_SESSION={SESSION!r}
export DAYOA_LEDGER_PATH='/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260803T082714Z_take101_export_take222_fullcov_ledger.md'
test "$(tmux list-windows -t {SESSION!r} -F '#{{window_index}}' | wc -l)" -eq 1
test "$(tmux list-panes -t {SESSION!r} -F '#{{pane_id}}' | wc -l)" -eq 1
test -z "$(squeue -h -u ubuntu -o '%i')"
test ! -d {ROOT!r}/.dayoa_agent/write.lock
dyec analysis lock acquire --analysis-root {ROOT!r} --operation write --intent 'Install proven Take222 terminal warning-path repair and run five-target proof'
{checks}
test "$(sha256sum {STAGE!r}/take222_run_command_13.4.2.sh | awk '{{print $1}}')" = {HARNESS_SHA256!r}
dyec analysis guard --analysis-root {ROOT!r} --operation write -- cp {STAGE!r}/take222_run_command_13.4.2.sh {CHECKOUT!r}/take222_run_command_13.4.2.sh
test "$(sha256sum {CHECKOUT!r}/take222_run_command_13.4.2.sh | awk '{{print $1}}')" = {HARNESS_SHA256!r}
cd {CHECKOUT!r}
PYTHONDONTWRITEBYTECODE=1 /home/ubuntu/miniconda3/envs/DAY-EC/bin/python -m pytest -q -p no:cacheprovider tests/test_hiomr2_nicu_rules.py tests/test_hiomr2_nicu_sv.py tests/test_hiomr2_non_hg002_diagnostics.py tests/test_hiomr2_jasmine_rules.py
/home/ubuntu/miniconda3/envs/DAY-EC/bin/python -m ruff check --select F,E9 daylily_omics_analysis/hiomr2_jasmine_rtg.py daylily_omics_analysis/hiomr2_nicu_sv.py daylily_omics_analysis/hiomr2_truvari.py tests/test_hiomr2_jasmine_rules.py tests/test_hiomr2_nicu_rules.py tests/test_hiomr2_nicu_sv.py tests/test_hiomr2_non_hg002_diagnostics.py
git diff --check -- daylily_omics_analysis/hiomr2_jasmine_rtg.py daylily_omics_analysis/hiomr2_nicu_sv.py daylily_omics_analysis/hiomr2_truvari.py tests/test_hiomr2_jasmine_rules.py tests/test_hiomr2_nicu_rules.py tests/test_hiomr2_nicu_sv.py workflow/rules/hiomr2_nicu_research.smk workflow/rules/hiomr2_truvari.smk
printf '%s\n' 'TAKE222_TERMINAL_REPAIR_TESTS_RC=0'
find {ROOT!r}/.dayoa_agent/write.lock -maxdepth 2 -type f -print -exec sed -n '1,120p' {{}} \;
"""
    result = run_shell(
        target.instance_id,
        REGION,
        script,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=600,
        comment="Apply and test Take222 terminal repair",
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
