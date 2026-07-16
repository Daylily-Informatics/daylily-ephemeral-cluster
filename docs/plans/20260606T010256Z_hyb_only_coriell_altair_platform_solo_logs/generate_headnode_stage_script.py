#!/usr/bin/env python3
import csv
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parent
OBJECTS_TSV = LOG_DIR / "gate0_source_objects.tsv"
OUT = LOG_DIR / "headnode_stage_scratch_data.sh"
ONT_OUT = LOG_DIR / "headnode_stage_ont_data.sh"
ILMN_OUT = LOG_DIR / "headnode_stage_ilmn_data.sh"

ONT_SPECS = [
    ("NA00232", "SMN", "barcode18", "NA00232_SMN_R1_all.fastq.gz", ["chip1", "chip2", "chip4"], 219),
    ("NA09677", "SMN", "barcode19", "NA09677_SMN_R1_all.fastq.gz", ["chip1", "chip2", "chip3", "chip4"], 228),
    ("NA03986", "DMPK", "barcode20", "NA03986_DMPK_R1_all.fastq.gz", ["chip1", "chip2", "chip4"], 219),
    ("NA05164", "DMPK", "barcode21", "NA05164_DMPK_R1_all.fastq.gz", ["chip1", "chip2", "chip4"], 219),
]

CHIP_PATHS = {
    "chip1": "/fsx/run_dir_mounts/ont-4coriells-chip1",
    "chip2": "/fsx/run_dir_mounts/ont-4coriells-chip2",
    "chip3": "/fsx/run_dir_mounts/ont-4coriells-chip3",
    "chip4": "/fsx/run_dir_mounts/ont-4coriells-chip4",
}

ILMN_ROOT = "/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq"


def q(value):
    return "'" + value.replace("'", "'\"'\"'") + "'"


def main():
    objects = list(csv.DictReader(OBJECTS_TSV.open(), delimiter="\t"))
    ilmn = sorted(
        (obj for obj in objects if obj["platform"] == "ILMN"),
        key=lambda obj: (obj["sample"], obj["uri"]),
    )
    common_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "export LC_ALL=C",
        "mkdir -p /fsx/scratch/ONT/manifests /fsx/scratch/ONT/logs /fsx/scratch/ONT/tmp /fsx/scratch/ILMN/logs /fsx/scratch/ILMN/tmp",
        "ONT_LOG=/fsx/scratch/ONT/logs/stage_commands.log",
        "ILMN_LOG=/fsx/scratch/ILMN/logs/stage_commands.log",
        "printf 'start\\t%s\\n' \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\" | tee -a \"$ONT_LOG\" \"$ILMN_LOG\"",
        "df -h /fsx | tee -a \"$ONT_LOG\" \"$ILMN_LOG\"",
        "for d in /fsx/run_dir_mounts/ont-4coriells-chip1 /fsx/run_dir_mounts/ont-4coriells-chip2 /fsx/run_dir_mounts/ont-4coriells-chip3 /fsx/run_dir_mounts/ont-4coriells-chip4 /fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq; do test -d \"$d\"; done",
        "",
    ]
    ont_common_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "export LC_ALL=C",
        "mkdir -p /fsx/scratch/ONT/manifests /fsx/scratch/ONT/logs /fsx/scratch/ONT/tmp",
        "ONT_LOG=/fsx/scratch/ONT/logs/stage_commands.log",
        "printf 'start_ont\\t%s\\n' \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\" | tee -a \"$ONT_LOG\"",
        "df -h /fsx | tee -a \"$ONT_LOG\"",
        "for d in /fsx/run_dir_mounts/ont-4coriells-chip1 /fsx/run_dir_mounts/ont-4coriells-chip2 /fsx/run_dir_mounts/ont-4coriells-chip3 /fsx/run_dir_mounts/ont-4coriells-chip4; do test -d \"$d\"; done",
        "",
    ]
    ont_lines = [
        "build_ont_sample() {",
        "  local sample=\"$1\" panel=\"$2\" barcode=\"$3\" output_name=\"$4\" expected_count=\"$5\"; shift 5",
        "  local final=\"/fsx/scratch/ONT/${output_name}\"",
        "  local tmp=\"/fsx/scratch/ONT/tmp/${output_name}.tmp.$$\"",
        "  local manifest=\"/fsx/scratch/ONT/manifests/${sample}.sources.tsv\"",
        "  local paths=\"/fsx/scratch/ONT/tmp/${sample}.paths.$$\"",
        "  printf 'sample\\tbarcode\\tchip\\tpath\\tbytes\\n' > \"$manifest\"",
        "  : > \"$paths\"",
        "  local chip root found path size",
        "  for chip in \"$@\"; do",
        "    root=\"/fsx/run_dir_mounts/ont-4coriells-${chip}/fastq_pass/${barcode}\"",
        "    test -d \"$root\"",
        "    while IFS= read -r path; do",
        "      size=$(stat -c '%s' \"$path\")",
        "      printf '%s\\t%s\\t%s\\t%s\\t%s\\n' \"$sample\" \"$barcode\" \"$chip\" \"$path\" \"$size\" >> \"$manifest\"",
        "      printf '%s\\n' \"$path\" >> \"$paths\"",
        "    done < <(find \"$root\" -maxdepth 1 -type f \\( -name '*.fastq.gz' -o -name '*.fq.gz' \\) | sort)",
        "  done",
        "  found=$(wc -l < \"$paths\" | tr -d ' ')",
        "  if [[ \"$found\" != \"$expected_count\" ]]; then",
        "    printf 'ERROR\\t%s\\texpected_count=%s\\tfound=%s\\n' \"$sample\" \"$expected_count\" \"$found\" | tee -a \"$ONT_LOG\"",
        "    exit 2",
        "  fi",
        "  printf 'CMD\\t%s\\tcat %s sources to %s\\n' \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\" \"$found\" \"$final\" | tee -a \"$ONT_LOG\"",
        "  rm -f \"$tmp\"",
        "  while IFS= read -r path; do cat -- \"$path\" >> \"$tmp\"; done < \"$paths\"",
        "  mv -f \"$tmp\" \"$final\"",
        "  gzip -t \"$final\"",
        "  printf 'DONE\\t%s\\t%s\\t%s\\t%s\\n' \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\" \"$sample\" \"$final\" \"$(stat -c '%s' \"$final\")\" | tee -a \"$ONT_LOG\"",
        "  rm -f \"$paths\"",
        "}",
        "",
    ]

    for sample, panel, barcode, output_name, chips, expected_count in ONT_SPECS:
        chip_args = " ".join(q(chip) for chip in chips)
        ont_lines.append(f"build_ont_sample {q(sample)} {q(panel)} {q(barcode)} {q(output_name)} {q(str(expected_count))} {chip_args}")
    ont_lines.extend([
        "df -h /fsx | tee -a \"$ONT_LOG\"",
        "printf 'finish_ont\\t%s\\n' \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\" | tee -a \"$ONT_LOG\"",
    ])
    ilmn_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "export LC_ALL=C",
        "mkdir -p /fsx/scratch/ILMN/logs /fsx/scratch/ILMN/tmp",
        "ILMN_LOG=/fsx/scratch/ILMN/logs/stage_commands.log",
        "printf 'start_ilmn\\t%s\\n' \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\" | tee -a \"$ILMN_LOG\"",
        "df -h /fsx | tee -a \"$ILMN_LOG\"",
        "test -d /fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq",
        "",
        "printf 'sample\\tsource\\tdest\\tbytes\\n' > /fsx/scratch/ILMN/logs/source_manifest.tsv",
    ]
    for obj in ilmn:
        name = obj["uri"].rsplit("/", 1)[-1]
        sample = obj["sample"]
        src = f"{ILMN_ROOT}/{name}"
        dest = f"/fsx/scratch/ILMN/{name}"
        tmp = f"/fsx/scratch/ILMN/tmp/{name}.tmp.$$"
        ilmn_lines.extend([
            f"test -s {q(src)}",
            f"printf 'CMD\\t%s\\tcp -- %s %s\\n' \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\" {q(src)} {q(dest)} | tee -a \"$ILMN_LOG\"",
            f"cp -- {q(src)} {q(tmp)}",
            f"mv -f {q(tmp)} {q(dest)}",
            f"gzip -t {q(dest)}",
            f"printf '%s\\t%s\\t%s\\t%s\\n' {q(sample)} {q(src)} {q(dest)} \"$(stat -c '%s' {q(dest)})\" >> /fsx/scratch/ILMN/logs/source_manifest.tsv",
        ])
    ilmn_lines.extend([
        "df -h /fsx | tee -a \"$ILMN_LOG\"",
        "printf 'finish_ilmn\\t%s\\n' \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\" | tee -a \"$ILMN_LOG\"",
    ])
    lines = common_lines + ont_lines + ilmn_lines[8:]
    OUT.write_text("\n".join(lines) + "\n")
    ONT_OUT.write_text("\n".join(ont_common_lines + ont_lines) + "\n")
    ILMN_OUT.write_text("\n".join(ilmn_lines) + "\n")


if __name__ == "__main__":
    main()
