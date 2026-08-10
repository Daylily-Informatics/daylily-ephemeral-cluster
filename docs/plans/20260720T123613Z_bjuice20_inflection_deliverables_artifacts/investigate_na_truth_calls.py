#!/usr/bin/env python3
"""Refresh NA/Coriell expected-positive call support from raw/package artifacts."""

from __future__ import annotations

import csv
import gzip
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ARTIFACT_DIR = Path(__file__).resolve().parent
PACKAGE_INVENTORY = ARTIFACT_DIR / "package_inventory.tsv"
CORIELL_EXPECTED = ARTIFACT_DIR / "coriell_expected_positives.tsv"

S3_INFLIGHT_RAW_BASE = (
    "s3://lsmc-dayoa-analysis-results-usw2/validation/"
    "inflight_pr53_recovery_20260720T011608Z/"
    "ifx-p2-1000-120-0715/bjuiceprevalanalysis-complete/"
    "daylily-omics-analysis/results/day/hg38"
)
S3_SUPPLEMENTAL_PRE_RAW_BASE = (
    "s3://lsmc-dayoa-analysis-results-usw2/validation/"
    "pre_13.0.11_8_g1d44044_20260719T214703Z/"
    "ifx-p2-1000-120-0715/bjuiceprevalanalysis-complete/"
    "daylily-omics-analysis/results/day/hg38"
)
S3_PACKAGE_BASE = f"{S3_INFLIGHT_RAW_BASE}/deliveries/inflection/bjuiceprevalanalysis-complete"
RAW_BASES = [
    ("repaired_inflight_raw", S3_INFLIGHT_RAW_BASE),
    ("successful_pre_export_raw", S3_SUPPLEMENTAL_PRE_RAW_BASE),
]
AWS_ARGS = ["--profile", "lsmc", "--region", "us-west-2"]


FIELDS = [
    "sample",
    "expected_positive",
    "assay_area",
    "package_status",
    "support_status",
    "support_level",
    "observed_call_summary",
    "primary_evidence_path",
    "secondary_evidence_path",
    "interpretation",
    "limitations",
]


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            out = {field: row.get(field, "") for field in fields}
            if out[fields[-1]] == "":
                out[fields[-1]] = "not_applicable"
            writer.writerow(out)


def summary_text(value: Any) -> str:
    text = str(value).replace("\n", " ")
    replacements = {
        "\u03b1": "alpha",
        "\u2014": "-",
        "\u2013": "-",
        "\u2265": ">=",
        "\u2264": "<=",
    }
    for before, after in replacements.items():
        text = text.replace(before, after)
    return text


def run_aws(args: list[str], *, required: bool = True) -> bytes | None:
    command = ["aws", "s3", *args, *AWS_ARGS]
    proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode == 0:
        return proc.stdout
    if required:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(command)}\n"
            f"{proc.stderr.decode(errors='replace')}"
        )
    return None


def cp_text(uri: str, *, gzipped: bool = False, required: bool = True) -> str | None:
    payload = run_aws(["cp", uri, "-"], required=required)
    if payload is None:
        return None
    if gzipped:
        payload = gzip.decompress(payload)
    return payload.decode("utf-8", errors="replace")


def ls_text(uri: str) -> str:
    payload = run_aws(["ls", uri, "--recursive"], required=False)
    if payload is None:
        return ""
    return payload.decode("utf-8", errors="replace")


def package_uri(package_id: str, relative_path: str) -> str:
    return f"{S3_PACKAGE_BASE}/{package_id}/{relative_path}"


def raw_uri(package_id: str, relative_path: str, *, base: str = S3_INFLIGHT_RAW_BASE) -> str:
    return f"{base}/{package_id}/{relative_path}"


def cp_raw_text(
    package_id: str,
    relative_path: str,
    *,
    gzipped: bool = False,
    required: bool = True,
) -> tuple[str | None, str, str]:
    attempted = []
    for source, base in RAW_BASES:
        uri = raw_uri(package_id, relative_path, base=base)
        attempted.append(uri)
        text = cp_text(uri, gzipped=gzipped, required=False)
        if text is not None:
            return text, uri, source
    if required:
        raise RuntimeError("No raw object found for " + relative_path + " in: " + "; ".join(attempted))
    return None, attempted[0], ""


def parse_eh_row(package_id: str, sample: str, gene: str, variant_id: str) -> tuple[dict[str, str], str, str]:
    rel = f"align/hiomrs_sr/na/hiomrs/expansionhunter/{package_id}.eh.tsv"
    text, uri, source = cp_raw_text(package_id, rel, required=True)
    assert text is not None
    rows = csv.DictReader(text.splitlines(), delimiter="\t")
    for row in rows:
        if row.get("SampleID") == sample and row.get("gene") == gene and row.get("variant_id") == variant_id:
            return row, uri, source
    raise RuntimeError(f"No ExpansionHunter row for {sample} {gene} {variant_id}")


def parse_yaml_scalar(raw: str) -> Any:
    value = raw.strip()
    if value == "[]":
        return []
    if value in {"''", '""'}:
        return ""
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value in {"None", "null"}:
        return None
    try:
        return int(value)
    except ValueError:
        pass
    if value.startswith('"'):
        inner = value[1:-1] if value.endswith('"') else value[1:]
        inner = re.sub(r"\\\s*\n\s*\\?\s*", "", inner)
        return bytes(inner, "utf-8").decode("unicode_escape", errors="replace")
    if value.startswith("'"):
        inner = value[1:-1] if value.endswith("'") else value[1:]
        return inner.replace("''", "'")
    return value


def extract_yaml_section(text: str, section_name: str) -> str:
    lines = text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line == f"{section_name}:":
            start = idx + 1
            break
    if start is None:
        raise RuntimeError(f"SegDup YAML is missing required section {section_name}")
    end = len(lines)
    for idx in range(start, len(lines)):
        if lines[idx] and not lines[idx].startswith(" "):
            end = idx
            break
    return "\n".join(lines[start:end]) + "\n"


def parse_yaml_mapping(block: str, key_name: str) -> dict[str, Any]:
    lines = block.splitlines()
    values: dict[str, Any] = {}
    start = None
    for idx, line in enumerate(lines):
        if line == f"  {key_name}:":
            start = idx + 1
            break
    if start is None:
        return values
    for line in lines[start:]:
        if not line.startswith("    "):
            break
        stripped = line[4:]
        if not stripped or stripped.startswith("- ") or ": " not in stripped:
            continue
        key, raw = stripped.split(": ", 1)
        values[key] = parse_yaml_scalar(raw)
    return values


def parse_yaml_top_scalar(block: str, key_name: str) -> Any:
    lines = block.splitlines()
    for idx, line in enumerate(lines):
        prefix = f"  {key_name}:"
        if not line.startswith(prefix):
            continue
        raw = line[len(prefix) :]
        continuation = []
        for extra in lines[idx + 1 :]:
            if not extra.startswith("    "):
                break
            continuation.append(extra.strip())
        if continuation:
            raw = raw + "\n" + "\n".join(continuation)
        return parse_yaml_scalar(raw)
    return ""


def parse_segdup_yaml_subset(text: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for section_name in ["HBA", "RCCX1"]:
        section = extract_yaml_section(text, section_name)
        parsed[section_name] = {
            "Copy numbers": parse_yaml_mapping(section, "Copy numbers"),
            "cn_interpretation": parse_yaml_top_scalar(section, "cn_interpretation"),
        }
        if section_name == "RCCX1":
            parsed[section_name]["cyp21_analysis"] = parse_yaml_mapping(section, "cyp21_analysis")
            parsed[section_name]["module_count"] = parse_yaml_top_scalar(section, "module_count")
    return parsed


def parse_yaml(package_id: str) -> tuple[dict[str, Any], str, str]:
    rel = f"align/hiomrs_sr/na/hiomrs/segdup/{package_id}.yaml"
    text, uri, source = cp_raw_text(package_id, rel, required=False)
    if text is None:
        rel = f"variants/segdup/{package_id}.yaml"
        uri = package_uri(package_id, rel)
        text = cp_text(uri, required=True)
        source = "package_fallback"
    assert text is not None
    try:
        import yaml  # type: ignore[import-not-found]

        return yaml.safe_load(text), uri, source
    except ModuleNotFoundError:
        return parse_segdup_yaml_subset(text), uri, source


def parse_smn_summary(package_id: str) -> tuple[dict[str, Any] | None, str, str]:
    rel = f"align/hiomrs_sr/na/htd/smn12/{package_id}.hiomrs_sr.na.smn12.summary.json"
    text, uri, source = cp_raw_text(package_id, rel, required=False)
    if not text:
        return None, uri, source
    payload = json.loads(text)
    if len(payload) != 1:
        return payload, uri, source
    return next(iter(payload.values())), uri, source


def parse_smn_concordance(package_id: str) -> tuple[dict[str, Any], str]:
    uri = package_uri(package_id, "smn/smn_concordance.json")
    text = cp_text(uri, required=True)
    assert text is not None
    return json.loads(text), uri


def parse_package_metrics(package_id: str) -> tuple[dict[str, Any], str]:
    uri = package_uri(package_id, "qc/package_metrics.json")
    text = cp_text(uri, required=True)
    assert text is not None
    return json.loads(text), uri


def count_vcf_records(uri: str, *, gzipped: bool = True) -> int:
    text = cp_text(uri, gzipped=gzipped, required=True)
    assert text is not None
    return sum(1 for line in text.splitlines() if line and not line.startswith("#"))


def parse_info_value(info: str, key: str) -> str:
    match = re.search(rf"(?:^|;){re.escape(key)}=([^;]+)", info)
    return match.group(1) if match else ""


def max_abs_svlen(info: str) -> int:
    raw = parse_info_value(info, "SVLEN")
    if not raw:
        return 0
    values = []
    for item in raw.split(","):
        try:
            values.append(abs(int(item)))
        except ValueError:
            continue
    return max(values) if values else 0


def scan_large_sv(package_id: str, chroms: set[str], min_len: int = 1_000_000) -> dict[str, Any]:
    rels = {
        "longreadsv": (
            f"align/hiomrs_sr/na/sv/hiomrs/{package_id}.hiomrs_sr.na.hiomrs."
            f"sv.callsets/native/{package_id}.sentieon_longreadsv.vcf.gz"
        ),
        "tiddit": f"align/hiomrs_sr/na/sv/tiddit/{package_id}.hiomrs_sr.tiddit.sv.sort.vcf.gz",
    }
    result: dict[str, Any] = {}
    for caller, rel in rels.items():
        text, uri, source = cp_raw_text(package_id, rel, gzipped=True, required=True)
        assert text is not None
        hits = []
        by_type = Counter()
        by_filter = Counter()
        for line in text.splitlines():
            if not line or line.startswith("#"):
                continue
            chrom, pos, _id, _ref, alt, _qual, filt, info, *_rest = line.split("\t")
            if chrom not in chroms:
                continue
            svlen = max_abs_svlen(info)
            if svlen < min_len:
                continue
            svtype = parse_info_value(info, "SVTYPE")
            end = parse_info_value(info, "END")
            by_type[svtype] += 1
            by_filter[filt] += 1
            hits.append(
                {
                    "chrom": chrom,
                    "pos": pos,
                    "end": end,
                    "alt": alt,
                    "svtype": svtype,
                    "svlen": svlen,
                    "filter": filt,
                }
            )
        result[caller] = {
            "uri": uri,
            "source": source,
            "hit_count": len(hits),
            "by_svtype": dict(sorted(by_type.items())),
            "by_filter": dict(sorted(by_filter.items())),
            "examples": hits[:5],
        }
    return result


def count_raw_cnv_records(package_id: str) -> tuple[int, str, str]:
    rel = f"align/hiomrs_sr/na/cnv/hiomrs/{package_id}.hiomrs_sr.na.hiomrs.cnv.vcf.gz"
    text, uri, source = cp_raw_text(package_id, rel, gzipped=True, required=True)
    assert text is not None
    return sum(1 for line in text.splitlines() if line and not line.startswith("#")), uri, source


def peddy_sex_check(package_id: str) -> tuple[dict[str, str] | None, str]:
    rel = (
        f"align/hiomrs_sr/na/snv/hiomrs/peddy/{package_id}.hiomrs_sr.na.hiomrs."
        "peddy.sex_check.csv"
    )
    text, uri, _source = cp_raw_text(package_id, rel, required=False)
    if not text:
        return None, uri
    rows = list(csv.DictReader(text.splitlines()))
    return (rows[0] if rows else None), uri


def parse_sex_complement(package_id: str, aligner: str = "hiomrs_sr") -> tuple[dict[str, Any] | None, str]:
    rel = f"align/{aligner}/na/alignqc/sex_complement/{package_id}.{aligner}.na.sex_complement.json"
    text, uri, _source = cp_raw_text(package_id, rel, required=False)
    if not text:
        return None, uri
    return json.loads(text), uri


def parse_goleft_chr_summary(package_id: str, chrom: str) -> tuple[dict[str, Any], str]:
    rel = "align/hiomrs_sr/na/alignqc/goleft/goleft-indexcov.bed.gz"
    text, uri, _source = cp_raw_text(package_id, rel, gzipped=True, required=True)
    assert text is not None
    values = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) < 4 or fields[0] != chrom:
            continue
        try:
            values.append(float(fields[3]))
        except ValueError:
            continue
    if not values:
        raise RuntimeError(f"No goleft indexcov rows for {package_id} {chrom}")
    values.sort()
    n = len(values)
    median = values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2
    return {
        "window_count": n,
        "mean": round(sum(values) / n, 4),
        "median": round(median, 4),
        "fraction_gt_1_2": round(sum(1 for value in values if value > 1.2) / n, 4),
        "fraction_gt_1_3": round(sum(1 for value in values if value > 1.3) / n, 4),
        "fraction_lt_0_8": round(sum(1 for value in values if value < 0.8) / n, 4),
    }, uri


def sample_listing(package_id: str, *, base: str = S3_INFLIGHT_RAW_BASE) -> str:
    return ls_text(raw_uri(package_id, "", base=base))


def contains_suffix(listing: str, suffix: str) -> bool:
    return any(line.rstrip().endswith(suffix) for line in listing.splitlines())


def build_raw_inventory(inventory_by_sample: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    rows = []
    for sample in sorted(row["sample"] for row in inventory_by_sample.values() if row["sample"].startswith("NA")):
        package_id = inventory_by_sample[sample]["package_id"]
        listing = sample_listing(package_id)
        supplemental_listing = sample_listing(package_id, base=S3_SUPPLEMENTAL_PRE_RAW_BASE)
        raw_smn_suffix = f"/align/hiomrs_sr/na/htd/smn12/{package_id}.hiomrs_sr.na.smn12.summary.json"
        rows.append(
            {
                "sample": sample,
                "package_id": package_id,
                "package_status": inventory_by_sample[sample]["package_manifest_status"],
                "raw_snapshot": S3_INFLIGHT_RAW_BASE,
                "raw_expansionhunter_tsv": str(contains_suffix(listing, f"/align/hiomrs_sr/na/hiomrs/expansionhunter/{package_id}.eh.tsv")),
                "raw_segdup_yaml": str(contains_suffix(listing, f"/align/hiomrs_sr/na/hiomrs/segdup/{package_id}.yaml")),
                "raw_segdup_final_vcfs": str("/align/hiomrs_sr/na/hiomrs/segdup/" in listing and ".result.vcf.gz" in listing),
                "raw_segdup_shard_tars": str("/align/hiomrs_sr/na/hiomrs/segdup/shards/" in listing and ".segdup.tar.gz" in listing),
                "raw_smn12_summary_json": str(contains_suffix(listing, raw_smn_suffix)),
                "raw_cnv_vcf": str(contains_suffix(listing, f"/align/hiomrs_sr/na/cnv/hiomrs/{package_id}.hiomrs_sr.na.hiomrs.cnv.vcf.gz")),
                "raw_longreadsv_vcf": str(contains_suffix(listing, f"/align/hiomrs_sr/na/sv/hiomrs/{package_id}.hiomrs_sr.na.hiomrs.sv.callsets/native/{package_id}.sentieon_longreadsv.vcf.gz")),
                "raw_tiddit_vcf": str(contains_suffix(listing, f"/align/hiomrs_sr/na/sv/tiddit/{package_id}.hiomrs_sr.tiddit.sv.sort.vcf.gz")),
                "raw_sex_complement_json": str(contains_suffix(listing, f"/align/hiomrs_sr/na/alignqc/sex_complement/{package_id}.hiomrs_sr.na.sex_complement.json")),
                "raw_goleft_indexcov_bed": str(contains_suffix(listing, "/align/hiomrs_sr/na/alignqc/goleft/goleft-indexcov.bed.gz")),
                "supplemental_pre_smn12_summary_json": str(contains_suffix(supplemental_listing, raw_smn_suffix)),
            }
        )
    return rows


def base_row(expected_by_sample: dict[str, dict[str, str]], inventory_by_sample: dict[str, dict[str, str]], sample: str) -> dict[str, Any]:
    return {
        "sample": sample,
        "expected_positive": expected_by_sample[sample]["expected_positive"],
        "assay_area": expected_by_sample[sample]["assay_area"],
        "package_status": inventory_by_sample[sample]["package_manifest_status"],
    }


def main() -> int:
    expected = read_tsv(CORIELL_EXPECTED)
    inventory = read_tsv(PACKAGE_INVENTORY)
    expected_by_sample = {row["sample"]: row for row in expected}
    inventory_by_sample = {row["sample"]: row for row in inventory}
    rows: list[dict[str, Any]] = []
    evidence: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "s3_inflight_raw_base": S3_INFLIGHT_RAW_BASE,
        "s3_package_base": S3_PACKAGE_BASE,
        "s3_supplemental_pre_raw_base": S3_SUPPLEMENTAL_PRE_RAW_BASE,
        "aws_profile": "lsmc",
        "samples": {},
    }
    raw_inventory = build_raw_inventory(inventory_by_sample)

    # NA05067: chromosome 9 abnormality. CNV is empty, but TIDDIT has large chr9 SVs.
    sample = "NA05067"
    package_id = inventory_by_sample[sample]["package_id"]
    metrics, metrics_uri = parse_package_metrics(package_id)
    cnv_records, cnv_uri, cnv_source = count_raw_cnv_records(package_id)
    sv_scan = scan_large_sv(package_id, {"chr9"})
    tiddit = sv_scan["tiddit"]
    sentieon = sv_scan["longreadsv"]
    goleft_chr9, goleft_uri = parse_goleft_chr_summary(package_id, "chr9")
    examples = tiddit["examples"]
    example_text = "; ".join(
        f"{hit['chrom']}:{hit['pos']}-{hit['end']} {hit['svtype']} {hit['svlen']}bp {hit['filter']}"
        for hit in examples[:3]
    )
    row = base_row(expected_by_sample, inventory_by_sample, sample)
    row.update(
        {
            "support_status": "partial_support",
            "support_level": "raw pre-package chromosome-9 support only",
            "observed_call_summary": (
                f"CNV records={cnv_records} ({cnv_source}); goleft chr9 mean={goleft_chr9['mean']} "
                f"median={goleft_chr9['median']} windows={goleft_chr9['window_count']}; "
                f"LongReadSV large chr9 events={sentieon['hit_count']}; "
                f"TIDDIT large chr9 events={tiddit['hit_count']} "
                f"(filters {tiddit['by_filter']}); examples: {example_text}"
            ),
            "primary_evidence_path": goleft_uri,
            "secondary_evidence_path": f"{tiddit['uri']}; {cnv_uri}; {metrics_uri}",
            "interpretation": (
                "Raw pre-package data has chromosome 9 dosage/SV evidence, but it does "
                "not directly call the public trisomy 9 karyotype."
            ),
            "limitations": "CNV VCF has zero records; goleft chr9 depth is not a formal trisomy call; LongReadSV has no >=1 Mb chr9 event; TIDDIT calls are SV breakend-style evidence, not karyotype/ploidy truth.",
        }
    )
    rows.append(row)
    evidence["samples"][sample] = {
        "package_id": package_id,
        "cnv_record_count": cnv_records,
        "cnv_source": cnv_source,
        "metrics_cnv_record_count": metrics["vcf_metrics"]["cnv_vcf"]["record_count"],
        "goleft_chr9": goleft_chr9,
        "goleft_uri": goleft_uri,
        "large_sv_scan": sv_scan,
    }

    # NA10798: HBA Filipino alpha-thalassemia deletion.
    sample = "NA10798"
    package_id = inventory_by_sample[sample]["package_id"]
    segdup_yaml, yaml_uri, yaml_source = parse_yaml(package_id)
    hba = segdup_yaml["HBA"]
    hba_cn = hba["Copy numbers"]
    row = base_row(expected_by_sample, inventory_by_sample, sample)
    row.update(
        {
            "support_status": "called",
            "support_level": f"direct SegDup HBA copy-number support ({yaml_source})",
            "observed_call_summary": (
                "HBA copy numbers: "
                f"non-duplication={hba_cn.get('non-duplication')}, "
                f"a3.7={hba_cn.get('a3.7')}, a4.2={hba_cn.get('a4.2')}; "
                f"{summary_text(hba.get('cn_interpretation', ''))}"
            ),
            "primary_evidence_path": yaml_uri,
            "secondary_evidence_path": raw_uri(package_id, f"align/hiomrs_sr/na/hiomrs/segdup/{package_id}.HBA.result.vcf.gz"),
            "interpretation": "Matches a heterozygous HBA-region deletion signal compatible with the expected --FIL/alpha alpha truth.",
            "limitations": "The package labels the HBA pattern as requiring manual review and does not name the Filipino deletion allele explicitly.",
        }
    )
    rows.append(row)
    evidence["samples"][sample] = {"package_id": package_id, "hba": hba, "segdup_yaml_source": yaml_source}

    # Repeat-expansion samples with direct target rows.
    repeat_targets = {
        "NA13189": {
            "gene": "HTT",
            "variant_id": "HD_HTT",
            "expected": "larger allele 50 CAG",
            "interpretation": "Observed max allele 52 with CI including 50; directly supports the HTT CAG truth call.",
            "status": "called",
            "level": "direct ExpansionHunter repeat support",
            "limitations": "Short-read repeat sizing remains approximate but the target and classification align.",
        },
        "NA15848": {
            "gene": "FXN",
            "variant_id": "FRDA_FXN",
            "expected": "about 830 GAA repeats",
            "interpretation": "ExpansionHunter calls FXN in pathogenic range, supporting the expansion class but not the public absolute repeat size.",
            "status": "qualitative_support_size_discordant",
            "level": "qualitative ExpansionHunter expansion support",
            "limitations": "Observed max allele is far below the expected ~830 repeat size; do not treat as exact repeat-size confirmation.",
        },
        "NA15849": {
            "gene": "FXN",
            "variant_id": "FRDA_FXN",
            "expected": "about 920 GAA repeats",
            "interpretation": "ExpansionHunter calls FXN in pathogenic range, supporting the expansion class but not the public absolute repeat size.",
            "status": "qualitative_support_size_discordant",
            "level": "qualitative ExpansionHunter expansion support",
            "limitations": "Observed max allele is far below the expected ~920 repeat size; do not treat as exact repeat-size confirmation.",
        },
        "NA20230": {
            "gene": "FMR1",
            "variant_id": "FXS_FMR1",
            "expected": "53 CGG repeats",
            "interpretation": "Observed max allele 55 with CI including 53; directly supports the FMR1 intermediate-repeat truth call.",
            "status": "called",
            "level": "direct ExpansionHunter repeat support",
            "limitations": "Short-read repeat sizing remains approximate but the target and classification align.",
        },
    }
    for sample, target in repeat_targets.items():
        package_id = inventory_by_sample[sample]["package_id"]
        eh, eh_uri, eh_source = parse_eh_row(package_id, sample, target["gene"], target["variant_id"])
        row = base_row(expected_by_sample, inventory_by_sample, sample)
        row.update(
            {
                "support_status": target["status"],
                "support_level": f"{target['level']} ({eh_source})",
                "observed_call_summary": (
                    f"ExpansionHunter {target['gene']} {target['variant_id']}: "
                    f"genotype={eh['genotype']}, CI={eh['genotype_confidence_interval']}, "
                    f"max_allele={eh['max_allele']}, status={eh['status']}; "
                    f"expected {target['expected']}"
                ),
                "primary_evidence_path": eh_uri,
                "secondary_evidence_path": raw_uri(package_id, f"align/hiomrs_sr/na/hiomrs/expansionhunter/{package_id}.eh.vcf"),
                "interpretation": target["interpretation"],
                "limitations": target["limitations"],
            }
        )
        rows.append(row)
        evidence["samples"][sample] = {"package_id": package_id, "expansionhunter_row": eh, "expansionhunter_source": eh_source}

    # CYP21A2 deletion samples are represented through RCCX1 SegDup evidence.
    for sample in ["NA14732", "NA14733"]:
        package_id = inventory_by_sample[sample]["package_id"]
        segdup_yaml, yaml_uri, yaml_source = parse_yaml(package_id)
        rccx = segdup_yaml["RCCX1"]
        cn = rccx["Copy numbers"]
        cyp21 = rccx.get("cyp21_analysis", {})
        row = base_row(expected_by_sample, inventory_by_sample, sample)
        row.update(
            {
                "support_status": "called",
                "support_level": f"direct RCCX1 SegDup CYP21A2 copy-number support ({yaml_source})",
                "observed_call_summary": (
                    f"RCCX1 copy numbers: CYP21A2={cn.get('CYP21A2')}, "
                    f"CYP21A1P={cn.get('CYP21A1P')}, total_cyp21={cyp21.get('total_cyp21')}, "
                    f"functional_count={cyp21.get('functional_count')}, pseudo_count={cyp21.get('pseudo_count')}; "
                    f"module_count={rccx.get('module_count')}"
                ),
                "primary_evidence_path": yaml_uri,
                "secondary_evidence_path": raw_uri(package_id, f"align/hiomrs_sr/na/hiomrs/segdup/{package_id}.RCCX1.result.vcf.gz"),
                "interpretation": "Matches heterozygous loss of functional CYP21A2 copy number.",
                "limitations": "CYP21A2 is delivered under the RCCX1 SegDup summary/gene role, not as a standalone CYP21A2 package role.",
            }
        )
        rows.append(row)
        evidence["samples"][sample] = {"package_id": package_id, "rccx1": rccx, "segdup_yaml_source": yaml_source}

    # NA15603: UPD/ROH truth is not represented by a package role.
    sample = "NA15603"
    package_id = inventory_by_sample[sample]["package_id"]
    metrics, metrics_uri = parse_package_metrics(package_id)
    cnv_records, cnv_uri, cnv_source = count_raw_cnv_records(package_id)
    raw_listing = sample_listing(package_id)
    roh_upd_hits = [
        line
        for line in raw_listing.splitlines()
        if re.search(r"roh|upd|baf", line, flags=re.IGNORECASE)
    ]
    row = base_row(expected_by_sample, inventory_by_sample, sample)
    row.update(
        {
            "support_status": "outside_pipeline_scope_no_supporting_call",
            "support_level": "no ordinary package-call support",
            "observed_call_summary": (
                f"CNV records={cnv_records} ({cnv_source}); raw ROH/UPD/BAF-matching objects={len(roh_upd_hits)}; "
                "package metrics list standard CNV, SV, SegDup, SMN, repeat, SNV, mito roles but no ROH/UPD role."
            ),
            "primary_evidence_path": metrics_uri,
            "secondary_evidence_path": cnv_uri,
            "interpretation": "No produced package evidence directly supports chromosome 8 uniparental isodisomy.",
            "limitations": "UPD/ROH detection is outside the delivered Inflection package role set inspected here.",
        }
    )
    rows.append(row)
    evidence["samples"][sample] = {
        "package_id": package_id,
        "cnv_record_count": cnv_records,
        "cnv_source": cnv_source,
        "raw_roh_upd_baf_hits": roh_upd_hits,
        "package_metric_roles": sorted(metrics["vcf_metrics"]),
    }

    # SMN copy-number truth samples.
    smn_expectations = {
        "NA19235": {"smn1": "4", "smn2": "0"},
        "NA20775": {"smn1": "3", "smn2": "1"},
    }
    for sample, expected_cn in smn_expectations.items():
        package_id = inventory_by_sample[sample]["package_id"]
        raw_smn, raw_smn_uri, raw_smn_source = parse_smn_summary(package_id)
        concordance, concordance_uri = parse_smn_concordance(package_id)
        smncn = concordance["smncopynumbercaller"]
        sentieon = concordance["sentieon"]
        matched = (
            smncn.get("smn1_copy_number") == expected_cn["smn1"]
            and smncn.get("smn2_copy_number") == expected_cn["smn2"]
        )
        row = base_row(expected_by_sample, inventory_by_sample, sample)
        status = "called" if matched and concordance.get("overall_concordance") == "CONCORDANT" else "called_primary_smn_discordant"
        row.update(
            {
                "support_status": status,
                "support_level": "raw SMN12 support with delivered two-caller concordance summary",
                "observed_call_summary": (
                    f"expected SMN1/SMN2={expected_cn['smn1']}/{expected_cn['smn2']}; "
                    f"raw SMN12={None if raw_smn is None else str(raw_smn.get('SMN1')) + '/' + str(raw_smn.get('SMN2'))} ({raw_smn_source or 'missing'}); "
                    f"SMNCopyNumberCaller={smncn.get('smn1_copy_number')}/{smncn.get('smn2_copy_number')}; "
                    f"Sentieon={sentieon.get('smn1_copy_number')}/{sentieon.get('smn2_copy_number')}; "
                    f"overall_concordance={concordance.get('overall_concordance')}; status={concordance.get('status')}"
                ),
                "primary_evidence_path": raw_smn_uri,
                "secondary_evidence_path": concordance_uri,
                "interpretation": (
                    "Matches the expected public SMN1/SMN2 copy-number truth."
                    if status == "called"
                    else "SMNCopyNumberCaller matches the expected public SMN1/SMN2 truth, but Sentieon disagrees on SMN2."
                ),
                "limitations": (
                    ""
                    if status == "called"
                    else "Treat NA20775 as supported by the primary SMNCopyNumberCaller summary but not fully two-caller concordant."
                ),
            }
        )
        rows.append(row)
        evidence["samples"][sample] = {
            "package_id": package_id,
            "raw_smn12_summary": raw_smn,
            "raw_smn12_uri": raw_smn_uri,
            "raw_smn12_source": raw_smn_source,
            "smn_concordance": concordance,
        }

    # NA20027: Turner syndrome / X monosomy.
    sample = "NA20027"
    package_id = inventory_by_sample[sample]["package_id"]
    metrics, metrics_uri = parse_package_metrics(package_id)
    cnv_records, cnv_uri, cnv_source = count_raw_cnv_records(package_id)
    sv_scan = scan_large_sv(package_id, {"chrX", "chrY"})
    peddy_row, peddy_uri = peddy_sex_check(package_id)
    sex_comp, sex_comp_uri = parse_sex_complement(package_id)
    tiddit = sv_scan["tiddit"]
    sentieon = sv_scan["longreadsv"]
    peddy_summary = (
        "peddy sex_check unavailable"
        if peddy_row is None
        else (
            f"peddy ped_sex={peddy_row.get('ped_sex')}, predicted_sex={peddy_row.get('predicted_sex')}, "
            f"error={peddy_row.get('error')}, het_ratio={peddy_row.get('het_ratio')}"
        )
    )
    row = base_row(expected_by_sample, inventory_by_sample, sample)
    sex_summary = "sex_complement unavailable"
    if sex_comp is not None:
        metrics_obs = sex_comp.get("observed_metrics", {})
        sex_summary = (
            f"sex_complement={sex_comp.get('inferred_sex_chromosome_complement')}, "
            f"x_copy_state={metrics_obs.get('x_copy_state')}, y_copy_state={metrics_obs.get('y_copy_state')}, "
            f"indexcov_cn_x={metrics_obs.get('indexcov_cn_x')}, indexcov_cn_y={metrics_obs.get('indexcov_cn_y')}"
        )
    row.update(
        {
            "support_status": "called_raw_qc_support",
            "support_level": "raw sex-complement QC support, not a delivered variant-call role",
            "observed_call_summary": (
                f"CNV records={cnv_records} ({cnv_source}); LongReadSV large chrX/Y events={sentieon['hit_count']}; "
                f"TIDDIT large chrX/Y events={tiddit['hit_count']} (types {tiddit['by_svtype']}); "
                f"{sex_summary}; {peddy_summary}"
            ),
            "primary_evidence_path": sex_comp_uri,
            "secondary_evidence_path": f"{cnv_uri}; {metrics_uri}; {peddy_uri}",
            "interpretation": "Raw sex-complement QC supports X monosomy / 45,X Turner syndrome at the chromosome-complement level.",
            "limitations": "This is not a formal cytogenetic karyotype or delivered variant-call package role; TIDDIT large chrX events are inversions, not X-copy loss.",
        }
    )
    rows.append(row)
    evidence["samples"][sample] = {
        "package_id": package_id,
        "cnv_record_count": cnv_records,
        "cnv_source": cnv_source,
        "metrics_cnv_record_count": metrics["vcf_metrics"]["cnv_vcf"]["record_count"],
        "large_sv_scan": sv_scan,
        "sex_complement": sex_comp,
        "sex_complement_uri": sex_comp_uri,
        "peddy_sex_check": peddy_row,
        "peddy_uri": peddy_uri,
    }

    # NA23687: missing package in the repaired snapshot, but supplemental pre-export has SMN12.
    sample = "NA23687"
    package_id = inventory_by_sample[sample]["package_id"]
    raw_smn, raw_smn_uri, raw_smn_source = parse_smn_summary(package_id)
    raw_segdup_prefix = raw_uri(package_id, "align/hiomrs_sr/na/hiomrs/segdup/")
    raw_segdup = ls_text(raw_segdup_prefix)
    supplemental_summary = (
        "raw SMN12 unavailable"
        if raw_smn is None
        else (
            f"{raw_smn_source} SMN12={raw_smn.get('SMN1')}/{raw_smn.get('SMN2')}, "
            f"isCarrier={raw_smn.get('isCarrier')}, Info={raw_smn.get('Info')}"
        )
    )
    row = base_row(expected_by_sample, inventory_by_sample, sample)
    row.update(
        {
            "support_status": "called_supplemental_prepackage_not_delivered",
            "support_level": "supplemental raw SMN12 support; package missing from repaired in-flight snapshot",
            "observed_call_summary": (
                "Repaired in-flight package manifest absent; "
                f"{supplemental_summary}."
            ),
            "primary_evidence_path": raw_smn_uri,
            "secondary_evidence_path": f"{package_uri(package_id, 'package_manifest.json')}; {raw_smn_uri}; {raw_segdup_prefix}",
            "interpretation": "Supports the expected SMA carrier SMN1/SMN2=1/2 truth in supplemental raw pre-package data, but not in the delivered package snapshot.",
            "limitations": "The supporting raw call comes from the successful 2026-07-19 pre-export, not from the repaired in-flight package boundary; use it as biological call support, not delivery proof.",
        }
    )
    rows.append(row)
    evidence["samples"][sample] = {
        "package_id": package_id,
        "raw_smn12_summary": raw_smn,
        "raw_smn12_uri": raw_smn_uri,
        "raw_smn12_source": raw_smn_source,
        "raw_segdup_prefix": raw_segdup_prefix,
        "raw_segdup_object_count": len([line for line in raw_segdup.splitlines() if line.strip()]),
    }

    rows.sort(key=lambda row: row["sample"])
    support_counts = Counter(row["support_status"] for row in rows)
    evidence["support_status_counts"] = dict(sorted(support_counts.items()))
    evidence["row_count"] = len(rows)
    status_by_sample = {
        row["sample"]: f"{row['support_status']}: {row['interpretation']}" for row in rows
    }

    write_tsv(ARTIFACT_DIR / "na_truth_call_support.tsv", rows, FIELDS)
    write_tsv(
        ARTIFACT_DIR / "na_prepackage_result_inventory.tsv",
        raw_inventory,
        [
            "sample",
            "package_id",
            "package_status",
            "raw_snapshot",
            "raw_expansionhunter_tsv",
            "raw_segdup_yaml",
            "raw_segdup_final_vcfs",
            "raw_segdup_shard_tars",
            "raw_smn12_summary_json",
            "raw_cnv_vcf",
            "raw_longreadsv_vcf",
            "raw_tiddit_vcf",
            "raw_sex_complement_json",
            "raw_goleft_indexcov_bed",
            "supplemental_pre_smn12_summary_json",
        ],
    )
    coriell_rows = read_tsv(CORIELL_EXPECTED)
    for row in coriell_rows:
        if row["sample"] in status_by_sample:
            row["call_status"] = status_by_sample[row["sample"]]
    write_tsv(
        CORIELL_EXPECTED,
        coriell_rows,
        ["sample", "expected_positive", "assay_area", "call_status", "source_url"],
    )
    truth_path = ARTIFACT_DIR / "truth_fscore_status.tsv"
    truth_rows = read_tsv(truth_path)
    for row in truth_rows:
        if row["sample"] in status_by_sample and row["truth_type"] == "Coriell expected positive":
            row["call_status"] = status_by_sample[row["sample"]]
    write_tsv(
        truth_path,
        truth_rows,
        ["sample", "truth_type", "expected_truth_source", "package_status", "call_status", "fscore"],
    )
    (ARTIFACT_DIR / "na_truth_call_evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (ARTIFACT_DIR / "na_truth_call_support_flow.mmd").write_text(
        "\n".join(
            [
                "flowchart LR",
                '    Expected["13 NA expected positives"] --> Package["Inflection package snapshot"]',
                '    Package --> Raw["Raw pre-package result tree"]',
                '    Raw --> Direct["Direct support: HBA, HTT, CYP21A2/RCCX1, SMN, FMR1"]',
                '    Raw --> Qual["Qualitative support: FXN pathogenic-range expansion, size discordant"]',
                '    Raw --> Partial["Partial support: chr9 goleft/TIDDIT, no trisomy CNV"]',
                '    Raw --> Turner["Turner support: sex-complement X call"]',
                '    Raw --> Gap["No direct support: UPD8"]',
                '    Raw --> Supplemental["Supplemental pre-export SMN12 supports NA23687; not delivered"]',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    summary_path = ARTIFACT_DIR / "report_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["live_s3_refresh"] = (
            "explicit --profile lsmc refresh performed for bounded NA raw pre-package and package call-support artifacts"
        )
        summary["na_call_support_rows"] = len(rows)
        summary["na_call_support_status_counts"] = dict(sorted(support_counts.items()))
        summary["na_prepackage_inventory_rows"] = len(raw_inventory)
        summary["na_supplemental_pre_export_boundary"] = S3_SUPPLEMENTAL_PRE_RAW_BASE
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "support_status_counts": dict(support_counts)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
