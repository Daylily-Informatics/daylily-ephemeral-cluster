#!/usr/bin/env python3
"""Build the terminal Take222 + Take333lc HIOMR2 report and audit tables."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path("/Users/jmajor/Downloads/dyec-dayao-pipe-runtime-artifacts")
SOURCE = ROOT / "source-data"
OTHER = SOURCE / "other_reports"
OLD_ARTIFACT = ROOT / "artifact.json"
OLD_NOTES = ROOT / "notes.md"
S3_ROOT = "s3://lsmc-ssf-sequencing-data/derived/preval-hiomr2/take333lc-final-20260804T174813Z/"
REMOTE_REPORT_DIR = "final-report"
REPORT_MD = "TAKE222_TAKE333LC_HIOMR2_FINAL_REPORT.md"
REPORT_PDF = "TAKE222_TAKE333LC_HIOMR2_FINAL_REPORT.pdf"
MULTIQC_REL = "daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc.html"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


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


def typed(data: list[dict[str, str]]) -> list[dict[str, object]]:
    return [{key: coerce(value) for key, value in row.items()} for row in data]


def write_tsv(name: str, data: list[dict[str, object]], fields: list[str]) -> Path:
    path = ROOT / name
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)
    return path


def fmt(value: object, digits: int = 6) -> str:
    if value in (None, "", ".", "NA"):
        return "NA"
    return f"{float(value):.{digits}f}"


def markdown_table(data: list[dict[str, object]], fields: list[tuple[str, str]], digits: dict[str, int] | None = None) -> str:
    digits = digits or {}
    lines = ["| " + " | ".join(label for _, label in fields) + " |", "|" + "|".join("---" for _ in fields) + "|"]
    for row in data:
        values = []
        for field, _ in fields:
            value = row.get(field, "")
            if field in digits and value not in (None, "", ".", "NA"):
                value = fmt(value, digits[field])
            values.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

# Complete GIAB-HC concordance grid: Take222 HG003/HG004 plus Take333lc HG002.
giab = typed(rows(ROOT / "take222_giabhc_snv_results.tsv"))
for row in rows(OTHER / "giab_concordance_mqc.tsv"):
    if row["ROI"] != "giabHC":
        continue
    giab.append(
        {
            "analysis": "take333lc",
            "sample": row["SampleID"],
            "caller": row["SNVCaller"],
            "variant_class": row["VariantClass"],
            "f_score": float(row["Fscore"]) if row["Fscore"] else "",
            "precision": float(row["Precision"]) if row["Precision"] else "",
            "recall": float(row["Sensitivity-Recall"]) if row["Sensitivity-Recall"] else "",
            "tp": int(float(row["TP"])) if row["TP"] else "",
            "fp": int(float(row["FP"])) if row["FP"] else "",
            "fn": int(float(row["FN"])) if row["FN"] else "",
            "status": row["ConcordanceStatus"],
        }
    )
for row in giab:
    row.setdefault("analysis", "take222")
    for field in ("tp", "fp", "fn"):
        if isinstance(row[field], float) and row[field].is_integer():
            row[field] = int(row[field])
giab.sort(key=lambda row: (str(row["sample"]), str(row["caller"]), str(row["variant_class"])))
expected_classes = {"SNPts", "SNPtv", "INS_50", "INS_gt50", "DEL_50", "DEL_gt50", "Indel_50", "Indel_gt50", "All"}
keys = {(row["sample"], row["caller"], row["variant_class"]) for row in giab}
if len(keys) != len(giab) or len(giab) != 54:
    raise ValueError(f"GIAB grid is not the expected unique 54 rows: {len(giab)} rows, {len(keys)} keys")
for sample in ("HG002", "HG003", "HG004"):
    for caller in ("sentdhiomr2", "sentdhiomr2_cli_gvcf"):
        actual = {row["variant_class"] for row in giab if row["sample"] == sample and row["caller"] == caller}
        if actual != expected_classes:
            raise ValueError(f"incomplete GIAB class grid for {sample}/{caller}: {actual}")
write_tsv(
    "final_giabhc_snv_results_all_samples_callers_classes.tsv",
    giab,
    ["analysis", "sample", "caller", "variant_class", "f_score", "precision", "recall", "tp", "fp", "fn", "status"],
)

# Take333lc coverage and fragment statistics, joined with the prior full-coverage rows.
coverage = typed(rows(ROOT / "take222_sample_coverage_fragment_stats.tsv"))
for row in rows(OTHER / "alignstats_combo_mqc.tsv"):
    if row["aligner"] not in {"sentdhiomr2sr", "sentdhiomr2lr"}:
        continue
    modality = "Illumina ~5x" if row["aligner"] == "sentdhiomr2sr" else "ONT ~5x"
    coverage.append(
        {
            "analysis": "take333lc",
            "sample": "HG002",
            "modality": modality,
            "mean_coverage_x": float(row["WgsCoverageMean"]),
            "median_coverage_x": float(row["WgsCoverageMedian"]),
            "bases_30x_pct": float(row["WgsCoverageBases30Pct"]),
            "mapped_reads_pct": float(row["MappedReadsPct"]),
            "duplicate_reads_pct": float(row["DuplicateReadsPct"]),
            "insert_size_median_bp": int(float(row["InsertSizeMedian"])),
            "insert_size_mean_bp": float(row["InsertSizeMean"]),
            "raw_read_records_millions": round(float(row["TotalRecords"]) / 1_000_000, 6),
            "samtools_error_rate_pct": "",
        }
    )
for row in coverage:
    row.setdefault("analysis", "take222")
write_tsv(
    "final_sample_coverage_fragment_stats.tsv",
    coverage,
    ["analysis", "sample", "modality", "mean_coverage_x", "median_coverage_x", "bases_30x_pct", "mapped_reads_pct", "duplicate_reads_pct", "insert_size_median_bp", "insert_size_mean_bp", "raw_read_records_millions", "samtools_error_rate_pct"],
)

# Expected and observed SMN copy number. Expected rows are campaign-control
# expectations, not configured workflow truth fields.
smn = [
    {"analysis": "take222", "sample": "HG003", "coverage": "full", "expected_smn1": 2, "expected_smn2": 2, "sentieon_smn1": 2, "sentieon_smn2": 2, "smncnc_smn1": 2, "smncnc_smn2": 2, "smncnc_status": "PASS:Majority", "interpretation": "both callers match campaign expectation"},
    {"analysis": "take222", "sample": "HG004", "coverage": "full", "expected_smn1": 2, "expected_smn2": 2, "sentieon_smn1": 2, "sentieon_smn2": 2, "smncnc_smn1": 2, "smncnc_smn2": 2, "smncnc_status": "PASS:Majority", "interpretation": "both callers match campaign expectation"},
    {"analysis": "take222", "sample": "NA19235", "coverage": "full", "expected_smn1": 4, "expected_smn2": 0, "sentieon_smn1": 4, "sentieon_smn2": 0, "smncnc_smn1": 4, "smncnc_smn2": 0, "smncnc_status": "PASS:Majority", "interpretation": "two-caller concordant positive control"},
    {"analysis": "take222", "sample": "NA20775", "coverage": "full", "expected_smn1": 3, "expected_smn2": 1, "sentieon_smn1": 3, "sentieon_smn2": 2, "smncnc_smn1": 3, "smncnc_smn2": 1, "smncnc_status": "PASS:Majority", "interpretation": "SMNCopyNumberCaller matches expectation; Sentieon SMN2 is discordant"},
    {"analysis": "take333lc", "sample": "HG002", "coverage": "~5x/~5x", "expected_smn1": 2, "expected_smn2": 2, "sentieon_smn1": 2, "sentieon_smn2": 2, "smncnc_smn1": "NA", "smncnc_smn2": "NA", "smncnc_status": "Ambiguous; null calls", "interpretation": "Sentieon matches expectation; SMNCopyNumberCaller is not callable at this depth"},
]
write_tsv(
    "final_smn12_expected_and_calls_by_sample_caller.tsv",
    smn,
    ["analysis", "sample", "coverage", "expected_smn1", "expected_smn2", "sentieon_smn1", "sentieon_smn2", "smncnc_smn1", "smncnc_smn2", "smncnc_status", "interpretation"],
)

# Canonical SV callsets and their exact Truvari status. A missing benchmark is
# explicitly represented as NO_ARTIFACT, never as zero.
truvari_rows = {row["query"]: row for row in rows(OTHER / "sentdhiomr2_truvari_mqc.tsv")}
failure_reasons = {
    "jasmine_full": "projected 16,732 vs compared 16,727 records",
    "jasmine_final": "projected 16,711 vs compared 16,706 records",
    "longreadsv": "projected 15,451 vs compared 15,446 records",
    "sniffles2": "projected 9,864 vs compared 9,860 records",
    "cnvscope_copy_state_pass": "copy-state directional proxy diagnostic failed",
    "cnvscope_copy_state_all": "copy-state directional proxy diagnostic failed",
}
inventory_rows = rows(SOURCE / "take333lc_output_inventory.tsv")
inv = {row["path"]: row for row in inventory_rows}
canonical = [
    ("Manta", "source caller", "nicu-research/normalized/manta/", "manta", "NO_ARTIFACT"),
    ("Dysgu", "source caller", "nicu-research/normalized/dysgu/", "dysgu", "NO_ARTIFACT"),
    ("LongReadSV", "source caller", "nicu-research/normalized/longreadsv/", "longreadsv", "DIAGNOSTIC_FAILED"),
    ("TIDDIT", "source caller", "nicu-research/normalized/tiddit/", "tiddit", "SUCCESS"),
    ("Sniffles2", "source caller", "nicu-research/normalized/sniffles2/", "sniffles2", "DIAGNOSTIC_FAILED"),
    ("Severus", "source caller", "nicu-research/normalized/severus/", "severus", "NO_ARTIFACT"),
    ("Sniffles1/Iris", "accepted integration source", "integrated/raw_sources/HG002-gy7skbxt0rc9h2/sniffles1_iris.vcf.gz", "sniffles1_iris", "SUCCESS"),
    ("Jasmine companion", "merger projection", "integrated/companion/jasmine.companion.vcf.gz", "jasmine_companion", "SUCCESS"),
    ("Jasmine full", "full integration merger", "integrated/full_integration/jasmine.full.vcf.gz", "jasmine_full", "DIAGNOSTIC_FAILED"),
    ("Jasmine final", "final integration merger", "integrated/final/jasmine.final.vcf.gz", "jasmine_final", "DIAGNOSTIC_FAILED"),
    ("Jasmine packaged", "NICU packaged merger", "nicu-research/merged/jasmine/", "jasmine_full+jasmine_final", "RELATED_DIAGNOSTICS_FAILED"),
    ("SURVIVOR", "merger", "nicu-research/merged/survivor/", "survivor", "NO_ARTIFACT"),
    ("OctopuSV", "merger", "nicu-research/merged/octopusv/", "octopusv", "NO_ARTIFACT"),
    ("CNVscope", "CNV callset", "sentdhiomr2/cnv/", "cnvscope", "SUCCESS"),
]
sv_rows: list[dict[str, object]] = []
for caller, role, fragment, query, default_status in canonical:
    matches = [row for path, row in inv.items() if path.endswith(".vcf.gz") and fragment in path and "/benchmarks/" not in path and "/deliveries/" not in path]
    if not matches and caller == "CNVscope":
        matches = [row for path, row in inv.items() if path.endswith(".cnv.vcf.gz") and "/sentdhiomr2/cnv/" in path]
    if not matches:
        path = "present in integration tree" if caller == "Sniffles1/Iris" else "not resolved"
        bytes_value = ""
    else:
        matches.sort(key=lambda row: row["path"])
        path = matches[0]["path"]
        bytes_value = int(matches[0]["bytes"])
    metric = truvari_rows.get(query)
    if metric:
        status = metric["status"]
        f1, precision, recall = metric["f1"], metric["precision"], metric["recall"]
        tp, fp, fn = metric["TP-comp"], metric["FP"], metric["FN"]
        projected, excluded = metric["projected_records"], metric["excluded_records"]
        note = failure_reasons.get(query, "GIAB v5.0q DEL/INS >=50 bp, PASS-only")
    else:
        status = default_status
        f1 = precision = recall = tp = fp = fn = projected = excluded = "NA"
        note = "No per-callset Truvari artifact was produced" if "FAILED" not in status else "Related full/final Jasmine diagnostics failed record reconciliation"
    sv_rows.append(
        {"sample": "HG002", "caller_or_merger": caller, "role": role, "canonical_vcf": path, "bytes": bytes_value, "truvari_query": query, "status": status, "f1": f1, "precision": precision, "recall": recall, "tp_comp": tp, "fp": fp, "fn": fn, "projected_records": projected, "excluded_records": excluded, "note": note}
    )
write_tsv(
    "final_hg002_sv_callsets_and_truvari.tsv",
    sv_rows,
    ["sample", "caller_or_merger", "role", "canonical_vcf", "bytes", "truvari_query", "status", "f1", "precision", "recall", "tp_comp", "fp", "fn", "projected_records", "excluded_records", "note"],
)

# Preserve every raw Truvari row, including the hard-SNV cross-domain diagnostic
# and copy-state proxy failures.
truvari_all = typed(rows(OTHER / "sentdhiomr2_truvari_mqc.tsv"))
for row in truvari_all:
    row["interpretation"] = failure_reasons.get(str(row["query"]), "")
    if row["query"] == "hard_snv":
        row["interpretation"] = "cross-domain >=50 bp DEL/INS projection; not small-variant accuracy"
write_tsv(
    "final_hg002_all_truvari_queries.tsv",
    truvari_all,
    list(truvari_all[0].keys()),
)

# Direct SV caller record/type counts.
direct_sv: list[dict[str, object]] = typed(rows(ROOT / "take222_direct_sv_counts.tsv"))
for filename, caller in (("sentdhiomr2_sniffles2_mqc.tsv", "Sniffles2"), ("sentdhiomr2_tiddit_mqc.tsv", "TIDDIT")):
    row = rows(OTHER / filename)[0]
    direct_sv.append({"sample": "HG002", "caller": caller, "total_records": row["total_records"], "DEL": row["DEL"], "INS": row["INS"], "DUP": row["DUP"], "INV": row["INV"], "BND": row["BND"], "other": int(row["TRA"]) + int(row["CNV"]) + int(row["other_svtype"]) + int(row["no_svtype"]), "status": row["status"]})
write_tsv("final_direct_sv_counts.tsv", direct_sv, ["sample", "caller", "total_records", "DEL", "INS", "DUP", "INV", "BND", "other", "status"])

# Runtime: preserve Take222 rows and add the single-sample Take333lc workload.
runtime = typed(rows(ROOT / "take222_runtime_per_sample.tsv"))
bench = rows(SOURCE / "reports" / "benchmarks.tsv")
bench = [row for row in bench if row.get("status") == "success"]
starts = [datetime.fromisoformat(row["start_datetime"].replace("Z", "+00:00")) for row in bench if row["start_datetime"] not in {"", "NA"}]
ends = [datetime.fromisoformat(row["end_datetime"].replace("Z", "+00:00")) for row in bench if row["end_datetime"] not in {"", "NA"}]
longest = max(bench, key=lambda row: float(row["s"]))
take333_runtime = {
    "analysis": "take333lc",
    "sample": "HG002",
    "benchmark_rows": len(bench),
    "first_task_start_utc": min(starts).isoformat().replace("+00:00", "Z"),
    "last_task_end_utc": max(ends).isoformat().replace("+00:00", "Z"),
    "benchmark_span_hours": round((max(ends) - min(starts)).total_seconds() / 3600, 6),
    "task_wall_hours_sum": round(sum(float(row["s"]) for row in bench) / 3600, 6),
    "allocated_vcpu_hours": round(sum(float(row["s"]) * float(row["snakemake_threads"]) for row in bench) / 3600, 6),
    "observed_cpu_hours": round(sum(float(row["cpu_time"]) for row in bench) / 3600, 6),
    "task_cost_usd": round(sum(float(row["task_cost"]) for row in bench), 6),
    "longest_task_rule": longest["rule"],
    "longest_task_hours": round(float(longest["s"]) / 3600, 6),
}
for row in runtime:
    row.setdefault("analysis", "take222")
runtime.append(take333_runtime)
write_tsv(
    "final_runtime_per_sample.tsv",
    runtime,
    ["analysis", "sample", "benchmark_rows", "first_task_start_utc", "last_task_end_utc", "benchmark_span_hours", "task_wall_hours_sum", "allocated_vcpu_hours", "observed_cpu_hours", "task_cost_usd", "longest_task_rule", "longest_task_hours"],
)

rule_agg: dict[str, dict[str, object]] = defaultdict(lambda: {"rows": 0, "task_wall_hours_sum": 0.0, "allocated_vcpu_hours": 0.0, "observed_cpu_hours": 0.0, "task_cost_usd": 0.0})
for row in bench:
    agg = rule_agg[row["rule"]]
    agg["rows"] = int(agg["rows"]) + 1
    agg["task_wall_hours_sum"] = float(agg["task_wall_hours_sum"]) + float(row["s"]) / 3600
    agg["allocated_vcpu_hours"] = float(agg["allocated_vcpu_hours"]) + float(row["s"]) * float(row["snakemake_threads"]) / 3600
    agg["observed_cpu_hours"] = float(agg["observed_cpu_hours"]) + float(row["cpu_time"]) / 3600
    agg["task_cost_usd"] = float(agg["task_cost_usd"]) + float(row["task_cost"])
runtime_rules = []
for rule, agg in rule_agg.items():
    runtime_rules.append({"rule": rule, **{key: round(value, 6) if isinstance(value, float) else value for key, value in agg.items()}})
runtime_rules.sort(key=lambda row: float(row["task_wall_hours_sum"]), reverse=True)
write_tsv("take333lc_runtime_by_rule.tsv", runtime_rules, ["rule", "rows", "task_wall_hours_sum", "allocated_vcpu_hours", "observed_cpu_hours", "task_cost_usd"])

# Take333lc package and output inventory summaries.
package_map = json.loads((SOURCE / "take333lc_inflection_package_manifests.json").read_text())
package_rows = []
package_roles = defaultdict(lambda: {"sample_occurrences": 0, "bytes": 0})
for path, payload in package_map.items():
    artifacts = payload["artifacts"]
    package_rows.append({"analysis": "take333lc", "sample": payload["external_sample_id"], "analysis_unit_uid": payload["analysis_unit_uid"], "schema": payload["schema"], "artifact_count": payload["artifact_count"], "established_artifacts": sum(a["package_tier"] == "established" for a in artifacts), "experimental_artifacts": sum(a["package_tier"] == "experimental" for a in artifacts), "declared_bytes": sum(int(a["bytes"]) for a in artifacts), "package_mode": payload["package_mode"], "customer_release_eligible": payload["customer_release_eligible"], "manifest_path": path})
    for artifact in artifacts:
        key = (artifact["package_tier"], artifact["role"], artifact["semantic_type"])
        package_roles[key]["sample_occurrences"] += 1
        package_roles[key]["bytes"] += int(artifact["bytes"])
write_tsv("take333lc_inflection_package_summary.tsv", package_rows, list(package_rows[0].keys()))
package_role_rows = [{"package_tier": key[0], "role": key[1], "semantic_type": key[2], **value} for key, value in sorted(package_roles.items())]
write_tsv("take333lc_inflection_artifact_roles.tsv", package_role_rows, ["package_tier", "role", "semantic_type", "sample_occurrences", "bytes"])
inventory_summary = typed(rows(SOURCE / "take333lc_output_inventory_summary.json")) if False else json.loads((SOURCE / "take333lc_output_inventory_summary.json").read_text())
if isinstance(inventory_summary, dict):
    summary_rows = inventory_summary.get("categories") or inventory_summary.get("rows") or []
else:
    summary_rows = inventory_summary
if not summary_rows:
    by_category = defaultdict(lambda: {"file_count": 0, "bytes": 0})
    for row in inventory_rows:
        key = row.get("category", "unclassified")
        by_category[key]["file_count"] += 1
        by_category[key]["bytes"] += int(row["bytes"])
    summary_rows = [{"category": key, **value, "gigabytes": round(value["bytes"] / 1e9, 6)} for key, value in by_category.items()]
write_tsv("take333lc_output_inventory_category_summary.tsv", summary_rows, ["category", "file_count", "bytes", "gigabytes"])

# Reader-facing Markdown: retain the complete old report, repair its now-stale
# conclusions, then append a terminal evidence section with full-grain tables.
old_notes = OLD_NOTES.read_text(encoding="utf-8")
old_notes = old_notes.replace("# Take222 full-coverage HIOMR2 kitchen-sink, mega/NICU, MultiQC, and Inflection packaging review", "# Take222 full-coverage and Take333lc HG002 5x/5x HIOMR2 final review")
old_notes = old_notes.replace("Sentieon's regional SMN1 output completed, but the rollup does not expose numeric copy-number fields.", "Sentieon's regional SMN1 output completed; its adjacent YAML records numeric SMN1/SMN2 copy-number calls and is reconciled in the terminal addendum below.")
old_notes = old_notes.replace("but the manifest does not configure expected truth copy numbers. Consequently, `overall_concordance` is `NOT_CONFIGURED`; this report does not relabel those calls as a formal truth pass.", "The workflow manifest does not configure truth copy numbers, so `overall_concordance` remains `NOT_CONFIGURED`; the terminal addendum separately labels reviewed campaign-control expectations and does not rewrite workflow truth status.")

giab_md = markdown_table(
    giab,
    [("sample", "Sample"), ("caller", "Route"), ("variant_class", "Class"), ("f_score", "F-score"), ("precision", "Precision"), ("recall", "Recall"), ("tp", "TP"), ("fp", "FP"), ("fn", "FN")],
    {"f_score": 9, "precision": 9, "recall": 9},
)
smn_md = markdown_table(smn, [("sample", "Sample"), ("coverage", "Coverage"), ("expected_smn1", "Expected SMN1"), ("expected_smn2", "Expected SMN2"), ("sentieon_smn1", "Sentieon SMN1"), ("sentieon_smn2", "Sentieon SMN2"), ("smncnc_smn1", "SMNCNC SMN1"), ("smncnc_smn2", "SMNCNC SMN2"), ("smncnc_status", "SMNCNC status"), ("interpretation", "Interpretation")])
sv_md = markdown_table(sv_rows, [("caller_or_merger", "Caller/merger"), ("role", "Role"), ("status", "Truvari status"), ("f1", "F1"), ("precision", "Precision"), ("recall", "Recall"), ("tp_comp", "TP"), ("fp", "FP"), ("fn", "FN"), ("projected_records", "Projected"), ("excluded_records", "Excluded"), ("note", "Note")], {"f1": 6, "precision": 6, "recall": 6})
runtime_md = markdown_table([row for row in runtime if row["sample"] != "shared_or_global"], [("analysis", "Analysis"), ("sample", "Sample"), ("benchmark_rows", "Rows"), ("benchmark_span_hours", "Benchmark span h"), ("task_wall_hours_sum", "Task-wall h"), ("allocated_vcpu_hours", "Allocated vCPU-h"), ("task_cost_usd", "Task cost USD"), ("longest_task_rule", "Longest rule"), ("longest_task_hours", "Longest h")], {"benchmark_span_hours": 3, "task_wall_hours_sum": 3, "allocated_vcpu_hours": 1, "task_cost_usd": 2, "longest_task_hours": 3})

terminal = f"""

---

## Terminal Take333lc evidence and corrected cross-run synthesis

### Completion and provenance

Take333lc is now terminal **RC=0** under DayOA **13.4.3**. The exact five-target recovery completed strict final MultiQC and the schema-1.3 Inflection analytical package after the cluster budget safeguard was raised by explicit double approval from **$1,500 to $2,200**. The source input is HG002 at approximately 5.86x Illumina plus 5.00x ONT. The final MultiQC HTML is 10,300,380 bytes; `multiqc_data.json` is 14,219,216 bytes; and the evidence manifest is 323,836 bytes.

Stable export destinations for the fresh full-root export are:

- Full export root: `{S3_ROOT}`
- Final MultiQC: `{S3_ROOT}{MULTIQC_REL}`
- Durable Markdown report: `{S3_ROOT}{REMOTE_REPORT_DIR}/{REPORT_MD}`
- Durable PDF report: `{S3_ROOT}{REMOTE_REPORT_DIR}/{REPORT_PDF}`

Seven-day signed URLs are intentionally not embedded in this durable report because they expire; the terminal Slack handoff carries them after export reconciliation.

### Coverage and fragment evidence for HG002 5x/5x

The duplicate-marked short-read alignment has mean coverage **5.724x**, median **5x**, 99.742% mapped reads, 0.745% duplicate reads, and median insert size 462 bp. The long-read alignment has mean coverage **4.827x**, median **5x**, and 95.023% mapped reads. CoverageEvennessTwo reports mean-window depth 6.040x for short reads and 4.827x for ONT. This is a deliberate low-coverage proof and must not be compared to the Take222 37–46x Illumina / 12–15x ONT full-coverage lane as if depth were held constant.

### Complete SNV concordance for ROI=giabHC

The table below includes **all 54 rows**: three truth-enabled GIAB samples, both materialization/evaluation routes, and all nine variant classes. `sentdhiomr2` and `sentdhiomr2_cli_gvcf` are route variants of the same HIOMR2 caller, not independent biological callers. No empty metric is coerced to zero.

{giab_md}

At 5x/5x, HG002 All-class F1 is about 0.9519; short SNP classes remain stronger than <=50 bp indels, while >50 bp classes are sparse and weak. Full-coverage HG003/HG004 remain ~0.999 All-class F1. This depth contrast is the dominant explanation and should not be interpreted as a release regression.

### SMN1/SMN2 expected and observed calls

{smn_md}

The expected columns are reviewed campaign-control expectations, not configured workflow truth fields. Sentieon numeric CN values come from each completed `SMN1.yaml`; the old report's statement that Sentieon emitted no numeric CN is superseded. NA20775 remains a useful discordance boundary: expected and SMNCopyNumberCaller are 3/1, while Sentieon is 3/2. HG002 at 5x is Sentieon 2/2, but SMNCopyNumberCaller explicitly emits null SMN1/SMN2 with `Info=Ambiguous`; that is an unavailable call, not 0/0.

### Every canonical SV caller/merger output and Truvari result

{sv_md}

All successful standard rows use GIAB GRCh38 v5.0q DEL/INS >=50 bp truth, PASS-only queries, truth-BED containment, 500 bp reference distance, and 0.7 size/sequence similarity. Sniffles1/Iris is the strongest scored source at F1 **0.603387**. TIDDIT is precise (0.845224) but has low recall (0.024836). Jasmine companion is F1 **0.043382**. The full/final Jasmine, LongReadSV, and Sniffles2 diagnostics ran Truvari successfully but are deliberately `DIAGNOSTIC_FAILED` because output counts were 4–5 records short of projected counts; their partial Truvari output files exist, but their metrics are not accepted. Manta, Dysgu, Severus, SURVIVOR, and OctopuSV have no per-callset Truvari artifact and are reported as gaps, never zeros. The hard-SNV Truvari row is a cross-domain >=50 bp DEL/INS projection and is not a measure of small-variant accuracy.

### Kitchen-sink and mega/NICU output interpretation

Take333lc materialized the production established tier (scoped hard VCF/index, CNVscope post-model VCF/index, LongReadSV VCF/index, short-read CRAM/CRAI, and command manifest) and the experimental NICU tier. NICU includes normalized Manta, Dysgu, LongReadSV, TIDDIT, Sniffles2, and Severus sources; Jasmine, SURVIVOR, and OctopuSV mergers; BEDPE/concordance/support/topology/CNV-SV evidence; benchmark receipts; and lossless-content FASTQ recoverability evidence. Jasmine has 71,946 records, including 40,472 Manta-supported and 9,981 Dysgu-supported records; BND topology is valid. These are analytical/research artifacts and are not customer-release eligible or clinically interpretable.

### MultiQC review

The strict final MultiQC collected 227 benchmark rows across 225 aggregate rules, one HG002 sample, 180 RTG concordance rows, 11 Truvari rows, 25 NICU artifact rows, all coverage/alignment/targeted-calling modules, and final evidence-manifest inputs. It correctly surfaces warning/diagnostic status instead of inventing missing metrics. The most important caveat is that the generic library-summary coverage fields remain `NOT CONFIGURED`, while the authoritative AlignStats and CoverageEvennessTwo sections contain the measured 5x evidence; readers should use those explicit modules.

### Inflection analytical dataset

The Take333lc schema-1.3 package contains **37 declared artifacts**: **9 established** and **28 experimental**, totaling {package_rows[0]['declared_bytes']:,} bytes. It is an analytical package, includes NICU research, and is explicitly not customer-release eligible. The established tier is the stable review surface. Experimental callers, mergers, topology, support, benchmarking, and recoverability artifacts are valuable for R&D and release qualification, but should remain clearly segregated from established deliverables.

### Runtime and cost

{runtime_md}

Task-wall sums are workload, not controller makespan. Take222's four samples ran concurrently; its fastest sample-scoped task burden was NA20775. Take333lc's benchmark span includes the completed final recovery artifacts, while cluster startup, Slurm pending/configuring time, and the budget pause are outside task benchmarks. Runtime recommendations remain evidence-based: keep the established core required; keep Sniffles1/Iris/LongReadSV as primary truth-evaluated SV evidence; keep Jasmine analytical but not accuracy-certified; make SURVIVOR/OctopuSV, FASTQ recoverability, and expensive alternative-source lanes optional until same-depth ablation establishes incremental true positives per dollar and wall-hour. Do not remove callers solely because their current F1 is low at 5x or because no benchmark artifact exists.

### Current terminal state

Take222 is complete at full coverage with four Inflection packages and final MultiQC. Take333lc is complete at 5x/5x with final MultiQC and one Inflection analytical package. Controllers and Slurm queues were empty at terminal verification, and the Take333lc analysis lock was released. The remaining work for this report is delivery only: install this Markdown/PDF under the analysis root, export the entire root to the fresh S3 prefix above, reconcile the export receipt, create seven-day links, and send the Slack handoff.
"""
OLD_NOTES.write_text(old_notes.rstrip() + terminal + "\n", encoding="utf-8")

# Canonical report artifact: preserve the complete previous block sequence, make
# narrow corrections, and append the terminal tables and synthesis.
artifact = json.loads(OLD_ARTIFACT.read_text(encoding="utf-8"))
manifest = artifact["manifest"]
snapshot = artifact["snapshot"]
manifest["title"] = "Take222 full-coverage and Take333lc HG002 5x/5x HIOMR2 final review"
manifest["generatedAt"] = generated_at
snapshot["generatedAt"] = generated_at
for block in manifest["blocks"]:
    if block["id"] == "title":
        block["body"] = "# Take222 full-coverage and Take333lc HG002 5x/5x HIOMR2 final review\n\n## Decision summary\n\nBoth qualifying campaigns are terminal under DayOA **13.4.3**. Take222 completed four full-coverage samples with final MultiQC and four Inflection packages. Take333lc completed HG002 at approximately 5.86x Illumina plus 5.00x ONT with strict final MultiQC, one Inflection analytical package, all requested GIAB-HC SNV rows, and explicit Truvari success/failure/gap receipts. The final recovery was briefly blocked by the $1,500 budget safeguard and completed after an explicitly approved increase to $2,200."
    elif block["id"] == "smn_intro":
        block["body"] = "## SMN1/2 positive-control evidence\n\nThe completed Sentieon `SMN1.yaml` files do expose numeric SMN1/SMN2 copy number. Sentieon and SMNCopyNumberCaller agree for HG003, HG004, and NA19235. NA20775 is the expected discordance boundary: Sentieon 3/2 versus expected and SMNCopyNumberCaller 3/1. At 5x, HG002 is Sentieon 2/2 while SMNCopyNumberCaller is explicitly ambiguous with null calls."
    elif block["id"] == "smn_callers_detail":
        block["body"] = "### Per-sample, per-caller SMN12 detail\n\nThe terminal table below supersedes the earlier rollup limitation by reading the adjacent Sentieon YAML contracts directly. Campaign expectations remain separate from workflow truth, which is still `NOT_CONFIGURED`."
    elif block["id"] == "truvari_detail":
        block["body"] = "### Truvari results by sample and caller\n\nTake222 remains warning/not-applicable for public HG002 SV truth. Take333lc supplies HG002 truth-bearing results and explicit diagnostic failures/gaps; the terminal callset table below is the authoritative cross-run surface."
    elif block["id"] == "current_intro":
        block["body"] = "## Current testing state\n\nTake222 and Take333lc are now both terminal under DayOA 13.4.3 with final MultiQC and complete Inflection analytical packaging. The stale pre-recovery states in the original report are superseded by the terminal section below."
    elif block["id"] == "caveats":
        block["body"] = "## Caveats and reproducibility\n\nTake222 has no HG002 SV-truth sample, so its Truvari lanes are correctly not applicable. Take333lc is low coverage and cannot be compared to Take222 without controlling depth. Missing Truvari artifacts and diagnostic record-reconciliation failures are not zero scores. Campaign SMN expectations are not workflow-configured truth. Benchmark task-wall sums exclude controller, queue, startup, budget-pause, and infrastructure time."

def source_entry(source_id: str, label: str, path: str, description: str) -> dict[str, object]:
    return {"id": source_id, "label": label, "path": path, "query": {"engine": "duckdb", "language": "sql", "sql": f"SELECT * FROM read_csv_auto('{path}', delim='\\t', header=true)", "description": description, "tables_used": [path], "executed_at": generated_at}}

new_sources = [
    source_entry("final_giab", "Complete GIAB-HC SNV concordance grid", "final_giabhc_snv_results_all_samples_callers_classes.tsv", "All 54 sample/route/class rows for HG002, HG003, and HG004."),
    source_entry("final_smn", "Expected and observed SMN copy number", "final_smn12_expected_and_calls_by_sample_caller.tsv", "Campaign expectations, Sentieon YAML calls, and SMNCopyNumberCaller calls kept distinct."),
    source_entry("final_sv", "HG002 canonical SV callsets and Truvari", "final_hg002_sv_callsets_and_truvari.tsv", "Every canonical caller/merger output with accepted metrics, diagnostic failures, or explicit missing-artifact gaps."),
    source_entry("final_runtime", "Cross-run per-sample benchmark runtime", "final_runtime_per_sample.tsv", "Take222 and Take333lc benchmark workload, span, allocation, and task-cost measures."),
    source_entry("take333_package", "Take333lc Inflection package", "take333lc_inflection_package_summary.tsv", "Terminal schema-1.3 analytical package summary."),
]
existing_source_ids = {source["id"] for source in manifest["sources"]}
for entry in new_sources:
    if entry["id"] not in existing_source_ids:
        manifest["sources"].append(entry)
artifact["sources"] = manifest["sources"]

snapshot["datasets"].update(
    {
        "final_coverage": coverage,
        "final_giab": giab,
        "final_giab_chart": [row for row in giab if row["variant_class"] == "All"],
        "final_smn": smn,
        "final_sv": sv_rows,
        "final_truvari_all": truvari_all,
        "final_runtime": [row for row in runtime if row["sample"] != "shared_or_global"],
        "take333_runtime_rules": runtime_rules[:25],
        "take333_package": package_rows,
        "take333_package_roles": package_role_rows,
        "take333_inventory": summary_rows,
    }
)

manifest["charts"].append({"id": "final_giab_chart", "title": "All-class GIAB-HC F-score by sample and route", "subtitle": "HG002 is ~5x/~5x; HG003 and HG004 are full coverage. Routes are materializations, not independent biological callers.", "type": "bar", "dataset": "final_giab_chart", "sourceId": "final_giab", "encodings": {"x": {"field": "sample", "type": "nominal"}, "y": {"field": "f_score", "type": "quantitative"}, "color": {"field": "caller", "type": "nominal"}, "tooltip": [{"field": "sample", "type": "nominal"}, {"field": "caller", "type": "nominal"}, {"field": "f_score", "type": "quantitative"}, {"field": "precision", "type": "quantitative"}, {"field": "recall", "type": "quantitative"}]}})

def cols(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [{"field": field, "label": label} for field, label in pairs]

manifest["tables"].extend(
    [
        {"id": "final_coverage_table", "title": "Take222 full-coverage and Take333lc 5x/5x coverage", "dataset": "final_coverage", "sourceId": "coverage", "columns": cols(("analysis", "Analysis"), ("sample", "Sample"), ("modality", "Modality"), ("mean_coverage_x", "Mean x"), ("median_coverage_x", "Median x"), ("mapped_reads_pct", "Mapped %"), ("duplicate_reads_pct", "Duplicate %"), ("insert_size_median_bp", "Insert median"))},
        {"id": "final_giab_table", "title": "Complete GIAB-HC SNV concordance: every sample, route, and class", "dataset": "final_giab", "sourceId": "final_giab", "columns": cols(("sample", "Sample"), ("caller", "Route"), ("variant_class", "Class"), ("f_score", "F-score"), ("precision", "Precision"), ("recall", "Recall"), ("tp", "TP"), ("fp", "FP"), ("fn", "FN"))},
        {"id": "final_smn_table", "title": "Expected and observed SMN1/SMN2 copy number", "dataset": "final_smn", "sourceId": "final_smn", "columns": cols(("sample", "Sample"), ("coverage", "Coverage"), ("expected_smn1", "Expected SMN1"), ("expected_smn2", "Expected SMN2"), ("sentieon_smn1", "Sentieon SMN1"), ("sentieon_smn2", "Sentieon SMN2"), ("smncnc_smn1", "SMNCNC SMN1"), ("smncnc_smn2", "SMNCNC SMN2"), ("smncnc_status", "SMNCNC status"), ("interpretation", "Interpretation"))},
        {"id": "final_sv_table", "title": "Every canonical HG002 SV caller/merger callset and Truvari status", "dataset": "final_sv", "sourceId": "final_sv", "columns": cols(("caller_or_merger", "Caller/merger"), ("role", "Role"), ("status", "Status"), ("f1", "F1"), ("precision", "Precision"), ("recall", "Recall"), ("tp_comp", "TP"), ("fp", "FP"), ("fn", "FN"), ("note", "Interpretation"))},
        {"id": "final_runtime_table", "title": "Cross-run per-sample benchmark runtime", "dataset": "final_runtime", "sourceId": "final_runtime", "columns": cols(("analysis", "Analysis"), ("sample", "Sample"), ("benchmark_rows", "Rows"), ("benchmark_span_hours", "Span h"), ("task_wall_hours_sum", "Task-wall h"), ("allocated_vcpu_hours", "vCPU-h"), ("task_cost_usd", "Task USD"), ("longest_task_rule", "Longest rule"), ("longest_task_hours", "Longest h"))},
        {"id": "take333_package_table", "title": "Take333lc Inflection analytical package", "dataset": "take333_package", "sourceId": "take333_package", "columns": cols(("sample", "Sample"), ("artifact_count", "Artifacts"), ("established_artifacts", "Established"), ("experimental_artifacts", "Experimental"), ("declared_bytes", "Declared bytes"), ("package_mode", "Mode"), ("customer_release_eligible", "Release eligible"))},
    ]
)

manifest["blocks"].extend(
    [
        {"id": "terminal_divider", "type": "markdown", "body": "---\n\n## Terminal Take333lc evidence and corrected cross-run synthesis\n\nTake333lc is terminal RC=0 under DayOA **13.4.3** after the approved budget-cap increase from $1,500 to $2,200. It completed strict final MultiQC and schema-1.3 Inflection analytical packaging for HG002 at ~5.86x Illumina plus ~5.00x ONT."},
        {"id": "terminal_coverage_intro", "type": "markdown", "body": "### Coverage and fragments\n\nHG002 duplicate-marked Illumina mean/median coverage is 5.724x/5x with 99.742% mapped reads and a 462 bp median insert. ONT mean/median coverage is 4.827x/5x with 95.023% mapped reads."},
        {"id": "terminal_coverage_table", "type": "table", "tableId": "final_coverage_table"},
        {"id": "terminal_giab_intro", "type": "markdown", "body": "### Complete SNV concordance for ROI=giabHC\n\nAll 54 rows are retained: three samples, both HIOMR2 materialization/evaluation routes, and all nine variant classes. HG002 is low coverage; HG003/HG004 are full coverage."},
        {"id": "terminal_giab_chart", "type": "chart", "chartId": "final_giab_chart"},
        {"id": "terminal_giab_table", "type": "table", "tableId": "final_giab_table"},
        {"id": "terminal_smn_intro", "type": "markdown", "body": "### SMN1/SMN2 expected and observed calls\n\nCampaign-control expectations are separated from workflow truth. Sentieon numeric values are read from completed YAMLs. HG002 SMNCopyNumberCaller nulls are explicit ambiguity, not zero copy number."},
        {"id": "terminal_smn_table", "type": "table", "tableId": "final_smn_table"},
        {"id": "terminal_sv_intro", "type": "markdown", "body": "### Every canonical SV output and Truvari result\n\nSuccessful metrics, diagnostic record-reconciliation failures, and missing-artifact gaps are distinct. Sniffles1/Iris is strongest at F1 0.603387. No absent or failed metric is reported as zero."},
        {"id": "terminal_sv_table", "type": "table", "tableId": "final_sv_table"},
        {"id": "terminal_package_intro", "type": "markdown", "body": f"### Inflection package and MultiQC\n\nThe terminal package has 37 artifacts (9 established, 28 experimental) totaling {package_rows[0]['declared_bytes']:,} bytes. Final MultiQC is 10,300,380 bytes and includes the complete GIAB, Truvari, NICU, runtime, coverage, and provenance evidence surfaces."},
        {"id": "terminal_package_table", "type": "table", "tableId": "take333_package_table"},
        {"id": "terminal_runtime_intro", "type": "markdown", "body": "### Runtime and recommendations\n\nTask-wall burden is not makespan. Keep the established core required; retain Sniffles1/Iris/LongReadSV truth evaluation; keep Jasmine analytical but not accuracy-certified; and make SURVIVOR/OctopuSV, FASTQ recoverability, and expensive alternate lanes optional pending controlled depth-matched ablation."},
        {"id": "terminal_runtime_table", "type": "table", "tableId": "final_runtime_table"},
        {"id": "terminal_delivery", "type": "markdown", "body": f"### Durable delivery locations\n\nFresh full-root export: `{S3_ROOT}`\n\nFinal MultiQC: `{S3_ROOT}{MULTIQC_REL}`\n\nMarkdown report: `{S3_ROOT}{REMOTE_REPORT_DIR}/{REPORT_MD}`\n\nPDF report: `{S3_ROOT}{REMOTE_REPORT_DIR}/{REPORT_PDF}`\n\nSeven-day signed URLs are sent in Slack after export reconciliation because they expire."},
    ]
)

OLD_ARTIFACT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({"generated_at": generated_at, "giab_rows": len(giab), "smn_rows": len(smn), "sv_rows": len(sv_rows), "runtime_rows": len(runtime), "package_rows": len(package_rows), "s3_root": S3_ROOT}, indent=2))
