#!/usr/bin/env python3
"""Build reviewed Take222 report datasets from captured MultiQC and package evidence."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


OUTPUT = Path("/Users/jmajor/Downloads/dyec-dayao-pipe-runtime-artifacts")
SOURCE = OUTPUT / "source-data"
MQC = SOURCE / "take222_multiqc_extract.json"
PACKAGES = SOURCE / "take222_inflection_package_manifests.json"
SELECTED = SOURCE / "selected_artifacts"


def write_tsv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def base_sample(value: str) -> str:
    return value.rstrip(".").split("-")[0]


multiqc = json.loads(MQC.read_text(encoding="utf-8"))
raw = multiqc["saved_raw_data"]
packages = json.loads(PACKAGES.read_text(encoding="utf-8"))

# Coverage, fragment, mapping, and raw-read evidence.
general = raw["multiqc_general_stats"]
sample_metrics: list[dict[str, object]] = []
for key, row in sorted(general.items()):
    if ".sentdhiomr2sr.smd" in key:
        modality = "Illumina"
    elif ".sentdhiomr2lr.na" in key:
        modality = "ONT[0,25)"
    else:
        continue
    sample_metrics.append(
        {
            "sample": base_sample(key),
            "modality": modality,
            "mean_coverage_x": row.get("alignstats-WgsCoverageMean", ""),
            "median_coverage_x": row.get("alignstats-WgsCoverageMedian", ""),
            "bases_30x_pct": row.get("alignstats-WgsCoverageBases30Pct", ""),
            "mapped_reads_pct": row.get("alignstats-MappedReadsPct", ""),
            "duplicate_reads_pct": row.get("alignstats-DuplicateReadsPct", ""),
            "insert_size_median_bp": row.get("alignstats-InsertSizeMedian", ""),
            "insert_size_mean_bp": row.get("samtools_stats-insert_size_average", ""),
            "raw_read_records_millions": row.get("samtools_stats-raw_total_sequences", ""),
            "samtools_error_rate_pct": row.get("samtools_stats-error_rate", ""),
        }
    )
write_tsv(
    OUTPUT / "take222_sample_coverage_fragment_stats.tsv",
    sample_metrics,
    [
        "sample",
        "modality",
        "mean_coverage_x",
        "median_coverage_x",
        "bases_30x_pct",
        "mapped_reads_pct",
        "duplicate_reads_pct",
        "insert_size_median_bp",
        "insert_size_mean_bp",
        "raw_read_records_millions",
        "samtools_error_rate_pct",
    ],
)

# Hard-VCF and CLI-gVCF RTG vcfeval results in GIAB HC. These two lanes are
# deliberately kept separate even though their observed values are identical.
giab_rows: list[dict[str, object]] = []
for row in raw["multiqc_giab_concordance"].values():
    if row.get("ROI") != "giabHC":
        continue
    giab_rows.append(
        {
            "sample": row.get("SampleID", ""),
            "caller": row.get("SNVCaller", ""),
            "variant_class": row.get("VariantClass", ""),
            "f_score": row.get("Fscore", ""),
            "precision": row.get("Precision", ""),
            "recall": row.get("Sensitivity-Recall", ""),
            "tp": row.get("TP", ""),
            "fp": row.get("FP", ""),
            "fn": row.get("FN", ""),
            "status": row.get("ConcordanceStatus", ""),
        }
    )
giab_rows.sort(key=lambda row: (str(row["sample"]), str(row["caller"]), str(row["variant_class"])))
write_tsv(
    OUTPUT / "take222_giabhc_snv_results.tsv",
    giab_rows,
    ["sample", "caller", "variant_class", "f_score", "precision", "recall", "tp", "fp", "fn", "status"],
)

# SMN1/2 orthogonal caller evidence.
smn_rows: list[dict[str, object]] = []
for row in raw["multiqc_smn12_orthogonal_calls"].values():
    smn_rows.append(
        {
            "sample": row.get("SampleID", ""),
            "smn_copynumbercaller_smn1_cn": row.get("smncopynumbercaller_smn1_copy_number", ""),
            "smn_copynumbercaller_smn2_cn": row.get("smncopynumbercaller_smn2_copy_number", ""),
            "smn_copynumbercaller_status": row.get("smncopynumbercaller_status", ""),
            "sentieon_smn1_cn": row.get("sentieon_smn1_copy_number", ""),
            "sentieon_smn2_cn": row.get("sentieon_smn2_copy_number", ""),
            "sentieon_status": row.get("sentieon_status", ""),
            "expected_smn1_cn": row.get("expected_smn1_copy_number", ""),
            "expected_smn2_cn": row.get("expected_smn2_copy_number", ""),
            "overall_concordance": row.get("overall_concordance", ""),
            "discordance_flag": row.get("discordance_flag", ""),
        }
    )
smn_rows.sort(key=lambda row: str(row["sample"]))
write_tsv(
    OUTPUT / "take222_smn12_results.tsv",
    smn_rows,
    [
        "sample",
        "smn_copynumbercaller_smn1_cn",
        "smn_copynumbercaller_smn2_cn",
        "smn_copynumbercaller_status",
        "sentieon_smn1_cn",
        "sentieon_smn2_cn",
        "sentieon_status",
        "expected_smn1_cn",
        "expected_smn2_cn",
        "overall_concordance",
        "discordance_flag",
    ],
)

# Per-sample, per-caller SMN1/2 call detail. SMNCopyNumberCaller emits numeric
# SMN1/SMN2 copy numbers. Sentieon SegDup emits a regional SMN1 VCF but the
# captured rollup does not expose a numeric copy-number call; preserve that
# distinction explicitly instead of coercing the completed VCF into a CN.
smn_by_sample = {
    str(row.get("SampleID", "")): row
    for row in raw["multiqc_smn12_orthogonal_calls"].values()
}
smn_caller_rows: list[dict[str, object]] = []
smn_json_paths = sorted(
    SELECTED.glob("*/align/sentdhiomr2sr/smd/htd/smn12/*.summary.json")
)
for path in smn_json_paths:
    analysis_unit_uid = path.relative_to(SELECTED).parts[0]
    sample = base_sample(analysis_unit_uid)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if len(payload) != 1:
        raise ValueError(f"expected one SMN12 record in {path}, found {len(payload)}")
    call = next(iter(payload.values()))
    rollup = smn_by_sample[sample]
    smn_caller_rows.append(
        {
            "sample": sample,
            "caller": "SMNCopyNumberCaller",
            "caller_scope": "SMN1/SMN2 copy number",
            "status": rollup.get("smncopynumbercaller_status", ""),
            "smn1_cn": call.get("SMN1", ""),
            "smn2_cn": call.get("SMN2", ""),
            "smn2delta78_cn": call.get("SMN2delta78", ""),
            "full_length_cn_raw": call.get("Full_length_CN_raw", ""),
            "total_cn_raw": call.get("Total_CN_raw", ""),
            "median_depth": call.get("Median_depth", ""),
            "coverage_mad": call.get("Coverage_MAD", ""),
            "carrier": call.get("isCarrier", ""),
            "sma_affected": call.get("isSMA", ""),
            "call_info": call.get("Info", ""),
            "g27134tg_cn": call.get("g27134TG_CN", ""),
            "expected_concordance": rollup.get(
                "smncopynumbercaller_expected_concordance", ""
            ),
            "primary_result": rollup.get(
                "smncopynumbercaller_primary_path", ""
            ),
            "interpretation": "numeric SMN1/SMN2 copy-number call",
        }
    )
    smn_caller_rows.append(
        {
            "sample": sample,
            "caller": "Sentieon SegDup SMN1",
            "caller_scope": "SMN1 regional variant VCF",
            "status": rollup.get("sentieon_status", ""),
            "smn1_cn": "NA_NOT_EMITTED",
            "smn2_cn": "NA_NOT_EMITTED",
            "smn2delta78_cn": "NA_NOT_EMITTED",
            "full_length_cn_raw": "",
            "total_cn_raw": "",
            "median_depth": "",
            "coverage_mad": "",
            "carrier": "",
            "sma_affected": "",
            "call_info": "regional VCF complete",
            "g27134tg_cn": "",
            "expected_concordance": rollup.get(
                "sentieon_expected_concordance", ""
            ),
            "primary_result": rollup.get("sentieon_primary_path", ""),
            "interpretation": "variant-level SMN1 output; no numeric CN in rollup",
        }
    )
smn_caller_rows.sort(key=lambda row: (str(row["sample"]), str(row["caller"])))
write_tsv(
    OUTPUT / "take222_smn12_calls_by_caller.tsv",
    smn_caller_rows,
    [
        "sample",
        "caller",
        "caller_scope",
        "status",
        "smn1_cn",
        "smn2_cn",
        "smn2delta78_cn",
        "full_length_cn_raw",
        "total_cn_raw",
        "median_depth",
        "coverage_mad",
        "carrier",
        "sma_affected",
        "call_info",
        "g27134tg_cn",
        "expected_concordance",
        "primary_result",
        "interpretation",
    ],
)

# Per-sample coverage matrix for every NICU source caller and merger. Take222
# emits an explicit Truvari receipt only for the NICU Jasmine merged callset.
# The remaining callers/mergers are recorded as not produced, not as zero-score
# benchmarks. The separate public HIOMR2 HG002 validation gate is also carried
# as a query row because it is present in the completed output tree.
truvari_entities = (
    ("Manta", "source caller"),
    ("Dysgu", "source caller"),
    ("TIDDIT", "source caller"),
    ("LongReadSV", "source caller"),
    ("Sniffles2", "source caller"),
    ("Severus", "source caller"),
    ("Jasmine", "merger"),
    ("SURVIVOR", "merger"),
    ("OctopuSV", "merger"),
)
truvari_rows: list[dict[str, object]] = []
for sample in sorted({row["sample"] for row in smn_rows}):
    receipt_paths = list(
        SELECTED.glob(
            f"{sample}-*/align/sentmm2ont/na/snv/sentdhiomr2/"
            "nicu-research/benchmarks/*.truvari.terminal_receipt.json"
        )
    )
    if len(receipt_paths) != 1:
        raise ValueError(
            f"expected one NICU Truvari receipt for {sample}, found {len(receipt_paths)}"
        )
    receipt = json.loads(receipt_paths[0].read_text(encoding="utf-8"))
    for caller, role in truvari_entities:
        if caller == "Jasmine":
            status = "WARNING_NOT_APPLICABLE"
            artifact_present = True
            applicable = receipt.get("applicability", {}).get("applicable", "")
            reason_code = receipt.get("applicability", {}).get("reason_code", "")
            query_name = receipt.get("query_name", "")
            query_vcf_sha256 = receipt.get("query_vcf_sha256", "")
            note = "No HG002 analysis unit; no command attempted and no metrics emitted"
        else:
            status = "NO_PER_CALLER_TRUVARI_ARTIFACT"
            artifact_present = False
            applicable = "NOT_EVALUATED"
            reason_code = "TAKE222_NO_PER_CALLER_TRUVARI"
            query_name = ""
            query_vcf_sha256 = ""
            note = "Analytical callset exists, but Take222 produced no caller-specific Truvari result"
        truvari_rows.append(
            {
                "sample": sample,
                "caller_or_query": caller,
                "callset_role": role,
                "artifact_present": artifact_present,
                "benchmark_status": status,
                "applicable": applicable,
                "truth_scope": "HG002 only",
                "query_name": query_name,
                "tp_base": "NA",
                "tp_comp": "NA",
                "fp": "NA",
                "fn": "NA",
                "precision": "NA",
                "recall": "NA",
                "f1": "NA",
                "reason_code": reason_code,
                "attempted_command": False,
                "query_vcf_sha256": query_vcf_sha256,
                "note": note,
            }
        )

aggregate_receipt = json.loads(
    (
        SELECTED
        / "benchmarks"
        / "truvari"
        / "hiomr2_hg002"
        / "aggregate"
        / "terminal_receipt.json"
    ).read_text(encoding="utf-8")
)
for row in aggregate_receipt.get("rows", []):
    truvari_rows.append(
        {
            "sample": row.get("SampleID", ""),
            "caller_or_query": "HIOMR2 public HG002 gate",
            "callset_role": "aggregate validation query",
            "artifact_present": True,
            "benchmark_status": "WARNING_NOT_APPLICABLE",
            "applicable": False,
            "truth_scope": row.get("truth_scope", "HG002_only"),
            "query_name": row.get("query", ""),
            "tp_base": "NA",
            "tp_comp": "NA",
            "fp": "NA",
            "fn": "NA",
            "precision": "NA",
            "recall": "NA",
            "f1": "NA",
            "reason_code": aggregate_receipt.get("warning", {}).get("code", ""),
            "attempted_command": False,
            "query_vcf_sha256": "",
            "note": aggregate_receipt.get("warning", {}).get("message", ""),
        }
    )
truvari_rows.sort(
    key=lambda row: (str(row["sample"]), str(row["callset_role"]), str(row["caller_or_query"]))
)
write_tsv(
    OUTPUT / "take222_truvari_results_by_caller.tsv",
    truvari_rows,
    [
        "sample",
        "caller_or_query",
        "callset_role",
        "artifact_present",
        "benchmark_status",
        "applicable",
        "truth_scope",
        "query_name",
        "tp_base",
        "tp_comp",
        "fp",
        "fn",
        "precision",
        "recall",
        "f1",
        "reason_code",
        "attempted_command",
        "query_vcf_sha256",
        "note",
    ],
)

# Two compact matrices keep the per-sample/per-caller audit readable in the
# portable HTML/PDF while the long-form TSV above preserves every receipt
# field. "No artifact" is deliberately distinct from an evaluated zero.
truvari_by_sample = {
    sample: {
        str(row["caller_or_query"]): row
        for row in truvari_rows
        if row["sample"] == sample
    }
    for sample in sorted({str(row["sample"]) for row in truvari_rows})
}


def compact_truvari_status(row: dict[str, object]) -> str:
    if row["benchmark_status"] == "WARNING_NOT_APPLICABLE":
        return "Warning: no HG002"
    return "No artifact"


source_matrix_rows = []
merger_matrix_rows = []
for sample, sample_rows in truvari_by_sample.items():
    source_matrix_rows.append(
        {
            "sample": sample,
            **{
                caller: compact_truvari_status(sample_rows[caller])
                for caller in ("Manta", "Dysgu", "TIDDIT", "LongReadSV", "Sniffles2", "Severus")
            },
        }
    )
    merger_matrix_rows.append(
        {
            "sample": sample,
            **{
                caller: compact_truvari_status(sample_rows[caller])
                for caller in ("Jasmine", "SURVIVOR", "OctopuSV", "HIOMR2 public HG002 gate")
            },
        }
    )
write_tsv(
    OUTPUT / "take222_truvari_source_caller_matrix.tsv",
    source_matrix_rows,
    ["sample", "Manta", "Dysgu", "TIDDIT", "LongReadSV", "Sniffles2", "Severus"],
)
write_tsv(
    OUTPUT / "take222_truvari_merger_query_matrix.tsv",
    merger_matrix_rows,
    ["sample", "Jasmine", "SURVIVOR", "OctopuSV", "HIOMR2 public HG002 gate"],
)

# Sample-scoped benchmark totals and top rules. The totals are task-walltime
# sums, not campaign/controller makespan.
benchmarks = list(raw["multiqc_snakemake_benchmark_rows"].values())
known_samples = {"HG003", "HG004", "NA19235", "NA20775"}
runtime_acc: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
runtime_count: Counter[str] = Counter()
runtime_start: dict[str, str] = {}
runtime_end: dict[str, str] = {}
runtime_longest: dict[str, tuple[float, str]] = {}
top_rules: list[dict[str, object]] = []
global_runtime: dict[str, float] = defaultdict(float)
global_count = 0
for row in benchmarks:
    sample = base_sample(str(row.get("sample", "")))
    wall = float(row.get("walltime_hours", 0) or 0)
    vcpu = float(row.get("allocated_vcpu_time_hours", 0) or 0)
    cpu = float(row.get("observed_cpu_time_hours", 0) or 0)
    cost = float(row.get("task_cost", 0) or 0)
    if sample in known_samples:
        runtime_count[sample] += 1
        runtime_acc[sample]["task_wall_hours"] += wall
        runtime_acc[sample]["allocated_vcpu_hours"] += vcpu
        runtime_acc[sample]["observed_cpu_hours"] += cpu
        runtime_acc[sample]["task_cost"] += cost
        start = str(row.get("start_datetime", ""))
        end = str(row.get("end_datetime", ""))
        if start and (sample not in runtime_start or start < runtime_start[sample]):
            runtime_start[sample] = start
        if end and (sample not in runtime_end or end > runtime_end[sample]):
            runtime_end[sample] = end
        if sample not in runtime_longest or wall > runtime_longest[sample][0]:
            runtime_longest[sample] = (wall, str(row.get("aggregate_rule", "")))
        top_rules.append(
            {
                "sample": sample,
                "rule": row.get("aggregate_rule", ""),
                "wall_hours": wall,
                "allocated_vcpu_hours": vcpu,
                "observed_cpu_hours": cpu,
                "task_cost": cost,
                "threads": row.get("snakemake_threads", ""),
                "instance_type": row.get("instance_type", ""),
                "status": row.get("status", ""),
            }
        )
    else:
        global_count += 1
        global_runtime["task_wall_hours"] += wall
        global_runtime["allocated_vcpu_hours"] += vcpu
        global_runtime["observed_cpu_hours"] += cpu
        global_runtime["task_cost"] += cost

runtime_rows: list[dict[str, object]] = []
for sample in sorted(known_samples):
    values = runtime_acc[sample]
    first_start = runtime_start[sample]
    last_end = runtime_end[sample]
    benchmark_span = (datetime.fromisoformat(last_end.replace("Z", "+00:00")) - datetime.fromisoformat(first_start.replace("Z", "+00:00"))).total_seconds() / 3600
    runtime_rows.append(
        {
            "sample": sample,
            "benchmark_rows": runtime_count[sample],
            "first_task_start_utc": first_start,
            "last_task_end_utc": last_end,
            "benchmark_span_hours": round(benchmark_span, 6),
            "task_wall_hours_sum": round(values["task_wall_hours"], 6),
            "allocated_vcpu_hours": round(values["allocated_vcpu_hours"], 6),
            "observed_cpu_hours": round(values["observed_cpu_hours"], 6),
            "task_cost_usd": round(values["task_cost"], 6),
            "longest_task_rule": runtime_longest[sample][1],
            "longest_task_hours": round(runtime_longest[sample][0], 6),
        }
    )
runtime_rows.append(
    {
        "sample": "shared_or_global",
        "benchmark_rows": global_count,
        "first_task_start_utc": "",
        "last_task_end_utc": "",
        "benchmark_span_hours": "",
        "task_wall_hours_sum": round(global_runtime["task_wall_hours"], 6),
        "allocated_vcpu_hours": round(global_runtime["allocated_vcpu_hours"], 6),
        "observed_cpu_hours": round(global_runtime["observed_cpu_hours"], 6),
        "task_cost_usd": round(global_runtime["task_cost"], 6),
        "longest_task_rule": "",
        "longest_task_hours": "",
    }
)
write_tsv(
    OUTPUT / "take222_runtime_per_sample.tsv",
    runtime_rows,
    [
        "sample",
        "benchmark_rows",
        "first_task_start_utc",
        "last_task_end_utc",
        "benchmark_span_hours",
        "task_wall_hours_sum",
        "allocated_vcpu_hours",
        "observed_cpu_hours",
        "task_cost_usd",
        "longest_task_rule",
        "longest_task_hours",
    ],
)
top_rules.sort(key=lambda row: float(row["wall_hours"]), reverse=True)
write_tsv(
    OUTPUT / "take222_longest_sample_tasks.tsv",
    top_rules[:40],
    ["sample", "rule", "wall_hours", "allocated_vcpu_hours", "observed_cpu_hours", "task_cost", "threads", "instance_type", "status"],
)

# Aggregate per-rule runtime across the four samples.
rule_acc: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
rule_samples: dict[str, set[str]] = defaultdict(set)
rule_count: Counter[str] = Counter()
for row in top_rules:
    rule = str(row["rule"])
    rule_count[rule] += 1
    rule_samples[rule].add(str(row["sample"]))
    rule_acc[rule]["wall"] += float(row["wall_hours"])
    rule_acc[rule]["vcpu"] += float(row["allocated_vcpu_hours"])
    rule_acc[rule]["cpu"] += float(row["observed_cpu_hours"])
    rule_acc[rule]["cost"] += float(row["task_cost"])
rule_rows = [
    {
        "rule": rule,
        "rows": rule_count[rule],
        "samples": ",".join(sorted(rule_samples[rule])),
        "task_wall_hours_sum": round(values["wall"], 6),
        "allocated_vcpu_hours": round(values["vcpu"], 6),
        "observed_cpu_hours": round(values["cpu"], 6),
        "task_cost_usd": round(values["cost"], 6),
    }
    for rule, values in rule_acc.items()
]
rule_rows.sort(key=lambda row: float(row["task_wall_hours_sum"]), reverse=True)
write_tsv(
    OUTPUT / "take222_runtime_by_rule.tsv",
    rule_rows,
    ["rule", "rows", "samples", "task_wall_hours_sum", "allocated_vcpu_hours", "observed_cpu_hours", "task_cost_usd"],
)

# NICU result counts and applicability status.
nicu_rows: list[dict[str, object]] = []
for row in raw["multiqc_sentdhiomr2_nicu"].values():
    nicu_rows.append(
        {
            "sample": base_sample(str(row.get("AnalysisUnitUID", ""))),
            "jasmine_records": row.get("jasmine_records", ""),
            "jasmine_dysgu_supported": row.get("jasmine_dysgu_supported", ""),
            "jasmine_manta_supported": row.get("jasmine_manta_supported", ""),
            "cnv_50pct_reciprocal_matches": row.get("cnv_50pct_reciprocal_matches", ""),
            "bnd_topology_valid": row.get("bnd_topology_valid", ""),
            "truvari_status": row.get("truvari_status", ""),
            "truvari_f1": row.get("truvari_f1", ""),
            "ont_source_read_records": row.get("ont_source_read_records", ""),
            "sr_source_read_records": row.get("sr_source_read_records", ""),
            "fastq_content_level_lossless": row.get("fastq_content_level_lossless", ""),
            "exact_original_fastq_bytes_recoverable": row.get("exact_original_fastq_bytes_recoverable", ""),
        }
    )
nicu_rows.sort(key=lambda row: str(row["sample"]))
write_tsv(
    OUTPUT / "take222_nicu_summary.tsv",
    nicu_rows,
    [
        "sample",
        "jasmine_records",
        "jasmine_dysgu_supported",
        "jasmine_manta_supported",
        "cnv_50pct_reciprocal_matches",
        "bnd_topology_valid",
        "truvari_status",
        "truvari_f1",
        "ont_source_read_records",
        "sr_source_read_records",
        "fastq_content_level_lossless",
        "exact_original_fastq_bytes_recoverable",
    ],
)

# Direct long-read SV counts surfaced in MultiQC.
sv_rows: list[dict[str, object]] = []
for source_key, caller_label in (
    ("multiqc_sentdhiomr2_sniffles2", "Sniffles2"),
    ("multiqc_sentdhiomr2_tiddit", "TIDDIT"),
):
    for row in raw[source_key].values():
        sv_rows.append(
            {
                "sample": base_sample(str(row.get("base_sample", ""))),
                "caller": caller_label,
                "total_records": row.get("total_records", ""),
                "DEL": row.get("DEL", ""),
                "INS": row.get("INS", ""),
                "DUP": row.get("DUP", ""),
                "INV": row.get("INV", ""),
                "BND": row.get("BND", ""),
                "other": row.get("other_svtype", ""),
                "status": row.get("status", ""),
            }
        )
sv_rows.sort(key=lambda row: (str(row["sample"]), str(row["caller"])))
write_tsv(
    OUTPUT / "take222_direct_sv_counts.tsv",
    sv_rows,
    ["sample", "caller", "total_records", "DEL", "INS", "DUP", "INV", "BND", "other", "status"],
)

# Inflection manifests: package summary, review tags, and a deduplicated role catalog.
package_rows: list[dict[str, object]] = []
review_rows: list[dict[str, object]] = []
role_counter: Counter[tuple[str, str, str]] = Counter()
for path, package in sorted(packages.items()):
    artifacts = package["artifacts"]
    established = sum(1 for artifact in artifacts if artifact.get("package_tier") == "established")
    experimental = sum(1 for artifact in artifacts if artifact.get("package_tier") == "experimental")
    package_rows.append(
        {
            "sample": package.get("external_sample_id", ""),
            "analysis_unit_uid": package.get("analysis_unit_uid", ""),
            "schema": package.get("schema", ""),
            "package_mode": package.get("package_mode", ""),
            "artifact_count": package.get("artifact_count", ""),
            "established_artifacts": established,
            "experimental_artifacts": experimental,
            "declared_bytes": sum(int(artifact.get("bytes", 0) or 0) for artifact in artifacts),
            "nicu_research_included": package.get("nicu_research_included", ""),
            "customer_release_eligible": package.get("customer_release_eligible", ""),
            "customer_release_reason": package.get("customer_release_reason", ""),
            "manifest_path": path,
        }
    )
    total_tags = sum(int(value) for value in package.get("scoped_vcf_review_tag_counts", {}).values())
    for tag, count in sorted(package.get("scoped_vcf_review_tag_counts", {}).items()):
        review_rows.append(
            {
                "sample": package.get("external_sample_id", ""),
                "review_tag": tag,
                "count": count,
                "share_pct": round(100 * int(count) / total_tags, 6) if total_tags else "",
            }
        )
    for artifact in artifacts:
        role_counter[(str(artifact.get("package_tier", "")), str(artifact.get("role", "")), str(artifact.get("semantic_type", "")))] += 1

write_tsv(
    OUTPUT / "take222_inflection_package_summary.tsv",
    package_rows,
    [
        "sample",
        "analysis_unit_uid",
        "schema",
        "package_mode",
        "artifact_count",
        "established_artifacts",
        "experimental_artifacts",
        "declared_bytes",
        "nicu_research_included",
        "customer_release_eligible",
        "customer_release_reason",
        "manifest_path",
    ],
)
write_tsv(OUTPUT / "take222_variant_review_tags.tsv", review_rows, ["sample", "review_tag", "count", "share_pct"])
role_rows = [
    {"package_tier": tier, "role": role, "semantic_type": semantic_type, "sample_occurrences": count}
    for (tier, role, semantic_type), count in sorted(role_counter.items())
]
write_tsv(
    OUTPUT / "take222_inflection_artifact_roles.tsv",
    role_rows,
    ["package_tier", "role", "semantic_type", "sample_occurrences"],
)

summary = {
    "report_creation_date": multiqc.get("report_creation_date"),
    "multiqc_version": multiqc.get("config_version"),
    "multiqc_data_source_module_count": len(multiqc.get("report_data_sources", {})),
    "multiqc_raw_dataset_count": len(raw),
    "benchmark_row_count": len(benchmarks),
    "sample_scoped_benchmark_rows": sum(runtime_count.values()),
    "global_benchmark_rows": global_count,
    "package_count": len(packages),
    "package_artifact_count": sum(int(package.get("artifact_count", 0)) for package in packages.values()),
    "package_declared_bytes": sum(sum(int(artifact.get("bytes", 0) or 0) for artifact in package["artifacts"]) for package in packages.values()),
    "giabhc_result_rows": len(giab_rows),
    "smn12_rows": len(smn_rows),
    "nicu_rows": len(nicu_rows),
}
(OUTPUT / "take222_report_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

inventory_summary = json.loads((SOURCE / "take222_output_inventory_summary.json").read_text(encoding="utf-8"))
inventory_rows = [
    {
        "category": category,
        "file_count": inventory_summary["category_counts"][category],
        "bytes": inventory_summary["category_bytes"][category],
        "gigabytes": round(inventory_summary["category_bytes"][category] / 1_000_000_000, 6),
    }
    for category in sorted(inventory_summary["category_counts"])
]
write_tsv(OUTPUT / "take222_output_inventory_category_summary.tsv", inventory_rows, ["category", "file_count", "bytes", "gigabytes"])
print(json.dumps(summary, indent=2))
