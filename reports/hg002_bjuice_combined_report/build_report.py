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
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
import numpy as np


EXPERIMENTS = {
    "E1": {
        "analysis_id": "prod-cand-1703-hg002-bjuice-v2-multiau-20260814T114522Z",
        "title": "Initial downsampling experiment",
    },
    "E2": {
        "analysis_id": "prod-cand-1703-hg002-bjuice-v2-seqkitfix-20260815T080300Z",
        "title": "Corrected balanced re-downsampling experiment",
    },
}
AU_ORDER = ["p5xp5", "1x1", "3x3", "5x5", "10x5", "15x5", "15x10"]
AU_INDEX = {name: index for index, name in enumerate(AU_ORDER)}
TARGETS = {
    "p5xp5": (Decimal("0.5"), Decimal("0.5")),
    "1x1": (Decimal("1"), Decimal("1")),
    "3x3": (Decimal("3"), Decimal("3")),
    "5x5": (Decimal("5"), Decimal("5")),
    "10x5": (Decimal("10"), Decimal("5")),
    "15x5": (Decimal("15"), Decimal("5")),
    "15x10": (Decimal("15"), Decimal("10")),
}
EXPERIMENT_COLORS = {"E1": "#3977a8", "E2": "#d0783d"}
EXPERIMENT_MARKERS = {"E1": "o", "E2": "s"}
CALLER_STYLES = {
    "TrussSV": ("#315f88", "o"),
    "Sniffles2": ("#c2783e", "s"),
    "LongReadSV": ("#7a5a9d", "^"),
    "TIDDIT": ("#6f8850", "D"),
}

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


def annotate_side_labels(
    ax: Any,
    points: list[dict[str, Any]],
    x_key: str,
    y_key: str,
    label_fn: Any,
    fontsize: float,
) -> None:
    """Place dense point labels in stable experiment-specific callout columns."""
    for experiment, x_fraction in (("E1", 0.03), ("E2", 0.62)):
        group = sorted(
            [row for row in points if row["experiment"] == experiment],
            key=lambda row: (float(row[y_key]), float(row[x_key]), row["au"]),
            reverse=True,
        )
        for row, y_fraction in zip(group, np.linspace(0.91, 0.09, len(group))):
            ax.annotate(
                label_fn(row),
                (float(row[x_key]), float(row[y_key])),
                xycoords="data",
                xytext=(x_fraction, y_fraction),
                textcoords="axes fraction",
                fontsize=fontsize,
                ha="left",
                va="center",
                color="#111827",
                bbox={"boxstyle": "round,pad=0.16", "facecolor": "white", "edgecolor": EXPERIMENT_COLORS[experiment], "alpha": 0.78, "linewidth": 0.6},
                arrowprops={"arrowstyle": "-", "color": EXPERIMENT_COLORS[experiment], "alpha": 0.42, "linewidth": 0.55},
            )


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


def parse_experiment(experiment: str, evidence_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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
        ilmn_files = list(unit_root.glob("align/sentdhiomr2rsr/na/alignqc/mosdepth/*.summary.txt"))
        ont_files = list(unit_root.glob("align/sentdhiomr2lr/na/alignqc/mosdepth/*.summary.txt"))
        if len(ilmn_files) != 1 or len(ont_files) != 1:
            raise ValueError(f"{experiment}:{runtime}: expected one ILMN and one ONT Mosdepth summary")
        ilmn_token, ilmn = read_total_mean(ilmn_files[0])
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
                "ilmn_measured_token": ilmn_token,
                "ilmn_measured": float(ilmn),
                "ont_measured_token": ont_token,
                "ont_measured": float(ont),
                "ilmn_target": float(target_ilmn),
                "ont_target": float(target_ont),
                "subsample_pct": unit["SUBSAMPLE_PCT"],
                "ont_start_hour": int(unit["ONT_FQ_START_HOUR"]),
                "ont_end_hour": int(unit["ONT_FQ_END_HOUR"]),
                "ilmn_abs_error": float(ilmn - target_ilmn),
                "ont_abs_error": float(ont - target_ont),
                "coverage_source_ilmn": source_relative(ilmn_files[0], dayoa_root),
                "coverage_source_ont": source_relative(ont_files[0], dayoa_root),
                "dayoa_root": str(dayoa_root),
                "selection_status": "source",
            }
        )
    observations.sort(key=lambda row: (AU_INDEX[row["au"]], row["experiment"]))
    if {row["au"] for row in observations} != set(AU_ORDER):
        raise ValueError(f"{experiment}: AU label set mismatch")
    return observations, {"inventory": inventory, "dayoa_root": dayoa_root, "bundle_root": bundle_root}


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
            dropped_status = {**dropped, "selection_status": "superseded_by_E2"}
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
                    "reason": "exact observation duplicate; newer E2 retained",
                }
            )
    retained.sort(key=lambda row: (row["ilmn_measured"], row["ont_measured"], AU_INDEX[row["au"]], row["experiment"]))
    all_with_status.sort(key=lambda row: (row["au"], row["ilmn_measured"], row["ont_measured"], row["experiment"]))
    return retained, resolutions, all_with_status


def coverage_axes(observations: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    y = sorted({row["ilmn_measured_token"] for row in observations}, key=Decimal)
    x = sorted({row["ont_measured_token"] for row in observations}, key=Decimal)
    return y, x


def coordinate_groups(observations: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in observations:
        groups[(row["ilmn_measured_token"], row["ont_measured_token"])].append(row)
    for members in groups.values():
        members.sort(key=lambda row: (row["experiment"], AU_INDEX[row["au"]]))
    return groups


def save_figure(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220, bbox_inches="tight", metadata={"Software": "HG002 combined report generator"})
    plt.close(fig)


def coverage_grid(observations: list[dict[str, Any]], figures: Path, tables: Path, chart_map: list[dict[str, str]]) -> list[list[str]]:
    y_values, x_values = coverage_axes(observations)
    y_index = {value: index for index, value in enumerate(y_values)}
    x_index = {value: index for index, value in enumerate(x_values)}
    groups = coordinate_groups(observations)
    matrix = np.full((len(y_values), len(x_values)), np.nan)
    for y, x in groups:
        matrix[y_index[y], x_index[x]] = 1

    cmap = LinearSegmentedColormap.from_list("coverage", ["#e8f1f8", "#3977a8"])
    cmap.set_bad("#f0f1f2")
    fig, ax = plt.subplots(figsize=(max(13, len(x_values) * 1.4), max(9, len(y_values) * 0.72)), constrained_layout=True)
    ax.imshow(matrix, origin="lower", aspect="auto", cmap=cmap, vmin=0, vmax=1, alpha=0.8)
    ax.set_title("Combined measured-coverage availability grid", pad=15)
    ax.set_xlabel("Measured ONT coverage (Mosdepth total mean)")
    ax.set_ylabel("Measured Illumina coverage (Mosdepth total mean)")
    ax.set_xticks(range(len(x_values)), [f"{value}x" for value in x_values], rotation=35, ha="right")
    ax.set_yticks(range(len(y_values)), [f"{value}x" for value in y_values])
    ax.set_xticks(np.arange(-0.5, len(x_values), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(y_values), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.7)
    ax.tick_params(which="minor", bottom=False, left=False)
    for row_index in range(len(y_values)):
        for col_index in range(len(x_values)):
            key = (y_values[row_index], x_values[col_index])
            label = "\n".join(member["plot_label"] for member in groups.get(key, [])) or "—"
            ax.text(col_index, row_index, label, ha="center", va="center", fontsize=10.5, color="black", fontweight="medium")
    output = figures / "combined_measured_coverage_grid.png"
    save_figure(fig, output)
    chart_map.append(
        {
            "figure": output.name,
            "chart_type": "heatmap",
            "title": "Combined measured-coverage availability grid",
            "source_table": "coverage_grid.tsv",
            "metric": "retained observation occupancy",
        }
    )

    wide_rows: list[dict[str, str]] = []
    markdown_rows: list[list[str]] = []
    for y in reversed(y_values):
        row = {"ilmn_measured": y}
        markdown_row = [f"{y}x"]
        for x in x_values:
            cell = "; ".join(member["plot_label"] for member in groups.get((y, x), [])) or "—"
            row[f"ont_{x}x"] = cell
            markdown_row.append(cell)
        wide_rows.append(row)
        markdown_rows.append(markdown_row)
    write_tsv(tables / "coverage_grid.tsv", wide_rows, ["ilmn_measured"] + [f"ont_{x}x" for x in x_values])
    return [["ILMN \\ ONT"] + [f"{x}x" for x in x_values]] + markdown_rows


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
    y_values, x_values = coverage_axes(observations)
    y_index = {value: index for index, value in enumerate(y_values)}
    x_index = {value: index for index, value in enumerate(x_values)}
    by_observation = {row["observation_id"]: row for row in metric_rows}
    groups = coordinate_groups(observations)
    matrix = np.full((len(y_values), len(x_values)), np.nan)
    annotations: dict[tuple[str, str], list[str]] = {}
    for key, members in groups.items():
        values: list[float] = []
        labels: list[str] = []
        for member in members:
            row = by_observation.get(member["observation_id"])
            value = number(row.get(value_field)) if row else None
            labels.append(f"{member['plot_label']} {value_format.format(value) if value is not None else 'NA'}")
            if value is not None:
                values.append(value)
        annotations[key] = labels
        if values:
            matrix[y_index[key[0]], x_index[key[1]]] = float(np.mean(values))

    valid = matrix[~np.isnan(matrix)]
    if not len(valid):
        raise ValueError(f"no numeric values for heatmap {filename}")
    vmin, vmax = float(valid.min()), float(valid.max())
    if vmin == vmax:
        vmin -= 0.5 if value_field in {"fn", "fp"} else 0.01
        vmax += 0.5 if value_field in {"fn", "fp"} else 0.01
    cmap = plt.get_cmap(cmap_name).copy()
    cmap.set_bad("#f0f1f2")
    fig, ax = plt.subplots(figsize=(max(14, len(x_values) * 1.55), max(9, len(y_values) * 0.8)), constrained_layout=True)
    image = ax.imshow(matrix, origin="lower", aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax, alpha=0.8)
    ax.set_title(title, pad=15)
    ax.set_xlabel("Measured ONT coverage (Mosdepth total mean)")
    ax.set_ylabel("Measured Illumina coverage (Mosdepth total mean)")
    ax.set_xticks(range(len(x_values)), [f"{value}x" for value in x_values], rotation=35, ha="right")
    ax.set_yticks(range(len(y_values)), [f"{value}x" for value in y_values])
    ax.set_xticks(np.arange(-0.5, len(x_values), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(y_values), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.7)
    ax.tick_params(which="minor", bottom=False, left=False)
    for y, x in groups:
        label = "\n".join(annotations[(y, x)])
        ax.text(x_index[x], y_index[y], label, ha="center", va="center", fontsize=9.2, color="black", fontweight="medium")
    bar = fig.colorbar(image, ax=ax, shrink=0.85)
    bar.set_label(cbar_label)
    output = figures / filename
    save_figure(fig, output)
    chart_map.append({"figure": filename, "chart_type": "heatmap", "title": title, "source_table": source_table, "metric": value_field})


def hard_vcf_metrics(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for observation in observations:
        dayoa_root = Path(observation["dayoa_root"])
        unit_root = dayoa_root / "results/day/hg38" / observation["runtime_au"]
        files = list(unit_root.glob("align/sentmm2ont/na/snv/sentdhiomr2/concordance/_giabHC/*_concordance.mqc.tsv"))
        if len(files) != 1:
            raise ValueError(f"expected one hard-VCF GIAB-HC file for {observation['plot_label']}")
        source = {row["VariantClass"]: row for row in read_tsv(files[0]) if row["ROI"] == "giabHC"}
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
                    "source_path": source_relative(files[0], dayoa_root),
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

        fig, ax = plt.subplots(figsize=(11.5, 8.5), constrained_layout=True)
        plotted_points: list[dict[str, Any]] = []
        for experiment in ("E1", "E2"):
            points = [row for row in subset if row["experiment"] == experiment and row["precision"] is not None and row["recall"] is not None]
            plotted_points.extend(points)
            ax.scatter(
                [row["recall"] for row in points],
                [row["precision"] for row in points],
                s=88,
                marker=EXPERIMENT_MARKERS[experiment],
                color=EXPERIMENT_COLORS[experiment],
                edgecolor="#20242a",
                linewidth=0.6,
                alpha=0.88,
                label=EXPERIMENTS[experiment]["title"],
            )
        annotate_side_labels(ax, plotted_points, "recall", "precision", lambda row: f"{row['plot_label']}  F={row['fscore']:.4f}", 7.8)
        ax.set_title(f"Combined hard-VCF GIAB-HC {title_class}: precision versus recall")
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision")
        ax.grid(alpha=0.25)
        ax.legend(loc="best")
        output = figures / f"hard_vcf_giabhc_{token}_precision_recall.png"
        save_figure(fig, output)
        chart_map.append({"figure": output.name, "chart_type": "scatter", "title": ax.get_title(), "source_table": "hard_vcf_giabhc_metrics.tsv", "metric": "precision versus recall"})


def truvari_metrics(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    caller_names = {"tagged_trussv": "TrussSV", "sniffles2": "Sniffles2", "longreadsv": "LongReadSV", "tiddit": "TIDDIT"}
    rows: list[dict[str, Any]] = []
    for observation in observations:
        dayoa_root = Path(observation["dayoa_root"])
        unit_root = dayoa_root / "results/day/hg38" / observation["runtime_au"]
        files = sorted(unit_root.glob("align/sentmm2ont/na/snv/sentdhiomr2/slim-consensus/truari/*"))
        if files:
            raise AssertionError("misspelled Truvari directory unexpectedly exists")
        summaries = sorted(unit_root.glob("align/sentmm2ont/na/snv/sentdhiomr2/slim-consensus/truvari/*/queries/*/truvari/summary.json"))
        if len(summaries) != 4:
            raise ValueError(f"expected four raw Truvari summaries for {observation['plot_label']}; found {len(summaries)}")
        for path in summaries:
            caller_token = path.parents[1].name
            caller = caller_names.get(caller_token, caller_token)
            data = json.loads(path.read_text())
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
                    "source_path": source_relative(path, dayoa_root),
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

    callers = sorted({row["caller"] for row in rows})
    fig, axes = plt.subplots(2, 2, figsize=(17, 13), constrained_layout=True, sharex=True, sharey=True)
    for ax, caller in zip(axes.ravel(), callers):
        color, marker = CALLER_STYLES.get(caller, ("#555555", "o"))
        plotted_points: list[dict[str, Any]] = []
        for experiment in ("E1", "E2"):
            points = [row for row in rows if row["caller"] == caller and row["experiment"] == experiment and number(row["precision"]) is not None and number(row["recall"]) is not None]
            if not points:
                continue
            plotted_points.extend(points)
            face = "none" if experiment == "E1" else color
            ax.scatter(
                [row["recall"] for row in points],
                [row["precision"] for row in points],
                s=70,
                marker=marker,
                facecolors=face,
                edgecolors=color,
                linewidth=1.2,
                alpha=0.9,
            )
        annotate_side_labels(ax, plotted_points, "recall", "precision", lambda row: f"{row['plot_label']}  F={fmt(row['fscore'], 3)}", 6.4)
        ax.set_title(caller)
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision")
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)
        ax.grid(alpha=0.22)
    legend_handles = [Line2D([0], [0], marker=CALLER_STYLES.get(caller, ("", "o"))[1], color="none", markerfacecolor=CALLER_STYLES.get(caller, ("#555", "o"))[0], markeredgecolor=CALLER_STYLES.get(caller, ("#555", "o"))[0], markersize=8, label=caller) for caller in callers]
    legend_handles.extend(
        [
            Line2D([0], [0], marker="o", color="none", markerfacecolor="none", markeredgecolor="#444", label="E1 open markers"),
            Line2D([0], [0], marker="o", color="none", markerfacecolor="#777", markeredgecolor="#444", label="E2 filled markers"),
        ]
    )
    fig.legend(handles=legend_handles, fontsize=10, ncol=6, loc="outside lower center")
    fig.suptitle("Combined Truvari precision versus recall: solo callers and TrussSV", fontsize=19)
    output = figures / "truvari_all_callers_precision_recall.png"
    save_figure(fig, output)
    chart_map.append({"figure": output.name, "chart_type": "faceted scatter", "title": "Combined Truvari precision versus recall: solo callers and TrussSV", "source_table": "truvari_metrics.tsv", "metric": "precision versus recall"})


def coverage_plots(observations: list[dict[str, Any]], figures: Path, chart_map: list[dict[str, str]]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.8), constrained_layout=True)
    for axis, target_key, measured_key, title in (
        (axes[0], "ilmn_target", "ilmn_measured", "Illumina target versus measured coverage"),
        (axes[1], "ont_target", "ont_measured", "ONT target versus measured coverage"),
    ):
        for experiment in ("E1", "E2"):
            subset = [row for row in observations if row["experiment"] == experiment]
            axis.scatter([row[target_key] for row in subset], [row[measured_key] for row in subset], color=EXPERIMENT_COLORS[experiment], marker=EXPERIMENT_MARKERS[experiment], s=85, edgecolor="#222", linewidth=0.6, alpha=0.88, label=experiment)
            for row in subset:
                axis.annotate(row["plot_label"], (row[target_key], row[measured_key]), xytext=(5, 4), textcoords="offset points", fontsize=8.3)
        limit = max(max(row[target_key] for row in observations), max(row[measured_key] for row in observations)) * 1.08
        axis.plot([0, limit], [0, limit], linestyle="--", color="#4b5563", linewidth=1.2, label="target = measured")
        axis.set_xlim(0, limit)
        axis.set_ylim(0, limit)
        axis.set_title(title)
        axis.set_xlabel("Nominal target coverage (x)")
        axis.set_ylabel("Measured Mosdepth total mean (x)")
        axis.grid(alpha=0.22)
    axes[0].legend(loc="best")
    output = figures / "planned_vs_measured_coverage.png"
    save_figure(fig, output)
    chart_map.append({"figure": output.name, "chart_type": "scatter", "title": "Planned versus measured coverage", "source_table": "retained_observations.tsv", "metric": "target and measured coverage"})

    fig, ax = plt.subplots(figsize=(12, 8), constrained_layout=True)
    for experiment in ("E1", "E2"):
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
    ax.legend(handles=[Line2D([0], [0], color=EXPERIMENT_COLORS[e], marker=EXPERIMENT_MARKERS[e], label=e) for e in ("E1", "E2")])
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
                "source_path": source_relative(smn_files[0], dayoa_root),
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
    summary: dict[tuple[str, str], tuple[int, int]] = {}
    for observation in obs_order:
        for gene in gene_order:
            calls = [row for row in segdup_rows if row["observation_id"] == observation["observation_id"] and row["gene"] == gene and row["call_state"] == "non_reference_call"]
            summary[(observation["observation_id"], gene)] = (sum(row["filter"] == "PASS" for row in calls), sum(row["filter"] != "PASS" for row in calls))
    matrix = np.array([[sum(summary[(obs["observation_id"], gene)]) for obs in obs_order] for gene in gene_order], dtype=float)
    cmap = LinearSegmentedColormap.from_list("segdup", ["#f0f1f2", "#c5daea", "#3977a8", "#213f5a"])
    fig, ax = plt.subplots(figsize=(max(16, len(obs_order) * 1.0), max(7, len(gene_order) * 0.5)), constrained_layout=True)
    image = ax.imshow(matrix, cmap=cmap, aspect="auto", vmin=0, vmax=max(1, matrix.max()), alpha=0.8)
    ax.set_title("Combined SegDup non-reference calls by retained observation")
    ax.set_xticks(range(len(obs_order)), [obs["plot_label"] for obs in obs_order], rotation=40, ha="right")
    ax.set_yticks(range(len(gene_order)), gene_order)
    ax.set_xlabel("Retained experiment:AU observation")
    ax.set_ylabel("SegDup gene")
    for row_index, gene in enumerate(gene_order):
        for col_index, observation in enumerate(obs_order):
            passed, failed = summary[(observation["observation_id"], gene)]
            label = "NA" if passed + failed == 0 else (f"P{passed}" if failed == 0 else f"P{passed}/F{failed}")
            ax.text(col_index, row_index, label, ha="center", va="center", fontsize=7.2, color="black")
    bar = fig.colorbar(image, ax=ax, shrink=0.85)
    bar.set_label("Non-reference VCF record count")
    output = figures / "segdup_call_heatmap.png"
    save_figure(fig, output)
    chart_map.append({"figure": output.name, "chart_type": "heatmap", "title": ax.get_title(), "source_table": "segdup_calls.tsv", "metric": "non-reference record count"})

    metrics = ["SMN1_CN", "SMN2_CN", "SMN2delta7_8_CN"]
    smn_by_obs = {row["observation_id"]: row for row in smn_rows}
    smn_matrix = np.full((len(metrics), len(obs_order)), np.nan)
    for row_index, metric in enumerate(metrics):
        for col_index, observation in enumerate(obs_order):
            value = number(smn_by_obs[observation["observation_id"]][metric])
            if value is not None:
                smn_matrix[row_index, col_index] = value
    smn_cmap = plt.get_cmap("YlGnBu").copy()
    smn_cmap.set_bad("#f0f1f2")
    valid = smn_matrix[~np.isnan(smn_matrix)]
    fig, ax = plt.subplots(figsize=(max(15, len(obs_order) * 0.95), 5.2), constrained_layout=True)
    image = ax.imshow(smn_matrix, cmap=smn_cmap, aspect="auto", vmin=0, vmax=max(4, float(valid.max()) if len(valid) else 4), alpha=0.8)
    ax.set_title("Combined SMN1/2 copy-number calls by retained observation")
    ax.set_xticks(range(len(obs_order)), [obs["plot_label"] for obs in obs_order], rotation=40, ha="right")
    ax.set_yticks(range(len(metrics)), ["SMN1 copy number", "SMN2 copy number", "SMN2 Δ7–8 copy number"])
    for row_index, metric in enumerate(metrics):
        for col_index, observation in enumerate(obs_order):
            value = number(smn_by_obs[observation["observation_id"]][metric])
            ax.text(col_index, row_index, "NA" if value is None else f"{value:g}", ha="center", va="center", fontsize=9, color="black")
    bar = fig.colorbar(image, ax=ax, shrink=0.82)
    bar.set_label("Copy-number call")
    output = figures / "smn12_copy_number_heatmap.png"
    save_figure(fig, output)
    chart_map.append({"figure": output.name, "chart_type": "heatmap", "title": ax.get_title(), "source_table": "smn12_calls.tsv", "metric": "SMN1 SMN2 copy number"})
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
    for experiment in ("E1", "E2"):
        exemplar = next(row for row in observations if row["experiment"] == experiment)
        benchmark_path = Path(exemplar["dayoa_root"]) / "results/day/hg38/reports/benchmarks_summary.tsv"
        for raw in read_tsv(benchmark_path):
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
            }
        )
    return task_rows, summary_rows


def benchmark_plots(observations: list[dict[str, Any]], task_rows: list[dict[str, Any]], summary_rows: list[dict[str, Any]], figures: Path, chart_map: list[dict[str, str]]) -> None:
    obs_order = sorted(observations, key=lambda row: (row["experiment"], AU_INDEX[row["au"]]))
    for metric, scale, xlabel, title, filename, color in (
        ("longest_walltime_s", 1 / 3600, "Longest successful execution (hours)", "Per-task walltime by retained observation", "benchmark_per_task_walltime.png", "#3977a8"),
        ("total_cost_usd", 1, "Total task-group cost (USD)", "Per-task cost by retained observation", "benchmark_per_task_cost.png", "#d0783d"),
    ):
        fig, axes = plt.subplots(7, 2, figsize=(18, 28), constrained_layout=True)
        axes = axes.ravel()
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
        fig.suptitle(title, fontsize=19)
        output = figures / filename
        save_figure(fig, output)
        chart_map.append({"figure": output.name, "chart_type": "small-multiple bar", "title": title, "source_table": "benchmark_task_groups.tsv", "metric": metric})

    summaries = sorted(summary_rows, key=lambda row: (row["experiment"], AU_INDEX[row["au"]]))
    labels = [row["plot_label"] for row in summaries]
    x = np.arange(len(labels))
    fig, axes = plt.subplots(1, 3, figsize=(19, 6.5), constrained_layout=True)
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
        axis.set_xticks(x, labels, rotation=45, ha="right", fontsize=8)
        axis.grid(axis="y", alpha=0.2)
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
    coverage_markdown: list[list[str]],
    hard_rows: list[dict[str, Any]],
    truvari_rows: list[dict[str, Any]],
    smn_rows: list[dict[str, Any]],
    benchmark_summaries: list[dict[str, Any]],
    duplicate_count: int,
) -> None:
    figures = assets / "figures"
    tables = assets / "tables"
    e1 = [row for row in observations if row["experiment"] == "E1"]
    e2 = [row for row in observations if row["experiment"] == "E2"]
    e1_ilmn_mae = float(np.mean([abs(row["ilmn_abs_error"]) for row in e1]))
    e2_ilmn_mae = float(np.mean([abs(row["ilmn_abs_error"]) for row in e2]))
    e1_ont_mae = float(np.mean([abs(row["ont_abs_error"]) for row in e1]))
    e2_ont_mae = float(np.mean([abs(row["ont_abs_error"]) for row in e2]))
    trussv = [row for row in truvari_rows if row["caller"] == "TrussSV" and number(row["fscore"]) is not None]
    best_trussv = max(trussv, key=lambda row: row["fscore"])
    costs = {row["observation_id"]: row["total_cost_usd"] for row in benchmark_summaries}
    total_cost_e1 = sum(costs[row["observation_id"]] for row in e1)
    total_cost_e2 = sum(costs[row["observation_id"]] for row in e2)
    e2_below_target = sum(row["ilmn_measured"] < row["ilmn_target"] for row in e2)
    observation_markdown = [
        [
            row["plot_label"],
            f"{row['ilmn_target']}x × {row['ont_target']}x",
            f"{row['ilmn_measured_token']}x × {row['ont_measured_token']}x",
            str(row["subsample_pct"]),
            f"[{row['ont_start_hour']},{row['ont_end_hour']})",
            row["runtime_au"],
            row["selection_status"],
        ]
        for row in sorted(observations, key=lambda row: (row["experiment"], AU_INDEX[row["au"]]))
    ]

    image = lambda name: f"![{name}]({relative_asset(report_path, figures / name)})"
    table_link = lambda name: f"[{name}]({relative_asset(report_path, tables / name)})"
    lines: list[str] = [
        "# HG002 Bjuice combined downsampling heatmap report",
        "",
        "## Technical summary",
        "",
        f"This report combines **{len(observations)} retained measured-coverage observations** from two completed HG002 HIOMR2 kitchensink-mega downsampling experiments. Exact duplicate identity is `(AU, measured ILMN, measured ONT)`; **{duplicate_count} older E1 observation(s)** were superseded by E2. Experiment provenance remains visible as `E1:<AU>` or `E2:<AU>` in every chart and table.",
        "",
        f"E2 reduced mean absolute Illumina target error to **{e2_ilmn_mae:.2f}x**, versus **{e1_ilmn_mae:.2f}x** in E1, but measured Illumina coverage remained below nominal in **{e2_below_target}/7 E2 AUs**. ONT mean absolute target error was **{e2_ont_mae:.2f}x** in E2 and **{e1_ont_mae:.2f}x** in E1. The strongest retained TrussSV global F-score was **{best_trussv['fscore']:.4f}** at **{best_trussv['plot_label']}**. Successful benchmark task rows sum to **${total_cost_e1:,.2f}** for retained E1 observations and **${total_cost_e2:,.2f}** for retained E2 observations.",
        "",
        "E1 completed its live rerun at `rc=0` on 2026-08-14; E2 completed the retained kitchensink-mega/final-MultiQC closure at `rc=0` on 2026-08-16. E1's manifest fractions were present, but its Illumina rule did not apply them as intended; E1 coverage is therefore used only as measured observational evidence. E2 is the corrected re-downsampling experiment. Analytical packaging is not part of the E2 completion claim.",
        "",
        "## Where data exist: unified measured-coverage grid",
        "",
        "Rows are measured Illumina coverage and columns are measured ONT coverage. The Markdown grid is shown from largest ILMN value at the top to smallest at the bottom, matching the plotted heatmap's smallest-at-bottom orientation. `—` is a true grid gap.",
        "",
        markdown_table(coverage_markdown[0], coverage_markdown[1:]),
        "",
        image("combined_measured_coverage_grid.png"),
        "",
        "### Retained observation provenance",
        "",
        markdown_table(["Observation", "Nominal ILMN × ONT", "Measured ILMN × ONT", "ILMN fraction", "ONT hours", "Runtime AU", "Selection"], observation_markdown),
        "",
        "The full retained-observation table includes nominal targets, exact measured tokens, fractions, ONT windows, source paths, and selection status: " + table_link("retained_observations.tsv") + ".",
        "",
        "## Coverage targeting and ONT yield",
        "",
        image("planned_vs_measured_coverage.png"),
        "",
        image("ont_coverage_vs_runtime.png"),
        "",
        "The ONT figure is descriptive aligned yield versus cumulative `[0,end)` input duration. Lines connect experiment-specific hour means and are not a fitted physical yield model.",
        "",
        "## Hard-VCF GIAB high-confidence concordance",
        "",
        "Crude SNP uses `SNPts + SNPtv/2` independently for TP, FN, and FP; precision, recall, and F-score are recalculated from those composite counts. Every heatmap uses the same unified measured-coverage grid and retains all experiment/AU labels in shared cells.",
        "",
    ]
    for klass, title in (("snp", "SNP (SNPts + SNPtv/2)"), ("ins_50", "INS_50"), ("del_50", "DEL_50")):
        lines.extend(
            [
                f"### {title}",
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
            image("truvari_trussv_global_fscore_heatmap.png"),
            "",
            image("truvari_trussv_gt_concordance_heatmap.png"),
            "",
            image("truvari_all_callers_precision_recall.png"),
            "",
            "Caller color and shape are stable; E1 uses open markers and E2 filled markers. Points with undefined raw precision or recall remain in the table as `NA` and are not plotted. Exact raw-summary values: " + table_link("truvari_metrics.tsv") + ".",
            "",
            "## SegDup and SMN1/2 calls",
            "",
            image("segdup_call_heatmap.png"),
            "",
            "SegDup cell codes are `P#` for PASS non-reference calls, `F#` for non-PASS calls, and `NA` for no non-reference call. Exact records: " + table_link("segdup_calls.tsv") + ".",
            "",
            image("smn12_copy_number_heatmap.png"),
            "",
            "Undefined low-coverage SMN copy-number calls remain `NA`; they are not coerced to zero. Complete SMN fields: " + table_link("smn12_calls.tsv") + ".",
            "",
            "## Benchmark cost and parallel-aware runtime",
            "",
            image("benchmark_per_task_walltime.png"),
            "",
            image("benchmark_per_task_cost.png"),
            "",
            image("benchmark_au_totals.png"),
            "",
            "The task plots show the top 12 groups per retained observation; the TSV retains every successful task group. Observed makespan spans the first through last benchmark timestamp. Active-interval union merges overlapping task intervals. Longest task is a lower bound, not a DAG-derived critical path.",
            "Nine successful E2 benchmark records have no source-reported task cost. They remain counted as unpriced records; cost totals sum only numeric source values and therefore represent a documented lower bound.",
            "",
            "Supporting benchmark tables: " + table_link("benchmark_task_groups.tsv") + " and " + table_link("benchmark_au_totals.tsv") + ".",
            "",
            "## Scope, methods, and limitations",
            "",
            "- Coverage is the exact `chrom=total` Mosdepth mean from the HIOMR2 short-read and long-read alignment summaries.",
            "- Hard-VCF metrics are restricted to `ROI=giabHC`; the crude SNP construction is intentionally not a standard variant-class aggregation.",
            "- Truvari metrics come from raw `summary.json`. Undefined no-call rates are `NA`, even where a downstream report-oriented artifact normalized them to zero.",
            "- SegDup is descriptive callset output, not truth/query concordance. A no-call state is not evidence of reference genotype truth.",
            "- The two experiments reuse the same HG002 source material and their downsampled inputs are nested; observations are not statistically independent. Results are descriptive and no causal or inferential claim is made.",
            "- E1 and E2 may contain different runtime software provenance because E2 was completed after authorized R&D reporting repairs. The report uses produced artifacts and does not relabel E2 as a pristine later release execution.",
            "",
            "## Audit and reproducibility",
            "",
            "- Source inventory with original and locally verified SHA-256 values: " + table_link("source_inventory.tsv") + ".",
            "- Exact duplicate decisions: " + table_link("duplicate_resolution.tsv") + ".",
            "- Duplicate metric comparisons: " + table_link("duplicate_metric_audit.tsv") + ".",
            "- Figure-to-table mapping: " + table_link("chart_map.tsv") + ".",
            "",
            "Generated from bounded DYEC evidence snapshots on 2026-08-16.",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n")


def duplicate_metric_audit(resolutions: list[dict[str, Any]], hard_rows: list[dict[str, Any]], truvari_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    audits: list[dict[str, Any]] = []
    for resolution in resolutions:
        for family, rows, group_field, metrics in (
            ("hard_vcf", hard_rows, "class", ("fscore", "fn", "fp")),
            ("truvari", truvari_rows, "caller", ("fscore", "precision", "recall", "gt_concordance", "fn", "fp")),
        ):
            dropped = [row for row in rows if row["experiment"] == resolution["dropped_experiment"] and row["runtime_au"] == resolution["dropped_runtime_au"]]
            retained = [row for row in rows if row["experiment"] == resolution["retained_experiment"] and row["runtime_au"] == resolution["retained_runtime_au"]]
            dropped_by = {row[group_field]: row for row in dropped}
            retained_by = {row[group_field]: row for row in retained}
            for group in sorted(set(dropped_by) | set(retained_by)):
                for metric in metrics:
                    old = number(dropped_by.get(group, {}).get(metric))
                    new = number(retained_by.get(group, {}).get(metric))
                    audits.append(
                        {
                            "au": resolution["au"],
                            "ilmn_measured_token": resolution["ilmn_measured_token"],
                            "ont_measured_token": resolution["ont_measured_token"],
                            "family": family,
                            "group": group,
                            "metric": metric,
                            "dropped_E1_value": old,
                            "retained_E2_value": new,
                            "absolute_delta": abs(new - old) if old is not None and new is not None else None,
                            "identical": old == new if old is not None and new is not None else None,
                        }
                    )
    return audits


def main() -> None:
    args = parse_args()
    figures = args.assets_dir / "figures"
    tables = args.assets_dir / "tables"
    figures.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)

    source_observations: list[dict[str, Any]] = []
    source_inventory: list[dict[str, Any]] = []
    for experiment in ("E1", "E2"):
        observations, metadata = parse_experiment(experiment, args.evidence_root)
        source_observations.extend(observations)
        source_inventory.extend(metadata["inventory"])
    if len(source_observations) != 14:
        raise ValueError("expected fourteen source observations")

    retained, resolutions, all_status = deduplicate(source_observations)
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
    coverage_md = coverage_grid(retained, figures, tables, chart_map)
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
    duplicate_audit = duplicate_metric_audit(resolutions, all_hard_rows, all_truvari_rows)

    observation_fields = [
        "observation_id", "experiment", "experiment_title", "analysis_id", "au", "runtime_au", "source_analysis_unit_uid",
        "plot_label", "ilmn_target", "ont_target", "ilmn_measured_token", "ont_measured_token", "ilmn_abs_error", "ont_abs_error",
        "subsample_pct", "ont_start_hour", "ont_end_hour", "selection_status", "coverage_source_ilmn", "coverage_source_ont",
    ]
    write_tsv(tables / "retained_observations.tsv", retained, observation_fields)
    write_tsv(tables / "duplicate_resolution.tsv", resolutions, ["au", "ilmn_measured_token", "ont_measured_token", "dropped_experiment", "dropped_runtime_au", "retained_experiment", "retained_runtime_au", "reason"])
    write_tsv(tables / "duplicate_metric_audit.tsv", duplicate_audit, ["au", "ilmn_measured_token", "ont_measured_token", "family", "group", "metric", "dropped_E1_value", "retained_E2_value", "absolute_delta", "identical"])
    write_tsv(tables / "hard_vcf_giabhc_metrics.tsv", hard_rows, ["observation_id", "experiment", "analysis_id", "au", "runtime_au", "plot_label", "ilmn_measured_token", "ont_measured_token", "roi", "class", "tp", "fn", "fp", "precision", "recall", "fscore", "source_path"])
    write_tsv(tables / "truvari_metrics.tsv", truvari_rows, ["observation_id", "experiment", "analysis_id", "au", "runtime_au", "plot_label", "ilmn_measured_token", "ont_measured_token", "caller", "tp_base", "tp_comp", "fn", "fp", "precision", "recall", "fscore", "gt_concordance", "base_count", "query_count", "source_path"])
    write_tsv(tables / "segdup_calls.tsv", segdup_rows, ["observation_id", "experiment", "analysis_id", "au", "runtime_au", "plot_label", "ilmn_measured_token", "ont_measured_token", "gene", "call_state", "chrom", "pos", "ref", "alt", "filter", "gt", "qual"])
    write_tsv(tables / "smn12_calls.tsv", smn_rows, ["observation_id", "experiment", "analysis_id", "au", "runtime_au", "plot_label", "ilmn_measured_token", "ont_measured_token", "SMN1_CN", "SMN2_CN", "SMN2delta7_8_CN", "Total_CN_raw", "Full_length_CN_raw", "g27134TG_CN", "isSMA", "isCarrier", "Info", "Median_depth", "source_path"])
    write_tsv(tables / "benchmark_task_groups.tsv", benchmark_tasks, ["observation_id", "experiment", "analysis_id", "au", "runtime_au", "plot_label", "ilmn_measured_token", "ont_measured_token", "rule", "successful_records", "priced_records", "unpriced_records", "longest_walltime_s", "total_cost_usd", "allocated_vcpu_h", "observed_cpu_h"])
    write_tsv(tables / "benchmark_au_totals.tsv", benchmark_summaries, ["observation_id", "experiment", "analysis_id", "au", "runtime_au", "plot_label", "ilmn_measured_token", "ont_measured_token", "successful_records", "priced_records", "unpriced_records", "task_groups", "total_cost_usd", "allocated_vcpu_h", "observed_cpu_h", "sum_task_wall_h", "observed_makespan_h", "active_interval_union_h", "longest_task_h"])
    write_tsv(tables / "source_inventory.tsv", source_inventory, ["experiment", "analysis_root", "relative_path", "bytes", "mtime_epoch", "sha256", "local_path", "local_sha256", "local_sha256_match"])
    write_tsv(tables / "chart_map.tsv", chart_map, ["figure", "chart_type", "title", "source_table", "metric"])

    heatmaps = [row for row in chart_map if row["chart_type"] == "heatmap"]
    concordance_heatmaps = [row for row in heatmaps if row["figure"] != "combined_measured_coverage_grid.png" and row["figure"] not in {"segdup_call_heatmap.png", "smn12_copy_number_heatmap.png"}]
    if len(concordance_heatmaps) != 11:
        raise AssertionError(f"expected 11 concordance heatmaps; found {len(concordance_heatmaps)}")
    if len([row for row in heatmaps if row["figure"] == "combined_measured_coverage_grid.png"]) != 1:
        raise AssertionError("missing coverage layout heatmap")

    build_report(args.report_path, args.assets_dir, retained, coverage_md, hard_rows, truvari_rows, smn_rows, benchmark_summaries, len(resolutions))

    expected_tables = {
        "retained_observations.tsv", "coverage_grid.tsv", "duplicate_resolution.tsv", "duplicate_metric_audit.tsv",
        "hard_vcf_giabhc_metrics.tsv", "truvari_metrics.tsv", "segdup_calls.tsv", "smn12_calls.tsv",
        "benchmark_task_groups.tsv", "benchmark_au_totals.tsv", "source_inventory.tsv", "chart_map.tsv",
    }
    missing_tables = [name for name in expected_tables if not (tables / name).is_file()]
    if missing_tables:
        raise AssertionError(f"missing tables: {missing_tables}")
    if not args.report_path.is_file():
        raise AssertionError("report was not created")
    print(json.dumps({"report": str(args.report_path), "assets": str(args.assets_dir), "source_observations": len(source_observations), "retained_observations": len(retained), "exact_duplicates": len(resolutions), "concordance_heatmaps": len(concordance_heatmaps), "all_heatmaps": len(heatmaps), "figures": len(chart_map), "tables": len(expected_tables)}, indent=2))


if __name__ == "__main__":
    main()
