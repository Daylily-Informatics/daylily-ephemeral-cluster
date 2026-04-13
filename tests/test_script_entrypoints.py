from __future__ import annotations

from pathlib import Path
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
        assert "Session Manager command: aws ssm start-session --region us-west-2 --target i-abc123 --document-name SSM-SessionManagerRunShell" in out

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
        mock_start.assert_called_once_with("i-abc123", "us-west-2", profile="dev")
        out = capsys.readouterr().out
        assert "Opening Session Manager session as ubuntu to i-abc123" in out
        assert "sudo -iu ubuntu" not in out

    @patch(
        "daylily_ec.scripts.daylily_ssh_into_headnode.start_session",
        side_effect=SsmError("Session Manager must be configured to run shell sessions as ubuntu via SSM-SessionManagerRunShell."),
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

    def test_build_default_command_includes_requested_flags(self):
        command = run_omics_module.build_default_command(
            target="produce_snv_concordances",
            genome="hg38",
            jobs=8,
            aligners=["bwa2a", "strobe"],
            dedupers=["dppl"],
            snv_callers=["deep"],
            containerized=False,
            dry_run=True,
            extra="--rerun-incomplete",
        )

        assert "DAY_CONTAINERIZED=false" in command
        assert "bin/day_run" in command
        assert "aligners=['bwa2a','strobe']" in command
        assert "-j 8" in command
        assert "-n" in command
        assert "--rerun-incomplete" in command

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
        assert config.stage_dir == "/home/ubuntu/stage/run-1"
        assert "__DAYLILY_STAGE_DIR__=/home/ubuntu/stage/run-1" in capsys.readouterr().out

    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.run_shell",
        return_value=SimpleNamespace(stdout="__DAYLILY_SESSION__=sess-1\n", stderr=""),
    )
    @patch(
        "daylily_ec.scripts.daylily_run_omics_analysis_headnode.discover_stage_config",
        return_value=run_omics_module.RemoteConfig(
            stage_dir="/fsx/stage/run-1",
            samples_path="/fsx/stage/run-1/foo_samples.tsv",
            units_path="/fsx/stage/run-1/foo_units.tsv",
        ),
    )
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
        _mock_discover,
        mock_run_shell,
        capsys,
    ):
        rc = run_omics_module.main(["--profile", "dev", "--dry-run"])

        assert rc == 0
        script = mock_run_shell.call_args.args[2]
        assert "nohup tmux new-session" in script
        assert "tmux has-session" in script
        assert "DAY_CONTAINERIZED=true" in script
        assert 'mkdir -p "$analysis_root/$(whoami)"' in script
        assert 'mkdir -p "$clone_root"' not in script
        assert "__DAYLILY_ERROR__=destination_exists_without_repo" in script
        assert 'elif [[ -n "${DAY_PROJECT:-}" ]]; then' in script
        assert 'export PROJECT="$DAY_PROJECT"' in script
        assert "set +u" in script
        assert "set -u" in script
        assert ". bin/day_activate slurm hg38 remote" in script
        assert "bin/day_run" in script
        assert "exec bash -il" in script
        assert '--which-one "$TRANSPORT"' not in script
        out = capsys.readouterr().out
        assert "daylily-ssh-into-headnode --profile dev --region us-west-2 --cluster cluster-a" in out
        assert "Then run: tmux attach -t sess-1" in out

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
        _mock_discover,
        _mock_run_shell,
    ):
        with pytest.raises(CommandError, match="did not report success"):
            run_omics_module.main(["--profile", "dev"])


class TestCfgHeadnodeScript:
    def test_load_repo_overrides_parses_file(self, tmp_path):
        override_file = tmp_path / "repos.txt"
        override_file.write_text(
            "# comment\n"
            "daylily-omics-analysis:release-1\n"
            "invalid-line\n"
            "rna-seq-star-deseq2:main\n",
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
        assert "daylily-ssh-into-headnode --profile dev --region us-west-2 --cluster cluster-a" in capsys.readouterr().out

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
