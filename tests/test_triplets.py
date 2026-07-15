"""Tests for daylily_ec.config triplet parsing, auto-select, and write-back.

Covers CP-002 acceptance criteria:
1. Load config/daylily_ephemeral_cluster_template.yaml
2. Missing required keys added as [PROMPTUSER, "", ""]
3. Auto-select logic matches Bash exactly
4. Normalization: null/None → "", True/False → "true"/"false"
5. String, list, and map triplet formats all parsed correctly
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from daylily_ec.config.models import (
    ConfigFile,
    REQUIRED_CONFIG_KEYS,
    Triplet,
)
from daylily_ec.config.triplets import (
    ensure_required_keys,
    get_effective_default,
    has_effective_set_value,
    is_auto_select_disabled,
    load_config,
    resolve_derived_max_count,
    resolve_value,
    should_auto_apply,
    write_config,
    write_next_run_template,
)

# ── Triplet parsing (AC-5) ──────────────────────────────────────────────


class TestTripletParsing:
    """Triplet model accepts string, list, and map formats."""

    def test_string_format_promptuser(self):
        t = Triplet.model_validate("PROMPTUSER")
        assert t.action == "PROMPTUSER"
        assert t.default_value == ""
        assert t.set_value == ""

    def test_string_format_usesetvalue(self):
        t = Triplet.model_validate("USESETVALUE")
        assert t.action == "USESETVALUE"

    def test_list_format_full(self):
        t = Triplet.model_validate(["USESETVALUE", "default-val", "subnet-abc123"])
        assert t.action == "USESETVALUE"
        assert t.default_value == "default-val"
        assert t.set_value == "subnet-abc123"

    def test_list_format_partial(self):
        t = Triplet.model_validate(["PROMPTUSER", ""])
        assert t.action == "PROMPTUSER"
        assert t.default_value == ""
        assert t.set_value == ""

    def test_list_format_empty(self):
        t = Triplet.model_validate([])
        assert t.action == "PROMPTUSER"

    def test_map_format(self):
        t = Triplet.model_validate(
            {
                "action": "USESETVALUE",
                "default_value": "",
                "set_value": "subnet-abc123",
            }
        )
        assert t.action == "USESETVALUE"
        assert t.set_value == "subnet-abc123"

    def test_map_format_missing_keys(self):
        t = Triplet.model_validate({"action": "USESETVALUE"})
        assert t.default_value == ""
        assert t.set_value == ""

    def test_none_input(self):
        t = Triplet.model_validate(None)
        assert t.action == "PROMPTUSER"

    def test_list_with_none_elements(self):
        t = Triplet.model_validate([None, None, None])
        assert t.action == "PROMPTUSER"
        assert t.default_value == ""
        assert t.set_value == ""

    def test_to_list_roundtrip(self):
        t = Triplet(action="USESETVALUE", default_value="d", set_value="s")
        assert t.to_list() == ["USESETVALUE", "d", "s"]


# ── Normalization (AC-4) ────────────────────────────────────────────────


class TestNormalization:
    """null/None → '', True/False → 'true'/'false'."""

    def test_null_to_empty(self):
        t = Triplet.model_validate(["PROMPTUSER", "null", "null"])
        assert t.default_value == ""
        assert t.set_value == ""

    def test_none_string_to_empty(self):
        t = Triplet.model_validate(["PROMPTUSER", "None", "None"])
        assert t.default_value == ""
        assert t.set_value == ""

    def test_true_normalized(self):
        t = Triplet.model_validate(["PROMPTUSER", "True", "TRUE"])
        assert t.default_value == "true"
        assert t.set_value == "true"

    def test_false_normalized(self):
        t = Triplet.model_validate(["PROMPTUSER", "False", "FALSE"])
        assert t.default_value == "false"
        assert t.set_value == "false"

    def test_lowercase_true_unchanged(self):
        t = Triplet.model_validate(["PROMPTUSER", "true", "false"])
        assert t.default_value == "true"
        assert t.set_value == "false"


# ── Auto-select logic (AC-3) ────────────────────────────────────────────


class TestAutoSelect:
    """should_auto_apply matches Bash should_auto_apply_config_value."""

    def test_usesetvalue_with_value(self):
        assert should_auto_apply("USESETVALUE", "subnet-123") is True

    def test_usesetvalue_empty_value(self):
        assert should_auto_apply("USESETVALUE", "") is False

    def test_promptuser_with_set_value(self):
        assert should_auto_apply("PROMPTUSER", "subnet-123") is True

    def test_promptuser_no_value(self):
        assert should_auto_apply("PROMPTUSER", "") is False

    def test_promptuser_value_is_promptuser(self):
        assert should_auto_apply("PROMPTUSER", "PROMPTUSER") is False

    def test_disabled_via_env(self, monkeypatch):
        monkeypatch.setenv("DAY_DISABLE_AUTO_SELECT", "1")
        assert should_auto_apply("USESETVALUE", "subnet-123") is False

    def test_not_disabled_when_env_zero(self, monkeypatch):
        monkeypatch.setenv("DAY_DISABLE_AUTO_SELECT", "0")
        assert should_auto_apply("USESETVALUE", "subnet-123") is True

    def test_not_disabled_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("DAY_DISABLE_AUTO_SELECT", raising=False)
        assert should_auto_apply("USESETVALUE", "subnet-123") is True


class TestResolveValue:
    def test_auto_applies(self):
        t = Triplet(action="USESETVALUE", default_value="", set_value="val")
        assert resolve_value(t) == "val"

    def test_returns_empty_when_prompt(self):
        t = Triplet(action="PROMPTUSER", default_value="", set_value="")
        assert resolve_value(t) == ""

    def test_disabled_returns_empty(self, monkeypatch):
        monkeypatch.setenv("DAY_DISABLE_AUTO_SELECT", "1")
        t = Triplet(action="USESETVALUE", default_value="", set_value="val")
        assert resolve_value(t) == ""


# ── has_effective_set_value ────────────────────────────────────────────


class TestHasEffectiveSetValue:
    def test_non_empty_non_prompt(self):
        assert has_effective_set_value("subnet-123") is True

    def test_empty_string(self):
        assert has_effective_set_value("") is False

    def test_promptuser_string(self):
        assert has_effective_set_value("PROMPTUSER") is False


# ── is_auto_select_disabled ───────────────────────────────────────────


class TestIsAutoSelectDisabled:
    def test_disabled(self, monkeypatch):
        monkeypatch.setenv("DAY_DISABLE_AUTO_SELECT", "1")
        assert is_auto_select_disabled() is True

    def test_not_disabled(self, monkeypatch):
        monkeypatch.delenv("DAY_DISABLE_AUTO_SELECT", raising=False)
        assert is_auto_select_disabled() is False

    def test_other_value(self, monkeypatch):
        monkeypatch.setenv("DAY_DISABLE_AUTO_SELECT", "yes")
        assert is_auto_select_disabled() is False


# ── get_effective_default ─────────────────────────────────────────────


class TestGetEffectiveDefault:
    """Cascade: config default_value → template_defaults → fallback."""

    def test_config_default_wins(self):
        cfg = ConfigFile(
            ephemeral_cluster={
                "config": {"fsx_fs_size": ["PROMPTUSER", "4800", ""]},
                "template_defaults": {"fsx_fs_size": "7200"},
            }
        )
        assert get_effective_default(cfg, "fsx_fs_size") == "4800"

    def test_template_default_fallback(self):
        cfg = ConfigFile(
            ephemeral_cluster={
                "config": {"fsx_fs_size": ["PROMPTUSER", "", ""]},
                "template_defaults": {"fsx_fs_size": "7200"},
            }
        )
        assert get_effective_default(cfg, "fsx_fs_size") == "7200"

    def test_explicit_fallback(self):
        cfg = ConfigFile(
            ephemeral_cluster={
                "config": {"fsx_fs_size": ["PROMPTUSER", "", ""]},
                "template_defaults": {},
            }
        )
        assert get_effective_default(cfg, "fsx_fs_size", "9600") == "9600"

    def test_missing_key_uses_fallback(self):
        cfg = ConfigFile(ephemeral_cluster={"config": {}, "template_defaults": {}})
        assert get_effective_default(cfg, "nonexistent", "fb") == "fb"


# ── ensure_required_keys ─────────────────────────────────────────────


class TestEnsureRequiredKeys:
    """Missing keys are added as PROMPTUSER triplets."""

    def test_adds_missing_keys(self):
        cfg = ConfigFile(ephemeral_cluster={"config": {}, "template_defaults": {}})
        added = ensure_required_keys(cfg)
        assert added is True
        for key in REQUIRED_CONFIG_KEYS:
            assert key in cfg.ephemeral_cluster.config
            t = cfg.ephemeral_cluster.config[key]
            assert t.action == "PROMPTUSER"
            assert t.default_value == ""
            assert t.set_value == ""

    def test_no_change_when_all_present(self):
        config_data = {k: ["PROMPTUSER", "", ""] for k in REQUIRED_CONFIG_KEYS}
        cfg = ConfigFile(ephemeral_cluster={"config": config_data, "template_defaults": {}})
        added = ensure_required_keys(cfg)
        assert added is False

    def test_partial_fill(self):
        cfg = ConfigFile(
            ephemeral_cluster={
                "config": {"cluster_name": ["USESETVALUE", "", "my-cluster"]},
                "template_defaults": {},
            }
        )
        ensure_required_keys(cfg)
        # Existing key preserved
        assert cfg.ephemeral_cluster.config["cluster_name"].set_value == "my-cluster"
        # Missing keys added
        assert "budget_amount" in cfg.ephemeral_cluster.config


# ── load_config ──────────────────────────────────────────────────────


class TestLoadConfig:
    """load_config parses YAML files into ConfigFile."""

    def test_load_from_yaml(self, tmp_path):
        p = tmp_path / "test.yaml"
        p.write_text(textwrap.dedent("""\
            ephemeral_cluster:
              config:
                reference_s3_uri: [USESETVALUE, "", "my-bucket"]
                cluster_name: PROMPTUSER
              template_defaults:
                fsx_fs_size: "7200"
        """))
        cfg = load_config(p)
        assert cfg.ephemeral_cluster.config["reference_s3_uri"].set_value == "my-bucket"
        assert cfg.ephemeral_cluster.config["cluster_name"].action == "PROMPTUSER"
        assert cfg.ephemeral_cluster.template_defaults["fsx_fs_size"] == "7200"

    def test_load_nonexistent_returns_empty(self, tmp_path):
        cfg = load_config(tmp_path / "nope.yaml")
        assert cfg.ephemeral_cluster.config == {}

    def test_load_template_file(self):
        """AC-1: load the actual template YAML from the repo."""
        tpl = (
            Path(__file__).resolve().parent.parent
            / "config"
            / "daylily_ephemeral_cluster_template.yaml"
        )
        if not tpl.exists():
            pytest.skip("template file not found")
        cfg = load_config(tpl)
        ec = cfg.ephemeral_cluster
        assert set(ec.config) == set(REQUIRED_CONFIG_KEYS)
        assert "ssh_key_name" not in ec.config
        assert ec.config["export_destination_s3_uri"].action == "PROMPTUSER"
        assert ec.config["slurm_accounting_enabled"].default_value == "false"
        assert ec.config["slurm_accounting_database_name"].default_value == "dayec_slurm_acct"
        assert ec.config["budget_amount"].default_value == "200"
        assert ec.config["allowed_budget_users"].default_value == "ubuntu"
        assert ec.config["global_allowed_budget_users"].default_value == "ubuntu"
        assert ec.config["pcluster_backport_manifest"].default_value == ""
        assert ec.config["dragen_license_secret_arn"].default_value == ""
        assert ec.config["dragen_license_policy_arn"].default_value == ""
        assert ec.config["fsx_deployment_type"].set_value == "PERSISTENT_2"
        assert ec.config["fsx_fs_size"].set_value == "4800"
        assert ec.config["fsx_throughput_mbps_per_tib"].set_value == "250"
        assert ec.config["fsx_lustre_version"].set_value == "2.15"
        assert ec.config["fsx_metadata_mode"].set_value == "AUTOMATIC"
        assert ec.config["fsx_encryption_mode"].set_value == "AWS_MANAGED_FSX"
        assert ec.config["fsx_owner"].set_value == "DYEC"
        assert ec.config["fsx_lifecycle"].set_value == "CLUSTER_BOUND"
        assert ec.config["sweep_protection_tag"].set_value == "ursa-preserve=true"
        assert ec.template_defaults["fsx_fs_size"] == "7200"
        assert ec.template_defaults["max_count_192I_HUGENVME"] == "1"
        assert ec.config["max_count_384I"].default_value == "1"
        assert ec.config["max_count_384I_NVME_R"].default_value == "1"


class TestDerivedMaxCount:
    def test_inherits_parent_when_subtype_has_no_set_value(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {
                        "max_count_128I_C": ["USESETVALUE", "1", ""],
                    }
                }
            }
        )

        assert resolve_derived_max_count(cfg, "max_count_128I_C", 16) == "16"

    def test_explicit_subtype_set_value_wins(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {
                        "max_count_128I_C": ["USESETVALUE", "1", "7"],
                    }
                }
            }
        )

        assert resolve_derived_max_count(cfg, "max_count_128I_C", 16) == "7"

    def test_invalid_explicit_subtype_set_value_fails(self):
        cfg = ConfigFile.model_validate(
            {
                "ephemeral_cluster": {
                    "config": {
                        "max_count_128I_C": ["USESETVALUE", "1", "sixteen"],
                    }
                }
            }
        )

        with pytest.raises(ValueError):
            resolve_derived_max_count(cfg, "max_count_128I_C", 16)


# ── write_config ─────────────────────────────────────────────────────


class TestWriteConfig:
    """write_config serializes back to YAML in list triplet format."""

    def test_roundtrip(self, tmp_path):
        cfg = ConfigFile(
            ephemeral_cluster={
                "config": {
                    "reference_s3_uri": ["USESETVALUE", "def", "my-bucket"],
                    "cluster_name": ["PROMPTUSER", "my-cluster", ""],
                },
                "template_defaults": {"fsx_fs_size": "7200"},
            }
        )
        out = tmp_path / "out.yaml"
        write_config(cfg, out)
        loaded = load_config(out)
        assert loaded.ephemeral_cluster.config["reference_s3_uri"].set_value == "my-bucket"
        assert loaded.ephemeral_cluster.config["cluster_name"].default_value == "my-cluster"
        assert loaded.ephemeral_cluster.template_defaults["fsx_fs_size"] == "7200"

    def test_creates_parent_dirs(self, tmp_path):
        out = tmp_path / "sub" / "dir" / "cfg.yaml"
        cfg = ConfigFile(
            ephemeral_cluster={"config": {"k": ["PROMPTUSER", "", ""]}, "template_defaults": {}}
        )
        write_config(cfg, out)
        assert out.exists()


# ── write_next_run_template ──────────────────────────────────────────


class TestWriteNextRunTemplate:
    """write_next_run_template produces a next-run config with USESETVALUE."""

    def test_basic_template(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DAY_DISABLE_AUTO_SELECT", raising=False)
        cfg = ConfigFile(
            ephemeral_cluster={
                "config": {
                    "reference_s3_uri": ["PROMPTUSER", "", ""],
                    "cluster_name": ["PROMPTUSER", "my-cluster", ""],
                },
                "template_defaults": {},
            }
        )
        final = {"reference_s3_uri": "bucket-a", "cluster_name": "prod-cluster"}
        dest = tmp_path / "next.yaml"
        result = write_next_run_template(cfg, final, dest)
        assert result == dest
        loaded = load_config(dest)
        # Actions become USESETVALUE when auto-select not disabled
        assert loaded.ephemeral_cluster.config["reference_s3_uri"].action == "USESETVALUE"
        assert loaded.ephemeral_cluster.config["reference_s3_uri"].set_value == "bucket-a"
        assert loaded.ephemeral_cluster.config["cluster_name"].set_value == "prod-cluster"

    def test_preserves_action_when_disabled(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DAY_DISABLE_AUTO_SELECT", "1")
        cfg = ConfigFile(
            ephemeral_cluster={
                "config": {"reference_s3_uri": ["PROMPTUSER", "", ""]},
                "template_defaults": {},
            }
        )
        dest = tmp_path / "next.yaml"
        write_next_run_template(cfg, {"reference_s3_uri": "k"}, dest)
        loaded = load_config(dest)
        # Action stays PROMPTUSER because auto-select is disabled
        assert loaded.ephemeral_cluster.config["reference_s3_uri"].action == "PROMPTUSER"

    def test_preserves_template_defaults(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DAY_DISABLE_AUTO_SELECT", raising=False)
        cfg = ConfigFile(
            ephemeral_cluster={
                "config": {"k": ["PROMPTUSER", "", ""]},
                "template_defaults": {"fsx_fs_size": "7200"},
            }
        )
        dest = tmp_path / "next.yaml"
        write_next_run_template(cfg, {"k": "v"}, dest)
        loaded = load_config(dest)
        assert loaded.ephemeral_cluster.template_defaults["fsx_fs_size"] == "7200"
