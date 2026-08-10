#!/usr/bin/env python3
"""Generate the Bjuice20 Inflection deliverables report package."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PLANS = ROOT / "daylily-ephemeral-cluster" / "docs" / "plans"
DAYOA = ROOT / "daylily-omics-analysis"
TS = "20260720T123613Z"
ARTIFACT_DIR = (
    PLANS / f"{TS}_bjuice20_inflection_deliverables_artifacts"
)
REPORT = PLANS / f"{TS}_bjuice20_inflection_deliverables_report.md"
LEDGER = PLANS / f"{TS}_bjuice20_inflection_deliverables_ledger.md"
NA_SUPPORT = ARTIFACT_DIR / "na_truth_call_support.tsv"
NA_PREPACKAGE_INVENTORY = ARTIFACT_DIR / "na_prepackage_result_inventory.tsv"

MANIFEST_DIR = (
    PLANS
    / "20260719T133324Z_majors_bjuiceprevalanalysis_complete_artifacts"
    / "manifests"
)
RUNTIME_SUMMARY = (
    PLANS
    / "20260719T133324Z_majors_bjuiceprevalanalysis_complete_artifacts"
    / "runtime_hg003_ont_0_4"
    / "runtime_summary.json"
)
PACKAGE_AVAILABILITY = (
    PLANS
    / "20260720T011608Z_bjuice20_inflight_fsx_export"
    / "inflection_packages_available.md"
)
MANUAL_COPY = (
    PLANS
    / "20260720T011608Z_bjuice20_inflight_fsx_export"
    / "manual_copy_20260720T023359Z"
    / "manual_copy_completion.md"
)
EXPORT_YAML = (
    PLANS
    / "20260720T011608Z_bjuice20_inflight_fsx_export"
    / "fsx_export.yaml"
)
RUNBOOK = PLANS / "20260719T211558Z_inflection_package_export_runbook.md"
PROTOTYPE_CROSSWALK = (
    DAYOA
    / "docs"
    / "plans"
    / "20260717T000232Z_inflection_prototype_compatibility_crosswalk.md"
)
PRODUCER_LEDGER = (
    DAYOA
    / "docs"
    / "plans"
    / "20260719T205542Z_inflection_producer_source_merge_ledger.md"
)

S3_PREFIX = (
    "s3://lsmc-dayoa-analysis-results-usw2/validation/"
    "inflight_pr53_recovery_20260720T011608Z/"
    "ifx-p2-1000-120-0715/bjuiceprevalanalysis-complete/"
)

PRESENT_SAMPLES = {
    "HG001",
    "HG003",
    "HG004",
    "HG005",
    "HG006",
    "HG007",
    "NA05067",
    "NA10798",
    "NA13189",
    "NA14732",
    "NA14733",
    "NA15603",
    "NA15848",
    "NA15849",
    "NA19235",
    "NA20027",
    "NA20230",
    "NA20775",
}

MISSING_REASONS = {
    "HG002": (
        "No package manifest in the in-flight snapshot; package validation rejected "
        "invalid fallback ALT allele GGCGCAGGCGCAGAG. at chr1:10621 after "
        "LongReadSV phenotype handling and SR fallback completed."
    ),
    "NA23687": (
        "No package manifest in the in-flight snapshot; HIOMRS core job 6712 was "
        "still running and terminal gVCF/VCF plus package manifest were absent at "
        "snapshot start."
    ),
}

SEGDUP_VCF_GENES = [
    "CFH",
    "CYP11B1",
    "CYP2B6",
    "CYP2D6",
    "GBA1",
    "HBA",
    "NCF1",
    "PMS2",
    "RCCX1",
    "RHD",
    "SBDS",
    "SMN1",
    "STRC",
]

PACKAGE_ROLES = [
    ("evidence_qc", "expected_artifacts_tsv", "evidence/expected_artifacts.tsv"),
    ("evidence_qc", "expected_artifacts_json", "evidence/expected_artifacts.json"),
    ("small_variants", "snv_indel_vcf", "variants/snv/*.vcf.gz"),
    ("small_variants", "snv_indel_vcf_index", "variants/snv/*.vcf.gz.tbi"),
    ("cnv", "cnv_vcf", "variants/cnv/*.vcf.gz"),
    ("cnv", "cnv_vcf_index", "variants/cnv/*.vcf.gz.tbi"),
    ("sv", "hiomrs_sv_vcf", "variants/sv/hiomrs/*.vcf.gz"),
    ("sv", "hiomrs_sv_vcf_index", "variants/sv/hiomrs/*.vcf.gz.tbi"),
    ("sv", "hiomrs_sv_provenance", "variants/sv/hiomrs/*.provenance.json"),
    ("sv", "tiddit_sv_vcf", "variants/sv/tiddit/*.vcf.gz"),
    ("sv", "tiddit_sv_vcf_index", "variants/sv/tiddit/*.vcf.gz.tbi"),
    ("mitochondrial", "mitochondrial_vcf", "variants/mitochondrial/*.vcf.gz"),
    ("mitochondrial", "mitochondrial_vcf_index", "variants/mitochondrial/*.vcf.gz.tbi"),
    ("repeat_expansion", "expansionhunter_vcf", "variants/repeat_expansion/*.vcf.gz"),
    ("repeat_expansion", "expansionhunter_json", "variants/repeat_expansion/*.json"),
    ("repeat_expansion", "expansionhunter_report", "variants/repeat_expansion/*.tsv"),
    ("segdup", "segdup_summary", "variants/segdup/*summary*"),
    ("segdup", "segdup_merged_vcf", "variants/segdup/*merged*.vcf.gz"),
    ("segdup", "segdup_merged_vcf_index", "variants/segdup/*merged*.vcf.gz.tbi"),
    ("segdup", "segdup_gene_IKBKG", "variants/segdup/IKBKG/*.json"),
]

for gene in SEGDUP_VCF_GENES:
    PACKAGE_ROLES.append(("segdup", f"segdup_gene_{gene}", f"variants/segdup/{gene}/*.vcf.gz"))
    PACKAGE_ROLES.append(
        ("segdup", f"segdup_gene_{gene}_index", f"variants/segdup/{gene}/*.vcf.gz.tbi")
    )

PACKAGE_ROLES.extend(
    [
        ("smn", "sentieon_smn1_vcf", "smn/sentieon_smn1*.vcf.gz"),
        ("smn", "sentieon_smn1_vcf_index", "smn/sentieon_smn1*.vcf.gz.tbi"),
        ("smn", "sentieon_smn_summary", "smn/sentieon*.summary*"),
        ("smn", "smncopynumbercaller_summary", "smn/smncopynumbercaller*"),
        ("smn", "smn_concordance_json", "smn/smn_concordance.json"),
        ("smn", "smn_concordance_tsv", "smn/smn_concordance.tsv"),
        ("alignment", "short_read_cram", "alignments/short_read/*.cram"),
        ("alignment", "short_read_cram_index", "alignments/short_read/*.cram.crai"),
        ("evidence_qc", "package_metrics", "qc/package_metrics.json"),
        ("evidence_qc", "package_compliance", "qc/package_compliance.json"),
        ("evidence_qc", "artifact_failure_evidence", "evidence/artifact_failures.json"),
    ]
)

EXPECTED_ARTIFACT_ROLES = [
    "cnv_vcf",
    "expansionhunter",
    "mitochondrial_vcf",
    "segdup",
    "sentieon_longreadsv_vcf",
    "short_read_cram",
    "smn",
    "snv_indel_vcf",
    "tiddit_sv_vcf",
]

CORIELL = {
    "NA05067": {
        "expected": "Trisomy 9 / chromosome 9 abnormality, karyotype 47,XY,+9,del(9)(q11)[20]",
        "assay": "CNV / large-event chromosome 9 dosage",
        "status": "not assessed locally; package present but call evidence not locally refreshed",
        "source": "https://catalog.coriell.org/0/Sections/Search/Sample_Detail.aspx?Product=DNA&Ref=NA05067",
    },
    "NA10798": {
        "expected": "Alpha-thalassemia Filipino deletion, --FIL/alpha alpha",
        "assay": "HBA / segdup deletion",
        "status": "not assessed locally; package present but call evidence not locally refreshed",
        "source": "https://catalog.coriell.org/0/Sections/Search/Sample_Detail.aspx?Product=DNA&Ref=NA10798",
    },
    "NA13189": {
        "expected": "Huntington disease HTT CAG expansion; same subject as GM04856; public table reports larger allele 50 CAG",
        "assay": "HTT repeat expansion",
        "status": "not assessed locally; package present but call evidence not locally refreshed",
        "source": "https://catalog.coriell.org/0/Sections/Search/Sample_Detail.aspx?Product=CC&Ref=GM04856 ; https://pmc.ncbi.nlm.nih.gov/articles/PMC5507316/",
    },
    "NA14732": {
        "expected": "Heterozygous full deletion of CYP21A2",
        "assay": "CYP21A2 / segdup deletion",
        "status": "not assessed locally; package present but call evidence not locally refreshed",
        "source": "https://catalog.coriell.org/0/Sections/Search/Sample_Detail.aspx?Product=DNA&Ref=NA14732",
    },
    "NA14733": {
        "expected": "Heterozygous approximately 30 kb CYP21A2 deletion",
        "assay": "CYP21A2 / segdup deletion",
        "status": "not assessed locally; package present but call evidence not locally refreshed",
        "source": "https://catalog.coriell.org/0/Sections/Search/Sample_Detail.aspx?Ref=NA14733&product=DNA",
    },
    "NA15603": {
        "expected": "Uniparental isodisomy chromosome 8",
        "assay": "copy-neutral UPD / ROH",
        "status": "outside ordinary package-call scope unless ROH/UPD evidence exists",
        "source": "https://catalog.coriell.org/0/Sections/Search/Sample_Detail.aspx?Ref=NA15603&product=DNA",
    },
    "NA15848": {
        "expected": "FXN GAA expansion, one allele about 830 repeats",
        "assay": "FXN repeat expansion",
        "status": "not assessed locally; package present but call evidence not locally refreshed",
        "source": "https://www.coriell.org/0/sections/Search/Sample_Detail.aspx?Ref=NA15848&product=DNA",
    },
    "NA15849": {
        "expected": "FXN GAA expansion, one allele about 920 repeats",
        "assay": "FXN repeat expansion",
        "status": "not assessed locally; package present but call evidence not locally refreshed",
        "source": "https://catalog.coriell.org/0/Sections/Search/Sample_Detail.aspx?Ref=NA15849&product=DNA",
    },
    "NA19235": {
        "expected": "No public non-SMN disease variant found; SMN1/SMN2 expected 4/0 in public MLPA product docs",
        "assay": "SMN copy number only",
        "status": "no public non-SMN truth found; SMN call evidence not locally refreshed",
        "source": "https://catalog.coriell.org/0/Sections/Search/Sample_Detail.aspx?Product=DNA&Ref=NA19235 ; https://storage.mtender.gov.md/get/5cad7445-e224-4f73-b22a-9a1198e79b9f-1707303684385",
    },
    "NA20027": {
        "expected": "Turner syndrome, 45,X[20]",
        "assay": "sex-chromosome aneuploidy / X monosomy",
        "status": "not assessed locally; package present but call evidence not locally refreshed",
        "source": "https://catalog.coriell.org/0/Sections/Search/Sample_Detail.aspx?Product=DNA&Ref=NA20027",
    },
    "NA20230": {
        "expected": "FMR1 CGG repeat size 53",
        "assay": "FMR1 repeat expansion / intermediate allele",
        "status": "not assessed locally; package present but call evidence not locally refreshed",
        "source": "https://catalog.coriell.org/0/Sections/Search/Sample_Detail.aspx?Ref=NA20230&product=DNA",
    },
    "NA20775": {
        "expected": "No public non-SMN disease variant found; SMN1/SMN2 expected 3/1 in public MLPA product docs",
        "assay": "SMN copy number only",
        "status": "no public non-SMN truth found; SMN call evidence not locally refreshed",
        "source": "https://catalog.coriell.org/0/Sections/Search/Sample_Detail.aspx?Product=DNA&Ref=NA20775 ; https://storage.mtender.gov.md/get/5cad7445-e224-4f73-b22a-9a1198e79b9f-1707303684385",
    },
    "NA23687": {
        "expected": "SMA carrier, SMN1/SMN2 expected 1/2",
        "assay": "SMN copy number",
        "status": "not produced in snapshot; package manifest absent",
        "source": "https://catalog.coriell.org/0/Sections/Search/Sample_Detail.aspx?Product=DNA&Ref=NA23687",
    },
}


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fields, delimiter="\t")
        writer.writeheader()
        for row in rows:
            out = {field: row.get(field, "") for field in fields}
            if out[fields[-1]] == "":
                out[fields[-1]] = "not_applicable"
            writer.writerow(out)


def package_id(sample: str) -> str:
    return (
        f"{sample}-{sample}-{sample}-ILMN-LIB-{sample}-ONT-LIB-"
        f"BJUICE-PREVAL-{sample}-HIOMRS-A1"
    )


def na_support_status_by_sample() -> dict[str, str]:
    if not NA_SUPPORT.exists():
        return {}
    rows = read_tsv(NA_SUPPORT)
    return {
        row["sample"]: f"{row['support_status']}: {row['interpretation']}"
        for row in rows
    }


def link(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    samples = read_tsv(MANIFEST_DIR / "samples.tsv")
    libraries = read_tsv(MANIFEST_DIR / "libraries.tsv")
    analysis_units = read_tsv(MANIFEST_DIR / "analysis_units.tsv")
    sample_order = [row["SAMPLEID"] for row in samples]
    lib_by_sample: dict[str, list[dict[str, str]]] = {sample: [] for sample in sample_order}
    for row in libraries:
        lib_by_sample.setdefault(row["SAMPLEID"], []).append(row)
    au_by_sample = {row["SAMPLEID"]: row for row in analysis_units}

    inventory_rows: list[dict[str, object]] = []
    for sample in sample_order:
        libs = sorted(lib_by_sample.get(sample, []), key=lambda row: row["LIBRARY_ID"])
        sr_libs = [row for row in libs if "ILMN" in row["LIBRARY_ID"]]
        lr_libs = [row for row in libs if "ONT" in row["LIBRARY_ID"]]
        present = sample in PRESENT_SAMPLES
        inventory_rows.append(
            {
                "sample": sample,
                "sample_euid": next(row["SAMPLE_EUID"] for row in samples if row["SAMPLEID"] == sample),
                "analysis_unit_uid": au_by_sample[sample]["ANALYSIS_UNIT_UID"],
                "package_id": package_id(sample),
                "ilmn_library": sr_libs[0]["LIBRARY_ID"] if sr_libs else "",
                "ont_library": lr_libs[0]["LIBRARY_ID"] if lr_libs else "",
                "package_manifest_status": "present" if present else "missing",
                "package_state": "READY" if present else "not_produced",
                "artifact_failures": 0 if present else "",
                "expected_package_artifact_roles": len(PACKAGE_ROLES),
                "expected_core_artifact_roles": len(EXPECTED_ARTIFACT_ROLES),
                "missing_reason": "" if present else MISSING_REASONS.get(sample, ""),
                "package_prefix": f"{S3_PREFIX}results/day/hg38/deliveries/inflection/*/{package_id(sample)}/",
            }
        )

    package_inventory_fields = [
        "sample",
        "sample_euid",
        "analysis_unit_uid",
        "package_id",
        "ilmn_library",
        "ont_library",
        "package_manifest_status",
        "package_state",
        "artifact_failures",
        "expected_package_artifact_roles",
        "expected_core_artifact_roles",
        "missing_reason",
        "package_prefix",
    ]
    write_tsv(ARTIFACT_DIR / "package_inventory.tsv", inventory_rows, package_inventory_fields)

    matrix_rows: list[dict[str, object]] = []
    for row in inventory_rows:
        sample = str(row["sample"])
        for group, role, relative_path in PACKAGE_ROLES:
            present = sample in PRESENT_SAMPLES
            matrix_rows.append(
                {
                    "sample": sample,
                    "package_id": row["package_id"],
                    "artifact_group": group,
                    "artifact_role": role,
                    "expected_relative_path_pattern": relative_path,
                    "expected": "yes",
                    "observed_status": "present_in_ready_manifest" if present else "missing_package",
                    "evidence_basis": (
                        "package availability receipt says package_state READY and zero artifact failures"
                        if present
                        else MISSING_REASONS.get(sample, "")
                    ),
                }
            )
    write_tsv(
        ARTIFACT_DIR / "expected_files_matrix.tsv",
        matrix_rows,
        [
            "sample",
            "package_id",
            "artifact_group",
            "artifact_role",
            "expected_relative_path_pattern",
            "expected",
            "observed_status",
            "evidence_basis",
        ],
    )

    role_rows = [
        {"artifact_group": group, "artifact_role": role, "relative_path_pattern": rel}
        for group, role, rel in PACKAGE_ROLES
    ]
    write_tsv(
        ARTIFACT_DIR / "package_role_catalog.tsv",
        role_rows,
        ["artifact_group", "artifact_role", "relative_path_pattern"],
    )
    write_tsv(
        ARTIFACT_DIR / "expected_artifact_role_catalog.tsv",
        [{"artifact_role": role} for role in EXPECTED_ARTIFACT_ROLES],
        ["artifact_role"],
    )

    coriell_rows = []
    for sample in sample_order:
        if sample.startswith("NA"):
            entry = CORIELL[sample]
            coriell_rows.append(
                {
                    "sample": sample,
                    "expected_positive": entry["expected"],
                    "assay_area": entry["assay"],
                    "call_status": entry["status"],
                    "source_url": entry["source"],
                }
            )
    na_status_by_sample = na_support_status_by_sample()
    for row in coriell_rows:
        if row["sample"] in na_status_by_sample:
            row["call_status"] = na_status_by_sample[row["sample"]]
    write_tsv(
        ARTIFACT_DIR / "coriell_expected_positives.tsv",
        coriell_rows,
        ["sample", "expected_positive", "assay_area", "call_status", "source_url"],
    )

    truth_rows: list[dict[str, object]] = []
    for row in samples:
        sample = row["SAMPLEID"]
        if row["TRUTH_DATA_DIR"] != "na":
            truth_rows.append(
                {
                    "sample": sample,
                    "truth_type": "GIAB SNV truth",
                    "expected_truth_source": row["TRUTH_DATA_DIR"],
                    "package_status": "present" if sample in PRESENT_SAMPLES else "missing_package",
                    "call_status": (
                        "truth comparison requested; F-score not locally extracted without S3 package/concordance refresh"
                        if sample in PRESENT_SAMPLES
                        else "not produced in snapshot"
                    ),
                    "fscore": "",
                }
            )
        elif sample.startswith("NA"):
            truth_rows.append(
                {
                    "sample": sample,
                    "truth_type": "Coriell expected positive",
                    "expected_truth_source": CORIELL[sample]["source"],
                    "package_status": "present" if sample in PRESENT_SAMPLES else "missing_package",
                    "call_status": CORIELL[sample]["status"],
                    "fscore": "",
                }
            )
    for row in truth_rows:
        if row["sample"] in na_status_by_sample and row["truth_type"] == "Coriell expected positive":
            row["call_status"] = na_status_by_sample[row["sample"]]
    write_tsv(
        ARTIFACT_DIR / "truth_fscore_status.tsv",
        truth_rows,
        ["sample", "truth_type", "expected_truth_source", "package_status", "call_status", "fscore"],
    )

    runtime_payload = json.loads(RUNTIME_SUMMARY.read_text(encoding="utf-8"))
    runtime_counts = runtime_payload["counts"]
    ont_window = runtime_payload["ont_hour_window"]
    runtime_rows = [
        {
            "sample": "HG003",
            "runtime_scope": "local checked-in subset summary",
            "analysis_units": runtime_counts["analysis_units"],
            "specimens": runtime_counts["specimens"],
            "samples": runtime_counts["samples"],
            "libraries": runtime_counts["libraries"],
            "sequencing_inputs": runtime_counts["sequencing_inputs"],
            "ont_hour_window": (
                f"{ont_window['interval']}:{ont_window['start']}-{ont_window['end']}"
            ),
            "subsample_pct": runtime_payload["analysis_downsampling"]["SUBSAMPLE_PCT"],
            "wall_runtime": "not recorded in this JSON",
            "best_case_runtime": "not computable from local checked-in benchmark evidence",
            "evidence": link(RUNTIME_SUMMARY),
        }
    ]
    for row in inventory_rows:
        sample = str(row["sample"])
        runtime_rows.append(
            {
                "sample": sample,
                "runtime_scope": "bjuice20 package snapshot",
                "analysis_units": 1,
                "specimens": 1,
                "samples": 1,
                "libraries": 2,
                "sequencing_inputs": 4,
                "ont_hour_window": "",
                "subsample_pct": "",
                "wall_runtime": "not locally available; terminal controller evidence absent from snapshot package",
                "best_case_runtime": "not locally available; per-AU benchmark TSVs require S3/FSx refresh",
                "evidence": link(PACKAGE_AVAILABILITY),
            }
        )
    write_tsv(
        ARTIFACT_DIR / "runtime_summary.tsv",
        runtime_rows,
        [
            "sample",
            "runtime_scope",
            "analysis_units",
            "specimens",
            "samples",
            "libraries",
            "sequencing_inputs",
            "ont_hour_window",
            "subsample_pct",
            "wall_runtime",
            "best_case_runtime",
            "evidence",
        ],
    )

    gap_rows = [
        {
            "area": "Package identity and source lineage",
            "classification": "verified/no gap",
            "evidence": "Prototype regex/discovery identity was replaced by explicit six-manifest identity and package IDs.",
            "source": link(PROTOTYPE_CROSSWALK),
        },
        {
            "area": "Core expected-artifact declaration",
            "classification": "verified/no gap",
            "evidence": "Source declares nine required expected-artifact roles and package rule consumes exact workflow inputs.",
            "source": "daylily-omics-analysis/daylily_omics_analysis/expected_artifacts.py",
        },
        {
            "area": "Package artifact expansion",
            "classification": "verified/no gap",
            "evidence": "Package runbook describes 57 artifact rows per package; source/test evidence covers QC, indexes, SegDup genes, SMN, CRAM/CRAI, and package compliance roles.",
            "source": link(RUNBOOK),
        },
        {
            "area": "Produced bjuice20 packages",
            "classification": "execution/data gap",
            "evidence": "18 of 20 package manifests were present and READY; HG002 and NA23687 were not available in the snapshot.",
            "source": link(PACKAGE_AVAILABILITY),
        },
        {
            "area": "Terminal Inflection delivery set",
            "classification": "terminal-delivery gap",
            "evidence": "Final MultiQC, MultiQC data, evidence manifest, and delivery-set manifest were absent at snapshot start.",
            "source": link(PACKAGE_AVAILABILITY),
        },
        {
            "area": "FSx to S3 export",
            "classification": "packaging/export gap repaired",
            "evidence": "Initial export missed 36 hardlinked CRAM/CRAI package objects; manual repair copied and validated all 36 with zero failures.",
            "source": link(MANUAL_COPY),
        },
        {
            "area": "Live S3 raw/package call refresh for this report",
            "classification": "partial evidence refresh",
            "evidence": "Default credentials were unavailable during the original build, but the NA call-support refresh used explicit --profile lsmc S3 access for bounded raw pre-package result files, delivered package call files, and the supplemental successful pre-export raw SMN12 evidence. Runtime, GIAB F-scores, and terminal delivery artifacts remain unrefreshed.",
            "source": "daylily-ephemeral-cluster/docs/plans/20260720T123613Z_bjuice20_inflection_deliverables_artifacts/na_truth_call_support.tsv",
        },
    ]
    write_tsv(ARTIFACT_DIR / "gap_analysis.tsv", gap_rows, ["area", "classification", "evidence", "source"])

    summary = {
        "timestamp": TS,
        "expected_samples": len(sample_order),
        "expected_libraries": len(libraries),
        "expected_sequencing_inputs": len(read_tsv(MANIFEST_DIR / "sequencing_inputs.tsv")),
        "expected_analysis_units": len(analysis_units),
        "present_packages": len(PRESENT_SAMPLES),
        "missing_packages": sorted(MISSING_REASONS),
        "package_roles_per_ready_package": len(PACKAGE_ROLES),
        "core_expected_artifact_roles": len(EXPECTED_ARTIFACT_ROLES),
        "primary_s3_prefix": S3_PREFIX,
        "live_s3_refresh": "explicit --profile lsmc refresh performed for bounded NA raw pre-package and package call-support artifacts",
    }
    if NA_SUPPORT.exists():
        na_support_rows = read_tsv(NA_SUPPORT)
        summary["na_call_support_rows"] = len(na_support_rows)
        counts: dict[str, int] = {}
        for row in na_support_rows:
            counts[row["support_status"]] = counts.get(row["support_status"], 0) + 1
        summary["na_call_support_status_counts"] = dict(sorted(counts.items()))
    if NA_PREPACKAGE_INVENTORY.exists():
        summary["na_prepackage_inventory_rows"] = len(read_tsv(NA_PREPACKAGE_INVENTORY))
        summary["na_supplemental_pre_export_boundary"] = (
            "s3://lsmc-dayoa-analysis-results-usw2/validation/"
            "pre_13.0.11_8_g1d44044_20260719T214703Z/"
            "ifx-p2-1000-120-0715/bjuiceprevalanalysis-complete/"
            "daylily-omics-analysis/results/day/hg38"
        )
    (ARTIFACT_DIR / "report_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    write_report(inventory_rows, coriell_rows, gap_rows, summary)
    write_ledger()
    return 0


def markdown_table(rows: list[dict[str, object]], fields: list[str], max_rows: int | None = None) -> str:
    selected = rows if max_rows is None else rows[:max_rows]
    lines = [
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    for row in selected:
        values = []
        for field in fields:
            value = str(row.get(field, ""))
            value = value.replace("|", "\\|").replace("\n", " ")
            values.append(value)
        lines.append("| " + " | ".join(values) + " |")
    if max_rows is not None and len(rows) > max_rows:
        lines.append(
            f"| ... | ... | ... | ... | ... | ... | ... | ... |"
        )
    return "\n".join(lines)


def write_report(
    inventory_rows: list[dict[str, object]],
    coriell_rows: list[dict[str, object]],
    gap_rows: list[dict[str, object]],
    summary: dict[str, object],
) -> None:
    na_support_rows = read_tsv(NA_SUPPORT) if NA_SUPPORT.exists() else []
    status_mmd = """stateDiagram-v2
    [*] --> Expected20
    Expected20 --> Ready18: package_manifest present / READY / zero failures
    Expected20 --> MissingHG002: invalid fallback ALT at chr1:10621
    Expected20 --> MissingNA23687: core HIOMRS job 6712 still running
    Ready18 --> PackageOnly: delivery_profile local
    PackageOnly --> NotCustomerDelivery: terminal delivery set absent
"""
    flow_mmd = """flowchart LR
    M[Six checked-in manifests] --> AU[20 analysis units]
    AU --> E[build_inflection_expected_artifacts\\n9 required roles]
    E --> P[package_inflection_library\\n57 package roles]
    P --> R[18 READY package manifests]
    P --> G[2 missing packages]
    R --> X[FSx export]
    X --> H[36 CRAM/CRAI hardlink objects repaired]
    R --> T[Terminal delivery set absent]
"""
    gap_mmd = """flowchart TB
    Proto[Prototype check_compliance.py\\n38 executable assertions] --> Crosswalk[Compatibility crosswalk]
    Crosswalk --> Source[inflection.delivery.v1 source]
    Source --> Package[Package role catalog]
    Package --> Produced[18 READY packages]
    Produced --> Gaps[Execution and terminal-delivery gaps]
    Source --> Verified[Identity, lineage, validation, no-discovery contracts]
"""
    (ARTIFACT_DIR / "package_status_state.mmd").write_text(status_mmd, encoding="utf-8")
    (ARTIFACT_DIR / "manifest_to_package_flow.mmd").write_text(flow_mmd, encoding="utf-8")
    (ARTIFACT_DIR / "gap_analysis_flow.mmd").write_text(gap_mmd, encoding="utf-8")

    missing = [row for row in inventory_rows if row["package_manifest_status"] == "missing"]
    group_counts: dict[str, int] = {}
    for group, _role, _rel in PACKAGE_ROLES:
        group_counts[group] = group_counts.get(group, 0) + 1
    group_rows = [
        {"artifact_group": group, "roles_per_package": count}
        for group, count in sorted(group_counts.items())
    ]
    na_flow_mmd = """flowchart LR
    Expected["13 NA expected positives"] --> Package["Inflection package snapshot"]
    Package --> Raw["Raw pre-package result tree"]
    Raw --> Direct["Direct support: HBA, HTT, CYP21A2/RCCX1, SMN, FMR1"]
    Raw --> Qual["Qualitative support: FXN pathogenic-range expansion, size discordant"]
    Raw --> Partial["Partial support: chr9 goleft/TIDDIT, no trisomy CNV"]
    Raw --> Turner["Turner support: sex-complement X call"]
    Raw --> Gap["No direct support: UPD8"]
    Raw --> Supplemental["Supplemental pre-export SMN12 supports NA23687; not delivered"]
"""
    if na_support_rows:
        (ARTIFACT_DIR / "na_truth_call_support_flow.mmd").write_text(
            na_flow_mmd,
            encoding="utf-8",
        )
    report = f"""# Bjuice20 Inflection Deliverables Technical Report

Generated: `{TS}`

## Technical Summary

The Bjuice20 manifest universe defines **20 samples, 40 libraries, 80 sequencing inputs, and 20 HIOMRS analysis units**. The checked-in in-flight export receipt reports **18 per-analysis-unit Inflection packages present**, every listed package at `package_state=READY` with zero artifact failures. Two packages were not produced in the snapshot: `HG002` and `NA23687`.

This report treats `{S3_PREFIX}` as the primary package evidence boundary. The original local build could not refresh S3 through the default credential chain, but the NA call-support refresh used explicit `--profile lsmc --region us-west-2` access for bounded raw pre-package result files and delivered package call artifacts. Package presence, missing-package reasons, terminal-artifact absence, and export repair status still come from checked-in receipts. The NA call-support section now separates raw result evidence, delivered package evidence, and the supplemental successful pre-export raw SMN12 evidence used for `NA23687`.

The report does **not** claim customer-delivery readiness. The in-flight receipt explicitly says the delivery profile is `local`, package-only analytical artifacts were available, and final MultiQC/evidence/delivery-set artifacts were absent at snapshot start.

## Package Status

```mermaid
{status_mmd.rstrip()}
```

{markdown_table(inventory_rows, ["sample", "analysis_unit_uid", "package_manifest_status", "package_state", "expected_package_artifact_roles", "missing_reason"], max_rows=None)}

## Expected Inflection Files Per Library

Each produced package is expected to carry **{len(PACKAGE_ROLES)} package artifact roles**. The source-level expected-artifact manifest declares **{len(EXPECTED_ARTIFACT_ROLES)} required analytical roles**, and `package_inflection_library` expands those into indexes, QC, package metrics, SegDup gene outputs, SMN evidence, short-read CRAM/CRAI, and package-compliance artifacts.

The full per-sample by per-role matrix is in `{link(ARTIFACT_DIR / "expected_files_matrix.tsv")}`. For the 18 ready packages, the observed status in that matrix is `present_in_ready_manifest` because the checked-in package-availability receipt states each listed package was `READY` with zero failures. For `HG002` and `NA23687`, every expected role is marked `missing_package`.

{markdown_table(group_rows, ["artifact_group", "roles_per_package"], max_rows=None)}

```mermaid
{flow_mmd.rstrip()}
```

## Missing Data And Runtime

`HG002` was blocked after LongReadSV phenotype handling and the separate short-read fallback path completed, because package validation rejected an invalid fallback ALT allele (`GGCGCAGGCGCAGAG.` at `chr1:10621`). `NA23687` was not terminal at snapshot start: HIOMRS core job `6712` was still running, and the terminal gVCF/VCF plus package manifest were absent.

Terminal delivery artifacts were absent at snapshot start:

- `DAY_final_multiqc.html`
- `DAY_final_multiqc_data/multiqc_data.json`
- `dayoa_evidence_manifest.json`
- `INFLECTION_delivery_set/delivery_set_manifest.json`

Runtime evidence is incomplete for the all-20 snapshot in this local checkout. The checked-in HG003 subset summary exists, but terminal controller timing and per-AU benchmark TSVs for the package snapshot were not refreshed as part of the NA raw/package call-support pass. The runtime table therefore records the evidence gap rather than computing unsupported wall or best-case values. See `{link(ARTIFACT_DIR / "runtime_summary.tsv")}`.

## Truth And Coriell Expected Positives

The seven HG samples have GIAB truth/control paths in `samples.tsv`; package-level F-scores were not extracted in this local run because concordance package files were not locally refreshed from S3. For the NA/Coriell samples, the expected-positive matrix below records public truth expectations and the local call-status boundary.

{markdown_table(coriell_rows, ["sample", "expected_positive", "assay_area", "call_status", "source_url"], max_rows=None)}

The machine-readable truth table is `{link(ARTIFACT_DIR / "truth_fscore_status.tsv")}`.

## Gap Analysis Against The Original Functionality

```mermaid
{gap_mmd.rstrip()}
```

{markdown_table(gap_rows, ["area", "classification", "evidence", "source"], max_rows=None)}

The important distinction is that source capability and package construction are mostly verified by the checked-in DayOA source, tests, and crosswalk. The remaining gaps are execution/data availability (`HG002`, `NA23687` as delivered packages), terminal delivery artifacts, runtime/GIAB F-score extraction, and package-manifest refresh beyond the bounded NA raw/package call-support evidence.

## Methods And Sources

Inputs reviewed:

- `{link(MANIFEST_DIR / "samples.tsv")}`, `{link(MANIFEST_DIR / "libraries.tsv")}`, `{link(MANIFEST_DIR / "analysis_units.tsv")}`, and sibling manifest TSVs.
- `{link(PACKAGE_AVAILABILITY)}`.
- `{link(MANUAL_COPY)}`.
- `{link(RUNBOOK)}`.
- `{link(PROTOTYPE_CROSSWALK)}`.
- `{link(PRODUCER_LEDGER)}`.
- `daylily-omics-analysis/daylily_omics_analysis/expected_artifacts.py`.
- `daylily-omics-analysis/workflow/rules/inflection_delivery.smk`.
- Bounded S3 raw pre-package result files and package call artifacts under the `inflight_pr53_recovery_20260720T011608Z` snapshot, read with `--profile lsmc --region us-west-2` for the NA call-support refresh.
- Supplemental raw SMN12 evidence under `s3://lsmc-dayoa-analysis-results-usw2/validation/pre_13.0.11_8_g1d44044_20260719T214703Z/ifx-p2-1000-120-0715/bjuiceprevalanalysis-complete/daylily-omics-analysis/results/day/hg38`, used only to record `NA23687` biological call support while preserving its missing delivered-package status.

Generated artifacts:

- `{link(ARTIFACT_DIR / "package_inventory.tsv")}`
- `{link(ARTIFACT_DIR / "expected_files_matrix.tsv")}`
- `{link(ARTIFACT_DIR / "package_role_catalog.tsv")}`
- `{link(ARTIFACT_DIR / "expected_artifact_role_catalog.tsv")}`
- `{link(ARTIFACT_DIR / "coriell_expected_positives.tsv")}`
- `{link(ARTIFACT_DIR / "truth_fscore_status.tsv")}`
- `{link(ARTIFACT_DIR / "runtime_summary.tsv")}`
- `{link(ARTIFACT_DIR / "gap_analysis.tsv")}`
- `{link(ARTIFACT_DIR / "na_truth_call_support.tsv")}`
- `{link(ARTIFACT_DIR / "na_truth_call_evidence.json")}`
- `{link(ARTIFACT_DIR / "na_prepackage_result_inventory.tsv")}`
- `{link(ARTIFACT_DIR / "na_truth_call_support_flow.mmd")}`
- `{link(ARTIFACT_DIR / "investigate_na_truth_calls.py")}`
- `{link(ARTIFACT_DIR / "report_summary.json")}`
- `{link(ARTIFACT_DIR / "package_status_state.mmd")}`
- `{link(ARTIFACT_DIR / "manifest_to_package_flow.mmd")}`
- `{link(ARTIFACT_DIR / "gap_analysis_flow.mmd")}`

## Recommended Next Steps

1. Re-run the package-manifest, benchmark, and GIAB concordance extraction from S3 or FSx when terminal evidence is available.
2. Refresh this report with actual per-AU benchmark totals, wall-clock controller timing, and GIAB F-scores.
3. Run a terminal export after controller `rc=0` and final MultiQC/evidence/delivery-set artifacts exist, then add a dated terminal-delivery section rather than overwriting the in-flight snapshot truth.
"""
    if na_support_rows:
        na_report_rows = [
            {
                "sample": row["sample"],
                "support_status": row["support_status"],
                "supporting_call_evidence": row["observed_call_summary"],
                "interpretation": row["interpretation"],
            }
            for row in na_support_rows
        ]
        na_section = f"""## Truth And Coriell Expected Positives

The seven HG samples have GIAB truth/control paths in `samples.tsv`; package-level GIAB F-scores were not extracted in this refresh. For the 13 NA/Coriell samples, a bounded S3 call-support refresh inspected raw pre-package ExpansionHunter, SegDup YAML/VCF, SMN12, CNV, SV, goleft indexcov, sex-complement, and Peddy evidence where available; delivered package files were retained as cross-checks. The successful 2026-07-19 pre-export raw SMN12 file is used as supplemental `NA23687` call support, while the repaired in-flight package snapshot still records `NA23687` as not delivered.

Full call-support evidence is in `{link(ARTIFACT_DIR / "na_truth_call_support.tsv")}` and `{link(ARTIFACT_DIR / "na_truth_call_evidence.json")}`. Raw-result availability is summarized in `{link(ARTIFACT_DIR / "na_prepackage_result_inventory.tsv")}`. Public expected-positive source URLs remain in `{link(ARTIFACT_DIR / "coriell_expected_positives.tsv")}`.

```mermaid
{na_flow_mmd.rstrip()}
```

{markdown_table(na_report_rows, ["sample", "support_status", "supporting_call_evidence", "interpretation"], max_rows=None)}

The machine-readable GIAB/Coriell truth-status table is `{link(ARTIFACT_DIR / "truth_fscore_status.tsv")}`.

"""
        start = report.index("## Truth And Coriell Expected Positives")
        end = report.index("## Gap Analysis Against The Original Functionality")
        report = report[:start] + na_section + report[end:]
    REPORT.write_text(report, encoding="utf-8")


def write_ledger() -> None:
    rows = [
        ("A1", "Orchestrator", "SUCCESS", "Created report package and bounded evidence scope."),
        ("A2", "Source Inventory", "SUCCESS", "Generated 20-sample package inventory from checked-in manifests."),
        ("A3", "Package Inventory", "PARTIAL", "Package presence still uses checked-in package availability receipt; later explicit `--profile lsmc` S3 refresh inspected bounded NA raw/package call artifacts only."),
        ("A4", "Expected Matrix", "SUCCESS", "Generated 1,140-row expected-files matrix from 20 samples x 57 package roles."),
        ("A5", "Missing Data", "SUCCESS", "Recorded HG002, NA23687, terminal artifacts, and CRAM/CRAI repair boundaries."),
        ("A6", "Runtime", "PARTIAL", "Recorded HG003 local subset evidence and all-20 benchmark/controller evidence gap."),
        ("A7", "Truth/F-score", "PARTIAL", "Recorded GIAB/Coriell truth sources; refreshed NA expected-positive call support from S3 raw pre-package and package artifacts; GIAB F-scores remain unextracted."),
        ("A8", "Coriell Research", "SUCCESS", "Added public expected-positive matrix with source URLs."),
        ("A9", "Gap Analysis", "SUCCESS", "Compared source/crosswalk/runbook/package receipts and classified gaps."),
        ("A10", "QA/Report", "SUCCESS", "Generated report, ledger, TSV/JSON artifacts, Mermaid diagrams, and reproducible NA call-support refresh script."),
    ]
    lines = [
        "# Bjuice20 Inflection Deliverables Multiagent Ledger",
        "",
        f"Generated: `{TS}`",
        "",
        "| Row | Agent | State | Evidence |",
        "|---|---|---|---|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    lines.extend(
        [
            "",
            "## Acceptance",
            "",
            "- Expected universe: 20 samples, 40 libraries, 80 sequencing inputs, 20 analysis units.",
            "- Produced-package receipt: 18 ready packages, 2 missing packages.",
            "- Report explicitly records the original default-credential gap, the later explicit-profile NA raw/package call-support refresh, and does not claim terminal customer delivery.",
            "- NA call-support refresh generated 13 rows: 6 direct called, 1 primary-SMN called with Sentieon discordance, 1 raw Turner QC support row, 1 supplemental NA23687 raw SMN12 support row, 2 qualitative FXN support rows, 1 partial chr9 support row, and 1 UPD8 out-of-scope row.",
        ]
    )
    LEDGER.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
