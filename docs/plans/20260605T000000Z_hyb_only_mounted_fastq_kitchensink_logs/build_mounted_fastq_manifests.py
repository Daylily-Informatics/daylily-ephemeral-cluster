#!/usr/bin/env python3
import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent

TRUTH_HG003 = "/fsx/references/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG003/"

ONT_CHIPS = {
    "chip1": {
        "log": "01039_s3_ls_ont_chip1.stdout.txt",
        "prefix": "basecalls/lsmc/ssf-hq/pca100/2026/20260522_ONT_4Coriells_chip1/20260522_ONT_4Coriells_chip1/20260522_2252_2B_PBM13545_f3392d36/",
        "fsx": "/fsx/run_dir_mounts/ont-4coriells-chip1/",
    },
    "chip2": {
        "log": "01040_s3_ls_ont_chip2.stdout.txt",
        "prefix": "basecalls/lsmc/ssf-hq/pca100/2026/20260522_ONT_4Coriells_chip2/20260522_ONT_4Coriells_chip2/20260523_0038_1C_PBM14931_9bbdbb3f/",
        "fsx": "/fsx/run_dir_mounts/ont-4coriells-chip2/",
    },
    "chip3": {
        "log": "01041_s3_ls_ont_chip3.stdout.txt",
        "prefix": "basecalls/lsmc/ssf-hq/pca100/2026/20260522_ONT_4Coriells_chip3/20260522_ONT_4Coriells_chip3/20260523_0038_1F_PBK89072_e28a4508/",
        "fsx": "/fsx/run_dir_mounts/ont-4coriells-chip3/",
    },
    "chip4": {
        "log": "01042_s3_ls_ont_chip4.stdout.txt",
        "prefix": "basecalls/lsmc/ssf-hq/pca100/2026/20260522_ONT_4Coriells_chip4/20260522_ONT_4Coriells_chip4/20260523_0039_3E_PBM13048_8867cb21/",
        "fsx": "/fsx/run_dir_mounts/ont-4coriells-chip4/",
    },
}

BARCODE_SAMPLE = {
    "barcode18": ("NA00232", "SMN"),
    "barcode19": ("NA09677", "SMN"),
    "barcode20": ("NA03986", "DMPK"),
    "barcode21": ("NA05164", "DMPK"),
}

ILMN_LOG = "01043_s3_ls_ilmn_fastq.stdout.txt"
ILMN_PREFIX = "basecalls/lsmc/ssf-hq/lh01121/2026/20260526_LH01121_0004_B23WW2NLT4/Analysis/1/Data/BCLConvert/fastq/"
ILMN_FSX = "/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq/"

COLUMNS = [
    "RUN_ID",
    "SAMPLE_ID",
    "EXPERIMENTID",
    "SAMPLE_TYPE",
    "LIB_PREP",
    "SEQ_VENDOR",
    "SEQ_PLATFORM",
    "LANE",
    "SEQBC_ID",
    "PATH_TO_CONCORDANCE_DATA_DIR",
    "ILMN_R1_FQ",
    "ILMN_R2_FQ",
    "ONT_R1_FQ",
    "ONT_R2_FQ",
    "ONT_FLOWCELL_ID",
    "STAGE_DIRECTIVE",
    "SUBSAMPLE_PCT",
    "SAMPLEUSE",
    "BWA_KMER",
    "DEEP_MODEL",
    "IS_POS_CTRL",
    "IS_NEG_CTRL",
    "TUM_NRM_SAMPLEID_MATCH",
    "N_X",
    "N_Y",
    "EXTERNAL_SAMPLE_ID",
]


def parse_s3_ls(path: Path):
    for line in path.read_text().splitlines():
        parts = line.split(maxsplit=3)
        if len(parts) != 4:
            continue
        _date, _time, size, key = parts
        if not size.isdigit():
            continue
        yield int(size), key


def write_tsv(path: Path, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in COLUMNS})


def build_ont():
    rows = []
    sources = []
    for chip, meta in ONT_CHIPS.items():
        idx_by_barcode = {barcode: 0 for barcode in BARCODE_SAMPLE}
        for size, key in parse_s3_ls(ROOT / meta["log"]):
            if not key.endswith(".fastq.gz") or "/fastq_pass/" not in key:
                continue
            match = re.search(r"/fastq_pass/(barcode[0-9]+)/", f"/{key}")
            if not match:
                continue
            barcode = match.group(1)
            if barcode not in BARCODE_SAMPLE:
                continue
            if not key.startswith(meta["prefix"]):
                raise SystemExit(f"Unexpected ONT key prefix for {chip}: {key}")
            sample, experiment = BARCODE_SAMPLE[barcode]
            rel = key[len(meta["prefix"]):]
            fsx_path = meta["fsx"] + rel
            unit_idx = idx_by_barcode[barcode]
            idx_by_barcode[barcode] += 1
            seqbc = f"{barcode}_{chip}_{unit_idx:04d}"
            rows.append(
                {
                    "RUN_ID": f"ONT_4Coriells_{chip}",
                    "SAMPLE_ID": sample,
                    "EXPERIMENTID": experiment,
                    "SAMPLE_TYPE": "gdna",
                    "LIB_PREP": "PF",
                    "SEQ_VENDOR": "ONT",
                    "SEQ_PLATFORM": "PROMETHION",
                    "LANE": chip,
                    "SEQBC_ID": seqbc,
                    "ONT_R1_FQ": fsx_path,
                    "ONT_FLOWCELL_ID": chip,
                    "STAGE_DIRECTIVE": "pass_through",
                    "SUBSAMPLE_PCT": "na",
                    "SAMPLEUSE": "sample",
                    "BWA_KMER": "19",
                    "DEEP_MODEL": "ONT_R104",
                    "IS_POS_CTRL": "false",
                    "IS_NEG_CTRL": "false",
                    "TUM_NRM_SAMPLEID_MATCH": "na",
                    "N_X": "1",
                    "N_Y": "1",
                    "EXTERNAL_SAMPLE_ID": sample,
                }
            )
            sources.append((chip, barcode, sample, size, key, fsx_path))
    rows.sort(key=lambda row: (row["RUN_ID"], row["SAMPLE_ID"], row["SEQBC_ID"], row["ONT_R1_FQ"]))
    return rows, sources


def build_ilmn():
    selected = {}
    sample_re = re.compile(
        r"^(NA00232-SMN|NA09677-SMN|NA03986-DMPK|NA05164-DMPK|Altair-HG003-[abc])_S([0-9]+)_R([12])_001\.fastq\.gz$"
    )
    for size, key in parse_s3_ls(ROOT / ILMN_LOG):
        if not key.startswith(ILMN_PREFIX):
            continue
        name = key[len(ILMN_PREFIX):]
        if "/" in name:
            continue
        match = sample_re.match(name)
        if not match:
            continue
        sample_name, sample_num, read_num = match.groups()
        selected.setdefault(sample_name, {})[read_num] = (size, key, ILMN_FSX + name, sample_num)

    rows = []
    sources = []
    for sample_name in sorted(selected):
        reads = selected[sample_name]
        if set(reads) != {"1", "2"}:
            raise SystemExit(f"Missing R1/R2 pair for {sample_name}: {sorted(reads)}")
        r1_size, r1_key, r1_path, sample_num = reads["1"]
        r2_size, r2_key, r2_path, _sample_num2 = reads["2"]
        if sample_name.startswith("Altair-HG003-"):
            sample_id = sample_name.replace("Altair-", "")
            experiment = "GIAB"
            truth = TRUTH_HG003
            sampleuse = "posControl"
            is_pos = "true"
            external = "HG003"
        else:
            sample_id, experiment = sample_name.split("-", 1)
            truth = ""
            sampleuse = "sample"
            is_pos = "false"
            external = sample_id
        rows.append(
            {
                "RUN_ID": "20260526_LH01121_0004_B23WW2NLT4",
                "SAMPLE_ID": sample_id,
                "EXPERIMENTID": experiment,
                "SAMPLE_TYPE": "gdna",
                "LIB_PREP": "PF",
                "SEQ_VENDOR": "ILMN",
                "SEQ_PLATFORM": "NOVASEQ",
                "LANE": "all",
                "SEQBC_ID": f"S{sample_num}",
                "PATH_TO_CONCORDANCE_DATA_DIR": truth,
                "ILMN_R1_FQ": r1_path,
                "ILMN_R2_FQ": r2_path,
                "STAGE_DIRECTIVE": "pass_through",
                "SUBSAMPLE_PCT": "na",
                "SAMPLEUSE": sampleuse,
                "BWA_KMER": "19",
                "DEEP_MODEL": "WGS",
                "IS_POS_CTRL": is_pos,
                "IS_NEG_CTRL": "false",
                "TUM_NRM_SAMPLEID_MATCH": "na",
                "N_X": "1",
                "N_Y": "1",
                "EXTERNAL_SAMPLE_ID": external,
            }
        )
        sources.extend(
            [
                (sample_name, "R1", r1_size, r1_key, r1_path),
                (sample_name, "R2", r2_size, r2_key, r2_path),
            ]
        )
    return rows, sources


def main():
    ont_rows, ont_sources = build_ont()
    ilmn_rows, ilmn_sources = build_ilmn()
    if not ont_rows:
        raise SystemExit("No ONT rows generated")
    if not ilmn_rows:
        raise SystemExit("No ILMN rows generated")

    write_tsv(ROOT / "ont_analysis_samples.tsv", ont_rows)
    write_tsv(ROOT / "ilmn_analysis_samples.tsv", ilmn_rows)

    with (ROOT / "ont_source_manifest.tsv").open("w") as handle:
        handle.write("chip\tbarcode\tsample\tbytes\ts3_key\tfsx_path\n")
        for row in ont_sources:
            handle.write("\t".join(map(str, row)) + "\n")
    with (ROOT / "ilmn_source_manifest.tsv").open("w") as handle:
        handle.write("sample\tread\tbytes\ts3_key\tfsx_path\n")
        for row in ilmn_sources:
            handle.write("\t".join(map(str, row)) + "\n")

    print(f"ONT_ROWS\t{len(ont_rows)}")
    print(f"ILMN_ROWS\t{len(ilmn_rows)}")
    print(f"ONT_SOURCE_ROWS\t{len(ont_sources)}")
    print(f"ILMN_SOURCE_ROWS\t{len(ilmn_sources)}")


if __name__ == "__main__":
    main()
