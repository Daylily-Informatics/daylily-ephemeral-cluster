from __future__ import annotations

import csv
import io

import pytest

from daylily_ec.spot_price_logs import (
    SPOT_PRICE_LOG_JSON_BEGIN,
    build_spot_cost_intervals,
    build_remote_spot_price_log_script,
    extract_remote_spot_price_payload,
    parse_spot_price_log_line,
    spot_cost_intervals_to_csv,
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
    assert row["event"] == "start"


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
    assert row["event"] == "start"


def test_parse_lifecycle_start_spot_price_log_line() -> None:
    row = parse_spot_price_log_line(
        "2026-07-03 12:01:02 - Event: start, Node type: ComputeFleet, "
        "Partition: dragen, Compute resource: f26xlarge, Hostname: ip-10-0-0-1, "
        "Instance id: i-node, Region: us-west-2, AZ: us-west-2c, "
        "Instance type: f2.6xlarge, Spot price: 1.234 USD/hour, "
        "Recorded epoch: 1783080062"
    )

    assert row is not None
    assert row["event"] == "start"
    assert row["recorded_at_epoch"] == "1783080062"


def test_parse_shutdown_spot_price_log_line() -> None:
    row = parse_spot_price_log_line(
        "2026-07-03 12:31:02 - Event: shutdown, Node type: ComputeFleet, "
        "Partition: dragen, Compute resource: f26xlarge, Hostname: ip-10-0-0-1, "
        "Instance id: i-node, Region: us-west-2, AZ: us-west-2c, "
        "Instance type: f2.6xlarge, Spot price: 1.234 USD/hour, "
        "Recorded epoch: 1783081862, Shutdown reason: systemd-stop"
    )

    assert row is not None
    assert row["event"] == "shutdown"
    assert row["shutdown_reason"] == "systemd-stop"


def test_parse_interruption_notice_spot_price_log_line() -> None:
    row = parse_spot_price_log_line(
        "2026-07-03 12:29:02 - Event: interruption_notice, Node type: ComputeFleet, "
        "Partition: dragen, Compute resource: f26xlarge, Hostname: ip-10-0-0-1, "
        "Instance id: i-node, Region: us-west-2, AZ: us-west-2c, "
        "Instance type: f2.6xlarge, Spot price: 1.234 USD/hour, "
        "Recorded epoch: 1783081742, Interruption action: terminate, "
        "Interruption time: 2026-07-03T12:31:02Z"
    )

    assert row is not None
    assert row["event"] == "interruption_notice"
    assert row["interruption_action"] == "terminate"
    assert row["interruption_time"] == "2026-07-03T12:31:02Z"


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
    assert reader.fieldnames[-5:] == [
        "event",
        "recorded_at_epoch",
        "interruption_action",
        "interruption_time",
        "shutdown_reason",
    ]


def test_cost_interval_start_shutdown_uses_logged_price() -> None:
    start = parse_spot_price_log_line(
        "2026-07-03 12:01:02 - Node type: ComputeFleet, Partition: dragen, "
        "Compute resource: f26xlarge, Hostname: ip-10-0-0-1, Instance id: i-node, "
        "Region: us-west-2, AZ: us-west-2c, Instance type: f2.6xlarge, "
        "Spot price: 1.200 USD/hour"
    )
    shutdown = parse_spot_price_log_line(
        "2026-07-03 12:31:02 - Event: shutdown, Node type: ComputeFleet, "
        "Partition: dragen, Compute resource: f26xlarge, Hostname: ip-10-0-0-1, "
        "Instance id: i-node, Region: us-west-2, AZ: us-west-2c, "
        "Instance type: f2.6xlarge, Spot price: 1.200 USD/hour, "
        "Recorded epoch: 1783081862, Shutdown reason: systemd-stop"
    )
    assert start is not None
    assert shutdown is not None

    intervals = build_spot_cost_intervals([shutdown, start], price_source="logged")

    assert len(intervals) == 1
    assert intervals[0]["duration_seconds"] == "1800"
    assert intervals[0]["spot_cost_usd"] == "0.60000000"
    assert intervals[0]["open_interval"] == "false"


def test_cost_interval_interruption_notice_closes_without_shutdown() -> None:
    start = parse_spot_price_log_line(
        "2026-07-03 12:01:02 - Node type: ComputeFleet, Partition: dragen, "
        "Compute resource: f26xlarge, Hostname: ip-10-0-0-1, Instance id: i-node, "
        "Region: us-west-2, AZ: us-west-2c, Instance type: f2.6xlarge, "
        "Spot price: 1.200 USD/hour"
    )
    notice = parse_spot_price_log_line(
        "2026-07-03 12:29:02 - Event: interruption_notice, Node type: ComputeFleet, "
        "Partition: dragen, Compute resource: f26xlarge, Hostname: ip-10-0-0-1, "
        "Instance id: i-node, Region: us-west-2, AZ: us-west-2c, "
        "Instance type: f2.6xlarge, Spot price: 1.200 USD/hour, "
        "Recorded epoch: 1783081742, Interruption action: terminate, "
        "Interruption time: 2026-07-03T12:31:02Z"
    )
    assert start is not None
    assert notice is not None

    intervals = build_spot_cost_intervals([start, notice], price_source="logged")

    assert intervals[0]["end_event"] == "interruption_notice"
    assert intervals[0]["duration_seconds"] == "1800"
    assert intervals[0]["interruption_action"] == "terminate"


def test_cost_interval_remains_open_without_end_event() -> None:
    start = parse_spot_price_log_line(
        "2026-07-03 12:01:02 - Node type: ComputeFleet, Partition: dragen, "
        "Compute resource: f26xlarge, Hostname: ip-10-0-0-1, Instance id: i-node, "
        "Region: us-west-2, AZ: us-west-2c, Instance type: f2.6xlarge, "
        "Spot price: 1.200 USD/hour"
    )
    assert start is not None

    intervals = build_spot_cost_intervals([start], price_source="logged")

    assert intervals[0]["open_interval"] == "true"
    assert intervals[0]["spot_cost_usd"] == ""


def test_multiple_instance_rows_pair_by_instance_and_chronology() -> None:
    rows = []
    shutdown_epochs = {"31": "1783081862", "32": "1783081922"}
    for instance_id, minute in [("i-a", "01"), ("i-b", "02"), ("i-a", "31"), ("i-b", "32")]:
        event = "shutdown" if minute in {"31", "32"} else "start"
        extra = (
            f", Recorded epoch: {shutdown_epochs[minute]}, Shutdown reason: systemd-stop"
            if event == "shutdown"
            else ""
        )
        line = (
            f"2026-07-03 12:{minute}:02 - "
            f"{'Event: shutdown, ' if event == 'shutdown' else ''}"
            "Node type: ComputeFleet, Partition: dragen, Compute resource: f26xlarge, "
            f"Hostname: {instance_id}, Instance id: {instance_id}, Region: us-west-2, "
            "AZ: us-west-2c, Instance type: f2.6xlarge, Spot price: 1.200 USD/hour"
            f"{extra}"
        )
        row = parse_spot_price_log_line(line)
        assert row is not None
        rows.append(row)

    intervals = build_spot_cost_intervals(rows, price_source="logged")

    assert [interval["instance_id"] for interval in intervals] == ["i-a", "i-b"]
    assert [interval["duration_seconds"] for interval in intervals] == ["1800", "1800"]


def test_spot_price_history_cost_integrates_price_changes() -> None:
    class FakeEc2Client:
        def describe_spot_price_history(self, **kwargs):
            return {
                "SpotPriceHistory": [
                    {
                        "Timestamp": "2026-07-03T11:00:00+00:00",
                        "SpotPrice": "1.000",
                    },
                    {
                        "Timestamp": "2026-07-03T12:16:02+00:00",
                        "SpotPrice": "2.000",
                    },
                ]
            }

    start = parse_spot_price_log_line(
        "2026-07-03 12:01:02 - Node type: ComputeFleet, Partition: dragen, "
        "Compute resource: f26xlarge, Hostname: ip-10-0-0-1, Instance id: i-node, "
        "Region: us-west-2, AZ: us-west-2c, Instance type: f2.6xlarge, "
        "Spot price: 1.200 USD/hour"
    )
    shutdown = parse_spot_price_log_line(
        "2026-07-03 12:31:02 - Event: shutdown, Node type: ComputeFleet, "
        "Partition: dragen, Compute resource: f26xlarge, Hostname: ip-10-0-0-1, "
        "Instance id: i-node, Region: us-west-2, AZ: us-west-2c, "
        "Instance type: f2.6xlarge, Spot price: 1.200 USD/hour, "
        "Recorded epoch: 1783081862, Shutdown reason: systemd-stop"
    )
    assert start is not None
    assert shutdown is not None

    intervals = build_spot_cost_intervals(
        [start, shutdown],
        price_source="history",
        ec2_client=FakeEc2Client(),
    )

    assert intervals[0]["spot_cost_usd"] == "0.75000000"


def test_cost_interval_csv_includes_summary_schema() -> None:
    text = spot_cost_intervals_to_csv(
        [
            {
                "cluster": "cluster-a",
                "instance_id": "i-node",
                "duration_seconds": "1800",
                "spot_cost_usd": "0.60000000",
            }
        ]
    )
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    assert rows[0]["instance_id"] == "i-node"
    assert rows[0]["spot_cost_usd"] == "0.60000000"


def test_remote_spot_log_script_uses_explicit_paths_and_markers() -> None:
    script = build_remote_spot_price_log_script(
        paths=["/fsx/logs", "/fsx/scratch"],
        name_globs=["*.log", "*spot_price.txt"],
    )

    assert SPOT_PRICE_LOG_JSON_BEGIN in script
    assert 'roots = ["/fsx/logs", "/fsx/scratch"]' in script
    assert 'name_globs = ["*.log", "*spot_price.txt"]' in script
    assert "Spot price:" in script
    assert "interruption_notice" in script
    assert "Recorded epoch:" in script


def test_extract_remote_spot_price_payload() -> None:
    payload = extract_remote_spot_price_payload(
        "noise\n"
        "__DYEC_SPOT_PRICE_LOGS_JSON_BEGIN__\n"
        '{"rows": [], "visited_files": 0}\n'
        "__DYEC_SPOT_PRICE_LOGS_JSON_END__\n"
    )

    assert payload["rows"] == []
    assert payload["visited_files"] == 0
