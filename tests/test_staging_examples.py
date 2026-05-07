from __future__ import annotations

import csv
import os
from pathlib import Path

import pytest

import daylily_ec.stage_samples as module

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = ROOT / "examples" / "staging"
REFERENCE_ROOT = "s3://lsmc-dayoa-omics-analysis-us-west-2/data/"
SEQUENCING_ROOT = "s3://lsmc-ssf-sequencing-data/basecalls/"

EXAMPLES = {
    "ilmn_solo": {
        "rows": 3,
        "unit_fields": ("ILMN_R1_PATH", "ILMN_R2_PATH"),
    },
    "ultima_solo": {
        "rows": 3,
        "unit_fields": (module.ULTIMA_CRAM,),
    },
    "ont_solo": {
        "rows": 3,
        "unit_fields": (module.ONT_CRAM,),
    },
    "ont_fastq_solo": {
        "rows": 3,
        "unit_fields": ("ONT_R1_PATH", "ONT_R2_PATH"),
        "unit_field_values": {"ONT_R2_PATH": "na"},
    },
    "hybrid_ilmn_ont": {
        "rows": 3,
        "unit_fields": ("ILMN_R1_PATH", "ILMN_R2_PATH", module.ONT_CRAM),
    },
    "pacbio_solo": {
        "rows": 3,
        "unit_fields": (module.PB_BAM,),
    },
    "roche_solo": {
        "rows": 3,
        "unit_fields": (module.ROCHE_BAM, module.ROCHE_DOWNSAMPLE_RATIO),
    },
}

SOURCE_PATH_FIELDS = {
    module.PATH_TO_CONCORDANCE,
    module.CONCORDANCE_CONTROL_PATH,
    module.TRUTH_DATA_DIR,
    module.ILMN_R1_FQ,
    module.ILMN_R2_FQ,
    module.PACBIO_R1_FQ,
    module.PACBIO_R2_FQ,
    module.ONT_R1_FQ,
    module.ONT_R2_FQ,
    module.ONT_FASTQ_PREFIX,
    module.UG_R1_FQ,
    module.UG_R2_FQ,
    module.ULTIMA_CRAM,
    module.ONT_CRAM,
    module.PB_BAM,
    module.ONT_BAM,
    module.ROCHE_BAM,
}


def _stage_paths() -> module.StagePaths:
    return module.StagePaths(
        remote_fsx_root="/data/staged_sample_data",
        remote_stage_name="remote_stage_test",
        remote_fsx_stage="/data/staged_sample_data/remote_stage_test",
        remote_s3_stage="s3://bucket/data/staged_sample_data/remote_stage_test",
    )


def _manifest_path(example_name: str) -> Path:
    return EXAMPLE_ROOT / example_name / "analysis_samples_manifest.tsv"


def _read_manifest(example_name: str) -> tuple[list[str], list[dict[str, str]]]:
    path = _manifest_path(example_name)
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        assert reader.fieldnames is not None
        rows = [
            {key: value or "" for key, value in row.items() if key}
            for row in reader
            if any((value or "").strip() for value in row.values())
        ]
    return reader.fieldnames, rows


def _fake_ont_plan(
    prefix: str,
    *,
    flowcell_id: str,
    **_kwargs: object,
) -> module.OntFastqPrefixPlan:
    normalized_prefix, tag, run_id, _run_output_prefix = module.parse_ont_fastq_prefix(prefix)
    selected_flowcell = flowcell_id or "PBK85691"
    shard = module.OntFastqShard(
        uri=f"{normalized_prefix}{selected_flowcell}_pass_{tag}_9b079e46_1709963d_0.fastq.gz",
        key=f"prefix/{selected_flowcell}_pass_{tag}_9b079e46_1709963d_0.fastq.gz",
        size=637,
        filename=f"{selected_flowcell}_pass_{tag}_9b079e46_1709963d_0.fastq.gz",
        flowcell_id=selected_flowcell,
        run_id=run_id,
        tag=tag,
        shard_index=0,
        gzip_compressed=True,
    )
    return module.OntFastqPrefixPlan(
        prefix=normalized_prefix,
        tag=tag,
        flowcell_id=selected_flowcell,
        run_id=run_id,
        shards=(shard,),
        gzip_compressed=True,
    )


def _has_source_group(row: dict[str, str]) -> bool:
    has_raw = any(
        (row.get(r1_field) or row.get(r2_field))
        for r1_field, r2_field, _unit_r1_field, _unit_r2_field in module.RAW_SOURCE_SPECS
    )
    has_ont_fastq_prefix = bool(row.get(module.ONT_FASTQ_PREFIX))
    has_aligned = any(row.get(field) for field in module.ALIGNED_SOURCE_FIELDS)
    return has_raw or has_ont_fastq_prefix or has_aligned


def test_staging_example_manifests_have_supported_schema_and_s3_sources() -> None:
    assert sorted(path.name for path in EXAMPLE_ROOT.iterdir()) == [
        "README.md",
        "hybrid_ilmn_ont",
        "ilmn_solo",
        "ont_fastq_solo",
        "ont_solo",
        "pacbio_solo",
        "roche_solo",
        "ultima_solo",
    ]
    for example_name, expected in EXAMPLES.items():
        header, rows = _read_manifest(example_name)
        assert len(rows) == expected["rows"]
        assert set(header) <= module.ALLOWED_MANIFEST_FIELDS
        for row in rows:
            assert row[module.STAGE_DIRECTIVE] == "stage_data"
            assert row[module.STAGE_TARGET] == "/data/staged_sample_data"
            assert _has_source_group(row)
            for field in SOURCE_PATH_FIELDS:
                value = (row.get(field) or "").strip()
                if value:
                    allowed_root = (
                        SEQUENCING_ROOT if field == module.ONT_FASTQ_PREFIX else REFERENCE_ROOT
                    )
                    assert value.startswith(
                        allowed_root
                    ), f"{example_name} has non-reference source path in {field}: {value}"


@pytest.mark.parametrize("example_name", EXAMPLES)
def test_staging_example_manifests_parse_and_validate_sidecars(
    monkeypatch: pytest.MonkeyPatch,
    example_name: str,
) -> None:
    checked_paths: list[str] = []

    def fake_check_source_path(path: str, **_kwargs: object) -> None:
        checked_paths.append(path)

    monkeypatch.setattr(module, "check_source_path", fake_check_source_path)
    monkeypatch.setattr(module, "resolve_ont_fastq_prefix_plan", _fake_ont_plan)

    parsed = module.load_manifest_rows(
        _manifest_path(example_name),
        reference_bucket="s3://lsmc-dayoa-omics-analysis-us-west-2",
        aws_env={},
        debug=False,
    )

    _header, rows = _read_manifest(example_name)
    assert len(parsed) == EXAMPLES[example_name]["rows"]
    expected_cram_sidecars = {
        f"{row[field]}.crai"
        for row in rows
        for field in (module.ULTIMA_CRAM, module.ONT_CRAM)
        if row.get(field)
    }
    assert expected_cram_sidecars <= set(checked_paths)


@pytest.mark.parametrize("example_name,expected", EXAMPLES.items())
def test_staging_example_manifests_mock_stage_expected_outputs(
    monkeypatch: pytest.MonkeyPatch,
    example_name: str,
    expected: dict[str, object],
) -> None:
    monkeypatch.setattr(module, "check_source_path", lambda *args, **kwargs: None)

    def fake_stage_single_lane(
        r1: str,
        r2: str,
        dest_fsx_dir: str,
        _dest_s3_dir: str,
        **_kwargs: object,
    ) -> tuple[str, str]:
        return f"{dest_fsx_dir}/{os.path.basename(r1)}", f"{dest_fsx_dir}/{os.path.basename(r2)}"

    def fake_stage_path_with_sidecars(
        source: str,
        *,
        sidecar_suffixes: tuple[str, ...],
        dest_fsx_dir: str,
        **_kwargs: object,
    ) -> tuple[str, list[str]]:
        remote_path = f"{dest_fsx_dir}/{os.path.basename(source)}"
        sidecars = [
            f"{dest_fsx_dir}/{os.path.basename(source + suffix)}" for suffix in sidecar_suffixes
        ]
        return remote_path, [remote_path, *sidecars]

    def fake_stage_ont_fastq_prefix(
        prefix: str,
        *,
        flowcell_id: str,
        sample_prefix: str,
        dest_fsx_dir: str,
        **_kwargs: object,
    ) -> tuple[str, list[str]]:
        assert prefix.startswith(SEQUENCING_ROOT)
        assert flowcell_id
        remote_path = f"{dest_fsx_dir}/{sample_prefix}_{flowcell_id}_ONT_R1.fastq.gz"
        return remote_path, [remote_path]

    def fake_stage_concordance(
        source: str,
        dest_fsx: str,
        _dest_s3: str,
        **_kwargs: object,
    ) -> str:
        return dest_fsx if source and source.lower() != "na" else "na"

    monkeypatch.setattr(module, "stage_single_lane", fake_stage_single_lane)
    monkeypatch.setattr(module, "stage_path_with_sidecars", fake_stage_path_with_sidecars)
    monkeypatch.setattr(
        module, "stage_ont_fastq_prefix", fake_stage_ont_fastq_prefix, raising=False
    )
    monkeypatch.setattr(module, "resolve_ont_fastq_prefix_plan", _fake_ont_plan)
    monkeypatch.setattr(module, "stage_concordance", fake_stage_concordance)

    samples_rows, units_rows, created_files, run_ids = module.process_samples(
        _manifest_path(example_name),
        _stage_paths(),
        reference_bucket="s3://lsmc-dayoa-omics-analysis-us-west-2",
        aws_env={},
        debug=False,
    )

    assert len(samples_rows) == 1
    assert len(units_rows) == expected["rows"]
    assert run_ids
    assert samples_rows[0]["SAMPLEID"] == "HG003"
    assert samples_rows[0]["SAMPLESOURCE"] == "blood"
    assert samples_rows[0]["SAMPLECLASS"] == "research"
    assert samples_rows[0]["BIOLOGICAL_SEX"] == "male"
    assert samples_rows[0]["SAMPLE_TYPE"] == "gdna"
    assert samples_rows[0]["CONCORDANCE_CONTROL_PATH"].startswith(
        "/data/staged_sample_data/remote_stage_test/"
    )
    assert not any(path.startswith("s3://") for path in created_files)

    for field in expected["unit_fields"]:
        assert all(row[field] for row in units_rows), f"{example_name} did not populate {field}"

    for field, value in expected.get("unit_field_values", {}).items():
        assert all(
            row[field] == value for row in units_rows
        ), f"{example_name} did not set {field}={value}"

    if example_name == "hybrid_ilmn_ont":
        assert all(row["SAMPLEUSE"] == "posControl" for row in units_rows)
        assert all(row["BWA_KMER"] == "na" for row in units_rows)
        assert all(row["DEEP_MODEL"] == "WGS" for row in units_rows)
