from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

import pytest
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


def _write_headnode_utils(path: Path, marker: str = "helper") -> None:
    _write_executable(path / "day-clone", f"#!/usr/bin/env bash\necho {marker}\n")
    _write_executable(path / "sq", '#!/usr/bin/env bash\nexec sqq "$@"\n')
    _write_executable(
        path / "sqq",
        (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'format="SQ_FORMAT"\n'
            'if [[ "$#" -eq 0 ]]; then\n'
            '    exec squeue -o "$format"\n'
            "fi\n"
            'jobs=""\n'
            'for job in "$@"; do\n'
            '    if [[ -z "$jobs" ]]; then\n'
            '        jobs="$job"\n'
            "    else\n"
            '        jobs="${jobs},${job}"\n'
            "    fi\n"
            "done\n"
            'exec squeue -o "$format" -j "$jobs"\n'
        ),
    )


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
    assert state.reference_s3_uri == "reference-bucket"
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
            reference_s3_uri="reference-bucket",
        )
    )

    assert "export DAYLILY_EC_REPO_ROOT=/repo/dayec" in shell_code
    assert (
        'export DAY_CONTACT_EMAIL="${DAY_CONTACT_EMAIL:-john@daylilyinformatics.com}"' in shell_code
    )
    assert "export DAY_PROJECT=da-us-west-2b-demo" in shell_code
    assert "export DAY_AWS_REGION=us-west-2" in shell_code
    assert (
        'export APPTAINER_HOME="${APPTAINER_HOME:-/fsx/tmp/apptainer_home/'
        '${USER:-$(id -un)}}"' in shell_code
    )
    assert (
        'export DAYLILY_APPTAINER_CACHE="${DAYLILY_APPTAINER_CACHE:-/fsx/resources/environments/apptainer}"'
        in shell_code
    )
    assert (
        'export DAYLILY_CONTAINER_CACHE="${DAYLILY_CONTAINER_CACHE:-/fsx/resources/'
        'environments/containers/${USER:-$(id -un)}/$(hostname)}"' in shell_code
    )
    assert (
        'export APPTAINER_CACHEDIR="${APPTAINER_CACHEDIR:-$DAYLILY_APPTAINER_CACHE}"' in shell_code
    )
    assert (
        'export SINGULARITY_CACHEDIR="${SINGULARITY_CACHEDIR:-$APPTAINER_CACHEDIR}"' in shell_code
    )
    assert "/fsx/tmp/apptainer_cache" not in shell_code
    assert 'export DAY_ROOT="${PWD}"' in shell_code
    assert "reference_s3_uri=reference-bucket" in shell_code
    assert 'alias dy-b="${DAYLILY_EC_REPO_ROOT}/bin/init_dayec"' in shell_code
    assert 'alias day-build-env="${DAYLILY_EC_REPO_ROOT}/bin/init_dayec"' in shell_code
    assert "alias sq=sqq" in shell_code
    assert headnode.SQUEUE_FORMAT in shell_code


def test_build_shell_code_is_safe_with_unset_user_and_ps1(tmp_path: Path) -> None:
    shell_code = headnode.build_shell_code(
        headnode.HeadnodeState(
            region="us-west-2",
            project="test-project",
            reference_s3_uri="s3://reference-bucket",
        )
    )
    script = tmp_path / "headnode-shell.sh"
    script.write_text("set -u\nunset USER PS1\n" + shell_code, encoding="utf-8")

    result = subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_run_headnode_init_emit_shell_non_interactive_fails_on_missing_budget_tags(
    monkeypatch, capsys
) -> None:
    state = headnode.HeadnodeState(
        region="us-west-2",
        project="da-us-west-2b-demo",
        reference_s3_uri="reference-bucket",
        warnings=["Budget tags file not found."],
    )
    monkeypatch.setattr(headnode, "collect_headnode_state", lambda **kwargs: state)

    rc = headnode.run_headnode_init(non_interactive=True, emit_shell=True)
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert "Project:" not in captured.out
    assert "Warning: Budget tags file not found." in captured.err
    assert "Error: Budget tag project membership is required" in captured.err


def test_run_headnode_init_emit_shell_non_interactive_allows_explicit_skip(
    monkeypatch, capsys
) -> None:
    state = headnode.HeadnodeState(
        region="us-west-2",
        project="da-us-west-2b-demo",
        skip_project_check=True,
        reference_s3_uri="reference-bucket",
        warnings=["Budget tags file not found."],
    )
    monkeypatch.setattr(headnode, "collect_headnode_state", lambda **kwargs: state)

    rc = headnode.run_headnode_init(
        non_interactive=True,
        emit_shell=True,
        skip_project_check=True,
    )
    captured = capsys.readouterr()

    assert rc == 0
    assert "export DAY_PROJECT=da-us-west-2b-demo" in captured.out
    assert "Warning: Budget tags file not found." in captured.err


def test_run_headnode_init_emit_shell_non_interactive_fails_without_core_state(
    monkeypatch, capsys
) -> None:
    state = headnode.HeadnodeState()
    monkeypatch.setattr(headnode, "collect_headnode_state", lambda **kwargs: state)

    rc = headnode.run_headnode_init(non_interactive=True, emit_shell=True)
    captured = capsys.readouterr()

    assert rc == 1
    assert captured.out == ""
    assert "Error: Headnode region is required" in captured.err
    assert "Error: Headnode project is required" in captured.err
    assert "Error: Reference S3 URI is required" in captured.err


def test_run_headnode_init_interactive_mode_prompts_for_missing_budget(monkeypatch, capsys) -> None:
    state = headnode.HeadnodeState(
        region="us-west-2",
        project="da-us-west-2b-demo",
        reference_s3_uri="reference-bucket",
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
        "daylily:\n"
        "  sentieon_license:\n"
        "    mode: server\n"
        "    endpoint: license.sentieon.lsmc.bio:8990\n",
        encoding="utf-8",
    )
    (resources_dir / "config" / "daylily_pipeline_command_catalog.yaml").write_text(
        "default_repository: daylily-omics-analysis\nrepositories: {}\n",
        encoding="utf-8",
    )
    (resources_dir / "config" / "github_known_hosts").write_text(
        "github.com ssh-ed25519 test-host-key\n",
        encoding="utf-8",
    )
    (resources_dir / "etc" / "analysis_samples_template.tsv").write_text(
        "<REF-S3-URI>\n",
        encoding="utf-8",
    )
    cluster_config_path = tmp_path / "cluster-config.yaml"
    cluster_config_path.write_text(
        "HeadNode:\n  CustomActions:\n    OnNodeConfigured:\n      Script: s3://reference-bucket/bootstrap.sh\n",
        encoding="utf-8",
    )

    _write_headnode_utils(resources_dir / "bin" / "headnode_utils", marker="day-clone")
    _write_executable(
        fake_bin / "squeue",
        '#!/usr/bin/env bash\nprintf \'%s\\n\' "$@" >"${SQUEUE_ARG_LOG}"\n',
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
            "SQUEUE_ARG_LOG": str(log_dir / "squeue.args"),
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
    assert (
        '"${DAYLILY_EC_HEADNODE_BOOTSTRAPPED:-0}" != "1" '
        '|| "${CONDA_DEFAULT_ENV:-}" != "DAY-EC"'
        in bootstrap_text
    )
    assert 'source "$activate_script"' in bootstrap_text
    assert "conda activate DAY-EC" in bootstrap_text
    assert (
        'eval "$(daylily-ec headnode init --emit-shell --non-interactive --skip-project-check)"'
        in bootstrap_text
    )
    assert 'export SENTIEON_LICENSE="$sentieon_license_endpoint"' in bootstrap_text
    assert "legacy daylily.sentieon_lic_path is forbidden" in bootstrap_text
    assert "license.sentieon.lsmc.bio:8990" in bootstrap_text
    assert "daylily_headnode_bootstrap()" not in bootstrap_text
    assert "unset -f daylily_headnode_bootstrap" not in bootstrap_text
    assert (home_dir / ".config" / "daylily" / "daylily_pipeline_command_catalog.yaml").is_file()
    assert (home_dir / ".config" / "daylily" / "github_known_hosts").is_file()
    legacy_catalog = home_dir / ".config" / "daylily" / "daylily_available_repositories.yaml"
    assert legacy_catalog.is_symlink()
    assert legacy_catalog.readlink() == Path("daylily_pipeline_command_catalog.yaml")
    assert (user_bin_dir / "day-clone").is_file()
    assert (user_bin_dir / "sq").is_file()
    assert (user_bin_dir / "sqq").is_file()
    sq_result = subprocess.run(
        ["/bin/sh", "-c", "sq 123 456"],
        env={**env, "PATH": f"{user_bin_dir}:{fake_bin}:{env.get('PATH', '')}"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert sq_result.returncode == 0, sq_result.stderr
    assert (log_dir / "squeue.args").read_text(encoding="utf-8").splitlines() == [
        "-o",
        "SQ_FORMAT",
        "-j",
        "123,456",
    ]
    assert log_text.count("install_miniconda") >= 2
    assert log_text.count("activate") == 2
    assert (
        log_text.count(
            "daylily-ec:headnode init --emit-shell --non-interactive --skip-project-check"
        )
        == 2
    )
    bootstrap_result = subprocess.run(
        [
            "bash",
            "-c",
            f"source {shlex.quote(str(bootstrap_file))}; printf '%s' \"$SENTIEON_LICENSE\"",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert bootstrap_result.returncode == 0, bootstrap_result.stderr
    assert bootstrap_result.stdout == "license.sentieon.lsmc.bio:8990"


@pytest.mark.parametrize(
    ("config_text", "expected_error"),
    (
        (
            "daylily:\n  sentieon_lic_path: /fsx/legacy.lic\n",
            "legacy daylily.sentieon_lic_path is forbidden",
        ),
        (
            "daylily:\n"
            "  sentieon_license:\n"
            "    mode: local\n"
            "    endpoint: license.sentieon.lsmc.bio:8990\n",
            "daylily.sentieon_license.mode must be server",
        ),
        (
            "daylily:\n"
            "  sentieon_license:\n"
            "    mode: server\n"
            "    endpoint: usw2d-01.sentieon.lsmc.bio:8990\n",
            "daylily.sentieon_license.endpoint must be license.sentieon.lsmc.bio:8990",
        ),
    ),
)
def test_install_headnode_tools_rejects_noncanonical_sentieon_license_config(
    tmp_path: Path,
    config_text: str,
    expected_error: str,
) -> None:
    resources_dir = tmp_path / "resources"
    (resources_dir / "config").mkdir(parents=True)
    (resources_dir / "config" / "daylily_cli_global.yaml").write_text(
        config_text,
        encoding="utf-8",
    )

    env = os.environ.copy()
    env.update(
        {
            "DAYLILY_EC_RESOURCES_DIR": str(resources_dir),
            "HOME": str(tmp_path / "home"),
        }
    )
    result = subprocess.run(
        ["bash", str(REPO_ROOT / "bin" / "install-daylily-headnode-tools")],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert expected_error in result.stderr
    assert not (
        tmp_path
        / "home"
        / ".config"
        / "daylily"
        / "daylily-headnode-bootstrap.sh"
    ).exists()


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
        "daylily:\n"
        "  sentieon_license:\n"
        "    mode: server\n"
        "    endpoint: license.sentieon.lsmc.bio:8990\n",
        encoding="utf-8",
    )
    (resources_dir / "config" / "daylily_pipeline_command_catalog.yaml").write_text(
        "default_repository: daylily-omics-analysis\nrepositories: {}\n",
        encoding="utf-8",
    )
    (resources_dir / "config" / "github_known_hosts").write_text(
        "github.com ssh-ed25519 test-host-key\n",
        encoding="utf-8",
    )
    (resources_dir / "etc" / "analysis_samples_template.tsv").write_text(
        "<REF-S3-URI>\n",
        encoding="utf-8",
    )
    cluster_config_path = tmp_path / "cluster-config.yaml"
    cluster_config_path.write_text(
        "HeadNode:\n  CustomActions:\n    OnNodeConfigured:\n      Script: s3://reference-bucket/bootstrap.sh\n",
        encoding="utf-8",
    )

    _write_headnode_utils(resources_dir / "bin" / "headnode_utils", marker="day-clone")
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


def test_install_headnode_tools_prefers_checkout_over_installed_resources(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    installed_resources = tmp_path / "installed-resources"
    fake_bin = tmp_path / "fake-bin"

    for root, marker in ((repo_root, "checkout"), (installed_resources, "installed")):
        for path in (
            root / "bin" / "headnode_utils",
            root / "config",
            root / "etc",
        ):
            path.mkdir(parents=True, exist_ok=True)
        (root / "config" / "daylily_cli_global.yaml").write_text(
            "daylily:\n"
            "  sentieon_license:\n"
            "    mode: server\n"
            "    endpoint: license.sentieon.lsmc.bio:8990\n",
            encoding="utf-8",
        )
        (root / "config" / "daylily_pipeline_command_catalog.yaml").write_text(
            "default_repository: daylily-omics-analysis\nrepositories: {}\n",
            encoding="utf-8",
        )
        (root / "config" / "github_known_hosts").write_text(
            "github.com ssh-ed25519 test-host-key\n",
            encoding="utf-8",
        )
        (root / "etc" / "analysis_samples_template.tsv").write_text(
            "<REF-S3-URI>\n",
            encoding="utf-8",
        )
        _write_headnode_utils(root / "bin" / "headnode_utils", marker=marker)
    _write_executable(
        repo_root / "bin" / "install_miniconda",
        "#!/usr/bin/env bash\nexit 42\n",
    )
    fake_bin.mkdir(parents=True, exist_ok=True)
    _write_executable(
        fake_bin / "daylily-ec",
        (
            "#!/usr/bin/env bash\n"
            'if [[ "$1" == "resources-dir" ]]; then\n'
            f"  printf '%s\\n' {shlex.quote(str(installed_resources))}\n"
            "  exit 0\n"
            "fi\n"
            "exit 1\n"
        ),
    )

    script_source = (REPO_ROOT / "bin" / "install-daylily-headnode-tools").read_text(
        encoding="utf-8"
    )
    script_path = repo_root / "bin" / "install-daylily-headnode-tools"
    script_path.write_text(script_source, encoding="utf-8")
    script_path.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "DAYLILY_EC_RESOURCES_DIR": "",
            "DAYLILY_EC_CLUSTER_CONFIG_PATH": str(tmp_path / "missing-cluster-config.yaml"),
            "HOME": str(tmp_path / "home"),
            "PATH": f"{fake_bin}:{env.get('PATH', '')}",
        }
    )

    result = subprocess.run(
        ["bash", str(script_path)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    installed_day_clone = tmp_path / "home" / ".local" / "bin" / "day-clone"
    assert installed_day_clone.read_text(encoding="utf-8").endswith("echo checkout\n")


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


def test_headnode_squeue_helpers_are_watchable_from_non_interactive_shell(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    arg_log = tmp_path / "squeue.args"
    _write_executable(
        fake_bin / "squeue",
        '#!/usr/bin/env bash\nprintf \'%s\\n\' "$@" >"${SQUEUE_ARG_LOG}"\n',
    )
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{REPO_ROOT / 'bin' / 'headnode_utils'}:{fake_bin}:{env.get('PATH', '')}",
            "SQUEUE_ARG_LOG": str(arg_log),
        }
    )

    result = subprocess.run(
        ["/bin/sh", "-c", "sq 123 456"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert arg_log.read_text(encoding="utf-8").splitlines() == [
        "-o",
        headnode.SQUEUE_FORMAT,
        "-j",
        "123,456",
    ]


def test_headnode_squeue_helper_format_matches_headnode_init_constant() -> None:
    script = (REPO_ROOT / "bin" / "headnode_utils" / "sqq").read_text(encoding="utf-8")

    assert f'format="{headnode.SQUEUE_FORMAT}"' in script


def test_post_install_bootstrap_logs_and_fails_hard_for_missing_apptainer() -> None:
    script = (REPO_ROOT / "config/day_cluster/post_install_ubuntu_combined.sh").read_text(
        encoding="utf-8"
    )

    assert "set -Ee -o pipefail" in script
    outer_script = script.split("install_spot_lifecycle_hooks()")[0]
    assert "set -Eeuo pipefail" not in outer_script
    assert 'export HOME="${HOME:-/root}"' in script
    assert "trap 'rc=$?; echo \"[$(date +%Y%m%d_%H%M%S)] ERROR rc=${rc}" in script
    assert 'exec > >(tee -a "${local_log_fn}" "${fsx_log_fn}") 2>&1' in script
    assert "apptainer_1.4.5_amd64.deb" in script
    assert "70f19af846501acfbc2e42e7cfeee9ee11ddbbfa1c3502d0d99cde34e8e0af05" in script
    assert "reference_wait_timeout_seconds=3600" in script
    assert "wait_for_reference_data" in script
    assert 'runtime_assets_root="/fsx/references/runtime_assets"' in script
    assert 'references_root="/fsx/references"' in script
    assert 'environment_cache_root="/fsx/resources/environments"' in script
    assert 'work_root="/fsx/work"' in script
    assert 'run_mounts_root="/fsx/run_dir_mounts"' in script
    assert ".day.lsmc.bio" not in script
    assert 'control_data_root="/fsx/control_data"' not in script
    assert "Required DayOA role entries are visible" in script
    assert "required DayOA role entries did not appear" in script
    assert '[ -d "${references_root}/genomic_data" ]' in script
    assert '[ -d "${control_data_root}/genomic_data" ]' not in script
    assert '[ -d "${staging_root}" ]' not in script
    assert "make_role_data_read_only" in script
    assert 'chmod a-w "${role_root}"' in script
    assert 'stat -c "Role data permissions: %A %n" "${role_root}"' in script
    assert "fd-find ripgrep docker.io" in script
    assert "graphviz graphviz-dev python3-pip" in script
    assert "install_global_pygraphviz" in script
    assert 'python3 -m pip install --upgrade "pygraphviz==2.0.1"' in script
    assert "python3 -m pip install --upgrade pygraphviz" not in script
    assert "pygraphviz global import OK" in script
    assert "sbatch_wrapper_sha256" not in script
    assert "sleep_test_sha256" not in script
    assert "cached Apptainer deb not found" in script
    assert 'apt-get install -y "${apptainer_deb}"' in script
    assert 'ln -sfn "$(command -v apptainer)" /usr/local/bin/singularity' in script
    assert 'ln -sfn "${runtime_assets_root}/tool_specific_resources/cromwell_87.jar"' in script
    assert 'ln -sfn "${runtime_assets_root}/tool_specific_resources/womtool_87.jar"' in script
    assert "prepare_common_writable_dirs" in script
    assert 'spot_lifecycle_state_dir="/var/lib/daylily/spot_lifecycle"' in script
    assert "daylily-spot-lifecycle-shutdown.service" in script
    assert "daylily-spot-interruption-watch.service" in script
    assert "ExecStop=/opt/daylily/bin/daylily-spot-lifecycle-event shutdown systemd-stop" in script
    assert "latest/meta-data/spot/instance-action" in script
    assert "install_spot_lifecycle_hooks" in script
    assert "prepare_headnode_writable_dirs" in script
    assert "prepare_dayoa_environment_cache" in script
    assert "install -d -m 1777 \\" in script
    assert '"${work_root}"' in script
    assert '"${run_mounts_root}"' in script
    assert "install -d -m 0777 /fsx/analysis_results" in script
    assert "chmod a+rwx /fsx/analysis_results" in script
    assert "install -d -m 0775 -o ubuntu -g ubuntu /fsx/analysis_results/ubuntu" in script
    assert '"${work_root}/ubuntu/containers"' in script
    assert '"${work_root}/ubuntu/nextflow"' in script
    assert '"${work_root}/ubuntu/sarek"' in script
    assert '"${work_root}/daylily/containers"' in script
    assert "install_headnode_runtime_cache_profile" in script
    assert "cat <<'EOF' > /etc/profile.d/daylily-runtime-cache.sh" in script
    assert 'export DAYLILY_WORK_ROOT="${DAYLILY_WORK_ROOT:-/fsx/work/${USER}}"' in script
    assert (
        'export DAYLILY_APPTAINER_CACHE="${DAYLILY_APPTAINER_CACHE:-/fsx/resources/environments/apptainer}"'
        in script
    )
    assert (
        'export DAYLILY_CONTAINER_CACHE="${DAYLILY_CONTAINER_CACHE:-${DAYLILY_WORK_ROOT}/containers}"'
        in script
    )
    assert (
        'export DAYLILY_NEXTFLOW_SEED_CACHE="${DAYLILY_NEXTFLOW_SEED_CACHE:-/fsx/resources/environments/nextflow}"'
        in script
    )
    assert (
        'export SINGULARITY_CACHEDIR="${SINGULARITY_CACHEDIR:-${DAYLILY_APPTAINER_CACHE}}"'
        in script
    )
    assert 'export APPTAINER_CACHEDIR="${APPTAINER_CACHEDIR:-${DAYLILY_APPTAINER_CACHE}}"' in script
    assert (
        "DayOA Conda environments use an empty cluster-scoped writable cache; "
        "container and Nextflow caches are seeded from "
        "${runtime_assets_root}/cached_envs into ${environment_cache_root}" in script
    )
    assert "link_cached_entries" in script
    assert "resolve_cluster_cache_namespace" in script
    assert "aws cloudformation describe-stacks" in script
    assert '"${environment_cache_root}/conda/${user_name}/${cluster_cache_namespace}"' in script
    assert (
        '"${environment_cache_root}/containers/${user_name}/${cluster_cache_namespace}"'
        in script
    )
    assert '"${runtime_assets_root}/cached_envs/conda"' not in script
    assert '"${runtime_assets_root}/cached_envs/containers"' in script
    assert "/etc/profile.d/daylily-cluster-cache-namespace.sh" in script
    assert 'export DAYOA_CLUSTER_CACHE_NAMESPACE="${cluster_cache_namespace}"' in script
    assert "legacy linked Conda environments are forbidden" in script
    for removed in (
        "tail" + "scale",
        "headnode-" + "authkey",
        "pkgs." + "tail" + "scale" + ".com",
    ):
        assert removed not in script.lower()
    assert "chmod -R a+wrx /fsx" not in script
    assert "Original sbatch already present" in script
    assert "Original srun already present" in script
    assert "ln -sfn /opt/slurm/bin/sbatch /opt/slurm/bin/srun" in script
    assert "install_s3_executable" in script
    assert 'aws s3 cp "${boot_s3_uri}/${s3_key}" "${temp_path}"' in script
    assert 'install_s3_executable "sbatch"' in script
    assert 'install_s3_executable "sleep_test.sh"' in script
    assert 'install -m 0755 "${temp_path}" "${destination}"' in script
    assert "install_slurm_submission_policy" in script
    assert "install_slurm_job_submit_policy.sh" in script
    assert "/opt/slurm/etc/scripts/prolog.d" in script
    assert "/opt/slurm/etc/scripts/epilog.d" in script
    assert "/opt/slurm/etc/slurm.conf" not in script
    assert "systemctl restart slurm" not in script
    assert "mv /opt/slurm/bin/sbatch /opt/slurm/sbin/sbatch" in script
    assert "mv /opt/slurm/bin/srun /opt/slurm/sbin/srun" in script
    assert "ln -s /fsx/references/runtime_assets/cached_envs/conda/*" not in script
    assert "Required /fsx/references reference entries are visible" not in script
    assert "chmod +x /opt/slurm/bin/sbatch" not in script
    assert "chmod a+x /opt/slurm/bin/sleep_test.sh" not in script
    assert "ln -s /fsx/data/cached_envs/conda/*" not in script
    assert "ppa:apptainer/ppa" not in script
    assert "command -v apptainer" in script
    assert "command -v singularity" in script
    assert "cat <<'EOF' > /opt/slurm/sbin/check_tags.sh" in script
    assert "* * * * * /opt/slurm/sbin/check_tags.sh" in script
    global_actions = script.split("# GLOBAL ACTIONS HeadNode and ComputeFleet", 1)[1]
    headnode_branch = global_actions.split('if [ "${cfn_node_type}" == "HeadNode" ];then', 1)[1]
    assert "prepare_dayoa_environment_cache" not in global_actions.split(
        'if [ "${cfn_node_type}" == "HeadNode" ];then', 1
    )[0]
    assert headnode_branch.index("prepare_dayoa_environment_cache") < headnode_branch.index(
        "install_headnode_runtime_cache_profile"
    )
    assert headnode_branch.index("prepare_headnode_writable_dirs") < headnode_branch.index(
        "install_headnode_runtime_cache_profile"
    )
    assert script.index("cat <<'EOF' > /opt/slurm/sbin/check_tags.sh") < script.index(
        'if [ "${cfn_node_type}" == "ComputeFleet" ];then'
    )
    assert script.index('if [ "${cfn_node_type}" == "ComputeFleet" ];then') < script.index(
        'echo "Expanding /dev/shm to 80% of total memory"'
    )
    compute_branch = script.split('if [ "${cfn_node_type}" == "ComputeFleet" ];then', 1)[1]
    compute_branch = compute_branch.split("\nfi\n", 1)[0]
    assert "exit 0" not in compute_branch


def test_packaged_post_install_bootstrap_matches_source() -> None:
    source = REPO_ROOT / "config/day_cluster/post_install_ubuntu_combined.sh"
    packaged = (
        REPO_ROOT
        / "daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh"
    )

    assert packaged.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")


def test_ubuntu_bootstrap_installs_puppeteer_chrome_runtime() -> None:
    script = (REPO_ROOT / "config/day_cluster/post_install_ubuntu_combined.sh").read_text(
        encoding="utf-8"
    )
    chrome_runtime_packages = {
        "ca-certificates",
        "fonts-liberation",
        "libasound2",
        "libatk-bridge2.0-0",
        "libatk1.0-0",
        "libc6",
        "libcairo2",
        "libcups2",
        "libdbus-1-3",
        "libexpat1",
        "libfontconfig1",
        "libgbm1",
        "libglib2.0-0",
        "libgtk-3-0",
        "libnspr4",
        "libnss3",
        "libpango-1.0-0",
        "libpangocairo-1.0-0",
        "libstdc++6",
        "libx11-6",
        "libx11-xcb1",
        "libxcb1",
        "libxcomposite1",
        "libxdamage1",
        "libxext6",
        "libxfixes3",
        "libxi6",
        "libxrandr2",
        "libxrender1",
        "libxss1",
        "libxtst6",
        "xdg-utils",
    }
    package_block = script.split("# Update and install necessary packages", 1)[1].split(
        "# Install Apptainer", 1
    )[0]

    assert chrome_runtime_packages <= set(shlex.split(package_block.replace("\\\n", " ")))
    assert "--no-sandbox" not in script


def test_rhel_dragen_post_install_removes_cromwell_and_requires_womtool() -> None:
    source = (REPO_ROOT / "config/day_cluster/post_install_rhel8_dragen.sh").read_text(
        encoding="utf-8"
    )
    packaged = (
        REPO_ROOT / "daylily_ec/resources/payload/config/day_cluster/post_install_rhel8_dragen.sh"
    ).read_text(encoding="utf-8")

    for script in (source, packaged):
        assert 'wait_for_dir "${runtime_assets_root}/tool_specific_resources"' in script
        assert "wait_for_file()" in script
        assert (
            'wait_for_file "${runtime_assets_root}/tool_specific_resources/womtool_87.jar"'
            in script
        )
        assert "cromwell_87.jar" not in script
        assert "cromwell.jar" not in script
        assert "/fsx/analysis_results/cromwell_executions" not in script
        assert "not found or empty after" in script
        assert "install_womtool_link" in script
        assert "dnf_install_with_rpmdb_repair" in script
        assert "RHEL rpm database failure detected during dnf install" in script
        assert "DB_RUNRECOVERY" in script
        assert "configure_dragen_memlock_limits()" in script
        assert 'limits_file="/etc/security/limits.d/99-edico.conf"' in script
        assert "memlock   unlimited" in script
        assert "configure_dragen_memlock_limits\nconfigure_kernel_and_shm" in script
        assert "resolve_cluster_cache_namespace" in script
        assert "aws cloudformation describe-stacks" in script
        assert '"${runtime_assets_root}/cached_envs/conda"' not in script
        assert 'export DAYOA_CLUSTER_CACHE_NAMESPACE="${cluster_cache_namespace}"' in script
        assert "legacy linked Conda environments are forbidden" in script

        assert script.count("\n    prepare_dayoa_environment_cache\n") == 1
        headnode_actions = script.rsplit('if [ "${node_type}" = "HeadNode" ]; then', 1)[1]
        assert "prepare_dayoa_environment_cache" in headnode_actions

    assert source == packaged
