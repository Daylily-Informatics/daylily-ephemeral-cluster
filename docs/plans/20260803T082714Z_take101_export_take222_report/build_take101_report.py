#!/usr/bin/env python3
"""Build the canonical Take101 Data Analytics report artifact from reviewed TSVs."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "TAKE101_HG002_NA23687_FULLCOV_HIOMR2_13.4.2_VALIDATION_REPORT.artifact.json"


def coerce(value: str):
    if value == "":
        return ""
    if re.fullmatch(r"-?[0-9]+", value):
        return int(value)
    if re.fullmatch(r"-?(?:[0-9]+\.[0-9]*|[0-9]*\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value):
        return float(value)
    return value


def read_tsv(filename: str) -> list[dict[str, object]]:
    with (ROOT / filename).open(newline="", encoding="utf-8") as handle:
        return [{key: coerce(value) for key, value in row.items()} for row in csv.DictReader(handle, delimiter="\t")]


generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

coverage = read_tsv("TAKE101_COVERAGE_FRAGMENT_STATS.tsv")
treatments = read_tsv("TAKE101_VARIANT_TREATMENT_COUNTS.tsv")
giab = read_tsv("TAKE101_GIAB_HARD_VCF_F_SCORES.tsv")
smn12 = read_tsv("TAKE101_SMN12_AUDIT.tsv")
truvari = read_tsv("TAKE101_TRUVARI_AUDIT.tsv")
completion = read_tsv("TAKE101_COMPLETION_ARTIFACTS.tsv")
s3_uris = read_tsv("TAKE101_IMPORTANT_S3_URIS.tsv")
repairs = read_tsv("TAKE101_WORKFLOW_REPAIRS.tsv")
packages = read_tsv("TAKE101_PACKAGE_SUMMARY.tsv")
release = read_tsv("TAKE101_DAYOA_RELEASE_PROVENANCE.tsv")

coverage_chart = []
for row in coverage:
    short_modality = "ILMN" if str(row["modality"]).startswith("Illumina") else "ONT"
    coverage_chart.append(
        {
            "sample_modality": f"{row['sample']} {short_modality}",
            "sample": row["sample"],
            "modality": short_modality,
            "mean_coverage_x": row["mean_coverage_x"],
            "median_coverage_x": row["median_coverage_x"],
            "bases_30x_pct": row["bases_30x_pct"],
        }
    )

combined_counts: dict[str, int] = defaultdict(int)
for row in treatments:
    combined_counts[str(row["treatment"])] += int(row["count"])
combined_total = sum(combined_counts.values())
variant_treatment_combined = [
    {
        "treatment": treatment,
        "count": count,
        "share_pct": round(100.0 * count / combined_total, 4),
    }
    for treatment, count in sorted(combined_counts.items(), key=lambda item: item[1], reverse=True)
]

truvari_status_counts = [
    {"status": "Published / accepted metrics", "query_count": 6, "share_pct": 40.0},
    {"status": "Successful alias evidence", "query_count": 1, "share_pct": 6.6667},
    {"status": "Diagnostic gap / no published metric", "query_count": 7, "share_pct": 46.6667},
    {"status": "Not applicable", "query_count": 1, "share_pct": 6.6667},
]


def source(source_id: str, label: str, path: str, sql: str, description: str, tables: list[str], filters: list[str] | None = None):
    query = {
        "engine": "duckdb",
        "language": "sql",
        "sql": sql,
        "description": description,
        "tables_used": tables,
        "executed_at": generated_at,
    }
    if filters:
        query["filters"] = filters
    return {"id": source_id, "label": label, "path": path, "query": query}


sources = [
    source(
        "release_provenance",
        "DayOA 13.4.2 local/headnode release reconciliation",
        "TAKE101_DAYOA_RELEASE_PROVENANCE.tsv",
        "SELECT * FROM read_csv_auto('TAKE101_DAYOA_RELEASE_PROVENANCE.tsv', delim='\\t', header=true)",
        "Reads the exact pushed branch, annotated tag, commit, tree-equivalence, diff, and focused-test receipt.",
        ["TAKE101_DAYOA_RELEASE_PROVENANCE.tsv"],
    ),
    source(
        "coverage_fragment",
        "Final MultiQC coverage and fragment audit",
        "TAKE101_COVERAGE_FRAGMENT_STATS.tsv",
        "SELECT * FROM read_csv_auto('TAKE101_COVERAGE_FRAGMENT_STATS.tsv', delim='\\t', header=true)",
        "Reads reviewed AlignStats, Mosdepth, FastQC, and Samtools values for the final two-sample MultiQC snapshot.",
        [
            "TAKE101_COVERAGE_FRAGMENT_STATS.tsv",
            "daylily-omics-analysis/results/day/hg38/reports/DAY_final_multiqc_data/multiqc_data.json",
        ],
    ),
    source(
        "variant_treatments",
        "Inflection scoped-VCF review-tag counts",
        "TAKE101_VARIANT_TREATMENT_COUNTS.tsv",
        "SELECT * FROM read_csv_auto('TAKE101_VARIANT_TREATMENT_COUNTS.tsv', delim='\\t', header=true)",
        "Reads every scoped review-treatment count and its within-sample share from both package manifests.",
        [
            "TAKE101_VARIANT_TREATMENT_COUNTS.tsv",
            "daylily-omics-analysis/results/day/hg38/deliveries/inflection_hiomr2_analytical_callsets_vcf_gvcf/take101/HG002-ck2ky6p4wk6exh/package_manifest.json",
            "daylily-omics-analysis/results/day/hg38/deliveries/inflection_hiomr2_analytical_callsets_vcf_gvcf/take101/NA23687-zsvw0fa30jhz3n/package_manifest.json",
        ],
    ),
    source(
        "workflow_repairs",
        "Live-proven Take101 workflow repairs",
        "TAKE101_WORKFLOW_REPAIRS.tsv",
        "SELECT * FROM read_csv_auto('TAKE101_WORKFLOW_REPAIRS.tsv', delim='\\t', header=true)",
        "Reads the three bounded DayOA 13.4.2 repairs and their actual Take101 live evidence.",
        ["TAKE101_WORKFLOW_REPAIRS.tsv"],
    ),
    source(
        "giab_concordance",
        "RTG GIAB hard-VCF concordance",
        "TAKE101_GIAB_HARD_VCF_F_SCORES.tsv",
        "SELECT * FROM read_csv_auto('TAKE101_GIAB_HARD_VCF_F_SCORES.tsv', delim='\\t', header=true) WHERE roi = 'giabHC' AND caller = 'sentdhiomr2'",
        "Reads the HG002 hard-VCF RTG vcfeval rows in GIAB high-confidence regions.",
        [
            "TAKE101_GIAB_HARD_VCF_F_SCORES.tsv",
            "daylily-omics-analysis/results/day/hg38/other_reports/giab_concordance_mqc.tsv",
        ],
        ["ROI = giabHC", "SNVCaller = sentdhiomr2", "hard VCF rows only"],
    ),
    source(
        "smn12_orthogonal",
        "Sentieon SMN1 and SMNCopyNumberCaller audit",
        "TAKE101_SMN12_AUDIT.tsv",
        "SELECT * FROM read_csv_auto('TAKE101_SMN12_AUDIT.tsv', delim='\\t', header=true)",
        "Reads both samples' orthogonal regional-variant and copy-number evidence without conflating the caller roles.",
        [
            "TAKE101_SMN12_AUDIT.tsv",
            "daylily-omics-analysis/results/day/hg38/other_reports/smn12_orthogonal_calls_mqc.tsv",
        ],
    ),
    source(
        "truvari_audit",
        "Exhaustive Truvari and copy-state terminal audit",
        "TAKE101_TRUVARI_AUDIT.tsv",
        "SELECT * FROM read_csv_auto('TAKE101_TRUVARI_AUDIT.tsv', delim='\\t', header=true)",
        "Reads every standard query receipt, the alignment comparison, the alias receipt, copy-state gaps, and both sample-specific NICU receipts.",
        [
            "TAKE101_TRUVARI_AUDIT.tsv",
            "daylily-omics-analysis/results/day/hg38/benchmarks/truvari/hiomr2_hg002/aggregate/aggregate.json",
            "daylily-omics-analysis/results/day/hg38/benchmarks/truari/hiomr2_hg002/jasmine_alignment_compare/terminal_receipt.json",
        ],
        ["PASS-only for GIAB DEL/INS >=50 standard queries", "raw diagnostic metrics are not published metrics"],
    ),
    source(
        "package_summary",
        "Inflection analytical-package manifests",
        "TAKE101_PACKAGE_SUMMARY.tsv",
        "SELECT * FROM read_csv_auto('TAKE101_PACKAGE_SUMMARY.tsv', delim='\\t', header=true)",
        "Reads package schema, artifact count, declared bytes, NICU inclusion, mode, and customer-release eligibility.",
        ["TAKE101_PACKAGE_SUMMARY.tsv"],
    ),
    source(
        "completion_artifacts",
        "Verified completion artifact receipt",
        "TAKE101_COMPLETION_ARTIFACTS.tsv",
        "SELECT * FROM read_csv_auto('TAKE101_COMPLETION_ARTIFACTS.tsv', delim='\\t', header=true)",
        "Reads exact export-relative paths, sizes, hashes, and planned stable S3 URIs for primary terminal artifacts.",
        ["TAKE101_COMPLETION_ARTIFACTS.tsv"],
    ),
    source(
        "s3_objects",
        "Important stable S3 object URIs",
        "TAKE101_IMPORTANT_S3_URIS.tsv",
        "SELECT * FROM read_csv_auto('TAKE101_IMPORTANT_S3_URIS.tsv', delim='\\t', header=true)",
        "Reads the stable export prefix and important report, MultiQC, benchmark, evidence, and package URIs.",
        ["TAKE101_IMPORTANT_S3_URIS.tsv"],
    ),
]


def columns(*fields: tuple[str, str]):
    return [{"field": field, "label": label} for field, label in fields]


charts = [
    {
        "id": "coverage_mean_chart",
        "title": "Mean coverage by sample and modality",
        "subtitle": "Final Mosdepth means: duplicate-marked Illumina versus retained ONT elapsed-hour window [0,25).",
        "type": "bar",
        "dataset": "coverage_chart",
        "sourceId": "coverage_fragment",
        "encodings": {
            "x": {"field": "sample_modality", "type": "nominal"},
            "y": {"field": "mean_coverage_x", "type": "quantitative"},
            "tooltip": [
                {"field": "sample", "type": "nominal"},
                {"field": "modality", "type": "nominal"},
                {"field": "mean_coverage_x", "type": "quantitative"},
                {"field": "median_coverage_x", "type": "quantitative"},
                {"field": "bases_30x_pct", "type": "quantitative"},
            ],
        },
    },
    {
        "id": "variant_treatment_chart",
        "title": "Combined scoped-VCF treatment-tag share",
        "subtitle": "Across 10.43M scoped records from both analytical packages; labels are review treatments, not clinical classifications.",
        "type": "bar",
        "dataset": "variant_treatment_combined",
        "sourceId": "variant_treatments",
        "encodings": {
            "x": {"field": "treatment", "type": "nominal"},
            "y": {"field": "share_pct", "type": "quantitative"},
            "tooltip": [
                {"field": "treatment", "type": "nominal"},
                {"field": "count", "type": "quantitative"},
                {"field": "share_pct", "type": "quantitative"},
            ],
        },
    },
    {
        "id": "truvari_status_chart",
        "title": "Terminal benchmark evidence disposition",
        "subtitle": "All 15 audited result lanes are terminal; missing metrics remain explicit gaps rather than invented values.",
        "type": "bar",
        "dataset": "truvari_status_counts",
        "sourceId": "truvari_audit",
        "encodings": {
            "x": {"field": "status", "type": "nominal"},
            "y": {"field": "query_count", "type": "quantitative"},
            "tooltip": [
                {"field": "status", "type": "nominal"},
                {"field": "query_count", "type": "quantitative"},
                {"field": "share_pct", "type": "quantitative"},
            ],
        },
    },
]

tables = [
    {
        "id": "coverage_table",
        "title": "Coverage, mapping, read-length, and fragment statistics",
        "dataset": "coverage_fragment",
        "sourceId": "coverage_fragment",
        "defaultSort": {"field": "sample", "direction": "asc"},
        "columns": columns(
            ("sample", "Sample"), ("modality", "Modality"), ("mean_coverage_x", "Mean coverage"),
            ("median_coverage_x", "Median coverage"), ("bases_30x_pct", "Bases >=30x, %"),
            ("mapped_reads_pct", "Mapped, %"), ("duplicate_reads_pct", "Duplicates, %"),
            ("aligned_records", "Aligned records"), ("average_read_length_bp", "Mean read length, bp"),
            ("insert_median_bp", "Insert median, bp"), ("mean_insert_bp", "Insert mean, bp"),
        ),
    },
    {
        "id": "variant_treatment_table",
        "title": "Per-sample scoped-VCF review treatments",
        "dataset": "variant_treatments",
        "sourceId": "variant_treatments",
        "defaultSort": {"field": "count", "direction": "desc"},
        "columns": columns(
            ("sample", "Sample"), ("treatment", "Treatment"), ("count", "Records"),
            ("share_pct", "Within-sample share, %"), ("total_scoped_records", "Scoped total"),
        ),
    },
    {
        "id": "workflow_repairs_table",
        "title": "Live-proven DayOA 13.4.2 repairs",
        "dataset": "workflow_repairs",
        "sourceId": "workflow_repairs",
        "defaultSort": {"field": "repair", "direction": "asc"},
        "columns": columns(("repair", "Repair"), ("live_evidence", "Actual Take101 evidence"), ("behavior", "Fail-closed behavior")),
    },
    {
        "id": "giab_table",
        "title": "HG002 hard-VCF RTG vcfeval rows for ROI = giabHC",
        "dataset": "giab_hard_vcf",
        "sourceId": "giab_concordance",
        "defaultSort": {"field": "variant_class", "direction": "asc"},
        "columns": columns(
            ("variant_class", "Variant class"), ("fscore", "F-score"),
            ("sensitivity_recall", "Sensitivity / recall"), ("precision", "Precision"),
            ("tp", "TP"), ("fp", "FP"), ("fn", "FN"),
        ),
    },
    {
        "id": "smn12_table",
        "title": "Sentieon regional and SMNCopyNumberCaller evidence",
        "dataset": "smn12_callers",
        "sourceId": "smn12_orthogonal",
        "defaultSort": {"field": "sample", "direction": "asc"},
        "columns": columns(
            ("sample", "Sample"), ("caller", "Caller"), ("status", "Status"),
            ("smn1_cn", "SMN1 CN"), ("smn2_cn", "SMN2 CN"),
            ("is_sma", "SMA"), ("is_carrier", "Carrier"),
            ("median_depth", "Median depth"), ("raw_evidence", "Observed evidence"),
            ("interpretation", "Interpretation"),
        ),
    },
    {
        "id": "truvari_table",
        "title": "All terminal Truvari, alias, copy-state, and applicability evidence",
        "dataset": "truvari_audit",
        "sourceId": "truvari_audit",
        "defaultSort": {"field": "query", "direction": "asc"},
        "columns": columns(
            ("sample", "Sample"), ("query", "Query"), ("publication_status", "Published status"),
            ("projected", "Projected"), ("compared", "Compared"),
            ("published_f1", "Published F1"), ("raw_f1", "Raw F1"),
            ("raw_precision", "Raw precision"), ("raw_recall", "Raw recall"),
            ("gap_or_interpretation", "Gap / interpretation"),
        ),
    },
    {
        "id": "package_table",
        "title": "Inflection analytical-package closure",
        "dataset": "package_summary",
        "sourceId": "package_summary",
        "defaultSort": {"field": "sample", "direction": "asc"},
        "columns": columns(
            ("sample", "Sample"), ("schema", "Schema"), ("artifact_count", "Artifacts"),
            ("declared_bytes", "Declared bytes"), ("nicu_research_included", "NICU included"),
            ("package_mode", "Mode"), ("customer_release_eligible", "Customer-release eligible"),
            ("customer_release_reason", "Reason"),
        ),
    },
    {
        "id": "artifact_table",
        "title": "Primary terminal artifacts and stable S3 URIs",
        "dataset": "completion_artifacts",
        "sourceId": "completion_artifacts",
        "defaultSort": {"field": "artifact", "direction": "asc"},
        "columns": columns(
            ("artifact", "Artifact"), ("relative_path", "Export-relative path"),
            ("bytes", "Bytes"), ("sha256", "SHA-256"), ("s3_uri", "S3 URI"),
        ),
    },
    {
        "id": "s3_table",
        "title": "Important Take101 S3 locations",
        "dataset": "s3_uris",
        "sourceId": "s3_objects",
        "defaultSort": {"field": "label", "direction": "asc"},
        "columns": columns(("label", "Object / prefix"), ("s3_uri", "S3 URI"), ("description", "Purpose")),
    },
]

blocks = [
    {
        "id": "technical_summary",
        "type": "markdown",
        "sourceId": "release_provenance",
        "body": "# Take101 full-coverage HIOMR2 validation — DayOA 13.4.2\n\n## Technical summary\n\nThe literal eight-target HIOMR2 kitchen-sink, mega-adjacent validation, Inflection analytical-packaging, and final MultiQC closure completed at **RC=0** for full-coverage HG002 and NA23687. The original controller completed 441 of 466 logical steps; the bounded repair controller completed the remaining 25 of 25. All live-proven source changes are pushed on `codex/13.4.2-take101-multisample-nicu-warning` and released by annotated non-v tag **13.4.2** at commit `53b43186f0b840a756c9151df1ff1b830033c139`. Local and headnode release trees match exactly. These are analytical/research outputs, not clinical or customer-release packages.",
    },
    {
        "id": "coverage_summary",
        "type": "markdown",
        "sourceId": "coverage_fragment",
        "body": "## Coverage and fragment findings\n\nDuplicate-marked Illumina coverage is **45.23x** for HG002 and **44.24x** for NA23687; both have **92%** of measured bases at or above 30x. The retained ONT `[0,25)` windows are **12.19x** and **16.38x**, respectively. Illumina mapping is 99.80–99.83%, aligned duplicate rates are 12.97% and 11.73%, median inserts are 428 bp and 427 bp, and mean inserts are 459.6 bp and 458.3 bp. ONT contributes 4.97M and 5.27M aligned records with mean read lengths 7.7 kb and 9.8 kb. The observed coverage, rather than filenames, is the basis for describing this as a full-coverage two-sample proof.",
    },
    {"id": "coverage_chart_block", "type": "chart", "chartId": "coverage_mean_chart"},
    {"id": "coverage_table_block", "type": "table", "tableId": "coverage_table"},
    {
        "id": "variant_treatment_summary",
        "type": "markdown",
        "sourceId": "variant_treatments",
        "body": "## Variant treatments in the analytical packages\n\nHG002 has **5,149,139** scoped records and NA23687 has **5,281,521**. Confirmed records comprise **79.59%** and **80.21%**. The largest review categories are Unconfirmed (**10.35%**, **10.09%**), AlleleBalance (**4.84%**, **4.92%**), and LowCoverage (**3.88%**, **3.41%**). These labels are deterministic analytical review treatments applied to the scoped VCFs; they are not pathogenicity assertions, truth labels, or clinical classifications.",
    },
    {"id": "variant_treatment_chart_block", "type": "chart", "chartId": "variant_treatment_chart"},
    {"id": "variant_treatment_table_block", "type": "table", "tableId": "variant_treatment_table"},
    {
        "id": "repair_summary",
        "type": "markdown",
        "sourceId": "workflow_repairs",
        "body": "## Live-proven normalization and workflow repairs\n\nDayOA 13.4.2 adds only three bounded behaviors needed by this multisample proof: explicit non-HG002 NICU Truvari non-applicability, deterministic Somalier header-only group output when there are no groups, and provenance-recorded Manta IUPAC reference-anchor normalization. The actual NA23687 Manta fixture preserved all **155,191** records and changed exactly two source `GN` anchors to canonical `GR`. No alternate caller, guessed truth, or silent fallback was introduced.",
    },
    {"id": "workflow_repairs_table_block", "type": "table", "tableId": "workflow_repairs_table"},
    {
        "id": "giab_summary",
        "type": "markdown",
        "sourceId": "giab_concordance",
        "body": "## HG002 SNV hard-VCF accuracy in `ROI == giabHC`\n\nThe hard-VCF RTG vcfeval `All` F-score is **0.9992765**; transition and transversion F-scores are **0.9993632** and **0.9992946**. The 1–50 bp insertion and deletion rows are **0.9986882** and **0.9990539**. The `>50 bp` insertion stratum has only six TPs and ten FNs, while the deletion stratum has four TPs and no errors, so those tiny strata should not be generalized. The parallel CLI-gVCF rows have identical metrics. This GIAB truth analysis applies to HG002 only.",
    },
    {"id": "giab_table_block", "type": "table", "tableId": "giab_table"},
    {
        "id": "smn12_summary",
        "type": "markdown",
        "sourceId": "smn12_orthogonal",
        "body": "## SMN1 / SMN2 findings\n\nSMNCopyNumberCaller reports HG002 as **SMN1=2, SMN2=2**, `isSMA=false`, `isCarrier=false`, with median depth 53.15. NA23687 reports **SMN1=1, SMN2=2**, `isSMA=false`, `isCarrier=true`, with median depth 51.72. All 16 locus-level estimates agree with each final SMN1 integer. The Sentieon SMN1 lane completed and produced 65 and 67 regional variant records, but it is not a copy-number caller and declares no SMN1/SMN2 CN. Expected CN fields were not configured in this run, so no formal expected-versus-observed concordance claim is made.",
    },
    {"id": "smn12_table_block", "type": "table", "tableId": "smn12_table"},
    {
        "id": "truvari_summary",
        "type": "markdown",
        "sourceId": "truvari_audit",
        "body": "## Truvari results and explicit gaps\n\nAll **15** audited benchmark or applicability lanes are terminal. Six publish accepted metrics, one is a successful duplicate-alias receipt, seven retain diagnostic gaps with no published metric, and one is correctly not applicable. Among the GIAB SV PASS-only DEL/INS >=50 results, Sniffles1/Iris has F1 **0.73537**, the hard-VCF SV projection **0.29644**, Jasmine companion **0.19249**, TIDDIT **0.17660**, and CNVscope **0.01432**. The separate alignment-branch comparison has directional F1 **0.85068**; it compares Winnowmap with Sentieon-minimap2 and is not truth accuracy. Jasmine final/full, LongReadSV, Sniffles2, and NICU Jasmine are accepted operationally as warning-only completion, but their projection-versus-comparison gaps mean their raw summaries remain non-authoritative. NA23687 NICU Truvari is correctly not applicable because the configured truth is HG002-only.",
    },
    {"id": "truvari_status_chart_block", "type": "chart", "chartId": "truvari_status_chart"},
    {"id": "truvari_table_block", "type": "table", "tableId": "truvari_table"},
    {
        "id": "package_summary",
        "type": "markdown",
        "sourceId": "package_summary",
        "body": "## Inflection analytical-package closure\n\nEach package uses schema `dayoa.hiomr2_inflection_analytical_package/1.3`, declares **37 artifacts**, includes NICU research outputs, and passed an all-files-present and declared-size verification. Declared artifact bytes are **22.45 GB** for HG002 and **22.11 GB** for NA23687. Both are correctly marked analytical and not customer-release eligible because no owner-issued customer delivery identity is asserted.",
    },
    {"id": "package_table_block", "type": "table", "tableId": "package_table"},
    {
        "id": "limitations",
        "type": "markdown",
        "sourceId": "truvari_audit",
        "body": "## Limitations and robustness\n\n- HG002 is the only sample with configured GIAB SNV/SV truth; NA23687 provides the SMN12-positive-control boundary, not a genome-wide truth benchmark.\n- `hard_snv` in the Truvari table is a DEL/INS >=50 projection from the hard-VCF file. It is distinct from the RTG SNV hard-VCF F-scores.\n- Raw metrics from record-count reconciliation failures are retained for diagnosis but deliberately not published as accepted benchmark values.\n- The Jasmine work is accepted as good enough for this workflow proof, but warning-only Truvari lanes are explicit coverage gaps rather than evidence of accuracy.\n- The package review treatments and SMN copy-number outputs are analytical evidence, not clinical interpretations.\n- A 7-day presigned MultiQC URL is an ephemeral credential-bearing URL, so it is delivered in a separate post-export share receipt rather than embedded in this durable artifact.",
    },
    {
        "id": "artifact_summary",
        "type": "markdown",
        "sourceId": "completion_artifacts",
        "body": "## Primary completion artifacts\n\nThe final MultiQC, machine-readable MultiQC data, benchmark summary, evidence manifest, and both package manifests have exact pre-export sizes and SHA-256 values. The export reconciliation should match these values before the FSx source is accepted as deleted.",
    },
    {"id": "artifact_table_block", "type": "table", "tableId": "artifact_table"},
    {
        "id": "delivery_summary",
        "type": "markdown",
        "sourceId": "s3_objects",
        "body": "## S3 delivery map\n\nThe full-root destination is `s3://lsmc-ssf-sequencing-data/derived/preval-hiomr2/take101/`. Stable S3 URIs for the report, final MultiQC, benchmark summary, evidence manifest, and both Inflection packages are listed below. The exact export uses delete-on-success semantics: FSx deletion is permitted only after the export task succeeds. S3 object/byte/hash reconciliation and the verified 7-day MultiQC share URL are recorded separately after upload.",
    },
    {"id": "s3_table_block", "type": "table", "tableId": "s3_table"},
    {
        "id": "methodology",
        "type": "markdown",
        "sourceId": "coverage_fragment",
        "body": "## Methodology\n\nCoverage and fragment values were extracted from the final MultiQC JSON using the AlignStats, Mosdepth, FastQC, and Samtools namespaces. Variant-treatment counts and package eligibility come directly from the two package manifests. GIAB hard-VCF scores are filtered to `ROI=giabHC` and `SNVCaller=sentdhiomr2`. The Truvari audit enumerates every terminal receipt plus the two copy-state rows, preserving published metrics separately from raw diagnostic summaries. Artifact sizes and hashes were recomputed on the headnode before report installation.",
    },
    {
        "id": "next_steps",
        "type": "markdown",
        "sourceId": "release_provenance",
        "body": "## Next steps\n\nAfter verified export and delete-on-success completion, Take222 will clone exact DayOA **13.4.2** and test HG003, HG004, NA19235, and NA20775 with full-coverage Illumina plus Bjuice ONT `[0,25)`. The exact literal eight-target closure will first run with `-j 444 -p -T 1 -k --rerun-triggers mtime -n`; only a clean preflight permits the identical live command with `-n` removed.",
    },
    {
        "id": "further_questions",
        "type": "markdown",
        "sourceId": "truvari_audit",
        "body": "## Further questions\n\n1. Which exact records account for the seven- and eight-record projection reconciliation gaps, and should those exclusions become explicit receipts?\n2. Should the CNVscope copy-state truth contract be replaced with a source whose PASS semantics project nonempty LOSS/GAIN events?\n3. Should the Sniffles1/Iris Sentieon alias be explicitly represented in the aggregate schema rather than only in its terminal receipt?\n4. At four-sample full coverage, do the variant-treatment shares and SMN12 copy-number confidence remain stable across HG003, HG004, NA19235, and NA20775?",
    },
]

artifact = {
    "surface": "report",
    "manifest": {
        "version": 1,
        "surface": "report",
        "title": "Take101 full-coverage HIOMR2 validation — DayOA 13.4.2",
        "generatedAt": generated_at,
        "blocks": blocks,
        "cards": [],
        "charts": charts,
        "tables": tables,
        "sources": sources,
    },
    "snapshot": {
        "version": 1,
        "status": "ready",
        "generatedAt": generated_at,
        "datasets": {
            "coverage_chart": coverage_chart,
            "coverage_fragment": coverage,
            "variant_treatment_combined": variant_treatment_combined,
            "variant_treatments": treatments,
            "workflow_repairs": repairs,
            "giab_hard_vcf": giab,
            "smn12_callers": smn12,
            "truvari_status_counts": truvari_status_counts,
            "truvari_audit": truvari,
            "package_summary": packages,
            "completion_artifacts": completion,
            "s3_uris": s3_uris,
            "release_provenance": release,
        },
    },
    "sources": sources,
}

OUTPUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
print(OUTPUT)
