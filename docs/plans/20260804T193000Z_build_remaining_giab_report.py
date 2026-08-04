#!/usr/bin/env python3
"""Build the remaining-GIAB HIOMR2 final analytical report from exported evidence."""

from __future__ import annotations

import csv
import gzip
import io
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import boto3


PROFILE = "lsmc"
REGION = "us-west-2"
BUCKET = "lsmc-ssf-sequencing-data"
PREFIX = "derived/preval-hiomr2/remaining-giab/"
RESULTS = PREFIX + "daylily-omics-analysis/results/day/hg38/"
OUT = Path("/Users/jmajor/Downloads/remaining-giab-hiomr2-final-report")
REPORT_NAME = "REMAINING_GIAB_HIOMR2_FINAL_REPORT"
REPORT_REL = f"daylily-omics-analysis/results/day/hg38/reports/remaining-giab-final/{REPORT_NAME}.md"
REPORT_PDF_REL = REPORT_REL[:-3] + ".pdf"
MULTIQC_REL = "daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc.html"
SAMPLES = {
    "HG003-cqp3zghjfqgykp": "HG003",
    "HG004-9zznm9yqnkwtjr": "HG004",
    "NA19235-p9yktjchebvwjf": "NA19235",
    "NA20775-qhyxr5gkfymvhd": "NA20775",
}
EXPECTED_SMN = {
    "HG003": (2, 2),
    "HG004": (2, 2),
    "NA19235": (4, 0),
    "NA20775": (3, 1),
}


session = boto3.Session(profile_name=PROFILE, region_name=REGION)
s3 = session.client("s3")


def get_bytes(relative: str) -> bytes:
    return s3.get_object(Bucket=BUCKET, Key=RESULTS + relative)["Body"].read()


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


def f(value: str, digits: int = 3) -> str:
    if value in ("", "NA", None):
        return "NA"
    return f"{float(value):.{digits}f}"


def external(uid: str) -> str:
    return SAMPLES.get(uid, uid.split("-")[0])


def s3_uri(relative: str) -> str:
    return f"s3://{BUCKET}/{PREFIX}{relative}"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    data_dir = OUT / "data"
    data_dir.mkdir(exist_ok=True)
    objects = list_objects()
    object_map = {str(row["Key"]): row for row in objects}

    alignstats = tsv("other_reports/alignstats_combo_mqc.tsv")
    coverage: list[dict[str, object]] = []
    alignment_files: list[dict[str, object]] = []
    labels = {
        "sentdhiomr2sr": "Illumina full-coverage analysis alignment",
        "sentdhiomr2lr": "ONT [0,25 h) analysis alignment",
        "sentdhiomr2rsr": "restricted short-read comparison alignment",
    }
    for row in alignstats:
        if row["aligner"] not in labels:
            continue
        coverage.append(
            {
                "sample": external(row["base_sample"]),
                "alignment": row["aligner"] + "." + row["deduper"],
                "modality": labels[row["aligner"]],
                "mean_coverage_x": f(row["WgsCoverageMean"], 2),
                "median_coverage_x": f(row["WgsCoverageMedian"], 1),
                "bases_30x_pct": f(row["WgsCoverageBases30Pct"], 2),
                "mapped_reads_pct": f(row["MappedReadsPct"], 2),
                "duplicate_reads_pct": f(row["DuplicateReadsPct"], 2),
                "insert_size_median_bp": row["InsertSizeMedian"],
            }
        )
        source = row["InputFileName"]
        marker = "/results/day/hg38/"
        relative = source.split(marker, 1)[1] if marker in source else source.removeprefix("results/day/hg38/")
        key = RESULTS + relative
        obj = object_map.get(key)
        alignment_files.append(
            {
                "sample": external(row["base_sample"]),
                "alignment": row["aligner"] + "." + row["deduper"],
                "format": Path(relative).suffix.lstrip(".").upper(),
                "size_gb": f(str(int(obj["Size"]) / 1e9), 3) if obj else "not resolved",
                "s3_uri": s3_uri("daylily-omics-analysis/results/day/hg38/" + relative),
            }
        )
    coverage.sort(key=lambda row: (str(row["sample"]), str(row["alignment"])))
    alignment_files.sort(key=lambda row: (str(row["sample"]), str(row["alignment"])))
    write_tsv(data_dir / "coverage_and_alignment_stats.tsv", coverage)
    write_tsv(data_dir / "alignment_files.tsv", alignment_files)

    giab_rows = []
    for row in tsv("other_reports/giab_concordance_mqc.tsv"):
        if row["ROI"] != "giabHC" or row["SampleID"] not in {"HG003", "HG004"}:
            continue
        if row["SNVCaller"] not in {"sentdhiomr2", "sentdhiomr2_cli_gvcf"}:
            continue
        giab_rows.append(
            {
                "sample": row["SampleID"],
                "caller": row["SNVCaller"],
                "variant_class": row["VariantClass"],
                "f_score": f(row["Fscore"], 6),
                "precision": f(row["Precision"], 6),
                "recall": f(row["Sensitivity-Recall"], 6),
                "tp": str(int(float(row["TP"]))),
                "fp": str(int(float(row["FP"]))),
                "fn": str(int(float(row["FN"]))),
                "status": row["ConcordanceStatus"],
            }
        )
    class_order = {name: i for i, name in enumerate(("SNPts", "SNPtv", "INS_50", "DEL_50", "Indel_50", "INS_gt50", "DEL_gt50", "Indel_gt50", "All"))}
    giab_rows.sort(key=lambda row: (str(row["sample"]), str(row["caller"]), class_order.get(str(row["variant_class"]), 99)))
    expected_giab = 36
    if len(giab_rows) != expected_giab:
        raise RuntimeError(f"Expected {expected_giab} GIAB-HC rows, found {len(giab_rows)}")
    write_tsv(data_dir / "giabhc_snv_concordance.tsv", giab_rows)

    nicu_artifacts = tsv("other_reports/sentdhiomr2_nicu_artifacts_mqc.tsv")
    callset_rows = []
    for row in nicu_artifacts:
        role = row["artifact_role"]
        if row["semantic_type"] != "vcf" or role.endswith("_index"):
            continue
        callset_rows.append(
            {
                "sample": external(row["base_sample"]),
                "producer": row["producer"],
                "version": row["producer_version"],
                "artifact_role": role,
                "records": row["record_count"] or "NA",
                "tier": row["package_tier"],
                "source_path": row["source_path"],
            }
        )
    callset_rows.sort(key=lambda row: (str(row["sample"]), str(row["producer"]), str(row["artifact_role"])))
    write_tsv(data_dir / "sv_callset_inventory.tsv", callset_rows)

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
    full_callsets = []
    for uid, sample in SAMPLES.items():
        sample_prefix = RESULTS + uid + "/"
        for caller, role, fragment, suffix, package_tier in callset_specs:
            matches = [
                key for key in object_map
                if key.startswith(sample_prefix) and fragment in key and key.endswith(suffix)
            ]
            if len(matches) != 1:
                raise RuntimeError(f"Expected one {caller} callset for {sample}, found {len(matches)}")
            key = matches[0]
            full_callsets.append(
                {
                    "sample": sample,
                    "caller_or_composite": caller,
                    "role": role,
                    "size_mb": f(str(int(object_map[key]["Size"]) / 1e6), 3),
                    "package_tier": package_tier,
                    "s3_uri": f"s3://{BUCKET}/{key}",
                }
            )
    write_tsv(data_dir / "all_singleton_and_composite_sv_callsets.tsv", full_callsets)

    sv_counts = []
    for filename, caller in (("sentdhiomr2_sniffles2_mqc.tsv", "Sniffles2"), ("sentdhiomr2_tiddit_mqc.tsv", "TIDDIT")):
        for row in tsv("other_reports/" + filename):
            sv_counts.append(
                {
                    "sample": external(row["base_sample"]),
                    "caller": caller,
                    "records": row["total_records"],
                    "DEL": row["DEL"],
                    "INS": row["INS"],
                    "DUP": row["DUP"],
                    "INV": row["INV"],
                    "BND": row["BND"],
                    "status": row["status"],
                }
            )
    write_tsv(data_dir / "direct_sv_caller_counts.tsv", sv_counts)

    nicu_summary = tsv("other_reports/sentdhiomr2_nicu_summary_mqc.tsv")
    warning = nicu_summary[0]["truvari_warning"]
    truvari_callers = [
        ("Manta", "singleton"), ("Dysgu", "singleton"), ("LongReadSV", "singleton"),
        ("TIDDIT", "singleton"), ("Sniffles2", "singleton"), ("Severus", "singleton"),
        ("Jasmine", "composite merger"), ("SURVIVOR", "composite merger"),
        ("OctopuSV", "composite merger"),
    ]
    truvari_rows = [
        {
            "caller_or_composite": caller,
            "role": role,
            "callsets_present": "yes",
            "truvari_metrics": "not emitted",
            "precision": "NA",
            "recall": "NA",
            "f1": "NA",
            "reason": "GIAB SV v5.0q truth is HG002-only; remaining-GIAB has no active HG002 unit",
        }
        for caller, role in truvari_callers
    ]
    write_tsv(data_dir / "sv_truvari_availability.tsv", truvari_rows)

    smn_rows = []
    for row in tsv("other_reports/smn12_orthogonal_calls_mqc.tsv"):
        sample = row["SampleID"]
        expected = EXPECTED_SMN[sample]
        smn_rows.append(
            {
                "sample": sample,
                "campaign_expected_smn1": expected[0],
                "campaign_expected_smn2": expected[1],
                "sentieon_smn1_copy_number": row["sentieon_smn1_copy_number"],
                "sentieon_smn2_copy_number": row["sentieon_smn2_copy_number"],
                "smncopynumbercaller_smn1": row["smncopynumbercaller_smn1_copy_number"],
                "smncopynumbercaller_smn2": row["smncopynumbercaller_smn2_copy_number"],
                "smncopynumbercaller_status": row["smncopynumbercaller_status"],
                "current_run_expected_fields": row["expected_smn1_copy_number"] + "/" + row["expected_smn2_copy_number"],
                "interpretation": "matches campaign expectation" if (row["smncopynumbercaller_smn1_copy_number"], row["smncopynumbercaller_smn2_copy_number"]) == (str(expected[0]), str(expected[1])) else "discordant with campaign expectation",
            }
        )
    write_tsv(data_dir / "smn12_results.tsv", smn_rows)

    contamination = []
    for row in tsv("other_reports/contamination_mqc.tsv"):
        contamination.append(
            {
                "sample": row["external_sample_id"],
                "alignment": row["aligner"] + "." + row["deduper"],
                "gatk_pct": f(row["gatk_contamination_pct"], 3),
                "site_mix_pct": f(row["site_mix_contamination_pct"], 3),
                "status": row["gatk_status"] + "/" + row["site_mix_status"],
            }
        )
    write_tsv(data_dir / "contamination_summary.tsv", contamination)
    sex_rows = tsv("other_reports/sex_gender_rollup_mqc.tsv")
    sex_summary = [
        {
            "sample": row["SampleID"],
            "reported": row["reported_sex_normalized"] or "not configured",
            "short_read": row["sr_derived_sex_chromosome_complements"],
            "long_read": row["lr_derived_sex_chromosome_complements"],
            "peddy": row["peddy_predicted_genders"],
            "status": row["comparison_status"],
            "note": row["reason_codes"] or "consistent",
        }
        for row in sex_rows
    ]
    write_tsv(data_dir / "sex_gender_summary.tsv", sex_summary)

    benchmarks = tsv("reports/benchmarks.tsv")
    runtime_rows = []
    for uid, sample in SAMPLES.items():
        rows = [row for row in benchmarks if row.get("sample", "").rstrip(".") == uid and row.get("status") == "success"]
        if not rows:
            continue
        starts = [datetime.fromisoformat(row["start_datetime"].replace("Z", "+00:00")) for row in rows if row["start_datetime"] not in ("", "NA")]
        ends = [datetime.fromisoformat(row["end_datetime"].replace("Z", "+00:00")) for row in rows if row["end_datetime"] not in ("", "NA")]
        longest = max(rows, key=lambda row: float(row["s"]))
        runtime_rows.append(
            {
                "sample": sample,
                "benchmark_rows": len(rows),
                "benchmark_span_hours": f(str((max(ends) - min(starts)).total_seconds() / 3600), 2),
                "task_wall_hours_sum": f(str(sum(float(row["s"]) for row in rows) / 3600), 2),
                "allocated_vcpu_hours": f(str(sum(float(row["s"]) * float(row["snakemake_threads"]) for row in rows) / 3600), 1),
                "task_cost_usd": f(str(sum(float(row["task_cost"]) for row in rows)), 2),
                "longest_rule": longest["rule"],
                "longest_rule_hours": f(str(float(longest["s"]) / 3600), 2),
            }
        )
    write_tsv(data_dir / "runtime_per_sample.tsv", runtime_rows)

    manifest_prefix = RESULTS + "deliveries/inflection_hiomr2_analytical_callsets_vcf_gvcf/remaining-giab/"
    manifest_keys = sorted(key for key in object_map if key.startswith(manifest_prefix) and key.endswith("/package_manifest.json"))
    if len(manifest_keys) != 4:
        raise RuntimeError(f"Expected four exported package manifests, found {len(manifest_keys)}")
    package_rows = []
    role_counter: Counter[tuple[str, str, str]] = Counter()
    for key in manifest_keys:
        payload = json.loads(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
        artifacts = payload["artifacts"]
        sample = payload["external_sample_id"]
        package_rows.append(
            {
                "sample": sample,
                "analysis_unit": payload["analysis_unit_uid"],
                "schema": payload["schema"],
                "artifacts": payload["artifact_count"],
                "established": sum(a["package_tier"] == "established" for a in artifacts),
                "experimental": sum(a["package_tier"] == "experimental" for a in artifacts),
                "declared_gb": f(str(sum(int(a["bytes"]) for a in artifacts) / 1e9), 3),
                "customer_release_eligible": payload["customer_release_eligible"],
                "manifest_s3_uri": f"s3://{BUCKET}/{key}",
            }
        )
        for artifact in artifacts:
            role_counter[(artifact["package_tier"], artifact["role"], artifact["semantic_type"])] += 1
    package_rows.sort(key=lambda row: str(row["sample"]))
    package_roles = [
        {"tier": key[0], "role": key[1], "type": key[2], "sample_occurrences": count}
        for key, count in sorted(role_counter.items())
    ]
    write_tsv(data_dir / "inflection_package_summary.tsv", package_rows)
    write_tsv(data_dir / "inflection_package_artifact_roles.tsv", package_roles)

    producer_summary = []
    for caller, role, _, _, package_tier in callset_specs:
        rows = [row for row in full_callsets if row["caller_or_composite"] == caller]
        producer_summary.append(
            {
                "caller_or_composite": caller,
                "role": role,
                "samples": len(rows),
                "size_range_mb": f"{min(float(row['size_mb']) for row in rows):.3f}–{max(float(row['size_mb']) for row in rows):.3f}",
                "package_tier": package_tier,
            }
        )

    multiqc_url = os.environ.get("MULTIQC_PRESIGNED_URL") or s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": PREFIX + MULTIQC_REL},
        ExpiresIn=604800,
    )
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    md: list[str] = []
    md.append("# Remaining-GIAB full-coverage HIOMR2 final report")
    md.append("")
    md.append(f"Generated: {generated}")
    md.append("")
    md.append("## How to execute the pipeline")
    md.append("")
    md.append("The analytical run completed on DayOA `13.4.3`. DayOA `13.4.4` is the immutable reproduction release: it contains the same proven analytical code plus the checked-in operator runbook derived from this closeout. The six exact DayOA manifest tables and referenced FASTQ inputs are constructed and staged by upstream DYEC/BJuice tools; they are deliberately not recreated below.")
    md.append("")
    md.append("### Via the DYEC CLI")
    md.append("")
    md.append("Set `AWS_PROFILE`, `AWS_REGION`, `CLUSTER`, `EXECUTING_ENTITY`, `ANALYSIS_ID`, `SESSION_NAME`, `MANIFEST_DIR`, `PAYLOAD_STAGING_S3_URI`, `EXPORT_S3_URI`, and `EXPORT_RECEIPT_DIR` to explicit reviewed values. Then inspect the cluster and catalog contract:")
    md.append("")
    md.append("```bash\ndyec cluster-info --profile \"$AWS_PROFILE\" --region \"$AWS_REGION\"\ndyec catalog show inflection-bjuice-product-v0.2\n```")
    md.append("")
    md.append("Launch the dry-run controller with the exact five targets. The batch identifier is literal and must not be inferred:")
    md.append("")
    md.append("```bash\ndyec workflow launch \\\n+  --profile \"$AWS_PROFILE\" --region \"$AWS_REGION\" --cluster \"$CLUSTER\" \\\n+  --repository daylily-omics-analysis --git-tag 13.4.4 \\\n+  --analysis-id \"$ANALYSIS_ID\" --executing-entity \"$EXECUTING_ENTITY\" \\\n+  --input-contract six_manifest --manifest-dir \"$MANIFEST_DIR\" \\\n+  --payload-staging-s3-uri \"$PAYLOAD_STAGING_S3_URI\" --session-name \"$SESSION_NAME\" \\\n+  --project RnD --cost-center RnD --genome hg38 --jobs 444 \\\n+  --dy-command \"DAY_CONTAINERIZED=true dy-r produce_sentdhiomr2_kitchensink produce_sentdhiomr2_nicu_research produce_sentdhiomr2_jasmine_sharded_per_sample produce_sentdhiomr2_inflection_analytical_package results/day/hg38/reports/DAY_final_multiqc.html --config genome_build=hg38 'aligners=[\\\"sentmm2ont\\\"]' 'dedupers=[\\\"na\\\"]' 'snv_callers=[\\\"sentdhiomr2\\\"]' 'sv_callers=[]' 'htd_callers=[\\\"smn12\\\"]' hiomr2_inflection_package_mode=analytical use_fq_data_starting_hrs=0 use_fq_data_up_to_hrs=25 seqone_delivery_batch_id=$ANALYSIS_ID -j 444 -p -T 1 -k --rerun-triggers mtime -n\" \\\n+  --dry-run\n```")
    md.append("")
    md.append("Require dry-run RC 0. Promote the same exact root with `--reuse-existing-analysis-dir --input-contract none --no-input-staging`, omit the manifest/payload-staging flags, remove the final `-n` inside `--dy-command`, and remove launcher `--dry-run`. Keep the same tag, analysis ID, session lineage, project, cost center, targets, and config.")
    md.append("")
    md.append("Monitor read-only and export only after controller RC 0:")
    md.append("")
    md.append("```bash\ndyec --json workflow status --profile \"$AWS_PROFILE\" --region \"$AWS_REGION\" --cluster \"$CLUSTER\" --session \"$SESSION_NAME\"\ndyec workflow logs --profile \"$AWS_PROFILE\" --region \"$AWS_REGION\" --cluster \"$CLUSTER\" --session \"$SESSION_NAME\" --stream controller --lines 200\ndyec headnode jobs --profile \"$AWS_PROFILE\" --region \"$AWS_REGION\" --cluster \"$CLUSTER\"\ndyec headnode fsx-usage --profile \"$AWS_PROFILE\" --region \"$AWS_REGION\" --cluster \"$CLUSTER\"\ndyec command sample-stats hiomr-kitchensink --name \"$ANALYSIS_ID\" --analysis-root \"/fsx/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID\" --profile \"$AWS_PROFILE\" --region \"$AWS_REGION\" --cluster \"$CLUSTER\"\ndyec export --profile \"$AWS_PROFILE\" --region \"$AWS_REGION\" --cluster \"$CLUSTER\" --source-path \"/fsx/analysis_results/$EXECUTING_ENTITY/$ANALYSIS_ID\" --destination-s3-uri \"$EXPORT_S3_URI\" --output-dir \"$EXPORT_RECEIPT_DIR\" --wait --timeout-seconds 7200\ncat \"$EXPORT_RECEIPT_DIR/fsx_export.yaml\"\n```")
    md.append("")
    md.append("Require export receipt `status: success` and `detached: true`. The example is non-destructive because it does not pass `--delete-data-in-file-system`.")
    md.append("")
    md.append("### On a running headnode with DayOA directly")
    md.append("")
    md.append("Run as `ubuntu` in a persistent one-pane interactive login-shell tmux, with the analysis-root write lock held for workflow writes:")
    md.append("")
    md.append("```bash\nday-clone -t 13.4.4 -d <somename>\ncd /fsx/analysis_results/<executing-entity>/<somename>/daylily-omics-analysis\n```")
    md.append("")
    md.append("At this point, upstream tools have already constructed and staged the six manifest tables and the run config. Initialize the same tmux pane with separate commands:")
    md.append("")
    md.append("```bash\nsource dyoainit\ndy-a slurm hg38\nexport DAY_PROJECT=RnD\nexport DAYLILY_COST_CENTER=RnD\nexport SEQONE_DELIVERY_BATCH_ID=<explicit-analytical-batch-id>\n```")
    md.append("")
    md.append("Run `dy-r` with the five targets and `--configfile config/<run-config>.yaml`, followed by `--config genome_build=hg38 'aligners=[\"sentmm2ont\"]' 'dedupers=[\"na\"]' 'snv_callers=[\"sentdhiomr2\"]' 'sv_callers=[]' 'htd_callers=[\"smn12\"]' hiomr2_inflection_package_mode=analytical use_fq_data_starting_hrs=0 use_fq_data_up_to_hrs=25 \"seqone_delivery_batch_id=$SEQONE_DELIVERY_BATCH_ID\" -j 444 -p -T 1 -k --rerun-triggers mtime -n`. Only after RC 0, repeat the identical command without `-n`. Never invoke Snakemake directly.")
    md.append("")
    md.append("## Executive result")
    md.append("")
    md.append("`remaining-giab` completed the DayOA 13.4.3 HIOMR2 kitchen-sink plus NICU/mega research analysis and final MultiQC at 792/792 workflow steps with controller RC 0. The four samples were HG003, HG004, NA19235, and NA20775; each used eight full-coverage Illumina lanes and ONT reads from elapsed hours [0,25). The initially omitted analytical Inflection package target was subsequently run as four isolated packaging jobs and produced one validated package manifest per sample.")
    md.append("")
    md.append("This is a research/validation result, not a clinical release. The Inflection package explicitly separates established callsets from experimental NICU/mega artifacts and marks customer-release eligibility false.")
    md.append("")
    md.append("## Pipeline capabilities represented in this run")
    md.append("")
    md.append("- **Manifested hybrid inputs:** explicit specimen, sample, library, sequencing-input, and analysis-unit tables; eight Illumina lanes per sample; bounded ONT elapsed-hour selection; provenance and evidence receipts.")
    md.append("- **Alignment and QC:** full-coverage Illumina, ONT, and restricted short-read comparison alignments; AlignStats, mapping/yield/coverage/insert-size metrics, duplicate metrics, contamination estimates, sex-chromosome inference, Peddy, Somalier relatedness, coverage evenness, and sequence-QC inventories.")
    md.append("- **Small variants:** Sentieon HIOMR2 hard VCF and gVCF outputs, a CLI-gVCF comparison lane, normalization/annotation, GIAB RTG vcfeval across configured regions, and final MultiQC concordance tables.")
    md.append("- **Structural and copy-number variants:** singleton SV callsets from Manta, Dysgu, LongReadSV, TIDDIT, Sniffles2, and Severus; integrated/merged outputs from Jasmine, SURVIVOR, and OctopuSV; CNVscope and supporting normalized/provenance artifacts.")
    md.append("- **Targeted/complex variation:** SMN1/SMN2 copy-number calling, Sentieon segmental-duplication evidence, ExpansionHunter, broader segmental-duplication loci, ROH/UPD, and related targeted reports.")
    md.append("- **Research integration:** per-sample sharded Jasmine, NICU caller reconciliation, BND/topology validation, caller provenance, recoverability receipts, merged VCF/BEDPE products, and explicit warning receipts when a benchmark is not applicable.")
    md.append("- **Reporting and delivery:** strict final MultiQC, benchmark collection, DayOA evidence manifest, and a 37-artifact analytical package per sample with checksums, sizes, roles, tiers, and immutable source provenance.")
    md.append("")
    md.append("## Samples, alignments, and coverage")
    md.append("")
    md.append(md_table(coverage, [("sample", "Sample"), ("alignment", "Alignment"), ("mean_coverage_x", "Mean depth"), ("median_coverage_x", "Median"), ("bases_30x_pct", ">=30x %"), ("mapped_reads_pct", "Mapped %"), ("duplicate_reads_pct", "Duplicate %"), ("insert_size_median_bp", "Median insert")]))
    md.append("")
    md.append("The primary analytical alignment files are CRAMs. The table below links the exact exported objects used by the AlignStats rows; large per-sample Jasmine BAMs are working/intermediate research files and are not the canonical alignment deliverables.")
    md.append("")
    md.append(md_table(alignment_files, [("sample", "Sample"), ("alignment", "Alignment"), ("format", "Format"), ("size_gb", "GB"), ("s3_uri", "S3 URI")]))
    md.append("")
    md.append("## GIAB high-confidence small-variant concordance")
    md.append("")
    md.append("F-scores below are for ROI `giabHC`. HG003 and HG004 have configured truth and each has both the workflow hard-call lane (`sentdhiomr2`) and CLI-gVCF comparison lane (`sentdhiomr2_cli_gvcf`). NA19235 and NA20775 are SMN positive controls and do not have GIAB small-variant truth rows in this run.")
    md.append("")
    md.append(md_table(giab_rows, [("sample", "Sample"), ("caller", "Caller"), ("variant_class", "Class"), ("f_score", "F-score"), ("precision", "Precision"), ("recall", "Recall"), ("tp", "TP"), ("fp", "FP"), ("fn", "FN")]))
    md.append("")
    md.append("## Structural-variant outputs and Truvari")
    md.append("")
    md.append("All singleton and composite callsets below were produced. Direct record-count summaries are available for TIDDIT and Sniffles2; the S3 inventory proves each normalized VCF, while the package manifests add checksums and tiered treatment for the callsets selected for delivery.")
    md.append("")
    md.append(md_table(producer_summary, [("caller_or_composite", "Caller/composite"), ("role", "Role"), ("samples", "Samples"), ("size_range_mb", "VCF size range MB"), ("package_tier", "Package treatment")]))
    md.append("")
    md.append(md_table(sv_counts, [("sample", "Sample"), ("caller", "Caller"), ("records", "Records"), ("DEL", "DEL"), ("INS", "INS"), ("DUP", "DUP"), ("INV", "INV"), ("BND", "BND")]))
    md.append("")
    md.append("### Truvari availability")
    md.append("")
    md.append("No numeric Truvari precision, recall, or F1 values exist for any remaining-GIAB singleton or composite callset. Each sample has a schema-1.1 warning receipt with an empty metric object. The workflow correctly did not compare these callsets because its GIAB SV v5.0q truth contract is valid only for HG002, and this four-sample cohort contains no active HG002 analysis unit. Missing metrics are therefore **not zero scores** and are not analytical failures.")
    md.append("")
    md.append(md_table(truvari_rows, [("caller_or_composite", "Caller/composite"), ("role", "Role"), ("callsets_present", "Output"), ("truvari_metrics", "Truvari"), ("f1", "F1"), ("reason", "Reason")]))
    md.append("")
    md.append(f"Representative workflow warning: `{warning}`")
    md.append("")
    md.append("## SMN1/SMN2 copy-number results")
    md.append("")
    md.append("The current run's orthogonal summary contains complete SMNCopyNumberCaller results but `NA` in the Sentieon SMN1/SMN2 copy-number fields; Sentieon segmental-duplication VCFs exist, but this run did not materialize their copy-number interpretation into those MultiQC fields. Campaign expectations are shown for validation context and were not configured as workflow truth fields (`NOT_CONFIGURED`).")
    md.append("")
    md.append(md_table(smn_rows, [("sample", "Sample"), ("campaign_expected_smn1", "Expected SMN1"), ("campaign_expected_smn2", "Expected SMN2"), ("sentieon_smn1_copy_number", "Sentieon SMN1"), ("sentieon_smn2_copy_number", "Sentieon SMN2"), ("smncopynumbercaller_smn1", "SMNCNC SMN1"), ("smncopynumbercaller_smn2", "SMNCNC SMN2"), ("smncopynumbercaller_status", "Status"), ("interpretation", "Interpretation")]))
    md.append("")
    md.append("## MultiQC review")
    md.append("")
    md.append("- All 12 alignment/method contamination rows report `ok`. Full-coverage Illumina site-mix estimates are 0.2% for HG003/HG004 and remain low across the cohort; long-read method estimates are higher and should be interpreted as modality-specific estimates, not automatically as sample swaps.")
    md.append("- Reported and primary short-read-derived sex agree for HG003 and HG004. NA19235 and NA20775 have no reported gender configured; their primary short-read, long-read, and Peddy calls are female. Restricted short-read comparison rows soft-fail as XY for three female samples, which the rollup records explicitly without overriding primary evidence.")
    md.append("- Somalier reports all six pairwise relationships as unrelated in each short-read and long-read batch, with no duplicate/identical or first-degree pairs.")
    md.append("- Final MultiQC includes coverage, alignment, contamination, sequence QC, sex/gender, relatedness, small-variant concordance, targeted calls, NICU artifacts, direct SV summaries, and benchmark/provenance sections.")
    md.append("")
    md.append(md_table(sex_summary, [("sample", "Sample"), ("reported", "Reported"), ("short_read", "SR"), ("long_read", "LR"), ("peddy", "Peddy"), ("status", "Status"), ("note", "Note")]))
    md.append("")
    md.append("## Runtime evidence")
    md.append("")
    md.append("Benchmark span is the interval from the first to last successful task for a sample; summed task wall time is not controller elapsed time. Task cost is the sum of recorded task-level costs and excludes cluster startup/pending overhead.")
    md.append("")
    md.append(md_table(runtime_rows, [("sample", "Sample"), ("benchmark_rows", "Tasks"), ("benchmark_span_hours", "Span h"), ("task_wall_hours_sum", "Task-wall h"), ("allocated_vcpu_hours", "vCPU h"), ("task_cost_usd", "Task cost $"), ("longest_rule", "Longest rule"), ("longest_rule_hours", "Longest h")]))
    md.append("")
    md.append("## Inflection analytical packaging")
    md.append("")
    md.append("Packaging was the only omitted objective after the original 792-step run. A dry gate planned exactly four package rules and no analytical recomputation. The first live invocation was correctly refused before DAG execution because the dry-run wrapper had released the write lock; after normal lock reacquisition, jobs 5445–5448 produced the four packages. Each manifest uses schema `dayoa.hiomr2_inflection_analytical_package/1.3`, declares 37 artifacts (9 established and 28 experimental), and all referenced files were verified present and non-empty before export.")
    md.append("")
    md.append(md_table(package_rows, [("sample", "Sample"), ("schema", "Schema"), ("artifacts", "Artifacts"), ("established", "Established"), ("experimental", "Experimental"), ("declared_gb", "Declared GB"), ("customer_release_eligible", "Customer release"), ("manifest_s3_uri", "Manifest S3 URI")]))
    md.append("")
    md.append("The established tier contains the primary analytical VCF/gVCF/CNV deliverables and indexes. The experimental tier contains normalized singleton SV caller outputs, Jasmine/SURVIVOR/OctopuSV integrations, direct caller summaries/supporting tables, and NICU provenance. The package does not reinterpret warning-only Truvari receipts as accuracy metrics and does not mark research artifacts as clinically interpretable.")
    md.append("")
    md.append(md_table(package_roles, [("tier", "Tier"), ("role", "Role"), ("type", "Type"), ("sample_occurrences", "Samples")]))
    md.append("")
    md.append("## Durable links")
    md.append("")
    md.append(f"- Final MultiQC, seven-day presigned URL (generated {generated}): {multiqc_url}")
    md.append(f"- Final MultiQC S3 URI: `{s3_uri(MULTIQC_REL)}`")
    md.append(f"- This report, Markdown S3 URI: `{s3_uri(REPORT_REL)}`")
    md.append(f"- This report, PDF S3 URI: `{s3_uri(REPORT_PDF_REL)}`")
    md.append(f"- Full remaining-GIAB export root: `s3://{BUCKET}/{PREFIX}`")
    md.append("")
    md.append("## Evidence and limitations")
    md.append("")
    md.append("This report is generated from the exported final MultiQC tables, task benchmarks, caller artifact manifests, direct SV summaries, SMN orthogonal-call table, and the four package manifests. Numerical Truvari fields are intentionally absent because the workflow emitted warning receipts rather than metrics. Stable S3 URIs require authorized AWS access; the presigned MultiQC URL expires after seven days.")

    report_md = OUT / f"{REPORT_NAME}.md"
    report_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    evidence = {
        "generated_at": generated,
        "source_s3_prefix": f"s3://{BUCKET}/{PREFIX}",
        "object_count": len(objects),
        "object_bytes": sum(int(row["Size"]) for row in objects),
        "coverage_rows": len(coverage),
        "alignment_files": len(alignment_files),
        "giabhc_rows": len(giab_rows),
        "sv_callset_rows": len(callset_rows),
        "truvari_numeric_metrics": 0,
        "smn_rows": len(smn_rows),
        "package_manifests": len(package_rows),
        "package_artifact_roles": len(package_roles),
        "report_s3_uri": s3_uri(REPORT_REL),
        "report_pdf_s3_uri": s3_uri(REPORT_PDF_REL),
        "multiqc_s3_uri": s3_uri(MULTIQC_REL),
    }
    (OUT / "evidence_summary.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print(f"report={report_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
