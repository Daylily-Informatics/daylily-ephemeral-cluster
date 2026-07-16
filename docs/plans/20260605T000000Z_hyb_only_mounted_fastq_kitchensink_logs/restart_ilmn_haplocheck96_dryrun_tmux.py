#!/usr/bin/env python3
"""Restart the ILMN dry-run in the existing DayOA checkout via tmux send-keys."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from daylily_ec.aws.ssm import SsmCommandFailedError, run_shell  # noqa: E402


DEFAULT_REPO_PATH = (
    "/fsx/analysis_results/ubuntu/"
    "hybonly_ilmn_kitchensink_mounted_20260606T053415Z/"
    "daylily-omics-analysis"
)

CODE_UPDATE_PATHS = (
    "workflow/rules/contam_identity.smk",
    "config/day_profiles/slurm/templates/rule_config.yaml",
)

DY_COMMAND = (
    "dy-r "
    "produce_sent_align "
    "produce_dmd_dedup_cram "
    "produce_sentd_snv_vcf "
    "produce_alignstats "
    "produce_snv_concordances "
    "produce_relatedness "
    "produce_gatk_contam_estimate "
    "produce_site_mix_contam_estimate "
    "produce_global_contam_check "
    "produce_vep "
    "produce_expansionhunter "
    "produce_htd_calls "
    "produce_metagenomics "
    "produce_multiqc_all "
    "--config "
    "'aligners=[\"sent\"]' "
    "'dedupers=[\"dmd\"]' "
    "'snv_callers=[\"sentd\"]' "
    "'htd_callers=[\"cyrius\"]' "
    "'multiqc_qc={\"enable_tools\":[\"vep\",\"metagenomics\",\"contam_identity\"]}' "
    "-j 200 -p -k --rerun-triggers mtime -n"
)


def _remote_preflight_script(repo_path: str) -> str:
    quoted_repo = shlex.quote(repo_path)
    quoted_paths = " ".join(shlex.quote(path) for path in CODE_UPDATE_PATHS)
    return f"""
set -euo pipefail
repo_path={quoted_repo}
if [[ ! -d "$repo_path/.git" ]]; then
  echo "__DAYLILY_ERROR__=missing_repo $repo_path"
  exit 11
fi
echo "repo_path=$repo_path"
git -C "$repo_path" status --short --branch
echo "commit=$(git -C "$repo_path" rev-parse HEAD)"
echo "branch=$(git -C "$repo_path" rev-parse --abbrev-ref HEAD)"
echo "target_code_status:"
git -C "$repo_path" status --porcelain -- {quoted_paths} || true
echo "analysis_root_du:"
du -sh "$(dirname "$repo_path")" 2>/dev/null || true
"""


def _remote_script(session: str, repo_path: str) -> str:
    quoted_session = shlex.quote(session)
    quoted_repo = shlex.quote(repo_path)
    quoted_dy_command = shlex.quote(DY_COMMAND)
    return f"""
set -euo pipefail
session={quoted_session}
repo_path={quoted_repo}
dy_command={quoted_dy_command}
run_dir="/home/ubuntu/daylily-runs/$session"
tmux_log="$run_dir/tmux.log"
mkdir -p "$run_dir"
: > "$tmux_log"
if [[ ! -d "$repo_path/.git" ]]; then
  echo "__DAYLILY_ERROR__=missing_repo $repo_path"
  exit 11
fi
branch="$(git -C "$repo_path" rev-parse --abbrev-ref HEAD)"
if [[ "$branch" != "jem-dev" ]]; then
  echo "__DAYLILY_ERROR__=unexpected_branch $branch"
  exit 13
fi
grep -q 'export HAPLOCHECK_THREADS={{threads}}' "$repo_path/workflow/rules/contam_identity.smk"
grep -q 'ForkJoinPool.common.parallelism={{threads}}' "$repo_path/workflow/rules/contam_identity.smk"
python3 - "$repo_path/config/day_profiles/slurm/templates/rule_config.yaml" "$repo_path/config/day_profiles/slurm/rule_config.yaml" <<'PYCFG'
import sys
from pathlib import Path

for raw in sys.argv[1:]:
    path = Path(raw)
    if not path.exists():
        continue
    lines = path.read_text().splitlines()
    block = []
    in_block = False
    for line in lines:
        if line.startswith("haplocheck:"):
            in_block = True
            block.append(line)
            continue
        if in_block and line and not line.startswith((" ", "\t")):
            break
        if in_block:
            block.append(line)
    text = "\\n".join(block)
    if 'partition: "i192,i192mem,i192bigmem"' not in text or "threads: 96" not in text:
        print("bad haplocheck config in", path)
        print(text)
        raise SystemExit(15)
PYCFG
if tmux has-session -t "$session" 2>/dev/null; then
  echo "__DAYLILY_ERROR__=session_exists $session"
  exit 12
fi
tmux new-session -d -s "$session" 'bash -il'
tmux pipe-pane -t "$session" -o "cat >> $tmux_log"
tmux send-keys -t "$session" "cd $repo_path" C-m
tmux send-keys -t "$session" "git status --short --branch" C-m
tmux send-keys -t "$session" "git rev-parse HEAD" C-m
tmux send-keys -t "$session" "source dyoainit" C-m
tmux send-keys -t "$session" "dy-a slurm hg38" C-m
tmux send-keys -t "$session" "$dy_command" C-m
python3 - <<'PY'
import json, os
print(json.dumps({{
  "session": os.environ.get("SESSION_NAME", ""),
  "repo_path": os.environ.get("REPO_PATH", ""),
  "tmux_log": os.environ.get("TMUX_LOG", ""),
  "dy_command": os.environ.get("DY_COMMAND_VALUE", ""),
}}, sort_keys=True))
PY
""".replace(
        "os.environ.get(\"SESSION_NAME\", \"\")", repr(session)
    ).replace(
        "os.environ.get(\"REPO_PATH\", \"\")", repr(repo_path)
    ).replace(
        "os.environ.get(\"TMUX_LOG\", \"\")",
        repr(f"/home/ubuntu/daylily-runs/{session}/tmux.log"),
    ).replace(
        "os.environ.get(\"DY_COMMAND_VALUE\", \"\")", repr(DY_COMMAND)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--instance-id", default="i-05374380b57fad901")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--profile", default="lsmc")
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()

    if args.preflight_only:
        script = _remote_preflight_script(args.repo_path)
        comment = "preflight ILMN existing analysis before dry-run restart"
    else:
        script = _remote_script(args.session, args.repo_path)
        comment = f"restart ILMN haplocheck96 dry-run {args.session[:32]}"
    try:
        result = run_shell(
            args.instance_id,
            args.region,
            script,
            profile=args.profile,
            as_user="ubuntu",
            timeout=120,
            comment=comment,
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
