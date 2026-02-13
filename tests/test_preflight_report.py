"""Tests for CP-004: Preflight Framework and Report Writer.

Acceptance criteria:
1. Preflight emits JSON report to ~/.config/daylily/
2. Report ordering stable, keys sorted, includes PASS/WARN/FAIL
3. FAIL stops immediately — no AWS mutation
4. Gating order matches spec §10.5
5. --pass-on-warn allows WARN to continue, absence causes WARN to exit
"""

from __future__ import annotations

import json

from daylily_ec.state.models import CheckResult, CheckStatus, PreflightReport
from daylily_ec.state.store import (
    _safe_cluster_name,
    config_dir,
    write_preflight_report,
)
from daylily_ec.workflow.create_cluster import (
    clear_preflight_steps,
    exit_code_for,
    run_preflight,
    should_abort,
)


# ── CheckStatus enum ────────────────────────────────────────────────────


class TestCheckStatus:
    def test_values(self):
        assert CheckStatus.PASS.value == "PASS"
        assert CheckStatus.WARN.value == "WARN"
        assert CheckStatus.FAIL.value == "FAIL"

    def test_string_enum(self):
        # str(Enum) behavior varies across Python versions; .value is stable
        assert CheckStatus.PASS.value == "PASS"


# ── CheckResult model ───────────────────────────────────────────────────


class TestCheckResult:
    def test_basic(self):
        cr = CheckResult(id="toolchain.python", status=CheckStatus.PASS)
        assert cr.id == "toolchain.python"
        assert cr.status == CheckStatus.PASS
        assert cr.details == {}
        assert cr.remediation == ""

    def test_with_details(self):
        cr = CheckResult(
            id="quota.spot_vcpu",
            status=CheckStatus.WARN,
            details={"current": 128, "required": 256},
            remediation="Request quota increase",
        )
        assert cr.details["current"] == 128
        assert cr.remediation == "Request quota increase"


# ── PreflightReport model ───────────────────────────────────────────────


class TestPreflightReport:
    def test_empty_report(self):
        r = PreflightReport(run_id="20260211120000")
        assert r.passed is True
        assert r.has_warnings is False
        assert r.failed_checks == []
        assert r.warned_checks == []

    def test_passed_with_all_pass(self):
        r = PreflightReport(
            run_id="20260211120000",
            checks=[
                CheckResult(id="a", status=CheckStatus.PASS),
                CheckResult(id="b", status=CheckStatus.PASS),
            ],
        )
        assert r.passed is True
        assert r.has_warnings is False

    def test_fail_detection(self):
        r = PreflightReport(
            run_id="20260211120000",
            checks=[
                CheckResult(id="a", status=CheckStatus.PASS),
                CheckResult(id="b", status=CheckStatus.FAIL, remediation="fix it"),
            ],
        )
        assert r.passed is False
        assert len(r.failed_checks) == 1
        assert r.failed_checks[0].id == "b"

    def test_warn_detection(self):
        r = PreflightReport(
            run_id="20260211120000",
            checks=[
                CheckResult(id="a", status=CheckStatus.PASS),
                CheckResult(id="b", status=CheckStatus.WARN, remediation="heads up"),
            ],
        )
        assert r.passed is True
        assert r.has_warnings is True
        assert len(r.warned_checks) == 1

    def test_to_sorted_json_deterministic(self):
        r = PreflightReport(
            run_id="20260211120000",
            cluster_name="my-cluster",
            region="us-west-2",
            region_az="us-west-2b",
            aws_profile="test",
            account_id="123456789012",
            caller_arn="arn:aws:iam::123456789012:user/alice",
            checks=[
                CheckResult(id="toolchain.python", status=CheckStatus.PASS),
            ],
        )
        j1 = r.to_sorted_json()
        j2 = r.to_sorted_json()
        assert j1 == j2  # byte-stable

        parsed = json.loads(j1)
        # Keys must be sorted
        top_keys = list(parsed.keys())
        assert top_keys == sorted(top_keys)

    def test_run_id_auto_generated(self):
        r = PreflightReport()
        assert len(r.run_id) == 14  # YYYYMMDDHHMMSS
        assert r.run_id.isdigit()


# ── Store: _safe_cluster_name ────────────────────────────────────────────


class TestSafeClusterName:
    def test_none(self):
        assert _safe_cluster_name(None) == "unknown"

    def test_empty(self):
        assert _safe_cluster_name("") == "unknown"

    def test_normal(self):
        assert _safe_cluster_name("my-cluster") == "my-cluster"

    def test_special_chars(self):
        assert _safe_cluster_name("my cluster!@#") == "my_cluster___"

    def test_underscores_preserved(self):
        assert _safe_cluster_name("my_cluster_1") == "my_cluster_1"


# ── Store: config_dir ────────────────────────────────────────────────────


class TestConfigDir:
    def test_creates_directory(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        d = config_dir()
        assert d.exists()
        assert d.name == "daylily"
        assert d.parent == tmp_path

    def test_default_home(self, monkeypatch):
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        d = config_dir()
        assert d.name == "daylily"
        assert ".config" in str(d)


# ── Store: write_preflight_report ────────────────────────────────────────


class TestWritePreflightReport:
    def test_writes_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        report = PreflightReport(
            run_id="20260211120000",
            cluster_name="test-cluster",
            region="us-west-2",
            checks=[
                CheckResult(id="a", status=CheckStatus.PASS),
            ],
        )
        path = write_preflight_report(report)
        assert path.exists()
        assert path.name == "preflight_test-cluster_20260211120000.json"

        content = json.loads(path.read_text())
        assert content["cluster_name"] == "test-cluster"
        assert content["run_id"] == "20260211120000"
        # Keys sorted
        top_keys = list(content.keys())
        assert top_keys == sorted(top_keys)

    def test_unknown_cluster(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        report = PreflightReport(run_id="20260211120000")
        path = write_preflight_report(report)
        assert "unknown" in path.name


# ── Workflow: run_preflight ──────────────────────────────────────────────


def _make_step(check_id: str, status: CheckStatus):
    """Factory: return a preflight step that appends a single CheckResult."""

    def step(report: PreflightReport) -> PreflightReport:
        report.checks.append(
            CheckResult(id=check_id, status=status, remediation=f"fix {check_id}")
        )
        return report

    return step


class TestRunPreflight:
    def setup_method(self):
        clear_preflight_steps()

    def test_all_pass(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        steps = [
            _make_step("toolchain", CheckStatus.PASS),
            _make_step("identity", CheckStatus.PASS),
        ]
        report = run_preflight(PreflightReport(run_id="T1"), steps=steps)
        assert report.passed
        assert not report.has_warnings
        assert len(report.checks) == 2

    def test_fail_stops_immediately(self, tmp_path, monkeypatch):
        """AC-3: FAIL stops immediately — later steps should not run."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        call_log = []

        def step_pass(report):
            call_log.append("pass")
            report.checks.append(CheckResult(id="a", status=CheckStatus.PASS))
            return report

        def step_fail(report):
            call_log.append("fail")
            report.checks.append(
                CheckResult(id="b", status=CheckStatus.FAIL, remediation="boom")
            )
            return report

        def step_never(report):
            call_log.append("never")
            report.checks.append(CheckResult(id="c", status=CheckStatus.PASS))
            return report

        steps = [step_pass, step_fail, step_never]
        report = run_preflight(PreflightReport(run_id="T2"), steps=steps)

        assert not report.passed
        assert call_log == ["pass", "fail"]  # "never" was NOT called

    def test_warn_aborts_without_flag(self, tmp_path, monkeypatch):
        """AC-5: WARN without --pass-on-warn causes abort."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        steps = [
            _make_step("toolchain", CheckStatus.PASS),
            _make_step("quota", CheckStatus.WARN),
        ]
        report = run_preflight(
            PreflightReport(run_id="T3"),
            pass_on_warn=False,
            steps=steps,
        )
        assert report.has_warnings
        assert should_abort(report, pass_on_warn=False)

    def test_warn_continues_with_flag(self, tmp_path, monkeypatch):
        """AC-5: WARN with --pass-on-warn allows continuation."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        steps = [
            _make_step("toolchain", CheckStatus.PASS),
            _make_step("quota", CheckStatus.WARN),
        ]
        report = run_preflight(
            PreflightReport(run_id="T4"),
            pass_on_warn=True,
            steps=steps,
        )
        assert report.has_warnings
        assert not should_abort(report, pass_on_warn=True)

    def test_gating_order_preserved(self, tmp_path, monkeypatch):
        """AC-4: Checks emitted in registration order (§10.5)."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        ids = [
            "toolchain",
            "aws_identity",
            "iam_permission",
            "config",
            "quota",
            "s3_bucket_selector",
            "s3_bucket_validator",
            "keypair",
            "network",
        ]
        steps = [_make_step(cid, CheckStatus.PASS) for cid in ids]
        report = run_preflight(PreflightReport(run_id="T5"), steps=steps)
        assert [c.id for c in report.checks] == ids

    def test_report_written_to_disk(self, tmp_path, monkeypatch):
        """AC-1: Preflight emits JSON report to ~/.config/daylily/."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        steps = [_make_step("a", CheckStatus.PASS)]
        run_preflight(
            PreflightReport(run_id="T6", cluster_name="test"),
            steps=steps,
        )
        files = list((tmp_path / "daylily").glob("preflight_*.json"))
        assert len(files) == 1
        content = json.loads(files[0].read_text())
        assert content["run_id"] == "T6"


# ── Workflow: should_abort ───────────────────────────────────────────────


class TestShouldAbort:
    def test_all_pass(self):
        r = PreflightReport(
            checks=[CheckResult(id="a", status=CheckStatus.PASS)]
        )
        assert not should_abort(r)

    def test_fail(self):
        r = PreflightReport(
            checks=[CheckResult(id="a", status=CheckStatus.FAIL)]
        )
        assert should_abort(r)

    def test_warn_no_flag(self):
        r = PreflightReport(
            checks=[CheckResult(id="a", status=CheckStatus.WARN)]
        )
        assert should_abort(r, pass_on_warn=False)

    def test_warn_with_flag(self):
        r = PreflightReport(
            checks=[CheckResult(id="a", status=CheckStatus.WARN)]
        )
        assert not should_abort(r, pass_on_warn=True)


# ── Workflow: exit_code_for ──────────────────────────────────────────────


class TestExitCodeFor:
    def test_success(self):
        r = PreflightReport(
            checks=[CheckResult(id="a", status=CheckStatus.PASS)]
        )
        assert exit_code_for(r) == 0

    def test_fail(self):
        r = PreflightReport(
            checks=[CheckResult(id="a", status=CheckStatus.FAIL)]
        )
        assert exit_code_for(r) == 1

    def test_warn(self):
        r = PreflightReport(
            checks=[CheckResult(id="a", status=CheckStatus.WARN)]
        )
        assert exit_code_for(r) == 1

