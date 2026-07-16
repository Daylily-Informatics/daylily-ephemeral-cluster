#!/usr/bin/env python3
"""Build the audit CSV, boxplot fragment, and canonical portable report artifact."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import sqlite3
from pathlib import Path
from typing import Any, Iterable


AZS = ("us-west-2a", "us-west-2b", "us-west-2c", "us-west-2d")
PARTITIONS = ("i96nvme", "i128nvme", "i192nvme", "i384nvme", "i192hugenvme")


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def box(values: list[float]) -> dict[str, float]:
    q1, median, q3 = (percentile(values, fraction) for fraction in (0.25, 0.5, 0.75))
    iqr = q3 - q1
    low_fence, high_fence = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    inside = [value for value in values if low_fence <= value <= high_fence]
    return {
        "q1": q1,
        "median": median,
        "q3": q3,
        "whisker_low": min(inside),
        "whisker_high": max(inside),
    }


def assessment(snapshot: dict[str, Any], az: str, partition: str, instance_type: str) -> dict[str, Any]:
    price = snapshot["price_history_summary"][az][instance_type]
    bid = snapshot["type_bid_assessment"][az][partition][instance_type]
    launch = snapshot["cloudtrail"]["summary"][az].get(instance_type, {})
    offered = instance_type in snapshot["offered"][az]
    hard_exclude = (
        offered
        and price["min_usd_per_hour"] > 9.99
        and bid["price_above_all_containing_resource_bids"]
    )
    if not offered:
        recommendation = "EXCLUDE TODAY"
        reason = "Not offered in this Availability Zone."
    elif hard_exclude:
        recommendation = "EXCLUDE TODAY"
        reason = "72-hour minimum remained above the $9.99 global Spot ceiling."
    elif bid["price_above_all_containing_resource_bids"]:
        recommendation = "PRICE-GATED NOW; RETAIN"
        reason = "Current price exceeds today's computed resource bid, but the condition is not a persistent global-cap breach."
    elif launch.get("insufficient_capacity_events", 0) and not launch.get("launched_instances", 0):
        recommendation = "CAPACITY WATCH"
        reason = "Observed insufficient-capacity errors without a success in the account sample."
    else:
        recommendation = "RETAIN"
        reason = "Offered in the AZ and not price-gated by today's computed bid."
    return {
        "availability_zone": az,
        "partition": partition,
        "instance_type": instance_type,
        "offered": offered,
        "current_spot_usd_hour": price["current_usd_per_hour"],
        "median_72h_usd_hour": price["median_usd_per_hour"],
        "min_72h_usd_hour": price["min_usd_per_hour"],
        "max_72h_usd_hour": price["max_usd_per_hour"],
        "computed_bid_usd_hour": bid["highest_containing_resource_bid"],
        "success_instances": launch.get("launched_instances", 0),
        "insufficient_capacity_events": launch.get("insufficient_capacity_events", 0),
        "price_cap_failure_events": launch.get("spot_max_price_too_low_events", 0),
        "recommendation": recommendation,
        "reason": reason,
    }


def svg_boxplot(snapshot: dict[str, Any], width: int = 768) -> str:
    margin_left, margin_right, top = 62, 16, 28
    row_height, plot_height = 210, 148
    height = top + row_height * len(PARTITIONS)
    plot_width = width - margin_left - margin_right
    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-labelledby="boxplot-title boxplot-desc" style="max-width:100%;height:auto;color:CanvasText;background:Canvas">',
        '<title id="boxplot-title">NVMe partition Spot price boxplots by us-west-2 Availability Zone</title>',
        '<desc id="boxplot-desc">Each box summarizes one 72-hour median Linux Spot price per configured instance type. Points show every instance type. Boxes use Tukey quartiles and whiskers.</desc>',
    ]
    for row_index, partition in enumerate(PARTITIONS):
        y0 = top + row_index * row_height
        values_by_az: dict[str, list[dict[str, Any]]] = {}
        for az in AZS:
            values_by_az[az] = [
                {
                    "instance_type": instance_type,
                    "value": snapshot["price_history_summary"][az][instance_type]["median_usd_per_hour"],
                }
                for instance_type in snapshot["configured"][az][partition]
            ]
        vmax = max(item["value"] for values in values_by_az.values() for item in values) * 1.08
        scale_y = lambda value: y0 + plot_height - (value / vmax) * plot_height
        parts.append(f'<text x="{margin_left}" y="{y0 - 7}" font-size="15" font-weight="500">{partition}</text>')
        for fraction in (0.0, 0.5, 1.0):
            yy = y0 + plot_height - fraction * plot_height
            parts.append(f'<line x1="{margin_left}" x2="{width - margin_right}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="GrayText" stroke-opacity="0.22"/>')
            parts.append(f'<text x="{margin_left - 8}" y="{yy + 4:.1f}" text-anchor="end" font-size="11" fill="GrayText">${vmax * fraction:.1f}</text>')
        slot = plot_width / len(AZS)
        for az_index, az in enumerate(AZS):
            cx = margin_left + slot * (az_index + 0.5)
            values = [item["value"] for item in values_by_az[az]]
            stats = box(values)
            box_width = min(54, slot * 0.42)
            q1y, medy, q3y = (scale_y(stats[key]) for key in ("q1", "median", "q3"))
            lowy, highy = (scale_y(stats[key]) for key in ("whisker_low", "whisker_high"))
            parts.extend([
                f'<line x1="{cx:.1f}" x2="{cx:.1f}" y1="{highy:.1f}" y2="{lowy:.1f}" stroke="currentColor"/>',
                f'<line x1="{cx - box_width * .25:.1f}" x2="{cx + box_width * .25:.1f}" y1="{highy:.1f}" y2="{highy:.1f}" stroke="currentColor"/>',
                f'<line x1="{cx - box_width * .25:.1f}" x2="{cx + box_width * .25:.1f}" y1="{lowy:.1f}" y2="{lowy:.1f}" stroke="currentColor"/>',
                f'<rect x="{cx - box_width / 2:.1f}" y="{q3y:.1f}" width="{box_width:.1f}" height="{max(1, q1y - q3y):.1f}" fill="Highlight" fill-opacity="0.16" stroke="Highlight"/>',
                f'<line x1="{cx - box_width / 2:.1f}" x2="{cx + box_width / 2:.1f}" y1="{medy:.1f}" y2="{medy:.1f}" stroke="Highlight" stroke-width="2"/>',
            ])
            for point_index, item in enumerate(values_by_az[az]):
                jitter = ((point_index * 17) % 31 - 15) / 15 * box_width * 0.72
                label = html.escape(f"{partition} · {az} · {item['instance_type']} · 72h median ${item['value']:.4f}/hour")
                parts.append(f'<circle cx="{cx + jitter:.1f}" cy="{scale_y(item["value"]):.1f}" r="2.7" fill="Highlight" fill-opacity="0.66" data-label="{label}"/>')
            parts.append(f'<text x="{cx:.1f}" y="{y0 + plot_height + 19}" text-anchor="middle" font-size="11" fill="GrayText">{az[-1]}</text>')
        parts.append(f'<text x="{width - margin_right}" y="{y0 - 7}" text-anchor="end" font-size="11" fill="GrayText">72h median $/instance-hour</text>')
    parts.append("</svg>")
    return "".join(parts)


def inline_fragment(snapshot: dict[str, Any], svg: str) -> str:
    return f'''<div id="usw2-nvme-spot-boxplots">
<style>
#usw2-nvme-spot-boxplots {{ position: relative; width: 100%; color: var(--foreground); }}
#usw2-nvme-spot-boxplots .plot {{ width: 100%; }}
#usw2-nvme-spot-boxplots .plot svg {{ display: block; width: 100%; height: auto; }}
#usw2-nvme-spot-boxplots .tooltip {{ position: absolute; display: none; max-width: 260px; padding: 8px 10px; border: 1px solid var(--border); border-radius: 8px; background: var(--popover); color: var(--popover-foreground); pointer-events: none; }}
#usw2-nvme-spot-boxplots .caption {{ margin-top: 8px; color: var(--muted-foreground); }}
</style>
<div class="plot">{svg.replace('CanvasText', 'var(--foreground)').replace('Canvas', 'transparent').replace('GrayText', 'var(--muted-foreground)').replace('Highlight', 'var(--viz-series-1)')}</div>
<div class="tooltip text-small" role="status" aria-live="polite"></div>
<div class="caption text-small">Each point is one configured instance type's 72-hour median Linux/UNIX Spot price; boxes summarize the types within that partition and AZ. Tukey whiskers; dots outside them are outliers.</div>
<script>
(() => {{
  const root = document.getElementById('usw2-nvme-spot-boxplots');
  const tip = root.querySelector('.tooltip');
  for (const mark of root.querySelectorAll('circle[data-label]')) {{
    mark.addEventListener('pointerenter', () => {{ tip.textContent = mark.dataset.label; tip.style.display = 'block'; }});
    mark.addEventListener('pointermove', (event) => {{
      const rect = root.getBoundingClientRect();
      const left = Math.min(Math.max(8, event.clientX - rect.left + 10), Math.max(8, rect.width - 270));
      tip.style.left = `${{left}}px`;
      tip.style.top = `${{Math.max(8, event.clientY - rect.top - 42)}}px`;
    }});
    mark.addEventListener('pointerleave', () => {{ tip.style.display = 'none'; }});
  }}
}})();
</script>
</div>
'''


def markdown_list(items: Iterable[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def query_rows(connection: sqlite3.Connection, sql: str) -> list[dict[str, Any]]:
    cursor = connection.execute(sql)
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--audit-csv", type=Path, required=True)
    parser.add_argument("--boxplot-svg", type=Path, required=True)
    parser.add_argument("--visualization", type=Path, required=True)
    args = parser.parse_args()

    snapshot = json.loads(args.snapshot.read_text())
    rows = [
        assessment(snapshot, az, partition, instance_type)
        for az in AZS
        for partition in PARTITIONS
        for instance_type in snapshot["configured"][az][partition]
    ]
    fieldnames = list(rows[0])
    args.audit_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.audit_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    svg = svg_boxplot(snapshot)
    args.boxplot_svg.write_text(svg + "\n")
    args.visualization.parent.mkdir(parents=True, exist_ok=True)
    args.visualization.write_text(inline_fragment(snapshot, svg))

    exclude_rows = [row for row in rows if row["recommendation"] == "EXCLUDE TODAY"]
    watch_rows = [row for row in rows if row["recommendation"] == "PRICE-GATED NOW; RETAIN"]
    partition_rows = []
    for az in AZS:
        for partition in PARTITIONS:
            summary = snapshot["partition_summary"][az][partition]
            partition_rows.append({
                "availability_zone": az,
                "partition": partition,
                "configured_types": summary["configured_type_count"],
                "offered_types": summary["offered_type_count"],
                "placement_score": summary["placement_score"],
                "launched_instances_72h": summary["launch_success_instances"],
                "capacity_errors_72h": summary["insufficient_capacity_events"],
                "price_cap_errors_72h": summary["spot_max_price_too_low_events"],
                "exclude_today_count": sum(
                    row["availability_zone"] == az
                    and row["partition"] == partition
                    and row["recommendation"] == "EXCLUDE TODAY"
                    for row in rows
                ),
            })

    connection = sqlite3.connect(":memory:")
    connection.execute(
        """CREATE TABLE type_audit (
        availability_zone TEXT, partition TEXT, instance_type TEXT, offered INTEGER,
        current_spot_usd_hour REAL, median_72h_usd_hour REAL, min_72h_usd_hour REAL,
        max_72h_usd_hour REAL, computed_bid_usd_hour REAL, success_instances INTEGER,
        insufficient_capacity_events INTEGER, price_cap_failure_events INTEGER,
        recommendation TEXT, reason TEXT)"""
    )
    connection.executemany(
        "INSERT INTO type_audit VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [[int(value) if key == "offered" else value for key, value in row.items()] for row in rows],
    )
    connection.execute(
        """CREATE TABLE partition_summary (
        availability_zone TEXT, partition TEXT, configured_types INTEGER, offered_types INTEGER,
        placement_score INTEGER, launched_instances_72h INTEGER, capacity_errors_72h INTEGER,
        price_cap_errors_72h INTEGER, exclude_today_count INTEGER)"""
    )
    connection.executemany(
        "INSERT INTO partition_summary VALUES (?,?,?,?,?,?,?,?,?)",
        [list(row.values()) for row in partition_rows],
    )
    placement_score_sql = """SELECT partition, availability_zone, placement_score
    FROM partition_summary
    ORDER BY CASE partition
      WHEN 'i96nvme' THEN 1 WHEN 'i128nvme' THEN 2 WHEN 'i192nvme' THEN 3
      WHEN 'i384nvme' THEN 4 WHEN 'i192hugenvme' THEN 5 END,
      availability_zone"""

    best_az = {
        "i96nvme": "All four AZs score 9; us-west-2c has no currently price-gated type.",
        "i128nvme": "us-west-2a scores 6 (best), after excluding x2iedn.metal; us-west-2b is next at 3.",
        "i192nvme": "us-west-2b scores 9 (best) with no current price-gated type.",
        "i192hugenvme": "us-west-2b scores 7 (best) with no current price-gated type.",
        "i384nvme": "No healthy Spot choice: scores are 1, 1, 1, and 2. If unavoidable, us-west-2d is least weak; prefer the on-demand template for reliability.",
    }
    strong_by_az = {
        az: [row["instance_type"] for row in exclude_rows if row["availability_zone"] == az]
        for az in AZS
    }
    summary_body = f"""## Technical summary

All **282 configured partition/type/AZ memberships** are structurally offered and have Linux/UNIX Spot price history. The actionable problem today is not missing EC2 offerings; it is price gating and weak large-instance capacity.

The strongest recommendation is to **temporarily exclude {len(exclude_rows)} partition/type/AZ memberships** whose 72-hour minimum Spot price never fell below DYEC's **$9.99/hour global ceiling**. Most are `i384nvme` types. Leave the other currently price-gated types defined: their prices are nearer the computed resource bid, and some have successful launches in the same 72-hour window.

The account sample contains **469 relevant Spot `RunInstances` events**: **229 launched instances**, **20 insufficient-capacity errors**, and **255 `SpotMaxPriceTooLow` errors**. Those errors are workload-correlated, but they confirm that price-cap gating is real. The `i384nvme` placement score is only **1-2 in every AZ**, so do not depend on 384-vCPU Spot capacity for a cluster built now.

### Best current AZ by partition

{markdown_list(f'`{partition}` — {guidance}' for partition, guidance in best_az.items())}
"""
    exclude_body = "## Exclusions for clusters built today\n\n" + "\n".join(
        f"- **{az}:** " + (", ".join(f"`{item}`" for item in strong_by_az[az]) or "none")
        for az in AZS
    ) + "\n\nThese are temporary market exclusions, not permanent claims about the instance families. Re-run the collector before a later build."
    method_body = """## Scope, data, and definitions

- Window: `2026-07-13T03:11:01Z` through `2026-07-16T03:11:01Z` (72 hours).
- Price: EC2 Linux/UNIX Spot price per instance-hour in the named AZ.
- Boxplot value: one 72-hour median price per configured instance type, so volatile types do not receive extra statistical weight merely because their price changed more often.
- Placement score: eight-node-equivalent target expressed in vCPU, using AWS's required `capacity-optimized` scoring assumption. The templates use `price-capacity-optimized`, so the score is directional.
- Exclude today: type is offered, current price exceeds every containing compute-resource bid, and its 72-hour minimum remained above the $9.99 global cap.

## Methodology

The collector deduplicated repeated instance types within each partition, queried current AZ offerings, gathered 72-hour Spot price history, requested a partition-pool placement score, and classified account-observed CloudTrail launches and failures. Today's compute-resource bid was reproduced as `min(1.70 × current resource median, $9.99)`.

## Limitations and robustness

AWS does not expose a definitive current capacity flag for each individual Spot pool. Price history is not capacity evidence. Placement scores describe the submitted pool as a whole, are not guaranteed, and are only directly applicable when a later request matches the scored configuration and uses `capacity-optimized`. CloudTrail is an account-specific, retry-correlated sample; zero attempts means no evidence, not unavailability. The chart uses per-type 72-hour medians rather than time-weighted prices.

## Recommended next steps

1. For a build today, apply the listed temporary exclusions only in the matching AZ template.
2. Prefer `us-west-2b` for 192-vCPU NVMe work, `us-west-2a` for 128-vCPU NVMe work, and any AZ for 96-vCPU NVMe work (with `us-west-2c` the cleanest price-gate snapshot).
3. Avoid relying on `i384nvme` Spot. Use the Intel on-demand template when 384-vCPU reliability matters.
4. Re-run this collector immediately before later cluster creation; Spot state and placement scores are time-sensitive.

## Further questions

- Do the 255 price-cap failures materially delay Slurm scaling, or are they only EC2 Fleet override telemetry?
- Would a separate, explicitly approved global-cap policy for `i384nvme` be cheaper than on-demand for the expected job duration?
- Should this report become a pre-create advisory command that never mutates templates?
"""

    sources = [
        {
            "id": "live-snapshot",
            "label": "DYEC us-west-2 Spot market evidence snapshot",
            "path": str(args.snapshot),
            "query": {
                "engine": "AWS CLI with profile lsmc",
                "executed_at": snapshot["metadata"]["collected_at"],
                "description": "Read-only EC2 offerings, Spot price history, placement scores, CloudTrail RunInstances evidence, and current working-tree template membership.",
            },
        },
        {
            "id": "aws-placement-docs",
            "label": "AWS EC2 Spot placement score documentation",
            "href": "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-placement-score.html",
        },
        {
            "id": "aws-price-docs",
            "label": "AWS EC2 Spot price history documentation",
            "href": "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-spot-instances-history.html",
        },
        {
            "id": "aws-spot-docs",
            "label": "AWS EC2 Spot Instances concepts",
            "href": "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-spot-instances.html",
        },
    ]
    columns = [
        {"field": "partition", "label": "Partition"},
        {"field": "configured_types", "label": "Types", "format": "number"},
        {"field": "placement_score", "label": "Score", "format": "number"},
        {"field": "launched_instances_72h", "label": "Launched", "format": "number"},
        {"field": "capacity_errors_72h", "label": "Capacity errors", "format": "number"},
        {"field": "price_cap_errors_72h", "label": "Price-cap errors", "format": "number"},
        {"field": "exclude_today_count", "label": "Exclude today", "format": "number"},
    ]
    tables = []
    blocks: list[dict[str, Any]] = [
        {"id": "technical-summary", "type": "markdown", "body": summary_body, "sourceId": "live-snapshot"},
        {
            "id": "boxplot-intro",
            "type": "markdown",
            "body": "## Spot price distribution across configured NVMe types\n\nBoxes compare the configured instance-type price distributions within each partition and AZ; individual dots preserve every type.",
            "sourceId": "live-snapshot",
        },
        {
            "id": "boxplot",
            "type": "html",
            "body": f'<figure style="margin:0"><div style="max-width:100%;overflow:hidden">{svg}</div><figcaption style="margin-top:8px;color:GrayText">One 72-hour median Linux/UNIX Spot price per configured instance type. Tukey boxes and whiskers; dots show every type.</figcaption></figure>',
        },
        {
            "id": "placement-score-chart",
            "type": "chart",
            "chartId": "placement-scores",
        },
    ]
    for az in AZS:
        table_id = f"partition-summary-{az}"
        table_sql = f"""SELECT partition, configured_types, offered_types, placement_score,
          launched_instances_72h, capacity_errors_72h, price_cap_errors_72h,
          exclude_today_count
        FROM partition_summary
        WHERE availability_zone = '{az}'
        ORDER BY CASE partition
          WHEN 'i96nvme' THEN 1 WHEN 'i128nvme' THEN 2 WHEN 'i192nvme' THEN 3
          WHEN 'i384nvme' THEN 4 WHEN 'i192hugenvme' THEN 5 END"""
        tables.append({
            "id": table_id,
            "title": f"{az} NVMe partition evidence",
            "dataset": table_id,
            "columns": columns,
            "source": {
                "id": f"source-{table_id}",
                "label": f"SQLite derivation for {az} partition summary",
                "path": str(args.snapshot),
                "tables_used": ["partition_summary"],
                "query": {
                    "engine": "sqlite",
                    "sql": table_sql,
                    "description": "Actual query executed against the in-memory normalized market snapshot.",
                },
            },
        })
        blocks.append({"id": f"block-{table_id}", "type": "table", "tableId": table_id})
    blocks.append({"id": "exclusions", "type": "markdown", "body": exclude_body, "sourceId": "live-snapshot"})
    exclusion_columns = [
        {"field": "partition", "label": "Partition"},
        {"field": "instance_type", "label": "Instance type"},
        {"field": "current_spot_usd_hour", "label": "Current", "format": "currency"},
        {"field": "min_72h_usd_hour", "label": "72h min", "format": "currency"},
        {"field": "computed_bid_usd_hour", "label": "Today's bid", "format": "currency"},
        {"field": "price_cap_failure_events", "label": "Cap failures", "format": "number"},
    ]
    for az in AZS:
        table_id = f"exclude-{az}"
        table_sql = f"""SELECT partition, instance_type, current_spot_usd_hour,
          min_72h_usd_hour, computed_bid_usd_hour, price_cap_failure_events
        FROM type_audit
        WHERE availability_zone = '{az}' AND recommendation = 'EXCLUDE TODAY'
        ORDER BY partition, instance_type"""
        tables.append({
            "id": table_id,
            "title": f"{az} temporary exclusions",
            "dataset": table_id,
            "columns": exclusion_columns,
            "source": {
                "id": f"source-{table_id}",
                "label": f"SQLite derivation for {az} exclusions",
                "path": str(args.audit_csv),
                "tables_used": ["type_audit"],
                "query": {
                    "engine": "sqlite",
                    "sql": table_sql,
                    "description": "Actual query executed against the normalized per-type audit rows.",
                },
            },
        })
        blocks.append({"id": f"block-{table_id}", "type": "table", "tableId": table_id})
    blocks.append({"id": "methodology", "type": "markdown", "body": method_body, "sourceId": "live-snapshot"})

    datasets: dict[str, list[dict[str, Any]]] = {}
    datasets["placement-scores"] = query_rows(connection, placement_score_sql)
    for az in AZS:
        partition_table = next(table for table in tables if table["id"] == f"partition-summary-{az}")
        exclusion_table = next(table for table in tables if table["id"] == f"exclude-{az}")
        datasets[f"partition-summary-{az}"] = query_rows(connection, partition_table["source"]["query"]["sql"])
        datasets[f"exclude-{az}"] = query_rows(connection, exclusion_table["source"]["query"]["sql"])
    artifact = {
        "surface": "report",
        "manifest": {
            "version": 1,
            "surface": "report",
            "title": "us-west-2 NVMe Spot market review",
            "description": "Per-AZ assessment of defined NVMe partition types for clusters built on 2026-07-16.",
            "generatedAt": snapshot["metadata"]["collected_at"],
            "blocks": blocks,
            "cards": [],
            "charts": [
                {
                    "id": "placement-scores",
                    "title": "Partition-pool Spot placement scores by AZ",
                    "subtitle": "Directional 1-10 score for an eight-node-equivalent target; 10 is strongest.",
                    "showDescription": True,
                    "intent": "comparison",
                    "type": "bar",
                    "dataset": "placement-scores",
                    "source": {
                        "id": "source-placement-scores",
                        "label": "SQLite derivation for partition placement scores",
                        "path": str(args.snapshot),
                        "tables_used": ["partition_summary"],
                        "query": {
                            "engine": "sqlite",
                            "sql": placement_score_sql,
                            "description": "Actual query executed against the normalized partition summary rows.",
                        },
                    },
                    "xAxisTitle": "Partition",
                    "yAxisTitle": "Placement score (1-10)",
                    "encodings": {
                        "x": {
                            "field": "partition",
                            "type": "nominal",
                            "label": "Partition",
                        },
                        "y": {
                            "field": "placement_score",
                            "type": "quantitative",
                            "format": "number",
                            "label": "Placement score",
                        },
                        "color": {
                            "field": "availability_zone",
                            "type": "nominal",
                            "label": "Availability Zone",
                        },
                    },
                    "valueFormat": "number",
                    "layout": "full",
                    "settings": {
                        "groupMode": "grouped",
                        "showValues": True,
                    },
                }
            ],
            "tables": tables,
        },
        "snapshot": {
            "version": 1,
            "generatedAt": snapshot["metadata"]["collected_at"],
            "status": "ready",
            "datasets": datasets,
            "accessIssues": [],
        },
        "sources": sources,
        "package_info": {
            "audit_csv": str(args.audit_csv),
            "boxplot_svg": str(args.boxplot_svg),
            "chart_method": "Tukey boxplots across one 72-hour median per configured instance type",
            "watch_row_count": len(watch_rows),
        },
    }
    args.artifact.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "artifact": str(args.artifact),
        "audit_csv": str(args.audit_csv),
        "boxplot_svg": str(args.boxplot_svg),
        "visualization": str(args.visualization),
        "rows": len(rows),
        "exclude_today": len(exclude_rows),
        "price_gated_retain": len(watch_rows),
    }, indent=2))


if __name__ == "__main__":
    main()
