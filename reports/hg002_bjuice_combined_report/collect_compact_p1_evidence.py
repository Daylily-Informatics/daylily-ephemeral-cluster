#!/usr/bin/env python3
"""Collect bounded read-only P1 evidence from the exported Bjuice v0.9 E1 root.

The production point is positioned with native short-read (SR) coverage, not
realigned-short-read (RSR) coverage.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
from datetime import timezone
from pathlib import Path
from typing import Any

import boto3


BUCKET = "lsmc-ssf-sequencing-data"
DAYOA_PREFIX = (
    "derived/pcand-18022/pcand18022-bjuice-preval6-15014-dry-20260817t112900z/"
    "daylily-omics-analysis/"
)
RUNTIME_AU = "HG002-qvmjccyp5fr1y3"
SOURCE_AU = "BJUICEPREVAL6-HG002-HIOMRS"
ANALYSIS_ROOT = f"s3://{BUCKET}/{DAYOA_PREFIX.rstrip('/')}"
CALLER_NAMES = {
    "tagged_trussv": "TrussSV",
    "sniffles2": "Sniffles2",
    "longreadsv": "LongReadSV",
    "tiddit": "TIDDIT",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", default="lsmc")
    parser.add_argument("--region", default="us-west-2")
    return parser.parse_args()


def rows(data: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(data.decode("utf-8")), delimiter="\t"))


def list_keys(client: Any, prefix: str) -> list[str]:
    paginator = client.get_paginator("list_objects_v2")
    keys: list[str] = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        keys.extend(item["Key"] for item in page.get("Contents", []) if item["Key"] and not item["Key"].endswith("/"))
    return sorted(keys)


def total_mean(data: bytes) -> str:
    for row in rows(data):
        if row.get("chrom") == "total":
            return row["mean"]
    raise ValueError("Mosdepth summary does not contain chrom=total")


def vcf_counts(data: bytes) -> tuple[int, int]:
    passed = 0
    failed = 0
    with gzip.GzipFile(fileobj=io.BytesIO(data), mode="rb") as handle:
        for raw in handle:
            if raw.startswith(b"#"):
                continue
            fields = raw.decode("utf-8").rstrip("\n").split("\t")
            if len(fields) < 10:
                continue
            sample = dict(zip(fields[8].split(":"), fields[9].split(":")))
            alleles = re.split(r"[/|]", sample.get("GT", "NA"))
            if not any(allele not in {"0", ".", ""} for allele in alleles):
                continue
            if fields[6] == "PASS":
                passed += 1
            else:
                failed += 1
    return passed, failed


def main() -> None:
    args = parse_args()
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    client = session.client("s3")
    fetched: dict[str, bytes] = {}
    inventory: dict[str, dict[str, Any]] = {}

    def fetch(key: str) -> bytes:
        if key in fetched:
            return fetched[key]
        response = client.get_object(Bucket=BUCKET, Key=key)
        data = response["Body"].read()
        last_modified = response["LastModified"].astimezone(timezone.utc)
        inventory[key] = {
            "relative_path": key.removeprefix(DAYOA_PREFIX),
            "bytes": len(data),
            "mtime_epoch": int(last_modified.timestamp()),
            "sha256": hashlib.sha256(data).hexdigest(),
            "etag": response["ETag"].strip('"'),
            "s3_uri": f"s3://{BUCKET}/{key}",
        }
        fetched[key] = data
        return data

    report_prefix = DAYOA_PREFIX + "results/day/hg38/reports/"
    manifest_prefix = report_prefix + "input_manifests/"
    manifest_keys = list_keys(client, manifest_prefix)
    required_manifests = {
        "analysis_unit_identity_audit.tsv",
        "analysis_unit_inputs.tsv",
        "analysis_units.tsv",
        "libraries.tsv",
        "resolved_analysis_units.tsv",
        "samples.tsv",
        "sequencing_inputs.tsv",
        "specimens.tsv",
    }
    discovered_manifests = {key.removeprefix(manifest_prefix) for key in manifest_keys}
    if discovered_manifests != required_manifests:
        raise ValueError(f"unexpected input-manifest set: {sorted(discovered_manifests)}")
    manifest_data = {key.removeprefix(manifest_prefix): fetch(key) for key in manifest_keys}

    config_key = DAYOA_PREFIX + "config/bjuice_preval6_hiomr2.yaml"
    evidence_key = report_prefix + "dayoa_evidence_manifest.json"
    benchmark_key = report_prefix + "benchmarks_summary.tsv"
    config_text = fetch(config_key).decode("utf-8")
    if "HG002: fastq" not in config_text:
        raise ValueError("P1 config does not confirm HG002 fastq long-read input mode")
    evidence_manifest = json.loads(fetch(evidence_key).decode("utf-8"))
    benchmark_rows = [
        {field: row.get(field, "") for field in ("sample", "status", "rule", "s", "task_cost", "cpu_time", "snakemake_threads", "start_datetime", "end_datetime")}
        for row in rows(fetch(benchmark_key))
        if row.get("sample", "").rstrip(".") == RUNTIME_AU and row.get("status") == "success"
    ]
    if not benchmark_rows:
        raise ValueError(f"no successful benchmark rows for {RUNTIME_AU}")

    units = [row for row in rows(manifest_data["analysis_units.tsv"]) if row.get("ANALYSIS_UNIT_UID") == SOURCE_AU]
    identities = [row for row in rows(manifest_data["analysis_unit_identity_audit.tsv"]) if row.get("RUNTIME_ANALYSIS_UNIT_UID") == RUNTIME_AU]
    if len(units) != 1 or len(identities) != 1:
        raise ValueError(f"expected one source/runtime P1 unit, found {len(units)=} {len(identities)=}")
    unit = units[0]
    identity = identities[0]
    if identity.get("SOURCE_ANALYSIS_UNIT_UID") != SOURCE_AU or unit.get("SAMPLEID") != "HG002":
        raise ValueError("P1 manifest identity does not resolve to HG002")
    if "SR downsample full; ONT downsample full" not in unit.get("ANALYSIS_UNIT_COMMENT", ""):
        raise ValueError("P1 manifest comment does not attest full SR and ONT inputs")

    unit_prefix = DAYOA_PREFIX + f"results/day/hg38/{RUNTIME_AU}/"
    unit_keys = list_keys(client, unit_prefix)
    patterns = {
        "ilmn": re.compile(r"/align/sentdhiomr2sr/smd/alignqc/mosdepth/[^/]+\.summary\.txt$"),
        "ont": re.compile(r"/align/sentdhiomr2lr/na/alignqc/mosdepth/[^/]+\.summary\.txt$"),
        "hard": re.compile(r"/concordance/_giabHC/[^/]+_concordance\.mqc\.tsv$"),
        "smn": re.compile(r"/align/sentdhiomr2sr/smd/htd/smn12/[^/]+\.summary\.json$"),
        "truvari": re.compile(r"/slim-consensus/truvari/[^/]+/queries/[^/]+/truvari/summary\.json$"),
        "segdup": re.compile(r"/align/sentmm2ont/na/snv/sentdhiomr2/segdup/[^/]+/[^/]+/[^/]+\.result\.vcf\.gz$"),
    }
    selected = {name: [key for key in unit_keys if pattern.search(key)] for name, pattern in patterns.items()}
    expected_counts = {"ilmn": 1, "ont": 1, "hard": 1, "smn": 1, "truvari": 4}
    for name, expected in expected_counts.items():
        if len(selected[name]) != expected:
            raise ValueError(f"P1 expected {expected} {name} artifact(s), found {len(selected[name])}")
    if not selected["segdup"]:
        raise ValueError("P1 has no SegDup VCF artifacts")

    ilmn_key = selected["ilmn"][0]
    ont_key = selected["ont"][0]
    hard_key = selected["hard"][0]
    smn_key = selected["smn"][0]
    coverage = {
        RUNTIME_AU: {
            "ilmn": total_mean(fetch(ilmn_key)),
            "ont": total_mean(fetch(ont_key)),
            "ilmn_source": ilmn_key.removeprefix(DAYOA_PREFIX),
            "ont_source": ont_key.removeprefix(DAYOA_PREFIX),
        }
    }
    hard_vcf = {
        RUNTIME_AU: {
            "source_path": hard_key.removeprefix(DAYOA_PREFIX),
            "rows": rows(fetch(hard_key)),
        }
    }
    truvari = {RUNTIME_AU: []}
    for key in selected["truvari"]:
        caller = Path(key).parts[-3]
        truvari[RUNTIME_AU].append(
            {
                "caller": CALLER_NAMES.get(caller, caller),
                "source_path": key.removeprefix(DAYOA_PREFIX),
                "summary": json.loads(fetch(key).decode("utf-8")),
            }
        )
    segdup = {RUNTIME_AU: {}}
    for key in selected["segdup"]:
        gene = Path(key).parent.name
        passed, failed = vcf_counts(fetch(key))
        segdup[RUNTIME_AU][gene] = {
            "source_path": key.removeprefix(DAYOA_PREFIX),
            "pass_count": passed,
            "failed_count": failed,
        }
    smn12 = {
        RUNTIME_AU: {
            "source_path": smn_key.removeprefix(DAYOA_PREFIX),
            "payload": json.loads(fetch(smn_key).decode("utf-8")),
        }
    }
    payload = {
        "analysis_root": ANALYSIS_ROOT,
        "source_s3_prefix": f"s3://{BUCKET}/{DAYOA_PREFIX}",
        "execution_label": "Bjuice v0.9 production execution 1",
        "input_contract": {
            "short_read": "full",
            "long_read_window": "[0,24)",
            "coverage_target": None,
        },
        "coverage_measurement_contract": {
            "short_read": "native SR (sentdhiomr2sr/smd; not RSR)",
            "long_read": "LR (sentdhiomr2lr/na)",
            "metric": "Mosdepth chrom=total mean",
        },
        "units": units,
        "identity": identities,
        "coverage": coverage,
        "hard_vcf": hard_vcf,
        "truvari": truvari,
        "smn12": smn12,
        "segdup": segdup,
        "benchmarks": benchmark_rows,
        "evidence_manifest_sha256": inventory[evidence_key]["sha256"],
        "inventory": [inventory[key] for key in sorted(inventory)],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "runtime_au": RUNTIME_AU,
                "sr_coverage": coverage[RUNTIME_AU]["ilmn"],
                "lr_coverage": coverage[RUNTIME_AU]["ont"],
                "benchmark_rows": len(benchmark_rows),
                "segdup_files": len(segdup[RUNTIME_AU]),
                "inventory_files": len(payload["inventory"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
