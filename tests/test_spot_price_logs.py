from __future__ import annotations

import csv
import io

import pytest

from daylily_ec.spot_price_logs import (
    SPOT_PRICE_LOG_JSON_BEGIN,
    build_remote_spot_price_log_script,
    extract_remote_spot_price_payload,
    parse_spot_price_log_line,
    spot_price_rows_to_csv,
)


def test_parse_legacy_spot_price_log_line() -> None:
    row = parse_spot_price_log_line(
        "2026-07-03 12:01:02 - Region: us-west-2, AZ: us-west-2c, "
        "Instance type: f2.6xlarge, Spot price: 1.234 USD/hour",
        source_path="/fsx/scratch/ip-10-0-0-1_spot_price.log",
        line_number=7,
        cluster="jemx3",
        headnode_instance_id="i-head",
    )

    assert row is not None
    assert row["cluster"] == "jemx3"
    assert row["headnode_instance_id"] == "i-head"
    assert row["recorded_at"] == "2026-07-03 12:01:02"
    assert row["region"] == "us-west-2"
    assert row["availability_zone"] == "us-west-2c"
    assert row["instance_type"] == "f2.6xlarge"
    assert row["spot_price_usd_per_hour"] == "1.234"
    assert row["slurm_partition"] == ""
    assert row["compute_resource"] == ""


def test_parse_context_spot_price_log_line() -> None:
    row = parse_spot_price_log_line(
        "2026-07-03 12:01:02 - Node type: ComputeFleet, Partition: dragen, "
        "Compute resource: f26xlarge, Hostname: ip-10-0-0-1, Instance id: i-node, "
        "Region: us-west-2, AZ: us-west-2c, Instance type: f2.6xlarge, "
        "Spot price: 1.234 USD/hour",
        source_path="/fsx/logs/ip-10-0-0-1.log",
        line_number=3,
    )

    assert row is not None
    assert row["node_type"] == "ComputeFleet"
    assert row["slurm_partition"] == "dragen"
    assert row["compute_resource"] == "f26xlarge"
    assert row["hostname"] == "ip-10-0-0-1"
    assert row["instance_id"] == "i-node"


def test_parse_malformed_spot_price_log_line_fails() -> None:
    with pytest.raises(ValueError, match="Malformed spot price log line"):
        parse_spot_price_log_line("2026-07-03 Spot price: broken")


def test_spot_price_rows_to_csv_includes_public_schema() -> None:
    row = parse_spot_price_log_line(
        "2026-07-03 12:01:02 - Region: us-west-2, AZ: us-west-2c, "
        "Instance type: r7i.2xlarge, Spot price: 0.456 USD/hour",
        cluster="cluster-a",
        headnode_instance_id="i-head",
    )
    assert row is not None

    text = spot_price_rows_to_csv([row])
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)

    assert reader.fieldnames is not None
    assert reader.fieldnames[:4] == [
        "cluster",
        "headnode_instance_id",
        "source_path",
        "line_number",
    ]
    assert rows[0]["cluster"] == "cluster-a"
    assert rows[0]["spot_price_usd_per_hour"] == "0.456"


def test_remote_spot_log_script_uses_explicit_paths_and_markers() -> None:
    script = build_remote_spot_price_log_script(
        paths=["/fsx/logs", "/fsx/scratch"],
        name_globs=["*.log", "*spot_price.txt"],
    )

    assert SPOT_PRICE_LOG_JSON_BEGIN in script
    assert 'roots = ["/fsx/logs", "/fsx/scratch"]' in script
    assert 'name_globs = ["*.log", "*spot_price.txt"]' in script
    assert "Spot price:" in script


def test_extract_remote_spot_price_payload() -> None:
    payload = extract_remote_spot_price_payload(
        "noise\n"
        "__DYEC_SPOT_PRICE_LOGS_JSON_BEGIN__\n"
        '{"rows": [], "visited_files": 0}\n'
        "__DYEC_SPOT_PRICE_LOGS_JSON_END__\n"
    )

    assert payload["rows"] == []
    assert payload["visited_files"] == 0
