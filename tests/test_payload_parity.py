"""Parity between `config/` and the runtime-resolved `daylily_ec/resources/payload/` tree.

The payload tree is a duplicate of `config/` that DYEC resolves at runtime, so a
template edited on one side only ships a stale copy to whichever code path reads
the other. Nothing enforced this before; the drift is silent and reaches
production as a wrong cluster shape rather than an error.

Phase 2 of the scoped-role work edits
`config/day_cluster/intel/us-west-2/us-west-2d/prod_cluster_intel_spot_us-west-2d.yaml`,
so this guard is a prerequisite for that change, not general hygiene.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "config" / "day_cluster"
PAYLOAD = ROOT / "daylily_ec" / "resources" / "payload" / "config" / "day_cluster"

# Files present in config/ but absent from payload/ as of 2026-08-19. This is
# PRE-EXISTING drift, not something this test introduced, and it is recorded
# rather than fixed because the DRAGEN templates are outside the scoped-role
# work. Note they are NOT dead: prod_cluster_dragen_pcluster_image_rhel8.yaml is
# referenced by 10 cluster configs and _native_ami_rhel8 by 3, so any code path
# that resolves them from the payload tree will fail to find them.
#
# Shrinking this set is a fix; growing it is a regression.
KNOWN_PAYLOAD_GAPS = frozenset({
    "archive_do_not_use/prod_cluster_nested_spot_mem_scratch.yaml",
    "prod_cluster_dragen_native_ami_rhel8.yaml",
    "prod_cluster_dragen_native_ami_rhel8_nofsx.yaml",
    "prod_cluster_dragen_pcluster_image_rhel8.yaml",
    "prod_cluster_dragen_pcluster_image_rhel8_nofsx.yaml",
})

# Templates the scoped-role work edits. These must exist on both sides, or the
# Phase 2 permissions-boundary block reaches only one of them.
CONTAINMENT_TARGETS = (
    "intel/us-west-2/us-west-2d/prod_cluster_intel_spot_us-west-2d.yaml",
    "intel/us-west-2/us-west-2d/prod_cluster_intel_ondemand_us-west-2d.yaml",
)


def _relative(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


def _shared() -> list[str]:
    return sorted(_relative(SOURCE) & _relative(PAYLOAD))


def test_trees_exist():
    assert SOURCE.is_dir(), f"missing {SOURCE}"
    assert PAYLOAD.is_dir(), f"missing {PAYLOAD}"


def test_no_content_drift():
    """The check that matters: a file in both trees must be byte-identical.

    This is what catches a one-sided template edit — the failure mode that
    silently ships a stale cluster shape.
    """
    drifted = [
        rel for rel in _shared()
        if (SOURCE / rel).read_bytes() != (PAYLOAD / rel).read_bytes()
    ]
    assert not drifted, (
        "config/ and payload/ copies differ — edit both sides:\n  "
        + "\n  ".join(drifted)
    )


def test_no_new_payload_gaps():
    """Source-only files must match the recorded set exactly.

    Fails on a NEW one-sided file (regression) and also when a known gap is
    closed (update KNOWN_PAYLOAD_GAPS in the same commit).
    """
    gaps = _relative(SOURCE) - _relative(PAYLOAD)
    assert gaps == KNOWN_PAYLOAD_GAPS, (
        f"payload gaps changed.\n"
        f"  new (regression) : {sorted(gaps - KNOWN_PAYLOAD_GAPS)}\n"
        f"  closed (update the constant): {sorted(KNOWN_PAYLOAD_GAPS - gaps)}"
    )


def test_no_payload_only_files():
    """The payload tree is a copy; it must not gain files of its own."""
    orphans = _relative(PAYLOAD) - _relative(SOURCE)
    assert not orphans, f"payload-only files: {sorted(orphans)}"


@pytest.mark.parametrize("rel", CONTAINMENT_TARGETS)
def test_containment_targets_present_both_sides(rel):
    """Phase 2 edits these; a missing payload copy makes the boundary partial."""
    assert (SOURCE / rel).is_file(), f"missing source template: {rel}"
    assert (PAYLOAD / rel).is_file(), f"missing payload template: {rel}"
    assert (SOURCE / rel).read_bytes() == (PAYLOAD / rel).read_bytes()
