#!/usr/bin/env python3
"""Build the combined HG002 Bjuice downsampling technical report."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.lines import Line2D
import numpy as np


EXPERIMENTS = {
    "E1": {
        "analysis_id": "prod-cand-1703-hg002-bjuice-v2-multiau-20260814T114522Z",
        "title": "Initial full-SR, variable-LR experiment",
    },
    "E3": {
        "analysis_id": "prod-cand-1703-hg002-bjuice-4au-kitchensink-20260817T025004Z",
        "title": "Four-AU measured-coverage gap-fill experiment",
    },
    "P1": {
        "analysis_id": "pcand18022-bjuice-preval6-15014-dry-20260817t112900z",
        "title": "Bjuice v0.9 production full-coverage execution 1",
    },
    "E4": {
        "analysis_id": "prerel18025-bjuice-v2-hg002-20au-18042-20260818t1255z-live",
        "title": "Twenty-AU controlled native-SR × cumulative-ONT matrix",
    },
}
EXPERIMENT_INDEX = {name: index for index, name in enumerate(EXPERIMENTS)}
AU_ORDER = [
    "p5xp5",
    "1x1",
    "3x3",
    "5x5",
    "10x5",
    "15x5",
    "15x10",
    "10xby10x",
    "12xby12x",
    "20xby15x",
    "30xby15x",
    "fullcov_0to24",
    *[f"N{index:02d}" for index in range(1, 21)],
]
AU_INDEX = {name: index for index, name in enumerate(AU_ORDER)}
TARGETS = {
    "p5xp5": (Decimal("0.5"), Decimal("0.5")),
    "1x1": (Decimal("1"), Decimal("1")),
    "3x3": (Decimal("3"), Decimal("3")),
    "5x5": (Decimal("5"), Decimal("5")),
    "10x5": (Decimal("10"), Decimal("5")),
    "15x5": (Decimal("15"), Decimal("5")),
    "15x10": (Decimal("15"), Decimal("10")),
    "10xby10x": (Decimal("9.85"), Decimal("9.67")),
    "12xby12x": (Decimal("12.71"), Decimal("11.43")),
    "20xby15x": (Decimal("20"), Decimal("15")),
    "30xby15x": (Decimal("30"), Decimal("15")),
}
E4_SOURCE_TO_PLAN = {
    "HG002-ilmn0p5x-ont0p5x-h01": ("N01", Decimal("0.5"), Decimal("0.5"), 1),
    "HG002-ilmn0p5x-ont4x-h08": ("N02", Decimal("0.5"), Decimal("4"), 8),
    "HG002-ilmn0p5x-ont12x-h24": ("N03", Decimal("0.5"), Decimal("12"), 24),
    "HG002-ilmn0p5x-ont30x-h72": ("N04", Decimal("0.5"), Decimal("30"), 72),
    "HG002-ilmn10x-ont0p5x-h01": ("N05", Decimal("10"), Decimal("0.5"), 1),
    "HG002-ilmn10x-ont4x-h08": ("N06", Decimal("10"), Decimal("4"), 8),
    "HG002-ilmn10x-ont12x-h24": ("N07", Decimal("10"), Decimal("12"), 24),
    "HG002-ilmn10x-ont30x-h72": ("N08", Decimal("10"), Decimal("30"), 72),
    "HG002-ilmn30x-ont30x-h72": ("N09", Decimal("30"), Decimal("30"), 72),
    "HG002-ilmn43p73x-ont30x-h72": ("N10", Decimal("43.73"), Decimal("30"), 72),
    "HG002-ilmn2x-ont0p5x-h01": ("N11", Decimal("2"), Decimal("0.5"), 1),
    "HG002-ilmn2x-ont4x-h08": ("N12", Decimal("2"), Decimal("4"), 8),
    "HG002-ilmn2x-ont12x-h24": ("N13", Decimal("2"), Decimal("12"), 24),
    "HG002-ilmn2x-ont30x-h72": ("N14", Decimal("2"), Decimal("30"), 72),
    "HG002-ilmn20x-ont0p5x-h01": ("N15", Decimal("20"), Decimal("0.5"), 1),
    "HG002-ilmn20x-ont4x-h08": ("N16", Decimal("20"), Decimal("4"), 8),
    "HG002-ilmn20x-ont12x-h24": ("N17", Decimal("20"), Decimal("12"), 24),
    "HG002-ilmn20x-ont30x-h72": ("N18", Decimal("20"), Decimal("30"), 72),
    "HG002-ilmn5x-ont30x-h72": ("N19", Decimal("5"), Decimal("30"), 72),
    "HG002-ilmn15x-ont30x-h72": ("N20", Decimal("15"), Decimal("30"), 72),
}
TARGETS.update({label: (target_sr, target_lr) for label, target_sr, target_lr, _ in E4_SOURCE_TO_PLAN.values()})
EXPERIMENT_COLORS = {"E1": "#3977a8", "E3": "#5d8f70", "P1": "#87589b", "E4": "#d0783d"}
EXPERIMENT_MARKERS = {"E1": "o", "E3": "^", "P1": "P", "E4": "X"}
CALLER_STYLES = {
    "TrussSV": ("#315f88", "o"),
    "Sniffles2": ("#c2783e", "s"),
    "LongReadSV": ("#7a5a9d", "^"),
    "TIDDIT": ("#6f8850", "D"),
}
SOURCE_S3_URIS = [
    ("Shared full-prevalence Illumina FASTQs", "s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/Analysis/1/Data/BCLConvert/fastq/"),
    ("Shared HG002 ONT FC1 source", "s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set4-FC1/20260615_ONT_Set4-FC1/20260616_0048_3A_PBM08268_14b096e3/"),
    ("Shared HG002 ONT FC2 source", "s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set4-FC2/20260615_ONT_Set4-FC2/20260616_0040_3B_PBK89197_822a87b5/"),
    ("Shared HG002 ONT FC3 source", "s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/20260615_ONT_Set4-FC3/20260615_ONT_Set4-FC3/20260616_0041_3C_PBK89101_bd86eaac/"),
    ("E1 completed output export", "s3://lsmc-dayoa-analysis-results-usw2/derived/bjuice-v2-multi-analysis-unit/prod-cand-1703/prod-cand-1703-hg002-bjuice-v2-multiau-20260814T114522Z/daylily-omics-analysis/"),
    ("E3 completed output export", "s3://lsmc-dayoa-analysis-results-usw2/derived/bjuice-v2-multi-analysis-unit/prod-cand-1703/prod-cand-1703-hg002-bjuice-4au-kitchensink-20260817T025004Z/daylily-omics-analysis/"),
    ("P1 completed output export", "s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022-bjuice-preval6-15014-dry-20260817t112900z/daylily-omics-analysis/"),
]
CIRCLE_MARKER_AREA = 600  # 25% larger area than the former 480 pt² squares.
CIRCLE_LABEL_FONTSIZE = 7.2
HEATMAP_FONT_SCALE = 1.35
DENSITY_KERNEL_BANDWIDTH_X = 1.25  # Measured LR× units; each retained AU contributes one kernel.
DENSITY_KERNEL_BANDWIDTH_Y = 1.25  # Measured native-SR× units; axes remain numerically equal-scale.
DENSITY_GRID_SIZE = 180

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.titlesize": 17,
        "axes.labelsize": 14,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "axes.edgecolor": "#4b5563",
        "axes.labelcolor": "#252a31",
        "text.color": "#252a31",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
    }
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--direct-s3-coverage", type=Path, required=True)
    parser.add_argument("--assets-dir", type=Path, required=True)
    parser.add_argument("--report-path", type=Path, required=True)
    return parser.parse_args()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: na_value(row.get(name)) for name in fieldnames})


def na_value(value: Any) -> Any:
    if value is None:
        return "NA"
    if isinstance(value, float) and math.isnan(value):
        return "NA"
    return value


def number(value: Any) -> float | None:
    if value in (None, "", "NA", "null"):
        return None
    return float(value)


def fmt(value: Any, digits: int = 4, comma: bool = False) -> str:
    value = number(value)
    if value is None:
        return "NA"
    if comma:
        return f"{value:,.0f}"
    return f"{value:.{digits}f}"


def marker_label_color(cmap: Any, norm: Any, value: float) -> str:
    """Choose legible text against the metric-derived circle color."""
    red, green, blue, _ = cmap(norm(value))
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return "white" if luminance < 0.46 else "#111827"


def heatmap_font_size(base_size: float) -> float:
    """Apply the report-wide typography increase to 2D density/heatmap figures."""
    return base_size * HEATMAP_FONT_SCALE


def style_heatmap_colorbar(bar: Any, label: str) -> None:
    bar.set_label(label, fontsize=heatmap_font_size(14))
    bar.ax.tick_params(labelsize=heatmap_font_size(11))


def coverage_group_label(group: list[dict[str, Any]], include_fscore: bool = False) -> str:
    """Compact exact-coordinate duplicates while retaining every measured pair."""
    pairs = [f"{row['ilmn_measured_token']}x / {row['ont_measured_token']}x" for row in group]
    lines = ["  ·  ".join(pairs[index:index + 2]) for index in range(0, len(pairs), 2)]
    if include_fscore:
        lines.insert(0, "F=" + fmt(group[0]["fscore"], 3))
    return "\n".join(lines)


def annotate_point_labels(
    ax: Any,
    points: list[dict[str, Any]],
    x_key: str,
    y_key: str,
    group_label_fn: Any,
    fontsize: float,
    offset_scale: float = 1.0,
) -> list[Any]:
    """Label exact point groups locally without experiment encoding or leaders."""
    grouped: dict[tuple[float, float], list[dict[str, Any]]] = defaultdict(list)
    for row in points:
        grouped[(round(float(row[x_key]), 4), round(float(row[y_key]), 4))].append(row)
    angles = (45, -45, 135, -135, 0, 180, 90, -90)
    ordered_groups = sorted(grouped.values(), key=lambda group: (float(group[0][x_key]), float(group[0][y_key]), group[0].get("caller", "")))
    annotations: list[Any] = []
    for index, group in enumerate(ordered_groups):
        group = sorted(group, key=lambda item: (item.get("caller", ""), float(item["ilmn_measured_token"]), float(item["ont_measured_token"])))
        angle = math.radians(angles[index % len(angles)])
        radius = (7 + 4 * ((index // len(angles)) % 3)) * offset_scale
        row = group[0]
        annotations.append(
            ax.annotate(
                group_label_fn(group),
                (float(row[x_key]), float(row[y_key])),
                xytext=(math.cos(angle) * radius, math.sin(angle) * radius),
                textcoords="offset points",
                fontsize=fontsize,
                ha="left" if math.cos(angle) >= 0 else "right",
                va="center",
                linespacing=0.93,
                color="#111827",
                bbox={"boxstyle": "round,pad=0.08", "facecolor": "white", "edgecolor": "none", "alpha": 0.66},
                annotation_clip=True,
            )
        )
    return annotations


def relax_annotation_collisions(fig: Any, ax: Any, annotations: list[Any], iterations: int = 120) -> None:
    """Deterministically separate enlarged direct labels in display space."""
    if not annotations:
        return
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    points_per_pixel = 72.0 / fig.dpi
    for _ in range(iterations):
        boxes = [annotation.get_window_extent(renderer).expanded(1.04, 1.12) for annotation in annotations]
        shifts = [[0.0, 0.0] for _ in annotations]
        collisions = 0
        for left in range(len(boxes)):
            left_box = boxes[left]
            for right in range(left + 1, len(boxes)):
                right_box = boxes[right]
                overlap_x = min(left_box.x1, right_box.x1) - max(left_box.x0, right_box.x0)
                overlap_y = min(left_box.y1, right_box.y1) - max(left_box.y0, right_box.y0)
                if overlap_x <= 0 or overlap_y <= 0:
                    continue
                collisions += 1
                left_center = ((left_box.x0 + left_box.x1) / 2, (left_box.y0 + left_box.y1) / 2)
                right_center = ((right_box.x0 + right_box.x1) / 2, (right_box.y0 + right_box.y1) / 2)
                if overlap_y <= overlap_x:
                    direction = -1.0 if left_center[1] <= right_center[1] else 1.0
                    distance = (overlap_y + 2.0) / 2
                    shifts[left][1] += direction * distance
                    shifts[right][1] -= direction * distance
                else:
                    direction = -1.0 if left_center[0] <= right_center[0] else 1.0
                    distance = (overlap_x + 2.0) / 2
                    shifts[left][0] += direction * distance
                    shifts[right][0] -= direction * distance
        if collisions == 0:
            break
        axes_box = ax.get_window_extent(renderer)
        for index, annotation in enumerate(annotations):
            box = boxes[index]
            dx, dy = shifts[index]
            if box.x0 + dx < axes_box.x0 + 2:
                dx += axes_box.x0 + 2 - (box.x0 + dx)
            if box.x1 + dx > axes_box.x1 - 2:
                dx -= box.x1 + dx - (axes_box.x1 - 2)
            if box.y0 + dy < axes_box.y0 + 2:
                dy += axes_box.y0 + 2 - (box.y0 + dy)
            if box.y1 + dy > axes_box.y1 - 2:
                dy -= box.y1 + dy - (axes_box.y1 - 2)
            x_offset, y_offset = annotation.get_position()
            annotation.set_position((x_offset + dx * points_per_pixel, y_offset + dy * points_per_pixel))
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_relative(path: Path, dayoa_root: Path) -> str:
    return str(path.relative_to(dayoa_root))


def read_total_mean(path: Path) -> tuple[str, Decimal]:
    for row in read_tsv(path):
        if row["chrom"] == "total":
            token = row["mean"]
            return token, Decimal(token)
    raise ValueError(f"missing total coverage row: {path}")


def label_from_comment(comment: str) -> str:
    match = re.search(r"\bAU\s+([^:]+):", comment)
    if not match:
        raise ValueError(f"cannot recover AU label from comment: {comment}")
    label = match.group(1)
    if label not in TARGETS:
        raise ValueError(f"unexpected AU label {label}")
    return label


def verify_source_inventory(experiment: str, bundle_root: Path, dayoa_root: Path) -> list[dict[str, Any]]:
    rows = read_tsv(bundle_root / "source_inventory.tsv")
    verified: list[dict[str, Any]] = []
    for row in rows:
        local_path = dayoa_root / row["relative_path"]
        if not local_path.is_file():
            raise FileNotFoundError(local_path)
        local_hash = sha256_file(local_path)
        if local_hash != row["sha256"]:
            raise ValueError(f"source hash mismatch: {local_path}")
        verified.append(
            {
                **row,
                "experiment": experiment,
                "local_path": str(local_path),
                "local_sha256": local_hash,
                "local_sha256_match": 1,
            }
        )
    return verified


def parse_compact_e3(evidence_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read the bounded, hash-bound E3 extract collected through DYEC."""
    bundle_root = evidence_root / "E3"
    compact_path = bundle_root / "compact_evidence.json"
    compact = json.loads(compact_path.read_text())
    units = {row["ANALYSIS_UNIT_UID"]: row for row in compact["units"]}
    identities = compact["identity"]
    if len(units) != 4 or len(identities) != 4:
        raise ValueError("E3: expected four analysis units")
    observations: list[dict[str, Any]] = []
    for identity in identities:
        runtime = identity["RUNTIME_ANALYSIS_UNIT_UID"]
        unit = units[identity["SOURCE_ANALYSIS_UNIT_UID"]]
        label = label_from_comment(unit["ANALYSIS_UNIT_COMMENT"])
        coverage = compact["coverage"].get(runtime)
        if coverage is None:
            raise ValueError(f"E3:{runtime}: missing compact coverage")
        target_ilmn, target_ont = TARGETS[label]
        rsr = Decimal(coverage["ilmn"])
        ont = Decimal(coverage["ont"])
        observations.append(
            {
                "experiment": "E3",
                "experiment_title": EXPERIMENTS["E3"]["title"],
                "analysis_id": EXPERIMENTS["E3"]["analysis_id"],
                "au": label,
                "runtime_au": runtime,
                "source_analysis_unit_uid": identity["SOURCE_ANALYSIS_UNIT_UID"],
                "plot_label": f"E3:{label}",
                "ilmn_measured_token": None,
                "ilmn_measured": None,
                "rsr_measured_token": coverage["ilmn"],
                "rsr_measured": float(rsr),
                "ont_measured_token": coverage["ont"],
                "ont_measured": float(ont),
                "ilmn_target": float(target_ilmn),
                "ont_target": float(target_ont),
                "subsample_pct": unit["SUBSAMPLE_PCT"],
                "ont_start_hour": int(unit["ONT_FQ_START_HOUR"]),
                "ont_end_hour": int(unit["ONT_FQ_END_HOUR"]),
                "ilmn_abs_error": None,
                "ont_abs_error": float(ont - target_ont),
                "coverage_source_ilmn": None,
                "coverage_source_rsr": coverage["ilmn_source"],
                "coverage_source_ont": coverage["ont_source"],
                "dayoa_root": compact["analysis_root"] + "/daylily-omics-analysis",
                "selection_status": "source",
                "compact_evidence": compact,
            }
        )
    expected = {"10xby10x", "12xby12x", "20xby15x", "30xby15x"}
    if {row["au"] for row in observations} != expected:
        raise ValueError("E3: AU label set mismatch")
    inventory = [
        {
            "experiment": "E3",
            "analysis_root": compact["analysis_root"],
            **row,
            "local_path": "NA (bounded DYEC headnode extract)",
            "local_sha256": "NA",
            "local_sha256_match": "remote_hash_only",
        }
        for row in compact["inventory"]
    ]
    observations.sort(key=lambda row: AU_INDEX[row["au"]])
    return observations, {"inventory": inventory, "dayoa_root": None, "bundle_root": bundle_root}


def parse_compact_p1(evidence_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read the bounded P1 production extract without inventing a coverage target."""
    bundle_root = evidence_root / "P1"
    compact = json.loads((bundle_root / "compact_evidence.json").read_text())
    expected_contract = {"short_read": "full", "long_read_window": "[0,24)", "coverage_target": None}
    if compact.get("input_contract") != expected_contract:
        raise ValueError("P1: full-input contract mismatch")
    expected_measurement_contract = {
        "short_read": "native SR (sentdhiomr2sr/smd; not RSR)",
        "long_read": "LR (sentdhiomr2lr/na)",
        "metric": "Mosdepth chrom=total mean",
    }
    if compact.get("coverage_measurement_contract") != expected_measurement_contract:
        raise ValueError("P1: coverage measurement contract mismatch")
    units = {row["ANALYSIS_UNIT_UID"]: row for row in compact["units"]}
    identities = compact["identity"]
    if len(units) != 1 or len(identities) != 1:
        raise ValueError("P1: expected one HG002 full-coverage analysis unit")
    identity = identities[0]
    runtime = identity["RUNTIME_ANALYSIS_UNIT_UID"]
    unit = units.get(identity["SOURCE_ANALYSIS_UNIT_UID"])
    if unit is None or unit.get("SAMPLEID") != "HG002":
        raise ValueError("P1: runtime identity does not resolve to HG002")
    if "SR downsample full; ONT downsample full" not in unit.get("ANALYSIS_UNIT_COMMENT", ""):
        raise ValueError("P1: manifest does not attest full SR and ONT input")
    coverage = compact["coverage"].get(runtime)
    if coverage is None:
        raise ValueError("P1: missing Mosdepth coverage")
    if "/align/sentdhiomr2sr/smd/alignqc/mosdepth/" not in coverage["ilmn_source"]:
        raise ValueError("P1: SR coverage is not from native SR")
    ilmn = Decimal(coverage["ilmn"])
    ont = Decimal(coverage["ont"])
    observation = {
        "experiment": "P1",
        "experiment_title": EXPERIMENTS["P1"]["title"],
        "analysis_id": EXPERIMENTS["P1"]["analysis_id"],
        "au": "fullcov_0to24",
        "runtime_au": runtime,
        "source_analysis_unit_uid": identity["SOURCE_ANALYSIS_UNIT_UID"],
        "plot_label": "P1:fullcov",
        "ilmn_measured_token": coverage["ilmn"],
        "ilmn_measured": float(ilmn),
        "rsr_measured_token": None,
        "rsr_measured": None,
        "ont_measured_token": coverage["ont"],
        "ont_measured": float(ont),
        "ilmn_target": None,
        "ont_target": None,
        "subsample_pct": "full",
        "ont_start_hour": 0,
        "ont_end_hour": 24,
        "ilmn_abs_error": None,
        "ont_abs_error": None,
        "coverage_source_ilmn": coverage["ilmn_source"],
        "coverage_source_rsr": None,
        "coverage_source_ont": coverage["ont_source"],
        "dayoa_root": compact["analysis_root"],
        "selection_status": "source",
        "compact_evidence": compact,
    }
    inventory = [
        {
            "experiment": "P1",
            "analysis_root": compact["analysis_root"],
            **row,
            "local_path": "NA (bounded S3 export extract)",
            "local_sha256": "NA",
            "local_sha256_match": "s3_extract_hash",
        }
        for row in compact["inventory"]
    ]
    return [observation], {"inventory": inventory, "dayoa_root": None, "bundle_root": bundle_root}


def parse_compact_e4(evidence_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read the checksum-bound, in-flight E4 snapshot collected through DYEC."""
    bundle_root = evidence_root / "E4"
    compact_path = bundle_root / "compact_evidence.json"
    compact = json.loads(compact_path.read_text())
    if compact.get("schema_version") != "lsmc.hg002_bjuice_e4_compact_evidence.v1":
        raise ValueError("E4: unexpected compact-evidence schema")
    if compact.get("analysis_id") != EXPERIMENTS["E4"]["analysis_id"]:
        raise ValueError("E4: analysis identity mismatch")
    units = {row["ANALYSIS_UNIT_UID"]: row for row in compact["units"]}
    identities = compact["identity"]
    if set(units) != set(E4_SOURCE_TO_PLAN) or len(identities) != 20:
        raise ValueError("E4: expected the reviewed 20 source and runtime analysis units")
    source_to_runtime = {
        row["SOURCE_ANALYSIS_UNIT_UID"]: row["RUNTIME_ANALYSIS_UNIT_UID"] for row in identities
    }
    if set(source_to_runtime) != set(E4_SOURCE_TO_PLAN) or len(set(source_to_runtime.values())) != 20:
        raise ValueError("E4: incomplete or duplicate source/runtime identity mapping")

    end_status = compact["workflow_status_end"]["attempts"][-1]
    snapshot_state = end_status.get("state")
    snapshot_rc = end_status.get("controller", {}).get("exit_code")
    observations: list[dict[str, Any]] = []
    for source_uid, (label, target_sr, target_lr, expected_end_hour) in E4_SOURCE_TO_PLAN.items():
        runtime = source_to_runtime[source_uid]
        unit = units[source_uid]
        coverage = compact["coverage"].get(runtime)
        completeness = compact["completeness"].get(runtime)
        if coverage is None or completeness is None:
            raise ValueError(f"E4:{runtime}: missing coverage or completeness evidence")
        if (
            completeness.get("native_sr_coverage") != "complete"
            or completeness.get("lr_coverage") != "complete"
            or completeness.get("hard_vcf_giabhc") != "complete"
            or completeness.get("truvari_summaries") != 4
            or completeness.get("smn12_summary") != "complete"
            or completeness.get("segdup_vcfs") != 15
        ):
            raise ValueError(f"E4:{runtime}: a required report metric is not complete")
        if int(unit["ONT_FQ_START_HOUR"]) != 0 or int(unit["ONT_FQ_END_HOUR"]) != expected_end_hour:
            raise ValueError(f"E4:{source_uid}: ONT input interval disagrees with the reviewed plan")
        if f"target {target_sr}x" not in unit["ANALYSIS_UNIT_COMMENT"]:
            raise ValueError(f"E4:{source_uid}: native-SR target comment disagrees with the reviewed plan")
        native_sr = Decimal(coverage["native_sr"])
        rsr = Decimal(coverage["rsr"])
        lr = Decimal(coverage["lr"])
        if "/align/sentdhiomr2sr/smd/alignqc/mosdepth/" not in coverage["native_sr_source"]:
            raise ValueError(f"E4:{runtime}: native-SR source is not sentdhiomr2sr/smd")
        if "/align/sentdhiomr2rsr/na/alignqc/mosdepth/" not in coverage["rsr_source"]:
            raise ValueError(f"E4:{runtime}: RSR audit source mismatch")
        if "/align/sentdhiomr2lr/na/alignqc/mosdepth/" not in coverage["lr_source"]:
            raise ValueError(f"E4:{runtime}: LR source is not sentdhiomr2lr/na")
        observations.append(
            {
                "experiment": "E4",
                "experiment_title": EXPERIMENTS["E4"]["title"],
                "analysis_id": EXPERIMENTS["E4"]["analysis_id"],
                "au": label,
                "runtime_au": runtime,
                "source_analysis_unit_uid": source_uid,
                "plot_label": f"E4:{label}",
                "ilmn_measured_token": coverage["native_sr"],
                "ilmn_measured": float(native_sr),
                "rsr_measured_token": coverage["rsr"],
                "rsr_measured": float(rsr),
                "ont_measured_token": coverage["lr"],
                "ont_measured": float(lr),
                "ilmn_target": float(target_sr),
                "ont_target": float(target_lr),
                "subsample_pct": unit["SUBSAMPLE_PCT"],
                "ont_start_hour": 0,
                "ont_end_hour": expected_end_hour,
                "ilmn_abs_error": float(native_sr - target_sr),
                "ont_abs_error": float(lr - target_lr),
                "coverage_source_ilmn": coverage["native_sr_source"],
                "coverage_source_rsr": coverage["rsr_source"],
                "coverage_source_ont": coverage["lr_source"],
                "coverage_capture_method": "bounded live-FSx snapshot through DYEC",
                "evidence_captured_at": compact["captured_at_end_utc"],
                "direct_s3_captured_at": None,
                "snapshot_workflow_state": snapshot_state,
                "snapshot_controller_rc": snapshot_rc,
                "benchmark_scope": compact["capture_contract"]["benchmark_scope"],
                "dayoa_root": compact["dayoa_root"],
                "selection_status": "source_inflight_snapshot",
                "compact_evidence": compact,
            }
        )
    observations.sort(key=lambda row: AU_INDEX[row["au"]])
    inventory = [
        {
            "experiment": "E4",
            "analysis_root": compact["analysis_root"],
            **row,
            "local_path": "NA (bounded DYEC headnode extract)",
            "local_sha256": "NA",
            "local_sha256_match": "remote_hash_only",
        }
        for row in compact["inventory"]
    ]
    return observations, {"inventory": inventory, "dayoa_root": None, "bundle_root": bundle_root}


def parse_experiment(experiment: str, evidence_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if experiment == "E3":
        return parse_compact_e3(evidence_root)
    if experiment == "P1":
        return parse_compact_p1(evidence_root)
    if experiment == "E4":
        return parse_compact_e4(evidence_root)
    bundle_root = evidence_root / experiment
    dayoa_root = bundle_root / "daylily-omics-analysis"
    manifest_root = dayoa_root / "results/day/hg38/reports/input_manifests"
    inventory = verify_source_inventory(experiment, bundle_root, dayoa_root)

    unit_rows = read_tsv(manifest_root / "analysis_units.tsv")
    identity_rows = read_tsv(manifest_root / "analysis_unit_identity_audit.tsv")
    if len(unit_rows) != 7 or len(identity_rows) != 7:
        raise ValueError(f"{experiment}: expected seven analysis units")

    source_to_unit = {row["ANALYSIS_UNIT_UID"]: row for row in unit_rows}
    runtime_to_source = {row["RUNTIME_ANALYSIS_UNIT_UID"]: row["SOURCE_ANALYSIS_UNIT_UID"] for row in identity_rows}
    observations: list[dict[str, Any]] = []
    for runtime, source_uid in runtime_to_source.items():
        unit = source_to_unit[source_uid]
        label = label_from_comment(unit["ANALYSIS_UNIT_COMMENT"])
        unit_root = dayoa_root / "results/day/hg38" / runtime
        rsr_files = list(unit_root.glob("align/sentdhiomr2rsr/na/alignqc/mosdepth/*.summary.txt"))
        ont_files = list(unit_root.glob("align/sentdhiomr2lr/na/alignqc/mosdepth/*.summary.txt"))
        if len(rsr_files) != 1 or len(ont_files) != 1:
            raise ValueError(f"{experiment}:{runtime}: expected one RSR and one ONT Mosdepth summary")
        rsr_token, rsr = read_total_mean(rsr_files[0])
        ont_token, ont = read_total_mean(ont_files[0])
        target_ilmn, target_ont = TARGETS[label]
        observations.append(
            {
                "experiment": experiment,
                "experiment_title": EXPERIMENTS[experiment]["title"],
                "analysis_id": EXPERIMENTS[experiment]["analysis_id"],
                "au": label,
                "runtime_au": runtime,
                "source_analysis_unit_uid": source_uid,
                "plot_label": f"{experiment}:{label}",
                "ilmn_measured_token": None,
                "ilmn_measured": None,
                "rsr_measured_token": rsr_token,
                "rsr_measured": float(rsr),
                "ont_measured_token": ont_token,
                "ont_measured": float(ont),
                "ilmn_target": float(target_ilmn),
                "ont_target": float(target_ont),
                "subsample_pct": unit["SUBSAMPLE_PCT"],
                "ont_start_hour": int(unit["ONT_FQ_START_HOUR"]),
                "ont_end_hour": int(unit["ONT_FQ_END_HOUR"]),
                "ilmn_abs_error": None,
                "ont_abs_error": float(ont - target_ont),
                "coverage_source_ilmn": None,
                "coverage_source_rsr": source_relative(rsr_files[0], dayoa_root),
                "coverage_source_ont": source_relative(ont_files[0], dayoa_root),
                "dayoa_root": str(dayoa_root),
                "selection_status": "source",
            }
        )
    observations.sort(key=lambda row: (AU_INDEX[row["au"]], row["experiment"]))
    expected = {"p5xp5", "1x1", "3x3", "5x5", "10x5", "15x5", "15x10"}
    if {row["au"] for row in observations} != expected:
        raise ValueError(f"{experiment}: AU label set mismatch")
    return observations, {"inventory": inventory, "dayoa_root": dayoa_root, "bundle_root": bundle_root}


def read_direct_s3_coverage(path: Path) -> list[dict[str, str]]:
    """Read the bounded direct-S3 coverage capture used for every matrix coordinate."""
    fields = {
        "captured_at_utc",
        "experiment",
        "au",
        "analysis_unit_uid",
        "target_ilmn_x",
        "measured_sr_ilmn_x",
        "measured_rsr_ilmn_x",
        "target_ont_x",
        "measured_lr_ont_x",
        "source_s3_root",
        "sr_summary_s3_uri",
        "sr_summary_sha256",
        "rsr_summary_s3_uri",
        "rsr_summary_sha256",
        "lr_summary_s3_uri",
        "lr_summary_sha256",
    }
    rows = read_tsv(path)
    if len(rows) != 12:
        raise ValueError(f"expected 12 direct-S3 coverage rows, found {len(rows)}")
    if any(set(row) != fields for row in rows):
        raise ValueError(f"unexpected direct-S3 coverage schema: {path}")
    expected_counts = {"E1": 7, "E3": 4, "P1": 1}
    actual_counts = {experiment: sum(row["experiment"] == experiment for row in rows) for experiment in expected_counts}
    if actual_counts != expected_counts or any(row["experiment"] not in expected_counts for row in rows):
        raise ValueError(f"unexpected direct-S3 coverage experiment counts: {actual_counts}")
    keys = {(row["experiment"], row["analysis_unit_uid"]) for row in rows}
    if len(keys) != len(rows):
        raise ValueError("duplicate direct-S3 coverage identity")
    for row in rows:
        for field in ("measured_sr_ilmn_x", "measured_rsr_ilmn_x", "measured_lr_ont_x"):
            try:
                Decimal(row[field])
            except Exception as error:
                raise ValueError(f"invalid direct-S3 coverage {field}: {row[field]}") from error
        if any(len(row[field]) != 64 for field in ("sr_summary_sha256", "rsr_summary_sha256", "lr_summary_sha256")):
            raise ValueError(f"invalid direct-S3 summary hash for {row['experiment']}:{row['au']}")
    return rows


def apply_direct_s3_coverage(observations: list[dict[str, Any]], direct_rows: list[dict[str, str]]) -> None:
    """Overlay native-SR/LR coordinates and preserve RSR only as audit provenance."""
    direct_by_identity = {(row["experiment"], row["analysis_unit_uid"]): row for row in direct_rows}
    observation_keys = {(row["experiment"], row["runtime_au"]) for row in observations}
    if set(direct_by_identity) != observation_keys:
        raise ValueError("direct-S3 coverage identities do not match retained E1/E3/P1 evidence")
    for observation in observations:
        direct = direct_by_identity[(observation["experiment"], observation["runtime_au"])]
        expected_au = "fullcov" if observation["experiment"] == "P1" else observation["au"]
        if direct["au"] != expected_au:
            raise ValueError(f"direct-S3 AU mismatch for {observation['plot_label']}")
        for local_field, direct_field in (
            ("ilmn_measured_token", "measured_sr_ilmn_x"),
            ("rsr_measured_token", "measured_rsr_ilmn_x"),
            ("ont_measured_token", "measured_lr_ont_x"),
        ):
            local_value = observation.get(local_field)
            if local_value is not None and Decimal(str(local_value)) != Decimal(direct[direct_field]):
                raise ValueError(
                    f"{observation['plot_label']}: local {local_field}={local_value} disagrees with direct S3 {direct[direct_field]}"
                )
        for target_field, direct_field in (("ilmn_target", "target_ilmn_x"), ("ont_target", "target_ont_x")):
            target = observation[target_field]
            direct_target = direct[direct_field]
            if target is None:
                if direct_target != "NA":
                    raise ValueError(f"{observation['plot_label']}: direct S3 invented a target")
            elif Decimal(str(target)) != Decimal(direct_target):
                raise ValueError(f"{observation['plot_label']}: direct S3 target disagreement")
        sr = Decimal(direct["measured_sr_ilmn_x"])
        rsr = Decimal(direct["measured_rsr_ilmn_x"])
        lr = Decimal(direct["measured_lr_ont_x"])
        observation.update(
            {
                "ilmn_measured_token": direct["measured_sr_ilmn_x"],
                "ilmn_measured": float(sr),
                "rsr_measured_token": direct["measured_rsr_ilmn_x"],
                "rsr_measured": float(rsr),
                "ont_measured_token": direct["measured_lr_ont_x"],
                "ont_measured": float(lr),
                "ilmn_abs_error": float(sr - Decimal(str(observation["ilmn_target"]))) if observation["ilmn_target"] is not None else None,
                "ont_abs_error": float(lr - Decimal(str(observation["ont_target"]))) if observation["ont_target"] is not None else None,
                "coverage_source_ilmn": direct["sr_summary_s3_uri"],
                "coverage_source_rsr": direct["rsr_summary_s3_uri"],
                "coverage_source_ont": direct["lr_summary_s3_uri"],
                "direct_s3_captured_at": direct["captured_at_utc"],
                "evidence_captured_at": direct["captured_at_utc"],
                "coverage_capture_method": "direct completed-export S3 read",
                "snapshot_workflow_state": "completed export",
                "snapshot_controller_rc": 0,
                "benchmark_scope": "completed execution benchmark summary",
            }
        )


def deduplicate(source_observations: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for observation in source_observations:
        key = (observation["au"], observation["ilmn_measured_token"], observation["ont_measured_token"])
        groups[key].append(observation)

    retained: list[dict[str, Any]] = []
    resolutions: list[dict[str, Any]] = []
    all_with_status: list[dict[str, Any]] = []
    for key, group in groups.items():
        ordered = sorted(group, key=lambda row: row["experiment"], reverse=True)
        selected = ordered[0]
        selected = {**selected, "selection_status": "retained_latest" if len(group) > 1 else "retained_unique"}
        retained.append(selected)
        all_with_status.append(selected)
        for dropped in ordered[1:]:
            dropped_status = {**dropped, "selection_status": f"superseded_by_{selected['experiment']}"}
            all_with_status.append(dropped_status)
            resolutions.append(
                {
                    "au": key[0],
                    "ilmn_measured_token": key[1],
                    "ont_measured_token": key[2],
                    "dropped_experiment": dropped["experiment"],
                    "dropped_runtime_au": dropped["runtime_au"],
                    "retained_experiment": selected["experiment"],
                    "retained_runtime_au": selected["runtime_au"],
                    "reason": f"exact observation duplicate; newer {selected['experiment']} retained",
                }
            )
    retained.sort(key=lambda row: (row["ilmn_measured"], row["ont_measured"], AU_INDEX[row["au"]], row["experiment"]))
    all_with_status.sort(key=lambda row: (row["au"], row["ilmn_measured"], row["ont_measured"], row["experiment"]))
    return retained, resolutions, all_with_status


def coordinate_groups(observations: list[dict[str, Any]]) -> dict[tuple[float, float], list[dict[str, Any]]]:
    """Group only truly co-located native-SR×/LR× observations."""
    groups: dict[tuple[float, float], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        groups[(float(row["ilmn_measured"]), float(row["ont_measured"]))].append(row)
    for members in groups.values():
        members.sort(key=lambda row: (row["experiment"], AU_INDEX[row["au"]]))
    return groups


def coordinate_label_offsets(coordinates: Iterable[tuple[float, float]]) -> dict[tuple[float, float], tuple[float, float]]:
    """Nudge labels inside near-touching circles without moving data points."""
    ordered = sorted(set(coordinates))
    offsets = {coordinate: (0.0, 0.0) for coordinate in ordered}
    claimed: set[tuple[float, float]] = set()
    for index, first in enumerate(ordered):
        if first in claimed:
            continue
        for second in ordered[index + 1 :]:
            if second in claimed:
                continue
            first_sr, first_lr = first
            second_sr, second_lr = second
            delta_x = second_lr - first_lr
            delta_y = second_sr - first_sr
            distance = math.hypot(delta_x, delta_y)
            if not 0 < distance < 0.8:
                continue
            # Offset perpendicular to the line connecting the exact centers.
            # A 0.18× displacement remains within the 600 pt² circles but
            # separates labels at the E1 0.57×/1.16× LR pair.
            perpendicular_x = -delta_y / distance
            perpendicular_y = delta_x / distance
            amount = 0.18
            offsets[first] = (-perpendicular_x * amount, -perpendicular_y * amount)
            offsets[second] = (perpendicular_x * amount, perpendicular_y * amount)
            claimed.update((first, second))
            break
    return offsets


def configure_coverage_axes(ax: Any, observations: list[dict[str, Any]]) -> None:
    """Use a true numeric, equally scaled native-SR×/LR× coordinate system."""
    x_values = sorted({float(row["ont_measured"]) for row in observations})
    y_values = sorted({float(row["ilmn_measured"]) for row in observations})
    x_margin = max(0.6, (max(x_values) - min(x_values)) * 0.07)
    y_margin = max(0.8, (max(y_values) - min(y_values)) * 0.05)
    ax.set_xlim(min(x_values) - x_margin, max(x_values) + x_margin)
    ax.set_ylim(min(y_values) - y_margin, max(y_values) + y_margin)
    # Regular numeric ticks keep close measured values (for example 10.81× and
    # 10.97× native SR) from producing illegible overlapping tick labels. The
    # points remain at their exact unrounded coordinates and the exact values
    # are preserved in the linked TSVs and report sanity table.
    x_step = 2.5 if max(x_values) <= 25 else 5.0
    y_step = 5.0
    x_ticks = np.arange(0.0, math.ceil((max(x_values) + x_margin) / x_step) * x_step + x_step / 2, x_step)
    y_ticks = np.arange(0.0, math.ceil((max(y_values) + y_margin) / y_step) * y_step + y_step / 2, y_step)
    ax.set_xticks(x_ticks, [f"{value:g}×" for value in x_ticks], rotation=35, ha="right")
    ax.set_yticks(y_ticks, [f"{value:g}×" for value in y_ticks])
    ax.tick_params(axis="both", labelsize=heatmap_font_size(11))
    ax.set_xlabel("Measured ONT LR coverage (Mosdepth total mean)", fontsize=heatmap_font_size(14))
    ax.set_ylabel("Measured Illumina native SR coverage (Mosdepth total mean)", fontsize=heatmap_font_size(14))
    ax.set_aspect("equal", adjustable="box")
    ax.grid(color="#d6d9de", linewidth=0.65, alpha=0.85)
    ax.set_axisbelow(True)


def overlay_coordinate_density(ax: Any, observations: list[dict[str, Any]]) -> None:
    """Overlay observed-AU coordinate density without interpolating any metric.

    The dashed contours are a fixed-bandwidth two-dimensional kernel density
    estimate over individual retained AU coordinates. Co-located AUs each
    contribute one kernel, so the contour reflects observation density rather
    than the color-mapped quality metric. This intentionally does not infer a
    metric value for any unobserved coverage coordinate.
    """
    if len(observations) < 2:
        return
    x_values = np.array([float(row["ont_measured"]) for row in observations], dtype=float)
    y_values = np.array([float(row["ilmn_measured"]) for row in observations], dtype=float)
    x_grid = np.linspace(*ax.get_xlim(), DENSITY_GRID_SIZE)
    y_grid = np.linspace(*ax.get_ylim(), DENSITY_GRID_SIZE)
    x_mesh, y_mesh = np.meshgrid(x_grid, y_grid)
    density = np.zeros_like(x_mesh)
    for x_value, y_value in zip(x_values, y_values):
        density += np.exp(
            -0.5
            * (
                ((x_mesh - x_value) / DENSITY_KERNEL_BANDWIDTH_X) ** 2
                + ((y_mesh - y_value) / DENSITY_KERNEL_BANDWIDTH_Y) ** 2
            )
        )
    peak = float(np.max(density))
    if not math.isfinite(peak) or peak <= 0:
        return
    ax.contour(
        x_mesh,
        y_mesh,
        density,
        levels=[peak * fraction for fraction in (0.20, 0.45, 0.70)],
        colors="#374151",
        linewidths=0.8,
        linestyles="--",
        alpha=0.52,
        zorder=3.5,
    )


def save_figure(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220, bbox_inches="tight", metadata={"Software": "HG002 combined report generator"})
    plt.close(fig)


def coverage_grid(observations: list[dict[str, Any]], figures: Path, tables: Path, chart_map: list[dict[str, str]]) -> None:
    groups = coordinate_groups(observations)
    label_offsets = coordinate_label_offsets(groups)
    fig, ax = plt.subplots(figsize=(11.5, 20), constrained_layout=True)
    configure_coverage_axes(ax, observations)
    ax.set_title("Measured native-SR × LR coverage availability", pad=14, fontsize=heatmap_font_size(17))
    for (sr, lr), members in sorted(groups.items()):
        ax.scatter(lr, sr, marker="o", s=CIRCLE_MARKER_AREA, facecolor="#dbeaf4", edgecolors="none", linewidths=0, zorder=3)
    overlay_coordinate_density(ax, observations)
    for (sr, lr), members in sorted(groups.items()):
        offset_x, offset_y = label_offsets[(sr, lr)]
        ax.text(lr + offset_x, sr + offset_y, f"n={len(members)}", ha="center", va="center", fontsize=heatmap_font_size(CIRCLE_LABEL_FONTSIZE), color="#111827", zorder=4)
    ax.text(
        0.02,
        0.015,
        "Circle centers use equal-scale numeric axes. In-circle n is the retained-observation count; dashed contours are AU-coordinate density, not an inferred metric surface.",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=heatmap_font_size(8.5),
        color="#374151",
        bbox={"boxstyle": "round,pad=0.28", "facecolor": "white", "edgecolor": "#9ca3af", "alpha": 0.92, "linewidth": 0.6},
    )
    output = figures / "combined_measured_coverage_grid.png"
    save_figure(fig, output)
    chart_map.append(
        {
            "figure": output.name,
            "chart_type": "heatmap",
            "title": "Measured native-SR × LR coverage availability",
            "source_table": "coverage_grid.tsv",
            "metric": "retained observation occupancy",
        }
    )
    coordinate_rows = [
        {
            "measured_native_sr_ilmn_x": f"{sr:g}",
            "measured_lr_ont_x": f"{lr:g}",
            "retained_observation_count": str(len(members)),
            "observations": "; ".join(member["plot_label"] for member in members),
        }
        for (sr, lr), members in sorted(groups.items())
    ]
    write_tsv(tables / "coverage_grid.tsv", coordinate_rows, ["measured_native_sr_ilmn_x", "measured_lr_ont_x", "retained_observation_count", "observations"])


def plot_metric_heatmap(
    observations: list[dict[str, Any]],
    metric_rows: list[dict[str, Any]],
    value_field: str,
    title: str,
    filename: str,
    value_format: str,
    cmap_name: str,
    cbar_label: str,
    figures: Path,
    source_table: str,
    chart_map: list[dict[str, str]],
) -> None:
    by_observation = {row["observation_id"]: row for row in metric_rows}
    groups = coordinate_groups(observations)
    label_offsets = coordinate_label_offsets(groups)
    values_by_coordinate: dict[tuple[float, float], list[float]] = {}
    for key, members in groups.items():
        values: list[float] = []
        for member in members:
            row = by_observation.get(member["observation_id"])
            value = number(row.get(value_field)) if row else None
            if value is not None:
                values.append(value)
        values_by_coordinate[key] = values

    valid = np.array([value for values in values_by_coordinate.values() for value in values], dtype=float)
    if not len(valid):
        raise ValueError(f"no numeric values for heatmap {filename}")
    vmin, vmax = float(valid.min()), float(valid.max())
    if vmin == vmax:
        vmin -= 0.5 if value_field in {"fn", "fp"} else 0.01
        vmax += 0.5 if value_field in {"fn", "fp"} else 0.01
    cmap = plt.get_cmap(cmap_name).copy()
    cmap.set_bad("#f0f1f2")
    fig, ax = plt.subplots(figsize=(12.5, 20), constrained_layout=True)
    configure_coverage_axes(ax, observations)
    ax.set_title(f"{title} — numeric native-SR × LR coordinates", pad=14, fontsize=heatmap_font_size(17))
    colored_x: list[float] = []
    colored_y: list[float] = []
    colored_values: list[float] = []
    for (sr, lr), values in values_by_coordinate.items():
        if values:
            colored_x.append(lr)
            colored_y.append(sr)
            colored_values.append(float(np.mean(values)))
        else:
            ax.scatter(lr, sr, marker="o", s=CIRCLE_MARKER_AREA, facecolor="#f0f1f2", edgecolors="none", linewidths=0, zorder=3)
    image = ax.scatter(colored_x, colored_y, c=colored_values, marker="o", s=CIRCLE_MARKER_AREA, cmap=cmap, vmin=vmin, vmax=vmax, edgecolors="none", linewidths=0, alpha=0.9, zorder=3)
    overlay_coordinate_density(ax, observations)
    for (sr, lr), values in sorted(values_by_coordinate.items()):
        offset_x, offset_y = label_offsets[(sr, lr)]
        if values:
            value = float(np.mean(values))
            ax.text(lr + offset_x, sr + offset_y, value_format.format(value), ha="center", va="center", fontsize=heatmap_font_size(CIRCLE_LABEL_FONTSIZE), color=marker_label_color(cmap, image.norm, value), zorder=4)
        else:
            ax.text(lr + offset_x, sr + offset_y, "NA", ha="center", va="center", fontsize=heatmap_font_size(CIRCLE_LABEL_FONTSIZE), color="#4b5563", zorder=4)
    ax.text(
        0.02,
        0.015,
        "Dashed contours = 2D density of retained AU coordinates, independent of metric color; no metric is interpolated into blank space.",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=heatmap_font_size(8.0),
        color="#374151",
        bbox={"boxstyle": "round,pad=0.28", "facecolor": "white", "edgecolor": "#9ca3af", "alpha": 0.92, "linewidth": 0.6},
        zorder=5,
    )
    bar = fig.colorbar(image, ax=ax, shrink=0.76, pad=0.02)
    style_heatmap_colorbar(bar, cbar_label)
    output = figures / filename
    save_figure(fig, output)
    chart_map.append({"figure": filename, "chart_type": "heatmap", "title": title, "source_table": source_table, "metric": value_field})


def hard_vcf_metrics(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for observation in observations:
        if "compact_evidence" in observation:
            payload = observation["compact_evidence"]["hard_vcf"][observation["runtime_au"]]
            source = {row["VariantClass"]: row for row in payload["rows"] if row["ROI"] == "giabHC"}
            source_path = payload["source_path"]
        else:
            dayoa_root = Path(observation["dayoa_root"])
            unit_root = dayoa_root / "results/day/hg38" / observation["runtime_au"]
            files = list(unit_root.glob("align/sentmm2ont/na/snv/sentdhiomr2/concordance/_giabHC/*_concordance.mqc.tsv"))
            if len(files) != 1:
                raise ValueError(f"expected one hard-VCF GIAB-HC file for {observation['plot_label']}")
            source = {row["VariantClass"]: row for row in read_tsv(files[0]) if row["ROI"] == "giabHC"}
            source_path = source_relative(files[0], dayoa_root)
        for klass in ("SNP", "INS_50", "DEL_50"):
            if klass == "SNP":
                components = [source["SNPts"], source["SNPtv"]]
                tp = float(components[0]["TP"]) + float(components[1]["TP"]) / 2
                fn = float(components[0]["FN"]) + float(components[1]["FN"]) / 2
                fp = float(components[0]["FP"]) + float(components[1]["FP"]) / 2
            else:
                component = source[klass]
                tp, fn, fp = (float(component[name]) for name in ("TP", "FN", "FP"))
            precision = tp / (tp + fp) if tp + fp else None
            recall = tp / (tp + fn) if tp + fn else None
            fscore = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
            rows.append(
                {
                    **{key: observation[key] for key in ("experiment", "analysis_id", "au", "runtime_au", "plot_label", "ilmn_measured_token", "ont_measured_token")},
                    "observation_id": observation["observation_id"],
                    "class": klass,
                    "tp": tp,
                    "fn": fn,
                    "fp": fp,
                    "precision": precision,
                    "recall": recall,
                    "fscore": fscore,
                    "roi": "giabHC",
                    "source_path": source_path,
                }
            )
    return rows


def hard_vcf_plots(observations: list[dict[str, Any]], rows: list[dict[str, Any]], figures: Path, chart_map: list[dict[str, str]]) -> None:
    for klass in ("SNP", "INS_50", "DEL_50"):
        subset = [row for row in rows if row["class"] == klass]
        title_class = "SNP (SNPts + SNPtv/2)" if klass == "SNP" else klass
        token = klass.lower()
        for metric, title_metric, value_format, cmap, cbar in (
            ("fscore", "F-score", "{:.4f}", "viridis", "F-score"),
            ("fn", "false negatives", "{:,.0f}", "magma_r", "FN count"),
            ("fp", "false positives", "{:,.0f}", "magma_r", "FP count"),
        ):
            plot_metric_heatmap(
                observations,
                subset,
                metric,
                f"Combined hard-VCF GIAB-HC {title_class}: {title_metric}",
                f"hard_vcf_giabhc_{token}_{metric}_heatmap.png",
                value_format,
                cmap,
                cbar,
                figures,
                "hard_vcf_giabhc_metrics.tsv",
                chart_map,
            )

        fig, ax = plt.subplots(figsize=(15, 10), constrained_layout=True)
        plotted_points = [row for row in subset if row["precision"] is not None and row["recall"] is not None]
        ax.scatter(
            [row["recall"] for row in plotted_points],
            [row["precision"] for row in plotted_points],
            s=88,
            marker="o",
            color="#315f88",
            edgecolor="#20242a",
            linewidth=0.6,
            alpha=0.82,
        )
        annotate_point_labels(
            ax,
            plotted_points,
            "recall",
            "precision",
            coverage_group_label,
            7.0,
        )
        ax.set_title(f"Combined hard-VCF GIAB-HC {title_class}: precision versus recall")
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision")
        ax.grid(alpha=0.25)
        output = figures / f"hard_vcf_giabhc_{token}_precision_recall.png"
        save_figure(fig, output)
        chart_map.append({"figure": output.name, "chart_type": "scatter", "title": ax.get_title(), "source_table": "hard_vcf_giabhc_metrics.tsv", "metric": "precision versus recall"})


def truvari_metrics(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    caller_names = {"tagged_trussv": "TrussSV", "sniffles2": "Sniffles2", "longreadsv": "LongReadSV", "tiddit": "TIDDIT"}
    rows: list[dict[str, Any]] = []
    for observation in observations:
        if "compact_evidence" in observation:
            summaries = observation["compact_evidence"]["truvari"][observation["runtime_au"]]
            iterable = [(entry["caller"], entry["summary"], entry["source_path"]) for entry in summaries]
        else:
            dayoa_root = Path(observation["dayoa_root"])
            unit_root = dayoa_root / "results/day/hg38" / observation["runtime_au"]
            files = sorted(unit_root.glob("align/sentmm2ont/na/snv/sentdhiomr2/slim-consensus/truari/*"))
            if files:
                raise AssertionError("misspelled Truvari directory unexpectedly exists")
            summaries = sorted(unit_root.glob("align/sentmm2ont/na/snv/sentdhiomr2/slim-consensus/truvari/*/queries/*/truvari/summary.json"))
            if len(summaries) != 4:
                raise ValueError(f"expected four raw Truvari summaries for {observation['plot_label']}; found {len(summaries)}")
            iterable = [(caller_names.get(path.parents[1].name, path.parents[1].name), json.loads(path.read_text()), source_relative(path, dayoa_root)) for path in summaries]
        if len(iterable) != 4:
            raise ValueError(f"expected four raw Truvari summaries for {observation['plot_label']}; found {len(iterable)}")
        for caller, data, source_path in iterable:
            rows.append(
                {
                    **{key: observation[key] for key in ("experiment", "analysis_id", "au", "runtime_au", "plot_label", "ilmn_measured_token", "ont_measured_token")},
                    "observation_id": observation["observation_id"],
                    "caller": caller,
                    "tp_base": data.get("TP-base"),
                    "tp_comp": data.get("TP-comp"),
                    "fn": data.get("FN"),
                    "fp": data.get("FP"),
                    "precision": data.get("precision"),
                    "recall": data.get("recall"),
                    "fscore": data.get("f1"),
                    "gt_concordance": data.get("gt_concordance"),
                    "base_count": data.get("base cnt"),
                    "query_count": data.get("comp cnt"),
                    "source_path": source_path,
                }
            )
    return rows


def truvari_plots(observations: list[dict[str, Any]], rows: list[dict[str, Any]], figures: Path, chart_map: list[dict[str, str]]) -> None:
    trussv = [row for row in rows if row["caller"] == "TrussSV"]
    for metric, title, filename, cmap, cbar in (
        ("fscore", "Combined Truvari tagged TrussSV: global F-score", "truvari_trussv_global_fscore_heatmap.png", "viridis", "F-score"),
        ("gt_concordance", "Combined Truvari tagged TrussSV: genotype concordance", "truvari_trussv_gt_concordance_heatmap.png", "plasma", "GT concordance"),
    ):
        plot_metric_heatmap(observations, trussv, metric, title, filename, "{:.4f}", cmap, cbar, figures, "truvari_metrics.tsv", chart_map)

    plotted_points = [
        row
        for row in rows
        if number(row["precision"]) is not None
        and number(row["recall"]) is not None
        and number(row["ilmn_measured_token"]) is not None
        and number(row["ont_measured_token"]) is not None
    ]
    callers = sorted({row["caller"] for row in plotted_points})
    coverage_values = [float(row["ilmn_measured_token"]) + float(row["ont_measured_token"]) for row in plotted_points]
    coverage_norm = Normalize(vmin=min(coverage_values), vmax=max(coverage_values))
    coverage_cmap = LinearSegmentedColormap.from_list(
        "measured_total_coverage",
        ["#f6d746", "#f28e2b", "#9b4f96", "#173f5f"],
    )
    fig, ax = plt.subplots(figsize=(21, 17), constrained_layout=True)
    for caller in callers:
        marker = CALLER_STYLES.get(caller, ("#555555", "o"))[1]
        points = [row for row in plotted_points if row["caller"] == caller]
        ax.scatter(
            [row["recall"] for row in points],
            [row["precision"] for row in points],
            c=[float(row["ilmn_measured_token"]) + float(row["ont_measured_token"]) for row in points],
            cmap=coverage_cmap,
            norm=coverage_norm,
            s=82,
            marker=marker,
            edgecolors="#20242a",
            linewidth=0.7,
            alpha=0.82,
            label=caller,
        )
    sv_annotations = annotate_point_labels(
        ax,
        plotted_points,
        "recall",
        "precision",
        lambda group: "F=" + fmt(group[0]["fscore"], 3),
        13.77,
        offset_scale=2.2,
    )
    ax.set_xlabel("Recall", fontsize=47.6)
    ax.set_ylabel("Precision", fontsize=47.6)
    ax.tick_params(axis="both", labelsize=37.4)
    ax.margins(x=0.055, y=0.08)
    ax.grid(alpha=0.22)
    legend_handles = [Line2D([0], [0], marker=CALLER_STYLES.get(caller, ("", "o"))[1], color="none", markerfacecolor="#6b7280", markeredgecolor="#20242a", markersize=8, label=caller) for caller in callers]
    ax.legend(handles=legend_handles, fontsize=17, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    coverage_mappable = matplotlib.cm.ScalarMappable(norm=coverage_norm, cmap=coverage_cmap)
    coverage_bar = fig.colorbar(coverage_mappable, ax=ax, shrink=0.76, pad=0.025)
    coverage_bar.set_label("Measured coverage (ILMN SRx + ONTx)", fontsize=28)
    coverage_bar.ax.tick_params(labelsize=24)
    ax.set_title("Structural-variant precision versus recall — all callers", fontsize=68)
    relax_annotation_collisions(fig, ax, sv_annotations, iterations=200)
    output = figures / "truvari_all_callers_precision_recall.png"
    save_figure(fig, output)
    chart_map.append({"figure": output.name, "chart_type": "scatter", "title": "Structural-variant precision versus recall — all callers", "source_table": "truvari_metrics.tsv", "metric": "precision versus recall"})

    scored_rows = [
        row
        for row in rows
        if number(row["fscore"]) is not None
        and number(row["ilmn_measured_token"]) is not None
        and number(row["ont_measured_token"]) is not None
    ]
    highest_pair = max(
        (float(row["ilmn_measured_token"]), float(row["ont_measured_token"]))
        for row in scored_rows
    )
    highest_rows = [
        row
        for row in scored_rows
        if (float(row["ilmn_measured_token"]), float(row["ont_measured_token"])) == highest_pair
    ]
    expected_callers = {"LongReadSV", "Sniffles2", "TIDDIT", "TrussSV"}
    if len(highest_rows) != 4 or {row["caller"] for row in highest_rows} != expected_callers:
        raise ValueError(
            "Highest measured ILMN-SR/ONT coverage pair must contain exactly one F-score for each SV caller"
        )
    technology = {
        "TIDDIT": "SHORT READ",
        "LongReadSV": "LONG READ",
        "Sniffles2": "LONG READ",
        "TrussSV": "ENSEMBLE",
    }
    caller_order = ["Sniffles2", "LongReadSV", "TrussSV", "TIDDIT"]
    highest_by_caller = {row["caller"]: row for row in highest_rows}
    fig, ax = plt.subplots(figsize=(11, 10), constrained_layout=True)
    legend_handles: list[Any] = []
    for caller in caller_order:
        row = highest_by_caller[caller]
        color, marker = CALLER_STYLES[caller]
        fscore = float(row["fscore"])
        precision = float(row["precision"])
        recall = float(row["recall"])
        ax.scatter(
            recall,
            precision,
            s=340,
            marker=marker,
            facecolor=color,
            edgecolor="#20242a",
            linewidth=1.2,
            zorder=3,
        )
        ax.annotate(
            f"F={fscore:.4f}",
            (recall, precision),
            xytext=(13, 10),
            textcoords="offset points",
            va="bottom",
            fontsize=18,
            color="#111827",
        )
        legend_handles.append(
            Line2D(
                [0],
                [0],
                marker=marker,
                color="none",
                markerfacecolor=color,
                markeredgecolor="#20242a",
                markersize=12,
                label=f"{caller} — {technology[caller]}",
            )
        )
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("Recall", fontsize=19)
    ax.set_ylabel("Precision", fontsize=19)
    ax.tick_params(axis="both", labelsize=15)
    ax.grid(alpha=0.22)
    ax.legend(handles=legend_handles, fontsize=13, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.10))
    ax.set_title(
        "Highest-coverage SV precision versus recall\n"
        f"HG002 — {highest_pair[0]:g}× ILMN SR / {highest_pair[1]:g}× ONT",
        fontsize=24,
        pad=18,
    )
    output = figures / "truvari_highest_coverage_caller_fscore.png"
    save_figure(fig, output)
    chart_map.append(
        {
            "figure": output.name,
            "chart_type": "scatter",
            "title": "Highest-coverage SV precision versus recall",
            "source_table": "truvari_metrics.tsv",
            "metric": "precision versus recall with F-score labels at maximum measured ILMN-SR/ONT coverage",
        }
    )


def coverage_plots(observations: list[dict[str, Any]], figures: Path, chart_map: list[dict[str, str]]) -> None:
    fig, ax = plt.subplots(figsize=(12, 8), constrained_layout=True)
    for experiment in EXPERIMENTS:
        subset = sorted([row for row in observations if row["experiment"] == experiment], key=lambda row: (row["ont_end_hour"], row["au"]))
        grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in subset:
            grouped[row["ont_end_hour"]].append(row)
        hours = sorted(grouped)
        means = [float(np.mean([row["ont_measured"] for row in grouped[hour]])) for hour in hours]
        ax.plot(hours, means, color=EXPERIMENT_COLORS[experiment], linewidth=1.8, alpha=0.7)
        for row in subset:
            ax.scatter(row["ont_end_hour"], row["ont_measured"], color=EXPERIMENT_COLORS[experiment], marker=EXPERIMENT_MARKERS[experiment], s=78, edgecolor="#222", linewidth=0.5)
            ax.annotate(f"{row['plot_label']}\n{row['ont_measured_token']}x", (row["ont_end_hour"], row["ont_measured"]), xytext=(5, 5), textcoords="offset points", fontsize=8.2)
    ax.set_title("Combined ONT aligned coverage versus cumulative input runtime")
    ax.set_xlabel("ONT end hour for cumulative [0,end) input")
    ax.set_ylabel("Measured ONT coverage (Mosdepth total mean)")
    ax.grid(alpha=0.22)
    ax.legend(handles=[Line2D([0], [0], color=EXPERIMENT_COLORS[e], marker=EXPERIMENT_MARKERS[e], label=e) for e in EXPERIMENTS])
    output = figures / "ont_coverage_vs_runtime.png"
    save_figure(fig, output)
    chart_map.append({"figure": output.name, "chart_type": "line-scatter", "title": ax.get_title(), "source_table": "retained_observations.tsv", "metric": "ONT coverage and end hour"})


def parse_vcf_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with gzip.open(path, "rt") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 10:
                continue
            fmt_keys = fields[8].split(":")
            sample_values = fields[9].split(":")
            sample = dict(zip(fmt_keys, sample_values))
            gt = sample.get("GT", "NA")
            alleles = re.split(r"[/|]", gt)
            non_reference = any(allele not in {"0", ".", ""} for allele in alleles)
            if not non_reference:
                continue
            records.append({"chrom": fields[0], "pos": fields[1], "ref": fields[3], "alt": fields[4], "qual": fields[5], "filter": fields[6], "gt": gt})
    return records


def call_tables_and_plots(observations: list[dict[str, Any]], figures: Path, chart_map: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    parsed_segdup: dict[tuple[str, str], list[dict[str, Any]]] = {}
    genes: set[str] = set()
    smn_rows: list[dict[str, Any]] = []
    for observation in observations:
        if "compact_evidence" in observation:
            compact = observation["compact_evidence"]
            for gene, summary in compact["segdup"][observation["runtime_au"]].items():
                genes.add(gene)
                empty_record = {"chrom": None, "pos": None, "ref": None, "alt": None, "qual": None, "gt": None}
                parsed_segdup[(observation["observation_id"], gene)] = [
                    {**empty_record, "filter": "PASS"} for _ in range(int(summary["pass_count"]))
                ] + [{**empty_record, "filter": "non_PASS"} for _ in range(int(summary["failed_count"]))]
            smn_summary = compact["smn12"][observation["runtime_au"]]
            payload = smn_summary["payload"]
            smn_source_path = smn_summary["source_path"]
        else:
            dayoa_root = Path(observation["dayoa_root"])
            unit_root = dayoa_root / "results/day/hg38" / observation["runtime_au"]
            vcf_files = sorted(unit_root.glob("align/sentmm2ont/na/snv/sentdhiomr2/segdup/*/*/*.result.vcf.gz"))
            if not vcf_files:
                raise ValueError(f"no SegDup VCFs for {observation['plot_label']}")
            for path in vcf_files:
                gene = path.parent.name
                genes.add(gene)
                parsed_segdup[(observation["observation_id"], gene)] = parse_vcf_records(path)
            smn_files = list(unit_root.glob("align/sentdhiomr2sr/smd/htd/smn12/*.summary.json"))
            if len(smn_files) != 1:
                raise ValueError(f"expected one SMN12 summary for {observation['plot_label']}")
            payload = json.loads(smn_files[0].read_text())
            smn_source_path = source_relative(smn_files[0], dayoa_root)
        values = next(iter(payload.values()))
        smn_rows.append(
            {
                **{key: observation[key] for key in ("experiment", "analysis_id", "au", "runtime_au", "plot_label", "ilmn_measured_token", "ont_measured_token")},
                "observation_id": observation["observation_id"],
                "SMN1_CN": values.get("SMN1"),
                "SMN2_CN": values.get("SMN2"),
                "SMN2delta7_8_CN": values.get("SMN2delta78"),
                "Total_CN_raw": values.get("Total_CN_raw"),
                "Full_length_CN_raw": values.get("Full_length_CN_raw"),
                "g27134TG_CN": values.get("g27134TG_CN"),
                "isSMA": values.get("isSMA"),
                "isCarrier": values.get("isCarrier"),
                "Info": values.get("Info"),
                "Median_depth": values.get("Median_depth"),
                "source_path": smn_source_path,
            }
        )

    gene_order = sorted(genes)
    segdup_rows: list[dict[str, Any]] = []
    for observation in observations:
        for gene in gene_order:
            records = parsed_segdup.get((observation["observation_id"], gene), [])
            if not records:
                segdup_rows.append(
                    {
                        **{key: observation[key] for key in ("experiment", "analysis_id", "au", "runtime_au", "plot_label", "ilmn_measured_token", "ont_measured_token")},
                        "observation_id": observation["observation_id"],
                        "gene": gene,
                        "call_state": "NA",
                        "chrom": None,
                        "pos": None,
                        "ref": None,
                        "alt": None,
                        "filter": None,
                        "gt": None,
                        "qual": None,
                    }
                )
            else:
                for record in records:
                    segdup_rows.append(
                        {
                            **{key: observation[key] for key in ("experiment", "analysis_id", "au", "runtime_au", "plot_label", "ilmn_measured_token", "ont_measured_token")},
                            "observation_id": observation["observation_id"],
                            "gene": gene,
                            "call_state": "non_reference_call",
                            **record,
                        }
                    )

    obs_order = sorted(observations, key=lambda row: (row["ilmn_measured"], row["ont_measured"], row["experiment"], AU_INDEX[row["au"]]))
    groups = coordinate_groups(observations)
    label_offsets = coordinate_label_offsets(groups)
    summary: dict[tuple[str, str], tuple[int, int]] = {}
    for observation in obs_order:
        for gene in gene_order:
            calls = [row for row in segdup_rows if row["observation_id"] == observation["observation_id"] and row["gene"] == gene and row["call_state"] == "non_reference_call"]
            summary[(observation["observation_id"], gene)] = (sum(row["filter"] == "PASS" for row in calls), sum(row["filter"] != "PASS" for row in calls))
    cmap = LinearSegmentedColormap.from_list("segdup", ["#f0f1f2", "#c5daea", "#3977a8", "#213f5a"])
    maximum_calls = max(1, max(sum(summary[(obs["observation_id"], gene)]) for obs in obs_order for gene in gene_order))
    ncols = min(2, len(gene_order))
    nrows = math.ceil(len(gene_order) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(18, max(12, nrows * 13)), constrained_layout=True)
    axes = np.atleast_1d(axes).ravel()
    image = None
    for ax, gene in zip(axes, gene_order):
        configure_coverage_axes(ax, observations)
        ax.set_title(f"{gene}: non-reference SegDup calls", fontsize=heatmap_font_size(12))
        coordinates = sorted(groups)
        counts = [
            float(np.mean([sum(summary[(observation["observation_id"], gene)]) for observation in groups[coordinate]]))
            for coordinate in coordinates
        ]
        image = ax.scatter(
            [lr for _, lr in coordinates],
            [sr for sr, _ in coordinates],
            c=counts,
            marker="o",
            s=CIRCLE_MARKER_AREA,
            cmap=cmap,
            vmin=0,
            vmax=maximum_calls,
            edgecolors="none",
            linewidths=0,
            alpha=0.9,
            zorder=3,
        )
        overlay_coordinate_density(ax, observations)
        for (sr, lr), count in zip(coordinates, counts):
            offset_x, offset_y = label_offsets[(sr, lr)]
            ax.text(lr + offset_x, sr + offset_y, f"{count:g}", ha="center", va="center", fontsize=heatmap_font_size(CIRCLE_LABEL_FONTSIZE), color=marker_label_color(cmap, image.norm, count), zorder=4)
    for ax in axes[len(gene_order):]:
        ax.set_visible(False)
    fig.suptitle("SegDup calls at measured native-SR × LR coordinates\nDashed contours = retained-AU coordinate density, not a metric interpolation", fontsize=heatmap_font_size(18))
    if image is None:
        raise AssertionError("SegDup numeric-coordinate heatmap has no panels")
    bar = fig.colorbar(image, ax=list(axes[:len(gene_order)]), shrink=0.76, pad=0.02)
    style_heatmap_colorbar(bar, "Non-reference VCF record count")
    output = figures / "segdup_call_heatmap.png"
    save_figure(fig, output)
    chart_map.append({"figure": output.name, "chart_type": "heatmap", "title": "SegDup calls at measured native-SR × LR coordinates", "source_table": "segdup_calls.tsv", "metric": "non-reference record count"})

    metrics = ["SMN1_CN", "SMN2_CN", "SMN2delta7_8_CN"]
    smn_by_obs = {row["observation_id"]: row for row in smn_rows}
    smn_cmap = plt.get_cmap("YlGnBu").copy()
    smn_cmap.set_bad("#f0f1f2")
    valid = [number(smn_by_obs[observation["observation_id"]][metric]) for metric in metrics for observation in obs_order]
    valid = [value for value in valid if value is not None]
    fig, axes = plt.subplots(1, len(metrics), figsize=(27, 18), constrained_layout=True)
    image = None
    labels = {"SMN1_CN": "SMN1 copy number", "SMN2_CN": "SMN2 copy number", "SMN2delta7_8_CN": "SMN2 Δ7–8 copy number"}
    for ax, metric in zip(np.atleast_1d(axes).ravel(), metrics):
        configure_coverage_axes(ax, observations)
        ax.set_title(labels[metric], fontsize=heatmap_font_size(12))
        coordinate_values = {
            coordinate: [
                value
                for observation in members
                if (value := number(smn_by_obs[observation["observation_id"]][metric])) is not None
            ]
            for coordinate, members in groups.items()
        }
        numeric_coordinates = [coordinate for coordinate in sorted(groups) if coordinate_values[coordinate]]
        missing_coordinates = [coordinate for coordinate in sorted(groups) if not coordinate_values[coordinate]]
        image = ax.scatter(
            [lr for _, lr in numeric_coordinates],
            [sr for sr, _ in numeric_coordinates],
            c=[float(np.mean(coordinate_values[coordinate])) for coordinate in numeric_coordinates],
            marker="o",
            s=CIRCLE_MARKER_AREA,
            cmap=smn_cmap,
            vmin=0,
            vmax=max(4, float(max(valid)) if valid else 4),
            edgecolors="none",
            linewidths=0,
            alpha=0.9,
            zorder=3,
        )
        for sr, lr in missing_coordinates:
            ax.scatter(lr, sr, marker="o", s=CIRCLE_MARKER_AREA, facecolor="#f0f1f2", edgecolors="none", linewidths=0, zorder=3)
        overlay_coordinate_density(ax, observations)
        for sr, lr in missing_coordinates:
            offset_x, offset_y = label_offsets[(sr, lr)]
            ax.text(lr + offset_x, sr + offset_y, "NA", ha="center", va="center", fontsize=heatmap_font_size(CIRCLE_LABEL_FONTSIZE), color="#4b5563", zorder=4)
        for coordinate in numeric_coordinates:
            value = float(np.mean(coordinate_values[coordinate]))
            sr, lr = coordinate
            offset_x, offset_y = label_offsets[coordinate]
            ax.text(lr + offset_x, sr + offset_y, f"{value:g}", ha="center", va="center", fontsize=heatmap_font_size(CIRCLE_LABEL_FONTSIZE), color=marker_label_color(smn_cmap, image.norm, value), zorder=4)
    fig.suptitle("SMN copy-number calls at measured native-SR × LR coordinates\nDashed contours = retained-AU coordinate density, not a metric interpolation", fontsize=heatmap_font_size(18))
    if image is None:
        raise AssertionError("SMN numeric-coordinate heatmap has no panels")
    bar = fig.colorbar(image, ax=list(np.atleast_1d(axes).ravel()), shrink=0.74, pad=0.02)
    style_heatmap_colorbar(bar, "Copy-number call")
    output = figures / "smn12_copy_number_heatmap.png"
    save_figure(fig, output)
    chart_map.append({"figure": output.name, "chart_type": "heatmap", "title": "SMN copy-number calls at measured native-SR × LR coordinates", "source_table": "smn12_calls.tsv", "metric": "SMN1 SMN2 copy number"})
    return segdup_rows, smn_rows


def interval_union_hours(intervals: list[tuple[datetime, datetime]]) -> float:
    if not intervals:
        return 0.0
    intervals = sorted(intervals)
    total = 0.0
    start, end = intervals[0]
    for next_start, next_end in intervals[1:]:
        if next_start <= end:
            end = max(end, next_end)
        else:
            total += (end - start).total_seconds()
            start, end = next_start, next_end
    total += (end - start).total_seconds()
    return total / 3600


def benchmark_data(observations: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    retained = {(row["experiment"], row["runtime_au"]): row for row in observations}
    raw_by_obs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for experiment in EXPERIMENTS:
        exemplar = next(row for row in observations if row["experiment"] == experiment)
        raw_records = exemplar["compact_evidence"]["benchmarks"] if "compact_evidence" in exemplar else read_tsv(Path(exemplar["dayoa_root"]) / "results/day/hg38/reports/benchmarks_summary.tsv")
        for raw in raw_records:
            runtime = raw["sample"].rstrip(".")
            observation = retained.get((experiment, runtime))
            if observation is None or raw.get("status") != "success":
                continue
            row = dict(raw)
            row["observation"] = observation
            raw_by_obs[observation["observation_id"]].append(row)

    task_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for observation in observations:
        raw_rows = raw_by_obs[observation["observation_id"]]
        if not raw_rows:
            raise ValueError(f"no successful benchmark rows for {observation['plot_label']}")
        by_rule: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in raw_rows:
            by_rule[row["rule"]].append(row)
        for rule, grouped in by_rule.items():
            priced_costs = [value for row in grouped if (value := number(row.get("task_cost"))) is not None]
            allocated_vcpu_values = [
                seconds * threads / 3600
                for row in grouped
                if (seconds := number(row.get("s"))) is not None
                and (threads := number(row.get("snakemake_threads"))) is not None
            ]
            observed_cpu_values = [value / 3600 for row in grouped if (value := number(row.get("cpu_time"))) is not None]
            task_rows.append(
                {
                    **{key: observation[key] for key in ("experiment", "analysis_id", "au", "runtime_au", "plot_label", "ilmn_measured_token", "ont_measured_token")},
                    "observation_id": observation["observation_id"],
                    "rule": rule,
                    "successful_records": len(grouped),
                    "priced_records": len(priced_costs),
                    "unpriced_records": len(grouped) - len(priced_costs),
                    "longest_walltime_s": max(float(row["s"]) for row in grouped),
                    "total_cost_usd": sum(priced_costs),
                    "allocated_vcpu_h": sum(allocated_vcpu_values),
                    "observed_cpu_h": sum(observed_cpu_values),
                    "benchmark_scope": observation.get("benchmark_scope", "completed execution benchmark summary"),
                }
            )
        intervals: list[tuple[datetime, datetime]] = []
        for row in raw_rows:
            try:
                intervals.append((datetime.fromisoformat(row["start_datetime"].replace("Z", "+00:00")), datetime.fromisoformat(row["end_datetime"].replace("Z", "+00:00"))))
            except (ValueError, TypeError):
                pass
        priced_costs = [value for row in raw_rows if (value := number(row.get("task_cost"))) is not None]
        allocated_vcpu_values = [
            seconds * threads / 3600
            for row in raw_rows
            if (seconds := number(row.get("s"))) is not None
            and (threads := number(row.get("snakemake_threads"))) is not None
        ]
        observed_cpu_values = [value / 3600 for row in raw_rows if (value := number(row.get("cpu_time"))) is not None]
        summary_rows.append(
            {
                **{key: observation[key] for key in ("experiment", "analysis_id", "au", "runtime_au", "plot_label", "ilmn_measured_token", "ont_measured_token")},
                "observation_id": observation["observation_id"],
                "successful_records": len(raw_rows),
                "priced_records": len(priced_costs),
                "unpriced_records": len(raw_rows) - len(priced_costs),
                "task_groups": len(by_rule),
                "total_cost_usd": sum(priced_costs),
                "allocated_vcpu_h": sum(allocated_vcpu_values),
                "observed_cpu_h": sum(observed_cpu_values),
                "sum_task_wall_h": sum(float(row["s"]) for row in raw_rows) / 3600,
                "observed_makespan_h": ((max(end for _, end in intervals) - min(start for start, _ in intervals)).total_seconds() / 3600) if intervals else None,
                "active_interval_union_h": interval_union_hours(intervals),
                "longest_task_h": max(float(row["s"]) for row in raw_rows) / 3600,
                "benchmark_scope": observation.get("benchmark_scope", "completed execution benchmark summary"),
            }
        )
    return task_rows, summary_rows


def benchmark_plots(observations: list[dict[str, Any]], task_rows: list[dict[str, Any]], summary_rows: list[dict[str, Any]], figures: Path, chart_map: list[dict[str, str]]) -> None:
    obs_order = sorted(observations, key=lambda row: (EXPERIMENT_INDEX[row["experiment"]], AU_INDEX[row["au"]]))
    for metric, scale, xlabel, title, filename, color in (
        ("longest_walltime_s", 1 / 3600, "Longest successful execution (hours)", "Per-task walltime by retained observation", "benchmark_per_task_walltime.png", "#3977a8"),
        ("total_cost_usd", 1, "Total task-group cost (USD)", "Per-task cost by retained observation", "benchmark_per_task_cost.png", "#d0783d"),
    ):
        ncols = 4 if len(obs_order) > 16 else 2
        nrows = math.ceil(len(obs_order) / ncols)
        fig, axes = plt.subplots(nrows, ncols, figsize=(26 if ncols == 4 else 18, max(14, nrows * 4.0)), constrained_layout=True)
        axes = np.atleast_1d(axes).ravel()
        for axis, observation in zip(axes, obs_order):
            subset = sorted([row for row in task_rows if row["observation_id"] == observation["observation_id"]], key=lambda row: row[metric], reverse=True)[:12]
            subset.reverse()
            values = [row[metric] * scale for row in subset]
            labels = [row["rule"].replace("_", " ")[:42] for row in subset]
            axis.barh(range(len(subset)), values, color=color, edgecolor="#25313b", linewidth=0.4)
            axis.set_yticks(range(len(subset)), labels, fontsize=7)
            axis.set_title(observation["plot_label"], fontsize=12)
            axis.set_xlabel(xlabel, fontsize=9)
            axis.grid(axis="x", alpha=0.2)
        for axis in axes[len(obs_order):]:
            axis.set_visible(False)
        fig.suptitle(title, fontsize=19)
        output = figures / filename
        save_figure(fig, output)
        chart_map.append({"figure": output.name, "chart_type": "small-multiple bar", "title": title, "source_table": "benchmark_task_groups.tsv", "metric": metric})

    summaries = sorted(summary_rows, key=lambda row: (EXPERIMENT_INDEX[row["experiment"]], AU_INDEX[row["au"]]))
    labels = [row["plot_label"] for row in summaries]
    x = np.arange(len(labels))
    fig, axes = plt.subplots(1, 3, figsize=(25 if len(labels) > 20 else 19, 8), constrained_layout=True)
    colors = [EXPERIMENT_COLORS[row["experiment"]] for row in summaries]
    axes[0].bar(x, [row["total_cost_usd"] for row in summaries], color=colors, edgecolor="#333", linewidth=0.4)
    axes[0].set_title("Total successful task cost")
    axes[0].set_ylabel("USD")
    axes[1].bar(x - 0.18, [row["allocated_vcpu_h"] for row in summaries], 0.36, label="allocated vCPU-h", color="#5d8f70")
    axes[1].bar(x + 0.18, [row["observed_cpu_h"] for row in summaries], 0.36, label="observed CPU-h", color="#a5c296")
    axes[1].set_title("CPU consumption")
    axes[1].set_ylabel("CPU-hours")
    axes[1].legend(fontsize=8)
    width = 0.25
    axes[2].bar(x - width, [row["observed_makespan_h"] for row in summaries], width, label="observed makespan", color="#5069a8")
    axes[2].bar(x, [row["active_interval_union_h"] for row in summaries], width, label="active interval union", color="#70a5d8")
    axes[2].bar(x + width, [row["longest_task_h"] for row in summaries], width, label="longest task", color="#7da86b")
    axes[2].set_title("Parallel-aware duration measures")
    axes[2].set_ylabel("Hours")
    axes[2].legend(fontsize=8)
    for axis in axes:
        axis.set_xticks(x, labels, rotation=60 if len(labels) > 20 else 45, ha="right", fontsize=7.2 if len(labels) > 20 else 8)
        axis.grid(axis="y", alpha=0.2)
    fig.suptitle("Benchmark totals by retained observation (E4 values are an in-flight snapshot)", fontsize=17)
    output = figures / "benchmark_au_totals.png"
    save_figure(fig, output)
    chart_map.append({"figure": output.name, "chart_type": "grouped bar", "title": "Benchmark totals by retained observation", "source_table": "benchmark_au_totals.tsv", "metric": "cost CPU and duration"})


def markdown_table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] + ["---:" for _ in header[1:]]) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def relative_asset(report_path: Path, path: Path) -> str:
    return str(path.relative_to(report_path.parent))


def build_report(
    report_path: Path,
    assets: Path,
    observations: list[dict[str, Any]],
    hard_rows: list[dict[str, Any]],
    truvari_rows: list[dict[str, Any]],
    smn_rows: list[dict[str, Any]],
    benchmark_summaries: list[dict[str, Any]],
) -> None:
    figures = assets / "figures"
    tables = assets / "tables"
    trussv = [row for row in truvari_rows if row["caller"] == "TrussSV" and number(row["fscore"]) is not None]
    best_trussv = max(trussv, key=lambda row: row["fscore"])
    costs = {row["observation_id"]: row["total_cost_usd"] for row in benchmark_summaries}
    total_cost_by_experiment = {
        experiment: sum(costs.get(row["observation_id"], 0.0) for row in observations if row["experiment"] == experiment)
        for experiment in EXPERIMENTS
    }
    ordered = sorted(observations, key=lambda row: (EXPERIMENT_INDEX[row["experiment"]], AU_INDEX[row["au"]]))
    prior_observations = [row for row in observations if row["experiment"] != "E4"]
    e4_observations = [row for row in observations if row["experiment"] == "E4"]
    if len(prior_observations) != 12 or len(e4_observations) != 20:
        raise ValueError("report requires 12 prior observations plus 20 E4 observations")
    e4_compact = e4_observations[0]["compact_evidence"]
    e4_capture_time = e4_compact["captured_at_end_utc"]
    e4_workflow = e4_compact["workflow_status_end"]["attempts"][-1]
    e4_benchmark_rejections = e4_compact["benchmark_rejections"]
    e4_failed_benchmark_rows = sum("status=failed" in row["reason"] for row in e4_benchmark_rejections)
    e4_invalid_success_rows = sum("invalid successful benchmark" in row["reason"] for row in e4_benchmark_rejections)
    cost_parts = []
    for experiment in EXPERIMENTS:
        suffix = " (in-flight partial snapshot)" if experiment == "E4" else ""
        cost_parts.append(f"**${total_cost_by_experiment[experiment]:,.2f}** for {experiment}{suffix}")
    top_coverage_table = [
        [
            row["plot_label"],
            "NA" if row["ilmn_target"] is None else f"{row['ilmn_target']:g}×",
            f"{row['ilmn_measured_token']}×",
            f"{row['rsr_measured_token']}×",
            "NA" if row["ont_target"] is None else f"{row['ont_target']:g}×",
            f"{row['ont_measured_token']}×",
        ]
        for row in ordered
    ]
    observation_markdown = [
        [
            row["plot_label"],
            f"{row['ilmn_measured_token']}×",
            f"{row['rsr_measured_token']}×",
            f"{row['ont_measured_token']}×",
            f"[{row['ont_start_hour']},{row['ont_end_hour']})",
            row["runtime_au"],
        ]
        for row in ordered
    ]
    e4_completeness_markdown = [
        [
            row["plot_label"],
            row["source_analysis_unit_uid"],
            f"{row['ilmn_measured_token']}×",
            f"{row['ont_measured_token']}×",
            "complete",
            "4/4",
            "15/15",
            "complete",
            str(e4_compact["completeness"][row["runtime_au"]]["benchmark_success_rows"]),
        ]
        for row in sorted(e4_observations, key=lambda row: AU_INDEX[row["au"]])
    ]

    image = lambda name: f"![{name}]({relative_asset(report_path, figures / name)})"
    table_link = lambda name: f"[{name}]({relative_asset(report_path, tables / name)})"
    lines: list[str] = [
        "# HG002 Bjuice native-SR × LR measured-coverage matrix report",
        "",
        "## Measured-coverage sanity table",
        "",
        markdown_table(["ID", "target ILMNx", "SR ILMNx", "RSR ILMNx", "target ONTx", "LRONTx"], top_coverage_table),
        "",
        "This is the only report table that presents requested coverage targets. E1/E3/P1 values were re-read from three completed S3 exports; E4 values were read from the live FSx analysis root in a bounded DYEC snapshot. Every source path and SHA-256 is retained in " + table_link("direct_s3_coverage_regather.tsv") + " and " + table_link("source_inventory.tsv") + ".",
        "",
        "## Technical summary",
        "",
        f"This report contains **{len(observations)} observations**: all **12 prior E1/E3/P1 observations** plus **20 E4 controlled-matrix AUs** captured at **{e4_capture_time}**. E4 remained **{e4_workflow['state']}** with no controller, `day_run`, or Snakemake return code at capture, so E4 benchmark accounting is explicitly partial.",
        "",
        "Every coverage-positioned figure uses **measured native SR×** on its vertical axis and **measured LR×** on its horizontal axis, with equal numeric scale. RSR× is audit-only. The strongest retained tagged-TrussSV global F-score is **" + f"{best_trussv['fscore']:.4f}** at **{best_trussv['plot_label']}**. Captured successful benchmark rows sum to " + ", ".join(cost_parts) + ".",
        "",
        "E1 is **not a valid two-axis Illumina downsampling series**: every direct-S3 native-SR summary is exactly 43.73× (and has the same SHA-256), despite the AU-specific declared fractions. It is retained as a full-SR / variable-LR experiment. E3 supplies four variable-native-SR observations, P1 is a distinct full-input observation, and E4 supplies the intended 20-cell controlled matrix.",
        "",
        "RSR is not a conventional random Illumina downsample. The E1 Sentieon hybrid log shows stage 3 running on a generated `hybrid_stage2.bed` interval set, followed by `hybrid_transfer` from the full SR alignment into `g_sr_realigned.cram`. Its retained-record fraction and Mosdepth therefore vary with the hybrid-selected regions and LR input. The 8.54–14.01× E1 RSR range is expected to differ from the uniform 43.73× native-SR evidence and must not form a coverage-matrix axis.",
        "",
        "## E4 in-flight snapshot completeness",
        "",
        f"All 20 E4 AUs supplied parseable native-SR, RSR-audit, LR, hard-VCF GIAB-HC, four-caller Truvari, SMN12, and 15-gene SegDup artifacts. Their measured native-SR range is **{min(row['ilmn_measured'] for row in e4_observations):g}×–{max(row['ilmn_measured'] for row in e4_observations):g}×** and measured LR range is **{min(row['ont_measured'] for row in e4_observations):g}×–{max(row['ont_measured'] for row in e4_observations):g}×**.",
        "",
        markdown_table(
            ["E4 AU", "source AU", "native SR", "LR", "hard VCF", "Truvari", "SegDup", "SMN12", "usable benchmark rows"],
            e4_completeness_markdown,
        ),
        "",
        f"The E4 snapshot contains **{len(e4_compact['benchmarks']):,} usable successful raw benchmark rows**. Because the controller was still running, these are not final cost or runtime totals. The collector also retained an audit of **{e4_failed_benchmark_rows} failed-attempt rows** and excluded **{e4_invalid_success_rows} rows labelled successful whose walltime was `NA`**. Exact per-AU counts are in " + table_link("e4_snapshot_completeness.tsv") + ".",
        "",
        "## Source locations",
        "",
        markdown_table(["Source", "S3 URI"], [[label, f"`{uri}`"] for label, uri in SOURCE_S3_URIS]),
        "",
        f"E4 live source at capture: `{e4_compact['analysis_root']}` (DayOA {e4_compact['dayoa_git']['exact_tag']} at `{e4_compact['dayoa_git']['commit']}`). The exact completed-export S3 roots and direct summary-file URIs are recorded in " + table_link("source_s3_uris.tsv") + " and " + table_link("direct_s3_coverage_regather.tsv") + "; E4 file hashes and paths are in " + table_link("source_inventory.tsv") + ".",
        "",
        "## Measured native-SR × LR availability",
        "",
        "The circle centers below are placed at their actual numeric native-SR× and LR× values; x and y use the same coverage-unit scale. The in-circle value is the retained-observation count, and " + table_link("coverage_grid.tsv") + " lists the corresponding AU(s). Dashed contours show two-dimensional density of retained AU coordinates only; they do not interpolate any coverage or metric into blank space. This exposes E1 as a vertical full-SR series instead of falsely spreading it across nominal Illumina positions.",
        "",
        image("combined_measured_coverage_grid.png"),
        "",
        "### Retained observation provenance",
        "",
        markdown_table(["Observation", "measured SR ILMNx", "measured RSR ILMNx (audit only)", "measured LRONTx", "ONT hours", "Runtime AU"], observation_markdown),
        "",
        "The retained-observation table has native-SR, RSR, LR, source paths, and selection provenance without repeating the requested targets: " + table_link("retained_observations.tsv") + ".",
        "",
        "## Measured ONT coverage and runtime",
        "",
        "This is descriptive aligned LR yield versus cumulative input runtime. It uses measured LR× only; the lines connect experiment-specific hour means and are not a fitted yield model.",
        "",
        image("ont_coverage_vs_runtime.png"),
        "",
        "",
        "## Hard-VCF GIAB high-confidence concordance",
        "",
        "Crude SNP uses `SNPts + SNPtv/2` independently for TP, FN, and FP; precision, recall, and F-score are recalculated from those composite counts. Each color map uses the same equal-scale numeric native-SR×/LR× plane. Every 25%-larger circle prints its own plotted metric and has no colored edge. Dashed contours show retained-AU coordinate density only, not interpolated metric values. When multiple observations share a measured coordinate, both the circle color and printed value are their arithmetic mean; the metric TSV keeps unaggregated values.",
        "",
    ]
    for klass, title in (("snp", "SNP (SNPts + SNPtv/2)"), ("ins_50", "INS_50"), ("del_50", "DEL_50")):
        lines.extend(
            [
                f"### {title}",
                "",
                "F-score, false-negative, false-positive, and precision–recall views below all use the measured native-SR/LR coverage contract; no RSR or nominal coverage is used to position an observation. Precision–recall points use one neutral style without experiment encoding or connecting lines, and each point is labelled `measured ILMN× / measured ONT×`.",
                "",
                image(f"hard_vcf_giabhc_{klass}_fscore_heatmap.png"),
                "",
                image(f"hard_vcf_giabhc_{klass}_fn_heatmap.png"),
                "",
                image(f"hard_vcf_giabhc_{klass}_fp_heatmap.png"),
                "",
                image(f"hard_vcf_giabhc_{klass}_precision_recall.png"),
                "",
            ]
        )
    lines.extend(
        [
            "Exact hard-VCF values: " + table_link("hard_vcf_giabhc_metrics.tsv") + ".",
            "",
            "## Truvari structural-variant concordance",
            "",
            "The two coverage-coordinate maps use tagged TrussSV values. The final precision–recall plot combines all callers and all retained observations in one panel; raw summary metrics remain available for audit.",
            "",
            image("truvari_trussv_global_fscore_heatmap.png"),
            "",
            image("truvari_trussv_gt_concordance_heatmap.png"),
            "",
            image("truvari_all_callers_precision_recall.png"),
            "",
            "Marker shape encodes the caller (TIDDIT, LongReadSV, Sniffles2, or tagged TrussSV); a continuous color scale encodes total measured coverage as ILMN native-SR× plus ONT-LR×. Experiment is not encoded. There are no connecting or leader lines. Every exact-coordinate point group is labelled directly with its F-score; coverage-number labels are omitted from the plot for legibility and remain available in the exact raw-summary table. Points with undefined raw precision or recall remain in the table as `NA` and are not plotted. Exact raw-summary values: " + table_link("truvari_metrics.tsv") + ".",
            "",
            image("truvari_highest_coverage_caller_fscore.png"),
            "",
            "The four-point summary isolates the maximum retained measured-coverage observation and flags TIDDIT as short-read, LongReadSV and Sniffles2 as long-read, and TrussSV as ensemble.",
            "",
            "## SegDup and SMN1/2 calls",
            "",
        "These callset summaries are descriptive, not truth/query concordance. Their coordinate facets use the same measured native-SR×/LR× plane, so a vertical E1 arrangement represents the actual full-SR result rather than a nominal SR ladder. Each 25%-larger circle prints the displayed call count or copy number and has no colored edge; dashed contours represent retained-AU coordinate density only. Colors and values are coordinate-level arithmetic means when observations co-locate.",
            "",
            image("segdup_call_heatmap.png"),
            "",
            "Exact SegDup records, including PASS/non-PASS state, are available in " + table_link("segdup_calls.tsv") + ".",
            "",
            image("smn12_copy_number_heatmap.png"),
            "",
            "Undefined low-coverage SMN copy-number calls remain `NA`; they are not coerced to zero. Complete SMN fields: " + table_link("smn12_calls.tsv") + ".",
            "",
            "## Benchmark cost and parallel-aware runtime",
            "",
            "The per-task panels retain individual-AU task groups; the summary uses the exact retained observations. Neither view uses requested coverage values. E4 bars are explicitly an in-flight snapshot and must not be interpreted as final AU cost or duration.",
            "",
            image("benchmark_per_task_walltime.png"),
            "",
            image("benchmark_per_task_cost.png"),
            "",
            image("benchmark_au_totals.png"),
            "",
            "The task plots show the top 12 groups per retained observation; the TSV retains every usable successful task group. Observed makespan spans the first through last benchmark timestamp. Active-interval union merges overlapping task intervals. Longest task is a lower bound, not a DAG-derived critical path. E4 values stop at the snapshot timestamp and will increase as the controller finishes.",
            "",
            "Supporting benchmark tables: " + table_link("benchmark_task_groups.tsv") + " and " + table_link("benchmark_au_totals.tsv") + ".",
            "",
            "## Scope, methods, and limitations",
            "",
            "- Native SR× is the exact `chrom=total` Mosdepth mean from `sentdhiomr2sr/smd`; LR× is from `sentdhiomr2lr/na`. RSR× from `sentdhiomr2rsr/na` is retained only as a separately named audit result.",
            "- The completed-export S3 collection rejects a missing or duplicate native-SR, RSR, or LR summary and fails if a re-read direct value differs from the recorded contract. The E4 collector applies the same exact-cardinality and schema checks against its live FSx snapshot.",
            "- E1’s seven identical native-SR summaries establish a data-generation limitation, not a charting transformation. This report does not claim that its declared SR fractions were applied.",
            "- Hard-VCF metrics are restricted to `ROI=giabHC`; the crude SNP construction is intentionally not a standard variant-class aggregation.",
            "- Truvari metrics come from raw `summary.json`. Undefined no-call rates are `NA`, even where a downstream report-oriented artifact normalized them to zero.",
            "- SegDup is descriptive callset output, not truth/query concordance. A no-call state is not evidence of reference genotype truth.",
            "- E1, E3, P1, and E4 reuse the same HG002 source material; input subsets are nested and P1 is a full-input production observation. Results are descriptive and no causal or inferential claim is made.",
            f"- E4 was nonterminal at {e4_capture_time}. Its 20 core metric sets were complete and parseable, but its {len(e4_compact['benchmarks']):,} benchmark rows are a lower-bound snapshot, not final workflow accounting.",
            "- The executions may have different runtime software provenance. The report uses produced artifacts and does not relabel a later execution as a pristine re-execution of an earlier release.",
            "",
            "## Audit and reproducibility",
            "",
            "- Direct S3 native-SR, RSR, and LR values with exact source paths and SHA-256 values: " + table_link("direct_s3_coverage_regather.tsv") + ".",
            "- E4 per-AU metric and benchmark completeness at capture: " + table_link("e4_snapshot_completeness.tsv") + ".",
            "- Existing bounded evidence inventory for detailed call/benchmark inputs: " + table_link("source_inventory.tsv") + ".",
            "- Figure-to-table mapping: " + table_link("chart_map.tsv") + ".",
            "",
            f"Generated from bounded E1/E3/P1 evidence, direct S3 reads of their 36 Mosdepth summaries, and the checksum-bound E4 live-FSx snapshot captured {e4_compact['captured_at_start_utc']} through {e4_capture_time}.",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n")


def main() -> None:
    args = parse_args()
    figures = args.assets_dir / "figures"
    tables = args.assets_dir / "tables"
    figures.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)

    source_observations: list[dict[str, Any]] = []
    source_inventory: list[dict[str, Any]] = []
    for experiment in EXPERIMENTS:
        observations, metadata = parse_experiment(experiment, args.evidence_root)
        source_observations.extend(observations)
        source_inventory.extend(metadata["inventory"])
    experiment_counts = {
        experiment: sum(row["experiment"] == experiment for row in source_observations)
        for experiment in EXPERIMENTS
    }
    if experiment_counts != {"E1": 7, "E3": 4, "P1": 1, "E4": 20}:
        raise ValueError(f"unexpected source-observation counts: {experiment_counts}")
    direct_s3_rows = read_direct_s3_coverage(args.direct_s3_coverage)
    prior_source_observations = [row for row in source_observations if row["experiment"] != "E4"]
    apply_direct_s3_coverage(prior_source_observations, direct_s3_rows)

    retained, resolutions, _ = deduplicate(source_observations)
    if len(retained) != 32 or resolutions:
        raise AssertionError("the 12 prior and 20 E4 rows must remain 32 unique observations")
    p1_observations = [row for row in retained if row["experiment"] == "P1"]
    if len(p1_observations) != 1:
        raise AssertionError("expected one retained P1 observation")
    p1_observation = p1_observations[0]
    if any(p1_observation[field] is not None for field in ("ilmn_target", "ont_target", "ilmn_abs_error", "ont_abs_error")):
        raise AssertionError("P1 must not have invented target or target-error values")
    if (p1_observation["subsample_pct"], p1_observation["ont_start_hour"], p1_observation["ont_end_hour"]) != ("full", 0, 24):
        raise AssertionError("P1 full-input contract was not retained")
    if any("/align/sentdhiomr2sr/smd/alignqc/mosdepth/" not in row["coverage_source_ilmn"] for row in retained):
        raise AssertionError("a plotted Illumina coordinate is not native SR")
    if any("/align/sentdhiomr2rsr/na/alignqc/mosdepth/" not in row["coverage_source_rsr"] for row in retained):
        raise AssertionError("RSR audit source mismatch")
    if any("/align/sentdhiomr2lr/na/alignqc/mosdepth/" not in row["coverage_source_ont"] for row in retained):
        raise AssertionError("a plotted ONT coordinate is not LR")
    for index, observation in enumerate(retained, start=1):
        observation["observation_id"] = f"OBS{index:02d}"
    retained_key_to_id = {(row["experiment"], row["runtime_au"]): row["observation_id"] for row in retained}
    dropped_index = 0
    for row in source_observations:
        if (row["experiment"], row["runtime_au"]) in retained_key_to_id:
            row["observation_id"] = retained_key_to_id[(row["experiment"], row["runtime_au"])]
        else:
            dropped_index += 1
            row["observation_id"] = f"DROP{dropped_index:02d}"

    chart_map: list[dict[str, str]] = []
    coverage_grid(retained, figures, tables, chart_map)
    coverage_plots(retained, figures, chart_map)
    all_hard_rows = hard_vcf_metrics(source_observations)
    retained_ids = {row["observation_id"] for row in retained}
    hard_rows = [row for row in all_hard_rows if row["observation_id"] in retained_ids]
    hard_vcf_plots(retained, hard_rows, figures, chart_map)
    all_truvari_rows = truvari_metrics(source_observations)
    truvari_rows = [row for row in all_truvari_rows if row["observation_id"] in retained_ids]
    truvari_plots(retained, truvari_rows, figures, chart_map)
    segdup_rows, smn_rows = call_tables_and_plots(retained, figures, chart_map)
    benchmark_tasks, benchmark_summaries = benchmark_data(retained)
    benchmark_plots(retained, benchmark_tasks, benchmark_summaries, figures, chart_map)

    observation_fields = [
        "observation_id", "experiment", "experiment_title", "analysis_id", "au", "runtime_au", "source_analysis_unit_uid",
        "plot_label", "ilmn_measured_token", "rsr_measured_token", "ont_measured_token",
        "ilmn_target", "ont_target", "ilmn_abs_error", "ont_abs_error", "subsample_pct", "ont_start_hour", "ont_end_hour",
        "selection_status", "coverage_source_ilmn", "coverage_source_rsr", "coverage_source_ont", "coverage_capture_method",
        "evidence_captured_at", "direct_s3_captured_at", "snapshot_workflow_state", "snapshot_controller_rc", "benchmark_scope",
    ]
    write_tsv(tables / "retained_observations.tsv", retained, observation_fields)
    write_tsv(tables / "direct_s3_coverage_regather.tsv", direct_s3_rows, list(direct_s3_rows[0]))
    write_tsv(tables / "hard_vcf_giabhc_metrics.tsv", hard_rows, ["observation_id", "experiment", "analysis_id", "au", "runtime_au", "plot_label", "ilmn_measured_token", "ont_measured_token", "roi", "class", "tp", "fn", "fp", "precision", "recall", "fscore", "source_path"])
    write_tsv(tables / "truvari_metrics.tsv", truvari_rows, ["observation_id", "experiment", "analysis_id", "au", "runtime_au", "plot_label", "ilmn_measured_token", "ont_measured_token", "caller", "tp_base", "tp_comp", "fn", "fp", "precision", "recall", "fscore", "gt_concordance", "base_count", "query_count", "source_path"])
    write_tsv(tables / "segdup_calls.tsv", segdup_rows, ["observation_id", "experiment", "analysis_id", "au", "runtime_au", "plot_label", "ilmn_measured_token", "ont_measured_token", "gene", "call_state", "chrom", "pos", "ref", "alt", "filter", "gt", "qual"])
    write_tsv(tables / "smn12_calls.tsv", smn_rows, ["observation_id", "experiment", "analysis_id", "au", "runtime_au", "plot_label", "ilmn_measured_token", "ont_measured_token", "SMN1_CN", "SMN2_CN", "SMN2delta7_8_CN", "Total_CN_raw", "Full_length_CN_raw", "g27134TG_CN", "isSMA", "isCarrier", "Info", "Median_depth", "source_path"])
    write_tsv(tables / "benchmark_task_groups.tsv", benchmark_tasks, ["observation_id", "experiment", "analysis_id", "au", "runtime_au", "plot_label", "ilmn_measured_token", "ont_measured_token", "rule", "successful_records", "priced_records", "unpriced_records", "longest_walltime_s", "total_cost_usd", "allocated_vcpu_h", "observed_cpu_h", "benchmark_scope"])
    write_tsv(tables / "benchmark_au_totals.tsv", benchmark_summaries, ["observation_id", "experiment", "analysis_id", "au", "runtime_au", "plot_label", "ilmn_measured_token", "ont_measured_token", "successful_records", "priced_records", "unpriced_records", "task_groups", "total_cost_usd", "allocated_vcpu_h", "observed_cpu_h", "sum_task_wall_h", "observed_makespan_h", "active_interval_union_h", "longest_task_h", "benchmark_scope"])
    e4_observations = [row for row in retained if row["experiment"] == "E4"]
    e4_compact = e4_observations[0]["compact_evidence"]
    e4_completeness_rows = []
    for observation in sorted(e4_observations, key=lambda row: AU_INDEX[row["au"]]):
        completeness = e4_compact["completeness"][observation["runtime_au"]]
        e4_completeness_rows.append(
            {
                "captured_at_utc": e4_compact["captured_at_end_utc"],
                "analysis_id": observation["analysis_id"],
                "planned_au": observation["au"],
                "source_analysis_unit_uid": observation["source_analysis_unit_uid"],
                "runtime_au": observation["runtime_au"],
                "target_native_sr_x": observation["ilmn_target"],
                "measured_native_sr_x": observation["ilmn_measured_token"],
                "measured_rsr_audit_x": observation["rsr_measured_token"],
                "target_lr_x": observation["ont_target"],
                "measured_lr_x": observation["ont_measured_token"],
                "hard_vcf_giabhc": completeness["hard_vcf_giabhc"],
                "truvari_summaries": completeness["truvari_summaries"],
                "segdup_vcfs": completeness["segdup_vcfs"],
                "smn12_summary": completeness["smn12_summary"],
                "benchmark_success_rows": completeness["benchmark_success_rows"],
                "benchmark_rejected_or_incomplete_rows": completeness["benchmark_rejected_or_incomplete_rows"],
                "benchmark_snapshot": completeness["benchmark_snapshot"],
                "workflow_state_at_capture": observation["snapshot_workflow_state"],
                "controller_rc_at_capture": observation["snapshot_controller_rc"],
            }
        )
    write_tsv(
        tables / "e4_snapshot_completeness.tsv",
        e4_completeness_rows,
        [
            "captured_at_utc", "analysis_id", "planned_au", "source_analysis_unit_uid", "runtime_au",
            "target_native_sr_x", "measured_native_sr_x", "measured_rsr_audit_x", "target_lr_x", "measured_lr_x",
            "hard_vcf_giabhc", "truvari_summaries", "segdup_vcfs", "smn12_summary", "benchmark_success_rows",
            "benchmark_rejected_or_incomplete_rows", "benchmark_snapshot", "workflow_state_at_capture", "controller_rc_at_capture",
        ],
    )
    write_tsv(tables / "source_inventory.tsv", source_inventory, ["experiment", "analysis_root", "category", "relative_path", "bytes", "mtime_epoch", "sha256", "local_path", "local_sha256", "local_sha256_match"])
    write_tsv(tables / "source_s3_uris.tsv", [{"source": label, "s3_uri": uri} for label, uri in SOURCE_S3_URIS], ["source", "s3_uri"])
    write_tsv(tables / "chart_map.tsv", chart_map, ["figure", "chart_type", "title", "source_table", "metric"])

    heatmaps = [row for row in chart_map if row["chart_type"] == "heatmap"]
    concordance_heatmaps = [row for row in heatmaps if row["figure"] != "combined_measured_coverage_grid.png" and row["figure"] not in {"segdup_call_heatmap.png", "smn12_copy_number_heatmap.png"}]
    if len(concordance_heatmaps) != 11:
        raise AssertionError(f"expected 11 concordance heatmaps; found {len(concordance_heatmaps)}")
    if len([row for row in heatmaps if row["figure"] == "combined_measured_coverage_grid.png"]) != 1:
        raise AssertionError("missing coverage layout heatmap")

    build_report(args.report_path, args.assets_dir, retained, hard_rows, truvari_rows, smn_rows, benchmark_summaries)

    expected_tables = {
        "retained_observations.tsv", "direct_s3_coverage_regather.tsv", "coverage_grid.tsv",
        "e4_snapshot_completeness.tsv",
        "hard_vcf_giabhc_metrics.tsv", "truvari_metrics.tsv", "segdup_calls.tsv", "smn12_calls.tsv",
        "benchmark_task_groups.tsv", "benchmark_au_totals.tsv", "source_inventory.tsv", "source_s3_uris.tsv", "chart_map.tsv",
    }
    missing_tables = [name for name in expected_tables if not (tables / name).is_file()]
    if missing_tables:
        raise AssertionError(f"missing tables: {missing_tables}")
    if not args.report_path.is_file():
        raise AssertionError("report was not created")
    print(json.dumps({"report": str(args.report_path), "assets": str(args.assets_dir), "source_observations": len(source_observations), "retained_observations": len(retained), "prior_observations": len(prior_source_observations), "e4_observations": len(e4_observations), "direct_s3_coverage_rows": len(direct_s3_rows), "e4_benchmark_rows": len(e4_compact["benchmarks"]), "concordance_heatmaps": len(concordance_heatmaps), "all_heatmaps": len(heatmaps), "figures": len(chart_map), "tables": len(expected_tables)}, indent=2))


if __name__ == "__main__":
    main()
