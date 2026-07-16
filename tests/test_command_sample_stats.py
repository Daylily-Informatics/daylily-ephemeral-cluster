from __future__ import annotations

import json
import base64
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

import daylily_ec.command_sample_stats as module
import daylily_ec.cli as cli_module
from daylily_ec.cli import app
from typer.testing import CliRunner

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
    return {
        "workflow": {
            "master_log": str(master),
            "progress": {"completed": 3, "total": 9, "percent": 33},
            "failure_count": 0,
            "failure_lines": [],
        },
        "controller": {
            "processes": [{"elapsed_seconds": 600}],
            "tmux_panes": [
                {
                    "session": "hiomrs-test",
                    "observed_commands": ["dy-a slurm hg38", "dy-r produce_hiomrs"],
                }
            ],
        },
        "slurm": {
            "jobs": [
                {
                    "name": "rule_HG003_unit",
                    "state": "RUNNING",
                    "elapsed": "00:04:00",
                    "restart_count": 0,
                    "comment": "project-a",
                }
            ]
        },
        "accounting": {"jobs": []},
        "canonical_artifacts": {"all_present": False},
        "benchmarks": {"completed_cost_usd_sum": 1.25},
    }


@pytest.fixture
def analysis_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "analysis"
    dayoa = root / "daylily-omics-analysis"
    _write(
        dayoa / "config" / "units.tsv",
        "ANALYSIS_UNIT_UID\tSAMPLEID\nHG003_unit\tHG003\n",
    )
    _write(
        dayoa / "config" / "samples.tsv",
        "SAMPLEID\tBIOLOGICAL_SEX\tSAMPLESOURCE\tSAMPLEUSE\tORDER_TYPE\nHG003\tXY\tblood\tvalidation\tpositive_control\n",
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
    status = _status(root)
    monkeypatch.setattr(module, "collect_analysis_status", lambda *_args, **_kwargs: status)
    monkeypatch.setattr(
        module,
        "_git_identity",
        lambda *_args, **_kwargs: {
            "commit": "abc",
            "exact_tag": "11.0.13",
            "dirty": False,
            "dirty_paths": [],
        },
    )
    return root


def test_collect_sample_stats_contract(analysis_root: Path) -> None:
    payload = module.collect_command_sample_stats(
        analysis_root,
        name="bjuice10",
        pipeline="hiomrs-kitchensink",
    )

    assert list(payload) == ["bjuice10"]
    report = payload["bjuice10"]
    assert report["command_details"]["command_catalog_key"] == "hybrid_ilmn_ont_hiomrs_kitchensink"
    assert report["command_details"]["git_tag"] == "11.0.13"
    assert report["command_details"]["retried_jobs"]["count"] == 1
    assert report["analysis"]["started_at_source"] == "controller process elapsed time"
    assert 599 <= report["analysis"]["runtime_seconds"] <= 601
    assert report["pipeline"]["samples_rows"] == 1
    assert report["pipeline"]["units_rows"] == 1
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
    assert unit["overall_percent_complete"] == 100.0
    assert unit["milestones"]["mitochondrial"]["state"] == "complete"
    assert unit["milestones"]["segdup"]["completed_targets"] == 2
    assert unit["metrics"]["required_gender"]["value"] == "XY"
    assert unit["metrics"]["observed_gender"]["value"] == "XY"
    assert unit["metrics"]["final_qc_disposition"]["value"] == "pass"
    assert unit["giab_hc_snv_fscore"]["value"] == 0.998
    assert report["dag"]["available"] is True


def test_authoritative_analysis_unit_uid_is_required_and_unique(analysis_root: Path) -> None:
    units = analysis_root / "daylily-omics-analysis" / "config" / "units.tsv"
    units.write_text(
        "ANALYSIS_UNIT_UID\tSAMPLEID\nHG003_unit\tHG003\nHG003_unit\tHG003\n", encoding="utf-8"
    )
    with pytest.raises(module.CommandSampleStatsError, match="must be unique"):
        module.collect_command_sample_stats(analysis_root, name="x", pipeline="hiomrs-kitchensink")


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
    monkeypatch.setattr(module, "collect_analysis_status", lambda *_args, **_kwargs: status)

    payload = module.collect_command_sample_stats(
        analysis_root,
        name="x",
        pipeline="hiomrs-kitchensink",
    )

    milestones = payload["x"]["library_units"][0]["milestones"]
    assert milestones["hybrid_sv"]["display"] == "running 00:04:00"
    assert milestones["hybrid_snv"]["state"] == "complete"


def test_dag_copy_is_verified_and_refuses_overwrite(analysis_root: Path, tmp_path: Path) -> None:
    payload = module.collect_command_sample_stats(
        analysis_root, name="x", pipeline="hiomrs-kitchensink"
    )
    destination = tmp_path / "named-rulegraph.png"
    copied = module.copy_dag(payload, destination)
    assert destination.read_text(encoding="utf-8") == "png-data"
    assert copied["sha256"] == payload["x"]["dag"]["sha256"]
    with pytest.raises(module.CommandSampleStatsError, match="refusing to overwrite"):
        module.copy_dag(payload, destination)


def test_human_table_contains_requested_fields(analysis_root: Path) -> None:
    payload = module.collect_command_sample_stats(
        analysis_root, name="x", pipeline="hiomrs-kitchensink"
    )
    text = module.render_command_sample_stats(payload)
    assert "Sample\t%\tSR Aln\tLR Aln\tHybrid SNV\tHybrid SV\tMito" in text
    assert "QC Disposition\tPackage Ready\tDelivered\tGIAB HC Fscore" in text
    assert "HG003_unit" in text


def test_cli_emits_required_single_top_level_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = {"named-run": {"pipeline": {"name": "hiomrs-kitchensink"}}}
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
            "hiomrs-kitchensink",
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
