#!/usr/bin/env python3
"""Render the compact HG002 Bjuice matrix proposal from retained evidence.

This is a planning-only visual. Existing points use their direct-S3-audited
native-SR measurements and manifest input end hours. Proposed points use exact
input controls. The visual does not impute coverage for a proposed point.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt


FULL_NATIVE_SR_X = 43.73
NEW_AU_CELLS = [
    # (cell ID, nominal ILMN target, direct-ILMN fraction, nominal ONT target, ONT end hour)
    ("N01", 0.5, 0.011433798, 0.5, 1),
    ("N02", 0.5, 0.011433798, 4.0, 8),
    ("N03", 0.5, 0.011433798, 12.0, 24),
    ("N04", 0.5, 0.011433798, 30.0, 72),
    ("N05", 10.0, 0.228675966, 0.5, 1),
    ("N06", 10.0, 0.228675966, 4.0, 8),
    ("N07", 10.0, 0.228675966, 12.0, 24),
    ("N08", 10.0, 0.228675966, 30.0, 72),
    ("N09", 30.0, 0.686027898, 30.0, 72),
    ("N10", FULL_NATIVE_SR_X, 1.0, 30.0, 72),
    ("N11", 2.0, 0.045735193, 0.5, 1),
    ("N12", 2.0, 0.045735193, 4.0, 8),
    ("N13", 2.0, 0.045735193, 12.0, 24),
    ("N14", 2.0, 0.045735193, 30.0, 72),
    ("N15", 20.0, 0.457351932, 0.5, 1),
    ("N16", 20.0, 0.457351932, 4.0, 8),
    ("N17", 20.0, 0.457351932, 12.0, 24),
    ("N18", 20.0, 0.457351932, 30.0, 72),
    ("N19", 5.0, 0.114337983, 30.0, 72),
    ("N20", 15.0, 0.343013949, 30.0, 72),
]
MATRIX_ROWS = [0.5, 2.0, 5.0, 10.0, 15.0, 20.0, 30.0, FULL_NATIVE_SR_X]
MATRIX_WINDOWS = [1, 8, 24, 72]
GROUP_COLORS = {
    "E1": "#3b82b6",
    "E3": "#759b46",
    "E1+P1": "#8b5b9e",
    "E1×2": "#4b5563",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--assets-dir", type=Path, required=True)
    return parser.parse_args()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def existing_group_label(rows: list[dict[str, str]]) -> str:
    counts = Counter(row["experiment"] for row in rows)
    parts = [experiment if count == 1 else f"{experiment}×{count}" for experiment, count in sorted(counts.items())]
    return "+".join(parts)


def plot_compact_overlay(ax: Any, observations: list[dict[str, str]]) -> int:
    grouped: dict[tuple[float, float], list[dict[str, str]]] = defaultdict(list)
    for row in observations:
        grouped[(float(row["ilmn_measured_token"]), float(row["ont_end_hour"]))].append(row)

    # Pale squares establish the deliberately sparse four-by-four control lattice.
    for target in MATRIX_ROWS:
        for end_hour in MATRIX_WINDOWS:
            ax.scatter(end_hour, target, marker="s", s=1600, facecolor="#f2f4f7", edgecolors="#cfd5dd", linewidths=0.9, zorder=1)

    for cell_id, target, _fraction, _ont_target, end_hour in NEW_AU_CELLS:
        ax.scatter(end_hour, target, marker="o", s=600, facecolor="#d97706", edgecolors="none", zorder=3)
        ax.text(end_hour, target, cell_id, ha="center", va="center", fontsize=8.2, color="white", weight="bold", zorder=4)

    for (native_sr, end_hour), rows in sorted(grouped.items()):
        label = existing_group_label(rows)
        color = GROUP_COLORS.get(label, "#4b5563")
        ax.scatter(end_hour, native_sr, marker="o", s=560 + 120 * (len(rows) - 1), facecolor=color, edgecolors="none", alpha=0.96, zorder=5)
        ax.text(end_hour, native_sr, label, ha="center", va="center", fontsize=7.2, color="white", zorder=6)

    ax.set_xlim(-1.4, 74.4)
    ax.set_ylim(-1.5, 46.5)
    ax.set_xticks(MATRIX_WINDOWS)
    ax.set_xticklabels([f"[0,{hour})" for hour in MATRIX_WINDOWS])
    ax.set_yticks(MATRIX_ROWS)
    ax.set_yticklabels(["0.5×", "2×", "5×", "10×", "15×", "20×", "30×", f"full ({FULL_NATIVE_SR_X:g}×)"])
    ax.set_xlabel("Cumulative ONT input window end (hours; existing and planned control)")
    ax.set_ylabel("Native-SR coverage (existing = measured; orange = nominal target)")
    ax.set_title("Orange = exact new controls; colored circles = direct-S3 measured outcomes; grey = deliberately deferred", fontsize=11.5)
    ax.grid(color="#d9dee5", linewidth=0.75)
    ax.set_axisbelow(True)
    return len(grouped)


def main() -> None:
    args = parse_args()
    observations = read_tsv(args.observations)
    if len(observations) != 12:
        raise ValueError(f"expected exactly 12 retained E1/E3/P1 observations; found {len(observations)}")
    if {row["experiment"] for row in observations} != {"E1", "E3", "P1"}:
        raise ValueError("compact proposal requires the E1/E3/P1 report evidence set")

    args.assets_dir.mkdir(parents=True, exist_ok=True)
    proposed_rows = [
        {
            "new_au_id": cell_id,
            "nominal_ilmn_target_x": f"{target:g}",
            "illumina_source_fraction": f"{fraction:.9f}",
            "nominal_ont_target_x": f"{ont_target:g}",
            "ont_start_hour": 0,
            "ont_end_hour": end_hour,
            "ont_window": f"[0,{end_hour})",
            "purpose": (
                "low-SR boundary"
                if target == 0.5
                else "low/mid-SR cross"
                if target in {2.0, 10.0, 20.0}
                else "long-LR SR-ladder anchor"
            ),
            "state": "PROPOSED_NOT_LAUNCHED",
        }
        for cell_id, target, fraction, ont_target, end_hour in NEW_AU_CELLS
    ]
    write_tsv(
        args.assets_dir / "compact_new_au_cells.tsv",
        proposed_rows,
        ["new_au_id", "nominal_ilmn_target_x", "illumina_source_fraction", "nominal_ont_target_x", "ont_start_hour", "ont_end_hour", "ont_window", "purpose", "state"],
    )
    reuse_rows = [
        {
            "observation_id": row["observation_id"],
            "experiment": row["experiment"],
            "analysis_id": row["analysis_id"],
            "au": row["au"],
            "ont_window": f"[{row['ont_start_hour']},{row['ont_end_hour']})",
            "input_illumina_fraction": row["subsample_pct"],
            "measured_native_sr_x": row["ilmn_measured_token"],
            "measured_rsr_x": row["rsr_measured_token"],
            "measured_lr_ont_x": row["ont_measured_token"],
            "reuse_role": "direct-S3 measured evidence; do not infer a planned native-SR control from E1 input label",
        }
        for row in observations
    ]
    write_tsv(
        args.assets_dir / "current_observation_reuse.tsv",
        reuse_rows,
        ["observation_id", "experiment", "analysis_id", "au", "ont_window", "input_illumina_fraction", "measured_native_sr_x", "measured_rsr_x", "measured_lr_ont_x", "reuse_role"],
    )

    fig, ax = plt.subplots(figsize=(16, 8), constrained_layout=True)
    coordinate_count = plot_compact_overlay(ax, observations)
    fig.suptitle("HG002 Bjuice compact matrix: 12 measured outcomes plus 20 proposed controls", fontsize=18, color="#1f2937")
    output = args.assets_dir / "compact_matrix_existing_and_new.png"
    fig.savefig(output, dpi=220, bbox_inches="tight", metadata={"Software": "HG002 Bjuice compact matrix proposal generator"})
    plt.close(fig)
    print(json.dumps({"figure": str(output), "existing_observations": len(observations), "existing_coordinates": coordinate_count, "new_au_cells": len(proposed_rows)}, indent=2))


if __name__ == "__main__":
    main()
