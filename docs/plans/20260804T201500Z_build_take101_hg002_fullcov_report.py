#!/usr/bin/env python3
"""Build the Take101 HG002 plus NA23687 full-coverage HIOMR2 final report."""

from __future__ import annotations

import csv
import io
import json
import tarfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import boto3


PROFILE = "lsmc"
REGION = "us-west-2"
BUCKET = "lsmc-ssf-sequencing-data"
PREFIX = "derived/preval-hiomr2/take101/"
RESULTS = PREFIX + "daylily-omics-analysis/results/day/hg38/"
OUT = Path("/Users/jmajor/Downloads/take101-hg002-fullcov-hiomr2-final-report")
REPORT_NAME = "TAKE101_HG002_NA23687_FULLCOV_HIOMR2_FINAL_REPORT"
REPORT_DIR_REL = "daylily-omics-analysis/results/day/hg38/reports/take101-hg002-fullcov-final/"
MULTIQC_REL = "daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc.html"
SAMPLES = {
    "HG002-ck2ky6p4wk6exh": "HG002",
    "NA23687-zsvw0fa30jhz3n": "NA23687",
}
EXPECTED_SMN = {
    "HG002": (2, 2),
    "NA23687": (1, 2),
}


session = boto3.Session(profile_name=PROFILE, region_name=REGION)
s3 = session.client("s3")


def get_bytes(relative: str) -> bytes:
    return s3.get_object(Bucket=BUCKET, Key=RESULTS + relative)["Body"].read()


def get_json(relative: str) -> dict[str, object]:
    return json.loads(get_bytes(relative))


def tsv(relative: str) -> list[dict[str, str]]:
    text = get_bytes(relative).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text), delimiter="\t"))


def list_objects() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=PREFIX):
        rows.extend(page.get("Contents", []))
    return rows


def md_table(rows: list[dict[str, object]], columns: list[tuple[str, str]]) -> str:
    head = "| " + " | ".join(label for _, label in columns) + " |"
    sep = "|" + "|".join("---" for _ in columns) + "|"
    body = []
    for row in rows:
        values = []
        for key, _ in columns:
            value = str(row.get(key, "")).replace("|", "\\|").replace("\n", " ")
            values.append(value)
        body.append("| " + " | ".join(values) + " |")
    return "\n".join([head, sep, *body])


def write_tsv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: str | float | int | None, digits: int = 3) -> str:
    if value in ("", "NA", ".", None):
        return "NA"
    return f"{float(value):.{digits}f}"


def integer(value: str | float | int | None) -> str:
    if value in ("", "NA", ".", None):
        return "NA"
    return str(int(float(value)))


def external(uid: str) -> str:
    return SAMPLES.get(uid.rstrip("."), uid.rstrip(".").split("-")[0])


def s3_uri(relative_from_root: str) -> str:
    return f"s3://{BUCKET}/{PREFIX}{relative_from_root}"


def report_s3_uri(suffix: str) -> str:
    return s3_uri(REPORT_DIR_REL + REPORT_NAME + suffix)


def load_nicu_raw_summary() -> dict[str, object]:
    rel = (
        "HG002-ck2ky6p4wk6exh/align/sentmm2ont/na/snv/sentdhiomr2/"
        "nicu-research/benchmarks/HG002-ck2ky6p4wk6exh.truvari-output.tar.gz"
    )
    archive = io.BytesIO(get_bytes(rel))
    with tarfile.open(fileobj=archive, mode="r:gz") as handle:
        member = handle.extractfile("./truvari/summary.json")
        if member is None:
            raise RuntimeError("NICU Truvari archive lacks ./truvari/summary.json")
        return json.loads(member.read())


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    data_dir = OUT / "data"
    data_dir.mkdir(exist_ok=True)
    source_dir = OUT / "source-data"
    source_dir.mkdir(exist_ok=True)
    generated = datetime.now(timezone.utc).replace(microsecond=0)
    generated_iso = generated.isoformat().replace("+00:00", "Z")

    objects = list_objects()
    object_map = {str(row["Key"]): row for row in objects}

    # Alignment and coverage evidence.
    alignstats = tsv("other_reports/alignstats_combo_mqc.tsv")
    labels = {
        "sentdhiomr2sr": "Illumina full-coverage analysis alignment",
        "sentdhiomr2lr": "ONT [0,25 h) analysis alignment",
        "sentdhiomr2rsr": "restricted short-read comparison alignment",
    }
    coverage: list[dict[str, object]] = []
    alignment_files: list[dict[str, object]] = []
    for row in alignstats:
        if row["aligner"] not in labels:
            continue
        uid = row["base_sample"]
        alignment = row["aligner"] + "." + row["deduper"]
        coverage.append(
            {
                "sample": external(uid),
                "alignment": alignment,
                "modality": labels[row["aligner"]],
                "mean_depth": fmt(row["WgsCoverageMean"], 2),
                "median_depth": fmt(row["WgsCoverageMedian"], 1),
                "bases_30x_pct": fmt(row["WgsCoverageBases30Pct"], 2),
                "mapped_pct": fmt(row["MappedReadsPct"], 2),
                "duplicate_pct": fmt(row["DuplicateReadsPct"], 2),
                "median_insert_bp": integer(row["InsertSizeMedian"]),
            }
        )
        source = row["InputFileName"]
        marker = "/results/day/hg38/"
        relative = source.split(marker, 1)[1] if marker in source else source.removeprefix("results/day/hg38/")
        key = RESULTS + relative
        obj = object_map.get(key)
        alignment_files.append(
            {
                "sample": external(uid),
                "alignment": alignment,
                "format": Path(relative).suffix.lstrip(".").upper(),
                "size_gb": fmt(int(obj["Size"]) / 1e9, 3) if obj else "not resolved",
                "s3_uri": s3_uri("daylily-omics-analysis/results/day/hg38/" + relative),
            }
        )
    coverage.sort(key=lambda row: (str(row["sample"]), str(row["alignment"])))
    alignment_files.sort(key=lambda row: (str(row["sample"]), str(row["alignment"])))
    write_tsv(data_dir / "coverage_and_alignment_stats.tsv", coverage)
    write_tsv(data_dir / "alignment_files.tsv", alignment_files)

    # GIAB high-confidence small-variant concordance for both equivalent lanes.
    giab_rows: list[dict[str, object]] = []
    class_order = {name: i for i, name in enumerate(("SNPts", "SNPtv", "INS_50", "DEL_50", "Indel_50", "INS_gt50", "DEL_gt50", "Indel_gt50", "All"))}
    for row in tsv("other_reports/giab_concordance_mqc.tsv"):
        if row["SampleID"] != "HG002" or row["ROI"] != "giabHC":
            continue
        if row["SNVCaller"] not in {"sentdhiomr2", "sentdhiomr2_cli_gvcf"}:
            continue
        giab_rows.append(
            {
                "sample": row["SampleID"],
                "caller": row["SNVCaller"],
                "class": row["VariantClass"],
                "f_score": fmt(row["Fscore"], 6),
                "precision": fmt(row["Precision"], 6),
                "recall": fmt(row["Sensitivity-Recall"], 6),
                "tp": integer(row["TP"]),
                "fp": integer(row["FP"]),
                "fn": integer(row["FN"]),
            }
        )
    giab_rows.sort(key=lambda row: (str(row["caller"]), class_order.get(str(row["class"]), 99)))
    if len(giab_rows) != 18:
        raise RuntimeError(f"Expected 18 HG002 giabHC rows, found {len(giab_rows)}")
    write_tsv(data_dir / "hg002_giabhc_snv_concordance.tsv", giab_rows)

    # Structural callset inventory and direct record summaries.
    callset_specs = [
        ("Manta", "singleton", "/normalized/manta/", ".manta.normalized.vcf.gz", "not individually packaged"),
        ("Dysgu", "singleton", "/normalized/dysgu/", ".dysgu.normalized.vcf.gz", "not individually packaged"),
        ("LongReadSV", "singleton", "/normalized/longreadsv/", ".longreadsv.normalized.vcf.gz", "established"),
        ("TIDDIT", "singleton", "/normalized/tiddit/", ".tiddit.normalized.vcf.gz", "experimental"),
        ("Sniffles2", "singleton", "/normalized/sniffles2/", ".sniffles2.normalized.vcf.gz", "experimental"),
        ("Severus", "singleton", "/normalized/severus/", ".severus.normalized.vcf.gz", "experimental"),
        ("Jasmine", "composite merger", "/merged/jasmine/", ".jasmine.vcf.gz", "experimental"),
        ("SURVIVOR", "composite merger", "/merged/survivor/", ".survivor.vcf.gz", "experimental"),
        ("OctopuSV", "composite merger", "/merged/octopusv/", ".octopusv.vcf.gz", "experimental"),
    ]
    callsets: list[dict[str, object]] = []
    for uid, sample in SAMPLES.items():
        sample_prefix = RESULTS + uid + "/"
        for caller, role, fragment, suffix, tier in callset_specs:
            matches = [
                key for key in object_map
                if key.startswith(sample_prefix) and fragment in key and key.endswith(suffix)
            ]
            if len(matches) != 1:
                raise RuntimeError(f"Expected one {caller} callset for {sample}, found {len(matches)}")
            key = matches[0]
            callsets.append(
                {
                    "sample": sample,
                    "caller_or_composite": caller,
                    "role": role,
                    "size_mb": fmt(int(object_map[key]["Size"]) / 1e6, 3),
                    "package_tier": tier,
                    "s3_uri": f"s3://{BUCKET}/{key}",
                }
            )
    write_tsv(data_dir / "all_singleton_and_composite_sv_callsets.tsv", callsets)

    callset_summary: list[dict[str, object]] = []
    for caller, role, _, _, tier in callset_specs:
        rows = [row for row in callsets if row["caller_or_composite"] == caller]
        sizes = [float(row["size_mb"]) for row in rows]
        callset_summary.append(
            {
                "caller_or_composite": caller,
                "role": role,
                "samples": len(rows),
                "vcf_size_range_mb": f"{min(sizes):.3f}-{max(sizes):.3f}",
                "package_treatment": tier,
            }
        )

    direct_counts: list[dict[str, object]] = []
    for filename, caller in (("sentdhiomr2_sniffles2_mqc.tsv", "Sniffles2"), ("sentdhiomr2_tiddit_mqc.tsv", "TIDDIT")):
        for row in tsv("other_reports/" + filename):
            direct_counts.append(
                {
                    "sample": external(row["base_sample"]),
                    "caller": caller,
                    "records": row["total_records"],
                    "DEL": row["DEL"],
                    "INS": row["INS"],
                    "DUP": row["DUP"],
                    "INV": row["INV"],
                    "BND": row["BND"],
                }
            )
    write_tsv(data_dir / "direct_sv_caller_counts.tsv", direct_counts)

    # Exhaustive HG002 Truvari summaries, including raw diagnostic evidence.
    status_map: dict[str, tuple[str, str]] = {
        "cnvscope": ("accepted", "CNVscope CNV-to-DEL projection"),
        "hard_snv": ("accepted", "SV projection from the hard VCF; not the RTG SNV score"),
        "jasmine_companion": ("accepted", "companion Jasmine integration"),
        "jasmine_final": ("raw diagnostic only", "projected 21,936 versus compared 21,928"),
        "jasmine_full": ("raw diagnostic only", "projected 31,949 versus compared 31,941"),
        "longreadsv": ("raw diagnostic only", "projected 19,849 versus compared 19,841"),
        "sniffles1_iris": ("accepted", "Sentieon Sniffles1 plus Iris refinement"),
        "sniffles1_iris_sentieon": ("alias; do not double-count", "exact duplicate of sniffles1_iris"),
        "sniffles2": ("raw diagnostic only", "projected 18,269 versus compared 18,262"),
        "tiddit": ("accepted", "normalized TIDDIT"),
        "jasmine_alignment_compare": ("accepted directional comparison", "Winnowmap base versus Sentieon-minimap2 query; not GIAB truth accuracy"),
        "nicu_jasmine": ("raw diagnostic only", "projected 30,395 versus compared 30,388; warning receipt publishes no metric"),
    }
    summary_paths = {
        "cnvscope": "benchmarks/truvari/hiomr2_hg002/queries/cnvscope/truvari/summary.json",
        "hard_snv": "benchmarks/truari/hiomr2_hg002/queries/hard_snv/truari/summary.json",
        "jasmine_companion": "benchmarks/truari/hiomr2_hg002/queries/jasmine_companion/truari/summary.json",
        "jasmine_final": "benchmarks/truari/hiomr2_hg002/queries/jasmine_final/truari/summary.json",
        "jasmine_full": "benchmarks/truari/hiomr2_hg002/queries/jasmine_full/truari/summary.json",
        "longreadsv": "benchmarks/truari/hiomr2_hg002/queries/longreadsv/truari/summary.json",
        "sniffles1_iris": "benchmarks/truari/hiomr2_hg002/queries/sniffles1_iris/truari/summary.json",
        "sniffles1_iris_sentieon": "benchmarks/truari/hiomr2_hg002/queries/sniffles1_iris_sentieon/truari/summary.json",
        "sniffles2": "benchmarks/truari/hiomr2_hg002/queries/sniffles2/truari/summary.json",
        "tiddit": "benchmarks/truari/hiomr2_hg002/queries/tiddit/truari/summary.json",
        "jasmine_alignment_compare": "benchmarks/truari/hiomr2_hg002/jasmine_alignment_compare/truari/summary.json",
    }
    # Correct the historical directory spelling in one constructed entry above.
    summary_paths = {name: path.replace("truari", "truvari") for name, path in summary_paths.items()}
    truvari_rows: list[dict[str, object]] = []
    for name, path in summary_paths.items():
        summary = get_json(path)
        disposition, interpretation = status_map[name]
        truvari_rows.append(
            {
                "query": name,
                "disposition": disposition,
                "base_count": summary.get("base cnt", "NA"),
                "query_count": summary.get("comp cnt", "NA"),
                "tp": summary.get("TP-comp", "NA"),
                "fp": summary.get("FP", "NA"),
                "fn": summary.get("FN", "NA"),
                "precision": fmt(summary.get("precision"), 6),
                "recall": fmt(summary.get("recall"), 6),
                "f1": fmt(summary.get("f1"), 6),
                "gt_match": summary.get("TP-comp_TP-gt", "NA"),
                "gt_mismatch": summary.get("TP-comp_FP-gt", "NA"),
                "gt_concordance": fmt(summary.get("gt_concordance"), 6),
                "interpretation": interpretation,
            }
        )
    nicu_summary = load_nicu_raw_summary()
    disposition, interpretation = status_map["nicu_jasmine"]
    truvari_rows.append(
        {
            "query": "nicu_jasmine",
            "disposition": disposition,
            "base_count": nicu_summary.get("base cnt", "NA"),
            "query_count": nicu_summary.get("comp cnt", "NA"),
            "tp": nicu_summary.get("TP-comp", "NA"),
            "fp": nicu_summary.get("FP", "NA"),
            "fn": nicu_summary.get("FN", "NA"),
            "precision": fmt(nicu_summary.get("precision"), 6),
            "recall": fmt(nicu_summary.get("recall"), 6),
            "f1": fmt(nicu_summary.get("f1"), 6),
            "gt_match": nicu_summary.get("TP-comp_TP-gt", "NA"),
            "gt_mismatch": nicu_summary.get("TP-comp_FP-gt", "NA"),
            "gt_concordance": fmt(nicu_summary.get("gt_concordance"), 6),
            "interpretation": interpretation,
        }
    )
    query_order = {name: i for i, name in enumerate(status_map)}
    truvari_rows.sort(key=lambda row: query_order[str(row["query"])])
    write_tsv(data_dir / "hg002_truvari_with_genotype_concordance.tsv", truvari_rows)

    caller_truvari = [
        {"caller": "Manta", "role": "singleton", "result": "not emitted", "best_f1": "NA", "gt_concordance": "NA", "note": "normalized callset exists; no standalone Truvari query"},
        {"caller": "Dysgu", "role": "singleton", "result": "not emitted", "best_f1": "NA", "gt_concordance": "NA", "note": "normalized callset exists; no standalone Truvari query"},
        {"caller": "LongReadSV", "role": "singleton", "result": "raw diagnostic", "best_f1": fmt(next(r for r in truvari_rows if r["query"] == "longreadsv")["f1"], 6), "gt_concordance": fmt(next(r for r in truvari_rows if r["query"] == "longreadsv")["gt_concordance"], 6), "note": "eight-record reconciliation mismatch"},
        {"caller": "TIDDIT", "role": "singleton", "result": "accepted", "best_f1": fmt(next(r for r in truvari_rows if r["query"] == "tiddit")["f1"], 6), "gt_concordance": fmt(next(r for r in truvari_rows if r["query"] == "tiddit")["gt_concordance"], 6), "note": "published PASS-only DEL/INS >=50 metric"},
        {"caller": "Sniffles2", "role": "singleton", "result": "raw diagnostic", "best_f1": fmt(next(r for r in truvari_rows if r["query"] == "sniffles2")["f1"], 6), "gt_concordance": fmt(next(r for r in truvari_rows if r["query"] == "sniffles2")["gt_concordance"], 6), "note": "seven-record reconciliation mismatch"},
        {"caller": "Severus", "role": "singleton", "result": "not emitted", "best_f1": "NA", "gt_concordance": "NA", "note": "normalized callset exists; no standalone Truvari query"},
        {"caller": "Jasmine", "role": "composite", "result": "accepted plus raw diagnostics", "best_f1": fmt(next(r for r in truvari_rows if r["query"] == "jasmine_final")["f1"], 6), "gt_concordance": fmt(next(r for r in truvari_rows if r["query"] == "jasmine_final")["gt_concordance"], 6), "note": "best raw accuracy lane shown; companion accepted F1=0.192495; full/final/NICU raw lanes are not published"},
        {"caller": "SURVIVOR", "role": "composite", "result": "not emitted", "best_f1": "NA", "gt_concordance": "NA", "note": "merged callset exists; no standalone Truvari query"},
        {"caller": "OctopuSV", "role": "composite", "result": "not emitted", "best_f1": "NA", "gt_concordance": "NA", "note": "merged callset exists; no standalone Truvari query"},
    ]
    write_tsv(data_dir / "sv_caller_truvari_coverage.tsv", caller_truvari)

    # SMN evidence for both samples.
    smn_rows: list[dict[str, object]] = []
    for row in tsv("other_reports/smn12_orthogonal_calls_mqc.tsv"):
        expected_smn1, expected_smn2 = EXPECTED_SMN[row["SampleID"]]
        smn_rows.append(
            {
                "sample": row["SampleID"],
                "expected_smn1": expected_smn1,
                "expected_smn2": expected_smn2,
                "sentieon_smn1": row["sentieon_smn1_copy_number"],
                "sentieon_smn2": row["sentieon_smn2_copy_number"],
                "smncnc_smn1": row["smncopynumbercaller_smn1_copy_number"],
                "smncnc_smn2": row["smncopynumbercaller_smn2_copy_number"],
                "affected": row["smncopynumbercaller_affected_status"],
                "carrier": row["smncopynumbercaller_carrier_status"],
                "status": row["smncopynumbercaller_status"],
                "interpretation": ("carrier-positive; matches campaign expectation" if row["smncopynumbercaller_carrier_status"].lower() == "true" else "no SMA/carrier flag; matches campaign expectation"),
            }
        )
    smn_rows.sort(key=lambda row: str(row["sample"]))
    write_tsv(data_dir / "smn12_orthogonal_results.tsv", smn_rows)

    # Final MultiQC contextual review.
    sex_rows: list[dict[str, object]] = []
    for row in tsv("other_reports/sex_gender_rollup_mqc.tsv"):
        sex_rows.append(
            {
                "sample": row["SampleID"],
                "reported": row["reported_sex_normalized"] or "not configured",
                "short_read": row["sr_derived_sex_chromosome_complements"],
                "long_read": row["lr_derived_sex_chromosome_complements"],
                "peddy": row["peddy_predicted_genders"],
                "status": row["comparison_status"],
                "note": row["reason_codes"] or "consistent",
            }
        )
    contam = tsv("other_reports/contamination_mqc.tsv")
    contamination_summary = [
        {
            "sample": row["SampleID"],
            "alignment": row["aligner"] + "." + row["deduper"],
            "gatk_pct": fmt(row["gatk_contamination_pct"], 3),
            "site_mix_pct": fmt(row["site_mix_contamination_pct"], 3),
            "status": row["site_mix_status"],
        }
        for row in contam
    ]
    write_tsv(data_dir / "contamination_summary.tsv", contamination_summary)

    # Task-level runtime aggregation.
    benchmarks = tsv("reports/benchmarks_summary.tsv")
    runtime_rows: list[dict[str, object]] = []
    for uid, sample in SAMPLES.items():
        rows = [row for row in benchmarks if row["sample"].rstrip(".") == uid and row["status"] == "success"]
        starts = [datetime.fromisoformat(row["start_datetime"].replace("Z", "+00:00")) for row in rows]
        ends = [datetime.fromisoformat(row["end_datetime"].replace("Z", "+00:00")) for row in rows]
        longest = max(rows, key=lambda row: float(row["s"]))
        runtime_rows.append(
            {
                "sample": sample,
                "tasks": len(rows),
                "span_h": fmt((max(ends) - min(starts)).total_seconds() / 3600, 2),
                "task_wall_h": fmt(sum(float(row["s"]) for row in rows) / 3600, 2),
                "vcpu_h": fmt(sum(float(row["s"]) * float(row["snakemake_threads"]) / 3600 for row in rows), 1),
                "task_cost_usd": fmt(sum(float(row["task_cost"]) for row in rows), 2),
                "longest_rule": longest["rule"],
                "longest_h": fmt(float(longest["s"]) / 3600, 2),
            }
        )
    write_tsv(data_dir / "runtime_by_sample.tsv", runtime_rows)

    # Inflection package manifests and role inventory.
    packages: list[dict[str, object]] = []
    role_counter: Counter[tuple[str, str, str]] = Counter()
    for uid, sample in SAMPLES.items():
        rel = f"deliveries/inflection_hiomr2_analytical_callsets_vcf_gvcf/take101/{uid}/package_manifest.json"
        manifest = get_json(rel)
        artifacts = list(manifest["artifacts"])
        packages.append(
            {
                "sample": sample,
                "schema": manifest["schema"],
                "artifacts": len(artifacts),
                "established": sum(1 for row in artifacts if row["package_tier"] == "established"),
                "experimental": sum(1 for row in artifacts if row["package_tier"] == "experimental"),
                "declared_gb": fmt(sum(int(row["bytes"]) for row in artifacts) / 1e9, 3),
                "nicu_included": manifest["nicu_research_included"],
                "customer_release": manifest["customer_release_eligible"],
                "manifest_s3_uri": s3_uri("daylily-omics-analysis/results/day/hg38/" + rel),
            }
        )
        for artifact in artifacts:
            role_counter[(artifact["package_tier"], artifact["role"], artifact["semantic_type"])] += 1
    package_roles = [
        {"tier": tier, "role": role, "type": semantic_type, "samples": count}
        for (tier, role, semantic_type), count in sorted(role_counter.items())
    ]
    write_tsv(data_dir / "inflection_packages.tsv", packages)
    write_tsv(data_dir / "inflection_package_roles.tsv", package_roles)

    # Scoped VCF treatment counts from the reviewed durable receipts.
    reviewed_treatments = Path(
        "/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/"
        "20260803T082714Z_take101_export_take222_report/TAKE101_VARIANT_TREATMENT_COUNTS.tsv"
    )
    treatment_rows = list(csv.DictReader(reviewed_treatments.open(encoding="utf-8"), delimiter="\t"))
    write_tsv(data_dir / "variant_treatment_counts.tsv", treatment_rows)

    multiqc_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": PREFIX + MULTIQC_REL},
        ExpiresIn=604800,
    )

    report_lines = [
        "# Take101 HG002 + NA23687 full-coverage HIOMR2 final report",
        "",
        f"Generated: {generated_iso}",
        "",
        "## How to execute the pipeline",
        "",
        "Take101 was analyzed under DayOA `13.4.2`. DayOA `13.4.4` is the current immutable reproduction release: it retains the proven analytical behavior and removes the rejected standalone Jasmine/NICU diagnostics from the production gate. The six exact manifest tables and referenced FASTQ inputs are constructed and staged by upstream DYEC/BJuice tools and are deliberately not recreated below.",
        "",
        "### Via the DYEC CLI",
        "",
        "Set `AWS_PROFILE`, `AWS_REGION`, `CLUSTER`, `EXECUTING_ENTITY`, `ANALYSIS_ID`, `SESSION_NAME`, `MANIFEST_DIR`, `PAYLOAD_STAGING_S3_URI`, `EXPORT_S3_URI`, and `EXPORT_RECEIPT_DIR` to explicit reviewed values. Inspect the cluster and catalog contract, then launch the five-target dry run:",
        "",
        "```bash",
        "dyec cluster-info --profile \"$AWS_PROFILE\" --region \"$AWS_REGION\"",
        "dyec catalog show inflection-bjuice-product-v0.2",
        "dyec workflow launch \\",
        "  --profile \"$AWS_PROFILE\" --region \"$AWS_REGION\" --cluster \"$CLUSTER\" \\",
        "  --repository daylily-omics-analysis --git-tag 13.4.4 \\",
        "  --analysis-id \"$ANALYSIS_ID\" --executing-entity \"$EXECUTING_ENTITY\" \\",
        "  --input-contract six_manifest --manifest-dir \"$MANIFEST_DIR\" \\",
        "  --payload-staging-s3-uri \"$PAYLOAD_STAGING_S3_URI\" --session-name \"$SESSION_NAME\" \\",
        "  --project RnD --cost-center RnD --genome hg38 --jobs 333 \\",
        "  --dy-command \"DAY_CONTAINERIZED=true dy-r produce_sentdhiomr2_kitchensink produce_sentdhiomr2_nicu_research produce_sentdhiomr2_jasmine_sharded_per_sample produce_sentdhiomr2_inflection_analytical_package results/day/hg38/reports/DAY_final_multiqc.html --config genome_build=hg38 'aligners=[\\\"sentmm2ont\\\"]' 'dedupers=[\\\"na\\\"]' 'snv_callers=[\\\"sentdhiomr2\\\"]' 'sv_callers=[]' 'htd_callers=[\\\"smn12\\\"]' hiomr2_inflection_package_mode=analytical use_fq_data_starting_hrs=0 use_fq_data_up_to_hrs=25 seqone_delivery_batch_id=$ANALYSIS_ID -j 333 -p -T 1 -k --rerun-triggers mtime -n\" \\",
        "  --dry-run",
        "```",
        "",
        "Require dry-run RC 0. Promote the same analysis root with `--reuse-existing-analysis-dir --input-contract none --no-input-staging`, omit manifest/payload-staging flags, remove only the final `-n` inside `--dy-command`, and remove launcher `--dry-run`. After controller RC 0, monitor and export read-only:",
        "",
        "```bash",
        "dyec --json workflow status --profile \"$AWS_PROFILE\" --region \"$AWS_REGION\" --cluster \"$CLUSTER\" --session \"$SESSION_NAME\"",
        "dyec workflow logs --profile \"$AWS_PROFILE\" --region \"$AWS_REGION\" --cluster \"$CLUSTER\" --session \"$SESSION_NAME\" --stream controller --lines 200",
        "dyec headnode jobs --profile \"$AWS_PROFILE\" --region \"$AWS_REGION\" --cluster \"$CLUSTER\"",
        "dyec headnode fsx-usage --profile \"$AWS_PROFILE\" --region \"$AWS_REGION\" --cluster \"$CLUSTER\"",
        "dyec command sample-stats hiomr-kitchensink --name \"$ANALYSIS_ID\" --analysis-root \"/fsx/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID\" --profile \"$AWS_PROFILE\" --region \"$AWS_REGION\" --cluster \"$CLUSTER\"",
        "dyec export --profile \"$AWS_PROFILE\" --region \"$AWS_REGION\" --cluster \"$CLUSTER\" --source-path \"/fsx/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID\" --destination-s3-uri \"$EXPORT_S3_URI\" --output-dir \"$EXPORT_RECEIPT_DIR\" --wait --timeout-seconds 7200",
        "cat \"$EXPORT_RECEIPT_DIR/fsx_export.yaml\"",
        "```",
        "",
        "### On a running headnode with DayOA directly",
        "",
        "Run as `ubuntu` in a persistent, one-pane interactive login-shell tmux with the analysis-root write lock held for workflow writes:",
        "",
        "```bash",
        "day-clone -t 13.4.4 -d <somename>",
        "cd /fsx/analysis_results/<executing-entity>/<somename>/daylily-omics-analysis",
        "source dyoainit",
        "dy-a slurm hg38",
        "export DAY_PROJECT=RnD",
        "export DAYLILY_COST_CENTER=RnD",
        "export SEQONE_DELIVERY_BATCH_ID=<explicit-analytical-batch-id>",
        "```",
        "",
        "Run `dy-r` with the five targets above, `--configfile config/<run-config>.yaml`, the explicit analytical config shown in the DYEC example, and `-j 333 -p -T 1 -k --rerun-triggers mtime -n`. Only after RC 0, repeat the identical command without `-n`. Never invoke Snakemake directly.",
        "",
        "## Executive result",
        "",
        "Take101 completed the full two-sample HIOMR2 kitchen-sink, NICU/mega research graph, final MultiQC, and both Inflection analytical packages. The original live controller reached 441/466 steps; after two bounded, tested repairs, the exact 25-job closure dry run passed and the repair-live controller completed 25/25 with RC 0. Final state had no controller, no queued job, and no analysis-root write lock.",
        "",
        "The cohort is HG002 plus NA23687. Each sample used all eight accepted full-coverage Illumina lanes and ONT reads from elapsed hours [0,25). HG002 supplies the GIAB small-variant and GIAB SV truth comparisons; NA23687 is an SMN1-carrier-positive control with no HG002-specific truth benchmark.",
        "",
        "This is a research/validation result, not a clinical release. Package manifests mark customer-release eligibility false and separate established deliverables from experimental NICU/mega artifacts.",
        "",
        "## Pipeline capabilities represented in this run",
        "",
        "- **Manifested hybrid inputs:** explicit specimen, sample, library, sequencing-input, and analysis-unit tables; eight Illumina lanes per sample; bounded ONT elapsed-hour selection; provenance and evidence receipts.",
        "- **Alignment and QC:** full-coverage Illumina, ONT, and restricted short-read comparison alignments; AlignStats, mapping/yield/coverage/insert-size metrics, duplicates, contamination, inferred sex, Peddy, Somalier relatedness, coverage evenness, and sequence-QC inventories.",
        "- **Small variants:** Sentieon HIOMR2 hard VCF and gVCF, a CLI-gVCF parity lane, normalization/annotation, GIAB RTG vcfeval across configured regions, and final MultiQC concordance tables.",
        "- **Structural and copy-number variants:** Manta, Dysgu, LongReadSV, TIDDIT, Sniffles2, and Severus singleton callsets; Jasmine, SURVIVOR, and OctopuSV composites; CNVscope; normalized inputs; caller provenance; VCF/BEDPE products; and caller summaries.",
        "- **Targeted/complex variation:** SMN1/SMN2 copy number, Sentieon SMN1 regional variants, segmental-duplication loci, ExpansionHunter, ROH/UPD, and related targeted evidence.",
        "- **Research integration:** per-sample sharded Jasmine, NICU caller reconciliation, BND topology validation, source-support and merger-concordance tables, recoverability receipts, and explicit warning receipts for diagnostic reconciliation gaps.",
        "- **Reporting and delivery:** final MultiQC, combined task benchmarks, a DayOA evidence manifest, and a checksum/size/role-proven 37-artifact analytical package per sample.",
        "",
        "## Samples, alignments, and coverage",
        "",
        md_table(coverage, [("sample", "Sample"), ("alignment", "Alignment"), ("mean_depth", "Mean depth"), ("median_depth", "Median"), ("bases_30x_pct", ">=30x %"), ("mapped_pct", "Mapped %"), ("duplicate_pct", "Duplicate %"), ("median_insert_bp", "Median insert")]),
        "",
        "The primary analysis alignments are CRAMs. Full-coverage duplicate-marked short-read and long-read CRAMs are canonical analysis inputs; restricted short-read CRAMs are comparison artifacts.",
        "",
        md_table(alignment_files, [("sample", "Sample"), ("alignment", "Alignment"), ("format", "Format"), ("size_gb", "GB"), ("s3_uri", "S3 URI")]),
        "",
        "## HG002 GIAB high-confidence small-variant concordance",
        "",
        "The table reports every variant class for ROI `giabHC` in both the workflow hard-call lane and the CLI-gVCF comparison lane. The two lanes are numerically identical, proving parity for this run. `NA` for `Indel_gt50` means the denominator is empty, not a zero score.",
        "",
        md_table(giab_rows, [("sample", "Sample"), ("caller", "Caller"), ("class", "Class"), ("f_score", "F-score"), ("precision", "Precision"), ("recall", "Recall"), ("tp", "TP"), ("fp", "FP"), ("fn", "FN")]),
        "",
        "## Structural-variant outputs and Truvari",
        "",
        "All nine singleton/composite families below produced normalized or merged VCFs for both samples. Direct per-type record summaries were materialized for TIDDIT and Sniffles2; package manifests supply checksums and tier assignments for delivered callsets.",
        "",
        md_table(callset_summary, [("caller_or_composite", "Caller/composite"), ("role", "Role"), ("samples", "Samples"), ("vcf_size_range_mb", "VCF size range MB"), ("package_treatment", "Package treatment")]),
        "",
        md_table(direct_counts, [("sample", "Sample"), ("caller", "Caller"), ("records", "Records"), ("DEL", "DEL"), ("INS", "INS"), ("DUP", "DUP"), ("INV", "INV"), ("BND", "BND")]),
        "",
        "### HG002 Truvari accuracy and genotype concordance",
        "",
        "These are real values parsed from the exported Truvari `summary.json` files. `GT match` is `TP-comp_TP-gt`; `GT mismatch` is `TP-comp_FP-gt`; genotype concordance is GT match divided by matched comparison events. Take101's Truvari summaries do not contain separate GT precision, GT recall, or GT F1 fields, so none are inferred. Rows marked **raw diagnostic only** completed Truvari but failed the workflow's projected-versus-compared record reconciliation and therefore were not published into final MultiQC as accepted metrics.",
        "",
        md_table(truvari_rows, [("query", "Query"), ("disposition", "Disposition"), ("base_count", "Truth count"), ("query_count", "Query count"), ("tp", "TP"), ("fp", "FP"), ("fn", "FN"), ("precision", "Precision"), ("recall", "Recall"), ("f1", "F1"), ("gt_match", "GT match"), ("gt_mismatch", "GT mismatch"), ("gt_concordance", "GT concordance")]),
        "",
        "The strongest accepted truth-accuracy lane is `sniffles1_iris` (F1 0.735369; GT concordance 0.359020). The strongest raw diagnostic truth-accuracy lane is `sniffles2` by F1 0.724244, with GT concordance 0.811961, while `jasmine_final` reaches F1 0.698101 and GT concordance 0.736583. High GT concordance does not compensate for low recall: TIDDIT has GT concordance 0.881466 but F1 0.176604 because recall is 0.103713.",
        "",
        "### Caller-level Truvari coverage and gaps",
        "",
        md_table(caller_truvari, [("caller", "Caller/composite"), ("role", "Role"), ("result", "Truvari"), ("best_f1", "F1"), ("gt_concordance", "GT concordance"), ("note", "Interpretation")]),
        "",
        "Manta, Dysgu, Severus, SURVIVOR, and OctopuSV all produced callsets but have no standalone Truvari query in this execution. Their missing values are evidence gaps, not zeros. NA23687 was correctly not benchmarked against HG002 truth.",
        "",
        "## SMN1/SMN2 copy-number results",
        "",
        "SMNCopyNumberCaller produced complete calls for both samples and matches the campaign expectations shown below. Sentieon produced SMN1 regional small-variant VCFs but did not publish SMN1/SMN2 copy-number fields; those cells remain `NA`. The campaign expectations are validation context and were not configured as formal workflow truth fields.",
        "",
        md_table(smn_rows, [("sample", "Sample"), ("expected_smn1", "Expected SMN1"), ("expected_smn2", "Expected SMN2"), ("sentieon_smn1", "Sentieon SMN1"), ("sentieon_smn2", "Sentieon SMN2"), ("smncnc_smn1", "SMNCNC SMN1"), ("smncnc_smn2", "SMNCNC SMN2"), ("affected", "Affected"), ("carrier", "Carrier"), ("status", "Status"), ("interpretation", "Interpretation")]),
        "",
        "## MultiQC review",
        "",
        "- All six alignment/method contamination rows report `ok`. Full-coverage Illumina site-mix is 0.25% in both samples; ONT method estimates are 2.55% for HG002 and 2.45% for NA23687 and should be interpreted as modality-specific estimates.",
        "- HG002's reported male sex agrees with short-read, long-read, and Peddy calls. NA23687 has no reported sex configured; primary short-read, long-read, and Peddy evidence is female, while the restricted short-read comparison soft-fails as XY without overriding primary evidence.",
        "- Somalier classifies the sole pair as unrelated in all three alignment contexts. The no-group Somalier output was repaired deterministically only after the native outputs validated.",
        "- Final MultiQC includes coverage, alignment, contamination, sequence QC, sex/gender, relatedness, small-variant concordance, targeted calls, NICU artifacts, direct SV summaries, Truvari dispositions, and benchmark/provenance sections.",
        "",
        md_table(sex_rows, [("sample", "Sample"), ("reported", "Reported"), ("short_read", "SR"), ("long_read", "LR"), ("peddy", "Peddy"), ("status", "Status"), ("note", "Note")]),
        "",
        "## Runtime evidence",
        "",
        "Benchmark span is the interval from the first to last successful task for a sample; summed task wall time is not controller elapsed time. Task cost is the sum of recorded task-level costs and excludes cluster startup, pending, and retry overhead.",
        "",
        md_table(runtime_rows, [("sample", "Sample"), ("tasks", "Tasks"), ("span_h", "Span h"), ("task_wall_h", "Task-wall h"), ("vcpu_h", "vCPU h"), ("task_cost_usd", "Task cost $"), ("longest_rule", "Longest rule"), ("longest_h", "Longest h")]),
        "",
        "The fastest observed per-sample span was HG002 at 4.98 h; NA23687 spanned 6.25 h. These are overlapping task spans, not a guarantee for a future controller. The highest-value production combination remains full-coverage Sentieon HIOMR2 small variants plus the primary short-read and long-read alignments, SMNCopyNumberCaller, LongReadSV, and final MultiQC. Restricted short-read comparison, duplicate alias Truvari, and reconciliation-fragile standalone Jasmine diagnostics are best kept optional; experimental merger outputs remain useful for research but should not gate production completion.",
        "",
        "## Inflection analytical packaging",
        "",
        "Both packages use schema `dayoa.hiomr2_inflection_analytical_package/1.3`, declare 37 artifacts, include NICU research, and passed zero-missing/zero-size-mismatch validation before export. Each package is analytical/research-only and not customer-release eligible because no owner-issued customer delivery identity is asserted.",
        "",
        md_table(packages, [("sample", "Sample"), ("schema", "Schema"), ("artifacts", "Artifacts"), ("established", "Established"), ("experimental", "Experimental"), ("declared_gb", "Declared GB"), ("nicu_included", "NICU"), ("customer_release", "Customer release"), ("manifest_s3_uri", "Manifest S3 URI")]),
        "",
        "The established tier contains the scoped analytical VCF, CNVscope post-model VCF, LongReadSV VCF, full-coverage short-read CRAM, indexes, and command manifest. The experimental tier contains realigned comparison CRAMs, TIDDIT, Sniffles2, Severus, Jasmine, SURVIVOR, OctopuSV VCF/BEDPE products, source-support and merger-concordance tables, BND topology validation, CNV/SV concordance, and packaged Truvari evidence.",
        "",
        md_table(package_roles, [("tier", "Tier"), ("role", "Role"), ("type", "Type"), ("samples", "Samples")]),
        "",
        "### Scoped-VCF review treatments",
        "",
        "Treatment tags are review dispositions, not clinical classifications. Confirmed records account for 79.59% of HG002 and 80.21% of NA23687 scoped records; the largest review bucket is `NeedsReview-Unconfirmed` at roughly 10% per sample.",
        "",
        md_table(treatment_rows, [("sample", "Sample"), ("treatment", "Treatment"), ("count", "Count"), ("share_pct", "Share %"), ("total_scoped_records", "Scoped records")]),
        "",
        "## Durable links",
        "",
        f"- Final MultiQC, seven-day presigned URL (generated {generated_iso}): {multiqc_url}",
        f"- Final MultiQC S3 URI: `{s3_uri(MULTIQC_REL)}`",
        f"- This report, Markdown S3 URI: `{report_s3_uri('.md')}`",
        f"- This report, HTML S3 URI: `{report_s3_uri('.html')}`",
        f"- This report, PDF S3 URI: `{report_s3_uri('.pdf')}`",
        f"- HG002 Inflection package: `{s3_uri('daylily-omics-analysis/results/day/hg38/deliveries/inflection_hiomr2_analytical_callsets_vcf_gvcf/take101/HG002-ck2ky6p4wk6exh/')}`",
        f"- NA23687 Inflection package: `{s3_uri('daylily-omics-analysis/results/day/hg38/deliveries/inflection_hiomr2_analytical_callsets_vcf_gvcf/take101/NA23687-zsvw0fa30jhz3n/')}`",
        f"- Full Take101 analysis root: `{s3_uri('')}`",
        "",
        "## Evidence and limitations",
        "",
        "This report is generated from the exported final MultiQC tables, task benchmarks, S3 object inventory, raw Truvari summaries, caller artifacts, SMN orthogonal-call table, reviewed scoped-treatment receipt, and both Inflection package manifests. Raw diagnostic Truvari values are retained for transparency but are not promoted to accepted publication metrics. GIAB truth comparisons apply to HG002 only; NA23687 is not benchmarked against HG002 truth. Stable S3 URIs require authorized AWS access; the presigned MultiQC and report URLs expire after seven days.",
        "",
    ]
    markdown = "\n".join(report_lines)
    (OUT / f"{REPORT_NAME}.md").write_text(markdown, encoding="utf-8")

    source_notes = f"""# Source and report notes

- Audience: technical validation and pipeline operations.
- Report spine: prove Take101 completion; enumerate both samples; explain capabilities; audit alignments, coverage, GIAB-HC SNV, every available Truvari metric including genotype concordance, SMN1/SMN2, runtime, MultiQC, and package contents.
- Sources: live S3 inventory under `{s3_uri('')}`, final MultiQC custom tables, `benchmarks_summary.tsv`, raw Truvari `summary.json` files and NICU tar archive, both package manifests, and the reviewed treatment-count receipt.
- Visual omission: exact tables are used instead of charts because accepted and raw diagnostic Truvari lanes must not be visually conflated; caller/ROI auditability is the decision-useful requirement.
- No GT precision/recall/F1 values were inferred because Take101's raw Truvari summaries provide GT match, GT mismatch, and `gt_concordance`, but not separate GT precision, recall, or F1 fields.
- Report source generated at {generated_iso}; seven-day URLs are ephemeral credentials and must not be treated as durable provenance.
"""
    (OUT / "SOURCE_NOTES.md").write_text(source_notes, encoding="utf-8")

    evidence = {
        "generated_at": generated_iso,
        "analysis_root_s3_uri": s3_uri(""),
        "samples": SAMPLES,
        "s3_object_count": len(objects),
        "coverage_rows": len(coverage),
        "giabhc_rows": len(giab_rows),
        "sv_callset_rows": len(callsets),
        "truvari_rows_with_genotype_concordance": len(truvari_rows),
        "smn_rows": len(smn_rows),
        "package_count": len(packages),
        "report_s3_uris": {"md": report_s3_uri(".md"), "html": report_s3_uri(".html"), "pdf": report_s3_uri(".pdf")},
    }
    (OUT / "evidence_summary.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(OUT / f"{REPORT_NAME}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
