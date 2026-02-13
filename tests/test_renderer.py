"""Tests for daylily_ec.render.renderer — CP-011."""

from __future__ import annotations

from pathlib import Path

import pytest

from daylily_ec.render.renderer import (
    ALL_SUBSTITUTION_KEYS,
    CONFIG_DIR,
    REQUIRED_KEYS,
    render_template,
    write_init_artifacts,
)


# ── fixtures ─────────────────────────────────────────────────────────

MINI_TEMPLATE = (
    "Region: ${REGSUB_REGION}\n"
    "SubnetPublic: ${REGSUB_PUB_SUBNET}\n"
    "SubnetPrivate: ${REGSUB_PRIVATE_SUBNET}\n"
    "ClusterName: ${REGSUB_CLUSTER_NAME}\n"
)

MINIMAL_SUBS = {
    "REGSUB_REGION": "us-west-2",
    "REGSUB_PUB_SUBNET": "subnet-aaa",
    "REGSUB_PRIVATE_SUBNET": "subnet-bbb",
    "REGSUB_CLUSTER_NAME": "test-cluster",
}


def _full_subs() -> dict[str, str]:
    """Return a substitutions dict covering all 29 known keys."""
    return {k: f"val-{k}" for k in ALL_SUBSTITUTION_KEYS}


# ── TestConstants ────────────────────────────────────────────────────


class TestConstants:
    def test_all_keys_count(self):
        assert len(ALL_SUBSTITUTION_KEYS) == 29

    def test_required_keys_subset(self):
        assert REQUIRED_KEYS.issubset(ALL_SUBSTITUTION_KEYS)

    def test_required_keys_count(self):
        assert len(REQUIRED_KEYS) == 4

    def test_config_dir_ends_with_daylily(self):
        assert CONFIG_DIR.name == "daylily"


# ── TestRenderTemplate ───────────────────────────────────────────────


class TestRenderTemplate:
    def test_basic_substitution(self):
        result = render_template(MINI_TEMPLATE, MINIMAL_SUBS)
        assert "us-west-2" in result
        assert "${REGSUB_REGION}" not in result

    def test_all_tokens_replaced(self):
        result = render_template(MINI_TEMPLATE, MINIMAL_SUBS)
        assert "${" not in result

    def test_preserves_non_token_text(self):
        result = render_template(MINI_TEMPLATE, MINIMAL_SUBS)
        assert result.startswith("Region: us-west-2\n")

    def test_missing_required_key_raises(self):
        subs = dict(MINIMAL_SUBS)
        del subs["REGSUB_REGION"]
        with pytest.raises(ValueError, match="REGSUB_REGION"):
            render_template(MINI_TEMPLATE, subs)

    def test_empty_required_key_raises(self):
        subs = dict(MINIMAL_SUBS)
        subs["REGSUB_REGION"] = ""
        with pytest.raises(ValueError, match="REGSUB_REGION"):
            render_template(MINI_TEMPLATE, subs)

    def test_custom_required_keys(self):
        # Only require REGSUB_REGION — should pass with just that
        subs = {"REGSUB_REGION": "eu-west-1"}
        result = render_template(
            "Region: ${REGSUB_REGION}\n",
            subs,
            required_keys=frozenset({"REGSUB_REGION"}),
        )
        assert result == "Region: eu-west-1\n"

    def test_no_required_keys(self):
        result = render_template(
            "Hello: ${REGSUB_REGION}\n",
            {},
            required_keys=frozenset(),
        )
        assert result == "Hello: ${REGSUB_REGION}\n"

    def test_extra_keys_ignored(self):
        subs = {**MINIMAL_SUBS, "REGSUB_EXTRA": "ignored"}
        result = render_template(MINI_TEMPLATE, subs)
        assert "ignored" not in result


# ── TestByteStability ────────────────────────────────────────────────


class TestByteStability:
    def test_identical_inputs_identical_output(self):
        a = render_template(MINI_TEMPLATE, MINIMAL_SUBS)
        b = render_template(MINI_TEMPLATE, MINIMAL_SUBS)
        assert a == b

    def test_full_subs_stable(self):
        tpl = "".join(f"{k}: ${{{k}}}\n" for k in sorted(ALL_SUBSTITUTION_KEYS))
        subs = _full_subs()
        a = render_template(tpl, subs, required_keys=frozenset())
        b = render_template(tpl, subs, required_keys=frozenset())
        assert a == b


# ── TestAllSubstitutionKeys ──────────────────────────────────────────


class TestAllSubstitutionKeys:
    def test_all_keys_substituted(self):
        tpl = "".join(f"k: ${{{k}}}\n" for k in sorted(ALL_SUBSTITUTION_KEYS))
        subs = _full_subs()
        result = render_template(tpl, subs, required_keys=frozenset())
        assert "${" not in result
        for k in ALL_SUBSTITUTION_KEYS:
            assert f"val-{k}" in result

    def test_known_keys_present(self):
        expected = {
            "REGSUB_REGION", "REGSUB_PUB_SUBNET", "REGSUB_KEYNAME",
            "REGSUB_S3_BUCKET_INIT", "REGSUB_S3_BUCKET_NAME",
            "REGSUB_S3_IAM_POLICY", "REGSUB_PRIVATE_SUBNET",
            "REGSUB_S3_BUCKET_REF", "REGSUB_XMR_MINE",
            "REGSUB_XMR_POOL_URL", "REGSUB_XMR_WALLET",
            "REGSUB_FSX_SIZE", "REGSUB_DETAILED_MONITORING",
            "REGSUB_CLUSTER_NAME", "REGSUB_USERNAME", "REGSUB_PROJECT",
            "REGSUB_DELETE_LOCAL_ROOT", "REGSUB_SAVE_FSX",
            "REGSUB_ENFORCE_BUDGET", "REGSUB_AWS_ACCOUNT_ID",
            "REGSUB_ALLOCATION_STRATEGY", "REGSUB_DAYLILY_GIT_DEETS",
            "REGSUB_MAX_COUNT_8I", "REGSUB_MAX_COUNT_128I",
            "REGSUB_MAX_COUNT_192I", "REGSUB_HEADNODE_INSTANCE_TYPE",
            "REGSUB_HEARTBEAT_EMAIL", "REGSUB_HEARTBEAT_SCHEDULE",
            "REGSUB_HEARTBEAT_SCHEDULER_ROLE_ARN",
        }
        assert ALL_SUBSTITUTION_KEYS == expected


# ── TestWriteInitArtifacts ───────────────────────────────────────────


class TestWriteInitArtifacts:
    def _write_template(self, tmp_path: Path) -> Path:
        tpl = tmp_path / "template.yaml"
        tpl.write_text(MINI_TEMPLATE, encoding="utf-8")
        return tpl

    def test_creates_both_files(self, tmp_path: Path):
        tpl = self._write_template(tmp_path)
        out_dir = tmp_path / "out"
        yaml_init, init_tpl = write_init_artifacts(
            "prod", "20260211140000", str(tpl), MINIMAL_SUBS,
            config_dir=out_dir,
        )
        assert Path(yaml_init).is_file()
        assert Path(init_tpl).is_file()

    def test_yaml_init_is_raw_copy(self, tmp_path: Path):
        tpl = self._write_template(tmp_path)
        out_dir = tmp_path / "out"
        yaml_init, _ = write_init_artifacts(
            "prod", "20260211140000", str(tpl), MINIMAL_SUBS,
            config_dir=out_dir,
        )
        assert Path(yaml_init).read_text() == MINI_TEMPLATE

    def test_init_template_is_rendered(self, tmp_path: Path):
        tpl = self._write_template(tmp_path)
        out_dir = tmp_path / "out"
        _, init_tpl = write_init_artifacts(
            "prod", "20260211140000", str(tpl), MINIMAL_SUBS,
            config_dir=out_dir,
        )
        content = Path(init_tpl).read_text()
        assert "${" not in content
        assert "us-west-2" in content

    def test_naming_convention(self, tmp_path: Path):
        tpl = self._write_template(tmp_path)
        out_dir = tmp_path / "out"
        yaml_init, init_tpl = write_init_artifacts(
            "mycluster", "20260211", str(tpl), MINIMAL_SUBS,
            config_dir=out_dir,
        )
        assert "mycluster_cluster_20260211.yaml.init" in yaml_init
        assert "mycluster_init_template_20260211.yaml" in init_tpl

    def test_creates_config_dir(self, tmp_path: Path):
        tpl = self._write_template(tmp_path)
        out_dir = tmp_path / "deep" / "nested"
        write_init_artifacts(
            "prod", "ts", str(tpl), MINIMAL_SUBS, config_dir=out_dir,
        )
        assert out_dir.is_dir()

    def test_missing_template_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="Template not found"):
            write_init_artifacts(
                "prod", "ts", "/no/such/file.yaml", MINIMAL_SUBS,
                config_dir=tmp_path,
            )

    def test_missing_required_key_propagates(self, tmp_path: Path):
        tpl = self._write_template(tmp_path)
        subs = dict(MINIMAL_SUBS)
        del subs["REGSUB_REGION"]
        with pytest.raises(ValueError, match="REGSUB_REGION"):
            write_init_artifacts(
                "prod", "ts", str(tpl), subs, config_dir=tmp_path,
            )

    def test_byte_stable_artifacts(self, tmp_path: Path):
        tpl = self._write_template(tmp_path)
        d1 = tmp_path / "run1"
        d2 = tmp_path / "run2"
        _, p1 = write_init_artifacts(
            "c", "ts", str(tpl), MINIMAL_SUBS, config_dir=d1,
        )
        _, p2 = write_init_artifacts(
            "c", "ts", str(tpl), MINIMAL_SUBS, config_dir=d2,
        )
        assert Path(p1).read_bytes() == Path(p2).read_bytes()

