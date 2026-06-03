#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import csv
import gzip
import json
import pathlib
import shlex
import sys
from typing import Iterable

from daylily_ec.aws.ssm import (
    resolve_headnode_instance_id,
    run_shell,
    SsmCommandFailedError,
    wait_for_ssm_online,
    write_remote_text,
)


PROFILE = "lsmc"
REGION = "us-west-2"
CLUSTER = "dyec5117"
STAMP = "20260602T203117Z"
WORKTREE = pathlib.Path("/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster")
LOCAL_ROOT = WORKTREE / "bench_expts" / f"full25b_shard008_lane_batched_resume_{STAMP}"
CHECKOUT = pathlib.Path(
    "/fsx/analysis_results/ubuntu/"
    "bcl25b_full_shard008_odirect_off_20260602T115314Z/"
    "daylily-omics-analysis"
)
BCL = CHECKOUT / "results/runs/20260514_LH01106_0009_B23TVLGLT4/bclconvert"
_INSTANCE_ID: str | None = None

BCL_BASE_CONFIG = {
    "merge_lane_fastqs": "false",
    "merge_tile_fastqs": "false",
    "shared_thread_odirect_output": "false",
    "tile_shard_level": "8",
    "tile_shard_threads": "48",
    "tile_shard_mem_mb": "180000",
    "partition": "i192mem",
    "tmpdir": "/dev/shm",
    "parallel_tiles": "24",
    "tile_parallel_tiles": "8",
    "tile_conversion_threads": "2",
    "tile_compression_threads": "24",
    "tile_decompression_threads": "8",
    "compression_threads": "64",
    "conversion_threads": "4",
    "decompression_threads": "32",
    "fastq_gzip_compression_level": "1",
    "force": "true",
    "output_legacy_stats": "true",
    "num_unknown_barcodes_reported": "1000",
    "barcode_mismatches_index1": "0",
    "barcode_mismatches_index2": "0",
    "sample_sheet_settings": "{}",
    "sample_sheet_settings_by_lane": "{}",
}


def target_instance() -> str:
    global _INSTANCE_ID
    if _INSTANCE_ID is not None:
        return _INSTANCE_ID
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    wait_for_ssm_online(target.instance_id, REGION, profile=PROFILE, timeout=180)
    _INSTANCE_ID = target.instance_id
    return _INSTANCE_ID


def remote(script: str, *, timeout: int = 300, comment: str = "BCL batch tool") -> str:
    instance_id = target_instance()
    try:
        result = run_shell(
            instance_id,
            REGION,
            script,
            profile=PROFILE,
            timeout=timeout,
            comment=comment,
        )
    except SsmCommandFailedError as exc:
        if exc.result.stdout:
            print(exc.result.stdout, file=sys.stderr, end="")
        if exc.result.stderr:
            print(exc.result.stderr, file=sys.stderr, end="")
        raise
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    return result.stdout


def clean_stdout_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("DAY-EC activated")
    ]


def remote_size(remote_path: str) -> int:
    short = pathlib.Path(remote_path).name
    size_text = remote(
        f"stat -c %s {shlex.quote(remote_path)}",
        timeout=120,
        comment=f"Size {short}"[:100],
    )
    size_lines = clean_stdout_lines(size_text)
    if not size_lines or not size_lines[-1].isdigit():
        raise RuntimeError(f"could not parse remote size for {remote_path}: {size_text!r}")
    return int(size_lines[-1])


def copy_remote_bytes(remote_path: str, size: int) -> bytes:
    chunk_size = 16_000
    chunks: list[bytes] = []
    if size == 0:
        return b""
    for offset in range(0, size, chunk_size):
        block = offset // chunk_size
        short = pathlib.Path(remote_path).name
        stdout = remote(
            "dd if="
            + shlex.quote(remote_path)
            + f" bs={chunk_size} skip={block} count=1 status=none | base64 -w0",
            timeout=120,
            comment=f"Read {short} chunk {block}"[:100],
        )
        payload = "".join(clean_stdout_lines(stdout))
        chunks.append(base64.b64decode(payload.encode("ascii")))
    data = b"".join(chunks)
    if len(data) != size:
        raise RuntimeError(f"copied {len(data)} bytes for {remote_path}, expected {size}")
    return data


def copy_remote_file(remote_path: str, local_path: pathlib.Path) -> int:
    size = remote_size(remote_path)
    if size > 50_000:
        gzip_remote = f"/tmp/{pathlib.Path(remote_path).name}.{STAMP}.copy.gz"
        short = pathlib.Path(remote_path).name
        remote(
            f"gzip -c {shlex.quote(remote_path)} > {shlex.quote(gzip_remote)}",
            timeout=300,
            comment=f"Compress {short}"[:100],
        )
        gzip_size = remote_size(gzip_remote)
        gzip_data = copy_remote_bytes(gzip_remote, gzip_size)
        remote(f"rm -f {shlex.quote(gzip_remote)}", timeout=120, comment=f"Remove {short}.gz"[:100])
        data = gzip.decompress(gzip_data)
    else:
        data = copy_remote_bytes(remote_path, size)
    if len(data) != size:
        raise RuntimeError(f"copied {len(data)} bytes for {remote_path}, expected {size}")
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(data)
    return len(data)


def read_tsv(path: pathlib.Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def phase_dir(phase: str, lanes: Iterable[str]) -> pathlib.Path:
    return LOCAL_ROOT / f"{phase}_{'_'.join(lanes)}"


def preserve_phase(args: argparse.Namespace) -> None:
    lanes = list(args.lanes)
    delete_lanes = list(args.delete_lanes)
    local_dir = phase_dir(args.phase, lanes)
    (local_dir / "benchmarks").mkdir(parents=True, exist_ok=True)
    (local_dir / "manifests").mkdir(parents=True, exist_ok=True)

    lane_json = json.dumps(lanes)
    delete_lane_json = json.dumps(delete_lanes)
    remote_out = f"/tmp/bcl_{args.phase}_evidence_{STAMP}"
    script = f"""
set -euo pipefail
REMOTE_OUT={shlex.quote(remote_out)}
CHECKOUT={shlex.quote(str(CHECKOUT))}
BCL={shlex.quote(str(BCL))}
mkdir -p "$REMOTE_OUT"
python3 - <<'PY'
from __future__ import annotations
import csv
import json
import pathlib
from collections import defaultdict

lanes = json.loads({lane_json!r})
delete_lanes = json.loads({delete_lane_json!r})
remote = pathlib.Path({remote_out!r})
checkout = pathlib.Path({str(CHECKOUT)!r})
bcl = pathlib.Path({str(BCL)!r})

rows = []
for lane in lanes:
    for root_name, output_class in [("tile_fastqs", "tile"), ("lane_fastqs", "lane")]:
        root = bcl / root_name / lane
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.fastq.gz")):
            rel = p.relative_to(root)
            shard = rel.parts[0] if output_class == "tile" and rel.parts else ""
            size = p.stat().st_size
            rows.append({{
                "lane": lane,
                "output_class": output_class,
                "shard": shard,
                "path": str(p),
                "bytes": str(size),
                "gib": f"{{size / (1024 ** 3):.9f}}",
                "undetermined": "true"
                if "undetermined" in p.name.lower() or "Undetermined" in p.name
                else "false",
            }})

with (remote / "fastq_sizes.tsv").open("w", newline="") as handle:
    fields = ["lane", "output_class", "shard", "path", "bytes", "gib", "undetermined"]
    writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\\t", lineterminator="\\n")
    writer.writeheader()
    writer.writerows(rows)

totals = defaultdict(lambda: {{"count": 0, "bytes": 0, "und_count": 0, "und_bytes": 0}})
for row in rows:
    key = (row["lane"], row["output_class"])
    totals[key]["count"] += 1
    totals[key]["bytes"] += int(row["bytes"])
    if row["undetermined"] == "true":
        totals[key]["und_count"] += 1
        totals[key]["und_bytes"] += int(row["bytes"])

with (remote / "fastq_totals.tsv").open("w", newline="") as handle:
    fields = [
        "lane",
        "output_class",
        "fastq_file_count",
        "total_fastq_bytes",
        "total_fastq_gib",
        "undetermined_fastq_file_count",
        "undetermined_fastq_bytes",
        "undetermined_fastq_gib",
        "assigned_fastq_bytes",
        "assigned_fastq_gib",
    ]
    writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\\t", lineterminator="\\n")
    writer.writeheader()
    for (lane, output_class), total in sorted(totals.items()):
        assigned = total["bytes"] - total["und_bytes"]
        writer.writerow({{
            "lane": lane,
            "output_class": output_class,
            "fastq_file_count": total["count"],
            "total_fastq_bytes": total["bytes"],
            "total_fastq_gib": f"{{total['bytes'] / (1024 ** 3):.9f}}",
            "undetermined_fastq_file_count": total["und_count"],
            "undetermined_fastq_bytes": total["und_bytes"],
            "undetermined_fastq_gib": f"{{total['und_bytes'] / (1024 ** 3):.9f}}",
            "assigned_fastq_bytes": assigned,
            "assigned_fastq_gib": f"{{assigned / (1024 ** 3):.9f}}",
        }})

complete_rows = []
for lane in lanes:
    done = 0
    missing = 0
    for i in range(1, 9):
        marker = bcl / "tile_reports" / lane / f"{{i:04d}}_tiles" / "bclconvert.done"
        if marker.exists():
            done += 1
        else:
            missing += 1
    complete_rows.append({{"lane": lane, "done_shards": done, "missing_shards": missing}})
with (remote / "lane_completion.tsv").open("w", newline="") as handle:
    fields = ["lane", "done_shards", "missing_shards"]
    writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\\t", lineterminator="\\n")
    writer.writeheader()
    writer.writerows(complete_rows)

benchmarks = []
for root in [bcl / "benchmarks", checkout / "results/day_hg38/benchmarks"]:
    if not root.exists():
        continue
    for p in sorted(root.rglob("*.bench.tsv")):
        name = p.name
        include = any(lane in name for lane in lanes)
        if name in {{"bclconvert_validate_inputs.bench.tsv", "produce_bclconvert_fastqs.bench.tsv"}}:
            include = True
        if include:
            benchmarks.append(p)
with (remote / "benchmark_files.tsv").open("w") as handle:
    handle.write("remote_path\\tbytes\\n")
    for p in benchmarks:
        handle.write(f"{{p}}\\t{{p.stat().st_size}}\\n")

delete_paths = []
for lane in delete_lanes:
    for rel in [f"tile_fastqs/{{lane}}", f"tile_reports/{{lane}}", f"lane_fastqs/{{lane}}", f"lane_reports/{{lane}}"]:
        p = bcl / rel
        if p.exists():
            delete_paths.append(p)
    for sub in ["benchmarks", "logs"]:
        root = bcl / sub
        if root.exists():
            for p in sorted(root.glob(f"*{{lane}}*")):
                delete_paths.append(p)
seen = []
for p in delete_paths:
    s = str(p)
    if s not in seen and p.exists():
        seen.append(s)
with (remote / "deletion_manifest.tsv").open("w") as handle:
    handle.write("remote_path\\ttype\\tbytes\\n")
    for s in seen:
        p = pathlib.Path(s)
        size = p.stat().st_size if p.is_file() else 0
        handle.write(f"{{s}}\\t{{'dir' if p.is_dir() else 'file'}}\\t{{size}}\\n")
PY
{{
  echo -e "REMOTE_OUT\\t$REMOTE_OUT"
  echo "FILES"
  find "$REMOTE_OUT" -maxdepth 1 -type f -printf '%p\\t%s\\n' | sort
  echo "DF"
  df -h /fsx
}} > "$REMOTE_OUT/remote_inventory.txt"
cat "$REMOTE_OUT/remote_inventory.txt"
"""
    stdout = remote(script, timeout=300, comment=f"Preserve {args.phase} evidence")
    (local_dir / "remote_inventory.txt").write_text(stdout, encoding="utf-8")
    print(stdout, end="")

    manifest_paths = []
    for line in stdout.splitlines():
        if line.startswith("/tmp/") and "\t" in line:
            manifest_paths.append(line.rsplit("\t", 1)[0])
    for remote_path in manifest_paths:
        local_path = local_dir / "manifests" / pathlib.Path(remote_path).name
        copied = copy_remote_file(remote_path, local_path)
        print(f"copied_manifest\t{remote_path}\t{local_path}\t{copied}")

    benchmark_manifest = local_dir / "manifests" / "benchmark_files.tsv"
    copied_benchmarks = 0
    for row in read_tsv(benchmark_manifest):
        remote_path = row["remote_path"]
        local_name = remote_path.strip("/").replace("/", "_")
        local_path = local_dir / "benchmarks" / local_name
        copied = copy_remote_file(remote_path, local_path)
        copied_benchmarks += 1
        print(f"copied_benchmark\t{remote_path}\t{local_path}\t{copied}")
    print(f"local_phase_dir\t{local_dir}")
    print(f"benchmark_count\t{copied_benchmarks}")


def copy_benchmarks(args: argparse.Namespace) -> None:
    lanes = list(args.lanes)
    local_dir = phase_dir(args.phase, lanes)
    benchmark_manifest = local_dir / "manifests" / "benchmark_files.tsv"
    if not benchmark_manifest.is_file():
        raise SystemExit(f"missing benchmark manifest: {benchmark_manifest}")
    (local_dir / "benchmarks").mkdir(parents=True, exist_ok=True)
    copied_benchmarks = 0
    for row in read_tsv(benchmark_manifest):
        remote_path = row["remote_path"]
        local_name = remote_path.strip("/").replace("/", "_")
        local_path = local_dir / "benchmarks" / local_name
        copied = copy_remote_file(remote_path, local_path)
        copied_benchmarks += 1
        print(f"copied_benchmark\t{remote_path}\t{local_path}\t{copied}")
    print(f"local_phase_dir\t{local_dir}")
    print(f"benchmark_count\t{copied_benchmarks}")


def preserve_phase_fast(args: argparse.Namespace) -> None:
    lanes = list(args.lanes)
    delete_lanes = list(args.delete_lanes)
    local_dir = phase_dir(args.phase, lanes)
    (local_dir / "benchmarks").mkdir(parents=True, exist_ok=True)
    (local_dir / "manifests").mkdir(parents=True, exist_ok=True)

    lane_json = json.dumps(lanes)
    delete_lane_json = json.dumps(delete_lanes)
    remote_out = f"/tmp/bcl_{args.phase}_evidence_{STAMP}"
    script = f"""
set -euo pipefail
REMOTE_OUT={shlex.quote(remote_out)}
rm -rf "$REMOTE_OUT"
mkdir -p "$REMOTE_OUT"
python3 - <<'PY'
from __future__ import annotations
import csv
import json
import pathlib
import subprocess
from collections import defaultdict

lanes = json.loads({lane_json!r})
delete_lanes = json.loads({delete_lane_json!r})
remote = pathlib.Path({remote_out!r})
checkout = pathlib.Path({str(CHECKOUT)!r})
bcl = pathlib.Path({str(BCL)!r})

def find_rows(root: pathlib.Path, name: str, *, maxdepth: int | None = None) -> list[tuple[pathlib.Path, int]]:
    if not root.exists():
        return []
    cmd = ["find", str(root)]
    if maxdepth is not None:
        cmd.extend(["-maxdepth", str(maxdepth)])
    cmd.extend(["-type", "f", "-name", name, "-printf", "%p\\t%s\\n"])
    out = subprocess.check_output(cmd, text=True)
    rows = []
    for line in out.splitlines():
        if not line:
            continue
        path, size = line.rsplit("\\t", 1)
        rows.append((pathlib.Path(path), int(size)))
    return rows

rows = []
for lane in lanes:
    for root_name, output_class in [("tile_fastqs", "tile"), ("lane_fastqs", "lane")]:
        root = bcl / root_name / lane
        for p, size in sorted(find_rows(root, "*.fastq.gz")):
            rel = p.relative_to(root)
            shard = rel.parts[0] if output_class == "tile" and rel.parts else ""
            rows.append({{
                "lane": lane,
                "output_class": output_class,
                "shard": shard,
                "path": str(p),
                "bytes": str(size),
                "gib": f"{{size / (1024 ** 3):.9f}}",
                "undetermined": "true" if "undetermined" in p.name.lower() else "false",
            }})

with (remote / "fastq_sizes.tsv").open("w", newline="") as handle:
    fields = ["lane", "output_class", "shard", "path", "bytes", "gib", "undetermined"]
    writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\\t", lineterminator="\\n")
    writer.writeheader()
    writer.writerows(rows)

totals = defaultdict(lambda: {{"count": 0, "bytes": 0, "und_count": 0, "und_bytes": 0}})
for row in rows:
    key = (row["lane"], row["output_class"])
    totals[key]["count"] += 1
    totals[key]["bytes"] += int(row["bytes"])
    if row["undetermined"] == "true":
        totals[key]["und_count"] += 1
        totals[key]["und_bytes"] += int(row["bytes"])

with (remote / "fastq_totals.tsv").open("w", newline="") as handle:
    fields = [
        "lane",
        "output_class",
        "fastq_file_count",
        "total_fastq_bytes",
        "total_fastq_gib",
        "undetermined_fastq_file_count",
        "undetermined_fastq_bytes",
        "undetermined_fastq_gib",
        "assigned_fastq_bytes",
        "assigned_fastq_gib",
    ]
    writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\\t", lineterminator="\\n")
    writer.writeheader()
    for (lane, output_class), total in sorted(totals.items()):
        assigned = total["bytes"] - total["und_bytes"]
        writer.writerow({{
            "lane": lane,
            "output_class": output_class,
            "fastq_file_count": total["count"],
            "total_fastq_bytes": total["bytes"],
            "total_fastq_gib": f"{{total['bytes'] / (1024 ** 3):.9f}}",
            "undetermined_fastq_file_count": total["und_count"],
            "undetermined_fastq_bytes": total["und_bytes"],
            "undetermined_fastq_gib": f"{{total['und_bytes'] / (1024 ** 3):.9f}}",
            "assigned_fastq_bytes": assigned,
            "assigned_fastq_gib": f"{{assigned / (1024 ** 3):.9f}}",
        }})

complete_rows = []
for lane in lanes:
    done = 0
    missing = 0
    report_root = bcl / "tile_reports" / lane
    for i in range(1, 9):
        if list(report_root.glob(f"{{i:04d}}_tiles*/bclconvert.done")):
            done += 1
        else:
            missing += 1
    complete_rows.append({{"lane": lane, "done_shards": done, "missing_shards": missing}})
with (remote / "lane_completion.tsv").open("w", newline="") as handle:
    fields = ["lane", "done_shards", "missing_shards"]
    writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\\t", lineterminator="\\n")
    writer.writeheader()
    writer.writerows(complete_rows)

benchmarks = []
for root in [bcl / "benchmarks", checkout / "results/day_hg38/benchmarks"]:
    for p, size in find_rows(root, "*.bench.tsv"):
        name = p.name
        include = any(lane in name for lane in lanes)
        if name in {{"bclconvert_validate_inputs.bench.tsv", "produce_bclconvert_fastqs.bench.tsv"}}:
            include = True
        if include:
            benchmarks.append((p, size))
with (remote / "benchmark_files.tsv").open("w") as handle:
    handle.write("remote_path\\tbytes\\n")
    for p, size in sorted(benchmarks):
        handle.write(f"{{p}}\\t{{size}}\\n")

delete_paths = []
for lane in delete_lanes:
    for rel in [f"tile_fastqs/{{lane}}", f"tile_reports/{{lane}}", f"lane_fastqs/{{lane}}", f"lane_reports/{{lane}}"]:
        p = bcl / rel
        if p.exists():
            delete_paths.append(p)
    for sub in ["benchmarks", "logs"]:
        root = bcl / sub
        for p, _ in find_rows(root, f"*{{lane}}*", maxdepth=1):
            delete_paths.append(p)

seen = []
for p in delete_paths:
    s = str(p)
    if s not in seen and p.exists():
        seen.append(s)
with (remote / "deletion_manifest.tsv").open("w") as handle:
    handle.write("remote_path\\ttype\\tbytes\\n")
    for s in seen:
        p = pathlib.Path(s)
        size = p.stat().st_size if p.is_file() else 0
        handle.write(f"{{s}}\\t{{'dir' if p.is_dir() else 'file'}}\\t{{size}}\\n")
PY
{{
  echo -e "REMOTE_OUT\\t$REMOTE_OUT"
  echo "FILES"
  find "$REMOTE_OUT" -maxdepth 1 -type f -printf '%p\\t%s\\n' | sort
  echo "DF"
  df -h /fsx
}} > "$REMOTE_OUT/remote_inventory.txt"
cat "$REMOTE_OUT/remote_inventory.txt"
"""
    stdout = remote(script, timeout=300, comment=f"Preserve {args.phase} evidence")
    (local_dir / "remote_inventory.txt").write_text(stdout, encoding="utf-8")
    print(stdout, end="")

    manifest_paths = []
    for line in stdout.splitlines():
        if line.startswith("/tmp/") and "\t" in line:
            manifest_paths.append(line.rsplit("\t", 1)[0])
    for remote_path in manifest_paths:
        local_path = local_dir / "manifests" / pathlib.Path(remote_path).name
        copied = copy_remote_file(remote_path, local_path)
        print(f"copied_manifest\t{remote_path}\t{local_path}\t{copied}")

    benchmark_manifest = local_dir / "manifests" / "benchmark_files.tsv"
    copied_benchmarks = 0
    for row in read_tsv(benchmark_manifest):
        remote_path = row["remote_path"]
        local_name = remote_path.strip("/").replace("/", "_")
        local_path = local_dir / "benchmarks" / local_name
        copied = copy_remote_file(remote_path, local_path)
        copied_benchmarks += 1
        print(f"copied_benchmark\t{remote_path}\t{local_path}\t{copied}")
    print(f"local_phase_dir\t{local_dir}")
    print(f"benchmark_count\t{copied_benchmarks}")


def delete_manifest(args: argparse.Namespace) -> None:
    manifest = pathlib.Path(args.manifest)
    rows = read_tsv(manifest)
    paths = [row["remote_path"] for row in rows]
    if not paths:
        raise SystemExit(f"empty deletion manifest: {manifest}")
    path_exports = "\n".join(f"paths+=( {shlex.quote(path)} )" for path in paths)
    script = f"""
set -euo pipefail
paths=()
{path_exports}
echo "DELETE_LABEL {shlex.quote(args.label)}"
echo "BEFORE_DF"
df -h /fsx
echo "BEFORE_DU"
for p in "${{paths[@]}}"; do
  if [ -e "$p" ]; then du -sh "$p"; else echo "MISSING_BEFORE $p"; fi
done
echo "DELETE_PATHS"
for p in "${{paths[@]}}"; do
  echo "$p"
  rm -rf -- "$p"
done
echo "VERIFY_ABSENT"
missing=0
for p in "${{paths[@]}}"; do
  if [ -e "$p" ]; then echo "STILL_EXISTS $p"; missing=1; else echo "ABSENT $p"; fi
done
echo "AFTER_DF"
df -h /fsx
exit "$missing"
"""
    stdout = remote(script, timeout=1800, comment=f"Delete {args.label} manifest")
    print(stdout, end="")


def check_manifest(args: argparse.Namespace) -> None:
    manifest = pathlib.Path(args.manifest)
    rows = read_tsv(manifest)
    paths = [row["remote_path"] for row in rows]
    path_exports = "\n".join(f"paths+=( {shlex.quote(path)} )" for path in paths)
    script = f"""
set -euo pipefail
paths=()
{path_exports}
echo "CHECK_LABEL {shlex.quote(args.label)}"
echo "DF"
df -h /fsx
echo "PATH_STATE"
for p in "${{paths[@]}}"; do
  if [ -e "$p" ]; then
    if [ -d "$p" ]; then printf 'EXISTS\\tdir\\t%s\\n' "$p"; else printf 'EXISTS\\tfile\\t%s\\n' "$p"; fi
  else
    printf 'ABSENT\\t-\\t%s\\n' "$p"
  fi
done
"""
    stdout = remote(script, timeout=300, comment=f"Check {args.label} manifest")
    print(stdout, end="")


def bcl_config_json(lanes: list[str]) -> str:
    cfg = dict(BCL_BASE_CONFIG)
    cfg["tile_shard_lanes"] = ",".join(lanes)
    return json.dumps(cfg, separators=(",", ":"))


def start_phase(args: argparse.Namespace) -> None:
    raise SystemExit(
        "disabled: DayOA workflow execution must be done by sending dy-r commands "
        "into a persistent interactive ubuntu tmux login shell"
    )


def poll_phase(args: argparse.Namespace) -> None:
    raise SystemExit(
        "disabled: inspect the persistent dy-r tmux pane with tmux capture-pane "
        "and read logs only"
    )


def tmux_ensure(args: argparse.Namespace) -> None:
    session = args.session
    script = f"""
set -euo pipefail
if tmux has-session -t {shlex.quote(session)} 2>/dev/null; then
  echo "EXISTS\\t{session}"
else
  tmux new-session -d -s {shlex.quote(session)} 'bash -il'
  echo "CREATED\\t{session}"
fi
windows=$(tmux list-windows -t {shlex.quote(session)} -F '#{{window_index}}' | wc -l)
panes=$(tmux list-panes -t {shlex.quote(session)} -F '#{{pane_index}}' | wc -l)
echo "WINDOWS\\t$windows"
echo "PANES\\t$panes"
test "$windows" -eq 1
test "$panes" -eq 1
"""
    print(remote(script, timeout=120, comment=f"Ensure tmux {session}"), end="")


def tmux_send(args: argparse.Namespace) -> None:
    session = args.session
    command = args.command
    command_b64 = base64.b64encode(command.encode("utf-8")).decode("ascii")
    script = f"""
set -euo pipefail
export DAYOA_TMUX_CMD_B64={shlex.quote(command_b64)}
cmd=$(python3 -c 'import base64, os; print(base64.b64decode(os.environ["DAYOA_TMUX_CMD_B64"]).decode("utf-8"))')
tmux has-session -t {shlex.quote(session)}
windows=$(tmux list-windows -t {shlex.quote(session)} -F '#{{window_index}}' | wc -l)
panes=$(tmux list-panes -t {shlex.quote(session)} -F '#{{pane_index}}' | wc -l)
test "$windows" -eq 1
test "$panes" -eq 1
tmux send-keys -t {shlex.quote(session)} "$cmd" Enter
printf 'SENT\\t%s\\t%s\\n' {shlex.quote(session)} "$cmd"
"""
    print(remote(script, timeout=120, comment=f"Send tmux {session}"), end="")


def tmux_capture(args: argparse.Namespace) -> None:
    session = args.session
    lines = int(args.lines)
    script = f"""
set -euo pipefail
echo "POLL $(date -u +%Y-%m-%dT%H:%M:%SZ)"
tmux has-session -t {shlex.quote(session)}
windows=$(tmux list-windows -t {shlex.quote(session)} -F '#{{window_index}}' | wc -l)
panes=$(tmux list-panes -t {shlex.quote(session)} -F '#{{pane_index}}' | wc -l)
echo "SESSION\\t{session}"
echo "WINDOWS\\t$windows"
echo "PANES\\t$panes"
echo "DF"
df -h /fsx
echo "SQUEUE"
squeue -h -o '%i|%T|%M|%N|%j' || true
echo "PANE"
tmux capture-pane -pt {shlex.quote(session)} -S -{lines}
"""
    print(remote(script, timeout=300, comment=f"Capture tmux {session}"), end="")


def progress_report(args: argparse.Namespace) -> None:
    lanes = list(args.lanes)
    lane_csv = ",".join(lanes)
    fallback_shards: dict[tuple[str, str], int] = {}
    for manifest in sorted(LOCAL_ROOT.glob("phase*/manifests/fastq_sizes.tsv")):
        manifest_shards: dict[tuple[str, str], int] = {}
        for row in read_tsv(manifest):
            if row.get("output_class") != "tile":
                continue
            lane = row.get("lane", "")
            shard = row.get("shard", "")
            if not lane or not shard:
                continue
            try:
                size = int(row.get("bytes", "0"))
            except ValueError:
                continue
            manifest_shards[(lane, shard)] = manifest_shards.get((lane, shard), 0) + size
        fallback_shards.update(manifest_shards)
    fallback_sizes = list(fallback_shards.values())
    fallback_sum = sum(fallback_sizes)
    fallback_count = len(fallback_sizes)
    script = f"""
set -euo pipefail
python3 - <<'PY'
from __future__ import annotations
import os
import pathlib
import re
import subprocess
from datetime import datetime, timezone

lanes = {lanes!r}
fallback_sum = {fallback_sum}
fallback_count = {fallback_count}
bcl = pathlib.Path({str(BCL)!r})
tile_fastqs = bcl / "tile_fastqs"
tile_reports = bcl / "tile_reports"

def gib(n: int) -> float:
    return n / (1024 ** 3)

def tree_fastq_bytes(path: pathlib.Path) -> tuple[int, int]:
    total = 0
    count = 0
    if path.exists():
        for p in path.rglob("*.fastq.gz"):
            try:
                total += p.stat().st_size
                count += 1
            except FileNotFoundError:
                pass
    return total, count

def parse_elapsed(text: str) -> int:
    text = (text or "").strip()
    if not text:
        return 0
    days = 0
    if "-" in text:
        d, text = text.split("-", 1)
        try:
            days = int(d)
        except ValueError:
            days = 0
    parts = [int(p) for p in text.split(":") if p.isdigit()]
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h, m, s = 0, parts[0], parts[1]
    elif len(parts) == 1:
        h, m, s = 0, 0, parts[0]
    else:
        h = m = s = 0
    return days * 86400 + h * 3600 + m * 60 + s

complete_sizes = []
completion = []
for lane in lanes:
    done = 0
    missing = 0
    for i in range(1, 9):
        shard = f"{{i:04d}}_tiles"
        matches = sorted((tile_reports / lane).glob(f"{{shard}}*/bclconvert.done"))
        if not matches:
            missing += 1
            continue
        done += 1
        shard_dir = matches[0].parent.name
        size, count = tree_fastq_bytes(tile_fastqs / lane / shard_dir)
        if size > 0:
            complete_sizes.append(size)
    completion.append((lane, done, missing))

avg_complete = (
    (sum(complete_sizes) + fallback_sum) / (len(complete_sizes) + fallback_count)
    if (complete_sizes or fallback_count)
    else 0
)

try:
    squeue = subprocess.check_output(
        ["squeue", "-h", "-o", "%i|%T|%M|%N|%j"],
        text=True,
        stderr=subprocess.STDOUT,
    )
except Exception as exc:
    squeue = f"SQUEUE_ERROR|{{exc}}\\n"

job_re = re.compile(r"run_bclconvert_tile_shard-run_bclconvert_(L[0-9]{{3}})_([0-9]{{4}}_tiles[0-9]{{4}}-[0-9]{{4}})")
jobs = []
for line in squeue.splitlines():
    parts = line.split("|", 4)
    if len(parts) != 5:
        continue
    jobid, state, elapsed, nodes, name = parts
    match = job_re.search(name)
    if not match:
        continue
    lane, shard = match.groups()
    if lane not in lanes:
        continue
    elapsed_s = parse_elapsed(elapsed)
    size, count = tree_fastq_bytes(tile_fastqs / lane / shard)
    if avg_complete and size > 0:
        progress = min(size / avg_complete, 0.999)
        eta_s = max(int(elapsed_s * (1 / progress - 1)), 0)
        eta = f"{{eta_s/60:.1f}}m"
        progress_txt = f"{{progress*100:.1f}}%"
    else:
        eta = "unknown"
        progress_txt = "0.0%" if size == 0 else "unknown"
    jobs.append((jobid, state, elapsed, nodes, lane, shard, count, size, progress_txt, eta))

df = subprocess.check_output(["df", "-h", "/fsx"], text=True)
print(f"PROGRESS_TS\\t{{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}}")
print(f"LANES\\t{lane_csv}")
print("DF")
print(df.rstrip())
print(f"AVG_COMPLETE_SHARD_FASTQ_GIB\\t{{gib(int(avg_complete)):.3f}}")
print(f"COMPLETE_SHARDS_USED_FOR_AVG\\t{{len(complete_sizes) + fallback_count}}")
print("LANE_COMPLETION\\tlane\\tdone\\tmissing")
for lane, done, missing in completion:
    print(f"LANE_COMPLETION\\t{{lane}}\\t{{done}}\\t{{missing}}")
print("ACTIVE_JOBS\\tjobid\\tstate\\telapsed\\tnodes\\tlane\\tshard\\tfastq_count\\tfastq_gib\\tprogress_vs_avg\\teta")
if jobs:
    for row in sorted(jobs, key=lambda r: (r[4], r[5], r[0])):
        jobid, state, elapsed, nodes, lane, shard, count, size, progress_txt, eta = row
        print(f"ACTIVE_JOBS\\t{{jobid}}\\t{{state}}\\t{{elapsed}}\\t{{nodes}}\\t{{lane}}\\t{{shard}}\\t{{count}}\\t{{gib(size):.3f}}\\t{{progress_txt}}\\t{{eta}}")
else:
    print("ACTIVE_JOBS\\tnone")
PY
"""
    print(remote(script, timeout=300, comment="BCL progress report"), end="")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("preserve-phase")
    p.add_argument("--phase", required=True)
    p.add_argument("--lanes", nargs="+", required=True)
    p.add_argument("--delete-lanes", nargs="*", default=[])
    p.set_defaults(func=preserve_phase_fast)

    b = sub.add_parser("copy-benchmarks")
    b.add_argument("--phase", required=True)
    b.add_argument("--lanes", nargs="+", required=True)
    b.set_defaults(func=copy_benchmarks)

    d = sub.add_parser("delete-manifest")
    d.add_argument("--manifest", required=True)
    d.add_argument("--label", required=True)
    d.set_defaults(func=delete_manifest)

    c = sub.add_parser("check-manifest")
    c.add_argument("--manifest", required=True)
    c.add_argument("--label", required=True)
    c.set_defaults(func=check_manifest)

    s = sub.add_parser("start-phase")
    s.add_argument("--phase", required=True)
    s.add_argument("--lanes", nargs="+", required=True)
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=start_phase)

    poll = sub.add_parser("poll-phase")
    poll.add_argument("--phase", required=True)
    poll.add_argument("--dry-run", action="store_true")
    poll.set_defaults(func=poll_phase)

    te = sub.add_parser("tmux-ensure")
    te.add_argument("--session", required=True)
    te.set_defaults(func=tmux_ensure)

    ts = sub.add_parser("tmux-send")
    ts.add_argument("--session", required=True)
    ts.add_argument("--command", required=True)
    ts.set_defaults(func=tmux_send)

    tc = sub.add_parser("tmux-capture")
    tc.add_argument("--session", required=True)
    tc.add_argument("--lines", default="200")
    tc.set_defaults(func=tmux_capture)

    pr = sub.add_parser("progress-report")
    pr.add_argument("--lanes", nargs="+", required=True)
    pr.set_defaults(func=progress_report)

    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
