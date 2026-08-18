from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import daylily_ec.cli as cli_module
import daylily_ec.command_sample_stats as module
from daylily_ec.cli import app

runner = CliRunner()


def _write(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _status(root: Path) -> dict:
    master = _write(
        root / "daylily-omics-analysis" / ".snakemake" / "log" / "run.snakemake.log",
        "3 of 9 steps (33%) done\nTrying to restart job 7\n",
    )
    stdout = _write(root / "daylily-omics-analysis" / "logs" / "HG003_unit.out", "ETA 00:10:00\n")
    stderr = _write(root / "daylily-omics-analysis" / "logs" / "HG003_unit.err", "")
    return {
        "state": "RUNNING",
        "workflow": {
            "master_log": str(master),
            "progress": {"completed": 3, "total": 9, "percent": 33},
            "scheduled_rules": ["hiomrs_longreadsv"],
            "failure_count": 0,
            "failure_lines": [],
        },
        "controller": {
            "return_code": None,
            "processes": [{"elapsed_seconds": 600}],
            "tmux_panes": [
                {
                    "session": "hiomrs-test",
                    "observed_commands": [
                        "dy-a slurm hg38",
                        "dy-r produce_sentdhiomr_snv_vcf produce_sentdhiomr_sv produce_sentdhiomr_cnv",
                    ],
                }
            ],
        },
        "slurm": {
            "available": True,
            "jobs": [
                {
                    "job_id": "123",
                    "name": "rule_HG003_unit",
                    "state": "RUNNING",
                    "reason": "None",
                    "elapsed": "00:04:00",
                    "restart_count": 0,
                    "comment": "project-a",
                    "stdout": str(stdout),
                    "stderr": str(stderr),
                    "stdout_tail": {
                        "path": str(stdout),
                        "progress_markers": ["ETA 00:10:00"],
                    },
                    "stderr_tail": {"path": str(stderr), "progress_markers": []},
                }
            ],
        },
        "accounting": {"available": True, "jobs": []},
        "canonical_artifacts": {"all_present": False, "files": {}},
        "terminal_evidence": {
            "return_code": None,
            "requirements": {
                "controller_exit_zero": False,
                "controller_inactive": False,
                "scheduler_idle": False,
                "workflow_progress_complete": False,
                "strict_artifacts_present": False,
            },
            "success_verified": False,
        },
        "job_counts": {
            "submitted": {"value": 4, "available": True, "source": str(master)},
            "completed": {"value": 3, "available": True, "source": str(master)},
            "failed": {"value": 0, "available": True, "source": "sacct"},
            "running": {"value": 1, "available": True, "source": "squeue"},
            "pending": {"value": 0, "available": True, "source": "squeue"},
            "still_to_run": {"value": 6, "available": True, "source": str(master)},
            "dependency_blocked": {"value": 0, "available": True, "source": "squeue"},
        },
        "benchmarks": {"completed_cost_usd_sum": 1.25},
        "recent_rule_logs": {"recent": []},
    }


@pytest.fixture
def analysis_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "analysis"
    dayoa = root / "daylily-omics-analysis"
    _write(
        dayoa / "config" / "specimens.tsv",
        "SPECIMEN_ID\tSPECIMEN_EUID\tBIOLOGICAL_SEX\tSPECIMEN_TYPE\n"
        "HG003_specimen\tfixture-specimen-owned-003\tXY\tblood\n",
    )
    _write(
        dayoa / "config" / "samples.tsv",
        "SAMPLEID\tSAMPLE_EUID\tSPECIMEN_ID\tSAMPLEUSE\tORDER_TYPE\n"
        "HG003\tfixture-sample-owned-003\tHG003_specimen\tvalidation\tpositive_control\n",
    )
    _write(
        dayoa / "config" / "libraries.tsv",
        "LIBRARY_ID\tLIBRARY_EUID\tSAMPLEID\n"
        "HG003_sr_library\tfixture-library-owned-003\tHG003\n"
        "HG003_lr_library\tfixture-library-owned-004\tHG003\n",
    )
    _write(
        dayoa / "config" / "sequencing_inputs.tsv",
        "SEQUENCING_INPUT_UID\tLIBRARY_ID\tMODALITY\tLAYOUT\tILMN_R1_PATH\tILMN_R2_PATH\tONT_R1_PATH\n"
        "HG003_sr_input\tHG003_sr_library\tsr\tpaired_fastq\t/data/sr_R1.fastq.gz\t/data/sr_R2.fastq.gz\t\n"
        "HG003_lr_input\tHG003_lr_library\tlr\tsingle_fastq\t\t\t/data/lr.fastq.gz\n",
    )
    _write(
        dayoa / "config" / "analysis_units.tsv",
        "ANALYSIS_UNIT_UID\tSAMPLEID\tANALYSIS_UNIT_EUID\tDELIVERY_EUID\n"
        "HG003_unit\tHG003\tZ-AU-HG003\tZ-DELIVERY-HG003\n",
    )
    _write(
        dayoa / "config" / "analysis_unit_inputs.tsv",
        "ANALYSIS_UNIT_UID\tSEQUENCING_INPUT_UID\tROLE\tINPUT_ORDINAL\n"
        "HG003_unit\tHG003_sr_input\tsr\t1\n"
        "HG003_unit\tHG003_lr_input\tlr\t2\n",
    )
    _write(
        dayoa / "config" / "day_profiles" / "slurm" / "templates" / "rule_config.yaml",
        "hiomrs:\n  segdup_genes: CFH,CYP2D6\n",
    )
    build = dayoa / "results" / "day" / "hg38"
    unit = "HG003_unit"
    sr = build / unit / "align" / "hiomrs_sr" / "na"
    lr = build / unit / "align" / "hiomrs_lr" / "na"
    _write(sr / f"{unit}.hiomrs_sr.na.cram")
    _write(lr / f"{unit}.hiomrs_lr.na.cram")
    _write(sr / "snv" / "hiomrs" / f"{unit}.hiomrs_sr.na.hiomrs.g.vcf.gz")
    _write(sr / "sv" / "hiomrs" / f"{unit}.hiomrs_sr.na.hiomrs.sv.vcf.gz")
    _write(sr / "cnv" / "hiomrs" / f"{unit}.hiomrs_sr.na.hiomrs.cnv.vcf.gz")
    _write(sr / "hiomrs" / "mito" / f"{unit}.mito.vcf.gz")
    _write(sr / "hiomrs" / "segdup" / f"{unit}.CFH.result.vcf.gz")
    _write(sr / "hiomrs" / "segdup" / f"{unit}.CYP2D6.result.vcf.gz")
    _write(sr / "hiomrs" / "segdup" / f"{unit}.segdup.done")
    _write(sr / "hiomrs" / "expansionhunter" / f"{unit}.eh.vcf")
    header = "AlignedReadLengthMedian\tInsertSizeMedian\tWgsCoverageMean\tWgsCoverageMedian\n"
    _write(
        sr / "alignqc" / "alignstats" / f"{unit}.hiomrs_sr.na.alignstats.tsv",
        header + "151\t410\t31.5\t30.2\n",
    )
    _write(
        lr / "alignqc" / "alignstats" / f"{unit}.hiomrs_lr.na.alignstats.tsv",
        header + "15500\t0\t22.4\t21.8\n",
    )
    _write(
        sr / "alignqc" / "contam" / "site_mix" / f"{unit}.hiomrs_sr.na.site_mix.tsv",
        "contamination\n0.42\n",
    )
    _write(
        build
        / unit
        / "align"
        / "hiomrs_input_lr"
        / "na"
        / "alignqc"
        / "sex_complement"
        / f"{unit}.hiomrs_input_lr.na.sex_complement.json",
        json.dumps({"observed_sex": "XY"}),
    )
    _write(
        sr / "sv" / "hiomrs" / f"{unit}.hiomrs_sr.na.hiomrs.sv.provenance.json",
        json.dumps(
            {
                "schema_version": 1,
                "selected_callset": "sentieon_longreadsv",
                "workflow_rule": "hiomrs_longreadsv",
                "longreadsv": {"status": "complete", "return_code": 0},
                "short_read_fallback": {"status": "not_run", "return_code": None},
            }
        ),
    )
    _write(
        build / unit / f"{unit}_metadata.json",
        json.dumps(
            {
                "final_qc_disposition": "pass",
                "final_data_package_ready": True,
                "final_data_package_delivered": False,
                "relatives": ["Mother:unit-m:confirm"],
            }
        ),
    )
    _write(
        build / "other_reports" / "giab_concordance_mqc.tsv",
        "Sample\tVariantClass\tSNVCaller\tROI\tFscore\nHG003_unit\tSNV\thiomrs\tgiabHC\t0.998\n",
    )
    _write(dayoa / "dags" / "rulegraph.png", "png-data")
    _write(
        build / "reports" / "benchmarks_summary.tsv",
        "sample\trule\ts\ttask_cost\nHG003_unit\thiomrs_core\t120\t0.25\n",
    )
    status = _status(root)
    monkeypatch.setattr(module, "collect_analysis_status", lambda *_args, **_kwargs: status)
    monkeypatch.setattr(
        module,
        "_git_identity",
        lambda *_args, **_kwargs: {
            "commit": "abc",
            "exact_tag": "11.0.15",
            "dirty": False,
            "dirty_paths": [],
        },
    )
    return root


def test_collect_sample_stats_contract(analysis_root: Path) -> None:
    payload = module.collect_command_sample_stats(
        analysis_root,
        name="bjuice10",
        pipeline="hiomr-kitchensink",
    )

    assert list(payload) == ["bjuice10"]
    report = payload["bjuice10"]
    assert report["schema_version"] == "dyec.command_sample_stats.v2"
    assert report["compatible_schema_versions"] == ["dyec.command_sample_stats.v1"]
    assert report["command_details"]["command_catalog_key"] == "hybrid_ilmn_ont_hiomr_kitchensink"
    assert report["command_details"]["git_tag"] == "15.0.24"
    assert report["command_details"]["retried_jobs"]["count"] == 1
    assert report["analysis"]["started_at_source"] == "controller process elapsed time"
    assert 599 <= report["analysis"]["runtime_seconds"] <= 601
    assert report["pipeline"]["input_contract"] == "six_manifest"
    assert report["pipeline"]["manifest_files"] == [
        "specimens.tsv",
        "samples.tsv",
        "libraries.tsv",
        "sequencing_inputs.tsv",
        "analysis_units.tsv",
        "analysis_unit_inputs.tsv",
    ]
    assert report["pipeline"]["specimens_rows"] == 1
    assert report["pipeline"]["samples_rows"] == 1
    assert report["pipeline"]["units_rows"] == 1
    assert report["pipeline"]["libraries_rows"] == 2
    assert report["pipeline"]["jobs_submitted"] == 4
    assert report["pipeline"]["jobs_still_to_run"] == 6
    assert report["pipeline"]["jobs_retried"] == 1
    assert report["pipeline"]["ont_aligned_read_length_median_summary"] == {
        "minimum": 15500.0,
        "median": 15500.0,
        "maximum": 15500.0,
    }
    assert report["pipeline"]["ilmn_insert_size_median_summary"] == {
        "minimum": 410.0,
        "median": 410.0,
        "maximum": 410.0,
    }
    unit = report["library_units"][0]
    assert unit["analysis_unit_uid"] == "HG003_unit"
    assert unit["library_euid"] is None
    assert unit["library_euids"] == [
        "fixture-library-owned-003",
        "fixture-library-owned-004",
    ]
    assert unit["sample_euid"] == "fixture-sample-owned-003"
    assert unit["specimen_id"] == "HG003_specimen"
    assert unit["specimen_euid"] == "fixture-specimen-owned-003"
    assert unit["overall_percent_complete"] == 100.0
    assert unit["milestones"]["mitochondrial"]["state"] == "complete"
    assert unit["milestones"]["segdup"]["completed_targets"] == 2
    assert unit["metrics"]["required_gender"]["value"] == "XY"
    assert unit["metrics"]["observed_gender"]["value"] == "XY"
    assert unit["metrics"]["observed_gender_evidence"][0]["value"] == "XY"
    assert unit["metrics"]["final_qc_disposition"]["value"] == "pass"
    assert unit["giab_hc_snv_fscore"]["value"] == 0.998
    assert unit["benchmark_task_cost"]["value_usd"] == 0.25
    assert unit["runtime"]["full_wall"]["state"] == "available"
    assert unit["runtime"]["dag_critical_path_no_wait"]["seconds"] is None
    assert unit["hybrid_sv_provenance"]["selected_callset"] == "sentieon_longreadsv"
    assert report["dag"]["available"] is True


def test_v2_preserves_the_public_v1_field_surface(analysis_root: Path) -> None:
    report = module.collect_command_sample_stats(
        analysis_root,
        name="compatibility",
        pipeline="hiomr-kitchensink",
    )["compatibility"]

    assert {
        "schema_version",
        "name",
        "cluster",
        "analysis",
        "command_details",
        "costs",
        "pipeline",
        "library_units",
        "dag",
        "status_evidence",
    } <= report.keys()
    assert {
        "analysis_root",
        "dayoa_root",
        "started_at",
        "started_at_source",
        "runtime_seconds",
        "runtime",
        "generated_at",
        "tmux_sessions",
    } <= report["analysis"].keys()
    assert {
        "name",
        "samples_rows",
        "units_rows",
        "jobs_total",
        "jobs_complete",
        "jobs_failed",
        "jobs_failed_events",
        "jobs_running",
        "jobs_to_run",
        "percent_complete",
        "ont_aligned_read_length_median_summary",
        "ilmn_insert_size_median_summary",
        "final_multiqc",
    } <= report["pipeline"].keys()
    unit = report["library_units"][0]
    assert {
        "analysis_unit_uid",
        "sample_id",
        "overall_percent_complete",
        "milestones",
        "metrics",
        "giab_hc_snv_fscore",
    } <= unit.keys()
    assert {"state", "display", "path"} <= unit["milestones"]["hybrid_sv"].keys()
    assert {
        "required_gender",
        "observed_gender",
        "contamination_percent",
        "ilmn_mean_coverage",
        "ilmn_median_coverage",
        "ont_mean_coverage",
        "ont_median_coverage",
        "specimen_type",
        "sample_use",
        "order_type",
        "final_qc_disposition",
        "final_data_package_ready",
        "final_data_package_delivered",
        "relatives",
    } <= unit["metrics"].keys()


def test_authoritative_analysis_unit_uid_is_unique_when_supplied(analysis_root: Path) -> None:
    units = analysis_root / "daylily-omics-analysis" / "config" / "analysis_units.tsv"
    units.write_text(
        "ANALYSIS_UNIT_UID\tSAMPLEID\n" "HG003_unit\tHG003\n" "HG003_unit\tHG003\n",
        encoding="utf-8",
    )
    with pytest.raises(module.CommandSampleStatsError, match="duplicate key"):
        module.collect_command_sample_stats(analysis_root, name="x", pipeline="hiomr-kitchensink")


def test_dayoa13_sample_stats_rejects_blank_analysis_unit_without_rewriting(
    analysis_root: Path,
) -> None:
    units = analysis_root / "daylily-omics-analysis" / "config" / "analysis_units.tsv"
    units.write_text(
        "ANALYSIS_UNIT_UID\tSAMPLEID\n\tHG003\n",
        encoding="utf-8",
    )
    with pytest.raises(module.CommandSampleStatsError, match="blank or whitespace"):
        module.collect_command_sample_stats(analysis_root, name="x", pipeline="hiomr-kitchensink")


def test_dayoa13_sample_stats_rejects_legacy_units_even_with_six_manifests(
    analysis_root: Path,
) -> None:
    _write(
        analysis_root / "daylily-omics-analysis" / "config" / "units.tsv",
        "ANALYSIS_UNIT_UID\tSAMPLEID\nHG003_unit\tHG003\n",
    )
    with pytest.raises(
        module.CommandSampleStatsError, match="legacy manifest files are prohibited"
    ):
        module.collect_command_sample_stats(analysis_root, name="x", pipeline="hiomr-kitchensink")


def test_dayoa13_sample_stats_validates_specimen_foreign_key(analysis_root: Path) -> None:
    samples = analysis_root / "daylily-omics-analysis" / "config" / "samples.tsv"
    samples.write_text(
        "SAMPLEID\tSAMPLE_EUID\tSPECIMEN_ID\tSAMPLEUSE\tORDER_TYPE\n"
        "HG003\tfixture-sample-owned-003\tmissing-specimen\tvalidation\tpositive_control\n",
        encoding="utf-8",
    )
    with pytest.raises(module.CommandSampleStatsError, match="orphan SPECIMEN_ID"):
        module.collect_command_sample_stats(analysis_root, name="x", pipeline="hiomr-kitchensink")


def test_unsupported_pipeline_fails(analysis_root: Path) -> None:
    with pytest.raises(module.CommandSampleStatsError, match="unsupported pipeline"):
        module.collect_command_sample_stats(analysis_root, name="x", pipeline="bjuice-v1")


def test_running_state_is_scoped_to_the_matching_rule_family(
    analysis_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unit = "HG003_unit"
    sv = (
        analysis_root
        / "daylily-omics-analysis"
        / "results"
        / "day"
        / "hg38"
        / unit
        / "align"
        / "hiomrs_sr"
        / "na"
        / "sv"
        / "hiomrs"
        / f"{unit}.hiomrs_sr.na.hiomrs.sv.vcf.gz"
    )
    sv.unlink()
    status = _status(analysis_root)
    status["slurm"]["jobs"][0]["name"] = f"hiomrs_longreadsv.{unit}"
    status["slurm"]["jobs"][0]["restart_count"] = 2
    Path(status["slurm"]["jobs"][0]["stderr"]).write_text(
        "ERROR first exact failure\nERROR later failure\n", encoding="utf-8"
    )
    monkeypatch.setattr(module, "collect_analysis_status", lambda *_args, **_kwargs: status)

    payload = module.collect_command_sample_stats(
        analysis_root,
        name="x",
        pipeline="hiomr-kitchensink",
    )

    milestones = payload["x"]["library_units"][0]["milestones"]
    assert milestones["hybrid_sv"]["display"] == "running 00:04:00"
    execution = milestones["hybrid_sv"]["execution"]
    assert execution["job_id"]["value"] == "123"
    assert execution["rule"]["value"] == "hiomrs_longreadsv"
    assert execution["eta"]["value"] == "ETA 00:10:00"
    assert execution["first_causal_error"]["value"] == "ERROR first exact failure"
    assert execution["retry_count"]["value"] == 2
    assert milestones["hybrid_snv"]["state"] == "complete"


def test_failed_milestone_reports_exact_accounting_and_first_log_error(
    analysis_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unit = "HG003_unit"
    sv = (
        analysis_root
        / "daylily-omics-analysis"
        / "results"
        / "day"
        / "hg38"
        / unit
        / "align"
        / "hiomrs_sr"
        / "na"
        / "sv"
        / "hiomrs"
        / f"{unit}.hiomrs_sr.na.hiomrs.sv.vcf.gz"
    )
    sv.unlink()
    log = _write(
        sv.parent / "logs" / f"{unit}.hiomrs_longreadsv.log",
        "setup\nERROR causal failure\nERROR cleanup failure\n",
    )
    status = _status(analysis_root)
    status["slurm"]["jobs"] = []
    status["accounting"]["jobs"] = [
        {
            "JobIDRaw": "456",
            "JobName": f"hiomrs_longreadsv.{unit}",
            "State": "FAILED",
            "Elapsed": "00:03:21",
            "ExitCode": "1:0",
            "Reason": "NonZeroExitCode",
        }
    ]
    status["recent_rule_logs"] = {"recent": [{"path": str(log)}]}
    monkeypatch.setattr(module, "collect_analysis_status", lambda *_args, **_kwargs: status)

    payload = module.collect_command_sample_stats(
        analysis_root,
        name="x",
        pipeline="hiomr-kitchensink",
    )

    milestone = payload["x"]["library_units"][0]["milestones"]["hybrid_sv"]
    assert milestone["state"] == "failed"
    assert milestone["execution"]["job_id"]["value"] == "456"
    assert milestone["execution"]["elapsed_seconds"]["value"] == 201
    assert milestone["execution"]["terminal_failure"]["exit_code"] == "1:0"
    assert milestone["execution"]["first_causal_error"]["value"] == "ERROR causal failure"


def test_strict_success_requires_all_controller_requirements(
    analysis_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    status = _status(analysis_root)
    status["state"] = "SUCCESS"
    status["controller"]["return_code"] = 0
    status["controller"]["processes"] = []
    status["slurm"]["jobs"] = []
    status["workflow"]["progress"] = {"completed": 9, "total": 9, "percent": 100}
    status["terminal_evidence"] = {
        "return_code": 0,
        "requirements": {
            "controller_exit_zero": True,
            "controller_inactive": True,
            "scheduler_idle": True,
            "workflow_progress_complete": True,
            "strict_artifacts_present": True,
        },
        "success_verified": True,
    }
    status["canonical_artifacts"] = {
        "all_present": True,
        "files": {
            "DAY_final_multiqc.html": ["/results/DAY_final_multiqc.html"],
            "multiqc_data.json": ["/results/DAY_final_multiqc_data/multiqc_data.json"],
            "dayoa_evidence_manifest.json": ["/results/dayoa_evidence_manifest.json"],
        },
    }
    monkeypatch.setattr(module, "collect_analysis_status", lambda *_args, **_kwargs: status)

    report = module.collect_command_sample_stats(
        analysis_root,
        name="x",
        pipeline="hiomr-kitchensink",
    )["x"]

    assert report["analysis"]["terminal_state"] == "SUCCESS"
    assert report["pipeline"]["strict_success"]["verified"] is True
    assert report["pipeline"]["evidence_manifest"] is True


def test_unit_cost_is_withheld_when_any_matching_benchmark_row_is_unpriced(
    analysis_root: Path,
) -> None:
    summary = (
        analysis_root
        / "daylily-omics-analysis"
        / "results"
        / "day"
        / "hg38"
        / "reports"
        / "benchmarks_summary.tsv"
    )
    summary.write_text(
        "sample\trule\ts\ttask_cost\n"
        "HG003_unit\thiomrs_core\t120\t0.25\n"
        "HG003_unit\thiomrs_collect\t30\t\n",
        encoding="utf-8",
    )

    unit = module.collect_command_sample_stats(
        analysis_root,
        name="x",
        pipeline="hiomr-kitchensink",
    )["x"]["library_units"][0]

    assert unit["benchmark_task_cost"]["value_usd"] is None
    assert unit["benchmark_task_cost"]["state"] == "incomplete"
    assert unit["benchmark_task_cost"]["unpriced_rows"] == 1


def test_missing_scheduler_and_retry_sources_remain_null(
    analysis_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    status = _status(analysis_root)
    status["workflow"]["master_log"] = None
    status["slurm"] = {"available": False, "jobs": []}
    status["accounting"] = {"available": False, "jobs": [], "state_counts": {}}
    status["job_counts"] = {}
    monkeypatch.setattr(module, "collect_analysis_status", lambda *_args, **_kwargs: status)

    pipeline = module.collect_command_sample_stats(
        analysis_root,
        name="x",
        pipeline="hiomr-kitchensink",
    )["x"]["pipeline"]

    assert pipeline["jobs_running"] is None
    assert pipeline["jobs_failed"] is None
    assert pipeline["jobs_to_run"] is None
    assert pipeline["job_counts"]["retried"]["value"] is None
    assert pipeline["job_counts"]["retried"]["available"] is False


def test_dag_copy_is_verified_and_refuses_overwrite(analysis_root: Path, tmp_path: Path) -> None:
    payload = module.collect_command_sample_stats(
        analysis_root, name="x", pipeline="hiomr-kitchensink"
    )
    destination = tmp_path / "named-rulegraph.png"
    copied = module.copy_dag(payload, destination)
    assert destination.read_text(encoding="utf-8") == "png-data"
    assert copied["sha256"] == payload["x"]["dag"]["sha256"]
    with pytest.raises(module.CommandSampleStatsError, match="refusing to overwrite"):
        module.copy_dag(payload, destination)


def test_human_table_contains_requested_fields(analysis_root: Path) -> None:
    payload = module.collect_command_sample_stats(
        analysis_root, name="x", pipeline="hiomr-kitchensink"
    )
    text = module.render_command_sample_stats(payload)
    assert "Sample\t%\tSR Aln\tLR Aln\tHybrid SNV\tHybrid SV\tMito" in text
    assert "QC Disposition\tPackage Ready\tDelivered\tGIAB HC Fscore" in text
    assert "submitted=4" in text
    assert "dependency-blocked=0" in text
    assert "strict success=N" in text
    assert "HG003_unit" in text


def test_cli_emits_required_single_top_level_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = {"named-run": {"pipeline": {"name": "hiomr-kitchensink"}}}
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")
    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setattr(module, "collect_command_sample_stats", lambda *_args, **_kwargs: payload)
    monkeypatch.setattr(module, "render_command_sample_stats", lambda _payload: "table")

    result = runner.invoke(
        app,
        [
            "--json",
            "command",
            "sample-stats",
            "hiomr-kitchensink",
            "--name",
            "named-run",
            "--analysis-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == payload


def test_remote_dag_transfer_is_bounded_and_verified(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    content = b"rulegraph" * 4000

    def fake_run_shell(_instance, _region, script, **_kwargs):
        offset = int(script.split(" skip=", 1)[1].split(" ", 1)[0])
        count = int(script.split(" count=", 1)[1].split(" ", 1)[0])
        return SimpleNamespace(stdout=base64.b64encode(content[offset : offset + count]).decode())

    monkeypatch.setattr("daylily_ec.aws.ssm.run_shell", fake_run_shell)
    target = tmp_path / "named.png"
    result = cli_module._download_sample_stats_dag(
        instance_id="i-1",
        region="us-west-2",
        profile="lsmc",
        remote_user="ubuntu",
        remote_path="/fsx/analysis/dags/rulegraph.png",
        expected_size=len(content),
        expected_sha256=hashlib.sha256(content).hexdigest(),
        destination=target,
    )

    assert target.read_bytes() == content
    assert result["sha256"] == hashlib.sha256(content).hexdigest()


def test_aws_context_includes_cluster_and_project_budget_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Client:
        def __init__(self, name: str):
            self.name = name

        def describe_instances(self, **_kwargs):
            return {
                "Reservations": [{"Instances": [{"Placement": {"AvailabilityZone": "us-west-2c"}}]}]
            }

        def get_caller_identity(self):
            return {"Account": "123456789012"}

        def describe_budget(self, **_kwargs):
            return {
                "Budget": {
                    "BudgetName": "cluster-a",
                    "BudgetLimit": {"Amount": "600", "Unit": "USD"},
                    "TimeUnit": "MONTHLY",
                    "BudgetType": "COST",
                    "CalculatedSpend": {
                        "ActualSpend": {"Amount": "25", "Unit": "USD"},
                        "ForecastedSpend": {"Amount": "50", "Unit": "USD"},
                    },
                }
            }

    class Session:
        def __init__(self, **_kwargs):
            pass

        def client(self, name: str, **_kwargs):
            return Client(name)

    class Record:
        def __init__(self, payload):
            self.payload = payload

        def to_dict(self):
            return self.payload

    monkeypatch.setattr("boto3.Session", Session)
    monkeypatch.setattr(
        "daylily_ec.aws.cost_centers.get_cost_center",
        lambda *_args, **_kwargs: Record({"monthly_cap_usd": "600"}),
    )
    monkeypatch.setattr(
        "daylily_ec.aws.cost_centers.get_cost_center_usage",
        lambda *_args, **_kwargs: Record({"monthly_spend_usd": "25"}),
    )
    payload = {
        "run": {
            "cluster": {},
            "costs": {},
            "status_evidence": {
                "slurm": {"jobs": [{"comment": "project-a"}]},
                "accounting": {"jobs": []},
            },
        }
    }

    module.enrich_aws_context(
        payload,
        profile="lsmc",
        region="us-west-2",
        cluster="cluster-a",
        headnode_instance_id="i-1",
    )

    report = payload["run"]
    assert report["cluster"]["availability_zone"] == "us-west-2c"
    assert report["costs"]["cluster_budget"]["limit"] == "600"
    assert report["costs"]["cluster_budget"]["actual_spend"] == "25"
    assert report["costs"]["project_budget"]["usage"]["monthly_spend_usd"] == "25"
