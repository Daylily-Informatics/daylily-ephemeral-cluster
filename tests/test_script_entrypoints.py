from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml

from daylily_ec.aws.ssm import HeadNodeTarget, SsmError
from daylily_ec.scripts.common import CommandError
from daylily_ec.scripts.daylily_cfg_headnode import _load_repo_overrides
import daylily_ec.scripts.daylily_cfg_headnode as cfg_headnode_module
import daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests as remote_tests_module
import daylily_ec.scripts.daylily_run_omics_analysis_headnode as run_omics_module
import daylily_ec.scripts.daylily_ssh_into_headnode as ssh_headnode_module


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
    def test_bclconvert_profile_patch_inserts_yaml_keys_at_existing_child_indent(self, tmp_path, monkeypatch):
        run_dir = tmp_path / "run-dir"
        run_dir.mkdir()
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "runs.tsv").write_text(
            "RUNID\tPLATFORM\tRUN_DIR\n"
            f"RUN-1\tILMN\t{run_dir}\n",
            encoding="utf-8",
        )
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()
        rule_config = profile_dir / "rule_config.yaml"
        rule_config.write_text(
            "\n".join(
                [
                    "other:",
                    "  value: true",
                    "bclconvert:",
                    "  run_dir: ''",
                    "  force: 'false'",
                    "  threads: '1'",
                    "  partition: i1",
                    "  parallel_tiles: '1'",
                    "  conversion_threads: '1'",
                    "  compression_threads: '1'",
                    "  decompression_threads: '1'",
                    "  fastq_gzip_compression_level: '4'",
                    "  tmpdir: /tmp",
                    "next:",
                    "  value: true",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("DAY_PROFILE_DIR", str(profile_dir))

        exec(run_omics_module.BCLCONVERT_PROFILE_PATCH_SCRIPT, {})

        text = rule_config.read_text(encoding="utf-8")
        parsed = yaml.safe_load(text)
        assert parsed["bclconvert"]["adapter_read1"] == ""
        assert parsed["bclconvert"]["sample_sheet_settings"] == "{}"
        assert parsed["bclconvert"]["barcode_mismatches_index1"] == "0"
        assert "\n  adapter_read1:" in text
        assert "\n    adapter_read1:" not in text

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
                ]
            )
            + "\n"
        )

        assert launch.session_name == "sess-1"
        assert launch.run_dir == "/home/ubuntu/daylily-runs/sess-1"
        assert launch.repo_path.endswith("/daylily-omics-analysis")

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
        assert "bin/day_run" in command
        assert "aligners=['bwa2a','strobe']" in command
        assert "sv_callers=['tiddit']" in command
        assert "-j 8" in command
        assert "-n" in command
        assert "--rerun-incomplete" in command

    def test_main_rejects_dewey_options_without_artifact_registration(self):
        with pytest.raises(CommandError, match="artifact-registration-command-id"):
            run_omics_module.main(
                [
                    "--region",
                    "us-west-2",
                    "--profile",
                    "dev",
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
                "--analysis-id",
                "analysis",
                "--executing-entity",
                "johnm",
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
        )
        script = mock_run_shell.call_args.args[2]
        assert 'run_dir="/home/ubuntu/daylily-runs/$SESSION_NAME"' in script
        assert 'work_script="$run_dir/launch.sh"' in script
        assert 'tmux_log="$run_dir/tmux.log"' in script
        assert 'STATUS_FILE="${DAYLILY_RUN_DIR}/status.json"' in script
        assert "python3 -c " in script
        assert "nohup tmux new-session" in script
        assert '-e "DAYLILY_RUN_DIR=$run_dir"' in script
        assert '-e "DAYLILY_REPO_PATH=$repo_path"' in script
        assert '-e "DAYLILY_TMUX_LOG=$tmux_log"' in script
        assert 'tmux_session_name="${SESSION_NAME//[^A-Za-z0-9_-]/_}"' in script
        assert 'tmux has-session -t "=$tmux_session_name"' in script
        assert 'repo_key = "daylily-omics-analysis"' in script
        assert "DAY_CONTAINERIZED=true" in script
        assert "DY_COMMAND='DAY_CONTAINERIZED=true" in script
        assert "--default-resources" not in script
        assert "shopt -s expand_aliases" in script
        assert (
            'MERMAID_CHROME="$HOME/.cache/puppeteer/chrome/linux-148.0.7778.97/chrome-linux64/chrome"'
            in script
        )
        assert 'export PUPPETEER_EXECUTABLE_PATH="$MERMAID_CHROME"' in script
        assert 'run_dy_command "$DY_COMMAND"' in script
        assert script.index("shopt -s expand_aliases") < script.index(
            'run_dy_command "$DY_COMMAND"'
        )
        assert 'mkdir -p "$(dirname "$clone_root")"' in script
        assert 'mkdir -p "$clone_root"' not in script
        assert "REPLACE_EXISTING_ANALYSIS_DIR=false" in script
        assert "day-clone" in script
        assert '--destination "$ANALYSIS_ID"' in script
        assert '--executing-entity "$EXECUTING_ENTITY"' in script
        assert '-u "$EXECUTING_ENTITY"' not in script
        assert "--repository daylily-omics-analysis" in script
        assert "--git-tag main" in script
        assert "__DAYLILY_ERROR__=analysis_dir_exists" in script
        assert "__DAYLILY_REPLACED_ANALYSIS_DIR__=$clone_root" in script
        assert 'rm -rf -- "$clone_root"' in script
        assert 'if [[ ! -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then' in script
        assert '. "$HOME/miniconda3/etc/profile.d/conda.sh"' in script
        assert "unset PROJECT || true" in script
        assert "dyoa_args+=(--skip-project-check)" in script
        assert "set +u" in script
        assert "set -u" in script
        assert "activate_status=$?" in script
        assert 'if [[ "$DEFAULT_ACTIVATION" == "true" ]]; then' in script
        assert "DEFAULT_ACTIVATION=true" in script
        assert 'echo "[ERROR] day_activate failed with status $activate_status"' in script
        assert ". bin/day_activate slurm hg38 remote" in script
        assert "bin/day_run" in script
        assert 'local links_dir="$repo_path/config/run_dir_links"' in script
        assert 'if ! remove_run_dir_projection_links; then' in script
        assert script.index("remove_run_dir_projection_links") < script.index(
            "env -u AWS_PROFILE -u AWS_DEFAULT_PROFILE dyec export"
        )
        assert "env -u AWS_PROFILE -u AWS_DEFAULT_PROFILE dyec export" in script
        assert "dyec export \\\n      --profile" not in script
        assert "DEWEY_ANALYSIS_DIR_EXTERNAL_OBJECT_ID=" in script
        assert "registration_args+=(--dewey-analysis-dir-external-object-id" in script
        assert "registration_args+=(--dewey-run-artifact-euid" in script
        assert "registration_args+=(--dewey-ursa-analysis-euid" in script
        assert 'if [[ ! -d "$clone_root" ]]; then' in script
        assert 'exit "$workflow_status"' in script
        assert "exec bash -il" in script
        assert '--which-one "$TRANSPORT"' not in script
        out = capsys.readouterr().out
        assert "Run state directory: /home/ubuntu/daylily-runs/sess-1" in out
        assert (
            "Workflow repo path: /fsx/analysis_results/johnm/analysis/daylily-omics-analysis" in out
        )
        assert (
            "daylily-ssh-into-headnode --profile dev --region us-west-2 --cluster cluster-a" in out
        )
        assert "Then run: tmux attach -t sess-1" in out

    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.run_shell",
        return_value=SimpleNamespace(
            stdout=(
                "__DAYLILY_SESSION__=run-qc\n"
                "__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/run-qc\n"
                "__DAYLILY_REPO_PATH__=/fsx/analysis_results/johnm/run-qc/daylily-omics-analysis\n"
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
        assert "generate_bclconvert_runtime_tables" in script
        assert "project_run_context_mounts" in script
        assert "patch_bclconvert_profile_config" in script
        assert "patch_bclconvert_lane_split" in script
        assert 'replace_required_scalar("tmpdir", "/dev/shm")' in script
        assert 'replace_required_scalar("force", "true")' in script
        assert 'upsert_scalar("merge_lane_fastqs", "false")' in script
        assert 'upsert_scalar("merge_tile_fastqs", "false")' in script
        assert 'replace_required_scalar("partition", "i192hugenvme")' in script
        assert 'replace_required_scalar("parallel_tiles", "24")' in script
        assert 'replace_required_scalar("conversion_threads", "4")' in script
        assert 'replace_required_scalar("compression_threads", "64")' in script
        assert 'replace_required_scalar("decompression_threads", "32")' in script
        assert 'upsert_scalar("shared_thread_odirect_output", "false")' in script
        assert 'upsert_scalar("num_unknown_barcodes_reported", "1000")' in script
        assert 'upsert_scalar("output_legacy_stats", "true")' in script
        assert 'upsert_scalar("barcode_mismatches_index1", "0")' in script
        assert 'upsert_scalar("barcode_mismatches_index2", "0")' in script
        assert 'upsert_scalar("sample_sheet_settings", "{}")' in script
        assert "DAYOA_BCLCONVERT_LANE_SPLIT = True" in script
        assert "BCL_MERGE_LANE_FASTQS" in script
        assert "BCL_FASTQ_LIST_INPUT_FILES" in script
        assert "run_bclconvert_lane_fastqs_ready" in script
        assert "rule run_bclconvert_lane:" in script
        assert "workflow/scripts/run_bclconvert_lane.sh" in script
        assert "workflow/scripts/prepare_bclconvert_lane_samplesheet.py" in script
        assert "workflow/scripts/merge_bclconvert_lanes.py" in script
        assert "DayOA native BCL Convert lane-split rules detected" in script
        assert "do not expose native lane-split support" in script
        assert "dyec_run_bclconvert_lane.sh" not in script
        assert "gzip.decompress" not in script
        assert "base64.b64decode" not in script
        assert "Untested pending feature" in script
        assert "BCLCONVERT_PROFILE_PATCH_REQUESTED=true" in script
        assert "BCLConvert_Data" in script
        assert "SAMPLE_SHEET" in script
        assert 'raw_line.rstrip("\\r\\n")' in script
        assert 'lineterminator="\\n"' in script
        assert "units table left absent for DayOA bootstrap" in script
        assert "units_path.unlink()" in script
        assert "config/samples.tsv" in script
        assert "config/units.tsv" in script
        assert "bootstrap_bclconvert=true" in script

    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.run_shell",
        return_value=SimpleNamespace(
            stdout=(
                "__DAYLILY_SESSION__=ultima-run\n"
                "__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/ultima-run\n"
                "__DAYLILY_REPO_PATH__=/fsx/analysis_results/johnm/ultima-run/daylily-omics-analysis\n"
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
    def test_main_injects_ultima_run_qc_s3_config(
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
        assert "ultima_run_qc_config_requested" in script
        assert "append_ultima_run_qc_config" in script
        assert "SOURCE_S3_URI" in script
        assert "METRICS_PATH" in script
        assert "METRICS_S3_URI" in script
        assert "config/ultima_run_qc_metrics.csv" in script
        assert '"run_s3_uri": source_s3_uri' in script
        assert '"metrics_path": metrics_path' in script
        assert 'DY_COMMAND="$DY_COMMAND --config $extra_config"' in script

    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.run_shell",
        return_value=SimpleNamespace(
            stdout=(
                "__DAYLILY_SESSION__=ont-run\n"
                "__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/ont-run\n"
                "__DAYLILY_REPO_PATH__=/fsx/analysis_results/johnm/ont-run/daylily-omics-analysis\n"
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
    def test_main_repairs_ont_run_qc_pycoqc_runtime(
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
        assert "ont_run_qc_runtime_repair_requested" in script
        assert "patch_pycoqc_readonly_sort" in script
        assert "data = data.dropna().values" in script
        assert 'data = data.dropna().astype("int64").to_numpy(copy=True)' in script
        assert "cum_sum += int(v)" in script
        assert "return 0" in script
        assert "\nPYPYCOQC\n" in script
        assert "if ont_run_qc_runtime_repair_requested; then" in script
        assert "pycoQC readonly-sort repair target not found" in script

    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.run_shell",
        return_value=SimpleNamespace(
            stdout=(
                "__DAYLILY_SESSION__=alignstats-run\n"
                "__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/alignstats-run\n"
                "__DAYLILY_REPO_PATH__=/fsx/analysis_results/johnm/alignstats-run/daylily-omics-analysis\n"
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
    def test_main_repairs_goleft_empty_sex_arg_runtime(
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
        assert "goleft_indexcov_runtime_repair_requested" in script
        assert "patch_goleft_indexcov_empty_sex_arg" in script
        assert "goleft indexcov --directory $gl --sex {params.sexchrms:q}" in script
        assert "goleft indexcov --directory $gl " in script
        assert "goleft_status=$?" in script
        assert "goleft empty-sex guard already native in DayOA" in script
        assert 'goleft indexcov --directory $gl "${{sex_args[@]}}"' in script
        assert "no usable chroms?omes|no usable chromosomes" in script
        assert "--fai {params.huref}.fai {input.crai}" in script
        assert "\nPYGOLEFT\n" in script
        assert "if goleft_indexcov_runtime_repair_requested; then" in script
        assert "goleft runtime repair target not found" in script
        assert "mosdepth_empty_output_runtime_repair_requested" in script
        assert "patch_mosdepth_empty_outputs" in script
        assert "mosdepth emitted no global distribution" in script
        assert "if mosdepth_empty_output_runtime_repair_requested; then" in script

    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.run_shell",
        return_value=SimpleNamespace(
            stdout=(
                "__DAYLILY_SESSION__=snv-concordance-run\n"
                "__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/snv-concordance-run\n"
                "__DAYLILY_REPO_PATH__=/fsx/analysis_results/johnm/snv-concordance-run/daylily-omics-analysis\n"
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
    def test_main_repairs_rtg_vcfeval_parse_output_dir_runtime(
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
        assert "rtg_vcfeval_parse_runtime_repair_requested" in script
        assert "patch_rtg_vcfeval_parse_output_dir" in script
        assert "if rtg_vcfeval_parse_runtime_repair_requested; then" in script
        assert 'mkdir -p "$(dirname {output.mqc})"' in script
        assert 'rtg_mem_gb=$(( ({resources.mem_mb} * 85 / 100 + 1023) / 1024 ))' in script
        assert 'RTG_MEM="${{rtg_mem_gb}}G" rtg vcfeval' in script

    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.run_shell",
        return_value=SimpleNamespace(
            stdout=(
                "__DAYLILY_SESSION__=kitchensink-run\n"
                "__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/kitchensink-run\n"
                "__DAYLILY_REPO_PATH__=/fsx/analysis_results/johnm/kitchensink-run/daylily-omics-analysis\n"
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
    def test_main_repairs_zero_variant_vep_and_contam_identity_runtime(
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
        assert "vep_zero_variant_runtime_repair_requested" in script
        assert "patch_vep_empty_concat_fofn" in script
        assert 'echo "${{count_path%.record_count}}"' in script
        assert "contam_identity_zero_variant_runtime_repair_requested" in script
        assert "patch_contam_identity_zero_variant_outputs" in script
        assert (
            "NO_VARIANTS: haplocheck skipped because the input VCF has no variant records."
            in script
        )
        assert (
            "UNSUPPORTED_REFERENCE: haplocheck skipped because the input VCF is not restricted to rCRS positions."
            in script
        )
        assert "if grep -q 'outside the range.*rCRS only' {log:q}; then" in script
        assert 'elif [[ "$haplocheck_rc" -eq 0 ]]; then' in script
        assert (
            "NO_VARIANTS: read_haps skipped because the input VCF has no variant records." in script
        )
        assert (
            "READ_HAPS_FAILED: read_haps exited with status %s or wrote no usable QC table."
            in script
        )
        assert "READ_HAPS_UNAVAILABLE: read_haps command is unavailable" in script
        assert "READ_HAPS_MARKERS_UNAVAILABLE" in script
        assert 'if [[ \\"$read_haps_rc\\" != \\"0\\" ]]' in script
        assert '\\"$read_haps_rc\\" >> {log:q}' in script
        assert "read_haps_empty_failure_old" in script
        assert "read_haps_strict_precheck_old" in script
        assert "if ! command -v {params.command:q} > /dev/null; then" in script
        assert "elif [[ ! -s {params.reliable_snp_file:q} ]]; then" in script
        assert "hybrid_ultima_ont_stage1_runtime_repair_requested" not in script
        assert "patch_hybrid_ultima_ont_stage1_assertion" not in script
        assert "ReadSequenceKmerGraphBuilder.*kmerSize >= 1" not in script
        assert "if vep_zero_variant_runtime_repair_requested; then" in script
        assert "if contam_identity_zero_variant_runtime_repair_requested; then" in script
        assert "if hybrid_ultima_ont_stage1_runtime_repair_requested; then" not in script

    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.run_shell",
        return_value=SimpleNamespace(
            stdout=(
                "__DAYLILY_SESSION__=simple-test\n"
                "__DAYLILY_RUN_DIR__=/home/ubuntu/daylily-runs/simple-test\n"
                "__DAYLILY_REPO_PATH__=/fsx/analysis_results/johnm/simple-test/daylily-omics-analysis\n"
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
        assert 'nohup tmux new-session -d -s "$tmux_session_name"' in script
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
        mock_configure,
        tmp_path,
        capsys,
    ):
        override_file = tmp_path / "repos.txt"
        override_file.write_text("daylily-omics-analysis:release-1\n", encoding="utf-8")

        rc = cfg_headnode_module.main(["--profile", "dev", "--repo-overrides", str(override_file)])

        assert rc == 0
        mock_configure.assert_called_once_with(
            cluster_name="cluster-a",
            head_node_instance_id="i-abc123",
            region="us-west-2",
            profile="dev",
            repo_overrides={"daylily-omics-analysis": "release-1"},
        )
        assert "Headnode configured via SSM" in capsys.readouterr().out

    @patch("daylily_ec.scripts.daylily_cfg_headnode.configure_headnode", return_value=False)
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
        _mock_configure,
    ):
        with pytest.raises(CommandError, match="Headnode configuration failed"):
            cfg_headnode_module.main(["--profile", "dev"])


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
                "https://example.com/test.git",
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
        return_value=("https://example.com/test.git", "release-1"),
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
        assert "git clone -b release-1 https://example.com/test.git" in script
        out = capsys.readouterr().out
        assert "Tmux session 'sess-2' created" in out
        assert "Then run: tmux attach -t sess-2" in out

    @patch(
        "daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests.run_shell",
        return_value=SimpleNamespace(stdout=""),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_ephemeral_cluster_remote_tests._load_default_repo",
        return_value=("https://example.com/test.git", "release-1"),
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
