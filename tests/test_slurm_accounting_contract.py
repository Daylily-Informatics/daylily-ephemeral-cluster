"""Independent public-contract and redaction tests for create-time accounting."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from daylily_ec.aws.slurm_accounting import empty_slurm_accounting_render_blocks
from daylily_ec.config.models import REQUIRED_CONFIG_KEYS
from daylily_ec.render.renderer import render_template
from daylily_ec.state.models import SlurmAccountingOutcome, SlurmAccountingStage
from daylily_ec.state.slurm_accounting import status_message, warning_message
from daylily_ec.state.store import write_slurm_accounting_receipt
from daylily_ec.workflow.postcreate_slurm_accounting import (
    ACCOUNTING_OUTCOME_WARNING,
    run_postcreate_slurm_accounting,
)

LEGACY_CREATE_ACCOUNTING_KEYS = frozenset(
    {
        "slurm_accounting_enabled",
        "slurm_accounting_create_db",
        "slurm_accounting_stack_name",
        "slurm_accounting_database_name",
        "slurm_accounting_db_username",
        "slurm_accounting_instance_type",
    }
)


@pytest.mark.parametrize(
    "relative_path",
    [
        "config/daylily_ephemeral_cluster_template.yaml",
        "daylily_ec/resources/payload/config/daylily_ephemeral_cluster_template.yaml",
    ],
)
def test_create_config_has_no_legacy_accounting_prompt_default_or_required_key(
    relative_path: str,
) -> None:
    root = Path(__file__).resolve().parents[1]
    payload = yaml.safe_load((root / relative_path).read_text(encoding="utf-8"))
    ephemeral = payload["ephemeral_cluster"]

    assert LEGACY_CREATE_ACCOUNTING_KEYS.isdisjoint(ephemeral["config"])
    assert LEGACY_CREATE_ACCOUNTING_KEYS.isdisjoint(ephemeral["template_defaults"])
    assert LEGACY_CREATE_ACCOUNTING_KEYS.isdisjoint(REQUIRED_CONFIG_KEYS)


@pytest.mark.parametrize("requested_mode", ["on", "off"])
@pytest.mark.parametrize(
    "relative_path",
    [
        "config/day_cluster/intel/us-west-2/us-west-2d/prod_cluster_intel_spot_us-west-2d.yaml",
        (
            "daylily_ec/resources/payload/config/day_cluster/intel/us-west-2/"
            "us-west-2d/prod_cluster_intel_spot_us-west-2d.yaml"
        ),
    ],
)
def test_initial_cluster_render_is_accounting_free_for_both_requested_modes(
    requested_mode: str,
    relative_path: str,
) -> None:
    root = Path(__file__).resolve().parents[1]
    template = (root / relative_path).read_text(encoding="utf-8")
    substitutions = {
        "REGSUB_REGION": "us-west-2",
        "REGSUB_PUB_SUBNET": "subnet-public",
        "REGSUB_PRIVATE_SUBNET": "subnet-private",
        "REGSUB_CLUSTER_NAME": "fresh-cluster",
        **empty_slurm_accounting_render_blocks(),
    }

    rendered = render_template(template, substitutions)

    assert requested_mode in {"on", "off"}
    assert "REGSUB_SLURM_ACCOUNTING" not in rendered
    assert "Database:" not in rendered
    assert "AdditionalSecurityGroups:" not in rendered


def test_failure_sentinel_never_reaches_result_warning_status_or_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoint = "mysql://SENTINEL_ENDPOINT.internal:3306/slurm"
    private_ip = "10.99.88.77"
    secret_arn = "arn:aws:secretsmanager:us-west-2:123456789012:secret:SENTINEL_SECRET"
    raw_failure = RuntimeError(f"{endpoint} {private_ip} {secret_arn}")

    def fail_preparation(**_kwargs: object) -> None:
        raise raw_failure

    monkeypatch.setattr(
        "daylily_ec.workflow.attach_slurm_accounting.prepare_slurm_accounting_update",
        fail_preparation,
    )
    monkeypatch.setattr(
        "daylily_ec.workflow.postcreate_slurm_accounting.describe_compute_fleet",
        lambda *_args, **_kwargs: pytest.fail(
            "a preparation failure must not describe or mutate the fleet"
        ),
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    result = run_postcreate_slurm_accounting(
        cluster_name="fresh-cluster",
        region="us-west-2",
        region_az="us-west-2d",
        profile="ursa",
        cluster_configuration=tmp_path / "base-cluster.yaml",
        initial_headnode_instance_id="i-head",
        slurm_accounting="on",
        non_interactive=True,
        create_slurm_accounting_if_missing=False,
        acknowledge_slurm_accounting_create_cost=False,
    )

    assert result.outcome == ACCOUNTING_OUTCOME_WARNING
    receipt = result.to_receipt()
    receipt_path = write_slurm_accounting_receipt(
        receipt,
        cluster_name="fresh-cluster",
        run_id="20260716015218",
    )
    public_surfaces = "\n".join(
        [
            repr(result),
            receipt.model_dump_json(),
            receipt_path.read_text(encoding="utf-8"),
            warning_message(
                SlurmAccountingStage(result.error_stage),
                result.recovery_required,
            ),
            status_message(SlurmAccountingOutcome(result.outcome)),
        ]
    )

    for sentinel in (endpoint, private_ip, secret_arn, "SENTINEL"):
        assert sentinel not in public_surfaces
