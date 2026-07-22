from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from daylily_ec.headnode_observability import (
    ANALYSIS_DISCOVERY_MARKER,
    ANALYSIS_RESULTS_ROOT,
    BENCHMARK_REPORT_MARKER,
    BENCHMARK_NUMERIC_COLUMNS,
    DEFAULT_MAX_OUTPUT_BYTES,
    FSX_USAGE_MARKER,
    HeadnodeObservabilityError,
    MAX_SSM_STDOUT_BYTES,
    SYSTEM_INFO_MARKER,
    build_analysis_discovery_script,
    build_benchmark_report_script,
    build_fsx_usage_script,
    build_system_info_script,
    parse_analysis_discovery_output,
    parse_benchmark_report_output,
    parse_fsx_usage_output,
    parse_system_info_output,
    validate_analysis_root,
    validate_genome_build,
)


OBSERVED_AT = "2026-07-22T12:34:56Z"


def _marked(marker: str, payload: dict[str, object], *, prelude: str = "") -> str:
    return prelude + marker + json.dumps(payload, sort_keys=True) + "\n"


def _embedded_python(script: str) -> str:
    prefix = "python3 - <<'PY'\n"
    assert script.startswith("set -euo pipefail\n")
    assert script.endswith("\nPY\n")
    return script.split(prefix, 1)[1].rsplit("\nPY\n", 1)[0]


def test_all_generated_scripts_have_valid_embedded_python() -> None:
    scripts = [
        build_system_info_script(),
        build_fsx_usage_script(),
        build_analysis_discovery_script("direct"),
        build_analysis_discovery_script("recursive-dayoa"),
        build_benchmark_report_script(
            "/fsx/analysis_results/ubuntu/Z-RGX-TEST",
            "hg38",
        ),
    ]

    for script in scripts:
        compile(_embedded_python(script), "<dyec-headnode-observability>", "exec")


def test_system_info_script_is_fixed_bounded_and_secret_free() -> None:
    script = build_system_info_script()

    assert 'if [ "$(id -un)" != "ubuntu" ]' in script
    assert SYSTEM_INFO_MARKER in script
    assert 'open("/etc/os-release"' in script
    assert 'open("/proc/meminfo"' in script
    assert 'open("/proc/uptime"' in script
    assert "os.cpu_count()" in script
    assert 'importlib.metadata.version("daylily-ephemeral-cluster")' in script
    assert 'shutil.which("day-clone") is not None' in script
    assert '"day_clone_version": None' in script
    assert '"day_clone_default_ref": None' in script
    assert "day-clone --help" not in script
    assert "day-clone --list" not in script
    assert "subprocess" not in script
    assert "os.environ" not in script
    assert "argv" not in script
    assert "/proc/self" not in script
    assert "/proc/*" not in script
    assert f"> {MAX_SSM_STDOUT_BYTES}" in script


def test_system_info_parser_accepts_one_valid_marker() -> None:
    payload = {
        "schema_version": 1,
        "operation": "headnode_system_info",
        "observed_at": OBSERVED_AT,
        "host": {
            "hostname": "ip-10-0-0-1",
            "os_release": {
                "id": "ubuntu",
                "version_id": "24.04",
                "pretty_name": "Ubuntu 24.04.2 LTS",
            },
            "kernel_release": "6.8.0",
            "architecture": "x86_64",
            "uptime_seconds": 3600,
            "cpu_count": 16,
            "memory_total_kib": 131072000,
            "dyec_version": "13.0.8",
            "day_clone_available": True,
            "day_clone_version": None,
            "day_clone_default_ref": None,
        },
    }

    assert parse_system_info_output(_marked(SYSTEM_INFO_MARKER, payload)) == payload


@pytest.mark.parametrize(
    "stdout,match",
    [
        ("", "exactly one marker"),
        (SYSTEM_INFO_MARKER + "{}\n" + SYSTEM_INFO_MARKER + "{}\n", "exactly one marker"),
        (SYSTEM_INFO_MARKER + "not-json\n", "malformed JSON"),
    ],
)
def test_marker_parser_rejects_missing_duplicate_and_malformed_json(
    stdout: str, match: str
) -> None:
    with pytest.raises(HeadnodeObservabilityError, match=match):
        parse_system_info_output(stdout)


def test_marker_parser_enforces_output_bound() -> None:
    with pytest.raises(HeadnodeObservabilityError, match="exceeds the byte limit"):
        parse_system_info_output("x" * 101, max_output_bytes=100)

    with pytest.raises(HeadnodeObservabilityError, match="max_output_bytes"):
        parse_system_info_output("", max_output_bytes=DEFAULT_MAX_OUTPUT_BYTES + 1)


def test_system_info_parser_rejects_wrong_schema_and_invalid_host() -> None:
    payload = {
        "schema_version": 2,
        "operation": "headnode_system_info",
        "observed_at": OBSERVED_AT,
        "host": {},
    }
    with pytest.raises(HeadnodeObservabilityError, match="schema_version"):
        parse_system_info_output(_marked(SYSTEM_INFO_MARKER, payload))

    payload["schema_version"] = 1
    payload["host"] = {
        "hostname": "",
        "os_release": {
            "id": "ubuntu",
            "version_id": "24.04",
            "pretty_name": "Ubuntu 24.04.2 LTS",
        },
        "kernel_release": "6.8.0",
        "architecture": "x86_64",
        "uptime_seconds": 3600,
        "cpu_count": 16,
        "memory_total_kib": 131072000,
        "dyec_version": "13.0.8",
        "day_clone_available": True,
        "day_clone_version": None,
        "day_clone_default_ref": None,
    }
    with pytest.raises(HeadnodeObservabilityError, match="host.hostname"):
        parse_system_info_output(_marked(SYSTEM_INFO_MARKER, payload))


def test_system_info_parser_rejects_missing_static_fields_and_unsafe_tool_metadata() -> None:
    payload = {
        "schema_version": 1,
        "operation": "headnode_system_info",
        "observed_at": OBSERVED_AT,
        "host": {
            "hostname": "ip-10-0-0-1",
            "os_release": {
                "id": "ubuntu",
                "version_id": "24.04",
                "pretty_name": "Ubuntu 24.04.2 LTS",
            },
            "kernel_release": "6.8.0",
            "architecture": "x86_64",
            "uptime_seconds": 3600,
            "cpu_count": 16,
            "memory_total_kib": 131072000,
            "dyec_version": "13.0.8",
            "day_clone_available": True,
            "day_clone_version": None,
            "day_clone_default_ref": None,
        },
    }
    del payload["host"]["os_release"]
    with pytest.raises(HeadnodeObservabilityError, match="host fields"):
        parse_system_info_output(_marked(SYSTEM_INFO_MARKER, payload))

    payload["host"]["os_release"] = {
        "id": "ubuntu",
        "version_id": "24.04",
        "pretty_name": "Ubuntu 24.04.2 LTS",
    }
    payload["host"]["day_clone_default_ref"] = "bad\nref"
    with pytest.raises(HeadnodeObservabilityError, match="day_clone_default_ref"):
        parse_system_info_output(_marked(SYSTEM_INFO_MARKER, payload))

    payload["host"]["day_clone_default_ref"] = None
    payload["host"]["os_release"]["id"] = "amzn"
    with pytest.raises(HeadnodeObservabilityError, match="not Ubuntu"):
        parse_system_info_output(_marked(SYSTEM_INFO_MARKER, payload))

    payload["host"]["os_release"]["id"] = "ubuntu"
    payload["host"]["day_clone_available"] = False
    payload["host"]["day_clone_version"] = "13.0.18"
    with pytest.raises(HeadnodeObservabilityError, match="unavailable day-clone"):
        parse_system_info_output(_marked(SYSTEM_INFO_MARKER, payload))


def test_fsx_usage_script_is_fixed_to_df_pk_fsx() -> None:
    script = build_fsx_usage_script()

    assert 'if [ "$(id -un)" != "ubuntu" ]' in script
    assert '["df", "-Pk",' in script
    assert "'/fsx']," in script
    assert FSX_USAGE_MARKER in script
    assert "unexpected mountpoint" in script
    assert "shell=True" not in script
    assert "os.environ" not in script


def test_fsx_usage_parser_preserves_df_pk_semantics() -> None:
    payload = {
        "schema_version": 1,
        "operation": "headnode_fsx_usage",
        "observed_at": OBSERVED_AT,
        "filesystem": {
            "path": "/fsx",
            "filesystem": "10.0.0.1@tcp:/fsx",
            "size_kib": 1_000_000,
            "used_kib": 250_000,
            "available_kib": 750_000,
            "use_percent": 25,
            "mountpoint": "/fsx",
        },
    }

    assert parse_fsx_usage_output(_marked(FSX_USAGE_MARKER, payload)) == payload


def test_fsx_usage_parser_rejects_wrong_scope_and_percent() -> None:
    payload = {
        "schema_version": 1,
        "operation": "headnode_fsx_usage",
        "observed_at": OBSERVED_AT,
        "filesystem": {
            "path": "/tmp",
            "filesystem": "/dev/xvda1",
            "size_kib": 10,
            "used_kib": 5,
            "available_kib": 5,
            "use_percent": 50,
            "mountpoint": "/tmp",
        },
    }
    with pytest.raises(HeadnodeObservabilityError, match="does not describe /fsx"):
        parse_fsx_usage_output(_marked(FSX_USAGE_MARKER, payload))

    payload["filesystem"]["path"] = "/fsx"
    payload["filesystem"]["mountpoint"] = "/fsx"
    payload["filesystem"]["use_percent"] = 101
    with pytest.raises(HeadnodeObservabilityError, match="exceeds 100"):
        parse_fsx_usage_output(_marked(FSX_USAGE_MARKER, payload))


@pytest.mark.parametrize("mode", ["direct", "recursive-dayoa"])
def test_analysis_discovery_script_has_fixed_root_mode_and_limits(mode: str) -> None:
    script = build_analysis_discovery_script(
        mode,
        max_results=12,
        max_depth=6,
        max_scanned_entries=500,
    )

    assert 'if [ "$(id -un)" != "ubuntu" ]' in script
    assert f"root = Path('{ANALYSIS_RESULTS_ROOT}')" in script
    assert f"mode = '{mode}'" in script
    assert "max_results = 12" in script
    assert "max_depth = 6" in script
    assert "max_scanned_entries = 500" in script
    assert "root.is_symlink()" in script
    assert "entry.is_dir(follow_symlinks=False)" in script
    assert "found[:max_results]" in script
    assert ANALYSIS_DISCOVERY_MARKER in script


@pytest.mark.parametrize("mode", ["recursive", "", "DIRECT", "direct; id"])
def test_analysis_discovery_rejects_unknown_modes(mode: str) -> None:
    with pytest.raises(HeadnodeObservabilityError, match="mode must be one of"):
        build_analysis_discovery_script(mode)


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"max_results": 0}, "max_results"),
        ({"max_results": 1001}, "max_results"),
        ({"max_results": True}, "integer"),
        ({"max_depth": 0}, "max_depth"),
        ({"max_depth": 17}, "max_depth"),
        ({"max_scanned_entries": 0}, "max_scanned_entries"),
        ({"max_scanned_entries": 100001}, "max_scanned_entries"),
    ],
)
def test_analysis_discovery_rejects_invalid_limits(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(HeadnodeObservabilityError, match=match):
        build_analysis_discovery_script("direct", **kwargs)


def test_analysis_discovery_parser_accepts_bounded_results() -> None:
    payload = {
        "schema_version": 1,
        "operation": "analysis_discovery",
        "observed_at": OBSERVED_AT,
        "root": ANALYSIS_RESULTS_ROOT,
        "mode": "recursive-dayoa",
        "max_results": 2,
        "max_depth": 8,
        "max_scanned_entries": 100,
        "scanned_entries": 12,
        "truncated": False,
        "analyses": [
            {
                "analysis_root": "/fsx/analysis_results/ubuntu/run-1",
                "dayoa_root": ("/fsx/analysis_results/ubuntu/run-1/daylily-omics-analysis"),
                "relative_path": "ubuntu/run-1",
            }
        ],
    }

    assert parse_analysis_discovery_output(_marked(ANALYSIS_DISCOVERY_MARKER, payload)) == payload


def test_analysis_discovery_parser_rejects_over_limit_and_unsafe_paths() -> None:
    item = {
        "analysis_root": "/fsx/analysis_results/ubuntu/run-1",
        "dayoa_root": "/fsx/analysis_results/ubuntu/run-1/daylily-omics-analysis",
        "relative_path": "ubuntu/run-1",
    }
    payload = {
        "schema_version": 1,
        "operation": "analysis_discovery",
        "observed_at": OBSERVED_AT,
        "root": ANALYSIS_RESULTS_ROOT,
        "mode": "direct",
        "max_results": 1,
        "max_depth": 8,
        "max_scanned_entries": 100,
        "scanned_entries": 12,
        "truncated": True,
        "analyses": [item, item],
    }
    with pytest.raises(HeadnodeObservabilityError, match="violates its limit"):
        parse_analysis_discovery_output(_marked(ANALYSIS_DISCOVERY_MARKER, payload))

    payload["analyses"] = [
        {
            **item,
            "analysis_root": "/fsx/analysis_results/ubuntu/run;id",
            "dayoa_root": "/fsx/analysis_results/ubuntu/run;id/daylily-omics-analysis",
        }
    ]
    with pytest.raises(HeadnodeObservabilityError, match="unsafe"):
        parse_analysis_discovery_output(_marked(ANALYSIS_DISCOVERY_MARKER, payload))


def test_recursive_discovery_accepts_nested_dayoa_but_direct_mode_rejects_it() -> None:
    payload = {
        "schema_version": 1,
        "operation": "analysis_discovery",
        "observed_at": OBSERVED_AT,
        "root": ANALYSIS_RESULTS_ROOT,
        "mode": "recursive-dayoa",
        "max_results": 2,
        "max_depth": 8,
        "max_scanned_entries": 100,
        "scanned_entries": 12,
        "truncated": False,
        "analyses": [
            {
                "analysis_root": "/fsx/analysis_results/team/project/run-1",
                "dayoa_root": ("/fsx/analysis_results/team/project/run-1/daylily-omics-analysis"),
                "relative_path": "team/project/run-1",
            }
        ],
    }

    assert parse_analysis_discovery_output(_marked(ANALYSIS_DISCOVERY_MARKER, payload)) == payload
    payload["mode"] = "direct"
    with pytest.raises(HeadnodeObservabilityError, match="not owner/analysis"):
        parse_analysis_discovery_output(_marked(ANALYSIS_DISCOVERY_MARKER, payload))


@pytest.mark.parametrize(
    "path",
    [
        "relative/run",
        "/fsx/analysis_results/ubuntu",
        "/fsx/analysis_results/ubuntu/run/daylily-omics-analysis",
        "/fsx/analysis_results/ubuntu/../run",
        "/fsx/analysis_results/ubuntu/run id",
        "/fsx/analysis_results/ubuntu/run;id",
        "/tmp/ubuntu/run",
    ],
)
def test_analysis_root_validation_rejects_non_exact_or_unsafe_paths(path: str) -> None:
    with pytest.raises(HeadnodeObservabilityError):
        validate_analysis_root(path)


def test_analysis_root_and_genome_build_validation_accept_exact_values() -> None:
    assert (
        validate_analysis_root("/fsx/analysis_results/ubuntu/Z-RGX-TEST")
        == "/fsx/analysis_results/ubuntu/Z-RGX-TEST"
    )
    assert validate_genome_build("hg38_broad") == "hg38_broad"


def test_benchmark_report_script_is_exact_bounded_and_read_only() -> None:
    script = build_benchmark_report_script(
        "/fsx/analysis_results/ubuntu/Z-RGX-TEST",
        "hg38_broad",
        max_bytes=2048,
        max_rows=50,
        max_groups=8,
    )

    assert 'if [ "$(id -un)" != "ubuntu" ]' in script
    assert (
        "summary_path = Path('/fsx/analysis_results/ubuntu/Z-RGX-TEST/"
        "daylily-omics-analysis/results/day/hg38_broad/reports/benchmarks_summary.tsv')" in script
    )
    assert "max_bytes = 2048" in script
    assert "max_rows = 50" in script
    assert "max_groups = 8" in script
    assert "csv.DictReader" in script
    assert "required_columns = {'rule', *('s', 'task_cost')}" in script
    assert "numeric_columns = list(('s', 'task_cost'))" in script
    assert '"groups": groups' in script
    assert '"rows"' not in script
    assert '"sample"' not in script
    assert "runtime_seconds" not in script
    assert "glob(" not in script
    assert ".rglob(" not in script
    assert "is_symlink()" in script
    assert "unique-rule group limit" in script
    assert "math.isfinite(value)" in script
    assert "oversized field" in script
    assert BENCHMARK_REPORT_MARKER in script
    assert f"> {MAX_SSM_STDOUT_BYTES}" in script
    assert "write" not in script
    assert "unlink" not in script


def _run_generated_benchmark_report(
    tmp_path: Path,
    rows: list[dict[str, str]],
    *,
    max_groups: int = 8,
) -> subprocess.CompletedProcess[str]:
    fsx_root = tmp_path / "fsx"
    analysis_results = fsx_root / "analysis_results"
    analysis_root = analysis_results / "ubuntu" / "Z-RGX-TEST"
    summary = (
        analysis_root
        / "daylily-omics-analysis"
        / "results"
        / "day"
        / "hg38"
        / "reports"
        / "benchmarks_summary.tsv"
    )
    summary.parent.mkdir(parents=True)
    with summary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["sample", "rule", "s", "task_cost"],
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    embedded = _embedded_python(
        build_benchmark_report_script(
            "/fsx/analysis_results/ubuntu/Z-RGX-TEST",
            "hg38",
            max_groups=max_groups,
        )
    )
    embedded = embedded.replace("/fsx", str(fsx_root))
    return subprocess.run(
        [sys.executable, "-c", embedded],
        text=True,
        capture_output=True,
        check=False,
    )


def test_generated_benchmark_report_aggregates_exact_columns_deterministically(
    tmp_path: Path,
) -> None:
    result = _run_generated_benchmark_report(
        tmp_path,
        [
            {"sample": "B", "rule": "align", "s": "20", "task_cost": "0.2"},
            {"sample": "A", "rule": "call", "s": "5", "task_cost": "0.05"},
            {"sample": "A", "rule": "align", "s": "10", "task_cost": "0.1"},
        ],
    )

    assert result.returncode == 0, result.stderr
    assert len(result.stdout.encode("utf-8")) <= MAX_SSM_STDOUT_BYTES
    assert result.stdout.startswith(BENCHMARK_REPORT_MARKER)
    payload = json.loads(result.stdout.removeprefix(BENCHMARK_REPORT_MARKER))
    assert payload["source"]["row_count"] == 3
    assert payload["source"]["columns"] == ["sample", "rule", "s", "task_cost"]
    assert payload["numeric_columns"] == ["s", "task_cost"]
    assert [group["rule"] for group in payload["groups"]] == ["align", "call"]
    assert payload["groups"][0]["metrics"]["s"] == {
        "value_count": 2,
        "total": 30.0,
        "mean": 15.0,
        "median": 15.0,
    }
    assert "rows" not in payload


def test_generated_benchmark_report_fails_on_bad_numeric_and_group_overflow(
    tmp_path: Path,
) -> None:
    malformed = _run_generated_benchmark_report(
        tmp_path / "malformed",
        [{"sample": "A", "rule": "align", "s": "bad", "task_cost": "0.1"}],
    )
    assert malformed.returncode != 0
    assert malformed.stdout == ""
    assert "nonnumeric s value" in malformed.stderr

    overflow = _run_generated_benchmark_report(
        tmp_path / "overflow",
        [
            {"sample": "A", "rule": "align", "s": "1", "task_cost": "0.1"},
            {"sample": "A", "rule": "call", "s": "1", "task_cost": "0.1"},
        ],
        max_groups=1,
    )
    assert overflow.returncode != 0
    assert overflow.stdout == ""
    assert "unique-rule group limit" in overflow.stderr


@pytest.mark.parametrize("build", ["", "HG38", "hg19", "hg38; id"])
def test_benchmark_report_rejects_unknown_genome_build(build: str) -> None:
    with pytest.raises(HeadnodeObservabilityError, match="genome_build"):
        build_benchmark_report_script(
            "/fsx/analysis_results/ubuntu/Z-RGX-TEST",
            build,
        )


@pytest.mark.parametrize(
    "kwargs,match",
    [
        ({"max_bytes": 0}, "max_bytes"),
        ({"max_rows": 0}, "max_rows"),
        ({"max_rows": 100001}, "max_rows"),
        ({"max_groups": 0}, "max_groups"),
        ({"max_groups": 33}, "max_groups"),
    ],
)
def test_benchmark_report_rejects_invalid_limits(kwargs: dict[str, int], match: str) -> None:
    with pytest.raises(HeadnodeObservabilityError, match=match):
        build_benchmark_report_script(
            "/fsx/analysis_results/ubuntu/Z-RGX-TEST",
            "hg38",
            **kwargs,
        )


def _benchmark_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "operation": "benchmark_report",
        "observed_at": OBSERVED_AT,
        "analysis_root": "/fsx/analysis_results/ubuntu/Z-RGX-TEST",
        "genome_build": "hg38_broad",
        "summary_tsv": (
            "/fsx/analysis_results/ubuntu/Z-RGX-TEST/daylily-omics-analysis/"
            "results/day/hg38_broad/reports/benchmarks_summary.tsv"
        ),
        "source": {
            "bytes": 240,
            "columns": ["sample", "rule", "s", "task_cost"],
            "row_count": 3,
        },
        "group_by": "rule",
        "numeric_columns": list(BENCHMARK_NUMERIC_COLUMNS),
        "group_count": 2,
        "max_rows": 10,
        "max_bytes": 2048,
        "max_groups": 8,
        "truncated": False,
        "groups": [
            {
                "rule": "align",
                "row_count": 2,
                "metrics": {
                    "s": {"value_count": 2, "total": 30.0, "mean": 15.0, "median": 15.0},
                    "task_cost": {
                        "value_count": 2,
                        "total": 0.3,
                        "mean": 0.15,
                        "median": 0.15,
                    },
                },
            },
            {
                "rule": "call",
                "row_count": 1,
                "metrics": {
                    "s": {"value_count": 1, "total": 20.0, "mean": 20.0, "median": 20.0},
                    "task_cost": {
                        "value_count": 1,
                        "total": 0.2,
                        "mean": 0.2,
                        "median": 0.2,
                    },
                },
            },
        ],
    }


def test_benchmark_report_parser_accepts_exact_aggregates_without_rows() -> None:
    payload = _benchmark_payload()
    parsed = parse_benchmark_report_output(_marked(BENCHMARK_REPORT_MARKER, payload))
    assert parsed == payload
    assert "rows" not in parsed


def test_benchmark_report_parser_rejects_bad_path_and_raw_rows() -> None:
    payload = _benchmark_payload()
    payload["summary_tsv"] = "/tmp/benchmarks_summary.tsv"
    with pytest.raises(HeadnodeObservabilityError, match="summary path"):
        parse_benchmark_report_output(_marked(BENCHMARK_REPORT_MARKER, payload))

    payload = _benchmark_payload()
    payload["rows"] = [{"rule": "align", "s": "10", "task_cost": "0.1"}]
    with pytest.raises(HeadnodeObservabilityError, match="fields are invalid"):
        parse_benchmark_report_output(_marked(BENCHMARK_REPORT_MARKER, payload))


@pytest.mark.parametrize(
    "columns",
    [
        ["sample", "task", "s", "task_cost"],
        ["sample", "rule", "runtime_seconds", "task_cost"],
        ["sample", "rule", "s"],
    ],
)
def test_benchmark_report_parser_rejects_missing_exact_columns(columns: list[str]) -> None:
    payload = _benchmark_payload()
    payload["source"]["columns"] = columns
    with pytest.raises(HeadnodeObservabilityError, match="required columns"):
        parse_benchmark_report_output(_marked(BENCHMARK_REPORT_MARKER, payload))


def test_benchmark_report_parser_rejects_bad_group_counts_order_and_numeric_shape() -> None:
    payload = _benchmark_payload()
    payload["groups"] = list(reversed(payload["groups"]))
    with pytest.raises(HeadnodeObservabilityError, match="unique and sorted"):
        parse_benchmark_report_output(_marked(BENCHMARK_REPORT_MARKER, payload))

    payload = _benchmark_payload()
    payload["groups"][0]["metrics"]["s"]["value_count"] = 1
    with pytest.raises(HeadnodeObservabilityError, match="metric count"):
        parse_benchmark_report_output(_marked(BENCHMARK_REPORT_MARKER, payload))

    payload = _benchmark_payload()
    payload["groups"][0]["metrics"]["task_cost"]["mean"] = float("inf")
    with pytest.raises(HeadnodeObservabilityError, match="task_cost.mean"):
        parse_benchmark_report_output(_marked(BENCHMARK_REPORT_MARKER, payload))

    payload = _benchmark_payload()
    payload["source"]["row_count"] = 4
    with pytest.raises(HeadnodeObservabilityError, match="grouped rows"):
        parse_benchmark_report_output(_marked(BENCHMARK_REPORT_MARKER, payload))


def test_benchmark_report_parser_rejects_truncation_and_alias_numeric_columns() -> None:
    payload = _benchmark_payload()
    payload["truncated"] = True
    with pytest.raises(HeadnodeObservabilityError, match="truncated state"):
        parse_benchmark_report_output(_marked(BENCHMARK_REPORT_MARKER, payload))

    payload = _benchmark_payload()
    payload["numeric_columns"] = ["runtime_seconds", "task_cost"]
    with pytest.raises(HeadnodeObservabilityError, match="numeric columns"):
        parse_benchmark_report_output(_marked(BENCHMARK_REPORT_MARKER, payload))


def test_every_script_enforces_complete_ssm_stdout_limit() -> None:
    scripts = [
        build_system_info_script(),
        build_fsx_usage_script(),
        build_analysis_discovery_script("direct"),
        build_analysis_discovery_script("recursive-dayoa"),
        build_benchmark_report_script(
            "/fsx/analysis_results/ubuntu/Z-RGX-TEST",
            "hg38",
        ),
    ]
    for script in scripts:
        assert f'if len(output.encode("utf-8")) > {MAX_SSM_STDOUT_BYTES}:' in script
        assert 'print(output, end="")' in script


def test_default_output_limit_constant_is_explicit() -> None:
    assert MAX_SSM_STDOUT_BYTES == 20 * 1024
    assert DEFAULT_MAX_OUTPUT_BYTES == MAX_SSM_STDOUT_BYTES
