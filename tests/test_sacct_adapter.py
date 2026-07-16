from __future__ import annotations

import pytest

from daylily_ec.slurm.sacct import SACCT_FIELDS, SacctParseError, parse_sacct_parsable2


def _row(**overrides):
    values = {
        "JobIDRaw": "123",
        "JobID": "123",
        "User": "ubuntu",
        "Account": "root",
        "Comment": "project-a",
        "JobName": "sleep",
        "Partition": "i8",
        "State": "COMPLETED",
        "Submit": "2026-07-05T00:00:00",
        "Eligible": "2026-07-05T00:00:00",
        "Start": "2026-07-05T00:00:10",
        "End": "2026-07-05T00:01:10",
        "ElapsedRaw": "60",
        "NodeList": "ip-10-0-0-[1-2]",
        "AllocNodes": "2",
        "AllocCPUS": "8",
        "NCPUS": "8",
        "ExitCode": "0:0",
    }
    values.update(overrides)
    return "|".join(values[field] for field in SACCT_FIELDS)


def test_parse_sacct_row_with_node_expansion():
    records = parse_sacct_parsable2(
        _row(),
        node_expansions={"ip-10-0-0-[1-2]": ["ip-10-0-0-1", "ip-10-0-0-2"]},
        cluster="cluster-a",
    )

    assert len(records) == 1
    assert records[0].cost_center == "project-a"
    assert records[0].node_names == ("ip-10-0-0-1", "ip-10-0-0-2")
    assert records[0].start_at == "2026-07-05T00:00:10Z"
    assert records[0].cluster == "cluster-a"


def test_parse_allows_running_job_unknown_end_to_normalize_empty():
    records = parse_sacct_parsable2(_row(State="RUNNING", End="Unknown"))
    assert records[0].end_at == ""


def test_parse_skips_job_step_rows_without_comments():
    text = "\n".join([
        _row(JobIDRaw="123", JobID="123", Comment="project-a"),
        _row(JobIDRaw="123.batch", JobID="123.batch", User="", Comment=""),
    ])

    records = parse_sacct_parsable2(text)

    assert [record.job_id for record in records] == ["123"]
    assert records[0].cost_center == "project-a"


def test_parse_rejects_missing_comment():
    with pytest.raises(SacctParseError, match="missing required Comment"):
        parse_sacct_parsable2(_row(Comment=""))


def test_parse_rejects_malformed_row_count():
    with pytest.raises(SacctParseError, match="expected"):
        parse_sacct_parsable2("1|2|3")
