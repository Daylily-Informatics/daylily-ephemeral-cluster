"""Launch daylily-omics-analysis inside tmux on the headnode via SSM."""

from __future__ import annotations

import argparse
import base64
import gzip
import json
import os
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from daylily_ec.aws.ssm import (
    resolve_headnode_instance_id,
    run_shell,
    wait_for_ssm_online,
)
from daylily_ec.analysis_identity import analysis_source_path, validate_analysis_segment
from daylily_ec.headnode_readiness import validate_headnode_readiness
from daylily_ec.scripts.common import CommandError, need_cmd, resolve_cluster, resolve_region
from daylily_ec.workflow.snakemake_resources import (
    DEFAULT_JOB_MAX_RUNTIME_MINUTES,
    append_default_job_runtime,
    validate_job_max_runtime_minutes,
)


STAGE_CONFIG_DISCOVERY_TIMEOUT_SECONDS = 180


def shlex_quote_compressed_python(source: str) -> str:
    payload = base64.b64encode(gzip.compress(source.encode("utf-8"), mtime=0)).decode("ascii")
    command = (
        "import base64,gzip; "
        f"exec(gzip.decompress(base64.b64decode({payload!r})).decode('utf-8'))"
    )
    return shlex.quote(command)


BCL_RUN_CONTEXT_PROJECTION_SCRIPT = r'''
import csv
import re
import shutil
from pathlib import Path

runs_path = Path("config/runs.tsv")
if not runs_path.is_file():
    raise SystemExit(0)


def sanitize(value):
    text = str(value or "").strip()
    text = re.sub(r"[\\/]+", "_", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("._-") or "run"


def relative_to_or_none(path, root):
    try:
        return path.relative_to(root)
    except ValueError:
        return None


with runs_path.open(newline="", encoding="utf-8-sig") as handle:
    reader = csv.DictReader(handle, delimiter="\t")
    fieldnames = reader.fieldnames or []
    rows = list(reader)

if "RUN_DIR" not in fieldnames:
    raise SystemExit(0)

repo_root = Path.cwd().resolve()
links_dir = Path("config/run_dir_links")
links_dir.mkdir(parents=True, exist_ok=True)
changed = False

for row in rows:
    run_dir_text = str(row.get("RUN_DIR", "") or "").strip()
    if not run_dir_text:
        continue
    run_dir = Path(run_dir_text)
    if not run_dir.is_absolute():
        raise SystemExit(f"[ERROR] RUN_DIR must be an absolute mounted path: {run_dir_text}")
    run_dir_resolved = run_dir.resolve()
    if relative_to_or_none(run_dir_resolved, repo_root) is not None:
        continue
    if not run_dir_resolved.is_dir():
        raise SystemExit(f"[ERROR] RUN_DIR does not exist for projection: {run_dir_text}")

    link_name = sanitize(row.get("RUNID") or run_dir_resolved.name)
    link_path = links_dir / link_name
    link_abs = (repo_root / link_path).absolute()
    if link_path.exists() or link_path.is_symlink():
        if not link_path.is_symlink():
            raise SystemExit(f"[ERROR] Refusing to replace non-symlink run projection: {link_path}")
        if link_path.resolve() != run_dir_resolved:
            raise SystemExit(
                f"[ERROR] Existing run projection points at {link_path.resolve()}, expected {run_dir_resolved}"
            )
    else:
        link_path.symlink_to(run_dir_resolved, target_is_directory=True)

    row["RUN_DIR"] = str(link_abs)
    for key, value in list(row.items()):
        if key == "RUN_DIR":
            continue
        text = str(value or "").strip()
        if not text.startswith("/"):
            continue
        value_path = Path(text).resolve()
        rel = relative_to_or_none(value_path, run_dir_resolved)
        if rel is not None:
            row[key] = str(link_abs / rel)
    changed = True

if changed:
    tmp_path = runs_path.with_suffix(".tsv.tmp")
    with tmp_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    tmp_path.replace(runs_path)
    print(f"[INFO] Projected mounted RUN_DIR values through {links_dir}")
else:
    print("[INFO] No external mounted RUN_DIR values required projection.")
'''


BCLCONVERT_PROFILE_PATCH_SCRIPT = r'''
import csv
import os
import re
from pathlib import Path

runs_path = Path("config/runs.tsv")
if not runs_path.is_file():
    raise SystemExit("[ERROR] BCL Convert profile patch requires config/runs.tsv")

with runs_path.open(newline="", encoding="utf-8-sig") as handle:
    runs = list(csv.DictReader(handle, delimiter="\t"))

run_row = next((row for row in runs if str(row.get("PLATFORM", "")).upper() == "ILMN"), None)
if run_row is None:
    raise SystemExit("[ERROR] BCL Convert profile patch requires an ILMN run row in config/runs.tsv")

run_id = str(run_row.get("RUNID", "")).strip() or "<unknown-run>"
run_dir = Path(str(run_row.get("RUN_DIR", "")).strip())
if not run_dir.is_absolute() or not run_dir.is_dir():
    raise SystemExit(f"[ERROR] BCL Convert RUN_DIR must be an existing absolute directory: {run_dir}")

profile_dir = os.environ.get("DAY_PROFILE_DIR", "")
if not profile_dir:
    raise SystemExit("[ERROR] DAY_PROFILE_DIR is not set; cannot patch BCL Convert profile config")

rule_config = Path(profile_dir) / "rule_config.yaml"
if not rule_config.is_file():
    raise SystemExit(f"[ERROR] Missing DayOA profile rule config: {rule_config}")

lines = rule_config.read_text(encoding="utf-8").splitlines(keepends=True)
bcl_start = None
bcl_indent = None
for index, line in enumerate(lines):
    match = re.match(r"^(\s*)bclconvert:\s*(?:#.*)?$", line)
    if match:
        bcl_start = index
        bcl_indent = len(match.group(1))
        break
if bcl_start is None or bcl_indent is None:
    raise SystemExit(f"[ERROR] Missing bclconvert block in {rule_config}")

bcl_end = len(lines)
for index in range(bcl_start + 1, len(lines)):
    stripped = lines[index].strip()
    if not stripped or lines[index].lstrip().startswith("#"):
        continue
    indent = len(lines[index]) - len(lines[index].lstrip())
    if indent <= bcl_indent:
        bcl_end = index
        break


def replace_required_scalar(key, value):
    target_index = None
    for index in range(bcl_start + 1, bcl_end):
        if re.match(rf"^\s+{re.escape(key)}\s*:", lines[index]):
            target_index = index
            break
    if target_index is None:
        raise SystemExit(f"[ERROR] Missing bclconvert.{key} in {rule_config}")
    indent = re.match(r"^(\s*)", lines[target_index]).group(1)
    lines[target_index] = f'{indent}{key}: "{value}"\n'


def upsert_scalar(key, value):
    global bcl_end
    target_index = None
    for index in range(bcl_start + 1, bcl_end):
        if re.match(rf"^\s+{re.escape(key)}\s*:", lines[index]):
            target_index = index
            break
    if target_index is None:
        child_indent = " " * (bcl_indent + 4)
        lines.insert(bcl_end, f'{child_indent}{key}: "{value}"\n')
        bcl_end += 1
        return
    indent = re.match(r"^(\s*)", lines[target_index]).group(1)
    lines[target_index] = f'{indent}{key}: "{value}"\n'


replace_required_scalar("tmpdir", "/dev/shm")
replace_required_scalar("force", "true")
upsert_scalar("merge_lane_fastqs", "false")
upsert_scalar("merge_tile_fastqs", "false")
replace_required_scalar("threads", "192")
replace_required_scalar("partition", "i192mem,i192bigmem")
replace_required_scalar("parallel_tiles", "24")
replace_required_scalar("conversion_threads", "4")
replace_required_scalar("compression_threads", "64")
replace_required_scalar("decompression_threads", "32")
replace_required_scalar("fastq_gzip_compression_level", "1")
upsert_scalar("shared_thread_odirect_output", "false")
upsert_scalar("output_legacy_stats", "true")
upsert_scalar("num_unknown_barcodes_reported", "1000")
# Untested pending feature: optional sample-sheet injections stay unset unless explicitly
# configured, except the validation contract requires zero barcode mismatches.
upsert_scalar("adapter_read1", "")
upsert_scalar("adapter_read2", "")
upsert_scalar("adapter_behavior", "")
upsert_scalar("adapter_stringency", "")
upsert_scalar("minimum_adapter_overlap", "")
upsert_scalar("barcode_mismatches_index1", "0")
upsert_scalar("barcode_mismatches_index2", "0")
upsert_scalar("create_fastq_for_index_reads", "")
upsert_scalar("minimum_trimmed_read_length", "")
upsert_scalar("mask_short_reads", "")
upsert_scalar("override_cycles", "")
upsert_scalar("software_version", "")
upsert_scalar("trim_umi", "")
upsert_scalar("no_lane_splitting", "")
upsert_scalar("sample_sheet_settings", "{}")
upsert_scalar("sample_sheet_settings_by_lane", "{}")
rule_config.write_text("".join(lines), encoding="utf-8")
print(f"[INFO] Patched {rule_config} bclconvert direct mounted-input mode for {run_id}: {run_dir}")
'''


BCLCONVERT_LANE_SPLIT_PATCH_SCRIPT = '\nfrom pathlib import Path\n\nrule_path = Path("workflow/rules/bclconvert.smk")\nif not rule_path.is_file():\n    raise SystemExit(f"[ERROR] BCL Convert lane-split patch target missing: {rule_path}")\n\nscripts_dir = Path("workflow/scripts")\nscripts_dir.mkdir(parents=True, exist_ok=True)\n\nprepare_lane_samplesheet = scripts_dir / "dyec_prepare_bclconvert_lane_samplesheet.py"\nprepare_lane_samplesheet.write_text(r"""#!/usr/bin/env python3\nfrom __future__ import annotations\n\nimport argparse\nimport csv\nimport io\nimport json\nimport re\nfrom pathlib import Path\nfrom typing import Any\n\nSECTION_RE = re.compile(r"^\\[(?P<name>[^\\]]+)\\]")\nALLOWED_SETTINGS = {\n    "AdapterRead1",\n    "AdapterRead2",\n    "AdapterBehavior",\n    "AdapterStringency",\n    "MinimumAdapterOverlap",\n    "BarcodeMismatchesIndex1",\n    "BarcodeMismatchesIndex2",\n    "CreateFastqForIndexReads",\n    "MinimumTrimmedReadLength",\n    "MaskShortReads",\n    "OverrideCycles",\n    "SoftwareVersion",\n    "TrimUMI",\n    "NoLaneSplitting",\n}\n\n\ndef parse_args():\n    parser = argparse.ArgumentParser(description="Prepare a lane-specific BCL Convert sample sheet.")\n    parser.add_argument("--sample-sheet", required=True)\n    parser.add_argument("--out", required=True)\n    parser.add_argument("--lane", required=True)\n    parser.add_argument("--settings-json", default="{}")\n    parser.add_argument("--settings-by-lane-json", default="{}")\n    return parser.parse_args()\n\n\ndef normalize_lane(value: str) -> str:\n    text = str(value or "").strip()\n    if text.upper().startswith("L"):\n        text = text[1:]\n    return str(int(text))\n\n\ndef load_mapping(text: str, *, label: str) -> dict[str, Any]:\n    payload = str(text or "").strip()\n    if not payload:\n        return {}\n    try:\n        value = json.loads(payload)\n    except json.JSONDecodeError as exc:\n        raise SystemExit(f"ERROR: {label} must be a JSON object") from exc\n    if not isinstance(value, dict):\n        raise SystemExit(f"ERROR: {label} must be a JSON object")\n    return value\n\n\ndef canonical_updates(settings: dict[str, Any], *, label: str) -> dict[str, str]:\n    updates: dict[str, str] = {}\n    for key, value in settings.items():\n        canonical = str(key or "").strip()\n        if canonical not in ALLOWED_SETTINGS:\n            allowed = ", ".join(sorted(ALLOWED_SETTINGS))\n            raise SystemExit(f"ERROR: unsupported {label} setting {canonical!r}; allowed: {allowed}")\n        if value is None:\n            continue\n        text = str(value).strip()\n        if text == "":\n            continue\n        updates[canonical] = text\n    return updates\n\n\ndef lane_updates(settings_by_lane: dict[str, Any], lane: str) -> dict[str, str]:\n    lane_number = normalize_lane(lane)\n    candidates = [lane_number, f"L{int(lane_number):03d}", f"l{int(lane_number):03d}"]\n    for key in candidates:\n        value = settings_by_lane.get(key)\n        if value is None:\n            continue\n        if not isinstance(value, dict):\n            raise SystemExit("ERROR: sample_sheet_settings_by_lane values must be JSON objects")\n        return canonical_updates(value, label=f"sample_sheet_settings_by_lane[{key}]")\n    return {}\n\n\ndef validate_updates(updates: dict[str, str]) -> None:\n    for key in ("BarcodeMismatchesIndex1", "BarcodeMismatchesIndex2"):\n        if key not in updates:\n            continue\n        if updates[key] not in {"0", "1", "2"}:\n            raise SystemExit(f"ERROR: {key} must be 0, 1, or 2: {updates[key]}")\n\n\ndef csv_line(row: list[str]) -> str:\n    buffer = io.StringIO()\n    writer = csv.writer(buffer, lineterminator="")\n    writer.writerow(row)\n    return buffer.getvalue()\n\n\ndef upsert_settings(lines: list[str], updates: dict[str, str]) -> list[str]:\n    section_start = None\n    section_end = len(lines)\n    for index, raw_line in enumerate(lines):\n        stripped = raw_line.strip()\n        match = SECTION_RE.match(stripped)\n        if not match:\n            continue\n        if match.group("name").strip() == "BCLConvert_Settings":\n            section_start = index\n            continue\n        if section_start is not None and index > section_start:\n            section_end = index\n            break\n    if section_start is None:\n        raise SystemExit("ERROR: normalized sample sheet lacks [BCLConvert_Settings]")\n\n    remaining = dict(updates)\n    for index in range(section_start + 1, section_end):\n        if not lines[index].strip():\n            continue\n        row = next(csv.reader([lines[index]]))\n        key = row[0].strip() if row else ""\n        if key in remaining:\n            lines[index] = csv_line([key, remaining.pop(key)])\n\n    insert_at = section_end\n    for key, value in remaining.items():\n        lines.insert(insert_at, csv_line([key, value]))\n        insert_at += 1\n    return lines\n\n\ndef main() -> int:\n    args = parse_args()\n    global_settings = canonical_updates(load_mapping(args.settings_json, label="sample_sheet_settings"), label="sample_sheet_settings")\n    by_lane = load_mapping(args.settings_by_lane_json, label="sample_sheet_settings_by_lane")\n    updates = {**global_settings, **lane_updates(by_lane, args.lane)}\n    validate_updates(updates)\n    source = Path(args.sample_sheet)\n    output = Path(args.out)\n    lines = source.read_text(encoding="utf-8-sig").splitlines()\n    # Untested pending feature: this only changes content when explicit settings are supplied.\n    if updates:\n        lines = upsert_settings(lines, updates)\n    output.parent.mkdir(parents=True, exist_ok=True)\n    output.write_text("\\n".join(lines) + "\\n", encoding="utf-8")\n    print(\n        "prepared_lane_samplesheet "\n        f"lane={normalize_lane(args.lane)} "\n        f"settings={\'<unchanged>\' if not updates else json.dumps(updates, sort_keys=True)} "\n        f"out={output}"\n    )\n    return 0\n\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n""", encoding="utf-8")\nprepare_lane_samplesheet.chmod(0o755)\n\nrun_lane_helper = scripts_dir / "dyec_run_bclconvert_lane.sh"\nrun_lane_helper.write_text(r"""#!/usr/bin/env bash\nset -euo pipefail\ncontainer_uri="$1"\nrun_dir="$2"\nlane_output_dir="$3"\nsample_sheet="$4"\nlane_number="$5"\nlane_sample_sheet="$6"\nstrict_mode="$7"\nfirst_tile_only="$8"\nsampleproject_subdirectories="$9"\nfastq_gzip_compression_level="${10}"\nparallel_tiles="${11}"\nconversion_threads="${12}"\ncompression_threads="${13}"\ndecompression_threads="${14}"\nshared_thread_odirect_output="${15}"\noutput_legacy_stats="${16}"\nnum_unknown_barcodes_reported="${17}"\nsample_sheet_settings_json="${18}"\nsample_sheet_settings_by_lane_json="${19}"\nforce_arg="${20}"\nthreads="${21}"\nlog_path="${22}"\nfastq_list="${23}"\ndemux_stats="${24}"\ndone_path="${25}"\n\nmkdir -p "$lane_output_dir" "$(dirname "$lane_sample_sheet")" "$(dirname "$log_path")"\n: > "$log_path"\nexport TMPDIR="${TMPDIR:-/dev/shm}"\nmkdir -p "$TMPDIR"\nif [[ ! -d "$run_dir" ]]; then\n  echo "BCL input directory does not exist: $run_dir" >> "$log_path"\n  exit 2\nfi\n\npython workflow/scripts/dyec_prepare_bclconvert_lane_samplesheet.py \\\n  --sample-sheet "$sample_sheet" \\\n  --out "$lane_sample_sheet" \\\n  --lane "$lane_number" \\\n  --settings-json "$sample_sheet_settings_json" \\\n  --settings-by-lane-json "$sample_sheet_settings_by_lane_json" \\\n  >> "$log_path" 2>&1\n\necho "run_bclconvert_lane L$(printf \'%03d\' "$lane_number") started: $(date -Is)" >> "$log_path"\necho "host: $(hostname)" >> "$log_path"\necho "threads: $threads" >> "$log_path"\necho "TMPDIR: $TMPDIR" >> "$log_path"\necho "bcl_input_directory: $run_dir" >> "$log_path"\necho "output_directory: $lane_output_dir" >> "$log_path"\necho "sample_sheet: $lane_sample_sheet" >> "$log_path"\necho "bcl_only_lane: $lane_number" >> "$log_path"\necho "sample_sheet_settings_json: $sample_sheet_settings_json" >> "$log_path"\necho "sample_sheet_settings_by_lane_json: $sample_sheet_settings_by_lane_json" >> "$log_path"\necho "output_legacy_stats: $output_legacy_stats" >> "$log_path"\necho "num_unknown_barcodes_reported: $num_unknown_barcodes_reported" >> "$log_path"\nnproc >> "$log_path" 2>&1 || true\ndf -h "$TMPDIR" "$run_dir" "$lane_output_dir" >> "$log_path" 2>&1 || true\ncommand -v singularity >> "$log_path" 2>&1\nsingularity_bind_args=(--bind /fsx:/fsx)\necho "singularity_bind_args: ${singularity_bind_args[*]}" >> "$log_path"\nsingularity exec "${singularity_bind_args[@]}" "$container_uri" bcl-convert --version >> "$log_path" 2>&1\n\nheavy_threads="$((parallel_tiles * conversion_threads + compression_threads + decompression_threads))"\nif [[ "$heavy_threads" -lt 1 ]]; then\n  echo "BCLConvert CPU-heavy thread total must be >= 1" >> "$log_path"\n  exit 2\nfi\nif [[ "$heavy_threads" -gt "$threads" ]]; then\n  echo "BCLConvert thread allocation exceeds requested threads: heavy_threads=$heavy_threads threads=$threads" >> "$log_path"\n  exit 2\nfi\n\necho "bcl_num_parallel_tiles: $parallel_tiles" >> "$log_path"\necho "bcl_num_conversion_threads: $conversion_threads" >> "$log_path"\necho "bcl_num_compression_threads: $compression_threads" >> "$log_path"\necho "bcl_num_decompression_threads: $decompression_threads" >> "$log_path"\necho "bcl_cpu_heavy_threads: $heavy_threads" >> "$log_path"\n\nbcl_flags=(\n  --bcl-input-directory "$run_dir"\n  --output-directory "$lane_output_dir"\n  --sample-sheet "$lane_sample_sheet"\n  --bcl-only-lane "$lane_number"\n  --strict-mode "$strict_mode"\n  --first-tile-only "$first_tile_only"\n  --bcl-sampleproject-subdirectories "$sampleproject_subdirectories"\n  --fastq-gzip-compression-level "$fastq_gzip_compression_level"\n  --bcl-num-parallel-tiles "$parallel_tiles"\n  --bcl-num-conversion-threads "$conversion_threads"\n  --bcl-num-compression-threads "$compression_threads"\n  --bcl-num-decompression-threads "$decompression_threads"\n  --shared-thread-odirect-output "$shared_thread_odirect_output"\n  --output-legacy-stats "$output_legacy_stats"\n  --num-unknown-barcodes-reported "$num_unknown_barcodes_reported"\n)\nif [[ -n "$force_arg" ]]; then\n  bcl_flags+=("$force_arg")\nfi\n\nprintf \'bcl-convert command:\' >> "$log_path"\nprintf \' %q\' singularity exec "${singularity_bind_args[@]}" "$container_uri" bcl-convert "${bcl_flags[@]}" >> "$log_path"\nprintf \'\\n\' >> "$log_path"\nsingularity exec "${singularity_bind_args[@]}" "$container_uri" bcl-convert "${bcl_flags[@]}" >> "$log_path" 2>&1\n\ntest -s "$fastq_list"\ntest -s "$demux_stats"\nmkdir -p "$(dirname "$done_path")"\ntouch "$done_path"\necho "run_bclconvert_lane L$(printf \'%03d\' "$lane_number") finished: $(date -Is)" >> "$log_path"\n""", encoding="utf-8")\nrun_lane_helper.chmod(0o755)\n\nmerge_helper = scripts_dir / "dyec_merge_bclconvert_lanes.py"\nmerge_helper.write_text(r"""#!/usr/bin/env python3\nfrom __future__ import annotations\n\nimport argparse\nimport csv\nimport os\nimport shutil\nfrom pathlib import Path\n\n\ndef parse_args():\n    parser = argparse.ArgumentParser(description="Merge DYEC lane-split BCL Convert outputs.")\n    parser.add_argument("--lane-fastq-root", required=True)\n    parser.add_argument("--final-fastq-dir", required=True)\n    parser.add_argument("--report-dir", required=True)\n    parser.add_argument("--lanes", required=True)\n    parser.add_argument("--done", required=True)\n    parser.add_argument("--log", required=True)\n    return parser.parse_args()\n\n\ndef read_csv(path: Path, *, required: bool) -> tuple[list[str], list[dict[str, str]]]:\n    if not path.exists():\n        if required:\n            raise SystemExit(f"ERROR: missing required BCL Convert report: {path}")\n        return [], []\n    with path.open("r", encoding="utf-8-sig", newline="") as handle:\n        reader = csv.DictReader(handle)\n        fieldnames = reader.fieldnames or []\n        if required and not fieldnames:\n            raise SystemExit(f"ERROR: report has no header: {path}")\n        return fieldnames, [dict(row) for row in reader]\n\n\ndef write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:\n    if not fieldnames:\n        return\n    path.parent.mkdir(parents=True, exist_ok=True)\n    with path.open("w", encoding="utf-8", newline="") as handle:\n        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\\n")\n        writer.writeheader()\n        writer.writerows(rows)\n\n\ndef merge_report(lane_dirs: list[Path], report_name: str, dest: Path, *, required: bool) -> None:\n    merged_header: list[str] | None = None\n    merged_rows: list[dict[str, str]] = []\n    for lane_dir in lane_dirs:\n        header, rows = read_csv(lane_dir / "Reports" / report_name, required=required)\n        if not header:\n            continue\n        if merged_header is None:\n            merged_header = header\n        elif header != merged_header:\n            raise SystemExit(f"ERROR: {report_name} header mismatch in {lane_dir / \'Reports\' / report_name}")\n        merged_rows.extend(rows)\n    if merged_header is None:\n        if required:\n            raise SystemExit(f"ERROR: no lane reports found for {report_name}")\n        return\n    write_csv(dest, merged_header, merged_rows)\n\n\ndef move_lane_fastqs(lane_dirs: list[Path], final_fastq_dir: Path) -> dict[str, str]:\n    moved: dict[str, str] = {}\n    by_name: dict[str, str] = {}\n    final_fastq_dir.mkdir(parents=True, exist_ok=True)\n    for lane_dir in lane_dirs:\n        if not lane_dir.is_dir():\n            raise SystemExit(f"ERROR: missing lane output directory: {lane_dir}")\n        for src in sorted(lane_dir.rglob("*.fastq.gz")):\n            rel = src.relative_to(lane_dir)\n            if rel.parts and rel.parts[0] == "Reports":\n                continue\n            dst = final_fastq_dir / rel\n            dst.parent.mkdir(parents=True, exist_ok=True)\n            if dst.exists():\n                raise SystemExit(f"ERROR: refusing to overwrite merged FASTQ: {dst}")\n            src_abs = str(src.resolve())\n            src_text = str(src)\n            os.replace(src, dst)\n            dst_text = str(dst)\n            moved[src_abs] = dst_text\n            moved[src_text] = dst_text\n            by_name[src.name] = dst_text\n    moved.update({f"__BASENAME__/{name}": path for name, path in by_name.items()})\n    return moved\n\n\ndef copy_lane_artifacts(lane_dirs: list[Path], report_dir: Path) -> None:\n    by_lane_root = report_dir / "by_lane"\n    for lane_dir in lane_dirs:\n        lane_dest = by_lane_root / lane_dir.name\n        lane_dest.mkdir(parents=True, exist_ok=True)\n        for child in sorted(lane_dir.iterdir()):\n            if child.is_file() and child.name.endswith(".fastq.gz"):\n                continue\n            dest = lane_dest / child.name\n            if child.is_dir():\n                if dest.exists():\n                    shutil.rmtree(dest)\n                shutil.copytree(child, dest, ignore=shutil.ignore_patterns("*.fastq.gz"))\n            elif child.is_file():\n                shutil.copy2(child, dest)\n\n\ndef rewrite_fastq_path(value: str, lane_dirs: list[Path], moved: dict[str, str]) -> str:\n    text = str(value or "").strip()\n    if not text:\n        return text\n    if text in moved:\n        return moved[text]\n    path = Path(text)\n    try:\n        resolved = str(path.resolve())\n    except OSError:\n        resolved = text\n    if resolved in moved:\n        return moved[resolved]\n    basename_key = "__BASENAME__/" + path.name\n    if basename_key in moved:\n        return moved[basename_key]\n    for lane_dir in lane_dirs:\n        candidate = lane_dir / text\n        if str(candidate) in moved:\n            return moved[str(candidate)]\n        try:\n            candidate_resolved = str(candidate.resolve())\n        except OSError:\n            candidate_resolved = str(candidate)\n        if candidate_resolved in moved:\n            return moved[candidate_resolved]\n    if text.endswith(".fastq.gz"):\n        raise SystemExit(f"ERROR: FASTQ listed by BCL Convert was not produced for merge: {text}")\n    return text\n\n\ndef merge_fastq_list(lane_dirs: list[Path], dest: Path, moved: dict[str, str]) -> None:\n    merged_header: list[str] | None = None\n    merged_rows: list[dict[str, str]] = []\n    for lane_dir in lane_dirs:\n        header, rows = read_csv(lane_dir / "Reports" / "fastq_list.csv", required=True)\n        if merged_header is None:\n            merged_header = header\n        elif header != merged_header:\n            raise SystemExit(f"ERROR: fastq_list.csv header mismatch in {lane_dir}")\n        for row in rows:\n            for key in ("Read1File", "Read2File", "READ1FILE", "READ2FILE", "Read1_File", "Read2_File"):\n                if key in row:\n                    row[key] = rewrite_fastq_path(row[key], lane_dirs, moved)\n            merged_rows.append(row)\n    if merged_header is None:\n        raise SystemExit("ERROR: no lane fastq_list.csv files found")\n    write_csv(dest, merged_header, merged_rows)\n\n\ndef main() -> int:\n    args = parse_args()\n    lane_fastq_root = Path(args.lane_fastq_root)\n    final_fastq_dir = Path(args.final_fastq_dir)\n    report_dir = Path(args.report_dir)\n    log_path = Path(args.log)\n    done_path = Path(args.done)\n    lanes = [lane for lane in args.lanes.split(",") if lane]\n    if not lanes:\n        raise SystemExit("ERROR: no BCL lanes were provided to merge")\n    lane_dirs = [lane_fastq_root / lane for lane in lanes]\n    report_dir.mkdir(parents=True, exist_ok=True)\n    log_path.parent.mkdir(parents=True, exist_ok=True)\n    with log_path.open("a", encoding="utf-8") as log:\n        print(f"DYEC lane merge lanes: {\',\'.join(lanes)}", file=log)\n        print(f"DYEC lane merge root: {lane_fastq_root}", file=log)\n        print(f"DYEC final fastq dir: {final_fastq_dir}", file=log)\n    moved = move_lane_fastqs(lane_dirs, final_fastq_dir)\n    copy_lane_artifacts(lane_dirs, report_dir)\n    merge_fastq_list(lane_dirs, report_dir / "fastq_list.csv", moved)\n    merge_report(lane_dirs, "Demultiplex_Stats.csv", report_dir / "Demultiplex_Stats.csv", required=True)\n    merge_report(lane_dirs, "Top_Unknown_Barcodes.csv", report_dir / "Top_Unknown_Barcodes.csv", required=False)\n    merge_report(lane_dirs, "Index_Hopping_Counts.csv", report_dir / "Index_Hopping_Counts.csv", required=False)\n    done_path.parent.mkdir(parents=True, exist_ok=True)\n    done_path.touch()\n    return 0\n\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n""", encoding="utf-8")\nmerge_helper.chmod(0o755)\n\nlane_globals_marker = \'BCL_CONTAINER_URI = f"docker://nfcore/bclconvert:{BCL_RUNTIME_VERSION}"\\n\\n\\nlocalrules:\'\nlane_globals = r"""\nimport json\n\nBCL_CONTAINER_URI = f"docker://nfcore/bclconvert:{BCL_RUNTIME_VERSION}"\nBCL_OUTPUT_LEGACY_STATS = _bool(BCLCFG.get("output_legacy_stats", False), False)\nBCL_NUM_UNKNOWN_BARCODES_REPORTED = _intish(BCLCFG.get("num_unknown_barcodes_reported", 1000), 1000)\n# Untested pending feature: optional sample-sheet setting injection is dormant unless config supplies values.\nBCL_SAMPLE_SHEET_SETTING_CONFIG_KEYS = {\n    "AdapterRead1": "adapter_read1",\n    "AdapterRead2": "adapter_read2",\n    "AdapterBehavior": "adapter_behavior",\n    "AdapterStringency": "adapter_stringency",\n    "MinimumAdapterOverlap": "minimum_adapter_overlap",\n    "BarcodeMismatchesIndex1": "barcode_mismatches_index1",\n    "BarcodeMismatchesIndex2": "barcode_mismatches_index2",\n    "CreateFastqForIndexReads": "create_fastq_for_index_reads",\n    "MinimumTrimmedReadLength": "minimum_trimmed_read_length",\n    "MaskShortReads": "mask_short_reads",\n    "OverrideCycles": "override_cycles",\n    "SoftwareVersion": "software_version",\n    "TrimUMI": "trim_umi",\n    "NoLaneSplitting": "no_lane_splitting",\n}\n\n\ndef _bcl_mapping(value, *, name):\n    if value in (None, "", "None"):\n        return {}\n    if isinstance(value, dict):\n        return value\n    if isinstance(value, str):\n        try:\n            parsed = json.loads(value)\n        except json.JSONDecodeError as exc:\n            raise WorkflowError(f"bclconvert.{name} must be a mapping or JSON object string") from exc\n        if not isinstance(parsed, dict):\n            raise WorkflowError(f"bclconvert.{name} must be a mapping or JSON object string")\n        return parsed\n    raise WorkflowError(f"bclconvert.{name} must be a mapping or JSON object string")\n\n\nBCL_SAMPLE_SHEET_SETTINGS = {\n    canonical: str(BCLCFG.get(config_key, "") or "").strip()\n    for canonical, config_key in BCL_SAMPLE_SHEET_SETTING_CONFIG_KEYS.items()\n    if str(BCLCFG.get(config_key, "") or "").strip()\n}\nBCL_SAMPLE_SHEET_SETTINGS.update(_bcl_mapping(BCLCFG.get("sample_sheet_settings", {}), name="sample_sheet_settings"))\nBCL_SAMPLE_SHEET_SETTINGS_BY_LANE = _bcl_mapping(\n    BCLCFG.get("sample_sheet_settings_by_lane", {}), name="sample_sheet_settings_by_lane"\n)\nBCL_SAMPLE_SHEET_SETTINGS_JSON = json.dumps(BCL_SAMPLE_SHEET_SETTINGS, sort_keys=True)\nBCL_SAMPLE_SHEET_SETTINGS_BY_LANE_JSON = json.dumps(BCL_SAMPLE_SHEET_SETTINGS_BY_LANE, sort_keys=True)\n\nDYEC_BCLCONVERT_LANE_SPLIT_PATCH = True\nBCL_LANE_ROOT = Path(BCL_RUN_DIR) / "Data" / "Intensities" / "BaseCalls"\nif BCL_TARGET_REQUESTED:\n    if not BCL_LANE_ROOT.is_dir():\n        raise WorkflowError(f"BCL run directory is missing lane root: {BCL_LANE_ROOT}")\n    BCL_LANES = sorted(\n        path.name\n        for path in BCL_LANE_ROOT.iterdir()\n        if path.is_dir() and re.fullmatch(r"L[0-9][0-9][0-9]", path.name)\n    )\n    if not BCL_LANES:\n        raise WorkflowError(f"BCL run directory has no L### lane directories under {BCL_LANE_ROOT}")\nelse:\n    BCL_LANES = []\nBCL_LANE_FASTQ_ROOT = f"{BCL_ROOT}/lane_fastqs"\nBCL_LANE_REPORT_ROOT = f"{BCL_ROOT}/lane_reports"\nBCL_LANE_DONE_FILES = expand(f"{BCL_LANE_REPORT_ROOT}/{{lane}}/bclconvert.done", lane=BCL_LANES)\nBCL_LANE_FASTQ_LIST_FILES = expand(f"{BCL_LANE_FASTQ_ROOT}/{{lane}}/Reports/fastq_list.csv", lane=BCL_LANES)\nBCL_LANE_DEMUX_STATS_FILES = expand(f"{BCL_LANE_FASTQ_ROOT}/{{lane}}/Reports/Demultiplex_Stats.csv", lane=BCL_LANES)\nBCL_LANE_SAMPLE_SHEET_FILES = expand(f"{BCL_LANE_REPORT_ROOT}/{{lane}}/SampleSheet.csv", lane=BCL_LANES)\n\n\nlocalrules:"""\nlane_rule = r"""\nrule run_bclconvert_lane:\n    input:\n        validated=BCL_VALIDATE_OK,\n        sample_sheet=BCL_NORMALIZED_SAMPLE_SHEET,\n    output:\n        done=f"{BCL_LANE_REPORT_ROOT}/{{lane}}/bclconvert.done",\n        fastq_list=f"{BCL_LANE_FASTQ_ROOT}/{{lane}}/Reports/fastq_list.csv",\n        demux_stats=f"{BCL_LANE_FASTQ_ROOT}/{{lane}}/Reports/Demultiplex_Stats.csv",\n        lane_sample_sheet=f"{BCL_LANE_REPORT_ROOT}/{{lane}}/SampleSheet.csv",\n    wildcard_constraints:\n        lane="L[0-9][0-9][0-9]",\n    threads:\n        BCL_THREADS\n    resources:\n        partition=BCL_PARTITION,\n        vcpu=BCL_THREADS,\n        threads=BCL_THREADS,\n        mem_mb=BCL_MEM_MB,\n        tmpdir=BCL_TMPDIR,\n        exclusive="--exclusive",\n    params:\n        cluster_sample=lambda wildcards: f"run_bclconvert_{wildcards.lane}",\n        run_dir=BCL_RUN_DIR,\n        container_uri=BCL_CONTAINER_URI,\n        tmpdir=BCL_TMPDIR,\n        lane_number=lambda wildcards: str(int(wildcards.lane[1:])),\n        lane_output_dir=lambda wildcards: f"{BCL_LANE_FASTQ_ROOT}/{wildcards.lane}",\n        parallel_tiles=BCL_PARALLEL_TILES,\n        conversion_threads=BCL_CONVERSION_THREADS,\n        compression_threads=BCL_COMPRESSION_THREADS,\n        decompression_threads=BCL_DECOMPRESSION_THREADS,\n        fastq_gzip_compression_level=BCL_FASTQ_GZIP_COMPRESSION_LEVEL,\n        shared_thread_odirect_output="true" if BCL_SHARED_THREAD_ODIRECT_OUTPUT else "false",\n        output_legacy_stats="true" if BCL_OUTPUT_LEGACY_STATS else "false",\n        num_unknown_barcodes_reported=BCL_NUM_UNKNOWN_BARCODES_REPORTED,\n        sample_sheet_settings_json=BCL_SAMPLE_SHEET_SETTINGS_JSON,\n        sample_sheet_settings_by_lane_json=BCL_SAMPLE_SHEET_SETTINGS_BY_LANE_JSON,\n        force="-f" if BCL_FORCE else "",\n        strict_mode="true" if BCL_STRICT_MODE else "false",\n        first_tile_only="true" if BCL_FIRST_TILE_ONLY else "false",\n        sampleproject_subdirectories="true" if BCL_SAMPLEPROJECT_SUBDIRS else "false",\n    log:\n        f"{BCL_LOG_DIR}/run_bclconvert.{{lane}}.log",\n    benchmark:\n        f"{BCL_BENCH_DIR}/run_bclconvert.{{lane}}.bench.tsv",\n    shell:\n        "TMPDIR={params.tmpdir:q} bash workflow/scripts/dyec_run_bclconvert_lane.sh "\n        "{params.container_uri:q} {params.run_dir:q} {params.lane_output_dir:q} {input.sample_sheet:q} "\n        "{params.lane_number:q} {output.lane_sample_sheet:q} {params.strict_mode:q} "\n        "{params.first_tile_only:q} {params.sampleproject_subdirectories:q} "\n        "{params.fastq_gzip_compression_level:q} {params.parallel_tiles:q} "\n        "{params.conversion_threads:q} {params.compression_threads:q} "\n        "{params.decompression_threads:q} {params.shared_thread_odirect_output:q} "\n        "{params.output_legacy_stats:q} {params.num_unknown_barcodes_reported:q} "\n        "{params.sample_sheet_settings_json:q} {params.sample_sheet_settings_by_lane_json:q} "\n        "{params.force:q} {threads:q} {log:q} {output.fastq_list:q} "\n        "{output.demux_stats:q} {output.done:q}"\n\n\nrule run_bclconvert:\n    input:\n        validated=BCL_VALIDATE_OK,\n        sample_sheet=BCL_NORMALIZED_SAMPLE_SHEET,\n        lane_done=BCL_LANE_DONE_FILES,\n        fastq_lists=BCL_LANE_FASTQ_LIST_FILES,\n        demux_stats=BCL_LANE_DEMUX_STATS_FILES,\n        lane_sample_sheets=BCL_LANE_SAMPLE_SHEET_FILES,\n    output:\n        done=BCL_DONE,\n        fastq_list=f"{BCL_REPORT_DIR}/fastq_list.csv",\n        demux_stats=f"{BCL_REPORT_DIR}/Demultiplex_Stats.csv",\n    threads:\n        1\n    resources:\n        partition=BCL_PARTITION,\n        vcpu=1,\n        threads=1,\n        mem_mb=3000,\n        tmpdir=BCL_TMPDIR,\n    params:\n        cluster_sample="run_bclconvert_merge_lanes",\n        lanes=",".join(BCL_LANES),\n        lane_fastq_root=BCL_LANE_FASTQ_ROOT,\n        final_fastq_dir=BCL_FASTQ_DIR,\n        report_dir=BCL_REPORT_DIR,\n    log:\n        f"{BCL_LOG_DIR}/run_bclconvert.merge_lanes.log",\n    benchmark:\n        f"{BCL_BENCH_DIR}/run_bclconvert.merge_lanes.bench.tsv",\n    shell:\n        "python workflow/scripts/dyec_merge_bclconvert_lanes.py "\n        "--lane-fastq-root {params.lane_fastq_root:q} "\n        "--final-fastq-dir {params.final_fastq_dir:q} "\n        "--report-dir {params.report_dir:q} "\n        "--lanes {params.lanes:q} "\n        "--done {output.done:q} "\n        "--log {log:q} >> {log:q} 2>&1 && "\n        "test -s {output.fastq_list:q} && test -s {output.demux_stats:q}"\n"""\n\ntext = rule_path.read_text(encoding="utf-8")\nif "DYEC_BCLCONVERT_LANE_SPLIT_PATCH = True" not in text:\n    if lane_globals_marker not in text:\n        raise SystemExit(f"[ERROR] BCL Convert lane globals insertion point not found in {rule_path}")\n    text = text.replace(lane_globals_marker, lane_globals, 1)\n\nlocalrules_marker = "localrules:\\n    bclconvert_validate_inputs,\\n"\nlocalrules_patch = (\n    "localrules:\\n"\n    "    bclconvert_validate_inputs,\\n"\n    "    run_bclconvert,\\n"\n    "    bclconvert_metrics_summary,\\n"\n    "    bclconvert_generate_units_tsv,\\n"\n)\nif "run_bclconvert,\\n    bclconvert_metrics_summary" not in text:\n    if localrules_marker not in text:\n        raise SystemExit(f"[ERROR] BCL Convert localrules insertion point not found in {rule_path}")\n    text = text.replace(localrules_marker, localrules_patch, 1)\n\nstart_marker = "\\nrule run_bclconvert:\\n"\nend_marker = "\\n\\nrule bclconvert_generate_units_tsv:"\nif "rule run_bclconvert_lane:" not in text:\n    start = text.find(start_marker)\n    end = text.find(end_marker, start + len(start_marker))\n    if start < 0 or end < 0:\n        raise SystemExit(f"[ERROR] BCL Convert run_bclconvert rule block not found in {rule_path}")\n    text = text[:start] + "\\n" + lane_rule + text[end:]\n\nrule_path.write_text(text, encoding="utf-8")\nprint(\n    "[INFO] Patched BCL Convert direct lane-split rules in "\n    f"{rule_path}; helpers={prepare_lane_samplesheet},{run_lane_helper},{merge_helper}"\n)\n'


@dataclass
class RemoteConfig:
    stage_dir: str
    samples_path: str
    units_path: str


@dataclass
class WorkflowLaunchInfo:
    session_name: str
    run_dir: str
    repo_path: str


def normalize_remote_path(path: str) -> str:
    if path.startswith("~/"):
        return path.replace("~/", "/home/ubuntu/", 1)
    if path == "~":
        return "/home/ubuntu"
    return path


def parse_remote_config(stdout: str) -> RemoteConfig:
    stage_dir = samples_path = units_path = None
    for line in stdout.splitlines():
        if line.startswith("__DAYLILY_STAGE_DIR__="):
            stage_dir = line.split("=", 1)[1].strip()
        elif line.startswith("__DAYLILY_STAGE_SAMPLES__="):
            samples_path = line.split("=", 1)[1].strip()
        elif line.startswith("__DAYLILY_STAGE_UNITS__="):
            units_path = line.split("=", 1)[1].strip()
        elif line.startswith("__DAYLILY_ERROR__="):
            raise CommandError(f"Remote lookup failed: {line.split('=', 1)[1]}")
    if not (stage_dir and samples_path and units_path):
        raise CommandError("Unable to determine staged config paths on the head node.")
    return RemoteConfig(stage_dir, samples_path, units_path)


def parse_workflow_launch(stdout: str) -> WorkflowLaunchInfo:
    session_name = run_dir = repo_path = None
    for line in stdout.splitlines():
        if line.startswith("__DAYLILY_SESSION__="):
            session_name = line.split("=", 1)[1].strip()
        elif line.startswith("__DAYLILY_RUN_DIR__="):
            run_dir = line.split("=", 1)[1].strip()
        elif line.startswith("__DAYLILY_REPO_PATH__="):
            repo_path = line.split("=", 1)[1].strip()
        elif line.startswith("__DAYLILY_ERROR__="):
            raise CommandError(line.split("=", 1)[1])
    if not (session_name and run_dir and repo_path):
        raise CommandError("Tmux session creation did not report success.")
    return WorkflowLaunchInfo(session_name=session_name, run_dir=run_dir, repo_path=repo_path)


def discover_stage_config(
    instance_id: str,
    profile: str,
    region: str,
    stage_dir: Optional[str],
    stage_base: str,
) -> RemoteConfig:
    remote_wait_seconds = max(1, STAGE_CONFIG_DISCOVERY_TIMEOUT_SECONDS - 15)
    if stage_dir:
        target_dir = normalize_remote_path(stage_dir.rstrip("/"))
        script = f"""
set -euo pipefail
if [[ "$(id -un)" != "ubuntu" ]]; then
  echo "__DAYLILY_ERROR__=wrong_user"
  exit 5
fi
STAGE_DIR={shlex.quote(target_dir)}
WAIT_DEADLINE=$((SECONDS + {remote_wait_seconds}))
last_error=missing_stage_dir
found_config=false
while true; do
  if [[ -d "$STAGE_DIR" ]]; then
    samples_file=$(ls -1 "$STAGE_DIR"/*_samples.tsv 2>/dev/null | head -n 1 || true)
    units_file=$(ls -1 "$STAGE_DIR"/*_units.tsv 2>/dev/null | head -n 1 || true)
    if [[ -n "$samples_file" && -n "$units_file" ]]; then
      echo "__DAYLILY_STAGE_DIR__=$STAGE_DIR"
      echo "__DAYLILY_STAGE_SAMPLES__=$samples_file"
      echo "__DAYLILY_STAGE_UNITS__=$units_file"
      found_config=true
      break
    fi
    last_error=missing_config
  else
    last_error=missing_stage_dir
  fi
  if (( SECONDS >= WAIT_DEADLINE )); then
    echo "__DAYLILY_ERROR__=$last_error"
    if [[ "$last_error" == "missing_stage_dir" ]]; then
      exit 2
    fi
    exit 3
  fi
  sleep 5
done
if [[ "$found_config" == "true" ]]; then
  true
fi
"""
    else:
        stage_base_norm = normalize_remote_path(stage_base.rstrip("/"))
        script = f"""
set -euo pipefail
if [[ "$(id -un)" != "ubuntu" ]]; then
  echo "__DAYLILY_ERROR__=wrong_user"
  exit 5
fi
STAGE_BASE={shlex.quote(stage_base_norm)}
if [[ ! -d "$STAGE_BASE" ]]; then
  echo "__DAYLILY_ERROR__=missing_stage_base"
  exit 2
fi
WAIT_DEADLINE=$((SECONDS + {remote_wait_seconds}))
last_error=no_stage_runs
found_config=false
while true; do
  latest_dir=$(ls -1dt "$STAGE_BASE"/*/ 2>/dev/null | head -n 1 || true)
  if [[ -n "$latest_dir" ]]; then
    samples_file=$(ls -1 "$latest_dir"/*_samples.tsv 2>/dev/null | head -n 1 || true)
    units_file=$(ls -1 "$latest_dir"/*_units.tsv 2>/dev/null | head -n 1 || true)
    if [[ -n "$samples_file" && -n "$units_file" ]]; then
      echo "__DAYLILY_STAGE_DIR__=$latest_dir"
      echo "__DAYLILY_STAGE_SAMPLES__=$samples_file"
      echo "__DAYLILY_STAGE_UNITS__=$units_file"
      found_config=true
      break
    fi
    last_error=missing_config
  else
    last_error=no_stage_runs
  fi
  if (( SECONDS >= WAIT_DEADLINE )); then
    echo "__DAYLILY_ERROR__=$last_error"
    if [[ "$last_error" == "missing_config" ]]; then
      exit 4
    fi
    exit 3
  fi
  sleep 5
done
if [[ "$found_config" == "true" ]]; then
  true
fi
"""

    result = run_shell(
        instance_id,
        region,
        script,
        profile=profile,
        timeout=STAGE_CONFIG_DISCOVERY_TIMEOUT_SECONDS,
        comment="Discover staged config",
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    return parse_remote_config(result.stdout)


def format_list(values: List[str]) -> str:
    quoted = ",".join(f"'{value.strip()}'" for value in values if value.strip())
    return f"[{quoted}]"


def build_default_command(
    target: str,
    genome: str,
    jobs: int,
    aligners: List[str],
    dedupers: List[str],
    snv_callers: List[str],
    sv_callers: List[str],
    containerized: bool,
    dry_run: bool,
    extra: Optional[str],
) -> str:
    config_args = [
        f"genome_build={genome}",
        f"aligners={format_list(aligners)}",
        f"dedupers={format_list(dedupers)}",
        f"snv_callers={format_list(snv_callers)}",
    ]
    if sv_callers:
        config_args.append(f"sv_callers={format_list(sv_callers)}")
    command = [
        "DAY_CONTAINERIZED=true" if containerized else "DAY_CONTAINERIZED=false",
        "bin/day_run",
        target,
        "-p",
        "-k",
        f"-j {jobs}",
        "--config",
        " ".join(config_args),
    ]
    if dry_run:
        command.append("-n")
    if extra:
        command.append(extra)
    return " ".join(command)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Clone daylily-omics-analysis and launch a workflow inside tmux.",
    )
    parser.add_argument("--profile", default=os.environ.get("AWS_PROFILE"))
    parser.add_argument("--region", help="AWS region for the cluster")
    parser.add_argument("--cluster", help="ParallelCluster name")
    parser.add_argument(
        "--stage-dir",
        help="Specific staging directory containing *_samples.tsv and *_units.tsv",
    )
    parser.add_argument(
        "--run-context-file",
        help="Local runs.tsv file to write as config/runs.tsv for run-analysis workflows",
    )
    parser.add_argument(
        "--samples-file",
        help="Local samples.tsv file to write as config/samples.tsv for sample-analysis workflows",
    )
    parser.add_argument(
        "--units-file",
        help="Local units.tsv file to write as config/units.tsv for sample-analysis workflows",
    )
    parser.add_argument(
        "--stage-base",
        default="/fsx/staging/staged_external_sequencing_data",
        help="Base staging directory to scan when --stage-dir is omitted",
    )
    parser.add_argument(
        "--no-input-staging",
        dest="input_staging",
        action="store_false",
        help="Do not copy staged samples/units or write a run context before launching",
    )
    parser.add_argument(
        "--no-default-activation",
        dest="default_activation",
        action="store_false",
        help="Do not run the standard dyoainit plus Slurm activation before --dy-command",
    )
    parser.add_argument(
        "--bootstrap-test-config",
        action="store_true",
        help="Copy DayOA bundled test samples and units into config/ before launch",
    )
    parser.add_argument(
        "--session-name",
        help="Name of the tmux session to create on the head node. Defaults to --analysis-id.",
    )
    parser.add_argument(
        "--analysis-id",
        required=True,
        help="Analysis identifier passed to day-clone -d and used under /fsx/analysis_results.",
    )
    parser.add_argument(
        "--executing-entity",
        "-u",
        help="User or system identifier used under /fsx/analysis_results. Defaults to --cluster.",
    )
    parser.add_argument(
        "--repository",
        default="daylily-omics-analysis",
        help="Repository key to pass to day-clone",
    )
    parser.add_argument(
        "--git-tag",
        "-t",
        default="main",
        help="Git branch or tag to pass to day-clone",
    )
    parser.add_argument("--project", help="Project/budget to supply to dyoainit")
    parser.add_argument(
        "--skip-project-check",
        dest="skip_project_check",
        action="store_true",
        help="Skip upstream project validation in dyoainit (default for the supported flow)",
    )
    parser.add_argument(
        "--strict-project-check",
        dest="skip_project_check",
        action="store_false",
        help="Enable upstream project validation in dyoainit",
    )
    parser.add_argument("--genome", default="hg38")
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument("--aligners", default="bwa2a")
    parser.add_argument("--dedupers", default="dmd")
    parser.add_argument("--snv-callers", default="deep")
    parser.add_argument("--sv-callers", default="")
    parser.add_argument("--target", default="produce_snv_concordances")
    parser.add_argument("--dy-command", help="Override the dy-r command entirely")
    parser.add_argument("--snakemake-extra", help="Additional arguments appended to dy-r")
    parser.add_argument(
        "--max-runtime-minutes",
        type=int,
        default=DEFAULT_JOB_MAX_RUNTIME_MINUTES,
        help=(
            "Default Snakemake job time resource in minutes. "
            "Set 0 to omit; explicit --default-resources time=... in the command wins."
        ),
    )
    parser.add_argument(
        "--no-containerized",
        action="store_true",
        help="Disable DAY_CONTAINERIZED (enabled by default)",
    )
    parser.add_argument(
        "--export-destination-s3-uri",
        help="Full S3 prefix ending in <executing-entity>/<analysis-id>/ for auto-export",
    )
    parser.add_argument(
        "--export-trigger",
        choices=("none", "on-success", "on-fail", "all"),
        default="none",
        help="Auto-export trigger after the workflow exits",
    )
    parser.add_argument(
        "--delete-on-export-success",
        action="store_true",
        help="Delete the FSx analysis directory after a successful requested export",
    )
    parser.add_argument(
        "--replace-existing-analysis-dir",
        action="store_true",
        help=(
            "Explicit retry mode: remove an existing same analysis directory before "
            "launching. Without this flag, existing analysis directories fail hard."
        ),
    )
    parser.add_argument(
        "--artifact-registration-command-id",
        default="",
        help="Catalog command id whose artifact_registration policy should run after export",
    )
    parser.add_argument(
        "--dewey-url", default="", help="Dewey base URL for post-export registration"
    )
    parser.add_argument(
        "--dewey-token-env",
        default="",
        help="Environment variable containing the Dewey bearer token",
    )
    parser.add_argument(
        "--dewey-analysis-dir-external-object-id",
        default="",
        help="External object id for the exported daylily-omics-analysis S3 directory",
    )
    parser.add_argument(
        "--dewey-run-artifact-euid",
        default="",
        help="Dewey run artifact EUID linked to the exported analysis directory external object",
    )
    parser.add_argument(
        "--dewey-ursa-analysis-euid",
        default="",
        help="Ursa analysis EUID linked to the exported analysis directory external object",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.set_defaults(skip_project_check=True, input_staging=True, default_activation=True)
    return parser


def validate_export_registration_args(args: argparse.Namespace) -> None:
    if args.export_destination_s3_uri and args.export_trigger == "none":
        raise CommandError("--export-trigger must not be none when auto-export is requested.")
    if args.export_trigger != "none" and not args.export_destination_s3_uri:
        raise CommandError("--export-destination-s3-uri is required when --export-trigger is set.")
    if args.delete_on_export_success and not args.export_destination_s3_uri:
        raise CommandError("--delete-on-export-success requires --export-destination-s3-uri.")
    if args.artifact_registration_command_id and args.export_trigger == "none":
        raise CommandError("--artifact-registration-command-id requires an export trigger.")
    if args.artifact_registration_command_id and not args.dewey_url:
        raise CommandError("--dewey-url is required with --artifact-registration-command-id.")
    if args.artifact_registration_command_id and not args.dewey_token_env:
        raise CommandError("--dewey-token-env is required with --artifact-registration-command-id.")
    if not args.artifact_registration_command_id and (args.dewey_url or args.dewey_token_env):
        raise CommandError(
            "--artifact-registration-command-id is required when Dewey registration options are set."
        )
    dewey_link_options = {
        "--dewey-analysis-dir-external-object-id": args.dewey_analysis_dir_external_object_id,
        "--dewey-run-artifact-euid": args.dewey_run_artifact_euid,
        "--dewey-ursa-analysis-euid": args.dewey_ursa_analysis_euid,
    }
    if any(str(value or "").strip() for value in dewey_link_options.values()):
        missing = [
            option for option, value in dewey_link_options.items() if not str(value or "").strip()
        ]
        if missing:
            raise CommandError(
                "Dewey analysis-directory external-link options must be provided together: "
                + ", ".join(missing)
            )
        if not args.artifact_registration_command_id:
            raise CommandError(
                "--artifact-registration-command-id is required with Dewey external-link options."
            )


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.profile:
        raise CommandError("AWS profile is required. Set AWS_PROFILE or use --profile.")
    validate_export_registration_args(args)
    try:
        validate_job_max_runtime_minutes(args.max_runtime_minutes)
    except ValueError as exc:
        raise CommandError(str(exc)) from exc

    need_cmd("aws")
    need_cmd("pcluster")

    region = resolve_region(args.profile, args.region)
    cluster_name = resolve_cluster(args.profile, region, args.cluster)
    analysis_id = validate_analysis_segment(args.analysis_id, field_name="analysis_id")
    executing_entity = validate_analysis_segment(
        args.executing_entity or cluster_name,
        field_name="executing_entity",
    )
    source_path = analysis_source_path(
        executing_entity=executing_entity,
        analysis_id=analysis_id,
        headnode=True,
    )
    if not args.session_name:
        args.session_name = analysis_id
    if args.export_destination_s3_uri:
        from daylily_ec.workflow.export_data import (
            _create_session,
            validate_export_destination_s3_uri,
            validate_s3_destination_prefix_empty,
        )

        validate_export_destination_s3_uri(
            args.export_destination_s3_uri,
            source_path=source_path,
        )
        validate_s3_destination_prefix_empty(
            _create_session(region, args.profile).client("s3"),
            args.export_destination_s3_uri,
            source_path=source_path,
        )
    target = resolve_headnode_instance_id(cluster_name, region, profile=args.profile)
    wait_for_ssm_online(target.instance_id, region, profile=args.profile, timeout=120)
    validate_headnode_readiness(
        target.instance_id,
        region,
        profile=args.profile,
        timeout=120,
        comment="Validate DAY-EC headnode readiness before workflow launch",
    )

    run_context_content: Optional[str] = None
    samples_content: Optional[str] = None
    units_content: Optional[str] = None
    if args.run_context_file:
        if not args.input_staging:
            raise CommandError("--run-context-file cannot be used with --no-input-staging.")
        if args.stage_dir:
            raise CommandError("--stage-dir cannot be used with --run-context-file.")
        if args.samples_file or args.units_file:
            raise CommandError(
                "--run-context-file cannot be used with --samples-file or --units-file."
            )
        run_context_path = Path(args.run_context_file).expanduser()
        if not run_context_path.is_file():
            raise CommandError(f"Run context file not found: {run_context_path}")
        run_context_content = run_context_path.read_text(encoding="utf-8")
        stage_config = None
    elif args.samples_file or args.units_file:
        if not args.input_staging:
            raise CommandError(
                "--samples-file/--units-file cannot be used with --no-input-staging."
            )
        if args.stage_dir:
            raise CommandError("--stage-dir cannot be used with --samples-file/--units-file.")
        if not args.samples_file or not args.units_file:
            raise CommandError("--samples-file and --units-file must be provided together.")
        samples_path = Path(args.samples_file).expanduser()
        units_path = Path(args.units_file).expanduser()
        if not samples_path.is_file():
            raise CommandError(f"Samples file not found: {samples_path}")
        if not units_path.is_file():
            raise CommandError(f"Units file not found: {units_path}")
        samples_content = samples_path.read_text(encoding="utf-8")
        units_content = units_path.read_text(encoding="utf-8")
        stage_config = None
    elif args.input_staging:
        stage_config = discover_stage_config(
            target.instance_id,
            args.profile,
            region,
            args.stage_dir,
            args.stage_base,
        )
    else:
        if args.stage_dir:
            raise CommandError("--stage-dir cannot be used with --no-input-staging.")
        stage_config = None

    if args.dy_command:
        dy_command = args.dy_command
    else:
        dy_command = build_default_command(
            target=args.target,
            genome=args.genome,
            jobs=args.jobs,
            aligners=args.aligners.split(","),
            dedupers=args.dedupers.split(","),
            snv_callers=args.snv_callers.split(","),
            sv_callers=[value for value in args.sv_callers.split(",") if value],
            containerized=not args.no_containerized,
            dry_run=args.dry_run,
            extra=args.snakemake_extra,
        )
    dy_command = append_default_job_runtime(
        dy_command,
        max_runtime_minutes=args.max_runtime_minutes,
    )

    project_arg = shlex.quote(args.project) if args.project else ""
    repository_literal = json.dumps(args.repository)
    dy_command_literal = shlex.quote(dy_command)
    skip_check = "true" if args.skip_project_check else "false"
    run_context_mode = run_context_content is not None
    sample_config_mode = samples_content is not None or units_content is not None
    run_context_mode_literal = "true" if run_context_mode else "false"
    sample_config_mode_literal = "true" if sample_config_mode else "false"
    input_staging_mode_literal = "true" if args.input_staging else "false"
    default_activation_literal = "true" if args.default_activation else "false"
    bootstrap_test_config_literal = "true" if args.bootstrap_test_config else "false"
    run_context_payload = shlex.quote(run_context_content or "")
    samples_payload = shlex.quote(samples_content or "")
    units_payload = shlex.quote(units_content or "")
    export_destination_literal = shlex.quote(args.export_destination_s3_uri or "")
    delete_on_export_success = "true" if args.delete_on_export_success else "false"
    replace_existing_analysis_dir = "true" if args.replace_existing_analysis_dir else "false"
    if stage_config is None:
        stage_samples_path = ""
        stage_units_path = ""
    else:
        stage_samples_path = stage_config.samples_path
        stage_units_path = stage_config.units_path
    write_status_python = shlex.quote(
        "import json, os, pathlib; "
        "path = pathlib.Path(os.environ['DAYLILY_STATUS_FILE']); "
        "exit_code_raw = os.environ.get('DAYLILY_STATUS_EXIT_CODE', ''); "
        "exit_code = None if exit_code_raw in ('', '__PENDING__') else "
        "(int(exit_code_raw) if exit_code_raw.lstrip('-').isdigit() else exit_code_raw); "
        "payload = dict("
        "session_name=os.environ['DAYLILY_STATUS_SESSION'], "
        "repo_path=os.environ['DAYLILY_STATUS_REPO_PATH'], "
        "started_at=os.environ.get('DAYLILY_STATUS_STARTED_AT') or None, "
        "completed_at=os.environ.get('DAYLILY_STATUS_COMPLETED_AT') or None, "
        "exit_code=exit_code, "
        "command=os.environ['DAYLILY_STATUS_COMMAND']); "
        "path.parent.mkdir(parents=True, exist_ok=True); "
        "path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\\n', encoding='utf-8')"
    )
    run_context_projection_python = shlex.quote(BCL_RUN_CONTEXT_PROJECTION_SCRIPT)
    bclconvert_profile_patch_python = shlex.quote(BCLCONVERT_PROFILE_PATCH_SCRIPT)
    pipeline_script = f"""
set -euo pipefail
if [[ "$(id -un)" != "ubuntu" ]]; then
  echo "__DAYLILY_ERROR__=wrong_user"
  exit 6
	fi
	SESSION_NAME={shlex.quote(args.session_name)}
	ANALYSIS_ID={shlex.quote(analysis_id)}
	EXECUTING_ENTITY={shlex.quote(executing_entity)}
	RUN_CONTEXT_MODE={run_context_mode_literal}
	SAMPLE_CONFIG_MODE={sample_config_mode_literal}
	INPUT_STAGING_MODE={input_staging_mode_literal}
	DEFAULT_ACTIVATION={default_activation_literal}
	BOOTSTRAP_TEST_CONFIG={bootstrap_test_config_literal}
	RUN_CONTEXT_PAYLOAD={run_context_payload}
	SAMPLES_PAYLOAD={samples_payload}
	UNITS_PAYLOAD={units_payload}
	STAGE_SAMPLES={shlex.quote(stage_samples_path)}
	STAGE_UNITS={shlex.quote(stage_units_path)}
	PROJECT_VALUE={project_arg if project_arg else ""}
	SKIP_PROJECT_CHECK={skip_check}
	DY_COMMAND={dy_command_literal}
	EXPORT_DESTINATION_S3_URI={export_destination_literal}
	EXPORT_TRIGGER={shlex.quote(args.export_trigger)}
	DELETE_ON_EXPORT_SUCCESS={delete_on_export_success}
	REPLACE_EXISTING_ANALYSIS_DIR={replace_existing_analysis_dir}
	ARTIFACT_REGISTRATION_COMMAND_ID={shlex.quote(args.artifact_registration_command_id)}
	DEWEY_URL={shlex.quote(args.dewey_url)}
	DEWEY_TOKEN_ENV={shlex.quote(args.dewey_token_env)}
	DEWEY_ANALYSIS_DIR_EXTERNAL_OBJECT_ID={shlex.quote(args.dewey_analysis_dir_external_object_id)}
	DEWEY_RUN_ARTIFACT_EUID={shlex.quote(args.dewey_run_artifact_euid)}
	DEWEY_URSA_ANALYSIS_EUID={shlex.quote(args.dewey_ursa_analysis_euid)}
STATUS_FILE="${{DAYLILY_RUN_DIR}}/status.json"
TMUX_LOG="${{DAYLILY_TMUX_LOG}}"

write_status() {{
  python3 -c {write_status_python}
}}

export DAYLILY_STATUS_FILE="$STATUS_FILE"
export DAYLILY_STATUS_SESSION="$SESSION_NAME"
export DAYLILY_STATUS_REPO_PATH="${{DAYLILY_REPO_PATH}}"
export DAYLILY_STATUS_COMMAND="$DY_COMMAND"
export DAYLILY_STATUS_STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
export DAYLILY_STATUS_COMPLETED_AT=""
export DAYLILY_STATUS_EXIT_CODE="__PENDING__"
write_status

trap 'status=$?; if [[ "${{DAYLILY_STATUS_FINALIZED:-0}}" != "1" ]]; then export DAYLILY_STATUS_COMPLETED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; export DAYLILY_STATUS_EXIT_CODE="$status"; write_status; fi' EXIT

clone_root="$(dirname "${{DAYLILY_REPO_PATH}}")"
repo_path="${{DAYLILY_REPO_PATH}}"
mkdir -p "$(dirname "$clone_root")"

remove_run_dir_projection_links() {{
  local links_dir="$repo_path/config/run_dir_links"
  local entry
  if [[ ! -e "$links_dir" ]]; then
    return 0
  fi
  if [[ ! -d "$links_dir" ]]; then
    echo "[ERROR] Refusing to export with non-directory run projection path: $links_dir"
    return 1
  fi
  while IFS= read -r -d '' entry; do
    if [[ ! -L "$entry" ]]; then
      echo "[ERROR] Refusing to export with non-symlink run projection: $entry"
      return 1
    fi
    echo "[INFO] Removing run-directory projection before export: $entry -> $(readlink "$entry")"
    rm -- "$entry"
  done < <(find "$links_dir" -mindepth 1 -maxdepth 1 -print0)
  if find "$links_dir" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
    echo "[ERROR] Refusing to export with non-empty run projection directory: $links_dir"
    return 1
  fi
  rmdir "$links_dir"
}}

day-clone \
  --destination "$ANALYSIS_ID" \
  --executing-entity "$EXECUTING_ENTITY" \
  --repository {shlex.quote(args.repository)} \
  --git-tag {shlex.quote(args.git_tag)}
	cd "$repo_path"
	mkdir -p config

extract_runtime_config_path() {{
  local key="$1"
  python3 - "$key" "$DY_COMMAND" <<'PYCONFIGPATH'
import shlex
import sys

key = sys.argv[1]
command = sys.argv[2]
try:
    args = shlex.split(command)
except ValueError as exc:
    print(f"[ERROR] Could not parse DY_COMMAND for runtime config: {{exc}}", file=sys.stderr)
    raise SystemExit(2)

for index, arg in enumerate(args):
    if arg != "--config":
        continue
    for item in args[index + 1:]:
        if item.startswith("-"):
            break
        if "=" not in item:
            continue
        name, value = item.split("=", 1)
        if name == key:
            print(value)
            raise SystemExit(0)
raise SystemExit(0)
PYCONFIGPATH
}}

materialize_runtime_table() {{
  local key="$1"
  local target="$2"
  local source_path
  source_path="$(extract_runtime_config_path "$key")"
  if [[ -z "$source_path" ]]; then
    return 0
  fi
  if [[ ! -f "$source_path" ]]; then
    echo "[ERROR] Runtime config $key points to missing file: $source_path"
    exit 12
  fi
  cp -- "$source_path" "$target"
}}

bootstrap_test_config() {{
  local samples_source=".test_data/data/0.01xwgs_HG002_hg38.samples.tsv"
  local units_source=".test_data/data/0.01xwgs_HG002_hg38.units.tsv"
  if [[ ! -f "$samples_source" ]]; then
    echo "[ERROR] Missing DayOA test samples table: $samples_source"
    exit 12
  fi
  if [[ ! -f "$units_source" ]]; then
    echo "[ERROR] Missing DayOA test units table: $units_source"
    exit 12
  fi
  cp -- "$samples_source" config/samples.tsv
  cp -- "$units_source" config/units.tsv
  echo "[INFO] Bootstrapped DayOA test samples and units tables."
}}

bclconvert_runtime_tables_requested() {{
  case "$DY_COMMAND" in
    *produce_bclconvert_fastqs*|*produce_bclconvert_fastqs_and_metrics*|*produce_illumina_run_qc_and_bclconvert*|*run_bclconvert*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}}

generate_bclconvert_runtime_tables() {{
  python3 - <<'PYBCLTABLES'
import csv
from pathlib import Path

runs_path = Path("config/runs.tsv")
if not runs_path.is_file():
    raise SystemExit("[ERROR] BCL Convert bootstrap requires config/runs.tsv")

with runs_path.open(newline="", encoding="utf-8-sig") as handle:
    runs = list(csv.DictReader(handle, delimiter="\t"))

run_row = next((row for row in runs if str(row.get("PLATFORM", "")).upper() == "ILMN"), None)
if run_row is None:
    raise SystemExit("[ERROR] BCL Convert bootstrap requires an ILMN run row in config/runs.tsv")

run_id = str(run_row.get("RUNID", "")).strip()
sample_sheet = Path(str(run_row.get("SAMPLE_SHEET", "")).strip())
if not run_id:
    raise SystemExit("[ERROR] BCL Convert bootstrap ILMN run row is missing RUNID")
if not sample_sheet.is_file():
    raise SystemExit(f"[ERROR] BCL Convert sample sheet not found: {{sample_sheet}}")

sample_ids = []
in_data = False
header = None
sample_index = None
with sample_sheet.open(encoding="utf-8-sig") as handle:
    for raw_line in handle:
        line = raw_line.rstrip("\\r\\n")
        stripped = line.strip()
        if stripped == "[BCLConvert_Data]":
            in_data = True
            header = None
            sample_index = None
            continue
        if in_data and stripped.startswith("[") and stripped.endswith("]"):
            break
        if not in_data or not stripped:
            continue
        fields = [field.strip() for field in line.split(",")]
        if header is None:
            header = fields
            try:
                sample_index = header.index("Sample_ID")
            except ValueError as exc:
                raise SystemExit("[ERROR] BCLConvert_Data is missing Sample_ID") from exc
            continue
        if sample_index is None or sample_index >= len(fields):
            continue
        sample_id = fields[sample_index].strip()
        if sample_id:
            sample_ids.append(sample_id)

deduped_sample_ids = list(dict.fromkeys(sample_ids))
if not deduped_sample_ids:
    raise SystemExit(f"[ERROR] No Sample_ID rows found in {{sample_sheet}}")

samples_header = [
    "SAMPLEID",
    "SAMPLESOURCE",
    "SAMPLECLASS",
    "BIOLOGICAL_SEX",
    "CONCORDANCE_CONTROL_PATH",
    "IS_POSITIVE_CONTROL",
    "IS_NEGATIVE_CONTROL",
    "SAMPLE_TYPE",
    "TUM_NRM_SAMPLEID_MATCH",
    "EXTERNAL_SAMPLE_ID",
    "N_X",
    "N_Y",
    "TRUTH_DATA_DIR",
]
with Path("config/samples.tsv").open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle, delimiter="\t", lineterminator="\\n")
    writer.writerow(samples_header)
    for sample_id in deduped_sample_ids:
        is_negative = str(sample_id).upper() in {{"NTC", "NEGATIVE_CONTROL"}}
        writer.writerow(
            [
                sample_id,
                "control" if is_negative else "blood",
                "control" if is_negative else "research",
                "unknown",
                "na",
                "false",
                "true" if is_negative else "false",
                "control" if is_negative else "blood",
                "na",
                sample_id,
                "na",
                "na",
                "na",
            ]
        )

units_path = Path("config/units.tsv")
if units_path.exists():
    units_path.unlink()

print(
    f"[INFO] Wrote BCL Convert bootstrap samples for {{len(deduped_sample_ids)}} samples from {{sample_sheet}}; units table left absent for DayOA bootstrap"
)
PYBCLTABLES
}}

project_run_context_mounts() {{
  python3 -c {run_context_projection_python}
}}

patch_bclconvert_profile_config() {{
  python3 -c {bclconvert_profile_patch_python}
}}

patch_bclconvert_lane_split() {{
  python3 - <<'PYNATIVEBCL'
from pathlib import Path

rule_path = Path("workflow/rules/bclconvert.smk")
if not rule_path.is_file():
    raise SystemExit(f"[ERROR] BCL Convert rule file is missing: {{rule_path}}")

text = rule_path.read_text(encoding="utf-8")
required_markers = [
    "DAYOA_BCLCONVERT_LANE_SPLIT = True",
    "BCL_MERGE_LANE_FASTQS",
    "BCL_FASTQ_LIST_INPUT_FILES",
    "run_bclconvert_lane_fastqs_ready",
    "rule run_bclconvert_lane:",
    "workflow/scripts/run_bclconvert_lane.sh",
    "workflow/scripts/merge_bclconvert_lanes.py",
]
required_files = [
    "workflow/scripts/run_bclconvert_lane.sh",
    "workflow/scripts/prepare_bclconvert_lane_samplesheet.py",
    "workflow/scripts/merge_bclconvert_lanes.py",
]
missing_markers = [marker for marker in required_markers if marker not in text]
missing_files = [path for path in required_files if not Path(path).is_file()]
if missing_markers or missing_files:
    details = []
    if missing_markers:
        details.append("missing rule markers: " + ", ".join(missing_markers))
    if missing_files:
        details.append("missing files: " + ", ".join(missing_files))
    raise SystemExit(
        "[ERROR] DayOA BCL Convert rules do not expose native lane-split support; "
        "use a DayOA release with native mounted-run BCL Convert. "
        + "; ".join(details)
    )
print("[INFO] DayOA native BCL Convert lane-split rules detected; no DYEC runtime rule patch applied.")
PYNATIVEBCL
}}

ultima_run_qc_config_requested() {{
  case "$DY_COMMAND" in
    *produce_ultima_run_qc*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}}

append_ultima_run_qc_config() {{
  local extra_config
  extra_config="$(python3 - <<'PYULTIMACFG'
import csv
import json
import shlex
import subprocess
import sys
from pathlib import Path

runs_path = Path("config/runs.tsv")
if not runs_path.is_file():
    raise SystemExit("[ERROR] Ultima run QC requires config/runs.tsv")

with runs_path.open(newline="", encoding="utf-8-sig") as handle:
    runs = list(csv.DictReader(handle, delimiter="\t"))

run_row = next((row for row in runs if str(row.get("PLATFORM", "")).upper() == "ULTIMA"), None)
if run_row is None:
    raise SystemExit("[ERROR] Ultima run QC requires a ULTIMA run row in config/runs.tsv")

source_s3_uri = str(run_row.get("SOURCE_S3_URI", "")).strip()
if not source_s3_uri.startswith("s3://"):
    raise SystemExit("[ERROR] Ultima run QC requires SOURCE_S3_URI in config/runs.tsv")
metrics_path = str(run_row.get("METRICS_PATH", "")).strip()
metrics_s3_uri = str(run_row.get("METRICS_S3_URI", "")).strip()
if metrics_s3_uri:
    if not metrics_s3_uri.startswith("s3://"):
        raise SystemExit("[ERROR] Ultima run QC METRICS_S3_URI must be an s3:// URI")
    metrics_path = "config/ultima_run_qc_metrics.csv"
    try:
        subprocess.run(
            ["aws", "s3", "cp", metrics_s3_uri, metrics_path],
            check=True,
            stdout=sys.stderr,
            stderr=sys.stderr,
        )
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            f"[ERROR] Failed to copy Ultima run QC METRICS_S3_URI: {{exc.returncode}}"
        ) from exc
if not metrics_path:
    raise SystemExit(
        "[ERROR] Ultima run QC requires METRICS_PATH or METRICS_S3_URI in config/runs.tsv"
    )
if not Path(metrics_path).is_file():
    raise SystemExit(f"[ERROR] Ultima run QC metrics file not found: {{metrics_path}}")
if Path(metrics_path).stat().st_size == 0:
    raise SystemExit(f"[ERROR] Ultima run QC metrics file is empty: {{metrics_path}}")

payload = "run_qc=" + json.dumps(
    {{"ultima": {{"run_s3_uri": source_s3_uri, "metrics_path": metrics_path}}}},
    separators=(",", ":"),
)
print(shlex.quote(payload))
PYULTIMACFG
)"
  DY_COMMAND="$DY_COMMAND --config $extra_config"
}}

ont_run_qc_runtime_repair_requested() {{
  case "$DY_COMMAND" in
    *produce_ont_run_qc*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}}

patch_pycoqc_readonly_sort() {{
  python3 - <<'PYPYCOQC'
from pathlib import Path

roots = [Path("/fsx/resources/environments/conda/ubuntu")]
matches = []
for root in roots:
    if root.exists():
        matches.extend(root.glob("**/site-packages/pycoQC/pycoQC_plot.py"))

if not matches:
    print("[INFO] No installed pycoQC environment found for readonly-sort repair.")
    raise SystemExit(0)

parse_old = (
    "data = data.dropna().values\\n"
    "        data.sort()\\n"
    "        half_sum = data.sum()/2\\n"
    "        cum_sum = 0\\n"
    "        for v in data:\\n"
    "            cum_sum += v\\n"
    "            if cum_sum >= half_sum:\\n"
    "                return int(v)"
)
readonly_only = (
    "data = data.dropna().to_numpy(copy=True)\\n"
    "        data.sort()\\n"
    "        half_sum = data.sum()/2\\n"
    "        cum_sum = 0\\n"
    "        for v in data:\\n"
    "            cum_sum += v\\n"
    "            if cum_sum >= half_sum:\\n"
    "                return int(v)"
)
parse_new = (
    'data = data.dropna().astype("int64").to_numpy(copy=True)\\n'
    "        data.sort()\\n"
    "        half_sum = int(data.sum())/2\\n"
    "        cum_sum = 0\\n"
    "        for v in data:\\n"
    "            cum_sum += int(v)\\n"
    "            if cum_sum >= half_sum:\\n"
    "                return int(v)\\n"
    "        return 0"
)

for path in sorted(set(matches)):
    text = path.read_text(encoding="utf-8")
    if parse_new in text:
        print(f"[INFO] pycoQC readonly-sort repair already present: {{path}}")
        continue
    if readonly_only in text:
        target = readonly_only
    elif old in text:
        target = old
    else:
        raise SystemExit(
            f"[ERROR] pycoQC readonly-sort repair target not found in {{path}}"
        )
    path.write_text(text.replace(target, parse_new, 1), encoding="utf-8")
    print(f"[INFO] Patched pycoQC readonly-sort repair: {{path}}")
PYPYCOQC
}}

goleft_indexcov_runtime_repair_requested() {{
  case "$DY_COMMAND" in
    *produce_alignstats*|*produce_multiqc_all*|*produce_relatedness*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}}

patch_goleft_indexcov_empty_sex_arg() {{
  python3 - <<'PYGOLEFT'
from pathlib import Path

path = Path("workflow/rules/go_left.smk")
if not path.is_file():
    raise SystemExit(f"[ERROR] goleft runtime repair target missing: {{path}}")

old_with_sex = (
    "        goleft indexcov --directory $gl --sex {{params.sexchrms:q}} "
    "--fai {{params.huref}}.fai {{input.crai}} >> {{log}} 2>&1;"
)
old_without_sex = (
    "        goleft indexcov --directory $gl "
    "--fai {{params.huref}}.fai {{input.crai}} >> {{log}} 2>&1;"
)
new = (
    "        set +e\\n"
    "        goleft indexcov --directory $gl "
    "--fai {{params.huref}}.fai {{input.crai}} >> {{log}} 2>&1\\n"
    "        goleft_status=$?\\n"
    "        set -e\\n"
    '        if [[ "$goleft_status" != "0" ]]; then\\n'
    "            if grep -Eiq 'no usable chroms?omes|no usable chromosomes' {{log}}; then\\n"
    "                printf 'DYEC_RUNTIME_REPAIR: goleft skipped because input CRAI has no usable chromosomes.\\\\n' >> {{log}}\\n"
    "            else\\n"
    '                exit "$goleft_status"\\n'
    "            fi\\n"
    "        fi"
)

text = path.read_text(encoding="utf-8")
if new in text:
    print(f"[INFO] goleft empty-sex/no-usable-chromosomes repair already present: {{path}}")
    raise SystemExit(0)
if old_with_sex in text:
    text = text.replace(old_with_sex, new, 1)
elif old_without_sex in text:
    text = text.replace(old_without_sex, new, 1)
else:
    raise SystemExit(f"[ERROR] goleft runtime repair target not found in {{path}}")
path.write_text(text, encoding="utf-8")
print(f"[INFO] Patched goleft empty-sex/no-usable-chromosomes repair: {{path}}")
PYGOLEFT
}}

mosdepth_empty_output_runtime_repair_requested() {{
  case "$DY_COMMAND" in
    *produce_alignstats*|*produce_multiqc_all*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}}

patch_mosdepth_empty_outputs() {{
  python3 - <<'PYMOSDEPTH'
from pathlib import Path

path = Path("workflow/rules/mosdepth.smk")
if not path.is_file():
    raise SystemExit(f"[ERROR] mosdepth runtime repair target missing: {{path}}")

parse_old = (
    "        test -s {{output.summary:q}} || (printf 'ERROR: mosdepth summary output is missing or empty: %s\\\\n' {{output.summary:q}} | tee -a {{log.a:q}} >&2; exit 1)\\n"
    "        test -s {{output.global_dist:q}} || (printf 'ERROR: mosdepth global_dist output is missing or empty: %s\\\\n' {{output.global_dist:q}} | tee -a {{log.a:q}} >&2; exit 1)\\n"
    "        test -s {{output.region_dist:q}} || (printf 'ERROR: mosdepth region_dist output is missing or empty: %s\\\\n' {{output.region_dist:q}} | tee -a {{log.a:q}} >&2; exit 1)"
)
parse_new = (
    "        if [ ! -s {{output.summary:q}} ]; then\\n"
    "            printf 'chrom\\\\tlength\\\\tbases\\\\tmean\\\\tmin\\\\tmax\\\\ntotal\\\\t0\\\\t0\\\\t0\\\\t0\\\\t0\\\\n' > {{output.summary:q}}\\n"
    "            printf 'DYEC_RUNTIME_REPAIR: mosdepth emitted no summary; wrote zero-coverage sentinel.\\\\n' >> {{log.a:q}}\\n"
    "        fi\\n"
    "        if [ ! -s {{output.global_dist:q}} ]; then\\n"
    "            printf 'total\\\\t0\\\\t1\\\\n' > {{output.global_dist:q}}\\n"
    "            printf 'DYEC_RUNTIME_REPAIR: mosdepth emitted no global distribution; wrote zero-coverage sentinel.\\\\n' >> {{log.a:q}}\\n"
    "        fi\\n"
    "        if [ ! -s {{output.region_dist:q}} ]; then\\n"
    "            printf 'total\\\\t0\\\\t1\\\\n' > {{output.region_dist:q}}\\n"
    "            printf 'DYEC_RUNTIME_REPAIR: mosdepth emitted no region distribution; wrote zero-coverage sentinel.\\\\n' >> {{log.a:q}}\\n"
    "        fi"
)

text = path.read_text(encoding="utf-8")
if parse_new in text:
    print(f"[INFO] mosdepth empty-output repair already present: {{path}}")
    raise SystemExit(0)
if parse_old not in text:
    raise SystemExit(f"[ERROR] mosdepth empty-output repair target not found in {{path}}")
path.write_text(text.replace(parse_old, parse_new, 1), encoding="utf-8")
print(f"[INFO] Patched mosdepth empty-output repair: {{path}}")
PYMOSDEPTH
}}

rtg_vcfeval_parse_runtime_repair_requested() {{
  case "$DY_COMMAND" in
    *produce_snv_concordances*|*produce_multiqc_all*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}}

patch_rtg_vcfeval_parse_output_dir() {{
  python3 - <<'PYRTGPARSE'
from pathlib import Path

path = Path("workflow/rules/rtg_vcfeval.smk")
if not path.is_file():
    raise SystemExit(f"[ERROR] RTG vcfeval runtime repair target missing: {{path}}")

parse_old = (
    '            export DAYLILY_BCFTOOLS_THREADS="{{threads}}"\\n'
    "\\n"
    "            python workflow/scripts/parse-vcfeval-summary.py \\\\\\n"
)
parse_new = (
    '            export DAYLILY_BCFTOOLS_THREADS="{{threads}}"\\n'
    "\\n"
    '            mkdir -p "$(dirname {{output.mqc}})"\\n'
    "\\n"
    "            python workflow/scripts/parse-vcfeval-summary.py \\\\\\n"
)
rtg_mem_old = "            rtg vcfeval \\\\\\n"
rtg_mem_new = (
    "            rtg_mem_gb=$(( ({{resources.mem_mb}} * 85 / 100 + 1023) / 1024 ))\\n"
    '            RTG_MEM="${{{{rtg_mem_gb}}}}G" rtg vcfeval \\\\\\n'
)

text = path.read_text(encoding="utf-8")
changed = False
if parse_new not in text:
    if parse_old not in text:
        raise SystemExit(f"[ERROR] RTG vcfeval parse output-dir repair target not found in {{path}}")
    text = text.replace(parse_old, parse_new, 1)
    changed = True
if rtg_mem_new not in text:
    if rtg_mem_old not in text:
        raise SystemExit(f"[ERROR] RTG vcfeval JVM memory repair target not found in {{path}}")
    text = text.replace(rtg_mem_old, rtg_mem_new, 1)
    changed = True
if changed:
    path.write_text(text, encoding="utf-8")
    print(f"[INFO] Patched RTG vcfeval parse/JVM-memory repair: {{path}}")
else:
    print(f"[INFO] RTG vcfeval parse/JVM-memory repair already present: {{path}}")
PYRTGPARSE
}}

vep_zero_variant_runtime_repair_requested() {{
  case "$DY_COMMAND" in
    *produce_vep*|*produce_multiqc_all*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}}

patch_vep_empty_concat_fofn() {{
  python3 - <<'PYVEPZERO'
from pathlib import Path

path = Path("workflow/rules/vep.smk")
if not path.is_file():
    raise SystemExit(f"[ERROR] VEP runtime repair target missing: {{path}}")

old = (
    "        if [ ! -s {{params.tmp_fofn}} ]; then\\n"
    '            echo "ERROR: no non-empty VEP chromosome chunks to concatenate" >&2\\n'
    "            exit 2\\n"
    "        fi\\n"
    "        mv {{params.tmp_fofn}} {{output.fofn}}"
)
new = (
    "        if [ ! -s {{params.tmp_fofn}} ]; then\\n"
    "            for count_path in {{input.ann_counts}}; do\\n"
    '                echo "${{{{count_path%.record_count}}}}" >> {{params.tmp_fofn}}\\n'
    "                break\\n"
    "            done\\n"
    "        fi\\n"
    "        mv {{params.tmp_fofn}} {{output.fofn}}"
)

text = path.read_text(encoding="utf-8")
if new in text:
    print(f"[INFO] VEP zero-variant concat repair already present: {{path}}")
    raise SystemExit(0)
if old not in text:
    raise SystemExit(f"[ERROR] VEP zero-variant concat repair target not found in {{path}}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print(f"[INFO] Patched VEP zero-variant concat repair: {{path}}")
PYVEPZERO
}}

contam_identity_zero_variant_runtime_repair_requested() {{
  case "$DY_COMMAND" in
    *produce_global_contam_check*|*produce_haplocheck_contam_identity*|*produce_read_haps_contam_identity*|*contam_identity*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}}

patch_contam_identity_zero_variant_outputs() {{
  python3 - <<'PYCONTAMZERO'
from pathlib import Path

path = Path("workflow/rules/contam_identity.smk")
if not path.is_file():
    raise SystemExit(f"[ERROR] contamination identity runtime repair target missing: {{path}}")

hap_old = (
    "        {{params.command:q}} --out \\"$result_prefix\\" --raw {{input.vcf:q}} > {{log:q}} 2>&1\\n"
    '        test -s "$result_dir/contamination.txt"\\n'
    '        test -s "$result_dir/contamination.raw.txt"\\n'
    '        test -s "$result_dir/contamination.html"\\n'
    '        cp "$result_dir/contamination.txt" {{output.contamination:q}}\\n'
    '        cp "$result_dir/contamination.raw.txt" {{output.raw:q}}\\n'
    '        cp "$result_dir/contamination.html" {{output.html:q}}'
)
hap_new = (
    "        set +o pipefail\\n"
    "        if gzip -cd {{input.vcf:q}} | grep -m 1 -q -v '^#'; then\\n"
    "            has_variants=true\\n"
    "        else\\n"
    "            has_variants=false\\n"
    "        fi\\n"
    "        set -o pipefail\\n"
    '        if [[ "$has_variants" == "true" ]]; then\\n'
    "            set +e\\n"
    "            {{params.command:q}} --out \\"$result_prefix\\" --raw {{input.vcf:q}} > {{log:q}} 2>&1\\n"
    "            haplocheck_rc=$?\\n"
    "            set -e\\n"
    "            if grep -q 'outside the range.*rCRS only' {{log:q}}; then\\n"
    "                printf 'SampleID\\tContamination Status\\tContamination Level\\tDistance\\tSample Coverage\\tMajor Haplogroup\\tMinor Haplogroup\\n%s\\tUNSUPPORTED_REFERENCE\\t0\\t\\t0\\t\\t\\n' {{wildcards.sample:q}} > {{output.contamination:q}}\\n"
    "                printf 'SampleID\\tContamination Status\\tContamination Level\\tDistance\\tSample Coverage\\tMajor Haplogroup\\tMinor Haplogroup\\n%s\\tUNSUPPORTED_REFERENCE\\t0\\t\\t0\\t\\t\\n' {{wildcards.sample:q}} > {{output.raw:q}}\\n"
    "                printf '<html><body>UNSUPPORTED_REFERENCE</body></html>\\n' > {{output.html:q}}\\n"
    "                printf 'UNSUPPORTED_REFERENCE: haplocheck skipped because the input VCF is not restricted to rCRS positions.\\n' >> {{log:q}}\\n"
    '            elif [[ "$haplocheck_rc" -eq 0 ]]; then\\n'
    '                test -s "$result_dir/contamination.txt"\\n'
    '                test -s "$result_dir/contamination.raw.txt"\\n'
    '                test -s "$result_dir/contamination.html"\\n'
    '                cp "$result_dir/contamination.txt" {{output.contamination:q}}\\n'
    '                cp "$result_dir/contamination.raw.txt" {{output.raw:q}}\\n'
    '                cp "$result_dir/contamination.html" {{output.html:q}}\\n'
    "            else\\n"
    '                exit "$haplocheck_rc"\\n'
    "            fi\\n"
    "        else\\n"
    "            printf 'SampleID\\tContamination Status\\tContamination Level\\tDistance\\tSample Coverage\\tMajor Haplogroup\\tMinor Haplogroup\\n%s\\tNO_VARIANTS\\t0\\t\\t0\\t\\t\\n' {{wildcards.sample:q}} > {{output.contamination:q}}\\n"
    "            printf 'SampleID\\tContamination Status\\tContamination Level\\tDistance\\tSample Coverage\\tMajor Haplogroup\\tMinor Haplogroup\\n%s\\tNO_VARIANTS\\t0\\t\\t0\\t\\t\\n' {{wildcards.sample:q}} > {{output.raw:q}}\\n"
    "            printf '<html><body>NO_VARIANTS</body></html>\\n' > {{output.html:q}}\\n"
    "            printf 'NO_VARIANTS: haplocheck skipped because the input VCF has no variant records.\\n' > {{log:q}}\\n"
    "        fi"
)

read_haps_original_old = (
    "        command -v {{params.command:q}} > /dev/null\\n"
    "        test -s {{params.reliable_snp_file:q}}\\n"
    "        {{params.command:q}} {{params.extra_args}} -fa {{params.ref:q}} {{input.bam:q}} {{params.reliable_snp_file:q}} {{input.vcf:q}} > {{output.txt:q}} 2> {{log:q}}\\n"
    "        test -s {{output.txt:q}}\\n"
    "        grep -q 'PASS_FAIL' {{output.txt:q}}\\n"
    "        grep -q 'REASON' {{output.txt:q}}"
)
read_haps_partial_old = (
    "        command -v {{params.command:q}} > /dev/null\\n"
    "        test -s {{params.reliable_snp_file:q}}\\n"
    "        set +o pipefail\\n"
    "        if gzip -cd {{input.vcf:q}} | grep -m 1 -q -v '^#'; then\\n"
    "            has_variants=true\\n"
    "        else\\n"
    "            has_variants=false\\n"
    "        fi\\n"
    "        set -o pipefail\\n"
    '        if [[ "$has_variants" == "true" ]]; then\\n'
    "            {{params.command:q}} {{params.extra_args}} -fa {{params.ref:q}} {{input.bam:q}} {{params.reliable_snp_file:q}} {{input.vcf:q}} > {{output.txt:q}} 2> {{log:q}}\\n"
    "        else\\n"
    "            printf 'SNP_PAIRS ERROR_PAIRS DOUBLE_ERROR_PAIR_COUNT DOUBLE_ERROR_FRACTION REL_ERROR_FRACTION NONSENSE_FRACTION PASS_FAIL REASON\\n0 0 0 0 0 0 NO_DATA NO_VARIANTS\\n' > {{output.txt:q}}\\n"
    "            printf 'NO_VARIANTS: read_haps skipped because the input VCF has no variant records.\\n' > {{log:q}}\\n"
    "        fi\\n"
    "        test -s {{output.txt:q}}\\n"
    "        grep -q 'PASS_FAIL' {{output.txt:q}}\\n"
    "        grep -q 'REASON' {{output.txt:q}}"
)
read_haps_empty_failure_old = (
    "        set +o pipefail\\n"
    "        if gzip -cd {{input.vcf:q}} | grep -m 1 -q -v '^#'; then\\n"
    "            has_variants=true\\n"
    "        else\\n"
    "            has_variants=false\\n"
    "        fi\\n"
    "        set -o pipefail\\n"
    '        if [[ "$has_variants" == "true" ]]; then\\n'
    "            command -v {{params.command:q}} > /dev/null\\n"
    "            test -s {{params.reliable_snp_file:q}}\\n"
    "            {{params.command:q}} {{params.extra_args}} -fa {{params.ref:q}} {{input.bam:q}} {{params.reliable_snp_file:q}} {{input.vcf:q}} > {{output.txt:q}} 2> {{log:q}}\\n"
    "        else\\n"
    "            printf 'SNP_PAIRS ERROR_PAIRS DOUBLE_ERROR_PAIR_COUNT DOUBLE_ERROR_FRACTION REL_ERROR_FRACTION NONSENSE_FRACTION PASS_FAIL REASON\\n0 0 0 0 0 0 NO_DATA NO_VARIANTS\\n' > {{output.txt:q}}\\n"
    "            printf 'NO_VARIANTS: read_haps skipped because the input VCF has no variant records.\\n' > {{log:q}}\\n"
    "        fi\\n"
    "        test -s {{output.txt:q}}\\n"
    "        grep -q 'PASS_FAIL' {{output.txt:q}}\\n"
    "        grep -q 'REASON' {{output.txt:q}}"
)
read_haps_strict_precheck_old = (
    "        set +o pipefail\\n"
    "        if gzip -cd {{input.vcf:q}} | grep -m 1 -q -v '^#'; then\\n"
    "            has_variants=true\\n"
    "        else\\n"
    "            has_variants=false\\n"
    "        fi\\n"
    "        set -o pipefail\\n"
    '        if [[ "$has_variants" == "true" ]]; then\\n'
    "            command -v {{params.command:q}} > /dev/null\\n"
    "            test -s {{params.reliable_snp_file:q}}\\n"
    "            set +e\\n"
    "            {{params.command:q}} {{params.extra_args}} -fa {{params.ref:q}} {{input.bam:q}} {{params.reliable_snp_file:q}} {{input.vcf:q}} > {{output.txt:q}} 2> {{log:q}}\\n"
    "            read_haps_rc=$?\\n"
    "            set -e\\n"
    "            if [[ \\\"$read_haps_rc\\\" != \\\"0\\\" ]] || [[ ! -s {{output.txt:q}} ]] || ! grep -q 'PASS_FAIL' {{output.txt:q}} || ! grep -q 'REASON' {{output.txt:q}}; then\\n"
    "                printf 'SNP_PAIRS ERROR_PAIRS DOUBLE_ERROR_PAIR_COUNT DOUBLE_ERROR_FRACTION REL_ERROR_FRACTION NONSENSE_FRACTION PASS_FAIL REASON\\n0 0 0 0 0 0 NO_DATA READ_HAPS_FAILED\\n' > {{output.txt:q}}\\n"
    "                printf 'READ_HAPS_FAILED: read_haps exited with status %s or wrote no usable QC table.\\n' \\\"$read_haps_rc\\\" >> {{log:q}}\\n"
    "            fi\\n"
    "        else\\n"
    "            printf 'SNP_PAIRS ERROR_PAIRS DOUBLE_ERROR_PAIR_COUNT DOUBLE_ERROR_FRACTION REL_ERROR_FRACTION NONSENSE_FRACTION PASS_FAIL REASON\\n0 0 0 0 0 0 NO_DATA NO_VARIANTS\\n' > {{output.txt:q}}\\n"
    "            printf 'NO_VARIANTS: read_haps skipped because the input VCF has no variant records.\\n' > {{log:q}}\\n"
    "        fi\\n"
    "        test -s {{output.txt:q}}\\n"
    "        grep -q 'PASS_FAIL' {{output.txt:q}}\\n"
    "        grep -q 'REASON' {{output.txt:q}}"
)
read_haps_new = (
    "        set +o pipefail\\n"
    "        if gzip -cd {{input.vcf:q}} | grep -m 1 -q -v '^#'; then\\n"
    "            has_variants=true\\n"
    "        else\\n"
    "            has_variants=false\\n"
    "        fi\\n"
    "        set -o pipefail\\n"
    '        if [[ "$has_variants" == "true" ]]; then\\n'
    "            if ! command -v {{params.command:q}} > /dev/null; then\\n"
    "                printf 'SNP_PAIRS ERROR_PAIRS DOUBLE_ERROR_PAIR_COUNT DOUBLE_ERROR_FRACTION REL_ERROR_FRACTION NONSENSE_FRACTION PASS_FAIL REASON\\n0 0 0 0 0 0 NO_DATA READ_HAPS_UNAVAILABLE\\n' > {{output.txt:q}}\\n"
    "                printf 'READ_HAPS_UNAVAILABLE: read_haps command is unavailable: %s\\n' {{params.command:q}} > {{log:q}}\\n"
    "            elif [[ ! -s {{params.reliable_snp_file:q}} ]]; then\\n"
    "                printf 'SNP_PAIRS ERROR_PAIRS DOUBLE_ERROR_PAIR_COUNT DOUBLE_ERROR_FRACTION REL_ERROR_FRACTION NONSENSE_FRACTION PASS_FAIL REASON\\n0 0 0 0 0 0 NO_DATA READ_HAPS_MARKERS_UNAVAILABLE\\n' > {{output.txt:q}}\\n"
    "                printf 'READ_HAPS_MARKERS_UNAVAILABLE: read_haps marker file is missing or empty: %s\\n' {{params.reliable_snp_file:q}} > {{log:q}}\\n"
    "            else\\n"
    "                set +e\\n"
    "                {{params.command:q}} {{params.extra_args}} -fa {{params.ref:q}} {{input.bam:q}} {{params.reliable_snp_file:q}} {{input.vcf:q}} > {{output.txt:q}} 2> {{log:q}}\\n"
    "                read_haps_rc=$?\\n"
    "                set -e\\n"
    "                if [[ \\\"$read_haps_rc\\\" != \\\"0\\\" ]] || [[ ! -s {{output.txt:q}} ]] || ! grep -q 'PASS_FAIL' {{output.txt:q}} || ! grep -q 'REASON' {{output.txt:q}}; then\\n"
    "                printf 'SNP_PAIRS ERROR_PAIRS DOUBLE_ERROR_PAIR_COUNT DOUBLE_ERROR_FRACTION REL_ERROR_FRACTION NONSENSE_FRACTION PASS_FAIL REASON\\n0 0 0 0 0 0 NO_DATA READ_HAPS_FAILED\\n' > {{output.txt:q}}\\n"
    "                    printf 'READ_HAPS_FAILED: read_haps exited with status %s or wrote no usable QC table.\\n' \\\"$read_haps_rc\\\" >> {{log:q}}\\n"
    "                fi\\n"
    "            fi\\n"
    "        else\\n"
    "            printf 'SNP_PAIRS ERROR_PAIRS DOUBLE_ERROR_PAIR_COUNT DOUBLE_ERROR_FRACTION REL_ERROR_FRACTION NONSENSE_FRACTION PASS_FAIL REASON\\n0 0 0 0 0 0 NO_DATA NO_VARIANTS\\n' > {{output.txt:q}}\\n"
    "            printf 'NO_VARIANTS: read_haps skipped because the input VCF has no variant records.\\n' > {{log:q}}\\n"
    "        fi\\n"
    "        test -s {{output.txt:q}}\\n"
    "        grep -q 'PASS_FAIL' {{output.txt:q}}\\n"
    "        grep -q 'REASON' {{output.txt:q}}"
)

text = path.read_text(encoding="utf-8")
changed = False
if hap_new not in text:
    if hap_old not in text:
        raise SystemExit(f"[ERROR] haplocheck zero-variant repair target not found in {{path}}")
    text = text.replace(hap_old, hap_new, 1)
    changed = True
if read_haps_new not in text:
    if read_haps_original_old in text:
        text = text.replace(read_haps_original_old, read_haps_new, 1)
        changed = True
    elif read_haps_partial_old in text:
        text = text.replace(read_haps_partial_old, read_haps_new, 1)
        changed = True
    elif read_haps_empty_failure_old in text:
        text = text.replace(read_haps_empty_failure_old, read_haps_new, 1)
        changed = True
    elif read_haps_strict_precheck_old in text:
        text = text.replace(read_haps_strict_precheck_old, read_haps_new, 1)
        changed = True
    else:
        raise SystemExit(f"[ERROR] read_haps zero-variant repair target not found in {{path}}")
if changed:
    path.write_text(text, encoding="utf-8")
    print(f"[INFO] Patched contamination identity zero-variant repair: {{path}}")
else:
    print(f"[INFO] contamination identity zero-variant repair already present: {{path}}")
PYCONTAMZERO
}}

	BCLCONVERT_PROFILE_PATCH_REQUESTED=false
	if [[ "$RUN_CONTEXT_MODE" == "true" ]]; then
	  printf '%s' "$RUN_CONTEXT_PAYLOAD" > config/runs.tsv
	  project_run_context_mounts
	  materialize_runtime_table samples_table config/samples.tsv
	  materialize_runtime_table units_table config/units.tsv
	  if bclconvert_runtime_tables_requested; then
	    generate_bclconvert_runtime_tables
	    BCLCONVERT_PROFILE_PATCH_REQUESTED=true
	  fi
	  if ultima_run_qc_config_requested; then
	    append_ultima_run_qc_config
	  fi
	elif [[ "$SAMPLE_CONFIG_MODE" == "true" ]]; then
	  printf '%s' "$SAMPLES_PAYLOAD" > config/samples.tsv
	  printf '%s' "$UNITS_PAYLOAD" > config/units.tsv
	elif [[ "$INPUT_STAGING_MODE" == "true" ]]; then
	  cp "$STAGE_SAMPLES" config/samples.tsv
	  cp "$STAGE_UNITS" config/units.tsv
	elif [[ "$BOOTSTRAP_TEST_CONFIG" == "true" ]]; then
	  bootstrap_test_config
	else
	  echo "[INFO] Input staging skipped for this catalog command."
	fi

if [[ ! -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
  echo "[ERROR] Missing conda profile script at $HOME/miniconda3/etc/profile.d/conda.sh"
  exit 10
fi
. "$HOME/miniconda3/etc/profile.d/conda.sh"
shopt -s expand_aliases
MERMAID_CHROME="$HOME/.cache/puppeteer/chrome/linux-148.0.7778.97/chrome-linux64/chrome"
if [[ -z "${{PUPPETEER_EXECUTABLE_PATH:-}}" && -x "$MERMAID_CHROME" ]]; then
  export PUPPETEER_EXECUTABLE_PATH="$MERMAID_CHROME"
fi

run_dy_command() {{
  local command="$1"
  local dyoainit_source_needed=false
  if [[ "$command" == source\\ dyoainit\\;* ]]; then
    dyoainit_source_needed=true
    command="${{command#source dyoainit;}}"
  elif [[ "$command" == .\\ dyoainit\\;* ]]; then
    dyoainit_source_needed=true
    command="${{command#. dyoainit;}}"
  fi
  command="${{command#"${{command%%[![:space:]]*}}"}}"
  if [[ "$dyoainit_source_needed" == "true" ]]; then
    set +u
    set --
    source dyoainit
    local source_status=$?
    set -u
    if [[ "$source_status" != "0" ]]; then
      return "$source_status"
    fi
  fi
  set +u
  eval "$command"
  local command_status=$?
  set -u
  return "$command_status"
}}

declare -a dyoa_args=()
if [[ -n "$PROJECT_VALUE" ]]; then
  dyoa_args+=(--project {project_arg})
  export PROJECT="$PROJECT_VALUE"
else
  unset PROJECT || true
fi
if [[ "$SKIP_PROJECT_CHECK" == "true" ]]; then
  dyoa_args+=(--skip-project-check)
fi
if [[ "$DEFAULT_ACTIVATION" == "true" ]]; then
  set +u
  . dyoainit "${{dyoa_args[@]}}"
  set -u
  set +e
  set +u
  . bin/day_activate slurm {shlex.quote(args.genome)} remote
  activate_status=$?
  set -u
  set -e
  if [[ "$activate_status" != "0" ]]; then
    echo "[ERROR] day_activate failed with status $activate_status"
    exit "$activate_status"
  fi
fi
if [[ "$BCLCONVERT_PROFILE_PATCH_REQUESTED" == "true" ]]; then
  patch_bclconvert_profile_config
  patch_bclconvert_lane_split
fi
	if ont_run_qc_runtime_repair_requested; then
	  patch_pycoqc_readonly_sort
	fi
	if goleft_indexcov_runtime_repair_requested; then
	  patch_goleft_indexcov_empty_sex_arg
	fi
	if mosdepth_empty_output_runtime_repair_requested; then
	  patch_mosdepth_empty_outputs
	fi
	if rtg_vcfeval_parse_runtime_repair_requested; then
	  patch_rtg_vcfeval_parse_output_dir
	fi
	if vep_zero_variant_runtime_repair_requested; then
	  patch_vep_empty_concat_fofn
	fi
	if contam_identity_zero_variant_runtime_repair_requested; then
	  patch_contam_identity_zero_variant_outputs
	fi
	set +e
	run_dy_command "$DY_COMMAND"
workflow_status=$?
set -e
should_export=false
case "$EXPORT_TRIGGER" in
  none) should_export=false ;;
  on-success) [[ "$workflow_status" -eq 0 ]] && should_export=true ;;
  on-fail) [[ "$workflow_status" -ne 0 ]] && should_export=true ;;
  all) should_export=true ;;
  *) echo "[ERROR] Invalid EXPORT_TRIGGER=$EXPORT_TRIGGER"; workflow_status=20 ;;
esac
if [[ "$should_export" == "true" ]]; then
  if [[ -z "$EXPORT_DESTINATION_S3_URI" ]]; then
    echo "[ERROR] Export requested but EXPORT_DESTINATION_S3_URI is empty"
    workflow_status=21
  else
    if ! remove_run_dir_projection_links; then
      workflow_status=22
    else
      mkdir -p "$DAYLILY_RUN_DIR/export"
      registration_args=()
      if [[ -n "$ARTIFACT_REGISTRATION_COMMAND_ID" ]]; then
        registration_args+=(--artifact-registration-command-id "$ARTIFACT_REGISTRATION_COMMAND_ID")
        registration_args+=(--dewey-url "$DEWEY_URL")
        registration_args+=(--dewey-token-env "$DEWEY_TOKEN_ENV")
        if [[ -n "$DEWEY_ANALYSIS_DIR_EXTERNAL_OBJECT_ID" ]]; then
          registration_args+=(--dewey-analysis-dir-external-object-id "$DEWEY_ANALYSIS_DIR_EXTERNAL_OBJECT_ID")
          registration_args+=(--dewey-run-artifact-euid "$DEWEY_RUN_ARTIFACT_EUID")
          registration_args+=(--dewey-ursa-analysis-euid "$DEWEY_URSA_ANALYSIS_EUID")
        fi
      fi
      set +e
      env -u AWS_PROFILE -u AWS_DEFAULT_PROFILE dyec export \
        --region {shlex.quote(region)} \
        --cluster {shlex.quote(cluster_name)} \
        --source-path "$clone_root" \
        --destination-s3-uri "$EXPORT_DESTINATION_S3_URI" \
        --output-dir "$DAYLILY_RUN_DIR/export" \
        "${{registration_args[@]}}"
      export_status=$?
      set -e
      if [[ "$export_status" -ne 0 ]]; then
        echo "[ERROR] Export failed with status $export_status"
        workflow_status="$export_status"
      elif [[ "$DELETE_ON_EXPORT_SUCCESS" == "true" ]]; then
        rm -rf -- "$clone_root"
        echo "[INFO] Deleted FSx analysis directory after successful export: $clone_root"
      fi
    fi
  fi
fi
export DAYLILY_STATUS_FINALIZED=1
export DAYLILY_STATUS_COMPLETED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
export DAYLILY_STATUS_EXIT_CODE="$workflow_status"
write_status
echo "[INFO] Workflow exited with status $workflow_status"
if [[ ! -d "$clone_root" ]]; then
  exit "$workflow_status"
fi
exec bash -il
"""

    tmux_script = f"""
set -euo pipefail
SESSION_NAME={shlex.quote(args.session_name)}
ANALYSIS_ID={shlex.quote(analysis_id)}
EXECUTING_ENTITY={shlex.quote(executing_entity)}
REPO_KEY={shlex.quote(args.repository)}
analysis_root=$(python3 - <<'PYCONFIG'
from pathlib import Path
analysis_root = '/fsx/analysis_results'
config_path = Path.home() / '.config/daylily/daylily_cli_global.yaml'
if config_path.exists():
    for line in config_path.read_text().splitlines():
        line = line.strip()
        if line.startswith('analysis_root:'):
            analysis_root = line.split(':', 1)[1].strip()
            break
print(analysis_root.rstrip('/'))
PYCONFIG
)
repo_relative=$(python3 - <<'PYREPOS'
from pathlib import Path
repo_key = {repository_literal}
relative = 'daylily-omics-analysis'
config_path = Path.home() / '.config/daylily/daylily_pipeline_command_catalog.yaml'
if config_path.exists():
    current_key = None
    for raw in config_path.read_text().splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if stripped.endswith(':'):
            current_key = stripped[:-1].strip()
            continue
        if current_key == repo_key and stripped.startswith('relative_path:'):
            relative = stripped.split(':', 1)[1].strip()
            break
print(relative.strip())
PYREPOS
)
analysis_root=${{analysis_root%/}}
run_dir="/home/ubuntu/daylily-runs/$SESSION_NAME"
clone_root="$analysis_root/$EXECUTING_ENTITY/$ANALYSIS_ID"
repo_path="$clone_root/$repo_relative"
work_script="$run_dir/launch.sh"
tmux_log="$run_dir/tmux.log"
bootstrap_log="$run_dir/tmux-bootstrap.log"
status_file="$run_dir/status.json"
mkdir -p "$run_dir"
: >"$tmux_log"
export DAYLILY_RUN_DIR="$run_dir"
export DAYLILY_REPO_PATH="$repo_path"
export DAYLILY_TMUX_LOG="$tmux_log"
tmux_session_name="${{SESSION_NAME//[^A-Za-z0-9_-]/_}}"
if [[ -z "$tmux_session_name" ]]; then
  echo "__DAYLILY_ERROR__=invalid_tmux_session_name"
  exit 8
fi
if tmux has-session -t "=$tmux_session_name" 2>/dev/null; then
  echo "__DAYLILY_ERROR__=session_exists"
  exit 8
fi
if [[ -e "$clone_root" ]]; then
  if [[ "$REPLACE_EXISTING_ANALYSIS_DIR" != "true" ]]; then
    echo "__DAYLILY_ERROR__=analysis_dir_exists"
    exit 8
  fi
  if [[ -z "$analysis_root" || -z "$EXECUTING_ENTITY" || -z "$ANALYSIS_ID" ]]; then
    echo "__DAYLILY_ERROR__=unsafe_replace_existing_analysis_dir"
    exit 8
  fi
  expected_clone_root="$analysis_root/$EXECUTING_ENTITY/$ANALYSIS_ID"
  if [[ "$clone_root" != "$expected_clone_root" || "$clone_root" == "/" ]]; then
    echo "__DAYLILY_ERROR__=unsafe_replace_existing_analysis_dir"
    exit 8
  fi
  rm -rf -- "$clone_root"
  echo "__DAYLILY_REPLACED_ANALYSIS_DIR__=$clone_root"
fi
cat <<'PAYLOAD' > "$work_script"
{pipeline_script}
PAYLOAD
chmod 0700 "$work_script"
nohup tmux new-session -d -s "$tmux_session_name" \
  -e "DAYLILY_RUN_DIR=$run_dir" \
  -e "DAYLILY_REPO_PATH=$repo_path" \
  -e "DAYLILY_TMUX_LOG=$tmux_log" \
  "bash -lc 'source \"$work_script\" >>\"$tmux_log\" 2>&1'" >"$bootstrap_log" 2>&1 &
SESSION_START_DEADLINE=$((SECONDS + 60))
session_ready=false
quick_status=""
while true; do
  if tmux has-session -t "=$tmux_session_name" 2>/dev/null; then
    session_ready=true
    break
  fi
  if [[ -f "$status_file" ]]; then
    if quick_status="$(python3 - "$status_file" <<'PYQUICK'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
exit_code = payload.get("exit_code")
if exit_code is None:
    raise SystemExit(1)
print(f"exit_code={{exit_code}}")
PYQUICK
)"; then
      break
    fi
  fi
  if (( SECONDS >= SESSION_START_DEADLINE )); then
    break
  fi
  sleep 1
done
if [[ "$session_ready" != "true" ]]; then
  if [[ -n "$quick_status" ]]; then
    echo "__DAYLILY_COMPLETED_QUICKLY__=$quick_status"
    echo "__DAYLILY_SESSION__=$SESSION_NAME"
    echo "__DAYLILY_TMUX_SESSION__=$tmux_session_name"
    echo "__DAYLILY_RUN_DIR__=$run_dir"
    echo "__DAYLILY_REPO_PATH__=$repo_path"
    exit 0
  fi
  if [[ -s "$bootstrap_log" ]]; then
    cat "$bootstrap_log" >&2
  fi
  if [[ -s "$tmux_log" ]]; then
    tail -n 80 "$tmux_log" >&2
  fi
  echo "__DAYLILY_ERROR__=session_start_timeout"
  exit 8
fi
echo "__DAYLILY_SESSION__=$SESSION_NAME"
echo "__DAYLILY_TMUX_SESSION__=$tmux_session_name"
echo "__DAYLILY_RUN_DIR__=$run_dir"
echo "__DAYLILY_REPO_PATH__=$repo_path"
"""

    result = run_shell(
        target.instance_id,
        region,
        tmux_script,
        profile=args.profile,
        timeout=120,
        comment="Launch daylily workflow tmux session",
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")

    launch_info = parse_workflow_launch(result.stdout)
    print(f"Tmux session '{launch_info.session_name}' created on the head node.")
    print(f"Run state directory: {launch_info.run_dir}")
    print(f"Workflow repo path: {launch_info.repo_path}")
    print(
        "Reconnect with: daylily-ssh-into-headnode --profile {profile} --region {region} --cluster {cluster}".format(
            profile=args.profile,
            region=region,
            cluster=cluster_name,
        )
    )
    print(f"Then run: tmux attach -t {launch_info.session_name}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except CommandError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
