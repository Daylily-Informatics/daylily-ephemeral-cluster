#!/usr/bin/env python3
import csv
import os
import sys
from urllib.parse import urlparse

import boto3


PROFILE = os.environ.get("AWS_PROFILE", "lsmc")
REGION = os.environ.get("AWS_REGION", "us-west-2")

ONT_ROOTS = {
    "chip1": "s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260522_ONT_4Coriells_chip1/20260522_ONT_4Coriells_chip1/20260522_2252_2B_PBM13545_f3392d36/",
    "chip2": "s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260522_ONT_4Coriells_chip2/20260522_ONT_4Coriells_chip2/20260523_0038_1C_PBM14931_9bbdbb3f/",
    "chip3": "s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260522_ONT_4Coriells_chip3/20260522_ONT_4Coriells_chip3/20260523_0038_1F_PBK89072_e28a4508/",
    "chip4": "s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260522_ONT_4Coriells_chip4/20260522_ONT_4Coriells_chip4/20260523_0039_3E_PBM13048_8867cb21/",
}

ONT_SAMPLES = {
    "NA00232": ("SMN", "barcode18", ["chip1", "chip2", "chip4"]),
    "NA09677": ("SMN", "barcode19", ["chip1", "chip2", "chip3", "chip4"]),
    "NA03986": ("DMPK", "barcode20", ["chip1", "chip2", "chip4"]),
    "NA05164": ("DMPK", "barcode21", ["chip1", "chip2", "chip4"]),
}

ILMN_ROOT = "s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/lh01121/2026/20260526_LH01121_0004_B23WW2NLT4/Analysis/1/Data/BCLConvert/fastq/"
ILMN_EXACT_NAMES = [
    "NA00232-SMN_S46_R1_001.fastq.gz",
    "NA00232-SMN_S46_R2_001.fastq.gz",
    "NA09677-SMN_S47_R1_001.fastq.gz",
    "NA09677-SMN_S47_R2_001.fastq.gz",
    "NA03986-DMPK_S48_R1_001.fastq.gz",
    "NA03986-DMPK_S48_R2_001.fastq.gz",
    "NA05164-DMPK_S49_R1_001.fastq.gz",
    "NA05164-DMPK_S49_R2_001.fastq.gz",
]
HG_SAMPLES = [f"HG00{i}" for i in range(1, 8)]


def parse_s3(uri):
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"not an s3 uri: {uri}")
    return parsed.netloc, parsed.path.lstrip("/")


def list_objects(s3, uri):
    bucket, prefix = parse_s3(uri)
    paginator = s3.get_paginator("list_objects_v2")
    out = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            out.append((f"s3://{bucket}/{obj['Key']}", int(obj["Size"])))
    out.sort()
    return out


def main():
    session = boto3.Session(profile_name=PROFILE, region_name=REGION)
    s3 = session.client("s3")

    summary_rows = []
    object_rows = []

    for sample, (panel, barcode, chips) in ONT_SAMPLES.items():
        sample_total_count = 0
        sample_total_bytes = 0
        for chip in chips:
            prefix = f"{ONT_ROOTS[chip]}fastq_pass/{barcode}/"
            objects = [(uri, size) for uri, size in list_objects(s3, prefix) if uri.endswith((".fastq.gz", ".fq.gz", ".fastq", ".fq"))]
            count = len(objects)
            total = sum(size for _, size in objects)
            sample_total_count += count
            sample_total_bytes += total
            summary_rows.append({
                "platform": "ONT",
                "sample": sample,
                "panel": panel,
                "partition": chip,
                "barcode": barcode,
                "count": count,
                "bytes": total,
                "source": prefix,
            })
            for uri, size in objects:
                object_rows.append({
                    "platform": "ONT",
                    "sample": sample,
                    "panel": panel,
                    "partition": chip,
                    "barcode": barcode,
                    "uri": uri,
                    "bytes": size,
                })
        summary_rows.append({
            "platform": "ONT",
            "sample": sample,
            "panel": panel,
            "partition": "ALL_REQUESTED_CHIPS",
            "barcode": barcode,
            "count": sample_total_count,
            "bytes": sample_total_bytes,
            "source": ",".join(chips),
        })

    ilmn_objects = list_objects(s3, ILMN_ROOT)
    ilmn_by_name = {uri.rsplit("/", 1)[-1]: (uri, size) for uri, size in ilmn_objects}
    for name in ILMN_EXACT_NAMES:
        if name not in ilmn_by_name:
            raise SystemExit(f"missing expected ILMN object: {name}")
        uri, size = ilmn_by_name[name]
        sample = name.split("-", 1)[0]
        summary_rows.append({
            "platform": "ILMN",
            "sample": sample,
            "panel": "Coriell",
            "partition": name,
            "barcode": "",
            "count": 1,
            "bytes": size,
            "source": uri,
        })
        object_rows.append({
            "platform": "ILMN",
            "sample": sample,
            "panel": "Coriell",
            "partition": name,
            "barcode": "",
            "uri": uri,
            "bytes": size,
        })

    for sample in HG_SAMPLES:
        matches = [
            (uri, size)
            for uri, size in ilmn_objects
            if uri.rsplit("/", 1)[-1].startswith(f"Altair-{sample}-")
            and uri.endswith("_001.fastq.gz")
        ]
        matches.sort()
        if not matches:
            raise SystemExit(f"missing expected Altair objects for {sample}")
        summary_rows.append({
            "platform": "ILMN",
            "sample": sample,
            "panel": "Altair",
            "partition": "ALL_MATCHED_FASTQS",
            "barcode": "",
            "count": len(matches),
            "bytes": sum(size for _, size in matches),
            "source": ILMN_ROOT,
        })
        for uri, size in matches:
            object_rows.append({
                "platform": "ILMN",
                "sample": sample,
                "panel": "Altair",
                "partition": uri.rsplit("/", 1)[-1],
                "barcode": "",
                "uri": uri,
                "bytes": size,
            })

    summary_writer = csv.DictWriter(sys.stdout, fieldnames=["platform", "sample", "panel", "partition", "barcode", "count", "bytes", "source"], delimiter="\t", lineterminator="\n")
    summary_writer.writeheader()
    summary_writer.writerows(summary_rows)

    object_path = os.environ.get("SOURCE_OBJECTS_TSV")
    if object_path:
        with open(object_path, "w", newline="") as handle:
            object_writer = csv.DictWriter(handle, fieldnames=["platform", "sample", "panel", "partition", "barcode", "uri", "bytes"], delimiter="\t", lineterminator="\n")
            object_writer.writeheader()
            object_writer.writerows(object_rows)


if __name__ == "__main__":
    main()
