from __future__ import annotations

import json
import posixpath
import shlex
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from daylily_ec.aws.ssm import HeadNodeTarget, SsmError
from daylily_ec.scripts.common import CommandError
from daylily_ec.scripts.daylily_cfg_headnode import _load_repo_overrides
import daylily_ec.scripts.daylily_cfg_headnode as cfg_headnode_module
import daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests as remote_tests_module
import daylily_ec.scripts.daylily_run_omics_analysis_headnode as run_omics_module
import daylily_ec.scripts.daylily_ssh_into_headnode as ssh_headnode_module


def _controller_target_marker(
    session_name: str,
    repo_path: str,
    *,
    pid: int = 4242,
) -> str:
    analysis_root = posixpath.dirname(repo_path)
    payload = {
        "schema_version": "dyec.controller_target.v2",
        "controller_id": session_name,
        "pid": pid,
        "cwd": repo_path,
        "log_path": f"{repo_path}/.dyec/controller.log",
        "dag_path": f"{repo_path}/.dyec/controller-dag.png",
        "analysis_root": analysis_root,
        "status_attempt_id": "00000000-0000-4000-8000-000000000001",
    }
    return "\n".join(
        [
            f"__DAYLILY_TMUX_SESSION__={session_name}",
            "__DYEC_CONTROLLER_TARGET__=" + json.dumps(payload, separators=(",", ":")),
        ]
    )


def _assert_immutable_pinned_dayoa_controller(script: str) -> None:
    forbidden = (
        "BCLCONVERT_PROFILE_PATCH_SCRIPT",
        "BCLCONVERT_LANE_SPLIT_PATCH_SCRIPT",
        "patch_bclconvert_profile_config",
        "patch_bclconvert_lane_split",
        "patch_dayoa_runtime_tmpdir_wrappers",
        "patch_run_qc_reports_pycoqc_python",
        "patch_pycoqc_readonly_sort",
        "patch_goleft_indexcov_empty_sex_arg",
        "patch_mosdepth_empty_outputs",
        "patch_rtg_vcfeval_parse_output_dir",
        "patch_vep_empty_concat_fofn",
        "patch_contam_identity_zero_variant_outputs",
        "runtime_repair_requested",
        "workflow/rules/",
        "workflow/envs/",
    )
    for marker in forbidden:
        assert marker not in script
    assert 'verify_pinned_dayoa_checkout "before workflow dispatch"' in script
    assert 'verify_pinned_dayoa_checkout "after workflow return"' in script
    assert 'git -C "$repo_path" diff --quiet --' in script
    assert 'git -C "$repo_path" diff --cached --quiet --' in script
    assert 'git -C "$repo_path" ls-files --others --exclude-standard' in script
    assert "is_allowed_catalog_runtime_path()" in script
    assert "PINNED_SOURCE_TEST_OVERRIDE=" in script
    assert "pinned-source-test-override-$evidence_phase" in script
    assert "Explicit pinned-source test override active" in script
    for allowed_path in (
        ".dyec/controller.log",
        ".dyec/status.json.lock",
        ".dyec/status.json.tmp-*",
        "status.json",
        "analysis_artifacts.tsv",
        "artifact_lineage.tsv",
        "pipeline_details.md",
        "pipeline_workflow_planned.mmd",
        "pipeline_workflow_planned.pdf",
        "pipeline_workflow_checkpoint_*.mmd",
        "pipeline_workflow_checkpoint_*.pdf",
        "pipeline_workflow_final_success.mmd",
        "pipeline_workflow_final_success.pdf",
        "pipeline_workflow_final_failed.mmd",
        "pipeline_workflow_final_failed.pdf",
        "config/specimens.tsv",
        "config/samples.tsv",
        "config/libraries.tsv",
        "config/sequencing_inputs.tsv",
        "config/analysis_units.tsv",
        "config/analysis_unit_inputs.tsv",
        "config/dyec_manifest_stage_receipt.json",
        "config/dyec_runtime_config.yaml",
        "config/dyec_analysis_recovery_source.json",
        "config/day_profiles/slurm/.template-source.sha256",
    ):
        assert allowed_path in script
    assert 'case "$1" in' in script
    assert script.index('verify_pinned_dayoa_checkout "before workflow dispatch"') < script.index(
        'run_dy_command "$DY_COMMAND"'
    )
    assert script.index('verify_pinned_dayoa_checkout "after workflow return"') > script.index(
        'run_dy_command "$DY_COMMAND"'
    )


def test_regular_file_controller_log_does_not_delay_receipt_for_inherited_descriptor(
    tmp_path,
) -> None:
    controller_log = tmp_path / "controller.log"
    receipt = tmp_path / "status.rc"
    script = (
        'exec >>"$1" 2>&1\n'
        "sleep 2 &\n"
        'printf \'0\\n\' >"$2"\n'
    )

    subprocess.run(
        ["bash", "-c", script, "dyec-controller-test", str(controller_log), str(receipt)],
        check=True,
        timeout=1,
    )

    assert receipt.read_text(encoding="utf-8") == "0\n"


class TestSshIntoHeadnodeScript:
    @patch("daylily_ec.scripts.daylily_ssh_into_headnode.start_session")
    @patch("daylily_ec.scripts.daylily_ssh_into_headnode.wait_for_ssm_online")
    @patch(
        "daylily_ec.scripts.daylily_ssh_into_headnode.resolve_headnode_instance_id",
        return_value=HeadNodeTarget("cluster-a", "us-west-2", "i-abc123"),
    )
    @patch("daylily_ec.scripts.daylily_ssh_into_headnode.resolve_cluster", return_value="cluster-a")
    @patch("daylily_ec.scripts.daylily_ssh_into_headnode.resolve_region", return_value="us-west-2")
    @patch("daylily_ec.scripts.daylily_ssh_into_headnode.need_cmd")
    def test_dry_run_prints_preview_without_starting_session(
        self,
        _mock_need_cmd,
        _mock_region,
        _mock_cluster,
        _mock_target,
        _mock_wait,
        mock_start,
        capsys,
    ):
        rc = ssh_headnode_module.main(["--profile", "dev", "--dry-run"])

        assert rc == 0
        mock_start.assert_not_called()
        out = capsys.readouterr().out
        assert "Opening Session Manager session as ubuntu to i-abc123" in out
        assert (
            "Session Manager command: aws ssm start-session --region us-west-2 --target i-abc123 --document-name SSM-SessionManagerRunShell"
            in out
        )

    def test_requires_profile(self, monkeypatch):
        monkeypatch.delenv("AWS_PROFILE", raising=False)

        with pytest.raises(CommandError, match="AWS profile is required"):
            ssh_headnode_module.main([])

    @patch("daylily_ec.scripts.daylily_ssh_into_headnode.start_session", return_value=17)
    @patch("daylily_ec.scripts.daylily_ssh_into_headnode.wait_for_ssm_online")
    @patch(
        "daylily_ec.scripts.daylily_ssh_into_headnode.resolve_headnode_instance_id",
        return_value=HeadNodeTarget("cluster-a", "us-west-2", "i-abc123"),
    )
    @patch("daylily_ec.scripts.daylily_ssh_into_headnode.resolve_cluster", return_value="cluster-a")
    @patch("daylily_ec.scripts.daylily_ssh_into_headnode.resolve_region", return_value="us-west-2")
    @patch("daylily_ec.scripts.daylily_ssh_into_headnode.need_cmd")
    def test_starts_session(
        self,
        _mock_need_cmd,
        _mock_region,
        _mock_cluster,
        _mock_target,
        mock_wait,
        mock_start,
        capsys,
    ):
        rc = ssh_headnode_module.main(["--profile", "dev"])

        assert rc == 17
        mock_wait.assert_called_once_with("i-abc123", "us-west-2", profile="dev", timeout=120)
        mock_start.assert_called_once_with(
            "i-abc123",
            "us-west-2",
            profile="dev",
            replace_process=True,
        )
        out = capsys.readouterr().out
        assert "Opening Session Manager session as ubuntu to i-abc123" in out
        assert "sudo -iu ubuntu" not in out

    @patch(
        "daylily_ec.scripts.daylily_ssh_into_headnode.start_session",
        side_effect=SsmError(
            "Session Manager must be configured to run shell sessions as ubuntu via SSM-SessionManagerRunShell."
        ),
    )
    @patch("daylily_ec.scripts.daylily_ssh_into_headnode.wait_for_ssm_online")
    @patch(
        "daylily_ec.scripts.daylily_ssh_into_headnode.resolve_headnode_instance_id",
        return_value=HeadNodeTarget("cluster-a", "us-west-2", "i-abc123"),
    )
    @patch("daylily_ec.scripts.daylily_ssh_into_headnode.resolve_cluster", return_value="cluster-a")
    @patch("daylily_ec.scripts.daylily_ssh_into_headnode.resolve_region", return_value="us-west-2")
    @patch("daylily_ec.scripts.daylily_ssh_into_headnode.need_cmd")
    def test_start_session_failures_surface_as_command_error(
        self,
        _mock_need_cmd,
        _mock_region,
        _mock_cluster,
        _mock_target,
        _mock_wait,
        _mock_start,
    ):
        with pytest.raises(CommandError, match="run shell sessions as ubuntu"):
            ssh_headnode_module.main(["--profile", "dev"])


class TestRunOmicsAnalysisHeadnodeScript:
    @pytest.fixture(autouse=True)
    def _default_remote_user(self, monkeypatch):
        monkeypatch.setattr(run_omics_module, "resolve_remote_user", lambda *args, **kwargs: "ubuntu")

    def test_controller_has_no_embedded_dayoa_source_patch_payload(self):
        assert not hasattr(run_omics_module, "BCLCONVERT_PROFILE_PATCH_SCRIPT")
        assert not hasattr(run_omics_module, "BCLCONVERT_LANE_SPLIT_PATCH_SCRIPT")

    def test_parse_remote_config_success(self):
        result = run_omics_module.parse_remote_config(
            "\n".join(
                [
                    "__DAYLILY_STAGE_DIR__=/fsx/stage/run-1",
                    "__DAYLILY_STAGE_SAMPLES__=/fsx/stage/run-1/foo_samples.tsv",
                    "__DAYLILY_STAGE_UNITS__=/fsx/stage/run-1/foo_units.tsv",
                ]
            )
        )

        assert result.stage_dir == "/fsx/stage/run-1"
        assert result.samples_path.endswith("foo_samples.tsv")
        assert result.units_path.endswith("foo_units.tsv")

    def test_parse_remote_config_error_marker_raises(self):
        with pytest.raises(CommandError, match="Remote lookup failed: missing_stage_dir"):
            run_omics_module.parse_remote_config("__DAYLILY_ERROR__=missing_stage_dir")

    def test_main_requires_analysis_identity(self):
        with pytest.raises(SystemExit) as exc:
            run_omics_module.main(["--profile", "dev"])

        assert exc.value.code == 2

    def test_parse_workflow_launch_extracts_run_metadata(self):
        launch = run_omics_module.parse_workflow_launch(
            "\n".join(
                [
                    "__DAYLILY_SESSION__=sess-1",
                    "__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/sess-1",
                    "__DAYLILY_REPO_PATH__=/fsx/analysis_results/johnm/dayoa/daylily-omics-analysis",
                    "__DAYLILY_DY_COMMAND__=bin/day_run help --produce-analysis-artifact-manifest true",
                    _controller_target_marker(
                        "sess-1",
                        "/fsx/analysis_results/johnm/dayoa/daylily-omics-analysis",
                    ),
                ]
            )
            + "\n"
        )

        assert launch.session_name == "sess-1"
        assert launch.tmux_session_name == "sess-1"
        assert launch.run_dir == "/home/ubuntu/daylily-runs/sess-1"
        assert launch.repo_path.endswith("/daylily-omics-analysis")
        assert "--produce-analysis-artifact-manifest true" in launch.dy_command
        assert launch.controller_target.controller_id == "sess-1"
        assert launch.controller_target.pid == 4242
        assert launch.controller_target.analysis_root == "/fsx/analysis_results/johnm/dayoa"

    @pytest.mark.parametrize(
        ("updates", "match"),
        [
            ({"schema_version": "dyec.controller_target.v1"}, "schema must be"),
            ({"pid": 0}, "positive integer"),
            ({"cwd": "relative/path"}, "canonical absolute path"),
            (
                {"cwd": "/fsx/analysis_results/johnm/dayoa/not-the-dayoa-clone"},
                "must be the daylily-omics-analysis clone",
            ),
            (
                {"log_path": "/home/ubuntu/daylily-runs/controller.log"},
                "log_path must be within cwd",
            ),
            (
                {"dag_path": "/fsx/analysis_results/other/dag.png"},
                "dag_path must be within cwd",
            ),
        ],
    )
    def test_parse_controller_target_rejects_non_source_contracts(self, updates, match):
        repo_path = "/fsx/analysis_results/johnm/dayoa/daylily-omics-analysis"
        payload = json.loads(
            _controller_target_marker("sess-1", repo_path).splitlines()[-1].split("=", 1)[1]
        )
        payload.update(updates)

        with pytest.raises(CommandError, match=match):
            run_omics_module.parse_controller_target(json.dumps(payload))

    def test_parse_workflow_launch_rejects_duplicate_or_mismatched_controller_identity(self):
        repo_path = "/fsx/analysis_results/johnm/dayoa/daylily-omics-analysis"
        common = "\n".join(
            [
                "__DAYLILY_SESSION__=sess-1",
                "__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/sess-1",
                f"__DAYLILY_REPO_PATH__={repo_path}",
                "__DAYLILY_DY_COMMAND__=bin/day_run help --produce-dag true",
            ]
        )
        marker = _controller_target_marker("sess-1", repo_path)
        with pytest.raises(CommandError, match="duplicate controller target"):
            run_omics_module.parse_workflow_launch(f"{common}\n{marker}\n{marker}\n")

        mismatched = _controller_target_marker("sess-1", repo_path).replace(
            '"controller_id":"sess-1"', '"controller_id":"different-session"'
        )
        with pytest.raises(CommandError, match="identifiers disagree"):
            run_omics_module.parse_workflow_launch(f"{common}\n{mismatched}\n")

    def test_parse_workflow_launch_uses_actual_sanitized_tmux_session_identity(self):
        repo_path = "/fsx/analysis_results/johnm/dayoa/daylily-omics-analysis"
        stdout = "\n".join(
            [
                "__DAYLILY_SESSION__=analysis:requested",
                "__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/analysis:requested",
                f"__DAYLILY_REPO_PATH__={repo_path}",
                "__DAYLILY_DY_COMMAND__=bin/day_run help --produce-dag true",
                _controller_target_marker("analysis_requested", repo_path),
            ]
        )

        launch = run_omics_module.parse_workflow_launch(stdout)

        assert launch.session_name == "analysis:requested"
        assert launch.tmux_session_name == "analysis_requested"
        assert launch.controller_target.controller_id == "analysis_requested"

    def test_build_default_command_includes_requested_flags(self):
        command = run_omics_module.build_default_command(
            target="produce_snv_concordances",
            genome="hg38",
            jobs=8,
            aligners=["bwa2a", "strobe"],
            dedupers=["dmd"],
            snv_callers=["deep"],
            sv_callers=["tiddit"],
            containerized=False,
            dry_run=True,
            extra="--rerun-incomplete",
        )

        assert "DAY_CONTAINERIZED=false" in command
        assert "dy-r" in command
        assert "aligners=['bwa2a','strobe']" in command
        assert "sv_callers=['tiddit']" in command
        assert "-j 8" in command
        assert "-n" in command
        assert "--rerun-incomplete" in command
        assert "--produce-analysis-artifact-manifest true" in command
        assert "--produce-rulegraph true" in command
        assert "--produce-filegraph false" in command
        assert "--produce-dag false" in command

        overridden = run_omics_module.build_default_command(
            target="help",
            genome="hg38",
            jobs=1,
            aligners=["bwa2a"],
            dedupers=["dmd"],
            snv_callers=["deep"],
            sv_callers=[],
            containerized=False,
            dry_run=True,
            extra=None,
            producer_overrides={
                "--produce-analysis-artifact-manifest": "false",
                "--produce-rulegraph": "false",
                "--produce-filegraph": "true",
                "--produce-dag": "true",
            },
        )
        assert "--produce-analysis-artifact-manifest false" in overridden
        assert "--produce-rulegraph false" in overridden
        assert "--produce-filegraph true" in overridden
        assert "--produce-dag true" in overridden

    def test_apply_workflow_execution_options_enforces_dry_run_for_custom_command(self):
        command = run_omics_module.apply_workflow_execution_options(
            "dy-r produce_sentdhiomr2_kitchensink -p -k -j 6",
            dry_run=True,
            rerun_triggers=["mtime"],
        )

        tokens = shlex.split(command)
        assert tokens[-3:] == ["--rerun-triggers", "mtime", "-n"]
        assert run_omics_module.dy_command_has_dry_run_flag(command)

    def test_apply_workflow_execution_options_rejects_duplicate_rerun_trigger_contract(self):
        with pytest.raises(
            CommandError,
            match="cannot be combined with --rerun-triggers embedded in --dy-command",
        ):
            run_omics_module.apply_workflow_execution_options(
                "dy-r produce_sentdhiomr2_kitchensink -p -k -j 6 --rerun-triggers mtime",
                dry_run=True,
                rerun_triggers=["mtime"],
            )

    def test_main_rejects_removed_provider_registration_options(self):
        with pytest.raises(SystemExit) as exc_info:
            run_omics_module.main(
                [
                    "--region",
                    "us-west-2",
                    "--profile",
                    "dev",
                    "--git-tag",
                    "13.0.0",
                    "--analysis-id",
                    "analysis",
                    "--executing-entity",
                    "johnm",
                    "--export-destination-s3-uri",
                    "s3://bucket/analysis_results/johnm/analysis/",
                    "--export-trigger",
                    "on-success",
                    "--dewey-url",
                    "https://dewey.example",
                    "--dewey-token-env",
                    "DEWEY_TOKEN",
                ]
            )
        assert exc_info.value.code == 2

    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.run_shell")
    def test_discover_stage_config_with_explicit_stage_dir(self, mock_run_shell, capsys):
        mock_run_shell.return_value = SimpleNamespace(
            stdout="\n".join(
                [
                    "__DAYLILY_STAGE_DIR__=/home/ubuntu/stage/run-1",
                    "__DAYLILY_STAGE_SAMPLES__=/home/ubuntu/stage/run-1/foo_samples.tsv",
                    "__DAYLILY_STAGE_UNITS__=/home/ubuntu/stage/run-1/foo_units.tsv",
                ]
            )
            + "\n",
            stderr="",
        )

        config = run_omics_module.discover_stage_config(
            "i-abc123",
            "dev",
            "us-west-2",
            "ubuntu",
            "~/stage/run-1",
            "/ignored",
        )

        script = mock_run_shell.call_args.args[2]
        assert "/home/ubuntu/stage/run-1" in script
        assert "WAIT_DEADLINE=$((SECONDS +" in script
        assert "last_error=missing_stage_dir" in script
        assert "found_config=true" in script
        assert "break" in script
        assert (
            'samples_file=$(ls -1 "$STAGE_DIR"/*_samples.tsv 2>/dev/null | head -n 1 || true)'
            in script
        )
        assert (
            'units_file=$(ls -1 "$STAGE_DIR"/*_units.tsv 2>/dev/null | head -n 1 || true)' in script
        )
        assert "exit 0" not in script
        assert (
            mock_run_shell.call_args.kwargs["timeout"]
            == run_omics_module.STAGE_CONFIG_DISCOVERY_TIMEOUT_SECONDS
        )
        assert config.stage_dir == "/home/ubuntu/stage/run-1"
        assert "__DAYLILY_STAGE_DIR__=/home/ubuntu/stage/run-1" in capsys.readouterr().out

    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.run_shell")
    def test_discover_stage_config_waits_for_latest_stage_config(self, mock_run_shell):
        mock_run_shell.return_value = SimpleNamespace(
            stdout="\n".join(
                [
                    "__DAYLILY_STAGE_DIR__=/fsx/stage/run-2/",
                    "__DAYLILY_STAGE_SAMPLES__=/fsx/stage/run-2/foo_samples.tsv",
                    "__DAYLILY_STAGE_UNITS__=/fsx/stage/run-2/foo_units.tsv",
                ]
            )
            + "\n",
            stderr="",
        )

        config = run_omics_module.discover_stage_config(
            "i-abc123",
            "dev",
            "us-west-2",
            "ubuntu",
            None,
            "/fsx/stage",
        )

        script = mock_run_shell.call_args.args[2]
        assert "WAIT_DEADLINE=$((SECONDS +" in script
        assert "last_error=no_stage_runs" in script
        assert "found_config=true" in script
        assert 'latest_dir=$(ls -1dt "$STAGE_BASE"/*/ 2>/dev/null | head -n 1 || true)' in script
        assert (
            'samples_file=$(ls -1 "$latest_dir"/*_samples.tsv 2>/dev/null | head -n 1 || true)'
            in script
        )
        assert "exit 0" not in script
        assert config.units_path == "/fsx/stage/run-2/foo_units.tsv"

    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.run_shell",
        return_value=SimpleNamespace(
            stdout=(
                "__DAYLILY_SESSION__=sess-1\n"
                "__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/sess-1\n"
                "__DAYLILY_REPO_PATH__=/fsx/analysis_results/johnm/analysis/daylily-omics-analysis\n"
                "__DAYLILY_DY_COMMAND__=dy-r help --produce-analysis-artifact-manifest true\n"
                + _controller_target_marker(
                    "sess-1",
                    "/fsx/analysis_results/johnm/analysis/daylily-omics-analysis",
                )
                + "\n"
            ),
            stderr="",
        ),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.discover_stage_config",
        return_value=run_omics_module.RemoteConfig(
            stage_dir="/fsx/stage/run-1",
            samples_path="/fsx/stage/run-1/foo_samples.tsv",
            units_path="/fsx/stage/run-1/foo_units.tsv",
        ),
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.validate_headnode_readiness")
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.wait_for_ssm_online")
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_headnode_instance_id",
        return_value=HeadNodeTarget("cluster-a", "us-west-2", "i-abc123"),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_cluster",
        return_value="cluster-a",
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_region",
        return_value="us-west-2",
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.need_cmd")
    def test_main_launches_workflow_session(
        self,
        _mock_need_cmd,
        _mock_region,
        _mock_cluster,
        _mock_target,
        _mock_wait,
        mock_validate_headnode_readiness,
        mock_discover,
        mock_run_shell,
        capsys,
    ):
        events = []
        mock_validate_headnode_readiness.side_effect = lambda *args, **kwargs: events.append(
            "readiness"
        )
        mock_discover.side_effect = lambda *args, **kwargs: (
            events.append("discover")
            or run_omics_module.RemoteConfig(
                stage_dir="/fsx/stage/run-1",
                samples_path="/fsx/stage/run-1/foo_samples.tsv",
                units_path="/fsx/stage/run-1/foo_units.tsv",
            )
        )

        tmux_result = mock_run_shell.return_value
        mock_run_shell.side_effect = lambda *args, **kwargs: events.append("tmux") or tmux_result

        rc = run_omics_module.main(
            [
                "--profile",
                "dev",
                "--git-tag",
                "12.0.5",
                "--input-contract",
                "sample_manifest",
                "--analysis-id",
                "analysis",
                "--executing-entity",
                "johnm",
                "--project",
                "project-alpha",
                "--cost-center",
                "bjuice",
                "--dry-run",
            ]
        )

        assert rc == 0
        assert events == ["readiness", "discover", "tmux"]
        mock_validate_headnode_readiness.assert_called_once_with(
            "i-abc123",
            "us-west-2",
            profile="dev",
            timeout=120,
            comment="Validate DAY-EC headnode readiness before workflow launch",
            remote_user="ubuntu",
        )
        script = mock_run_shell.call_args.args[2]
        outer_syntax = subprocess.run(
            ["bash", "-n"], input=script, text=True, capture_output=True, check=False
        )
        assert outer_syntax.returncode == 0, outer_syntax.stderr
        pipeline = script.split("cat <<'PAYLOAD' > \"$work_script\"\n", 1)[1].split(
            "\nPAYLOAD\n", 1
        )[0]
        pipeline_syntax = subprocess.run(
            ["bash", "-n"], input=pipeline, text=True, capture_output=True, check=False
        )
        assert pipeline_syntax.returncode == 0, pipeline_syntax.stderr
        assert "REMOTE_USER=ubuntu" in script
        assert 'run_dir="/home/$REMOTE_USER/daylily-runs/$SESSION_NAME"' in script
        assert 'work_script="$run_dir/dyec-controller-launch.sh"' in script
        assert 'tmux_log="$run_dir/tmux.log"' in script
        assert 'controller_target_file="$run_dir/controller_target.json"' in script
        assert 'controller_log_path="$repo_path/.dyec/controller.log"' in script
        assert 'controller_dag_path="$repo_path/.dyec/controller-dag.png"' in script
        assert 'STATUS_FILE="${DAYLILY_REPO_PATH}/status.json"' in script
        assert 'STATUS_HELPER="${DAYLILY_REPO_PATH}/bin/util/analysis_status.py"' in script
        assert "STATUS_ATTEMPT_ID=" in script
        assert "status_v2 start-controller" in script
        assert "status_v2 finish-controller" in script
        assert "status_v2 record-snakemake-log" in script
        assert 'export DAYLILY_CONTROLLER_PID="$BASHPID"' in script
        assert 'export DAYLILY_STATUS_ATTEMPT_ID="$STATUS_ATTEMPT_ID"' in script
        assert 'status_file="$repo_path/status.json"' in script
        assert 'status_file="$run_dir/status.json"' not in script
        assert "os.replace(temporary, path)" in script
        assert 'snakemake_log_baseline="$DAYLILY_RUN_DIR/snakemake-log-baseline.txt"' in script
        assert "-name '*.snakemake.log'" in script
        assert 'comm -13 "$snakemake_log_baseline" "$snakemake_log_current"' in script
        assert '--log-path "${invocation_snakemake_logs[0]}"' in script
        assert '--log-attribution "exact invocation file-set difference"' in script
        assert "dyec.controller_target.v2" in script
        assert "python3 -c " in script
        assert "if ! day-clone" in script
        assert "__DAYLILY_ERROR__=analysis_clone_failed" in script
        assert script.index("status_v2 start-controller") < script.index(
            "python3 -c 'import json, os, pathlib; path = pathlib.Path(os.environ"
        )
        assert "DAYLILY_RUN_DIR=%q" in script
        assert "DAYLILY_REPO_PATH=%q" in script
        assert "DAYLILY_TMUX_LOG=%q" in script
        assert "DAYLILY_TMUX_SESSION=%q" in script
        assert "DAYLILY_CONTROLLER_TARGET_FILE=%q" in script
        assert "bash \"$DAYLILY_WORK_SCRIPT\"" in script
        assert 'tmux new-session -d -s "$tmux_session_name"' in script
        assert 'tmux_pane_target="$tmux_session_name:0.0"' in script
        assert 'tmux send-keys -t "$tmux_pane_target" "$tmux_command" C-m' in script
        assert 'exec bash --login --interactive' in script
        assert 'preserving tmux shell for inspection' in script
        assert 'tmux_session_name="${SESSION_NAME//[^A-Za-z0-9_-]/_}"' in script
        assert 'tmux has-session -t "=$tmux_session_name"' in script
        assert 'exec >> "$CONTROLLER_LOG_PATH" 2>&1' in script
        assert 'exec > >(tee -a "$CONTROLLER_LOG_PATH") 2>&1' not in script
        assert "-name 'dag_*.png'" in script
        assert 'comm -13 "$controller_dag_baseline" "$current"' in script
        assert "rulegraph" not in script[
            script.index("sync_controller_dag"):script.index("DAYLILY_STATUS_FINALIZED=1")
        ]
        assert 'runtime_tmp_name="${SESSION_NAME//[^A-Za-z0-9_-]/_}"' in script
        assert (
            'export DAYOA_RUNTIME_TMPDIR="${DAYOA_RUNTIME_TMPDIR:-/tmp/dayoa-conda-tmp-$runtime_tmp_name}"'
            in script
        )
        assert 'export TMPDIR="$DAYOA_RUNTIME_TMPDIR"' in script
        assert 'export TMP="$DAYOA_RUNTIME_TMPDIR"' in script
        assert 'export TEMP="$DAYOA_RUNTIME_TMPDIR"' in script
        assert 'export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$DAYOA_RUNTIME_TMPDIR/pip-cache}"' in script
        assert (
            'export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$DAYOA_RUNTIME_TMPDIR/xdg-cache}"' in script
        )
        assert (
            'export PIP_BUILD_TRACKER="${PIP_BUILD_TRACKER:-$DAYOA_RUNTIME_TMPDIR/pip-build-tracker}"'
            in script
        )
        _assert_immutable_pinned_dayoa_controller(script)
        assert 'repo_key = "daylily-omics-analysis"' in script
        assert "DAY_CONTAINERIZED=true" in script
        assert "DY_COMMAND='DAY_CONTAINERIZED=true" in script
        assert "--default-resources" not in script
        assert "shopt -s expand_aliases" in script
        assert "MERMAID_CHROME=" not in script
        assert "/.cache/puppeteer/chrome/" not in script
        assert 'export PUPPETEER_EXECUTABLE_PATH="$MERMAID_CHROME"' not in script
        assert 'run_dy_command "$DY_COMMAND"' in script
        assert script.index("shopt -s expand_aliases") < script.index(
            'run_dy_command "$DY_COMMAND"'
        )
        assert 'mkdir -p "$(dirname "$clone_root")"' in script
        assert 'mkdir -p "$clone_root"' in script
        assert script.index('mkdir -p "$clone_root"') < script.index("day-clone")
        assert "REPLACE_EXISTING_ANALYSIS_DIR=false" in script
        assert script.index("REPLACE_EXISTING_ANALYSIS_DIR=false") < script.index(
            'if [[ -e "$clone_root" ]]; then'
        )
        assert 'dayec_conda_profile="$HOME/miniconda3/etc/profile.d/conda.sh"' in script
        assert "conda activate DAY-EC" in script
        assert "python3 -c 'import yaml'" in script
        assert "ARTIFACT_RECOVERY_SHA256=" in script
        assert "config/dyec_analysis_recovery_source.json" in script
        assert "materialize_recovery_source" in script
        assert "Materialized exact recovery artifacts" in script
        assert script.index("conda activate DAY-EC") < script.index("day-clone")
        assert "day-clone" in script
        assert '--destination "$ANALYSIS_ID"' in script
        assert '--executing-entity "$EXECUTING_ENTITY"' in script
        assert '-u "$EXECUTING_ENTITY"' not in script
        assert "--repository daylily-omics-analysis" in script
        assert "--git-tag 12.0.5" in script
        assert "__DAYLILY_ERROR__=analysis_dir_exists" in script
        assert "__DAYLILY_REPLACED_ANALYSIS_DIR__=$clone_root" in script
        assert 'rm -rf -- "$clone_root"' in script
        assert 'if [[ ! -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then' in script
        assert '. "$HOME/miniconda3/etc/profile.d/conda.sh"' in script
        assert "PROJECT_VALUE=project-alpha" in script
        assert "COST_CENTER_VALUE=bjuice" in script
        assert "dyoa_args+=(--project project-alpha)" in script
        assert 'export PROJECT="$PROJECT_VALUE"' in script
        assert "apply_cost_center()" in script
        assert 'export DAY_PROJECT="$COST_CENTER_VALUE"' in script
        assert 'export DAYLILY_COST_CENTER="$COST_CENTER_VALUE"' in script
        assert script.index("apply_cost_center") < script.index('run_dy_command "$DY_COMMAND"')
        assert "dyoa_args+=(--skip-project-check)" in script
        assert "set +u" in script
        assert "set -u" in script
        assert "activate_status=$?" in script
        assert 'if [[ "$DEFAULT_ACTIVATION" == "true" ]]; then' in script
        assert "DEFAULT_ACTIVATION=true" in script
        assert "ANALYSIS_LOCK_MODE=true" in script
        assert "dyec analysis visit" in script
        assert "dyec analysis lock acquire" in script
        assert "dyec analysis lock release" in script
        assert script.index("dyec analysis lock acquire") < script.index("day-clone")
        assert 'echo "[ERROR] dy-a failed with status $activate_status"' in script
        assert "dy-a slurm hg38" in script
        assert "dy-r" in script
        assert 'local links_dir="$repo_path/config/run_dir_links"' in script
        assert "if ! remove_run_dir_projection_links; then" not in script
        assert '--mode export' not in script
        assert 'automatic $EXPORT_TRIGGER export' not in script
        assert '--s3-visit-uri "$EXPORT_DESTINATION_S3_URI"' not in script
        assert "env -u AWS_PROFILE -u AWS_DEFAULT_PROFILE dyec export" not in script
        assert "dyec export \\\n      --profile" not in script
        assert "DEWEY_" not in script
        assert "register-dewey" not in script
        assert 'if [[ ! -d "$clone_root" ]]; then' in script
        assert 'exit "$workflow_status"' in script
        assert "exec bash -il" in script
        assert '--which-one "$TRANSPORT"' not in script
        out = capsys.readouterr().out
        assert "Run state directory: /home/ubuntu/daylily-runs/sess-1" in out
        assert (
            "Workflow repo path: /fsx/analysis_results/johnm/analysis/daylily-omics-analysis" in out
        )
        assert 'Controller target: {"analysis_root": "/fsx/analysis_results/johnm/analysis"' in out
        assert (
            "daylily-ssh-into-headnode --profile dev --region us-west-2 --cluster cluster-a" in out
        )
        assert "Then run: tmux attach -t sess-1" in out
        assert "Slurm cost center: bjuice" in out

        mock_run_shell.reset_mock()
        rc = run_omics_module.main(
            [
                "--profile",
                "dev",
                "--git-tag",
                "12.0.5",
                "--input-contract",
                "sample_manifest",
                "--analysis-id",
                "analysis",
                "--executing-entity",
                "johnm",
                "--project",
                "project-alpha",
                "--replace-existing-analysis-dir",
                "--dry-run",
            ]
        )
        assert rc == 0
        replace_script = mock_run_shell.call_args.args[2]
        assert replace_script.index("REPLACE_EXISTING_ANALYSIS_DIR=true") < replace_script.index(
            'if [[ -e "$clone_root" ]]; then'
        )

        mock_run_shell.reset_mock()
        mock_discover.reset_mock()
        rc = run_omics_module.main(
            [
                "--profile",
                "dev",
                "--git-tag",
                "13.0.42",
                "--input-contract",
                "none",
                "--no-input-staging",
                "--analysis-id",
                "analysis",
                "--executing-entity",
                "johnm",
                "--session-name",
                "analysis-hiomr2-kitchensink",
                "--reuse-existing-analysis-dir",
                "--dy-command",
                "dy-r produce_sentdhiomr2_kitchensink -p -k -j 6",
            ]
        )
        assert rc == 0
        mock_discover.assert_not_called()
        continuation_script = mock_run_shell.call_args.args[2]
        continuation_outer_syntax = subprocess.run(
            ["bash", "-n"],
            input=continuation_script,
            text=True,
            capture_output=True,
            check=False,
        )
        assert continuation_outer_syntax.returncode == 0, continuation_outer_syntax.stderr
        continuation_pipeline = continuation_script.split(
            "cat <<'PAYLOAD' > \"$work_script\"\n", 1
        )[1].split("\nPAYLOAD\n", 1)[0]
        continuation_pipeline_syntax = subprocess.run(
            ["bash", "-n"],
            input=continuation_pipeline,
            text=True,
            capture_output=True,
            check=False,
        )
        assert (
            continuation_pipeline_syntax.returncode == 0
        ), continuation_pipeline_syntax.stderr
        assert "REUSE_EXISTING_ANALYSIS_DIR=true" in continuation_script
        assert "REPLACE_EXISTING_ANALYSIS_DIR=false" in continuation_script
        assert "__DAYLILY_REUSED_ANALYSIS_DIR__=$clone_root" in continuation_script
        assert "__DAYLILY_ERROR__=existing_analysis_ref_fetch_failed" in continuation_script
        assert (
            'day-clone --repository "$REPO_KEY" --git-tag "$DAYOA_GIT_REF" '
            '--fetch-existing "$repo_path"'
        ) in continuation_script
        assert "REPO_KEY=daylily-omics-analysis" in continuation_script
        assert 'git -C "$repo_path" rev-parse --verify "FETCH_HEAD^{commit}"' in continuation_script
        assert 'git -C "$repo_path" checkout --detach "$expected_commit"' in continuation_script
        assert continuation_script.index(
            'if [[ "$REUSE_EXISTING_ANALYSIS_DIR" == "true" ]]; then'
        ) < continuation_script.index(
            'elif [[ "$REPLACE_EXISTING_ANALYSIS_DIR" != "true" ]]; then'
        )

        mock_run_shell.reset_mock()
        rc = run_omics_module.main(
            [
                "--profile",
                "dev",
                "--git-tag",
                "13.0.42",
                "--input-contract",
                "none",
                "--no-input-staging",
                "--analysis-id",
                "analysis",
                "--executing-entity",
                "johnm",
                "--session-name",
                "analysis-hiomr2-kitchensink-local-ref",
                "--reuse-existing-analysis-dir",
                "--reuse-local-git-ref",
                "--reuse-local-git-commit",
                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "--dy-command",
                "dy-r produce_sentdhiomr2_kitchensink -p -k -j 6",
            ]
        )
        assert rc == 0
        local_ref_script = mock_run_shell.call_args.args[2]
        assert "REUSE_LOCAL_GIT_REF=true" in local_ref_script
        assert (
            "REUSE_LOCAL_GIT_COMMIT=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            in local_ref_script
        )
        assert '__DAYLILY_ERROR__=existing_analysis_local_commit_missing' in local_ref_script
        local_ref_branch = local_ref_script.split(
            'if [[ "$REUSE_LOCAL_GIT_REF" == "true" ]]; then',
            1,
        )[1].split("  else\n", 1)[0]
        assert (
            'git -C "$repo_path" rev-parse --verify '
            '"$REUSE_LOCAL_GIT_COMMIT^{commit}"'
        ) in local_ref_branch
        assert 'if [[ "$expected_commit" != "$REUSE_LOCAL_GIT_COMMIT" ]]; then' in local_ref_branch
        assert 'git -C "$repo_path" fetch --quiet --tags origin "$DAYOA_GIT_REF"' not in local_ref_branch

        mock_run_shell.reset_mock()
        rc = run_omics_module.main(
            [
                "--profile",
                "dev",
                "--git-tag",
                "13.0.42",
                "--input-contract",
                "none",
                "--no-input-staging",
                "--analysis-id",
                "analysis",
                "--executing-entity",
                "johnm",
                "--session-name",
                "analysis-pinned-source-test",
                "--reuse-existing-analysis-dir",
                "--reuse-local-git-ref",
                "--reuse-local-git-commit",
                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "--pinned-source-test-override",
                "approved dyoainit initialization test",
                "--dry-run",
                "--dy-command",
                "dy-r produce_sentdhiomr2_kitchensink -p -k -j 6 -n",
            ]
        )
        assert rc == 0
        override_script = mock_run_shell.call_args.args[2]
        assert "PINNED_SOURCE_TEST_OVERRIDE='approved dyoainit initialization test'" in override_script
        assert "DRY_RUN_MODE=true" in override_script
        assert '"$evidence_prefix.status.txt"' in override_script
        assert '"$evidence_prefix.worktree.patch"' in override_script
        assert '"$evidence_prefix.index.patch"' in override_script
        assert '"$evidence_prefix.untracked.txt"' in override_script
        override_reuse_block = override_script.split(
            'if [[ "$REUSE_EXISTING_ANALYSIS_DIR" == "true" ]]; then',
            1,
        )[1].split("else\n  if ! day-clone", 1)[0]
        assert '&& -z "$PINNED_SOURCE_TEST_OVERRIDE"' in override_reuse_block
        assert 'if [[ -n "$PINNED_SOURCE_TEST_OVERRIDE" ]]; then' in override_reuse_block
        assert 'actual_commit="$(git -C "$repo_path" rev-parse HEAD)"' in override_reuse_block

    def test_main_rejects_unsafe_existing_analysis_continuation(self):
        with pytest.raises(
            run_omics_module.CommandError,
            match="requires --reuse-existing-analysis-dir",
        ):
            run_omics_module.main(
                [
                    "--profile",
                    "dev",
                    "--git-tag",
                    "13.0.42",
                    "--analysis-id",
                    "analysis",
                    "--pinned-source-test-override",
                    "approved source test",
                    "--dry-run",
                ]
            )

        with pytest.raises(
            run_omics_module.CommandError,
            match="requires --input-contract none",
        ):
            run_omics_module.main(
                [
                    "--profile",
                    "dev",
                    "--git-tag",
                    "13.0.42",
                    "--analysis-id",
                    "analysis",
                    "--reuse-existing-analysis-dir",
                ]
            )

        with pytest.raises(
            run_omics_module.CommandError,
            match="requires --no-input-staging",
        ):
            run_omics_module.main(
                [
                    "--profile",
                    "dev",
                    "--git-tag",
                    "13.0.42",
                    "--analysis-id",
                    "analysis",
                    "--input-contract",
                    "none",
                    "--reuse-existing-analysis-dir",
                ]
            )

    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.run_shell",
        return_value=SimpleNamespace(
            stdout=(
                "__DAYLILY_SESSION__=run-qc\n"
                "__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/run-qc\n"
                "__DAYLILY_REPO_PATH__=/fsx/analysis_results/johnm/run-qc/daylily-omics-analysis\n"
                "__DAYLILY_DY_COMMAND__=bin/day_run help --produce-ursa-manifest true\n"
                + _controller_target_marker(
                    "run-qc",
                    "/fsx/analysis_results/johnm/run-qc/daylily-omics-analysis",
                )
                + "\n"
            ),
            stderr="",
        ),
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.discover_stage_config")
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.validate_headnode_readiness")
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.wait_for_ssm_online")
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_headnode_instance_id",
        return_value=HeadNodeTarget("cluster-a", "us-west-2", "i-abc123"),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_cluster",
        return_value="cluster-a",
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_region",
        return_value="us-west-2",
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.need_cmd")
    def test_main_launches_run_context_workflow(
        self,
        _mock_need_cmd,
        _mock_region,
        _mock_cluster,
        _mock_target,
        _mock_wait,
        mock_validate_headnode_readiness,
        mock_discover,
        mock_run_shell,
        tmp_path,
    ):
        events = []
        mock_validate_headnode_readiness.side_effect = lambda *args, **kwargs: events.append(
            "readiness"
        )
        tmux_result = mock_run_shell.return_value
        mock_run_shell.side_effect = lambda *args, **kwargs: events.append("tmux") or tmux_result
        run_context = tmp_path / "runs.tsv"
        run_context.write_text(
            "RUNID\tPLATFORM\tRUN_DIR\nRUN-1\tILMN\t/fsx/runs/RUN-1\n",
            encoding="utf-8",
        )

        rc = run_omics_module.main(
            [
                "--profile",
                "dev",
                "--git-tag",
                "13.0.0",
                "--analysis-id",
                "run-qc",
                "--executing-entity",
                "johnm",
                "--session-name",
                "run-qc",
                "--run-context-file",
                str(run_context),
                "--dy-command",
                "bin/day_run produce_illumina_run_qc --config "
                "run_context_file=config/runs.tsv "
                "samples_table=.test_data/data/samples.tsv "
                "units_table=.test_data/data/units.tsv",
            ]
        )

        assert rc == 0
        assert events == ["readiness", "tmux"]
        mock_discover.assert_not_called()
        script = mock_run_shell.call_args.args[2]
        assert "RUN_CONTEXT_MODE=true" in script
        assert "RUN-1" in script
        assert "printf '%s' \"$RUN_CONTEXT_PAYLOAD\" > config/runs.tsv" in script
        assert 'row["RUN_DIR"] = str(link_abs) + "/"' in script
        assert "materialize_runtime_table samples_table config/samples.tsv" in script
        assert "materialize_runtime_table units_table config/units.tsv" in script
        assert "[ERROR] Runtime config $key points to missing file: $source_path" in script
        assert "run_context_file=config/runs.tsv" in script

    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.run_shell",
        return_value=SimpleNamespace(
            stdout=(
                "__DAYLILY_SESSION__=sample-config\n"
                "__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/sample-config\n"
                "__DAYLILY_REPO_PATH__=/fsx/analysis_results/johnm/sample-config/daylily-omics-analysis\n"
                "__DAYLILY_DY_COMMAND__=bin/day_run help --produce-ursa-manifest true\n"
                + _controller_target_marker(
                    "sample-config",
                    "/fsx/analysis_results/johnm/sample-config/daylily-omics-analysis",
                )
                + "\n"
            ),
            stderr="",
        ),
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.discover_stage_config")
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.validate_headnode_readiness")
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.wait_for_ssm_online")
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_headnode_instance_id",
        return_value=HeadNodeTarget("cluster-a", "us-west-2", "i-abc123"),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_cluster",
        return_value="cluster-a",
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_region",
        return_value="us-west-2",
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.need_cmd")
    def test_main_launches_sample_config_workflow_without_stage_discovery(
        self,
        _mock_need_cmd,
        _mock_region,
        _mock_cluster,
        _mock_target,
        _mock_wait,
        mock_validate_headnode_readiness,
        mock_discover,
        mock_run_shell,
        tmp_path,
    ):
        events = []
        mock_validate_headnode_readiness.side_effect = lambda *args, **kwargs: events.append(
            "readiness"
        )
        tmux_result = mock_run_shell.return_value
        mock_run_shell.side_effect = lambda *args, **kwargs: events.append("tmux") or tmux_result
        samples_file = tmp_path / "samples.tsv"
        units_file = tmp_path / "units.tsv"
        samples_file.write_text("SAMPLEID\nHG003\n", encoding="utf-8")
        units_file.write_text("RUNID\tSAMPLEID\nRUN-1\tHG003\n", encoding="utf-8")

        rc = run_omics_module.main(
            [
                "--profile",
                "dev",
                "--git-tag",
                "12.0.5",
                "--input-contract",
                "sample_manifest",
                "--analysis-id",
                "sample-config",
                "--executing-entity",
                "johnm",
                "--session-name",
                "sample-config",
                "--samples-file",
                str(samples_file),
                "--units-file",
                str(units_file),
                "--dy-command",
                "bin/day_run produce_alignstats -p -k -j 1 -n",
            ]
        )

        assert rc == 0
        assert events == ["readiness", "tmux"]
        mock_discover.assert_not_called()
        script = mock_run_shell.call_args.args[2]
        assert "SAMPLE_CONFIG_MODE=true" in script
        assert "SAMPLEID" in script
        assert "RUN-1" in script
        assert "printf '%s' \"$SAMPLES_PAYLOAD\" > config/samples.tsv" in script
        assert "printf '%s' \"$UNITS_PAYLOAD\" > config/units.tsv" in script
        assert "RUN_CONTEXT_MODE=false" in script

    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.run_shell",
        return_value=SimpleNamespace(
            stdout=(
                "__DAYLILY_SESSION__=bcl-run\n"
                "__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/bcl-run\n"
                "__DAYLILY_REPO_PATH__=/fsx/analysis_results/johnm/bcl-run/daylily-omics-analysis\n"
                "__DAYLILY_DY_COMMAND__=bin/day_run help --produce-ursa-manifest true\n"
                + _controller_target_marker(
                    "bcl-run",
                    "/fsx/analysis_results/johnm/bcl-run/daylily-omics-analysis",
                )
                + "\n"
            ),
            stderr="",
        ),
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.discover_stage_config")
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.validate_headnode_readiness")
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.wait_for_ssm_online")
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_headnode_instance_id",
        return_value=HeadNodeTarget("cluster-a", "us-west-2", "i-abc123"),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_cluster",
        return_value="cluster-a",
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_region",
        return_value="us-west-2",
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.need_cmd")
    def test_main_generates_bclconvert_run_context_tables(
        self,
        _mock_need_cmd,
        _mock_region,
        _mock_cluster,
        _mock_target,
        _mock_wait,
        _mock_validate_headnode_readiness,
        mock_discover,
        mock_run_shell,
        tmp_path,
    ):
        run_context = tmp_path / "runs.tsv"
        run_context.write_text(
            "RUNID\tPLATFORM\tRUN_DIR\tSAMPLE_SHEET\n"
            "RUN-1\tILMN\t/fsx/runs/RUN-1\t/fsx/runs/RUN-1/SampleSheet.csv\n",
            encoding="utf-8",
        )

        rc = run_omics_module.main(
            [
                "--profile",
                "dev",
                "--git-tag",
                "13.0.0",
                "--analysis-id",
                "bcl-run",
                "--executing-entity",
                "johnm",
                "--session-name",
                "bcl-run",
                "--run-context-file",
                str(run_context),
                "--dy-command",
                "bin/day_run produce_bclconvert_fastqs_and_metrics "
                "--config run_context_file=config/runs.tsv bootstrap_bclconvert=true",
            ]
        )

        assert rc == 0
        mock_discover.assert_not_called()
        script = mock_run_shell.call_args.args[2]
        assert "bclconvert_runtime_tables_requested" in script
        assert "*produce_illumina_run_qc*|" not in script
        assert "*produce_illumina_run_qc_and_bclconvert*" in script
        assert "generate_bclconvert_runtime_tables" in script
        assert "project_run_context_mounts" in script
        assert "BCLConvert_Data" in script
        assert "SAMPLE_SHEET" in script
        assert 'raw_line.rstrip("\\r\\n")' in script
        assert 'lineterminator="\\n"' in script
        assert "units table left absent for DayOA bootstrap" in script
        assert "units_path.unlink()" in script
        assert "config/samples.tsv" in script
        assert "config/units.tsv" in script
        assert "bootstrap_bclconvert=true" in script
        _assert_immutable_pinned_dayoa_controller(script)

    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.run_shell",
        return_value=SimpleNamespace(
            stdout=(
                "__DAYLILY_SESSION__=ultima-run\n"
                "__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/ultima-run\n"
                "__DAYLILY_REPO_PATH__=/fsx/analysis_results/johnm/ultima-run/daylily-omics-analysis\n"
                "__DAYLILY_DY_COMMAND__=bin/day_run help --produce-ursa-manifest true\n"
                + _controller_target_marker(
                    "ultima-run",
                    "/fsx/analysis_results/johnm/ultima-run/daylily-omics-analysis",
                )
                + "\n"
            ),
            stderr="",
        ),
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.discover_stage_config")
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.validate_headnode_readiness")
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.wait_for_ssm_online")
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_headnode_instance_id",
        return_value=HeadNodeTarget("cluster-a", "us-west-2", "i-abc123"),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_cluster",
        return_value="cluster-a",
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_region",
        return_value="us-west-2",
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.need_cmd")
    def test_main_does_not_inject_ultima_run_qc_s3_config(
        self,
        _mock_need_cmd,
        _mock_region,
        _mock_cluster,
        _mock_target,
        _mock_wait,
        _mock_validate_headnode_readiness,
        mock_discover,
        mock_run_shell,
        tmp_path,
    ):
        run_context = tmp_path / "runs.tsv"
        run_context.write_text(
            "RUNID\tPLATFORM\tRUN_DIR\tSOURCE_S3_URI\tMETRICS_S3_URI\n"
            "RUN-1\tULTIMA\t/fsx/runs/RUN-1\ts3://bucket/run-1/\ts3://bucket/run-1/metrics.csv\n",
            encoding="utf-8",
        )

        rc = run_omics_module.main(
            [
                "--profile",
                "dev",
                "--git-tag",
                "13.0.0",
                "--analysis-id",
                "ultima-run",
                "--executing-entity",
                "johnm",
                "--session-name",
                "ultima-run",
                "--run-context-file",
                str(run_context),
                "--dy-command",
                "bin/day_run produce_ultima_run_qc --config run_context_file=config/runs.tsv",
            ]
        )

        assert rc == 0
        mock_discover.assert_not_called()
        script = mock_run_shell.call_args.args[2]
        assert "ultima_run_qc_config_requested" not in script
        assert "append_ultima_run_qc_config" not in script
        assert "Ultima run QC METRICS_S3_URI must" not in script
        assert "config/ultima_run_qc_metrics.csv" not in script

    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.run_shell",
        return_value=SimpleNamespace(
            stdout=(
                "__DAYLILY_SESSION__=ont-run\n"
                "__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/ont-run\n"
                "__DAYLILY_REPO_PATH__=/fsx/analysis_results/johnm/ont-run/daylily-omics-analysis\n"
                "__DAYLILY_DY_COMMAND__=bin/day_run help --produce-ursa-manifest true\n"
                + _controller_target_marker(
                    "ont-run",
                    "/fsx/analysis_results/johnm/ont-run/daylily-omics-analysis",
                )
                + "\n"
            ),
            stderr="",
        ),
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.discover_stage_config")
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.validate_headnode_readiness")
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.wait_for_ssm_online")
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_headnode_instance_id",
        return_value=HeadNodeTarget("cluster-a", "us-west-2", "i-abc123"),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_cluster",
        return_value="cluster-a",
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_region",
        return_value="us-west-2",
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.need_cmd")
    def test_main_keeps_ont_run_qc_checkout_immutable(
        self,
        _mock_need_cmd,
        _mock_region,
        _mock_cluster,
        _mock_target,
        _mock_wait,
        _mock_validate_headnode_readiness,
        mock_discover,
        mock_run_shell,
        tmp_path,
    ):
        run_context = tmp_path / "runs.tsv"
        run_context.write_text(
            "RUNID\tPLATFORM\tRUN_DIR\nRUN-1\tONT\t/fsx/runs/RUN-1\n",
            encoding="utf-8",
        )

        rc = run_omics_module.main(
            [
                "--profile",
                "dev",
                "--git-tag",
                "13.0.0",
                "--analysis-id",
                "ont-run",
                "--executing-entity",
                "johnm",
                "--session-name",
                "ont-run",
                "--run-context-file",
                str(run_context),
                "--dy-command",
                "bin/day_run produce_ont_run_qc --config run_context_file=config/runs.tsv",
            ]
        )

        assert rc == 0
        mock_discover.assert_not_called()
        script = mock_run_shell.call_args.args[2]
        _assert_immutable_pinned_dayoa_controller(script)

    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.run_shell",
        return_value=SimpleNamespace(
            stdout=(
                "__DAYLILY_SESSION__=alignstats-run\n"
                "__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/alignstats-run\n"
                "__DAYLILY_REPO_PATH__=/fsx/analysis_results/johnm/alignstats-run/daylily-omics-analysis\n"
                "__DAYLILY_DY_COMMAND__=bin/day_run help --produce-ursa-manifest true\n"
                + _controller_target_marker(
                    "alignstats-run",
                    "/fsx/analysis_results/johnm/alignstats-run/daylily-omics-analysis",
                )
                + "\n"
            ),
            stderr="",
        ),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.discover_stage_config",
        return_value=run_omics_module.RemoteConfig(
            stage_dir="/fsx/stage/run-1",
            samples_path="/fsx/stage/run-1/foo_samples.tsv",
            units_path="/fsx/stage/run-1/foo_units.tsv",
        ),
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.validate_headnode_readiness")
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.wait_for_ssm_online")
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_headnode_instance_id",
        return_value=HeadNodeTarget("cluster-a", "us-west-2", "i-abc123"),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_cluster",
        return_value="cluster-a",
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_region",
        return_value="us-west-2",
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.need_cmd")
    def test_main_keeps_alignstats_checkout_immutable(
        self,
        _mock_need_cmd,
        _mock_region,
        _mock_cluster,
        _mock_target,
        _mock_wait,
        _mock_validate_headnode_readiness,
        _mock_discover,
        mock_run_shell,
    ):
        rc = run_omics_module.main(
            [
                "--profile",
                "dev",
                "--git-tag",
                "12.0.5",
                "--input-contract",
                "sample_manifest",
                "--analysis-id",
                "alignstats-run",
                "--executing-entity",
                "johnm",
                "--session-name",
                "alignstats-run",
                "--dy-command",
                "bin/day_run produce_alignstats -p -k",
            ]
        )

        assert rc == 0
        script = mock_run_shell.call_args.args[2]
        _assert_immutable_pinned_dayoa_controller(script)

    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.run_shell",
        return_value=SimpleNamespace(
            stdout=(
                "__DAYLILY_SESSION__=snv-concordance-run\n"
                "__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/snv-concordance-run\n"
                "__DAYLILY_REPO_PATH__=/fsx/analysis_results/johnm/snv-concordance-run/daylily-omics-analysis\n"
                "__DAYLILY_DY_COMMAND__=bin/day_run help --produce-ursa-manifest true\n"
                + _controller_target_marker(
                    "snv-concordance-run",
                    "/fsx/analysis_results/johnm/snv-concordance-run/daylily-omics-analysis",
                )
                + "\n"
            ),
            stderr="",
        ),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.discover_stage_config",
        return_value=run_omics_module.RemoteConfig(
            stage_dir="/fsx/stage/run-1",
            samples_path="/fsx/stage/run-1/foo_samples.tsv",
            units_path="/fsx/stage/run-1/foo_units.tsv",
        ),
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.validate_headnode_readiness")
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.wait_for_ssm_online")
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_headnode_instance_id",
        return_value=HeadNodeTarget("cluster-a", "us-west-2", "i-abc123"),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_cluster",
        return_value="cluster-a",
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_region",
        return_value="us-west-2",
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.need_cmd")
    def test_main_keeps_snv_concordance_checkout_immutable(
        self,
        _mock_need_cmd,
        _mock_region,
        _mock_cluster,
        _mock_target,
        _mock_wait,
        _mock_validate_headnode_readiness,
        _mock_discover,
        mock_run_shell,
    ):
        rc = run_omics_module.main(
            [
                "--profile",
                "dev",
                "--git-tag",
                "12.0.5",
                "--input-contract",
                "sample_manifest",
                "--analysis-id",
                "snv-concordance-run",
                "--executing-entity",
                "johnm",
                "--session-name",
                "snv-concordance-run",
                "--dy-command",
                "bin/day_run produce_snv_concordances -p -k",
            ]
        )

        assert rc == 0
        script = mock_run_shell.call_args.args[2]
        _assert_immutable_pinned_dayoa_controller(script)

    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.run_shell",
        return_value=SimpleNamespace(
            stdout=(
                "__DAYLILY_SESSION__=kitchensink-run\n"
                "__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/kitchensink-run\n"
                "__DAYLILY_REPO_PATH__=/fsx/analysis_results/johnm/kitchensink-run/daylily-omics-analysis\n"
                "__DAYLILY_DY_COMMAND__=bin/day_run help --produce-ursa-manifest true\n"
                + _controller_target_marker(
                    "kitchensink-run",
                    "/fsx/analysis_results/johnm/kitchensink-run/daylily-omics-analysis",
                )
                + "\n"
            ),
            stderr="",
        ),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.discover_stage_config",
        return_value=run_omics_module.RemoteConfig(
            stage_dir="/fsx/stage/run-1",
            samples_path="/fsx/stage/run-1/foo_samples.tsv",
            units_path="/fsx/stage/run-1/foo_units.tsv",
        ),
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.validate_headnode_readiness")
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.wait_for_ssm_online")
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_headnode_instance_id",
        return_value=HeadNodeTarget("cluster-a", "us-west-2", "i-abc123"),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_cluster",
        return_value="cluster-a",
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_region",
        return_value="us-west-2",
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.need_cmd")
    def test_main_keeps_zero_variant_kitchensink_checkout_immutable(
        self,
        _mock_need_cmd,
        _mock_region,
        _mock_cluster,
        _mock_target,
        _mock_wait,
        _mock_validate_headnode_readiness,
        _mock_discover,
        mock_run_shell,
    ):
        rc = run_omics_module.main(
            [
                "--profile",
                "dev",
                "--git-tag",
                "12.0.5",
                "--input-contract",
                "sample_manifest",
                "--analysis-id",
                "kitchensink-run",
                "--executing-entity",
                "johnm",
                "--session-name",
                "kitchensink-run",
                "--dy-command",
                "bin/day_run produce_vep produce_global_contam_check produce_multiqc_all -p -k",
            ]
        )

        assert rc == 0
        script = mock_run_shell.call_args.args[2]
        _assert_immutable_pinned_dayoa_controller(script)

    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.run_shell",
        return_value=SimpleNamespace(
            stdout=(
                "__DAYLILY_SESSION__=simple-test\n"
                "__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/simple-test\n"
                "__DAYLILY_REPO_PATH__=/fsx/analysis_results/johnm/simple-test/daylily-omics-analysis\n"
                "__DAYLILY_DY_COMMAND__=bin/day_run help --produce-ursa-manifest true\n"
                + _controller_target_marker(
                    "simple-test",
                    "/fsx/analysis_results/johnm/simple-test/daylily-omics-analysis",
                )
                + "\n"
            ),
            stderr="",
        ),
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.discover_stage_config")
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.validate_headnode_readiness")
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.wait_for_ssm_online")
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_headnode_instance_id",
        return_value=HeadNodeTarget("cluster-a", "us-west-2", "i-abc123"),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_cluster",
        return_value="cluster-a",
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_region",
        return_value="us-west-2",
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.need_cmd")
    def test_main_launches_no_input_utility_workflow(
        self,
        _mock_need_cmd,
        _mock_region,
        _mock_cluster,
        _mock_target,
        _mock_wait,
        _mock_validate_headnode_readiness,
        mock_discover,
        mock_run_shell,
    ):
        rc = run_omics_module.main(
            [
                "--profile",
                "dev",
                "--git-tag",
                "13.0.0",
                "--analysis-id",
                "simple-test",
                "--executing-entity",
                "johnm",
                "--session-name",
                "simple-test",
                "--dy-command",
                "source dyoainit; dy-a local hg38; dy-r -p -k -j 1 help",
                "--no-input-staging",
                "--no-default-activation",
                "--bootstrap-test-config",
            ]
        )

        assert rc == 0
        mock_discover.assert_not_called()
        script = mock_run_shell.call_args.args[2]
        assert "INPUT_STAGING_MODE=false" in script
        assert "DEFAULT_ACTIVATION=false" in script
        assert "BOOTSTRAP_TEST_CONFIG=true" in script
        assert "bootstrap_test_config()" in script
        assert "[INFO] Bootstrapped DayOA test samples and units tables." in script
        assert 'cp "$STAGE_SAMPLES" config/samples.tsv' in script
        assert "DY_COMMAND='source dyoainit; dy-a local hg38; dy-r -p -k -j 1 help" in script
        assert "--default-resources" not in script
        assert 'if [[ "$command" == source\\ dyoainit\\;* ]]; then' in script
        assert "set --" in script
        assert "source dyoainit" in script
        assert "local command_status=$?" in script
        assert 'run_dy_command "$DY_COMMAND"' in script
        assert 'if [[ "$DEFAULT_ACTIVATION" == "true" ]]; then' in script
        assert "SESSION_START_DEADLINE=$((SECONDS + 60))" in script
        assert "session_ready=false" in script
        assert 'tmux_session_name="${SESSION_NAME//[^A-Za-z0-9_-]/_}"' in script
        assert 'tmux new-session -d -s "$tmux_session_name"' in script
        assert 'tmux_pane_target="$tmux_session_name:0.0"' in script
        assert 'tmux send-keys -t "$tmux_pane_target" "$tmux_command" C-m' in script
        assert 'preserving tmux shell for inspection' in script
        assert 'if tmux has-session -t "=$tmux_session_name"' in script
        assert "__DAYLILY_COMPLETED_QUICKLY__=$quick_status" in script
        assert "__DAYLILY_TMUX_SESSION__=$tmux_session_name" in script
        assert "__DAYLILY_ERROR__=session_start_timeout" in script

    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.run_shell",
        return_value=SimpleNamespace(stdout="", stderr=""),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.discover_stage_config",
        return_value=run_omics_module.RemoteConfig(
            stage_dir="/fsx/stage/run-1",
            samples_path="/fsx/stage/run-1/foo_samples.tsv",
            units_path="/fsx/stage/run-1/foo_units.tsv",
        ),
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.validate_headnode_readiness")
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.wait_for_ssm_online")
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_headnode_instance_id",
        return_value=HeadNodeTarget("cluster-a", "us-west-2", "i-abc123"),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_cluster",
        return_value="cluster-a",
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.resolve_region",
        return_value="us-west-2",
    )
    @patch("daylily_ec.scripts.daylily_run_omics_analysis_headnode.need_cmd")
    def test_main_raises_when_tmux_session_not_reported(
        self,
        _mock_need_cmd,
        _mock_region,
        _mock_cluster,
        _mock_target,
        _mock_wait,
        _mock_validate_headnode_readiness,
        _mock_discover,
        _mock_run_shell,
    ):
        with pytest.raises(CommandError, match="did not report success"):
            run_omics_module.main(
                [
                    "--profile",
                    "dev",
                    "--git-tag",
                    "12.0.5",
                    "--input-contract",
                    "sample_manifest",
                    "--analysis-id",
                    "analysis",
                    "--executing-entity",
                    "johnm",
                ]
            )


class TestCfgHeadnodeScript:
    def test_load_repo_overrides_parses_file(self, tmp_path):
        override_file = tmp_path / "repos.txt"
        override_file.write_text(
            "# comment\ndaylily-omics-analysis:release-1\ninvalid-line\nrna-seq-star-deseq2:main\n",
            encoding="utf-8",
        )

        assert _load_repo_overrides(str(override_file)) == {
            "daylily-omics-analysis": "release-1",
            "rna-seq-star-deseq2": "main",
        }

    def test_load_repo_overrides_missing_file_raises(self):
        with pytest.raises(CommandError, match="Repository overrides file not found"):
            _load_repo_overrides("/no/such/file")

    @patch("daylily_ec.scripts.daylily_cfg_headnode.configure_headnode", return_value=True)
    @patch(
        "daylily_ec.scripts.daylily_cfg_headnode.resolve_configured_headnode_repo_spec",
        return_value=SimpleNamespace(
            url="https://github.com/lsmc-bio/daylily-ephemeral-cluster.git",
            ref="16.1.85",
        ),
    )
    @patch("daylily_ec.scripts.daylily_cfg_headnode.wait_for_ssm_online")
    @patch(
        "daylily_ec.scripts.daylily_cfg_headnode.resolve_headnode_instance_id",
        return_value=HeadNodeTarget("cluster-a", "us-west-2", "i-abc123"),
    )
    @patch("daylily_ec.scripts.daylily_cfg_headnode.resolve_cluster", return_value="cluster-a")
    @patch("daylily_ec.scripts.daylily_cfg_headnode.resolve_region", return_value="us-west-2")
    @patch("daylily_ec.scripts.daylily_cfg_headnode.need_cmd")
    def test_main_configures_headnode(
        self,
        _mock_need_cmd,
        _mock_region,
        _mock_cluster,
        _mock_target,
        _mock_wait,
        _mock_repo_spec,
        mock_configure,
        tmp_path,
        capsys,
    ):
        override_file = tmp_path / "repos.txt"
        override_file.write_text("daylily-omics-analysis:release-1\n", encoding="utf-8")

        rc = cfg_headnode_module.main(
            [
                "--profile",
                "dev",
                "--repo-overrides",
                str(override_file),
                "--dyec-deploy-key-secret-arn",
                "arn:aws:secretsmanager:us-west-2:123456789012:secret:dyec-key",
                "--dayoa-deploy-key-secret-arn",
                "arn:aws:secretsmanager:us-west-2:123456789012:secret:dayoa-key",
            ]
        )

        assert rc == 0
        mock_configure.assert_called_once_with(
            cluster_name="cluster-a",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="dev",
            dyec_deploy_key_secret_arn="arn:aws:secretsmanager:us-west-2:123456789012:secret:dyec-key",
            dyec_deploy_key_region="us-west-2",
            dyec_repo_url="https://github.com/lsmc-bio/daylily-ephemeral-cluster.git",
            dyec_repo_ref="16.1.85",
            dayoa_deploy_key_secret_arn="arn:aws:secretsmanager:us-west-2:123456789012:secret:dayoa-key",
            dayoa_deploy_key_region="us-west-2",
            repo_overrides={"daylily-omics-analysis": "release-1"},
        )
        assert "Headnode configured via SSM" in capsys.readouterr().out

    def test_parser_does_not_offer_a_dyec_version_override(self):
        with pytest.raises(SystemExit):
            cfg_headnode_module.build_parser().parse_args(["--dyec-version", "16.1.84"])

    def test_parser_requires_both_deploy_key_references(self):
        parser = cfg_headnode_module.build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--profile", "dev"])
        with pytest.raises(SystemExit):
            parser.parse_args(
                [
                    "--profile",
                    "dev",
                    "--dyec-deploy-key-secret-arn",
                    "arn:aws:secretsmanager:us-west-2:123456789012:secret:dyec-key",
                ]
            )

    def test_main_rejects_blank_deploy_key_reference_before_tools(self, monkeypatch):
        monkeypatch.setattr(
            cfg_headnode_module,
            "need_cmd",
            lambda *_args, **_kwargs: pytest.fail("blank key must fail before tool checks"),
        )

        with pytest.raises(CommandError, match="--dyec-deploy-key-secret-arn must be non-empty"):
            cfg_headnode_module.main(
                [
                    "--profile",
                    "dev",
                    "--dyec-deploy-key-secret-arn",
                    " ",
                    "--dayoa-deploy-key-secret-arn",
                    "arn:aws:secretsmanager:us-west-2:123456789012:secret:dayoa-key",
                ]
            )

    @patch("daylily_ec.scripts.daylily_cfg_headnode.configure_headnode", return_value=False)
    @patch(
        "daylily_ec.scripts.daylily_cfg_headnode.resolve_configured_headnode_repo_spec",
        return_value=SimpleNamespace(
            url="https://github.com/lsmc-bio/daylily-ephemeral-cluster.git",
            ref="16.1.85",
        ),
    )
    @patch("daylily_ec.scripts.daylily_cfg_headnode.wait_for_ssm_online")
    @patch(
        "daylily_ec.scripts.daylily_cfg_headnode.resolve_headnode_instance_id",
        return_value=HeadNodeTarget("cluster-a", "us-west-2", "i-abc123"),
    )
    @patch("daylily_ec.scripts.daylily_cfg_headnode.resolve_cluster", return_value="cluster-a")
    @patch("daylily_ec.scripts.daylily_cfg_headnode.resolve_region", return_value="us-west-2")
    @patch("daylily_ec.scripts.daylily_cfg_headnode.need_cmd")
    def test_main_raises_when_configuration_fails(
        self,
        _mock_need_cmd,
        _mock_region,
        _mock_cluster,
        _mock_target,
        _mock_wait,
        _mock_repo_spec,
        _mock_configure,
    ):
        with pytest.raises(CommandError, match="Headnode configuration failed"):
            cfg_headnode_module.main(
                [
                    "--profile",
                    "dev",
                    "--dyec-deploy-key-secret-arn",
                    "arn:aws:secretsmanager:us-west-2:123456789012:secret:dyec-key",
                    "--dayoa-deploy-key-secret-arn",
                    "arn:aws:secretsmanager:us-west-2:123456789012:secret:dayoa-key",
                ]
            )


class TestRemoteTestsScript:
    def test_load_default_repo_reads_registry(self, tmp_path):
        registry = tmp_path / "repos.yaml"
        registry.write_text(
            "default_repository: test-repo\n"
            "repositories:\n"
            "  test-repo:\n"
            "    https_url: https://example.com/test.git\n"
            "    default_ref: release-1\n",
            encoding="utf-8",
        )

        with patch(
            "daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests.resource_path",
            return_value=registry,
        ):
            assert remote_tests_module._load_default_repo() == (
                "test-repo",
                "release-1",
            )

    def test_main_rejects_conflicting_flags(self):
        with pytest.raises(CommandError, match="Choose at most one"):
            remote_tests_module.main(["--profile", "dev", "--yes", "--no-launch"])

    @patch("daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests.wait_for_ssm_online")
    @patch(
        "daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests.resolve_headnode_instance_id",
        return_value=HeadNodeTarget("cluster-a", "us-west-2", "i-abc123"),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests.resolve_cluster",
        return_value="cluster-a",
    )
    @patch(
        "daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests.resolve_region",
        return_value="us-west-2",
    )
    @patch("daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests.need_cmd")
    def test_main_no_launch_prints_connect_command(
        self,
        _mock_need_cmd,
        _mock_region,
        _mock_cluster,
        _mock_target,
        _mock_wait,
        capsys,
    ):
        rc = remote_tests_module.main(["--profile", "dev", "--no-launch"])

        assert rc == 0
        assert (
            "daylily-ssh-into-headnode --profile dev --region us-west-2 --cluster cluster-a"
            in capsys.readouterr().out
        )

    @patch(
        "daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests.run_shell",
        return_value=SimpleNamespace(stdout="__DAYLILY_SESSION__=sess-2\n"),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests._load_default_repo",
        return_value=("test-repo", "release-1"),
    )
    @patch("daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests.wait_for_ssm_online")
    @patch(
        "daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests.resolve_headnode_instance_id",
        return_value=HeadNodeTarget("cluster-a", "us-west-2", "i-abc123"),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests.resolve_cluster",
        return_value="cluster-a",
    )
    @patch(
        "daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests.resolve_region",
        return_value="us-west-2",
    )
    @patch("daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests.need_cmd")
    def test_main_launches_remote_test_workflow(
        self,
        _mock_need_cmd,
        _mock_region,
        _mock_cluster,
        _mock_target,
        _mock_wait,
        _mock_load_repo,
        mock_run_shell,
        capsys,
    ):
        rc = remote_tests_module.main(["--profile", "dev"])

        assert rc == 0
        script = mock_run_shell.call_args.args[2]
        assert "tmux new-session" in script
        assert "day-clone --repository test-repo" in script
        assert "--git-tag release-1" in script
        assert "--executing-entity ubuntu" in script
        assert "git clone" not in script
        out = capsys.readouterr().out
        assert "Tmux session 'sess-2' created" in out
        assert "Then run: tmux attach -t sess-2" in out

    @patch(
        "daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests.run_shell",
        return_value=SimpleNamespace(stdout=""),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests._load_default_repo",
        return_value=("test-repo", "release-1"),
    )
    @patch("daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests.wait_for_ssm_online")
    @patch(
        "daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests.resolve_headnode_instance_id",
        return_value=HeadNodeTarget("cluster-a", "us-west-2", "i-abc123"),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests.resolve_cluster",
        return_value="cluster-a",
    )
    @patch(
        "daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests.resolve_region",
        return_value="us-west-2",
    )
    @patch("daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests.need_cmd")
    def test_main_raises_when_session_not_reported(
        self,
        _mock_need_cmd,
        _mock_region,
        _mock_cluster,
        _mock_target,
        _mock_wait,
        _mock_load_repo,
        _mock_run_shell,
    ):
        with pytest.raises(CommandError, match="did not report a tmux session name"):
            remote_tests_module.main(["--profile", "dev"])
