#!/usr/bin/env python3
"""Build the canonical Take222 technical report artifact from reviewed datasets."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("/Users/jmajor/Downloads/dyec-dayao-pipe-runtime-artifacts")
OUTPUT = ROOT / "artifact.json"


def coerce(value: str):
    if value == "":
        return ""
    if re.fullmatch(r"-?[0-9]+", value):
        return int(value)
    if re.fullmatch(r"-?(?:[0-9]+\.[0-9]*|[0-9]*\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value):
        return float(value)
    if value == "True":
        return True
    if value == "False":
        return False
    return value


def read_tsv(filename: str) -> list[dict[str, object]]:
    with (ROOT / filename).open(newline="", encoding="utf-8") as handle:
        return [{key: coerce(value) for key, value in row.items()} for row in csv.DictReader(handle, delimiter="\t")]


def source(source_id: str, label: str, path: str, description: str, filters: list[str] | None = None):
    query = {
        "engine": "duckdb",
        "language": "sql",
        "sql": f"SELECT * FROM read_csv_auto('{path}', delim='\\t', header=true)",
        "description": description,
        "tables_used": [path],
        "executed_at": generated_at,
    }
    if filters:
        query["filters"] = filters
    return {"id": source_id, "label": label, "path": path, "query": query}


def columns(*fields: tuple[str, str]):
    return [{"field": field, "label": label} for field, label in fields]


generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
coverage = read_tsv("take222_sample_coverage_fragment_stats.tsv")
giab_all = read_tsv("take222_giabhc_snv_results.tsv")
giab = [row for row in giab_all if row["caller"] == "sentdhiomr2" and row["variant_class"] in {"All", "SNPts", "SNPtv"}]
for row in giab:
    row["f_score_exact"] = f"F1={float(row['f_score']):.9f}"
    row["precision_exact"] = f"P={float(row['precision']):.9f}"
    row["recall_exact"] = f"R={float(row['recall']):.9f}"
smn = read_tsv("take222_smn12_results.tsv")
runtime = read_tsv("take222_runtime_per_sample.tsv")
runtime_samples = [row for row in runtime if row["sample"] != "shared_or_global"]
runtime_rules = read_tsv("take222_runtime_by_rule.tsv")[:20]
nicu = read_tsv("take222_nicu_summary.tsv")
direct_sv = read_tsv("take222_direct_sv_counts.tsv")
packages = read_tsv("take222_inflection_package_summary.tsv")
package_roles = read_tsv("take222_inflection_artifact_roles.tsv")
review_tags = read_tsv("take222_variant_review_tags.tsv")
current = read_tsv("take222_current_testing_snapshot.tsv")
for row in current:
    if row["lane"] == "remaining-giab":
        row["report_state"] = "Packaging incomplete"
        row["report_progress"] = "Workflow RC=0"
    else:
        row["report_state"] = "Failed"
        row["report_progress"] = row["progress"]

inventory = read_tsv("take222_output_inventory_category_summary.tsv")

coverage_chart = [
    {
        "sample_modality": f"{row['sample']} {'ILMN' if row['modality'] == 'Illumina' else 'ONT'}",
        "sample": row["sample"],
        "modality": row["modality"],
        "mean_coverage_x": row["mean_coverage_x"],
        "median_coverage_x": row["median_coverage_x"],
    }
    for row in coverage
]
giab_chart = [
    {
        "sample_variant": f"{row['sample']} {row['variant_class']}",
        "sample": row["sample"],
        "variant_class": row["variant_class"],
        "f_score": row["f_score"],
        "f_score_error_ppm": round((1 - float(row["f_score"])) * 1_000_000, 3),
        "precision": row["precision"],
        "recall": row["recall"],
    }
    for row in giab
]
runtime_chart = [
    {
        "sample": row["sample"],
        "task_wall_hours_sum": row["task_wall_hours_sum"],
        "benchmark_span_hours": row["benchmark_span_hours"],
        "task_cost_usd": row["task_cost_usd"],
    }
    for row in runtime_samples
]

combined_review: dict[str, int] = {}
for row in review_tags:
    combined_review[str(row["review_tag"])] = combined_review.get(str(row["review_tag"]), 0) + int(row["count"])
review_total = sum(combined_review.values())
review_chart = [
    {"review_tag": tag, "count": count, "share_pct": round(100 * count / review_total, 6)}
    for tag, count in sorted(combined_review.items(), key=lambda item: item[1], reverse=True)
]

sources = [
    source("coverage", "Final Take222 MultiQC coverage and fragment metrics", "take222_sample_coverage_fragment_stats.tsv", "Reviewed AlignStats and Samtools metrics for duplicate-marked Illumina and retained ONT [0,25) alignments."),
    source("giab", "RTG vcfeval GIAB high-confidence results", "take222_giabhc_snv_results.tsv", "All final hard-VCF and CLI-gVCF RTG rows for ROI=giabHC.", ["ROI = giabHC", "HG003 and HG004 configured truth only"]),
    source("smn", "Orthogonal SMN1/2 caller rollup", "take222_smn12_results.tsv", "Sentieon regional SMN1 and SMNCopyNumberCaller copy-number results without conflating caller roles."),
    source("runtime", "Per-sample benchmark aggregation", "take222_runtime_per_sample.tsv", "Sample-scoped task-wall sums, benchmark spans, allocated vCPU-hours, task cost, and longest rules.", ["Benchmark rows only", "Controller/queue/startup time excluded"]),
    source("runtime_rules", "Runtime aggregation by rule", "take222_runtime_by_rule.tsv", "Aggregate rule-level task wall time, allocated vCPU-hours, observed CPU, and task cost."),
    source("nicu", "NICU research summary", "take222_nicu_summary.tsv", "Merged-call support, topology, CNV-SV comparison, recoverability, and explicit Truvari applicability status."),
    source("direct_sv", "Direct TIDDIT and Sniffles2 output counts", "take222_direct_sv_counts.tsv", "Per-sample SV type and record counts surfaced in final MultiQC."),
    source("packages", "Inflection analytical package summary", "take222_inflection_package_summary.tsv", "One schema-1.3 analytical package per sample with tier counts, bytes, and release eligibility."),
    source("package_roles", "Inflection artifact-role catalog", "take222_inflection_artifact_roles.tsv", "Deduplicated established and experimental artifact roles across four package manifests."),
    source("review_tags", "Scoped-VCF review treatments", "take222_variant_review_tags.tsv", "Per-sample review-treatment counts and within-sample shares; these are not clinical classifications."),
    source("current", "Current live testing snapshot", "take222_current_testing_snapshot.tsv", "Read-only workflow/controller/queue/FSx snapshot for the two current DayOA 13.4.3 campaigns."),
    source("inventory", "Complete Take222 output inventory summary", "take222_output_inventory_category_summary.tsv", "Reads conservative file-family counts and bytes derived from the complete 5,881-path inventory."),
]

charts = [
    {
        "id": "coverage_chart",
        "title": "Mean observed coverage by sample and modality",
        "subtitle": "Duplicate-marked Illumina and retained ONT elapsed hours [0,25).",
        "type": "bar",
        "dataset": "coverage_chart",
        "sourceId": "coverage",
        "encodings": {
            "x": {"field": "sample_modality", "type": "nominal"},
            "y": {"field": "mean_coverage_x", "type": "quantitative"},
            "tooltip": [
                {"field": "sample", "type": "nominal"},
                {"field": "modality", "type": "nominal"},
                {"field": "mean_coverage_x", "type": "quantitative"},
                {"field": "median_coverage_x", "type": "quantitative"},
            ],
        },
    },
    {
        "id": "giab_chart",
        "title": "GIAB high-confidence F-score error",
        "subtitle": "Parts per million below a perfect F-score; lower is better. Hard-VCF lane; CLI-gVCF is identical.",
        "type": "bar",
        "dataset": "giab_chart",
        "sourceId": "giab",
        "encodings": {
            "x": {"field": "sample_variant", "type": "nominal"},
            "y": {"field": "f_score_error_ppm", "type": "quantitative"},
            "tooltip": [
                {"field": "sample", "type": "nominal"},
                {"field": "variant_class", "type": "nominal"},
                {"field": "f_score_error_ppm", "type": "quantitative"},
                {"field": "f_score", "type": "quantitative"},
                {"field": "precision", "type": "quantitative"},
                {"field": "recall", "type": "quantitative"},
            ],
        },
    },
    {
        "id": "runtime_chart",
        "title": "Sample-scoped benchmark task-wall burden",
        "subtitle": "Task-wall sums are workload, not controller makespan; all four benchmark spans were about 5.60 hours.",
        "type": "bar",
        "dataset": "runtime_chart",
        "sourceId": "runtime",
        "encodings": {
            "x": {"field": "sample", "type": "nominal"},
            "y": {"field": "task_wall_hours_sum", "type": "quantitative"},
            "tooltip": [
                {"field": "sample", "type": "nominal"},
                {"field": "task_wall_hours_sum", "type": "quantitative"},
                {"field": "benchmark_span_hours", "type": "quantitative"},
                {"field": "task_cost_usd", "type": "quantitative"},
            ],
        },
    },
    {
        "id": "review_chart",
        "title": "Combined scoped-VCF review-treatment share",
        "subtitle": "Review treatments prioritize evidence; they are not clinical classifications.",
        "type": "bar",
        "dataset": "review_chart",
        "sourceId": "review_tags",
        "encodings": {
            "x": {"field": "review_tag", "type": "nominal"},
            "y": {"field": "share_pct", "type": "quantitative"},
            "tooltip": [
                {"field": "review_tag", "type": "nominal"},
                {"field": "count", "type": "quantitative"},
                {"field": "share_pct", "type": "quantitative"},
            ],
        },
    },
]

tables = [
    {"id": "coverage_table", "title": "Coverage and fragment metrics", "dataset": "coverage", "sourceId": "coverage", "defaultSort": {"field": "sample", "direction": "asc"}, "columns": columns(("sample", "Sample"), ("modality", "Modality"), ("mean_coverage_x", "Mean coverage"), ("median_coverage_x", "Median coverage"), ("bases_30x_pct", "Bases >=30x, %"), ("mapped_reads_pct", "Mapped, %"), ("duplicate_reads_pct", "Duplicates, %"), ("insert_size_median_bp", "Insert median, bp"), ("insert_size_mean_bp", "Insert mean, bp"))},
    {"id": "giab_table", "title": "GIAB HC hard-VCF concordance", "dataset": "giab", "sourceId": "giab", "defaultSort": {"field": "sample", "direction": "asc"}, "columns": columns(("sample", "Sample"), ("variant_class", "Class"), ("f_score_exact", "F-score"), ("precision_exact", "Precision"), ("recall_exact", "Recall"), ("tp", "TP"), ("fp", "FP"), ("fn", "FN"))},
    {"id": "smn_table", "title": "SMN1/2 orthogonal caller results", "dataset": "smn", "sourceId": "smn", "defaultSort": {"field": "sample", "direction": "asc"}, "columns": columns(("sample", "Sample"), ("smn_copynumbercaller_smn1_cn", "SMNCNC SMN1 CN"), ("smn_copynumbercaller_smn2_cn", "SMNCNC SMN2 CN"), ("sentieon_status", "Sentieon regional status"), ("sentieon_smn1_cn", "Sentieon SMN1 CN"), ("overall_concordance", "Truth concordance"), ("discordance_flag", "Rollup flag"))},
    {"id": "runtime_table", "title": "Per-sample benchmark runtime and cost", "dataset": "runtime_samples", "sourceId": "runtime", "defaultSort": {"field": "task_wall_hours_sum", "direction": "asc"}, "columns": columns(("sample", "Sample"), ("benchmark_span_hours", "Benchmark span, h"), ("task_wall_hours_sum", "Task-wall sum, h"), ("allocated_vcpu_hours", "Allocated vCPU-h"), ("task_cost_usd", "Task cost, USD"), ("longest_task_rule", "Longest rule"), ("longest_task_hours", "Longest task, h"))},
    {"id": "runtime_rules_table", "title": "Largest aggregate runtime contributors", "dataset": "runtime_rules", "sourceId": "runtime_rules", "defaultSort": {"field": "task_wall_hours_sum", "direction": "desc"}, "columns": columns(("rule", "Rule"), ("rows", "Rows"), ("task_wall_hours_sum", "Task-wall sum, h"), ("allocated_vcpu_hours", "Allocated vCPU-h"), ("observed_cpu_hours", "Observed CPU-h"), ("task_cost_usd", "Task cost, USD"))},
    {"id": "nicu_table", "title": "NICU merger, topology, and applicability summary", "dataset": "nicu", "sourceId": "nicu", "defaultSort": {"field": "sample", "direction": "asc"}, "columns": columns(("sample", "Sample"), ("jasmine_records", "Jasmine records"), ("jasmine_dysgu_supported", "Dysgu-supported"), ("jasmine_manta_supported", "Manta-supported"), ("cnv_50pct_reciprocal_matches", "CNV-SV matches"), ("bnd_topology_valid", "BND topology"), ("truvari_status", "Truvari"))},
    {"id": "direct_sv_table", "title": "Direct Sniffles2 and TIDDIT output counts", "dataset": "direct_sv", "sourceId": "direct_sv", "defaultSort": {"field": "sample", "direction": "asc"}, "columns": columns(("sample", "Sample"), ("caller", "Caller"), ("total_records", "Records"), ("DEL", "DEL"), ("INS", "INS"), ("INV", "INV"), ("BND", "BND"), ("other", "Other"))},
    {"id": "packages_table", "title": "Inflection analytical packages", "dataset": "packages", "sourceId": "packages", "defaultSort": {"field": "sample", "direction": "asc"}, "columns": columns(("sample", "Sample"), ("artifact_count", "Artifacts"), ("established_artifacts", "Established"), ("experimental_artifacts", "Experimental"), ("declared_bytes", "Declared bytes"), ("package_mode", "Mode"), ("customer_release_eligible", "Release eligible"))},
    {"id": "package_roles_table", "title": "Inflection artifact-role catalog", "dataset": "package_roles", "sourceId": "package_roles", "defaultSort": {"field": "package_tier", "direction": "asc"}, "columns": columns(("package_tier", "Tier"), ("role", "Role"), ("semantic_type", "Type"), ("sample_occurrences", "Sample occurrences"))},
    {"id": "inventory_table", "title": "Complete output inventory by conservative file family", "dataset": "inventory", "sourceId": "inventory", "defaultSort": {"field": "bytes", "direction": "desc"}, "columns": columns(("category", "Family"), ("file_count", "Files"), ("gigabytes", "GB"), ("bytes", "Bytes"))},
    {"id": "current_table", "title": "Current DayOA 13.4.3 testing snapshot", "dataset": "current", "sourceId": "current", "defaultSort": {"field": "lane", "direction": "asc"}, "columns": columns(("lane", "Lane"), ("report_state", "State"), ("report_progress", "Progress"), ("active_jobs", "Active jobs"), ("snapshot_utc", "Snapshot UTC"))},
]

blocks = [
    {"id": "title", "type": "markdown", "body": "# Take222 full-coverage HIOMR2 kitchen-sink, mega/NICU, MultiQC, and Inflection packaging review\n\n## Decision summary\n\nTake222 is the latest completed qualifying run: HG003, HG004, NA19235, and NA20775; eight Illumina lanes plus ONT `[0,25)` per sample; DayOA **13.4.3**; final five-target proof **21/21, RC=0**. It produced 5,881 files (~1.109 TB), final MultiQC, complete NICU research artifacts, authoritative sharded Jasmine, and four Inflection analytical packages. The strongest accuracy evidence is small-variant `giabHC` F-score: **0.998872 HG003** and **0.999336 HG004**. SV Truvari is correctly warning-only because no HG002 is active in this cohort."},
    {"id": "coverage_intro", "type": "markdown", "sourceId": "coverage", "body": "## Coverage and fragment evidence\n\nDuplicate-marked Illumina mean coverage is 37.48–46.07x with >99.80% mapping. ONT `[0,25)` mean coverage is 12.15–14.82x with 93.70–95.83% mapping. NA19235 is the lowest Illumina coverage sample; NA20775 has the highest fraction of bases >=30x."},
    {"id": "coverage_chart_block", "type": "chart", "chartId": "coverage_chart"},
    {"id": "coverage_table_block", "type": "table", "tableId": "coverage_table"},
    {"id": "giab_intro", "type": "markdown", "sourceId": "giab", "body": "## Small-variant accuracy in GIAB HC\n\nHG003 and HG004 have configured GIAB truth. Hard-VCF and CLI-gVCF evaluations are numerically identical across all displayed classes, so they establish route parity rather than two independent measurements."},
    {"id": "giab_chart_block", "type": "chart", "chartId": "giab_chart"},
    {"id": "giab_table_block", "type": "table", "tableId": "giab_table"},
    {"id": "smn_intro", "type": "markdown", "sourceId": "smn", "body": "## SMN1/2 positive-control evidence\n\nSMNCopyNumberCaller reports HG003 2/2, HG004 2/2, NA19235 4/0, and NA20775 3/1. Sentieon's regional SMN1 output completed, but the rollup does not expose numeric copy-number fields. Expected truth CNs are not configured, so no formal concordance result is asserted."},
    {"id": "smn_table_block", "type": "table", "tableId": "smn_table"},
    {"id": "sv_intro", "type": "markdown", "sourceId": "nicu", "body": "## Mega/NICU structural-variant lane\n\nThe research stack includes Manta, Dysgu, Severus, TIDDIT, Sniffles2, LongReadSV, Jasmine, SURVIVOR, and OctopuSV plus exact provenance/comparison artifacts. All four BND topology checks pass. Jasmine produces 234.5k–251.1k union/merge records per sample; these counts are not validated germline event counts. All four Truvari lanes are explicit WARNING receipts with no fabricated metrics because GIAB SV truth is HG002-only."},
    {"id": "nicu_table_block", "type": "table", "tableId": "nicu_table"},
    {"id": "direct_sv_table_block", "type": "table", "tableId": "direct_sv_table"},
    {"id": "review_intro", "type": "markdown", "sourceId": "review_tags", "body": "## Scoped-VCF review treatments\n\nConfirmed records are 79.66–79.76% per sample. The largest review queues are Unconfirmed, AlleleBalance, and LowCoverage. These labels guide evidence review and are not clinical classifications."},
    {"id": "review_chart_block", "type": "chart", "chartId": "review_chart"},
    {"id": "package_intro", "type": "markdown", "sourceId": "packages", "body": "## Inflection analytical dataset\n\nEach schema-1.3 package has 37 artifacts: 9 established and 28 experimental. The four packages total 86.10 GB. Established outputs are the scoped VCF/index, CNVscope VCF/index, LongReadSV VCF/index, short-read CRAM/CRAI, and command manifest. Experimental outputs add the realigned CRAM, normalized callers, three mergers, BEDPE, support/concordance tables, topology/CNV-SV evidence, warning-only Truvari artifacts, and research provenance. All packages are nonclinical and not customer-release eligible."},
    {"id": "packages_table_block", "type": "table", "tableId": "packages_table"},
    {"id": "package_roles_table_block", "type": "table", "tableId": "package_roles_table"},
    {"id": "inventory_intro", "type": "markdown", "sourceId": "inventory", "body": "## Complete output-tree map\n\nThe companion inventory lists every one of 5,881 paths. The conservative family summary is shown below; the 734 GB unclassified bucket must not be treated as disposable without path-level review."},
    {"id": "inventory_table_block", "type": "table", "tableId": "inventory_table"},
    {"id": "runtime_intro", "type": "markdown", "sourceId": "runtime", "body": "## Runtime and cost\n\nThe benchmark snapshot has 706 rows. All sample spans are ~5.60 hours because the four samples ran concurrently. NA20775 has the lowest sample-scoped task-wall burden (25.06 h); NA19235 has the highest (27.37 h). Total benchmark burden is 107.51 task-wall h, 7,348 allocated vCPU-h, and $251.64 task cost. These are benchmark-task measures, not cluster/controller makespan or full infrastructure cost."},
    {"id": "runtime_chart_block", "type": "chart", "chartId": "runtime_chart"},
    {"id": "runtime_table_block", "type": "table", "tableId": "runtime_table"},
    {"id": "runtime_rules_table_block", "type": "table", "tableId": "runtime_rules_table"},
    {"id": "recommendations", "type": "markdown", "body": "## Recommendations\n\nKeep the established core required: Sentieon HIOMR2 scoped VCF/gVCF, deduplicated CRAM/QC, CNVscope, LongReadSV, final MultiQC/provenance, the Inflection established tier, and distinct Sentieon regional plus SMNCopyNumberCaller SMN outputs when in scope. Keep Jasmine as the primary research merger because it is the best-integrated operational path, but do not call it accuracy-proven yet.\n\nStrong optionality candidates are NICU FASTQ recoverability, Manta in routine snapshots, alternate SURVIVOR/OctopuSV materializations, and large merger-support tables. FASTQ recoverability and Manta are the two largest aggregate task-wall contributors; Manta alone consumes 11.00 task-wall h and $50.33. Do not remove any SV caller solely from record counts. First complete the same-release HG002 truth ablation and compare precision, recall, F1, unique true/false positives, runtime, vCPU allocation, and cost."},
    {"id": "current_intro", "type": "markdown", "sourceId": "current", "body": "## Current testing state\n\nAt the 07:40 UTC boundary, `remaining-giab` has a terminal workflow-success marker and final MultiQC, but zero Inflection package manifests under the expected delivery root; its requested packaging objective is therefore not accepted complete. `take333lc` ended RC=1 at 97% after RTG succeeded but atomic directory publication encountered a disappearing hidden partial directory; its final MultiQC is absent and one partial package manifest exists."},
    {"id": "current_table_block", "type": "table", "tableId": "current_table"},
    {"id": "caveats", "type": "markdown", "body": "## Caveats and reproducibility\n\nThe final MultiQC comment still names pre-release 13.4.2 because the report was generated before the live-proven tree was committed/tagged as 13.4.3; hash reconciliation and the release ledger establish final attribution. Take222 cannot rank SV accuracy because it has no HG002. SMN expected truth CNs are not configured. Observed CPU time is implausibly low for several high-thread tasks and should not drive resizing until benchmark process accounting is repaired. The Markdown companion contains the full narrative, evidence paths, and recommendations."},
]

manifest = {
    "version": 1,
    "surface": "report",
    "title": "Take222 full-coverage HIOMR2 kitchen-sink, mega/NICU, MultiQC, and Inflection packaging review",
    "generatedAt": generated_at,
    "sources": sources,
    "cards": [],
    "charts": charts,
    "tables": tables,
    "blocks": blocks,
}

snapshot = {
    "version": 1,
    "status": "ready",
    "generatedAt": generated_at,
    "datasets": {
        "coverage": coverage,
        "coverage_chart": coverage_chart,
        "giab": giab,
        "giab_chart": giab_chart,
        "smn": smn,
        "runtime_samples": runtime_samples,
        "runtime_chart": runtime_chart,
        "runtime_rules": runtime_rules,
        "nicu": nicu,
        "direct_sv": direct_sv,
        "packages": packages,
        "package_roles": package_roles,
        "review_tags": review_tags,
        "review_chart": review_chart,
        "inventory": inventory,
        "current": current,
    },
}

artifact = {"surface": "report", "manifest": manifest, "snapshot": snapshot, "sources": sources}
OUTPUT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(OUTPUT)
