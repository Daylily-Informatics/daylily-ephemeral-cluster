from __future__ import annotations

import json
from pathlib import Path

import pytest

from daylily_ec.command_catalog_performance import (
    CommandCatalogPerformanceError,
    CommandCatalogPerformanceOptions,
    build_command_catalog_performance_profile,
)


BENCHMARK_HEADER = (
    "command_id",
    "session",
    "rule",
    "rel_path",
    "threads_req",
    "partition",
    "mem_req_mb",
    "wall_s",
    "max_rss_mb",
    "max_pss_mb",
    "mean_load",
    "cpu_time_s",
    "avg_cpu_cores",
    "cpu_eff",
    "io_in_mb",
    "io_out_mb",
    "total_io_mb",
    "io_mb_s",
    "hostname",
    "ip",
    "region_az",
    "nproc",
    "instance_type",
    "spot_cost_per_instance_hour",
    "spot_cost_per_vcpu_hour",
    "task_cost",
)

RULE_HEADER = (
    "command_id",
    "rule",
    "benchmark_rows",
    "submitted_jobs",
    "partition",
    "threads_req",
    "mem_req_mb",
    "max_rss_mb",
    "p95_rss_mb",
    "max_mem_eff",
    "median_wall_s",
    "p95_wall_s",
    "median_cpu_eff",
    "p95_cpu_eff",
    "total_io_mb",
    "max_io_mb_s",
    "median_pack_count",
    "max_pack_count",
    "median_pack_cpu_frac",
    "median_pack_mem_frac",
    "nodes",
    "instances",
    "total_task_cost",
    "median_instance_hourly_cost",
    "median_vcpu_hourly_cost",
    "recommendation",
)

SLURM_HEADER = (
    "JobIDRaw",
    "Partition",
    "State",
    "AllocCPUS",
    "NNodes",
    "NodeList",
    "JobName",
    "ElapsedRaw",
    "ReqMem",
    "MaxRSS",
    "MaxVMSize",
    "AveCPU",
    "Elapsed",
    "Submit",
    "Start",
    "End",
    "ExitCode",
    "command_id",
    "session",
    "rule",
    "benchmark",
    "threads_req",
    "partition_req",
    "mem_req_mb",
    "alloc_cpus",
    "node",
    "node_cpus",
    "node_mem_mb",
    "pack_count_max",
    "pack_cpu_frac_max",
    "pack_mem_frac_max",
)


def write_tsv(path: Path, header: tuple[str, ...], rows: list[tuple[object, ...]]) -> None:
    path.write_text(
        "\n".join(["\t".join(header), *["\t".join(map(str, row)) for row in rows]]) + "\n",
        encoding="utf-8",
    )


def test_builds_version_keyed_performance_history(tmp_path: Path) -> None:
    benchmark = tmp_path / "benchmark_rows.tsv"
    rules = tmp_path / "rule_resource_summary.tsv"
    slurm = tmp_path / "slurm_jobs_with_packing.tsv"
    history = tmp_path / "history.json"
    output_dir = tmp_path / "out"

    write_tsv(
        benchmark,
        BENCHMARK_HEADER,
        [
            (
                "illumina_snv_alignstats",
                "session-a",
                "rule_a",
                "results/rule_a.bench.tsv",
                8,
                "i192",
                32000,
                10,
                1000,
                900,
                4,
                40,
                4,
                0.5,
                15,
                85,
                100,
                10,
                "node-a",
                "10.0.0.1",
                "us-west-2a",
                192,
                "m8i.metal-48xl",
                3.0,
                0.015625,
                0.01,
            ),
        ],
    )
    write_tsv(
        rules,
        RULE_HEADER,
        [
            (
                "illumina_snv_alignstats",
                "rule_a",
                1,
                1,
                "i192",
                8,
                32000,
                1000,
                1000,
                0.03125,
                10,
                10,
                0.5,
                0.5,
                100,
                10,
                2,
                2,
                0.2,
                0.4,
                "node-a",
                "node-a:m8i.metal-48xl",
                0.01,
                3.0,
                0.015625,
                "reduce memory request materially; CPU over-requested; I/O heavy",
            ),
        ],
    )
    write_tsv(
        slurm,
        SLURM_HEADER,
        [
            (
                "101",
                "i192",
                "COMPLETED",
                8,
                1,
                "node-a",
                "rule_a",
                10,
                "32000M",
                "1000M",
                "1200M",
                "00:00:40",
                "00:00:10",
                "2026-07-07T00:00:00",
                "2026-07-07T00:00:01",
                "2026-07-07T00:00:11",
                "0:0",
                "illumina_snv_alignstats",
                "session-a",
                "rule_a",
                "results/rule_a.bench.tsv",
                8,
                "i192",
                32000,
                8,
                "node-a",
                192,
                768000,
                2,
                0.2,
                0.4,
            ),
        ],
    )

    profile = build_command_catalog_performance_profile(
        CommandCatalogPerformanceOptions(
            benchmark_rows_tsv=benchmark,
            rule_summary_tsv=rules,
            slurm_jobs_tsv=slurm,
            dyec_version="10.0.103",
            dayoa_version="10.0.65",
            cluster="cmdcat",
            run_id="20260707T144453Z",
            output_dir=output_dir,
            history_json=history,
            command_ids=("illumina_snv_alignstats", "illumina_bclconvert"),
            dev_command_ids=frozenset({"illumina_bclconvert"}),
        )
    )

    assert profile["cohort_counts"] == {"dev": 1, "prod": 1}
    assert profile["commands"]["illumina_snv_alignstats"]["status"] == "benchmarked"
    assert profile["commands"]["illumina_bclconvert"]["status"] == "no_benchmark_evidence"
    assert profile["commands"]["illumina_snv_alignstats"]["allocated_vcpu_hours"] == 0.0222
    assert profile["commands"]["illumina_snv_alignstats"]["resource_signal_counts"] == {
        "io_bound_rule_count": 1,
        "over_memory_rule_count": 1,
        "over_threaded_rule_count": 1,
        "tight_packing_rule_count": 0,
    }
    assert (output_dir / "command_catalog_performance_profile.json").is_file()
    assert (output_dir / "command_catalog_performance_summary.tsv").is_file()
    stored = json.loads(history.read_text(encoding="utf-8"))
    assert sorted(stored["dyec_versions"]) == ["10.0.103"]

    with pytest.raises(CommandCatalogPerformanceError, match="already contains"):
        build_command_catalog_performance_profile(
            CommandCatalogPerformanceOptions(
                benchmark_rows_tsv=benchmark,
                dyec_version="10.0.103",
                output_dir=tmp_path / "again",
                history_json=history,
            )
        )


def test_compares_against_latest_prior_version(tmp_path: Path) -> None:
    benchmark = tmp_path / "benchmark_rows.tsv"
    history = tmp_path / "history.json"
    write_tsv(
        benchmark,
        BENCHMARK_HEADER,
        [
            (
                "illumina_snv_alignstats",
                "session-a",
                "rule_a",
                "results/rule_a.bench.tsv",
                8,
                "i192",
                32000,
                10,
                1000,
                900,
                4,
                40,
                4,
                0.5,
                15,
                85,
                100,
                10,
                "node-a",
                "10.0.0.1",
                "us-west-2a",
                192,
                "m8i.metal-48xl",
                3.0,
                0.015625,
                0.01,
            ),
        ],
    )
    build_command_catalog_performance_profile(
        CommandCatalogPerformanceOptions(
            benchmark_rows_tsv=benchmark,
            dyec_version="10.0.102",
            output_dir=tmp_path / "prior",
            history_json=history,
            command_ids=("illumina_snv_alignstats",),
        )
    )
    profile = build_command_catalog_performance_profile(
        CommandCatalogPerformanceOptions(
            benchmark_rows_tsv=benchmark,
            dyec_version="10.0.103",
            output_dir=tmp_path / "current",
            history_json=history,
            command_ids=("illumina_snv_alignstats",),
        )
    )

    comparison = profile["commands"]["illumina_snv_alignstats"]["comparison_to_prior"]
    assert comparison["status"] == "compared"
    assert comparison["metrics"]["total_wall_s"]["ratio"] == 1.0
