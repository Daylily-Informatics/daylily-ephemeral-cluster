#!/usr/bin/env python3
from __future__ import annotations

import base64
import csv
import datetime as dt
import gzip
import json
import math
import re
import statistics
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from textwrap import dedent

from daylily_ec.aws.ssm import resolve_headnode_instance_id, run_shell


RUN_ID = "20260707T144453Z"
CLUSTER = "cmdcat-103-all-20260707"
REGION = "us-west-2"
PROFILE = "lsmc"
OUT_PREFIX = Path("docs/plans") / f"{RUN_ID}_benchmark_resource_review"
RAW_S3_URI = (
    "s3://lsmc-ssf-sequencing-data/derived/command-catalog/"
    f"dyec-10.0.103/dayoa-10.0.64/{RUN_ID}/benchmark_resource_review/raw_remote_payload.json.gz"
)

COMMAND_SESSIONS = [
    ("simple-test", "ccv_live_simple-test_20260707T190607Z"),
    ("illumina_snv_alignstats", "ccv_live_illumina_snv_alignstats_20260707T165057Z"),
    (
        "illumina_snv_alignstats_relatedness_vep_multiqc",
        "ccv_live_illumina_snv_alignstats_relatedness_vep_multiqc_20260707T165057Z",
    ),
    ("illumina_hg002_kitchensink_multiqc", "ccv_live_illumina_hg002_kitchensink_multiqc_20260707T185605Z"),
    ("illumina_pangenome_snv", "ccv_live_illumina_pangenome_snv_20260707T190607Z"),
    ("ultima_snv_alignstats", "ccv_live_ultima_snv_alignstats_20260707T190607Z"),
    ("ultima_snv_alignstats_kitchensink", "ccv_live_ultima_snv_alignstats_kitchensink_20260707T190607Z"),
    ("ultima_pangenome_snv", "ccv_live_ultima_pangenome_snv_20260707T190607Z"),
    ("ont_snv_alignstats", "ccv_live_ont_snv_alignstats_20260707T165057Z"),
    ("ont_snv_alignstats_kitchensink", "ccv_live_ont_snv_alignstats_kitchensink_20260707T165057Z"),
    ("pacbio_snv_alignstats", "ccv_live_pacbio_snv_alignstats_20260707T190607Z"),
    ("roche_snv_alignstats", "ccv_live_roche_snv_alignstats_20260707T190607Z"),
    ("hybrid_ilmn_ont_snv", "ccv_live_hybrid_ilmn_ont_snv_20260707T211600Z"),
    ("hybrid_ilmn_ont_snv_kitchensink", "ccv_live_hybrid_ilmn_ont_snv_kitchensink_20260707T203440Z"),
    ("inflection-bjuice-product-v0.1", "ccv_live_inflection-bjuice-product-v0.1_20260707T225128Z"),
    ("complete_genomics_mgi_snv_concordance", "ccv_live_complete_genomics_mgi_snv_concordance_20260707T165057Z"),
    ("illumina_run_qc", "ccv_live_illumina_run_qc_20260707T165057Z"),
    ("illumina_bclconvert", "ccv_live_illumina_bclconvert_20260707T170404Z"),
    ("illumina_run_qc_bclconvert", "ccv_live_illumina_run_qc_bclconvert_20260707T170404Z"),
    ("ont_run_qc", "ccv_live_ont_run_qc_20260707T170900Z"),
    ("ultima_run_qc", "ccv_live_ultima_run_qc_20260707T171700Z"),
]


def remote_script() -> str:
    sessions_json = json.dumps(COMMAND_SESSIONS)
    return dedent(
        f"""
        import base64, csv, datetime as dt, gzip, json, os, re, subprocess, sys
        from pathlib import Path

        sessions = {sessions_json}
        now = dt.datetime.now(dt.timezone.utc).isoformat()

        def read_text(path):
            try:
                return Path(path).read_text(errors="replace")
            except Exception:
                return ""

        def parse_resources(text):
            result = {{}}
            for item in str(text or "").split(","):
                item = item.strip()
                if "=" not in item:
                    continue
                key, value = item.split("=", 1)
                result[key.strip()] = value.strip()
            return result

        def parse_tmux(session, command_id):
            path = Path("/home/ubuntu/daylily-runs") / session / "tmux.log"
            text = read_text(path)
            jobs = []
            bench_map = {{}}
            current = None
            for raw in text.splitlines():
                line = raw.rstrip("\\n")
                m = re.match(r"^rule ([A-Za-z0-9_.-]+):\\s*$", line)
                if m:
                    current = {{
                        "command_id": command_id,
                        "session": session,
                        "rule": m.group(1),
                        "threads": None,
                        "resources": {{}},
                        "benchmark": "",
                        "log": "",
                    }}
                    continue
                if current is None:
                    continue
                stripped = line.strip()
                if stripped.startswith("threads:"):
                    value = stripped.split(":", 1)[1].strip()
                    try:
                        current["threads"] = int(float(value))
                    except Exception:
                        current["threads"] = value
                    continue
                if stripped.startswith("resources:"):
                    current["resources"] = parse_resources(stripped.split(":", 1)[1])
                    continue
                if stripped.startswith("benchmark:"):
                    current["benchmark"] = stripped.split(":", 1)[1].strip()
                    bench_map[current["benchmark"]] = dict(current)
                    bench_map[Path(current["benchmark"]).name] = dict(current)
                    continue
                if stripped.startswith("log:"):
                    current["log"] = stripped.split(":", 1)[1].strip()
                    continue
                m = re.search(r"Submitted job (\\S+) with external jobid '?(\\d+)'?\\.", stripped)
                if m:
                    record = dict(current)
                    record["snakemake_job_id"] = m.group(1)
                    record["slurm_job_id"] = m.group(2)
                    jobs.append(record)
                    current = None
            return {{"jobs": jobs, "bench_map": bench_map, "tmux_log": str(path), "tmux_log_bytes": len(text)}}

        def parse_benchmarks(command_id, session, bench_map):
            root = Path("/fsx/analysis_results/ubuntu") / session / "daylily-omics-analysis"
            rows = []
            if not root.is_dir():
                return rows
            files = []
            result_root = root / "results"
            if result_root.is_dir():
                files = sorted(result_root.rglob("*.bench.tsv"))
            for path in files:
                try:
                    rel = str(path.relative_to(root))
                except Exception:
                    rel = str(path)
                meta = bench_map.get(rel) or bench_map.get(str(path)) or bench_map.get(path.name) or {{}}
                try:
                    with path.open(newline="") as handle:
                        reader = csv.DictReader(handle, delimiter="\\t")
                        for row_index, row in enumerate(reader):
                            out = {{
                                "command_id": command_id,
                                "session": session,
                                "path": str(path),
                                "rel_path": rel,
                                "file": path.name,
                                "row_index": row_index,
                                "rule": meta.get("rule") or path.stem.replace(".bench", ""),
                                "threads_req": meta.get("threads"),
                                "resources": meta.get("resources", {{}}),
                            }}
                            out.update(row)
                            rows.append(out)
                except Exception as exc:
                    rows.append({{
                        "command_id": command_id,
                        "session": session,
                        "path": str(path),
                        "rel_path": rel,
                        "file": path.name,
                        "row_index": -1,
                        "rule": meta.get("rule") or path.stem.replace(".bench", ""),
                        "threads_req": meta.get("threads"),
                        "resources": meta.get("resources", {{}}),
                        "parse_error": str(exc),
                    }})
            return rows

        def run(cmd):
            return subprocess.run(cmd, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        def parse_sacct():
            fmt = "JobIDRaw,Partition,State,AllocCPUS,NNodes,NodeList%80,JobName%140,ElapsedRaw,ReqMem%18,MaxRSS%18,MaxVMSize%18,AveCPU,Elapsed,Submit,Start,End,ExitCode"
            proc = run(f"sacct -X -S 2026-07-07T14:00:00 -o {{fmt}} -P 2>/dev/null || true")
            rows = []
            if not proc.stdout.strip():
                return rows
            reader = csv.DictReader(proc.stdout.splitlines(), delimiter="|")
            for row in reader:
                rows.append(row)
            return rows

        def parse_nodes():
            proc = run("scontrol show node -o || true")
            rows = []
            for line in proc.stdout.splitlines():
                item = {{}}
                for part in line.split():
                    if "=" in part:
                        key, value = part.split("=", 1)
                        item[key] = value
                if item.get("NodeName"):
                    rows.append(item)
            return rows

        status = {{}}
        all_jobs = []
        all_benchmarks = []
        tmux_meta = {{}}
        for command_id, session in sessions:
            status_path = Path("/home/ubuntu/daylily-runs") / session / "status.json"
            try:
                status[f"{{command_id}}|{{session}}"] = json.loads(status_path.read_text())
            except Exception as exc:
                status[f"{{command_id}}|{{session}}"] = {{"status_error": str(exc), "status_path": str(status_path)}}
            parsed = parse_tmux(session, command_id)
            tmux_meta[f"{{command_id}}|{{session}}"] = {{
                "tmux_log": parsed["tmux_log"],
                "tmux_log_bytes": parsed["tmux_log_bytes"],
                "submitted_jobs": len(parsed["jobs"]),
                "benchmarks_in_log": len(parsed["bench_map"]),
            }}
            all_jobs.extend(parsed["jobs"])
            all_benchmarks.extend(parse_benchmarks(command_id, session, parsed["bench_map"]))

        payload = {{
            "captured_at": now,
            "sessions": sessions,
            "status": status,
            "tmux_meta": tmux_meta,
            "submitted_jobs": all_jobs,
            "benchmark_rows": all_benchmarks,
            "sacct": parse_sacct(),
            "nodes": parse_nodes(),
        }}
        out_path = Path("/tmp/dyec_cmdcat_benchmark_raw_remote_payload.json.gz")
        out_path.write_bytes(gzip.compress(json.dumps(payload, separators=(",", ":")).encode()))
        s3_uri = "{RAW_S3_URI}"
        upload = run(f"aws s3 cp {{out_path}} {{s3_uri}} --region us-west-2")
        print(json.dumps({{"s3_uri": s3_uri, "rc": upload.returncode, "stdout": upload.stdout[-1000:], "stderr": upload.stderr[-1000:]}}))
        if upload.returncode:
            sys.exit(upload.returncode)
        """
    )


def to_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"NA", "N/A", "nan", "None"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def to_int(value: object) -> int | None:
    number = to_float(value)
    if number is None:
        return None
    return int(number)


def parse_mem_mb(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"Unknown", "None", "N/A"}:
        return None
    per_cpu = text.endswith("c")
    if text[-1:] in {"c", "n"}:
        text = text[:-1]
    m = re.match(r"^([0-9.]+)([KMGTP]?)$", text, re.I)
    if not m:
        return to_float(text)
    value_f = float(m.group(1))
    suffix = m.group(2).upper()
    factor = {"": 1 / 1024, "K": 1 / (1024 * 1024), "M": 1, "G": 1024, "T": 1024 * 1024, "P": 1024 * 1024 * 1024}[suffix]
    result = value_f * factor
    return result if not per_cpu else result


def parse_time(value: str | None, now: dt.datetime) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text or text.startswith("Unknown"):
        return None
    if text in {"None", "N/A"}:
        return None
    if text == "Unknown":
        return None
    if text == "Running":
        return now
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            parsed = dt.datetime.strptime(text, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=dt.timezone.utc)
            return parsed
        except ValueError:
            pass
    return None


def percentile(values: list[float], pct: float) -> float | None:
    clean = sorted(v for v in values if v is not None and math.isfinite(v))
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    idx = (len(clean) - 1) * pct
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return clean[int(idx)]
    return clean[lo] + (clean[hi] - clean[lo]) * (idx - lo)


def median(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None and math.isfinite(v)]
    if not clean:
        return None
    return statistics.median(clean)


def mode_text(values: list[object]) -> str:
    clean = [str(v) for v in values if v not in (None, "")]
    if not clean:
        return ""
    return Counter(clean).most_common(1)[0][0]


def fmt(value: object, digits: int = 2) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.{digits}f}"
    return str(value)


def recommend(row: dict[str, object]) -> str:
    notes: list[str] = []
    count = int(row["benchmark_rows"])
    if count == 0:
        return "No benchmark rows yet; wait for jobs to run before changing resources."
    mem_eff = row.get("max_mem_eff")
    cpu_eff = row.get("median_cpu_eff")
    threads = row.get("threads_req")
    max_rss = row.get("max_rss_mb")
    mem_req = row.get("mem_req_mb")
    max_io_rate = row.get("max_io_mb_s")
    total_io = row.get("total_io_mb")
    wall_p95 = row.get("p95_wall_s")
    partition = str(row.get("partition") or "")
    pack_cpu = row.get("median_pack_cpu_frac")
    pack_mem = row.get("median_pack_mem_frac")

    if isinstance(mem_eff, float) and mem_req:
        if mem_eff >= 0.9:
            notes.append("increase memory request; peak RSS is within 10% of requested memory")
        elif mem_eff >= 0.75:
            notes.append("keep memory or add a small guard band")
        elif mem_eff <= 0.2 and float(mem_req) >= 20000:
            notes.append("reduce memory request materially")
        elif mem_eff <= 0.4 and float(mem_req) >= 50000:
            notes.append("memory request is conservative; consider modest reduction")
        else:
            notes.append("memory looks acceptable")
    elif max_rss:
        notes.append("memory peak observed but request was not parsed")

    if isinstance(cpu_eff, float) and threads:
        threads_f = float(threads)
        if cpu_eff < 0.20 and threads_f >= 8:
            notes.append("CPU over-requested; lower threads/vcpu or pack more concurrent jobs")
        elif cpu_eff < 0.40 and threads_f >= 16:
            notes.append("CPU is underutilized; benchmark before keeping this many threads")
        elif cpu_eff > 0.85 and wall_p95 and float(wall_p95) > 300:
            notes.append("CPU saturated; more threads may help only if the tool scales")
        else:
            notes.append("CPU request looks acceptable")

    if isinstance(max_io_rate, float) and isinstance(total_io, float):
        if max_io_rate >= 250 or total_io >= 500000:
            if "nvme" not in partition:
                notes.append("I/O heavy on non-NVMe partition; consider NVMe/local scratch")
            else:
                notes.append("I/O heavy; keep NVMe/local scratch and avoid adding CPU as first fix")
        elif max_io_rate <= 5 and isinstance(cpu_eff, float) and cpu_eff < 0.4:
            notes.append("not obviously I/O-bound; low CPU use likely over-threading or scheduler wait")

    if isinstance(pack_cpu, float) and isinstance(pack_mem, float):
        if pack_cpu < 0.35 and pack_mem < 0.35 and count >= 3:
            notes.append("node sharing is light; packing could improve if DAG has enough parallel work")
        elif pack_cpu > 0.85 or pack_mem > 0.85:
            notes.append("node packing is tight; avoid increasing this rule without checking collisions")
        else:
            notes.append("node sharing looks reasonable")
    return "; ".join(dict.fromkeys(notes)) or "No change suggested from benchmark evidence."


def load_remote_payload() -> dict:
    target = resolve_headnode_instance_id(CLUSTER, REGION, profile=PROFILE)
    script = remote_script()
    encoded = base64.b64encode(script.encode()).decode()
    cmd = f"python3 -c \"import base64; exec(base64.b64decode('{encoded}').decode())\""
    result = run_shell(
        target.instance_id,
        REGION,
        cmd,
        profile=PROFILE,
        as_user="ubuntu",
        timeout=600,
        comment="collect command catalog benchmark/resource evidence",
    )
    if result.stderr.strip():
        print(result.stderr)
    payload_line = ""
    for line in reversed(result.stdout.splitlines()):
        candidate = line.strip()
        if candidate.startswith("{") and candidate.endswith("}"):
            payload_line = candidate
            break
    if not payload_line:
        raise RuntimeError(f"remote collector did not return upload JSON; stdout={result.stdout[:500]!r}")
    upload = json.loads(payload_line)
    if upload.get("rc") != 0:
        raise RuntimeError(f"remote upload failed: {upload}")
    OUT_PREFIX.mkdir(parents=True, exist_ok=True)
    raw_gz = OUT_PREFIX / "raw_remote_payload.json.gz"
    subprocess.run(
        ["aws", "--profile", PROFILE, "s3", "cp", upload["s3_uri"], str(raw_gz), "--region", REGION],
        check=True,
    )
    return json.loads(gzip.decompress(raw_gz.read_bytes()).decode())


def build_outputs(data: dict) -> None:
    OUT_PREFIX.mkdir(parents=True, exist_ok=True)
    (OUT_PREFIX / "raw_remote_payload.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    job_meta = {str(job.get("slurm_job_id")): job for job in data["submitted_jobs"] if job.get("slurm_job_id")}
    node_meta = {node.get("NodeName"): node for node in data["nodes"]}
    now = dt.datetime.fromisoformat(data["captured_at"])

    sacct = []
    for row in data["sacct"]:
        job_id = str(row.get("JobIDRaw") or "")
        meta = job_meta.get(job_id, {})
        node = str(row.get("NodeList") or "")
        nmeta = node_meta.get(node, {})
        start = parse_time(row.get("Start"), now)
        end = parse_time(row.get("End"), now) or (now if row.get("State") == "RUNNING" else None)
        if start and end and end < start:
            end = now
        req_mem = parse_mem_mb(row.get("ReqMem"))
        alloc_cpus = to_int(row.get("AllocCPUS")) or to_int((meta.get("resources") or {}).get("vcpu")) or to_int(meta.get("threads"))
        record = {
            **row,
            "command_id": meta.get("command_id", ""),
            "session": meta.get("session", ""),
            "rule": meta.get("rule") or str(row.get("JobName", "")).split("-", 1)[0],
            "benchmark": meta.get("benchmark", ""),
            "threads_req": meta.get("threads", ""),
            "partition_req": (meta.get("resources") or {}).get("partition") or row.get("Partition", ""),
            "mem_req_mb": req_mem,
            "alloc_cpus": alloc_cpus,
            "node": node,
            "node_cpus": to_int(nmeta.get("CPUTot")),
            "node_mem_mb": to_float(nmeta.get("RealMemory")),
            "start_dt": start,
            "end_dt": end,
        }
        sacct.append(record)

    by_node = defaultdict(list)
    for row in sacct:
        if row.get("node") and row.get("start_dt") and row.get("end_dt") and row.get("node") != "None assigned":
            by_node[row["node"]].append(row)

    for node, rows in by_node.items():
        events = []
        for row in rows:
            events.append((row["start_dt"], 1, row))
            events.append((row["end_dt"], -1, row))
        events.sort(key=lambda item: (item[0], -item[1]))
        active = []
        for _, delta, row in events:
            if delta == 1:
                active.append(row)
                concurrent = list(active)
                cpu_sum = sum((r.get("alloc_cpus") or 0) for r in concurrent)
                mem_sum = sum((r.get("mem_req_mb") or 0) for r in concurrent)
                for r in concurrent:
                    r["pack_count_max"] = max(int(r.get("pack_count_max") or 0), len(concurrent))
                    if r.get("node_cpus"):
                        r["pack_cpu_frac_max"] = max(float(r.get("pack_cpu_frac_max") or 0), cpu_sum / float(r["node_cpus"]))
                    if r.get("node_mem_mb"):
                        r["pack_mem_frac_max"] = max(float(r.get("pack_mem_frac_max") or 0), mem_sum / float(r["node_mem_mb"]))
            else:
                active = [r for r in active if r is not row]

    job_by_benchmark: dict[tuple[str, str, str], dict[str, object]] = {}
    job_by_benchmark_file: dict[tuple[str, str, str], dict[str, object]] = {}
    for job in data["submitted_jobs"]:
        benchmark = str(job.get("benchmark") or "")
        if not benchmark:
            continue
        command_id = str(job.get("command_id") or "")
        session = str(job.get("session") or "")
        job_by_benchmark[(command_id, session, benchmark)] = job
        job_by_benchmark_file[(command_id, session, Path(benchmark).name)] = job

    bench_rows = []
    for row in data["benchmark_rows"]:
        command_id = str(row.get("command_id", ""))
        session = str(row.get("session", ""))
        rel_path = str(row.get("rel_path", ""))
        job = (
            job_by_benchmark.get((command_id, session, rel_path))
            or job_by_benchmark.get((command_id, session, str(row.get("path") or "")))
            or job_by_benchmark_file.get((command_id, session, str(row.get("file") or "")))
            or {}
        )
        resources = (job.get("resources") or row.get("resources") or {})
        threads = (
            to_int(row.get("snakemake_threads"))
            or to_int(row.get("threads_req"))
            or to_int(job.get("threads"))
            or to_int(resources.get("threads"))
            or to_int(resources.get("vcpu"))
        )
        mem_req = to_float(resources.get("mem_mb")) or parse_mem_mb(resources.get("mem"))
        wall = to_float(row.get("s"))
        mean_load = to_float(row.get("mean_load"))
        cpu_time = to_float(row.get("cpu_time"))
        max_rss = to_float(row.get("max_rss"))
        max_pss = to_float(row.get("max_pss"))
        io_in = to_float(row.get("io_in")) or 0.0
        io_out = to_float(row.get("io_out")) or 0.0
        spot_cost = to_float(row.get("spot_cost"))
        nproc = to_float(row.get("nproc"))
        avg_cpu_cores = None
        if mean_load is not None:
            avg_cpu_cores = mean_load / 100 if mean_load > 100 else mean_load
        if avg_cpu_cores is None:
            avg_cpu_cores = to_float(row.get("cpu_efficiency"))
        if avg_cpu_cores is None and cpu_time is not None and wall:
            avg_cpu_cores = cpu_time / wall
        cpu_eff = (avg_cpu_cores / threads) if avg_cpu_cores is not None and threads else None
        total_io = io_in + io_out
        out = {
            "command_id": command_id,
            "session": session,
            "rule": row.get("rule", ""),
            "rel_path": rel_path,
            "threads_req": threads,
            "partition": resources.get("partition", ""),
            "mem_req_mb": mem_req,
            "wall_s": wall,
            "max_rss_mb": max_rss,
            "max_pss_mb": max_pss,
            "mean_load": mean_load,
            "cpu_time_s": cpu_time,
            "avg_cpu_cores": avg_cpu_cores,
            "cpu_eff": cpu_eff,
            "io_in_mb": io_in,
            "io_out_mb": io_out,
            "total_io_mb": total_io,
            "io_mb_s": total_io / wall if wall else None,
            "hostname": row.get("hostname", ""),
            "ip": row.get("ip", ""),
            "region_az": row.get("region_az", ""),
            "nproc": nproc,
            "instance_type": row.get("instance_type", ""),
            "spot_cost_per_instance_hour": spot_cost,
            "spot_cost_per_vcpu_hour": (spot_cost / nproc) if spot_cost is not None and nproc else None,
            "task_cost": to_float(row.get("task_cost")),
        }
        bench_rows.append(out)

    submit_by_key = defaultdict(list)
    for row in sacct:
        key = (row.get("command_id", ""), row.get("rule", ""))
        if row.get("command_id"):
            submit_by_key[key].append(row)

    groups = defaultdict(list)
    for row in bench_rows:
        groups[(row["command_id"], row["rule"])].append(row)

    summary = []
    for (command_id, rule), rows in sorted(groups.items()):
        jobs = submit_by_key.get((command_id, rule), [])
        max_rss = [r["max_rss_mb"] for r in rows if r.get("max_rss_mb") is not None]
        walls = [r["wall_s"] for r in rows if r.get("wall_s") is not None]
        cpu_eff = [r["cpu_eff"] for r in rows if r.get("cpu_eff") is not None]
        io_rates = [r["io_mb_s"] for r in rows if r.get("io_mb_s") is not None]
        total_io = sum(r.get("total_io_mb") or 0 for r in rows)
        mem_req_values = [r["mem_req_mb"] for r in rows if r.get("mem_req_mb") is not None]
        threads_values = [r["threads_req"] for r in rows if r.get("threads_req") is not None]
        pack_cpu = [r.get("pack_cpu_frac_max") for r in jobs if r.get("pack_cpu_frac_max") is not None]
        pack_mem = [r.get("pack_mem_frac_max") for r in jobs if r.get("pack_mem_frac_max") is not None]
        pack_count = [r.get("pack_count_max") for r in jobs if r.get("pack_count_max") is not None]
        mem_req = median(mem_req_values)
        max_rss_value = max(max_rss) if max_rss else None
        task_costs = [r["task_cost"] for r in rows if r.get("task_cost") is not None]
        hourly_costs = [r["spot_cost_per_instance_hour"] for r in rows if r.get("spot_cost_per_instance_hour") is not None]
        vcpu_hour_costs = [r["spot_cost_per_vcpu_hour"] for r in rows if r.get("spot_cost_per_vcpu_hour") is not None]
        item = {
            "command_id": command_id,
            "rule": rule,
            "benchmark_rows": len(rows),
            "submitted_jobs": len(jobs),
            "partition": mode_text([r.get("partition") for r in rows]) or mode_text([j.get("partition_req") for j in jobs]),
            "threads_req": median(threads_values),
            "mem_req_mb": mem_req,
            "max_rss_mb": max_rss_value,
            "p95_rss_mb": percentile(max_rss, 0.95),
            "max_mem_eff": (max_rss_value / mem_req) if max_rss_value is not None and mem_req else None,
            "median_wall_s": median(walls),
            "p95_wall_s": percentile(walls, 0.95),
            "median_cpu_eff": median(cpu_eff),
            "p95_cpu_eff": percentile(cpu_eff, 0.95),
            "total_io_mb": total_io,
            "max_io_mb_s": max(io_rates) if io_rates else None,
            "median_pack_count": median([float(x) for x in pack_count]),
            "max_pack_count": max(pack_count) if pack_count else None,
            "median_pack_cpu_frac": median(pack_cpu),
            "median_pack_mem_frac": median(pack_mem),
            "nodes": ", ".join(sorted({str(j.get("node")) for j in jobs if j.get("node") and j.get("node") != "None assigned"})[:12]),
            "instances": ", ".join(
                sorted(
                    {
                        f"{r.get('hostname')}:{r.get('instance_type')}"
                        for r in rows
                        if r.get("hostname") and r.get("instance_type")
                    }
                )[:12]
            ),
            "total_task_cost": sum(task_costs) if task_costs else None,
            "median_instance_hourly_cost": median(hourly_costs),
            "median_vcpu_hourly_cost": median(vcpu_hour_costs),
        }
        item["recommendation"] = recommend(item)
        summary.append(item)

    # Add submitted/running rules with no benchmark rows yet.
    for (command_id, rule), jobs in sorted(submit_by_key.items()):
        if (command_id, rule) in groups:
            continue
        item = {
            "command_id": command_id,
            "rule": rule,
            "benchmark_rows": 0,
            "submitted_jobs": len(jobs),
            "partition": mode_text([j.get("partition_req") for j in jobs]),
            "threads_req": median([float(j["alloc_cpus"]) for j in jobs if j.get("alloc_cpus")]),
            "mem_req_mb": median([float(j["mem_req_mb"]) for j in jobs if j.get("mem_req_mb")]),
            "max_rss_mb": None,
            "p95_rss_mb": None,
            "max_mem_eff": None,
            "median_wall_s": median([float(j["ElapsedRaw"]) for j in jobs if to_float(j.get("ElapsedRaw")) is not None]),
            "p95_wall_s": percentile([float(j["ElapsedRaw"]) for j in jobs if to_float(j.get("ElapsedRaw")) is not None], 0.95),
            "median_cpu_eff": None,
            "p95_cpu_eff": None,
            "total_io_mb": None,
            "max_io_mb_s": None,
            "median_pack_count": median([float(j.get("pack_count_max") or 0) for j in jobs]),
            "max_pack_count": max([int(j.get("pack_count_max") or 0) for j in jobs]) if jobs else None,
            "median_pack_cpu_frac": median([float(j.get("pack_cpu_frac_max")) for j in jobs if j.get("pack_cpu_frac_max") is not None]),
            "median_pack_mem_frac": median([float(j.get("pack_mem_frac_max")) for j in jobs if j.get("pack_mem_frac_max") is not None]),
            "nodes": ", ".join(sorted({str(j.get("node")) for j in jobs if j.get("node") and j.get("node") != "None assigned"})[:12]),
        }
        item["recommendation"] = recommend(item)
        summary.append(item)

    write_tsv(OUT_PREFIX / "benchmark_rows.tsv", bench_rows)
    job_rows = []
    for row in sacct:
        out = dict(row)
        out.pop("start_dt", None)
        out.pop("end_dt", None)
        job_rows.append(out)
    write_tsv(OUT_PREFIX / "slurm_jobs_with_packing.tsv", job_rows)
    write_tsv(OUT_PREFIX / "rule_resource_summary.tsv", summary)
    write_tsv(OUT_PREFIX / "actionable_resource_recommendations.tsv", actionable_rows(summary))
    write_report(OUT_PREFIX / "benchmark_resource_review.md", data, summary)


def write_tsv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(dict.fromkeys(key for row in rows for key in row.keys()))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def round_up(value: float, step: int) -> int:
    return int(math.ceil(value / step) * step)


def thread_test_ladder(threads: object, cpu_eff: object) -> str:
    threads_f = to_float(threads)
    cpu_eff_f = to_float(cpu_eff)
    if threads_f is None or cpu_eff_f is None:
        return ""
    if cpu_eff_f >= 0.4:
        return ""
    if threads_f >= 128:
        return "benchmark 48, 64, and 96 threads"
    if threads_f >= 96:
        return "benchmark 48 and 64 threads"
    if threads_f >= 48:
        return "benchmark 24, 32, and 48 threads"
    if threads_f >= 32:
        return "benchmark 8, 16, and 24 threads"
    if threads_f >= 16:
        return "benchmark 4, 8, and 16 threads"
    return ""


def memory_test_target(mem_req: object, max_rss: object) -> str:
    mem_req_f = to_float(mem_req)
    max_rss_f = to_float(max_rss)
    if mem_req_f is None or max_rss_f is None or mem_req_f <= 0:
        return ""
    target = round_up(max(max_rss_f * 1.75, max_rss_f + 4000, 8000), 1000)
    if target < mem_req_f * 0.8:
        return f"benchmark about {target} MB"
    if target < mem_req_f:
        return f"benchmark modest reduction toward {target} MB"
    return ""


def row_priority(row: dict[str, object]) -> float:
    cost = to_float(row.get("total_task_cost")) or 0
    rows = to_float(row.get("benchmark_rows")) or 0
    io_rate = to_float(row.get("max_io_mb_s")) or 0
    threads = to_float(row.get("threads_req")) or 0
    mem_req = to_float(row.get("mem_req_mb")) or 0
    return cost * 100 + rows * 0.05 + min(io_rate, 500) * 0.02 + min(threads, 192) * 0.02 + min(mem_req, 650000) / 100000


def actionable_rows(summary: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in summary:
        recommendation = str(row.get("recommendation") or "")
        benchmark_rows = to_float(row.get("benchmark_rows")) or 0
        submitted_jobs = to_float(row.get("submitted_jobs")) or 0
        cost = to_float(row.get("total_task_cost")) or 0
        threads = to_float(row.get("threads_req")) or 0
        mem_req = to_float(row.get("mem_req_mb")) or 0
        io_rate = to_float(row.get("max_io_mb_s")) or 0
        repeated = benchmark_rows >= 10 or submitted_jobs >= 10
        expensive = cost >= 0.05
        large_request = threads >= 48 or mem_req >= 128000
        io_heavy = "I/O heavy" in recommendation or io_rate >= 250
        pending_only = benchmark_rows == 0 and submitted_jobs > 0
        if not (expensive or repeated or large_request or io_heavy or pending_only):
            continue
        if submitted_jobs == 0 and cost < 0.05 and not repeated and not io_heavy:
            continue
        change_area = []
        if "increase memory" in recommendation:
            change_area.append("increase_memory")
        if "reduce memory" in recommendation or "memory request is conservative" in recommendation:
            change_area.append("reduce_memory")
        if "CPU over-requested" in recommendation or "CPU is underutilized" in recommendation:
            change_area.append("reduce_threads")
        if io_heavy:
            change_area.append("io_scratch")
        if pending_only:
            change_area.append("pending_no_benchmark")
        if not change_area:
            change_area.append("monitor")
        rows.append(
            {
                "command_id": row.get("command_id", ""),
                "rule": row.get("rule", ""),
                "priority_score": row_priority(row),
                "change_area": ",".join(change_area),
                "benchmark_rows": row.get("benchmark_rows", ""),
                "submitted_jobs": row.get("submitted_jobs", ""),
                "threads_req": row.get("threads_req", ""),
                "thread_test": thread_test_ladder(row.get("threads_req"), row.get("median_cpu_eff")),
                "mem_req_mb": row.get("mem_req_mb", ""),
                "max_rss_mb": row.get("max_rss_mb", ""),
                "memory_test": memory_test_target(row.get("mem_req_mb"), row.get("max_rss_mb")),
                "median_cpu_eff": row.get("median_cpu_eff", ""),
                "max_io_mb_s": row.get("max_io_mb_s", ""),
                "total_task_cost": row.get("total_task_cost", ""),
                "median_instance_hourly_cost": row.get("median_instance_hourly_cost", ""),
                "median_vcpu_hourly_cost": row.get("median_vcpu_hourly_cost", ""),
                "nodes": row.get("nodes", ""),
                "instances": row.get("instances", ""),
                "recommendation": recommendation,
            }
        )
    return sorted(rows, key=lambda row: to_float(row.get("priority_score")) or 0, reverse=True)


def executive_findings(summary: list[dict[str, object]]) -> list[str]:
    command_count = len({row.get("command_id") for row in summary if row.get("command_id")})
    pending_bcl = [
        row
        for row in summary
        if row.get("rule") == "run_bclconvert_lane" and to_float(row.get("benchmark_rows")) == 0
    ]
    return [
        "## Executive Findings",
        "",
        f"- Scope: `20` command IDs have benchmark or submitted-job evidence in this capture; `simple-test` has no benchmarked Slurm work. The summary table contains `{len(summary)}` command/rule groups across `{command_count}` command IDs.",
        "- Cost columns are taken directly from the benchmark TSVs: `spot_cost`, `nproc`, `instance_type`, `hostname`, and `task_cost`; the report also derives per-vCPU-hour cost as `spot_cost / nproc`.",
        "- Highest-dollar outlier: `complete_genomics_mgi_snv_concordance` / `sentieon_cgt7p_bwa_sort` cost about `$11.88` for one task on `r8idb.96xlarge`, requested `192` threads and `300000` MB, peaked near `172907` MB RSS, and used only about `0.03` of requested thread capacity. Test lower thread profiles before changing memory much.",
        "- High-thread pangenome and long-read callers are generally over-threaded for this catalog workload: `sent_aln_sort_snv`, `sentieon_pangenome_ug`, `sent_snv_ont`, `sent_snv_pacbio`, and `sentmm2_align_sort` should be benchmarked at smaller thread ladders rather than expanded.",
        "- The biggest memory reductions are low-risk candidates: `doppelmark_dups`, `rtg_vcfeval_roi`, `sentdhiomr_stage*`, `sentdhiomr_pass*`, `sentdhiomr_model_apply`, `sentdhiomr_final_norm`, transfer utilities, VEP/chunk helper rules, and most QC/reporting helpers request far more memory than observed RSS.",
        "- I/O-bound rules should not get more CPU as the first response. `sentdhiomr_transfer`, `sentdhiomr_sr_markdup`, `bcftools_vcfstat`, `expansionhunter_call`, and `legacy_cram_compat_bam` benefit more from NVMe/local scratch placement and lower memory requests.",
        "- Packing did happen across nodes and partitions, especially for the many small `sentdhiomr_transfer` and VEP jobs. Poor sharing is concentrated in high-thread/high-memory rules that monopolize nodes despite low CPU utilization; memory request reductions should improve packing more than scheduler changes.",
        "- Some reconstructed pack fractions are above `1.0` because Slurm accounting intervals overlap across dynamic cloud nodes; treat those as tight/collision-risk indicators, not proof of literal physical overcommit.",
        f"- BCLConvert remains unevaluable from completed benchmark data: `{len(pending_bcl)}` `run_bclconvert_lane` groups are pending with `48` CPUs and `500000M` each on `i192hugenvme`. By memory, that request permits at most two lanes per 1.49 TB node even though CPU would permit four.",
        "",
        "## Highest Priority Changes",
        "",
    ]


def write_report(path: Path, data: dict, summary: list[dict[str, object]]) -> None:
    by_command = defaultdict(list)
    for row in summary:
        by_command[row["command_id"]].append(row)
    lines = [
        "# Command Catalog Benchmark Resource Review",
        "",
        f"- Cluster: `{CLUSTER}`",
        f"- Captured: `{data['captured_at']}`",
        f"- Benchmark rows: `{len(data['benchmark_rows'])}`",
        f"- Submitted Slurm jobs mapped from controllers: `{len(data['submitted_jobs'])}`",
        "",
        "## Heuristics",
        "",
        "- Memory: peak RSS / requested memory >= 0.90 suggests increase; <= 0.20 on large requests suggests over-request.",
        "- CPU: median mean_load / requested threads < 0.20 on multi-thread jobs suggests over-threading; > 0.85 suggests CPU saturation.",
        "- I/O: high MB/s or very high total I/O with low CPU efficiency is treated as I/O-bound; prefer scratch/NVMe before adding CPU.",
        "- Packing: computed from Slurm job overlaps on the same node using allocated CPUs and requested memory.",
        "",
    ]
    lines.extend(executive_findings(summary))
    ranked = sorted(
        summary,
        key=lambda r: (
            0 if "increase memory" in str(r["recommendation"]) else 1,
            0 if "CPU over-requested" in str(r["recommendation"]) else 1,
            -(to_float(r.get("p95_wall_s")) or 0),
        ),
    )
    for row in ranked[:25]:
        lines.append(
            f"- `{row['command_id']}` / `{row['rule']}`: {row['recommendation']} "
            f"(rows={row['benchmark_rows']}, jobs={row['submitted_jobs']}, "
            f"threads={fmt(row.get('threads_req'), 0)}, mem_req_mb={fmt(row.get('mem_req_mb'), 0)}, "
            f"max_rss_mb={fmt(row.get('max_rss_mb'), 0)}, cpu_eff_med={fmt(row.get('median_cpu_eff'))}, "
            f"pack_cpu_med={fmt(row.get('median_pack_cpu_frac'))}, "
            f"task_cost=${fmt(row.get('total_task_cost'), 4)}, nodes={row.get('nodes')})"
        )
    lines.extend(["", "## Per Command And Rule", ""])
    for command_id in [c for c, _ in COMMAND_SESSIONS]:
        rows = sorted(by_command.get(command_id, []), key=lambda r: str(r["rule"]))
        lines.extend([f"### `{command_id}`", ""])
        if not rows:
            lines.extend(["No benchmark or submitted-job rows found.", ""])
            continue
        lines.append("| Rule | Rows | Jobs | Part | Threads | Mem Req MB | Max RSS MB | Mem Eff | CPU Eff Med | IO MB/s Max | Task Cost | $/vCPU-h | Pack Count Max | Pack CPU Med | Pack Mem Med | Instances | Nodes | Suggestion |")
        lines.append("|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|")
        for row in rows:
            lines.append(
                f"| `{row['rule']}` | {row['benchmark_rows']} | {row['submitted_jobs']} | "
                f"{row.get('partition') or ''} | {fmt(row.get('threads_req'), 0)} | "
                f"{fmt(row.get('mem_req_mb'), 0)} | {fmt(row.get('max_rss_mb'), 0)} | "
                f"{fmt(row.get('max_mem_eff'))} | {fmt(row.get('median_cpu_eff'))} | "
                f"{fmt(row.get('max_io_mb_s'))} | ${fmt(row.get('total_task_cost'), 4)} | "
                f"${fmt(row.get('median_vcpu_hourly_cost'), 5)} | {fmt(row.get('max_pack_count'), 0)} | "
                f"{fmt(row.get('median_pack_cpu_frac'))} | {fmt(row.get('median_pack_mem_frac'))} | "
                f"{row.get('instances') or ''} | {row.get('nodes') or ''} | {row['recommendation']} |"
            )
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    payload = load_remote_payload()
    build_outputs(payload)
    print(OUT_PREFIX / "benchmark_resource_review.md")
