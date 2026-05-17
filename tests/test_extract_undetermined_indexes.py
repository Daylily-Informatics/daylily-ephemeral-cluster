from __future__ import annotations

import csv
import gzip
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "bin" / "utils" / "ilmn" / "extract_undetermined_indexes"


def write_fastq(path: Path, tags: list[str], *, read: int) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for ordinal, tag in enumerate(tags, 1):
            fh.write(f"@INST:1:FLOW:1:1101:1000:{ordinal} {read}:N:0:{tag}\n")
            fh.write("ACGTACGT\n")
            fh.write("+\n")
            fh.write("FFFFFFFF\n")


def write_samplesheet(path: Path, data_rows: list[tuple[str, str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["[Header]"])
        writer.writerow(["IndexOrientation", "Forward"])
        writer.writerow([])
        writer.writerow(["[BCLConvert_Data]"])
        writer.writerow(["Sample_ID", "Index", "Index2"])
        for row in data_rows:
            writer.writerow(row)


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def count_fastq_records(path: Path) -> int:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return sum(1 for _line in fh) // 4


def run_tool(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_top_not_in_samplesheet_writes_report_and_allowlist(tmp_path: Path) -> None:
    r1_lane1 = tmp_path / "Undetermined_S0_L001_R1_001.fastq.gz"
    r1_lane2 = tmp_path / "Undetermined_S0_L002_R1_001.fastq.gz"
    samplesheet = tmp_path / "SampleSheet.csv"
    report = tmp_path / "top.tsv"
    allowlist = tmp_path / "selected.tsv"

    write_fastq(r1_lane1, ["AAAA+CCCC", "GGGG+TTTT", "GGGG+TTTT", "CCCC+AAAA"], read=1)
    write_fastq(r1_lane2, ["GGGG+TTTT", "CCCC+AAAA", "TTTT+TTTT"], read=1)
    write_samplesheet(samplesheet, [("S1", "AAAA", "CCCC"), ("S2", "GGGG", "AAAA")])

    result = run_tool(
        str(r1_lane1),
        str(r1_lane2),
        "--mode",
        "called",
        "--samplesheet",
        str(samplesheet),
        "--top-not-in-samplesheet",
        "2",
        "--output",
        str(report),
        "--tag-pairs-out",
        str(allowlist),
        "--quiet",
    )

    assert result.returncode == 0, result.stderr
    rows = read_tsv(report)
    assert [(row["index"], row["index2"], row["count"]) for row in rows] == [
        ("GGGG", "TTTT", "3"),
        ("CCCC", "AAAA", "2"),
    ]
    assert rows[0]["matches_samplesheet_exact"] == "false"
    assert rows[0]["matches_samplesheet_i2_rc"] == "true"

    allowlist_rows = read_tsv(allowlist)
    assert [(row["index"], row["index2"]) for row in allowlist_rows] == [
        ("GGGG", "TTTT"),
        ("CCCC", "AAAA"),
    ]


def test_split_fastqs_merges_selected_pairs_across_lanes(tmp_path: Path) -> None:
    r1_lane1 = tmp_path / "Undetermined_S0_L001_R1_001.fastq.gz"
    r2_lane1 = tmp_path / "Undetermined_S0_L001_R2_001.fastq.gz"
    r1_lane2 = tmp_path / "Undetermined_S0_L002_R1_001.fastq.gz"
    r2_lane2 = tmp_path / "Undetermined_S0_L002_R2_001.fastq.gz"
    allowlist = tmp_path / "selected.tsv"
    split_dir = tmp_path / "split"
    split_report = tmp_path / "split.tsv"

    lane1_tags = ["AAAA+CCCC", "GGGG+TTTT", "GGGG+TTTT", "CCCC+AAAA"]
    lane2_tags = ["GGGG+TTTT", "CCCC+AAAA", "TTTT+TTTT"]
    write_fastq(r1_lane1, lane1_tags, read=1)
    write_fastq(r2_lane1, lane1_tags, read=2)
    write_fastq(r1_lane2, lane2_tags, read=1)
    write_fastq(r2_lane2, lane2_tags, read=2)
    allowlist.write_text("index\tindex2\nGGGG\tTTTT\nCCCC\tAAAA\n", encoding="utf-8")

    result = run_tool(
        str(r1_lane1),
        str(r1_lane2),
        "--read2-inputs",
        str(r2_lane1),
        str(r2_lane2),
        "--split-fastqs",
        "--mode",
        "called",
        "--tag-pairs-tsv",
        str(allowlist),
        "--fastq-out-dir",
        str(split_dir),
        "--output",
        str(split_report),
        "--quiet",
    )

    assert result.returncode == 0, result.stderr
    rows = read_tsv(split_report)
    assert [(row["index"], row["index2"], row["count"]) for row in rows] == [
        ("GGGG", "TTTT", "3"),
        ("CCCC", "AAAA", "2"),
    ]
    assert count_fastq_records(split_dir / "GGGG__TTTT_R1.fastq.gz") == 3
    assert count_fastq_records(split_dir / "GGGG__TTTT_R2.fastq.gz") == 3
    assert count_fastq_records(split_dir / "CCCC__AAAA_R1.fastq.gz") == 2
    assert count_fastq_records(split_dir / "CCCC__AAAA_R2.fastq.gz") == 2


def test_split_fastqs_rejects_record_count_mismatch(tmp_path: Path) -> None:
    r1 = tmp_path / "Undetermined_S0_L001_R1_001.fastq.gz"
    r2 = tmp_path / "Undetermined_S0_L001_R2_001.fastq.gz"
    allowlist = tmp_path / "selected.tsv"

    write_fastq(r1, ["GGGG+TTTT", "GGGG+TTTT"], read=1)
    write_fastq(r2, ["GGGG+TTTT"], read=2)
    allowlist.write_text("index\tindex2\nGGGG\tTTTT\n", encoding="utf-8")

    result = run_tool(
        str(r1),
        "--read2-inputs",
        str(r2),
        "--split-fastqs",
        "--mode",
        "called",
        "--tag-pairs-tsv",
        str(allowlist),
        "--fastq-out-dir",
        str(tmp_path / "split"),
        "--output",
        str(tmp_path / "split.tsv"),
        "--quiet",
    )

    assert result.returncode != 0
    assert "R1/R2 FASTQ record count mismatch" in result.stderr


def test_top_not_in_samplesheet_requires_valid_samplesheet(tmp_path: Path) -> None:
    r1 = tmp_path / "Undetermined_S0_L001_R1_001.fastq.gz"
    samplesheet = tmp_path / "SampleSheet.csv"
    write_fastq(r1, ["GGGG+TTTT"], read=1)
    samplesheet.write_text("[Header]\nIndexOrientation,Forward\n", encoding="utf-8")

    result = run_tool(
        str(r1),
        "--mode",
        "called",
        "--samplesheet",
        str(samplesheet),
        "--top-not-in-samplesheet",
        "1",
        "--quiet",
    )

    assert result.returncode != 0
    assert "[BCLConvert_Data] section not found" in result.stderr
