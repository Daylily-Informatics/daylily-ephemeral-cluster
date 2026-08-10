#!/usr/bin/env python3
"""Pin the idle Take222 checkout to the live-proven DayOA 13.4.3 tag."""

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell

CLUSTER = "preval-hiomr2"
PROFILE = "lsmc"
REGION = "us-west-2"
ROOT = "/fsx/analysis_results/preval-hiomr2/take222"
REPO = ROOT + "/daylily-omics-analysis"


def main() -> int:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    script = f"""set -euo pipefail
export DAYOA_AGENT_ID=codex-take222-release-20260803
export DAYOA_AGENT_KIND=codex
export DAYOA_HUMAN_REQUESTOR='John Major'
export DAYOA_TMUX_SESSION=dayoa_take222_hg003_hg004_smn12_20260803
export DAYOA_LEDGER_PATH='/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260803T234000Z_dayoa_13_4_3_dyec_release_slack_ledger.md'
dyec analysis lock acquire --analysis-root {ROOT} --operation write --intent 'Pin idle Take222 DayOA checkout to live-proven immutable 13.4.3 tag'
cleanup() {{ dyec analysis lock release --analysis-root {ROOT} >/dev/null 2>&1 || true; }}
trap cleanup EXIT
dyec analysis guard --analysis-root {ROOT} --operation write --intent 'Switch idle Take222 checkout to verified DayOA 13.4.3 tag' -- bash -lc '
  set -euo pipefail
  cd {REPO}
  git fetch origin refs/tags/13.4.3:refs/tags/13.4.3
  test "$(git cat-file -t 13.4.3)" = tag
  test "$(git rev-parse 13.4.3^{{}})" = 0ead6be3ded35a2652afb4fa6b08af893c188c84
  for path in \
    daylily_omics_analysis/hiomr2_jasmine_rtg.py \
    daylily_omics_analysis/hiomr2_nicu_sv.py \
    daylily_omics_analysis/hiomr2_truvari.py \
    tests/test_hiomr2_jasmine_rules.py \
    tests/test_hiomr2_nicu_rules.py \
    tests/test_hiomr2_nicu_sv.py \
    tests/test_hiomr2_non_hg002_diagnostics.py \
    workflow/rules/hiomr2_nicu_research.smk \
    workflow/rules/hiomr2_truvari.smk; do
    test "$(git hash-object "$path")" = "$(git rev-parse "13.4.3:$path")"
  done
  git update-ref --no-deref HEAD 0ead6be3ded35a2652afb4fa6b08af893c188c84
  git reset --mixed HEAD
  test "$(git rev-parse HEAD)" = 0ead6be3ded35a2652afb4fa6b08af893c188c84
  printf "head=%s\\ntag_type=%s\\n" "$(git rev-parse HEAD)" "$(git cat-file -t 13.4.3)"
  git status --short
'
"""
    result = run_shell(target.instance_id, REGION, script, profile=PROFILE, as_user="ubuntu", timeout=300, comment="Pin Take222 DayOA 13.4.3")
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return 0 if result.status == "Success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
