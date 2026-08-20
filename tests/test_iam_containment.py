"""ISS-80: cluster-level IAM containment.

ParallelCluster creates 18 roles and 16 instance profiles per cluster — 300 IAM
write calls across one create/delete lifecycle. Two cluster-config settings are
what make granting that safe:

  PermissionsBoundary  caps every role PC creates, so even AdministratorAccess
                       attached to a cluster role yields no more than the ceiling
  ResourcePrefix       puts those roles under /daylily-pc/, so a deployer's
                       iam:CreateRole grant can be scoped to a namespace

Without these the DaylilyDeployer policy's iam:PermissionsBoundary condition can
never be satisfied and every CreateRole is denied — the deploy fails deep in the
compute-fleet stack, reading like a permissions bug rather than a config gap.

Containment is opt-in: with DAY_IAM_PERMISSIONS_BOUNDARY unset the block renders
to nothing and the parsed cluster config is identical to before. That property is
what makes this safe to land ahead of the boundary being referenced anywhere.
"""
import re
from pathlib import Path

import pytest
import yaml

from daylily_ec.render.renderer import ALL_SUBSTITUTION_KEYS
from daylily_ec.workflow.create_cluster import (
    DEFAULT_IAM_RESOURCE_PREFIX,
    IAM_BOUNDARY_ENV_VAR,
    IAM_RESOURCE_PREFIX_ENV_VAR,
    render_iam_cluster_block,
)

ROOT = Path(__file__).resolve().parents[1]
REL = "config/day_cluster/intel/us-west-2/us-west-2d/prod_cluster_intel_spot_us-west-2d.yaml"
TEMPLATES = (ROOT / REL, ROOT / "daylily_ec/resources/payload" / REL)

LIVE_BOUNDARY = "arn:aws:iam::108782052779:policy/daylily/DayecClusterNodeBoundary"


def _parse(text: str, block: str):
    t = text.replace("${REGSUB_IAM_CLUSTER_BLOCK}", block)
    return yaml.safe_load(re.sub(r"\$\{[A-Z_0-9]+\}", "placeholder", t))


class TestOptIn:
    def test_unset_renders_nothing(self, monkeypatch):
        """Emitting a boundary that does not exist would fail every create."""
        monkeypatch.delenv(IAM_BOUNDARY_ENV_VAR, raising=False)
        assert render_iam_cluster_block() == ""

    def test_env_enables_it(self, monkeypatch):
        monkeypatch.setenv(IAM_BOUNDARY_ENV_VAR, LIVE_BOUNDARY)
        monkeypatch.delenv(IAM_RESOURCE_PREFIX_ENV_VAR, raising=False)
        block = render_iam_cluster_block()
        assert f"PermissionsBoundary: {LIVE_BOUNDARY}" in block
        assert f"ResourcePrefix: {DEFAULT_IAM_RESOURCE_PREFIX}" in block

    def test_explicit_argument_beats_env(self, monkeypatch):
        monkeypatch.setenv(IAM_BOUNDARY_ENV_VAR, "arn:from:env")
        assert "arn:explicit" in render_iam_cluster_block("arn:explicit")

    def test_prefix_override(self, monkeypatch):
        monkeypatch.setenv(IAM_BOUNDARY_ENV_VAR, LIVE_BOUNDARY)
        monkeypatch.setenv(IAM_RESOURCE_PREFIX_ENV_VAR, "/custom-path/")
        assert "ResourcePrefix: /custom-path/" in render_iam_cluster_block()

    def test_resource_prefix_is_a_valid_iam_path(self):
        """IAM requires a path to start and end with '/'."""
        assert DEFAULT_IAM_RESOURCE_PREFIX.startswith("/")
        assert DEFAULT_IAM_RESOURCE_PREFIX.endswith("/")

    def test_leading_newline(self):
        """The token sits inside a YAML comment; the newline escapes it."""
        assert render_iam_cluster_block("arn:x").startswith("\n")


class TestTemplate:
    def test_token_registered(self):
        assert "REGSUB_IAM_CLUSTER_BLOCK" in ALL_SUBSTITUTION_KEYS

    @pytest.mark.parametrize("t", TEMPLATES, ids=("source", "payload"))
    def test_token_present_and_commented(self, t):
        """A bare token on its own line breaks raw YAML loads of the template."""
        text = t.read_text()
        assert "${REGSUB_IAM_CLUSTER_BLOCK}" in text
        line = next(l for l in text.splitlines() if "${REGSUB_IAM_CLUSTER_BLOCK}" in l)
        assert line.lstrip().startswith("#"), f"token must be commented, got: {line!r}"

    @pytest.mark.parametrize("t", TEMPLATES, ids=("source", "payload"))
    def test_unrendered_template_is_valid_yaml(self, t):
        yaml.safe_load(re.sub(r"\$\{[A-Z_0-9]+\}", "placeholder", t.read_text()))

    def test_payload_copy_matches(self):
        assert TEMPLATES[0].read_text() == TEMPLATES[1].read_text()


class TestRenderedDocument:
    def test_disabled_document_has_no_iam_key(self):
        doc = _parse(TEMPLATES[0].read_text(), "")
        assert "Iam" not in doc

    def test_enabled_document_carries_the_boundary(self):
        block = render_iam_cluster_block(LIVE_BOUNDARY, DEFAULT_IAM_RESOURCE_PREFIX)
        doc = _parse(TEMPLATES[0].read_text(), block)
        assert doc["Iam"] == {
            "PermissionsBoundary": LIVE_BOUNDARY,
            "ResourcePrefix": DEFAULT_IAM_RESOURCE_PREFIX,
        }

    def test_enabling_changes_nothing_else(self):
        """The regression that matters: containment must be additive."""
        off = _parse(TEMPLATES[0].read_text(), "")
        on = _parse(TEMPLATES[0].read_text(), render_iam_cluster_block(LIVE_BOUNDARY))
        assert {k: v for k, v in on.items() if k != "Iam"} == off
