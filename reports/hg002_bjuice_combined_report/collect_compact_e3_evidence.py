#!/usr/bin/env python3
"""Collect bounded, read-only E3 evidence through the DYEC headnode CLI."""

from __future__ import annotations

import argparse
import base64
import gzip
import json
import subprocess
from pathlib import Path


ANALYSIS_ROOT = "/fsx/analysis_results/prod-cand-1703/prod-cand-1703-hg002-bjuice-4au-kitchensink-20260817T025004Z"


REMOTE_SCRIPT = r'''
import base64, csv, gzip, hashlib, json
from pathlib import Path

analysis_root = Path("__ANALYSIS_ROOT__")
mode = "__MODE__"
runtime_filter = "__RUNTIME__"
dayoa_root = analysis_root / "daylily-omics-analysis"
results = dayoa_root / "results/day/hg38"
manifest = results / "reports/input_manifests"

def rows(path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))

def rel(path):
    return str(path.relative_to(dayoa_root))

def meta(path):
    stat = path.stat()
    return {
        "relative_path": rel(path),
        "bytes": stat.st_size,
        "mtime_epoch": int(stat.st_mtime),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }

def total_mean(path):
    for row in rows(path):
        if row["chrom"] == "total":
            return row["mean"]
    raise ValueError(f"missing total coverage in {path}")

def vcf_records(path):
    out = []
    with gzip.open(path, "rt") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 10:
                continue
            sample = dict(zip(fields[8].split(":"), fields[9].split(":")))
            gt = sample.get("GT", "NA")
            if not any(value not in {"0", ".", ""} for value in gt.replace("|", "/").split("/")):
                continue
            ref = fields[3] if len(fields[3]) <= 120 else f"<{len(fields[3])}bp>"
            alt = fields[4] if len(fields[4]) <= 120 else f"<{len(fields[4])}bp>"
            out.append({"chrom": fields[0], "pos": fields[1], "ref": ref, "alt": alt, "qual": fields[5], "filter": fields[6], "gt": gt})
    return out

unit_rows = rows(manifest / "analysis_units.tsv")
identity_rows = rows(manifest / "analysis_unit_identity_audit.tsv")
source_by_uid = {row["ANALYSIS_UNIT_UID"]: row for row in unit_rows}
benchmark_fields = ("sample", "status", "rule", "s", "task_cost", "cpu_time", "snakemake_threads", "start_datetime", "end_datetime")
benchmark_rows = [
    {field: row.get(field, "") for field in benchmark_fields}
    for row in rows(results / "reports/benchmarks_summary.tsv")
    if row.get("status") == "success" and (not runtime_filter or row.get("sample", "").rstrip(".") == runtime_filter)
]
output = {
    "analysis_root": str(analysis_root),
    "units": unit_rows,
    "identity": identity_rows,
    "coverage": {},
    "hard_vcf": {},
    "truvari": {},
    "smn12": {},
    "segdup": {},
    "benchmarks": benchmark_rows,
    "inventory": [],
}
for required in [manifest / "analysis_units.tsv", manifest / "analysis_unit_identity_audit.tsv", results / "reports/benchmarks_summary.tsv"]:
    output["inventory"].append(meta(required))

caller_names = {"tagged_trussv": "TrussSV", "sniffles2": "Sniffles2", "longreadsv": "LongReadSV", "tiddit": "TIDDIT"}
for identity in identity_rows:
    runtime = identity["RUNTIME_ANALYSIS_UNIT_UID"]
    if runtime_filter and runtime != runtime_filter:
        continue
    root = results / runtime
    ilmn = list(root.glob("align/sentdhiomr2rsr/na/alignqc/mosdepth/*.summary.txt"))
    ont = list(root.glob("align/sentdhiomr2lr/na/alignqc/mosdepth/*.summary.txt"))
    hard = list(root.glob("align/sentmm2ont/na/snv/sentdhiomr2/concordance/_giabHC/*_concordance.mqc.tsv"))
    smn = list(root.glob("align/sentdhiomr2sr/smd/htd/smn12/*.summary.json"))
    truvari = sorted(root.glob("align/sentmm2ont/na/snv/sentdhiomr2/slim-consensus/truvari/*/queries/*/truvari/summary.json"))
    segdup = sorted(root.glob("align/sentmm2ont/na/snv/sentdhiomr2/segdup/*/*/*.result.vcf.gz"))
    if not (len(ilmn) == len(ont) == len(hard) == len(smn) == 1 and len(truvari) == 4 and segdup):
        raise ValueError(f"unexpected artifact cardinality for {runtime}: {len(ilmn)=} {len(ont)=} {len(hard)=} {len(smn)=} {len(truvari)=} {len(segdup)=}")
    output["coverage"][runtime] = {"ilmn": total_mean(ilmn[0]), "ont": total_mean(ont[0]), "ilmn_source": rel(ilmn[0]), "ont_source": rel(ont[0])}
    output["hard_vcf"][runtime] = {"source_path": rel(hard[0]), "rows": rows(hard[0])}
    output["truvari"][runtime] = []
    for path in truvari:
        output["truvari"][runtime].append({"caller": caller_names.get(path.parents[1].name, path.parents[1].name), "source_path": rel(path), "summary": json.loads(path.read_text())})
    output["smn12"][runtime] = {"source_path": rel(smn[0]), "payload": json.loads(smn[0].read_text())}
    output["segdup"][runtime] = {}
    for path in segdup:
        records = vcf_records(path)
        output["segdup"][runtime][path.parent.name] = {
            "source_path": rel(path),
            "pass_count": sum(record["filter"] == "PASS" for record in records),
            "failed_count": sum(record["filter"] != "PASS" for record in records),
        }
    for path in ilmn + ont + hard + smn + truvari + segdup:
        output["inventory"].append(meta(path))

if mode == "basic":
    output.pop("segdup")
    output.pop("benchmarks")
    output["inventory"] = [item for item in output["inventory"] if "/segdup/" not in item["relative_path"]]
elif mode == "segdup":
    output = {"analysis_root": output["analysis_root"], "segdup": output["segdup"], "inventory": [item for item in output["inventory"] if "/segdup/" in item["relative_path"]]}
elif mode == "benchmarks":
    output = {"analysis_root": output["analysis_root"], "benchmarks": output["benchmarks"], "inventory": [item for item in output["inventory"] if item["relative_path"].endswith("benchmarks_summary.tsv")]}
else:
    raise ValueError(f"unsupported compact-evidence mode: {mode}")
blob = gzip.compress(json.dumps(output, sort_keys=True, separators=(",", ":")).encode())
print(base64.b64encode(blob).decode())
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("basic", "segdup", "benchmarks", "merge"), default="merge")
    parser.add_argument("--runtime-au")
    args = parser.parse_args()
    def collect(mode: str, runtime_au: str | None = None) -> dict:
        script = (
            REMOTE_SCRIPT.replace("__ANALYSIS_ROOT__", ANALYSIS_ROOT)
            .replace("__MODE__", mode)
            .replace("__RUNTIME__", runtime_au or "")
        )
        payload = base64.b64encode(script.encode()).decode()
        command = f"echo {payload} | base64 -d | python3 -"
        result = subprocess.run(
            [
                "dyec", "--json", "headnode", "run", command,
                "--profile", "lsmc", "--region", "us-west-2", "--cluster", "prod-cand-1703",
                "--remote-user", "ubuntu", "--timeout", "300",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        response = json.loads(result.stdout)
        if not response.get("ok") or response.get("response_code") != 0:
            raise RuntimeError(response)
        encoded = response["stdout"].strip().splitlines()[-1]
        return json.loads(gzip.decompress(base64.b64decode(encoded)))

    if args.mode == "merge":
        basic_path = args.output.with_name("compact_evidence.basic.json")
        segdup_paths = sorted(args.output.parent.glob("compact_evidence.segdup.*.json"))
        benchmark_paths = sorted(args.output.parent.glob("compact_evidence.benchmarks.*.json"))
        if not basic_path.is_file() or len(segdup_paths) != 4 or len(benchmark_paths) != 4:
            raise RuntimeError("collect basic, segdup, and benchmarks evidence before merge")
        evidence = json.loads(basic_path.read_text())
        evidence["segdup"] = {}
        evidence["benchmarks"] = []
        for path in segdup_paths:
            segdup = json.loads(path.read_text())
            evidence["segdup"].update(segdup["segdup"])
            evidence["inventory"].extend(segdup["inventory"])
        for path in benchmark_paths:
            benchmarks = json.loads(path.read_text())
            evidence["benchmarks"].extend(benchmarks["benchmarks"])
            evidence["inventory"].extend(benchmarks["inventory"])
    else:
        evidence = collect(args.mode) if args.mode == "basic" else collect(args.mode, args.runtime_au)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output), "inventory_files": len(evidence["inventory"]), "units": len(evidence.get("identity", []))}, indent=2))


if __name__ == "__main__":
    main()
