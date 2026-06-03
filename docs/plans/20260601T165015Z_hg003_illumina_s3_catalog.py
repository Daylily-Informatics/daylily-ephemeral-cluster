#!/usr/bin/env python3
"""Catalog HG003 Illumina run directories in the LSMC sequencing bucket."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import boto3
from botocore.exceptions import ClientError


HG003_TOKEN = re.compile(r"(?i)(?:^|[^A-Za-z0-9])(hg003[A-Za-z0-9_.-]*)")
FASTQ_SUFFIXES = (".fastq.gz", ".fq.gz", ".fastq", ".fq")
SAMPLE_SHEET_NAME = re.compile(r"(?i)(^|[/_.-])sample[ _-]?sheet.*\.(csv|tsv|txt)$")
RUNINFO_CANDIDATES = ("RunInfo.xml", "runInfo.xml", "RunInfo.XML")
RUNPARAM_CANDIDATES = (
    "RunParameters.xml",
    "runParameters.xml",
    "RunParameters.XML",
    "RunParameters.json",
)
RUN_PREFIX_NAME = re.compile(r"(?i)^[0-9]{8}_[a-z0-9]+_[0-9]{4}_[ab]?[a-z0-9]+/$")


@dataclass
class S3Object:
    key: str
    size: int
    last_modified: str


@dataclass
class SampleSheetHit:
    sample_sheet_key: str
    sample_sheet_size: int
    sample_sheet_last_modified: str
    run_prefix: str
    run_info_key: str = ""
    matching_values: set[str] = field(default_factory=set)
    matching_rows: list[dict[str, str]] = field(default_factory=list)
    header_values: dict[str, str] = field(default_factory=dict)
    parse_error: str = ""


def human_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if value < 1024 or unit == "PiB":
            return f"{value:.2f} {unit}" if unit != "B" else f"{size} B"
        value /= 1024
    raise AssertionError("unreachable")


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def s3_uri(bucket: str, key: str) -> str:
    return f"s3://{bucket}/{key}"


def key_parent_prefix(key: str) -> str:
    stripped = key.rstrip("/")
    parent = stripped.rsplit("/", 1)[0] if "/" in stripped else ""
    return f"{parent}/" if parent else ""


def prefix_parents(prefix: str) -> Iterable[str]:
    current = prefix.rstrip("/")
    while current:
        yield f"{current}/"
        if "/" not in current:
            break
        current = current.rsplit("/", 1)[0]


def has_hg003_token(value: str) -> bool:
    return bool(HG003_TOKEN.search(value or ""))


def hg003_tokens(value: str) -> list[str]:
    return [match.group(1) for match in HG003_TOKEN.finditer(value or "")]


def list_objects(s3: Any, bucket: str, prefix: str) -> Iterable[S3Object]:
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            yield S3Object(
                key=item["Key"],
                size=int(item.get("Size", 0)),
                last_modified=item["LastModified"].astimezone(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            )


def list_prefix_level(s3: Any, bucket: str, prefix: str) -> tuple[list[S3Object], list[str]]:
    objects: list[S3Object] = []
    prefixes: list[str] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
        for item in page.get("Contents", []):
            objects.append(
                S3Object(
                    key=item["Key"],
                    size=int(item.get("Size", 0)),
                    last_modified=item["LastModified"].astimezone(timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                )
            )
        prefixes.extend(item["Prefix"] for item in page.get("CommonPrefixes", []))
    return objects, prefixes


def object_exists(s3: Any, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise
    return True


def read_text_object(s3: Any, bucket: str, key: str, max_bytes: int = 16 * 1024 * 1024) -> str:
    obj = s3.get_object(Bucket=bucket, Key=key)
    body = obj["Body"].read(max_bytes + 1)
    if len(body) > max_bytes:
        raise ValueError(f"object is larger than {max_bytes} bytes")
    return body.decode("utf-8-sig", errors="replace")


def find_run_info_key(s3: Any, bucket: str, sample_sheet_key: str) -> tuple[str, str]:
    for parent in prefix_parents(key_parent_prefix(sample_sheet_key)):
        for name in RUNINFO_CANDIDATES:
            key = f"{parent}{name}"
            if object_exists(s3, bucket, key):
                return parent, key
    return key_parent_prefix(sample_sheet_key), ""


def root_has_runinfo(s3: Any, bucket: str, prefix: str) -> bool:
    return any(object_exists(s3, bucket, f"{prefix}{name}") for name in RUNINFO_CANDIDATES)


def discover_run_prefixes(
    s3: Any,
    bucket: str,
    prefixes: list[str],
    *,
    max_depth: int,
) -> tuple[list[str], dict[str, int]]:
    stats = {"prefixes_visited": 0, "run_prefixes_discovered": 0}
    discovered: set[str] = set()
    queue: list[tuple[str, int]] = [(prefix, 0) for prefix in prefixes]
    while queue:
        prefix, depth = queue.pop(0)
        stats["prefixes_visited"] += 1
        objects, children = list_prefix_level(s3, bucket, prefix)
        basename = prefix.rstrip("/").rsplit("/", 1)[-1] + "/"
        root_sample_sheet = any(SAMPLE_SHEET_NAME.search(obj.key.rsplit("/", 1)[-1]) for obj in objects)
        root_runinfo = any(obj.key.rsplit("/", 1)[-1] in RUNINFO_CANDIDATES for obj in objects)
        looks_like_run = bool(RUN_PREFIX_NAME.match(basename))
        if root_sample_sheet or root_runinfo or (looks_like_run and root_has_runinfo(s3, bucket, prefix)):
            discovered.add(prefix)
            continue
        if depth >= max_depth:
            continue
        for child in children:
            queue.append((child, depth + 1))
    stats["run_prefixes_discovered"] = len(discovered)
    return sorted(discovered), stats


def parse_sample_sheet(text: str) -> tuple[set[str], list[dict[str, str]], dict[str, str]]:
    section = ""
    section_header: list[str] | None = None
    matching_values: set[str] = set()
    matching_rows: list[dict[str, str]] = []
    header_values: dict[str, str] = {}

    reader = csv.reader(io.StringIO(text))
    for line_number, raw_row in enumerate(reader, start=1):
        row = [cell.strip() for cell in raw_row]
        if not row or all(not cell for cell in row):
            continue
        first = row[0]
        if first.startswith("[") and first.endswith("]"):
            section = first.strip("[]")
            section_header = None
            continue

        if section.lower() == "header" and len(row) >= 2 and row[0]:
            header_values[row[0]] = row[1]

        if section.lower() not in {"data", "bclconvert_data"}:
            for value in row:
                for token in hg003_tokens(value):
                    matching_values.add(token)
            continue

        if section_header is None:
            section_header = row
            continue

        values = dict(zip(section_header, row))
        sample_like = {
            key: value
            for key, value in values.items()
            if "sample" in key.lower() or key.lower() in {"description", "project"}
        }
        searchable_values = list(sample_like.values()) or row
        row_tokens: set[str] = set()
        for value in searchable_values:
            row_tokens.update(hg003_tokens(value))
        if row_tokens:
            matching_values.update(row_tokens)
            record = {"section": section, "line_number": str(line_number)}
            record.update(values)
            matching_rows.append(record)

    return matching_values, matching_rows, header_values


def parse_run_info(text: str) -> dict[str, str]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        return {"run_info_parse_error": str(exc)}
    run = root.find(".//Run")
    if run is None:
        return {"run_info_parse_error": "missing Run element"}
    reads = []
    for read in run.findall(".//Read"):
        reads.append(
            ":".join(
                [
                    read.attrib.get("Number", ""),
                    read.attrib.get("NumCycles", ""),
                    read.attrib.get("IsIndexedRead", ""),
                ]
            )
        )
    flowcell_layout = root.find(".//FlowcellLayout")
    metadata = {
        "run_id": run.attrib.get("Id", ""),
        "run_number": run.attrib.get("Number", ""),
        "flowcell": (run.findtext("Flowcell") or "").strip(),
        "instrument": (run.findtext("Instrument") or "").strip(),
        "run_date": (run.findtext("Date") or "").strip(),
        "reads": ";".join(reads),
    }
    if flowcell_layout is not None:
        metadata.update(
            {
                "lane_count": flowcell_layout.attrib.get("LaneCount", ""),
                "surface_count": flowcell_layout.attrib.get("SurfaceCount", ""),
                "swath_count": flowcell_layout.attrib.get("SwathCount", ""),
                "tile_count": flowcell_layout.attrib.get("TileCount", ""),
            }
        )
    return metadata


def maybe_read_run_metadata(s3: Any, bucket: str, run_prefix: str, run_info_key: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    if run_info_key:
        metadata["run_info_key"] = run_info_key
        try:
            metadata.update(parse_run_info(read_text_object(s3, bucket, run_info_key)))
        except Exception as exc:  # noqa: BLE001
            metadata["run_info_read_error"] = str(exc)
    else:
        metadata["run_info_key"] = ""

    present = []
    for name in RUNPARAM_CANDIDATES:
        key = f"{run_prefix}{name}"
        if object_exists(s3, bucket, key):
            present.append(key)
    rta_key = f"{run_prefix}RTAComplete.txt"
    if object_exists(s3, bucket, rta_key):
        present.append(rta_key)
    metadata["run_metadata_sidecars"] = ";".join(present)
    return metadata


def find_sample_sheet_hits(
    s3: Any,
    bucket: str,
    prefixes: list[str],
    run_prefixes: list[str] | None = None,
) -> tuple[list[SampleSheetHit], dict[str, int]]:
    stats = {
        "objects_scanned": 0,
        "sample_sheet_candidates": 0,
        "sample_sheets_read": 0,
        "sample_sheets_with_hg003": 0,
    }
    hits: list[SampleSheetHit] = []
    seen_keys: set[str] = set()

    if run_prefixes is not None:
        for run_prefix in run_prefixes:
            print(f"[scan] checking root sample sheets under {s3_uri(bucket, run_prefix)}", file=sys.stderr)
            root_objects, _ = list_prefix_level(s3, bucket, run_prefix)
            stats["objects_scanned"] += len(root_objects)
            candidates = [
                obj for obj in root_objects if SAMPLE_SHEET_NAME.search(obj.key.rsplit("/", 1)[-1])
            ]
            stats["sample_sheet_candidates"] += len(candidates)
            for obj in candidates:
                if obj.key in seen_keys:
                    continue
                seen_keys.add(obj.key)
                try:
                    text = read_text_object(s3, bucket, obj.key)
                    stats["sample_sheets_read"] += 1
                    matching_values, matching_rows, header_values = parse_sample_sheet(text)
                    parse_error = ""
                except Exception as exc:  # noqa: BLE001
                    matching_values, matching_rows, header_values = set(), [], {}
                    parse_error = str(exc)
                if not matching_values and not has_hg003_token(obj.key):
                    continue
                run_info_key = next(
                    (
                        f"{run_prefix}{name}"
                        for name in RUNINFO_CANDIDATES
                        if object_exists(s3, bucket, f"{run_prefix}{name}")
                    ),
                    "",
                )
                hits.append(
                    SampleSheetHit(
                        sample_sheet_key=obj.key,
                        sample_sheet_size=obj.size,
                        sample_sheet_last_modified=obj.last_modified,
                        run_prefix=run_prefix,
                        run_info_key=run_info_key,
                        matching_values=matching_values,
                        matching_rows=matching_rows,
                        header_values=header_values,
                        parse_error=parse_error,
                    )
                )
                stats["sample_sheets_with_hg003"] += 1
        return hits, stats

    for prefix in prefixes:
        print(f"[scan] listing sample-sheet candidates under s3://{bucket}/{prefix}", file=sys.stderr)
        for obj in list_objects(s3, bucket, prefix):
            stats["objects_scanned"] += 1
            basename = obj.key.rsplit("/", 1)[-1]
            if not SAMPLE_SHEET_NAME.search(basename):
                continue
            if obj.key in seen_keys:
                continue
            seen_keys.add(obj.key)
            stats["sample_sheet_candidates"] += 1
            try:
                text = read_text_object(s3, bucket, obj.key)
                stats["sample_sheets_read"] += 1
                matching_values, matching_rows, header_values = parse_sample_sheet(text)
                parse_error = ""
            except Exception as exc:  # noqa: BLE001
                matching_values, matching_rows, header_values = set(), [], {}
                parse_error = str(exc)
            if not matching_values and not has_hg003_token(obj.key):
                continue
            run_prefix, run_info_key = find_run_info_key(s3, bucket, obj.key)
            hit = SampleSheetHit(
                sample_sheet_key=obj.key,
                sample_sheet_size=obj.size,
                sample_sheet_last_modified=obj.last_modified,
                run_prefix=run_prefix,
                run_info_key=run_info_key,
                matching_values=matching_values,
                matching_rows=matching_rows,
                header_values=header_values,
                parse_error=parse_error,
            )
            hits.append(hit)
            stats["sample_sheets_with_hg003"] += 1
    return hits, stats


def fastq_sample_token(key: str) -> str:
    basename = key.rsplit("/", 1)[-1]
    stem = basename
    for suffix in FASTQ_SUFFIXES:
        if stem.lower().endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    stem = re.split(r"_S[0-9]+(?:_|$)", stem, maxsplit=1)[0]
    stem = re.split(r"_L[0-9]{3}(?:_|$)", stem, maxsplit=1)[0]
    stem = re.split(r"_R[12](?:_|$)", stem, maxsplit=1)[0]
    if has_hg003_token(stem):
        return stem
    tokens = hg003_tokens(basename)
    if tokens:
        return tokens[0]
    tokens = hg003_tokens(key)
    return tokens[0] if tokens else ""


def list_matching_fastqs(s3: Any, bucket: str, run_prefix: str) -> tuple[list[dict[str, str]], dict[str, int]]:
    details: list[dict[str, str]] = []
    stats = {"fastq_objects_scanned": 0, "matching_fastq_count": 0, "matching_fastq_bytes": 0}
    for obj in list_objects(s3, bucket, run_prefix):
        stats["fastq_objects_scanned"] += 1
        lower = obj.key.lower()
        if not lower.endswith(FASTQ_SUFFIXES):
            continue
        token = fastq_sample_token(obj.key)
        if not token:
            continue
        lane_match = re.search(r"_L([0-9]{3})_", obj.key)
        read_match = re.search(r"_R([12])_", obj.key)
        details.append(
            {
                "run_prefix": run_prefix,
                "fastq_key": obj.key,
                "fastq_uri": s3_uri(bucket, obj.key),
                "sample_token": token,
                "lane": lane_match.group(1) if lane_match else "",
                "read": read_match.group(1) if read_match else "",
                "size_bytes": str(obj.size),
                "size_human": human_bytes(obj.size),
                "last_modified": obj.last_modified,
            }
        )
        stats["matching_fastq_count"] += 1
        stats["matching_fastq_bytes"] += obj.size
    return details, stats


def write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def make_markdown_report(
    path: Path,
    *,
    bucket: str,
    prefixes: list[str],
    stats: dict[str, int],
    run_rows: list[dict[str, Any]],
    samplesheet_rows: list[dict[str, Any]],
    generated_at: str,
) -> None:
    lines = [
        "# HG003 Illumina Run Directory Catalog",
        "",
        f"Generated: `{generated_at}`",
        f"Bucket: `s3://{bucket}/`",
        f"Prefixes scanned: `{', '.join(prefixes)}`",
        "",
        "## Scan Summary",
        "",
        f"- Objects scanned while looking for sample sheets: `{stats.get('objects_scanned', 0)}`",
        f"- Sample sheet candidates: `{stats.get('sample_sheet_candidates', 0)}`",
        f"- Sample sheets read: `{stats.get('sample_sheets_read', 0)}`",
        f"- Sample sheets with HG003 evidence: `{stats.get('sample_sheets_with_hg003', 0)}`",
        f"- Matching run directories: `{len(run_rows)}`",
        "",
        "## Matching Runs",
        "",
        "| Run directory | Flowcell | Instrument | Run date | HG003 samples | HG003 FASTQs | HG003 FASTQ size | RunInfo |",
        "|---|---:|---:|---:|---|---:|---:|---|",
    ]
    for row in run_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['run_uri']}`",
                    row.get("flowcell") or "",
                    row.get("instrument") or "",
                    row.get("run_date") or "",
                    row.get("matching_samples") or "",
                    str(row.get("matching_fastq_count") or "0"),
                    row.get("matching_fastq_size_human") or "0 B",
                    f"`{row.get('run_info_uri', '')}`" if row.get("run_info_uri") else "missing",
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Sample Sheet Evidence",
            "",
            "| Sample sheet | Run directory | Matching values | Matching row count | Parse error |",
            "|---|---|---|---:|---|",
        ]
    )
    for row in samplesheet_rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['sample_sheet_uri']}`",
                    f"`{row['run_uri']}`",
                    row.get("matching_values", ""),
                    str(row.get("matching_row_count", "0")),
                    row.get("parse_error", ""),
                ]
            )
            + " |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--bucket", default="lsmc-ssf-sequencing-data")
    parser.add_argument("--prefix", action="append", dest="prefixes")
    parser.add_argument("--out-prefix", required=True)
    parser.add_argument("--discover-run-roots", action="store_true")
    parser.add_argument("--max-depth", type=int, default=8)
    args = parser.parse_args()

    prefixes = args.prefixes or ["basecalls/", "raw/"]
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    s3 = session.client("s3")

    generated_at = now_utc()
    discovery_stats: dict[str, int] = {}
    run_prefixes: list[str] | None = None
    if args.discover_run_roots:
        run_prefixes, discovery_stats = discover_run_prefixes(
            s3,
            args.bucket,
            prefixes,
            max_depth=args.max_depth,
        )
        print(
            json.dumps(
                {"discovery_stats": discovery_stats, "run_prefixes": run_prefixes},
                indent=2,
            ),
            file=sys.stderr,
        )
    hits, scan_stats = find_sample_sheet_hits(s3, args.bucket, prefixes, run_prefixes=run_prefixes)
    scan_stats.update({f"discovery_{key}": value for key, value in discovery_stats.items()})
    by_run: dict[str, list[SampleSheetHit]] = defaultdict(list)
    for hit in hits:
        by_run[hit.run_prefix].append(hit)

    run_rows: list[dict[str, Any]] = []
    samplesheet_rows: list[dict[str, Any]] = []
    sample_rows: list[dict[str, Any]] = []
    fastq_rows: list[dict[str, Any]] = []

    for run_prefix in sorted(by_run):
        run_hits = by_run[run_prefix]
        run_info_key = next((hit.run_info_key for hit in run_hits if hit.run_info_key), "")
        metadata = maybe_read_run_metadata(s3, args.bucket, run_prefix, run_info_key)
        print(f"[scan] listing matching FASTQs under {s3_uri(args.bucket, run_prefix)}", file=sys.stderr)
        run_fastqs, fastq_stats = list_matching_fastqs(s3, args.bucket, run_prefix)
        fastq_rows.extend(run_fastqs)

        matching_values = sorted({value for hit in run_hits for value in hit.matching_values}, key=str.lower)
        sample_sheet_keys = [hit.sample_sheet_key for hit in run_hits]
        row = {
            "generated_at": generated_at,
            "bucket": args.bucket,
            "run_prefix": run_prefix,
            "run_uri": s3_uri(args.bucket, run_prefix),
            "run_dir_name": run_prefix.rstrip("/").rsplit("/", 1)[-1],
            "sample_sheet_count": str(len(run_hits)),
            "sample_sheet_uris": ";".join(s3_uri(args.bucket, key) for key in sample_sheet_keys),
            "matching_samples": ";".join(matching_values),
            "run_info_key": metadata.get("run_info_key", ""),
            "run_info_uri": s3_uri(args.bucket, metadata["run_info_key"]) if metadata.get("run_info_key") else "",
            "run_id": metadata.get("run_id", ""),
            "run_number": metadata.get("run_number", ""),
            "flowcell": metadata.get("flowcell", ""),
            "instrument": metadata.get("instrument", ""),
            "run_date": metadata.get("run_date", ""),
            "reads": metadata.get("reads", ""),
            "lane_count": metadata.get("lane_count", ""),
            "run_metadata_sidecars": metadata.get("run_metadata_sidecars", ""),
            "run_info_parse_error": metadata.get("run_info_parse_error", ""),
            "run_info_read_error": metadata.get("run_info_read_error", ""),
            "matching_fastq_count": str(fastq_stats["matching_fastq_count"]),
            "matching_fastq_size_bytes": str(fastq_stats["matching_fastq_bytes"]),
            "matching_fastq_size_human": human_bytes(fastq_stats["matching_fastq_bytes"]),
            "fastq_objects_scanned_under_run": str(fastq_stats["fastq_objects_scanned"]),
        }
        run_rows.append(row)

        for hit in run_hits:
            samplesheet_row = {
                "generated_at": generated_at,
                "bucket": args.bucket,
                "run_prefix": hit.run_prefix,
                "run_uri": s3_uri(args.bucket, hit.run_prefix),
                "sample_sheet_key": hit.sample_sheet_key,
                "sample_sheet_uri": s3_uri(args.bucket, hit.sample_sheet_key),
                "sample_sheet_size": str(hit.sample_sheet_size),
                "sample_sheet_last_modified": hit.sample_sheet_last_modified,
                "matching_values": ";".join(sorted(hit.matching_values, key=str.lower)),
                "matching_row_count": str(len(hit.matching_rows)),
                "parse_error": hit.parse_error,
                "header_values_json": json.dumps(hit.header_values, sort_keys=True),
            }
            samplesheet_rows.append(samplesheet_row)
            for match in hit.matching_rows:
                sample_rows.append(
                    {
                        "generated_at": generated_at,
                        "sample_sheet_key": hit.sample_sheet_key,
                        "sample_sheet_uri": s3_uri(args.bucket, hit.sample_sheet_key),
                        "run_prefix": hit.run_prefix,
                        "run_uri": s3_uri(args.bucket, hit.run_prefix),
                        "row_json": json.dumps(match, sort_keys=True),
                    }
                )

    out_prefix = Path(args.out_prefix)
    run_tsv = out_prefix.with_suffix(".runs.tsv")
    samplesheet_tsv = out_prefix.with_suffix(".samplesheets.tsv")
    sample_rows_tsv = out_prefix.with_suffix(".sample_rows.tsv")
    fastq_tsv = out_prefix.with_suffix(".fastqs.tsv")
    json_path = out_prefix.with_suffix(".json")
    md_path = out_prefix.with_suffix(".md")

    run_fields = [
        "generated_at",
        "bucket",
        "run_prefix",
        "run_uri",
        "run_dir_name",
        "sample_sheet_count",
        "sample_sheet_uris",
        "matching_samples",
        "run_info_key",
        "run_info_uri",
        "run_id",
        "run_number",
        "flowcell",
        "instrument",
        "run_date",
        "reads",
        "lane_count",
        "run_metadata_sidecars",
        "run_info_parse_error",
        "run_info_read_error",
        "matching_fastq_count",
        "matching_fastq_size_bytes",
        "matching_fastq_size_human",
        "fastq_objects_scanned_under_run",
    ]
    sample_sheet_fields = [
        "generated_at",
        "bucket",
        "run_prefix",
        "run_uri",
        "sample_sheet_key",
        "sample_sheet_uri",
        "sample_sheet_size",
        "sample_sheet_last_modified",
        "matching_values",
        "matching_row_count",
        "parse_error",
        "header_values_json",
    ]
    fastq_fields = [
        "run_prefix",
        "fastq_key",
        "fastq_uri",
        "sample_token",
        "lane",
        "read",
        "size_bytes",
        "size_human",
        "last_modified",
    ]
    write_tsv(run_tsv, run_rows, run_fields)
    write_tsv(samplesheet_tsv, samplesheet_rows, sample_sheet_fields)
    write_tsv(sample_rows_tsv, sample_rows, ["generated_at", "sample_sheet_key", "sample_sheet_uri", "run_prefix", "run_uri", "row_json"])
    write_tsv(fastq_tsv, fastq_rows, fastq_fields)
    json_path.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "bucket": args.bucket,
                "prefixes": prefixes,
                "scan_stats": scan_stats,
                "runs": run_rows,
                "sample_sheets": samplesheet_rows,
                "sample_rows": sample_rows,
                "fastqs": fastq_rows,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    make_markdown_report(
        md_path,
        bucket=args.bucket,
        prefixes=prefixes,
        stats=scan_stats,
        run_rows=run_rows,
        samplesheet_rows=samplesheet_rows,
        generated_at=generated_at,
    )
    print(json.dumps({"scan_stats": scan_stats, "run_count": len(run_rows), "outputs": [str(run_tsv), str(samplesheet_tsv), str(sample_rows_tsv), str(fastq_tsv), str(json_path), str(md_path)]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
