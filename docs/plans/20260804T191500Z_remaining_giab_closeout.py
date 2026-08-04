#!/usr/bin/env python3
"""Read-only status and validation helpers for remaining-GIAB closeout."""

from __future__ import annotations

import argparse

from daylily_ec.aws.ssm import SsmCommandFailedError, resolve_headnode_instance_id, run_shell


PROFILE = "lsmc"
REGION = "us-west-2"
CLUSTER = "preval-hiomr2"
ROOT = "/fsx/analysis_results/preval-hiomr2/remaining-giab"


def remote(action: str) -> str:
    common = f"""root={ROOT}
repo="$root/daylily-omics-analysis"
"""
    if action == "poll":
        return common + r"""
if test -e /home/ubuntu/remaining_giab_packaging_live_retry1.rc; then
  cat /home/ubuntu/remaining_giab_packaging_live_retry1.rc
else
  echo PACKAGING_LIVE_RETRY1_RC=ACTIVE
fi
echo QUEUE_BEGIN
squeue -h -o '%i|%T|%j|%M|%R' || true
echo QUEUE_END
echo PROGRESS_BEGIN
tail -n 160 /home/ubuntu/remaining_giab_packaging_live_retry1.log 2>/dev/null | grep -E 'Finished job|steps \(|Submitted|Error|failed|Complete log|package_sent' | tail -n 80 || true
echo PROGRESS_END
manifest_root="$repo/results/day/hg38/deliveries/inflection_hiomr2_analytical_callsets_vcf_gvcf/remaining-giab"
if test -d "$manifest_root"; then
  printf 'MANIFEST_COUNT='; find "$manifest_root" -name package_manifest.json -type f | wc -l
else
  echo MANIFEST_COUNT=0
fi
"""
    if action == "verify":
        return common + r"""
export DAYOA_AGENT_ID=codex-remaining-giab-packaging-recovery-20260804
export DAYOA_AGENT_KIND=codex
export DAYOA_HUMAN_REQUESTOR='John Major'
export DAYOA_TMUX_SESSION=dayoa_remaining_giab_20260804
export DAYOA_LEDGER_PATH=/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260804T004100Z_take333_remaining_giab_hiomr2_ledger.md
dyec analysis visit --analysis-root "$root" --mode read --intent 'Verify terminal remaining-GIAB Inflection packages'
cat /home/ubuntu/remaining_giab_packaging_live_retry1.rc
squeue -h -o '%i|%T|%j|%M|%R' || true
dyec analysis lock status --analysis-root "$root" || true
cd "$repo"
/home/ubuntu/miniconda3/envs/DAY-EC/bin/python -c 'import json,pathlib,sys; root=pathlib.Path("results/day/hg38/deliveries/inflection_hiomr2_analytical_callsets_vcf_gvcf/remaining-giab"); manifests=sorted(root.glob("*/package_manifest.json")); print(f"MANIFEST_COUNT={len(manifests)}"); expected={"HG003","HG004","NA19235","NA20775"}; seen=set(); errors=[]; print("MANIFESTS_BEGIN"); [(lambda p,d,a: (seen.add(d["external_sample_id"]), print("|".join([d["external_sample_id"],d["analysis_unit_uid"],d["schema"],str(d["artifact_count"]),str(sum(x["package_tier"]=="established" for x in a)),str(sum(x["package_tier"]=="experimental" for x in a)),str(sum(int(x["bytes"]) for x in a)),str(p)])), errors.extend([str(p)+": missing "+x["relative_path"] for x in a if not (p.parent/x["relative_path"]).is_file()]), errors.extend([str(p)+": empty "+x["relative_path"] for x in a if (p.parent/x["relative_path"]).is_file() and (p.parent/x["relative_path"]).stat().st_size==0]), errors.extend([str(p)+": size mismatch "+x["relative_path"] for x in a if (p.parent/x["relative_path"]).is_file() and (p.parent/x["relative_path"]).stat().st_size!=int(x["bytes"])])))(p,json.loads(p.read_text()),json.loads(p.read_text())["artifacts"]) for p in manifests]; print("MANIFESTS_END"); files=[p for p in root.rglob("*") if p.is_file()]; print(f"DELIVERY_FILES={len(files)}"); print(f"DELIVERY_BYTES={sum(p.stat().st_size for p in files)}"); print("SAMPLES="+",".join(sorted(seen))); print(f"ERROR_COUNT={len(errors)}"); [print(e) for e in errors]; sys.exit(0 if len(manifests)==4 and seen==expected and not errors else 1)'
"""
    if action == "keys":
        return common + r"""
cd "$repo"
/home/ubuntu/miniconda3/envs/DAY-EC/bin/python -c 'import json,pathlib; p=next(pathlib.Path("results/day/hg38/deliveries/inflection_hiomr2_analytical_callsets_vcf_gvcf/remaining-giab").glob("*/package_manifest.json")); d=json.loads(p.read_text()); print(sorted(d)); print(sorted(d["artifacts"][0])); print(json.dumps(d["artifacts"][0], indent=2, sort_keys=True))'
"""
    if action == "package_roles":
        return common + r"""
cd "$repo"
/home/ubuntu/miniconda3/envs/DAY-EC/bin/python -c 'import json,pathlib; p=next(pathlib.Path("results/day/hg38/deliveries/inflection_hiomr2_analytical_callsets_vcf_gvcf/remaining-giab").glob("*/package_manifest.json")); d=json.loads(p.read_text()); print("ROLES_BEGIN"); [print("|".join([x["package_tier"],x["role"],x["semantic_type"],x["relative_path"],str(x["bytes"])])) for x in d["artifacts"]]; print("ROLES_END")'
"""
    if action == "export_visit":
        return common + r"""
export DAYOA_AGENT_ID=codex-remaining-giab-packaging-recovery-20260804
export DAYOA_AGENT_KIND=codex
export DAYOA_HUMAN_REQUESTOR='John Major'
export DAYOA_TMUX_SESSION=dayoa_remaining_giab_20260804
export DAYOA_LEDGER_PATH=/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260804T004100Z_take333_remaining_giab_hiomr2_ledger.md
dyec analysis visit --analysis-root "$root" --mode export --intent 'Export completed Inflection packages and final report to the established remaining-GIAB S3 prefix'
"""
    if action == "pdf_tools":
        return common + r"""
for tool in pandoc wkhtmltopdf chromium chromium-browser google-chrome libreoffice; do
  command -v "$tool" || true
done
for py in /home/ubuntu/miniconda3/envs/DAY-EC/bin/python python3; do
  "$py" -c 'import reportlab; print("REPORTLAB_OK")' 2>/dev/null || true
  "$py" -c 'import weasyprint; print("WEASYPRINT_OK")' 2>/dev/null || true
done
"""
    if action == "git_status":
        return common + r"""
cd "$repo"
printf 'HEAD='; git rev-parse HEAD
printf 'DESCRIBE='; git describe --tags --always --dirty
printf 'BRANCH='; git branch --show-current
git status --short
git tag --list '13.4.*' --sort=-version:refname | head -n 10
git remote -v
"""
    if action == "report_status":
        return common + r"""
echo STAGE_BEGIN
find /home/ubuntu/remaining-giab-final-report-stage -maxdepth 2 -type f -printf '%P|%s\n' | sort
echo STAGE_END
target="$repo/results/day/hg38/reports/remaining-giab-final"
echo TARGET_BEGIN
if test -d "$target"; then
  find "$target" -maxdepth 2 -type f -printf '%P|%s\n' | sort
fi
echo TARGET_END
"""
    if action == "install_report":
        return common + r"""
export DAYOA_AGENT_ID=codex-remaining-giab-report-closeout-20260804
export DAYOA_AGENT_KIND=codex
export DAYOA_HUMAN_REQUESTOR='John Major'
export DAYOA_TMUX_SESSION=dayoa_remaining_giab_20260804
export DAYOA_LEDGER_PATH=/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260804T004100Z_take333_remaining_giab_hiomr2_ledger.md
stage=/home/ubuntu/remaining-giab-final-report-stage
target="$repo/results/day/hg38/reports/remaining-giab-final"
test -f "$stage/REMAINING_GIAB_HIOMR2_FINAL_REPORT.md"
test -f "$stage/REMAINING_GIAB_HIOMR2_FINAL_REPORT.html"
test -f "$stage/REMAINING_GIAB_HIOMR2_FINAL_REPORT.pdf"
dyec analysis visit --analysis-root "$root" --mode write --intent 'Install validated remaining-GIAB final report hard copy'
dyec analysis lock acquire --analysis-root "$root" --operation write --intent 'Install validated remaining-GIAB final report hard copy' --human-requestor "$DAYOA_HUMAN_REQUESTOR" --command-summary 'copy validated MD HTML PDF and evidence tables' --operation-scope report-install
release_lock() {
  dyec analysis lock release --analysis-root "$root" --human-requestor "$DAYOA_HUMAN_REQUESTOR" --note 'remaining-GIAB final report installation complete' >/dev/null
}
trap release_lock EXIT
dyec analysis guard --analysis-root "$root" --operation write --intent 'Install validated remaining-GIAB final report hard copy' --human-requestor "$DAYOA_HUMAN_REQUESTOR" -- bash -lc 'set -euo pipefail; stage=/home/ubuntu/remaining-giab-final-report-stage; target=/fsx/analysis_results/preval-hiomr2/remaining-giab/daylily-omics-analysis/results/day/hg38/reports/remaining-giab-final; mkdir -p "$target/data"; cp -a "$stage/REMAINING_GIAB_HIOMR2_FINAL_REPORT.md" "$stage/REMAINING_GIAB_HIOMR2_FINAL_REPORT.html" "$stage/REMAINING_GIAB_HIOMR2_FINAL_REPORT.pdf" "$stage/evidence_summary.json" "$target/"; cp -a "$stage/data"/. "$target/data"/'
find "$target" -maxdepth 2 -type f -printf '%P|%s\n' | sort
"""
    raise ValueError(action)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("poll", "verify", "keys", "package_roles", "export_visit", "pdf_tools", "git_status", "report_status", "install_report"))
    args = parser.parse_args()
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    try:
        result = run_shell(
            target.instance_id,
            REGION,
            remote(args.action),
            profile=PROFILE,
            as_user="ubuntu",
            timeout=300,
            comment=f"Remaining-GIAB closeout {args.action}",
        )
    except SsmCommandFailedError as exc:
        print(exc.result.stdout)
        if exc.result.stderr:
            print(exc.result.stderr)
        return 1
    print(result.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
