from __future__ import annotations

import os
import subprocess
from pathlib import Path

from typer.testing import CliRunner

import daylily_ec.headnode as headnode
from daylily_ec.cli import app

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[1]


class _FakeBudgetsClient:
    def __init__(self, budgets):
        self._budgets = budgets

    def describe_budgets(self, AccountId: str):
        assert AccountId == "123456789012"
        return {"Budgets": self._budgets}


class _FakeStsClient:
    def get_caller_identity(self):
        return {"Account": "123456789012"}


class _FakeSession:
    def __init__(self, budgets):
        self._budgets = budgets

    def client(self, service_name: str, region_name: str | None = None):
        _ = region_name
        if service_name == "sts":
            return _FakeStsClient()
        if service_name == "budgets":
            return _FakeBudgetsClient(self._budgets)
        raise AssertionError(f"unexpected service {service_name}")


def _activate_dayec_runtime(monkeypatch) -> None:
    monkeypatch.setenv("CONDA_PREFIX", "/tmp/dayec")
    monkeypatch.setenv("CONDA_DEFAULT_ENV", "DAY-EC")


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def test_collect_headnode_state_reads_project_budget_and_bucket(
    monkeypatch, tmp_path: Path
) -> None:
    cfnconfig_path = tmp_path / "cfnconfig"
    cfnconfig_path.write_text("cfn_region=us-west-2\n", encoding="utf-8")

    cluster_config_path = tmp_path / "cluster-config.yaml"
    cluster_config_path.write_text(
        "\n".join(
            [
                "Tags:",
                "  - Key: aws-parallelcluster-project",
                "    Value: da-us-west-2b-demo",
                "HeadNode:",
                "  CustomActions:",
                "    OnNodeConfigured:",
                "      Script: s3://reference-bucket/bootstrap.sh",
            ]
        ),
        encoding="utf-8",
    )

    budget_tags_path = tmp_path / "budget-tags.tsv"
    budget_tags_path.write_text("da-us-west-2b-demo\tubuntu,alice\n", encoding="utf-8")

    budgets = [
        {
            "BudgetName": "da-us-west-2b-demo",
            "BudgetLimit": {"Amount": "200", "Unit": "USD"},
            "CalculatedSpend": {"ActualSpend": {"Amount": "50", "Unit": "USD"}},
        }
    ]

    monkeypatch.setattr(headnode.getpass, "getuser", lambda: "alice")
    monkeypatch.setattr(headnode, "_build_session", lambda region, profile: _FakeSession(budgets))

    state = headnode.collect_headnode_state(
        profile="lsmc",
        cfnconfig_path=cfnconfig_path,
        cluster_config_path=cluster_config_path,
        budget_tags_path=budget_tags_path,
    )

    assert state.region == "us-west-2"
    assert state.project == "da-us-west-2b-demo"
    assert state.reference_bucket == "reference-bucket"
    assert state.aws_profile == "lsmc"
    assert state.aws_account_id == "123456789012"
    assert state.region_az_hint == "us-west-2b"
    assert state.cluster_name_hint == "demo"
    assert state.valid_projects == ["da-us-west-2b-demo"]
    assert state.budget_summary is not None
    assert state.budget_summary.exists is True
    assert state.budget_summary.total_budget == "200"
    assert state.budget_summary.used_budget == "50"
    assert state.warnings == []


def test_collect_headnode_state_skip_project_check_preserves_detected_project(
    monkeypatch, tmp_path: Path
) -> None:
    cfnconfig_path = tmp_path / "cfnconfig"
    cfnconfig_path.write_text("cfn_region=us-west-2\n", encoding="utf-8")

    cluster_config_path = tmp_path / "cluster-config.yaml"
    cluster_config_path.write_text(
        "\n".join(
            [
                "  - Key: aws-parallelcluster-project",
                "    Value: da-us-west-2b-demo",
                "      Script: s3://reference-bucket/bootstrap.sh",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(headnode.getpass, "getuser", lambda: "alice")

    state = headnode.collect_headnode_state(
        skip_project_check=True,
        cfnconfig_path=cfnconfig_path,
        cluster_config_path=cluster_config_path,
        budget_tags_path=tmp_path / "missing.tsv",
    )

    assert state.project == "da-us-west-2b-demo"
    assert state.budget_summary is None
    assert state.warnings == []


def test_collect_headnode_state_does_not_fall_back_to_global_when_project_is_not_authorized(
    monkeypatch, tmp_path: Path
) -> None:
    cfnconfig_path = tmp_path / "cfnconfig"
    cfnconfig_path.write_text("cfn_region=us-west-2\n", encoding="utf-8")

    cluster_config_path = tmp_path / "cluster-config.yaml"
    cluster_config_path.write_text(
        "\n".join(
            [
                "  - Key: aws-parallelcluster-project",
                "    Value: day-ssm-e2e-20260412103613",
                "      Script: s3://reference-bucket/bootstrap.sh",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    budget_tags_path = tmp_path / "budget-tags.tsv"
    budget_tags_path.write_text("da-us-west-2d-allowed\talice\n", encoding="utf-8")

    monkeypatch.setattr(headnode.getpass, "getuser", lambda: "alice")
    monkeypatch.setattr(headnode, "_build_session", lambda region, profile: _FakeSession([]))

    state = headnode.collect_headnode_state(
        cfnconfig_path=cfnconfig_path,
        cluster_config_path=cluster_config_path,
        budget_tags_path=budget_tags_path,
    )

    assert state.project == "day-ssm-e2e-20260412103613"
    assert all("daylily-global" not in warning for warning in state.warnings)
    assert any("Proceeding without fallback" in warning for warning in state.warnings)


def test_build_shell_code_exports_expected_compatibility_helpers(monkeypatch) -> None:
    monkeypatch.setenv("DAYLILY_EC_REPO_ROOT", "/repo/dayec")

    shell_code = headnode.build_shell_code(
        headnode.HeadnodeState(
            region="us-west-2",
            project="da-us-west-2b-demo",
            reference_bucket="reference-bucket",
        )
    )

    assert "export DAYLILY_EC_REPO_ROOT=/repo/dayec" in shell_code
    assert (
        'export DAY_CONTACT_EMAIL="${DAY_CONTACT_EMAIL:-john@daylilyinformatics.com}"' in shell_code
    )
    assert "export DAY_PROJECT=da-us-west-2b-demo" in shell_code
    assert "export DAY_AWS_REGION=us-west-2" in shell_code
    assert 'export DAY_ROOT="${PWD}"' in shell_code
    assert "reference_bucket=reference-bucket" in shell_code
    assert 'alias dy-b="${DAYLILY_EC_REPO_ROOT}/bin/init_dayec"' in shell_code
    assert 'alias day-build-env="${DAYLILY_EC_REPO_ROOT}/bin/init_dayec"' in shell_code
    assert "alias sq=sqq" in shell_code
    assert headnode.SQUEUE_FORMAT in shell_code


def test_run_headnode_init_emit_shell_non_interactive_sends_warnings_to_stderr(
    monkeypatch, capsys
) -> None:
    state = headnode.HeadnodeState(
        region="us-west-2",
        project="da-us-west-2b-demo",
        reference_bucket="reference-bucket",
        warnings=["Budget tags file not found."],
    )
    monkeypatch.setattr(headnode, "collect_headnode_state", lambda **kwargs: state)

    rc = headnode.run_headnode_init(non_interactive=True, emit_shell=True)
    captured = capsys.readouterr()

    assert rc == 0
    assert "export DAY_PROJECT=da-us-west-2b-demo" in captured.out
    assert "Project:" not in captured.out
    assert "Warning: Budget tags file not found." in captured.err


def test_run_headnode_init_interactive_mode_prompts_for_missing_budget(monkeypatch, capsys) -> None:
    state = headnode.HeadnodeState(
        region="us-west-2",
        project="da-us-west-2b-demo",
        reference_bucket="reference-bucket",
        budget_summary=headnode.BudgetSummary(name="da-us-west-2b-demo", exists=False),
    )
    prompts: list[str] = []

    monkeypatch.setattr(headnode, "collect_headnode_state", lambda **kwargs: state)
    monkeypatch.setattr(
        headnode,
        "_confirm",
        lambda prompt, default=False: prompts.append(prompt) or False,
    )

    rc = headnode.run_headnode_init()
    captured = capsys.readouterr()

    assert rc == 0
    assert prompts == ["Create missing budget 'da-us-west-2b-demo' now?"]
    assert "Project: da-us-west-2b-demo" in captured.out
    assert "Budget da-us-west-2b-demo was not found." in captured.out


def test_headnode_init_cli_passes_options_to_runtime(monkeypatch) -> None:
    _activate_dayec_runtime(monkeypatch)
    captured: dict[str, object] = {}

    def fake_run_headnode_init(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(headnode, "run_headnode_init", fake_run_headnode_init)

    result = runner.invoke(
        app,
        [
            "headnode",
            "init",
            "--project",
            "da-us-west-2b-demo",
            "--profile",
            "lsmc",
            "--skip-project-check",
            "--non-interactive",
            "--emit-shell",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "project": "da-us-west-2b-demo",
        "profile": "lsmc",
        "skip_project_check": True,
        "non_interactive": True,
        "emit_shell": True,
    }


def test_install_headnode_tools_writes_idempotent_login_bootstrap_block(tmp_path: Path) -> None:
    resources_dir = tmp_path / "resources"
    fake_bin = tmp_path / "fake-bin"
    home_dir = tmp_path / "home"
    log_dir = tmp_path / "logs"
    user_bin_dir = home_dir / ".local" / "bin"
    checkout_dir = home_dir / "projects" / "daylily-ephemeral-cluster"

    for path in (
        resources_dir / "bin" / "headnode_utils",
        resources_dir / "config",
        resources_dir / "etc",
        fake_bin,
        home_dir,
        log_dir,
        user_bin_dir,
        checkout_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)

    (resources_dir / "config" / "daylily_cli_global.yaml").write_text(
        "daylily: {}\n", encoding="utf-8"
    )
    (resources_dir / "config" / "daylily_available_repositories.yaml").write_text(
        "default_repository: daylily-omics-analysis\nrepositories: {}\n",
        encoding="utf-8",
    )
    (resources_dir / "etc" / "analysis_samples_template.tsv").write_text(
        "<REF-BUCKET-NAME>\n",
        encoding="utf-8",
    )
    cluster_config_path = tmp_path / "cluster-config.yaml"
    cluster_config_path.write_text(
        "HeadNode:\n  CustomActions:\n    OnNodeConfigured:\n      Script: s3://reference-bucket/bootstrap.sh\n",
        encoding="utf-8",
    )

    _write_executable(
        resources_dir / "bin" / "headnode_utils" / "day-clone",
        "#!/usr/bin/env bash\necho day-clone\n",
    )
    _write_executable(
        resources_dir / "bin" / "install_miniconda",
        "#!/usr/bin/env bash\nprintf 'install_miniconda\\n' >>\"${HEADNODE_TEST_LOG}\"\n",
    )
    _write_executable(
        checkout_dir / "activate",
        (
            "#!/usr/bin/env bash\n"
            'export PATH="${FAKE_DAYLILY_BIN}:$PATH"\n'
            'export DAYLILY_EC_REPO_ROOT="${DAYLILY_EC_RESOURCES_DIR}"\n'
            'export CONDA_DEFAULT_ENV="DAY-EC"\n'
            "printf 'activate\\n' >>\"${HEADNODE_TEST_LOG}\"\n"
        ),
    )
    _write_executable(
        fake_bin / "daylily-ec",
        (
            "#!/usr/bin/env bash\n"
            'printf \'daylily-ec:%s\\n\' "$*" >>"${HEADNODE_TEST_LOG}"\n'
            'if [[ "$1" == "headnode" && "$2" == "init" && "$3" == "--emit-shell" && "$4" == "--non-interactive" && "$5" == "--skip-project-check" ]]; then\n'
            "  printf '%s\\n' 'export TEST_HEADNODE_BOOTSTRAP=1'\n"
            "  exit 0\n"
            "fi\n"
            'if [[ "$1" == "resources-dir" ]]; then\n'
            "  printf '%s\\n' \"${DAYLILY_EC_RESOURCES_DIR}\"\n"
            "  exit 0\n"
            "fi\n"
            "exit 1\n"
        ),
    )

    legacy_block = (
        "# >>> daylily headnode bootstrap >>>\n"
        "daylily_headnode_bootstrap() {\n"
        '    local repo_root="$HOME/projects/daylily-ephemeral-cluster"\n'
        '    local activate_script="$repo_root/activate"\n'
        "    export DAYLILY_EC_HEADNODE_BOOTSTRAPPED=1\n"
        '    source "$activate_script"\n'
        "}\n"
        "daylily_headnode_bootstrap\n"
        "unset -f daylily_headnode_bootstrap\n"
        "# <<< daylily headnode bootstrap <<<\n"
    )
    conda_block = "# >>> conda initialize >>>\nconda hook\n# <<< conda initialize <<<\n"
    (home_dir / ".bashrc").write_text(legacy_block + "\n" + conda_block, encoding="utf-8")
    (home_dir / ".bash_profile").write_text(legacy_block + "\n" + conda_block, encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "DAYLILY_EC_RESOURCES_DIR": str(resources_dir),
            "DAYLILY_EC_CLUSTER_CONFIG_PATH": str(cluster_config_path),
            "FAKE_DAYLILY_BIN": str(fake_bin),
            "HEADNODE_TEST_LOG": str(log_dir / "installer.log"),
            "HOME": str(home_dir),
            "PATH": f"{fake_bin}:{env.get('PATH', '')}",
        }
    )

    script_path = REPO_ROOT / "bin" / "install-daylily-headnode-tools"
    for _ in range(2):
        result = subprocess.run(
            ["bash", str(script_path)],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    bashrc = (home_dir / ".bashrc").read_text(encoding="utf-8")
    bash_profile = (home_dir / ".bash_profile").read_text(encoding="utf-8")
    bootstrap_file = home_dir / ".config" / "daylily" / "daylily-headnode-bootstrap.sh"
    log_text = (log_dir / "installer.log").read_text(encoding="utf-8")

    assert bashrc.count("# >>> daylily headnode bootstrap >>>") == 1
    assert bash_profile.count("# >>> daylily headnode bootstrap >>>") == 1
    assert "daylily-headnode-bootstrap.sh" in bashrc
    assert "daylily-headnode-bootstrap.sh" in bash_profile
    assert bashrc.index("# >>> conda initialize >>>") < bashrc.index(
        "# >>> daylily headnode bootstrap >>>"
    )
    assert bash_profile.index("# >>> conda initialize >>>") < bash_profile.index(
        "# >>> daylily headnode bootstrap >>>"
    )
    assert bootstrap_file.exists()
    bootstrap_text = bootstrap_file.read_text(encoding="utf-8")
    assert 'repo_root="$HOME/projects/daylily-ephemeral-cluster"' in bootstrap_text
    assert 'case ":$PATH:" in' in bootstrap_text
    assert "stty -ixon -ixoff 2>/dev/null || true" in bootstrap_text
    assert "DAYLILY_EC_HEADNODE_BOOTSTRAPPED" in bootstrap_text
    assert 'source "$activate_script"' in bootstrap_text
    assert "conda activate DAY-EC" in bootstrap_text
    assert (
        'eval "$(daylily-ec headnode init --emit-shell --non-interactive --skip-project-check)"'
        in bootstrap_text
    )
    assert "daylily_headnode_bootstrap()" not in bootstrap_text
    assert "unset -f daylily_headnode_bootstrap" not in bootstrap_text
    assert (user_bin_dir / "day-clone").is_file()
    assert log_text.count("install_miniconda") >= 2
    assert log_text.count("activate") == 2
    assert (
        log_text.count(
            "daylily-ec:headnode init --emit-shell --non-interactive --skip-project-check"
        )
        == 2
    )


def test_install_headnode_tools_fails_when_miniconda_install_fails(tmp_path: Path) -> None:
    resources_dir = tmp_path / "resources"
    fake_bin = tmp_path / "fake-bin"
    home_dir = tmp_path / "home"

    for path in (
        resources_dir / "bin" / "headnode_utils",
        resources_dir / "config",
        resources_dir / "etc",
        fake_bin,
        home_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)

    (resources_dir / "config" / "daylily_cli_global.yaml").write_text(
        "daylily: {}\n", encoding="utf-8"
    )
    (resources_dir / "config" / "daylily_available_repositories.yaml").write_text(
        "default_repository: daylily-omics-analysis\nrepositories: {}\n",
        encoding="utf-8",
    )
    (resources_dir / "etc" / "analysis_samples_template.tsv").write_text(
        "<REF-BUCKET-NAME>\n",
        encoding="utf-8",
    )
    cluster_config_path = tmp_path / "cluster-config.yaml"
    cluster_config_path.write_text(
        "HeadNode:\n  CustomActions:\n    OnNodeConfigured:\n      Script: s3://reference-bucket/bootstrap.sh\n",
        encoding="utf-8",
    )

    _write_executable(
        resources_dir / "bin" / "headnode_utils" / "day-clone",
        "#!/usr/bin/env bash\necho day-clone\n",
    )
    _write_executable(
        resources_dir / "bin" / "install_miniconda",
        "#!/usr/bin/env bash\nexit 42\n",
    )
    _write_executable(
        resources_dir / "activate",
        '#!/usr/bin/env bash\nexport CONDA_DEFAULT_ENV="DAY-EC"\n',
    )
    _write_executable(
        fake_bin / "daylily-ec",
        "#!/usr/bin/env bash\nexit 0\n",
    )

    env = os.environ.copy()
    env.update(
        {
            "DAYLILY_EC_RESOURCES_DIR": str(resources_dir),
            "DAYLILY_EC_CLUSTER_CONFIG_PATH": str(cluster_config_path),
            "HOME": str(home_dir),
            "PATH": f"{fake_bin}:{env.get('PATH', '')}",
        }
    )

    script_path = REPO_ROOT / "bin" / "install-daylily-headnode-tools"
    result = subprocess.run(
        ["bash", str(script_path)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "install_miniconda" not in result.stdout
    assert not (home_dir / ".config" / "daylily" / "daylily-headnode-bootstrap.sh").exists()


def test_active_runtime_paths_no_longer_invoke_dyinit() -> None:
    for rel_path in (
        "bin/daylily-cfg-headnode",
        "bin/daylily-run-ephemeral-cluster-remote-tests",
        "bin/install-daylily-headnode-tools",
        "bin/helpers/ensure_dayec.sh",
        "daylily_ec/workflow/create_cluster.py",
        "daylily_ec/resources/payload/bin/daylily-cfg-headnode",
        "daylily_ec/resources/payload/bin/daylily-run-ephemeral-cluster-remote-tests",
        "daylily_ec/resources/payload/bin/install-daylily-headnode-tools",
        "daylily_ec/resources/payload/bin/helpers/ensure_dayec.sh",
    ):
        text = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
        assert "source dyinit" not in text
        assert ". dyinit" not in text


def test_packaged_install_headnode_tools_matches_source() -> None:
    source = REPO_ROOT / "bin/install-daylily-headnode-tools"
    packaged = REPO_ROOT / "daylily_ec/resources/payload/bin/install-daylily-headnode-tools"

    assert packaged.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")


def test_post_install_bootstrap_logs_and_fails_hard_for_missing_apptainer() -> None:
    script = (REPO_ROOT / "config/day_cluster/post_install_ubuntu_combined.sh").read_text(
        encoding="utf-8"
    )

    assert "set -Ee -o pipefail" in script
    assert "set -Eeuo pipefail" not in script
    assert 'export HOME="${HOME:-/root}"' in script
    assert "trap 'rc=$?; echo \"[$(date +%Y%m%d_%H%M%S)] ERROR rc=${rc}" in script
    assert 'exec > >(tee -a "${local_log_fn}" "${fsx_log_fn}") 2>&1' in script
    assert "apptainer_1.4.5_amd64.deb" in script
    assert "70f19af846501acfbc2e42e7cfeee9ee11ddbbfa1c3502d0d99cde34e8e0af05" in script
    assert "cached Apptainer deb not found" in script
    assert 'apt-get install -y "${apptainer_deb}"' in script
    assert 'ln -sfn "$(command -v apptainer)" /usr/local/bin/singularity' in script
    assert "ln -sfn /fsx/data/tool_specific_resources/cromwell_87.jar" in script
    assert "ln -sfn /fsx/data/tool_specific_resources/womtool_87.jar" in script
    assert "link_cached_entries /fsx/data/cached_envs/conda" in script
    assert "required" in script
    assert "optional" in script
    assert "No optional cached entries found under" in script
    assert "Cached entry already present, leaving in place" in script
    assert "Original sbatch already present" in script
    assert "Original srun already present" in script
    assert "ln -sfn /opt/slurm/bin/sbatch /opt/slurm/bin/srun" in script
    assert 'append_once "PrologFlags=Alloc" /opt/slurm/etc/slurm.conf' in script
    assert "mv /opt/slurm/bin/sbatch /opt/slurm/sbin/sbatch" in script
    assert "mv /opt/slurm/bin/srun /opt/slurm/sbin/srun" in script
    assert "ln -s /fsx/data/cached_envs/conda/*" not in script
    assert 'echo "PrologFlags=Alloc" >> /opt/slurm/etc/slurm.conf' not in script
    assert "ppa:apptainer/ppa" not in script
    assert "command -v apptainer" in script
    assert "command -v singularity" in script


def test_packaged_post_install_bootstrap_matches_source() -> None:
    source = REPO_ROOT / "config/day_cluster/post_install_ubuntu_combined.sh"
    packaged = (
        REPO_ROOT
        / "daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh"
    )

    assert packaged.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
