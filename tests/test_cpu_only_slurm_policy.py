from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from daylily_ec.workflow.create_cluster import (
    CPU_ONLY_SLURM_CUSTOM_SETTINGS,
    validate_cpu_only_slurm_contract,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "config/day_cluster"
PAYLOAD_ROOT = REPO_ROOT / "daylily_ec/resources/payload/config/day_cluster"


def _slurm_templates(root: Path) -> list[tuple[Path, dict]]:
    templates: list[tuple[Path, dict]] = []
    for path in sorted((*root.rglob("*.yaml"), *root.rglob("*.yml"))):
        text = path.read_text(encoding="utf-8")
        if "Scheduler: slurm" not in text and "SlurmQueues:" not in text:
            continue
        payload = yaml.safe_load(text)
        scheduling = payload.get("Scheduling") if isinstance(payload, dict) else None
        if isinstance(scheduling, dict) and scheduling.get("Scheduler") == "slurm":
            templates.append((path, payload))
    return templates


def test_every_source_and_payload_slurm_template_is_cpu_only() -> None:
    source_templates = _slurm_templates(SOURCE_ROOT)
    payload_templates = _slurm_templates(PAYLOAD_ROOT)

    assert len(source_templates) == 32
    assert len(payload_templates) == 27
    for path, payload in (*source_templates, *payload_templates):
        assert "SchedulableMemory" not in path.read_text(encoding="utf-8"), path
        settings = payload["Scheduling"]["SlurmSettings"]
        assert settings["EnableMemoryBasedScheduling"] is False, path
        assert settings["CustomSlurmSettings"] == CPU_ONLY_SLURM_CUSTOM_SETTINGS, path
        queues = payload["Scheduling"]["SlurmQueues"]
        assert queues, path
        for queue in queues:
            assert queue["JobExclusiveAllocation"] is False, (path, queue.get("Name"))
            for resource in queue.get("ComputeResources", []):
                assert "SchedulableMemory" not in resource, (path, queue.get("Name"))

        if "archive_do_not_use" not in path.parts:
            validate_cpu_only_slurm_contract(path)


def test_all_packaged_slurm_templates_match_their_sources() -> None:
    for payload_path, _payload in _slurm_templates(PAYLOAD_ROOT):
        relative_path = payload_path.relative_to(PAYLOAD_ROOT)
        source_path = SOURCE_ROOT / relative_path
        assert source_path.is_file(), relative_path
        assert payload_path.read_bytes() == source_path.read_bytes(), relative_path


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (
            lambda payload: payload["Scheduling"]["SlurmSettings"].__setitem__(
                "EnableMemoryBasedScheduling", True
            ),
            "must be false",
        ),
        (
            lambda payload: payload["Scheduling"]["SlurmSettings"].pop("CustomSlurmSettings"),
            "must enable JobSubmitPlugins",
        ),
        (
            lambda payload: payload["Scheduling"]["SlurmQueues"][0].__setitem__(
                "JobExclusiveAllocation", True
            ),
            "JobExclusiveAllocation false",
        ),
        (
            lambda payload: payload["HeadNode"]["CustomActions"].pop("OnNodeStart"),
            "OnNodeStart must install job_submit.lua",
        ),
        (
            lambda payload: payload["Scheduling"]["SlurmQueues"][0]["ComputeResources"][
                0
            ].__setitem__("SchedulableMemory", 1),
            "must not define SchedulableMemory",
        ),
    ),
)
def test_cpu_only_validator_rejects_contract_regressions(
    tmp_path: Path,
    mutation,
    message: str,
) -> None:
    source_path = (
        SOURCE_ROOT
        / "sentieon-single/us-west-2/us-west-2c/prod_cluster_sentieon-single_us-west-2c.yaml"
    )
    payload = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    mutation(payload)
    candidate = tmp_path / "cluster.yaml"
    candidate.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        validate_cpu_only_slurm_contract(candidate)


def test_cpu_only_boot_assets_are_bundled_and_do_not_mutate_slurm_config() -> None:
    asset_names = (
        "install_slurm_job_submit_policy.sh",
        "job_submit.lua",
        "post_install_almalinux8_dragen.sh",
        "post_install_rhel8_dragen.sh",
        "post_install_ubuntu_combined.sh",
        "sbatch",
    )
    for name in asset_names:
        source = SOURCE_ROOT / name
        payload = PAYLOAD_ROOT / name
        assert source.is_file(), name
        assert payload.is_file(), name
        assert source.read_bytes() == payload.read_bytes(), name

    assert not (SOURCE_ROOT / "update_s3_day_boot_script_refs.sh").exists()
    assert not (PAYLOAD_ROOT / "update_s3_day_boot_script_refs.sh").exists()

    installer = (SOURCE_ROOT / "install_slurm_job_submit_policy.sh").read_text(encoding="utf-8")
    assert "/opt/slurm/etc/job_submit.lua" in installer
    assert "slurm.conf" not in installer
    assert "restart slurm" not in installer

    for name in ("post_install_ubuntu_combined.sh", "post_install_rhel8_dragen.sh"):
        script = (SOURCE_ROOT / name).read_text(encoding="utf-8")
        assert "install_slurm_submission_policy" in script
        assert "install_slurm_job_submit_policy.sh" in script
        assert "/opt/slurm/etc/scripts/prolog.d" in script
        assert "/opt/slurm/etc/scripts/epilog.d" in script
        assert "50_daylily_job_tags" in script
        assert "/opt/slurm/etc/slurm.conf" not in script
        assert "systemctl restart slurm" not in script

    alma = (SOURCE_ROOT / "post_install_almalinux8_dragen.sh").read_text(encoding="utf-8")
    assert "post_install_rhel8_dragen.sh" in alma


def test_lua_policy_checks_submit_modify_and_slurm_unset_values() -> None:
    policy = (SOURCE_ROOT / "job_submit.lua").read_text(encoding="utf-8")
    assert "function slurm_job_submit" in policy
    assert "function slurm_job_modify" in policy
    assert "job_desc.min_mem_per_node" in policy
    assert "job_desc.min_mem_per_cpu" in policy
    assert "job_desc.mem_per_tres" in policy
    assert "slurm.NO_VAL64" in policy
    assert "return slurm.ERROR" in policy
    assert "return slurm.SUCCESS" in policy
