from __future__ import annotations

import pytest

from daylily_ec.bjuice_preval_config import BjuiceConfigError, _dayoa_read_group_label


def test_dayoa_read_group_label_normalizes_source_run_ids_without_underscores() -> None:
    assert (
        _dayoa_read_group_label(
            "20260618_LH01106_0011_A23MFMCLT3",
            field_name="ILMN run_id",
        )
        == "20260618-LH01106-0011-A23MFMCLT3"
    )
    assert (
        _dayoa_read_group_label(
            "20260616.0040_3B_PBK89197_822a87b5",
            field_name="ONT run_id",
        )
        == "20260616-0040-3B-PBK89197-822a87b5"
    )


def test_dayoa_read_group_label_rejects_values_without_safe_content() -> None:
    with pytest.raises(BjuiceConfigError, match="cannot be converted"):
        _dayoa_read_group_label("___...", field_name="run_id")
