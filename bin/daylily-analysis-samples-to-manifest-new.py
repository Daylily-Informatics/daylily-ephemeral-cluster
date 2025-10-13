#!/usr/bin/env python3
import os
import sys
import csv
import subprocess
from datetime import datetime
from collections import defaultdict

import boto3
import requests
from botocore.exceptions import NoCredentialsError

RUN_ID = "RUN_ID"
SAMPLE_ID = "SAMPLE_ID"
EXPERIMENT_ID = "EXPERIMENTID"
SAMPLE_TYPE = "SAMPLE_TYPE"
LIB_PREP = "LIB_PREP"
SEQ_VENDOR = "SEQ_VENDOR"
SEQ_PLATFORM = "SEQ_PLATFORM"
LANE = "LANE"
SEQBC_ID = "SEQBC_ID"
PATH_TO_CONCORDANCE = "PATH_TO_CONCORDANCE_DATA_DIR"
R1_FQ = "R1_FQ"
R2_FQ = "R2_FQ"
STAGE_DIRECTIVE = "STAGE_DIRECTIVE"
STAGE_TARGET = "STAGE_TARGET"
SUBSAMPLE_PCT = "SUBSAMPLE_PCT"
IS_POS_CTRL = "IS_POS_CTRL"
IS_NEG_CTRL = "IS_NEG_CTRL"
N_X = "N_X"
N_Y = "N_Y"
EXTERNAL_SAMPLE_ID = "EXTERNAL_SAMPLE_ID"

KEY_FIELDS = [
    RUN_ID,
    SAMPLE_ID,
    EXPERIMENT_ID,
    SAMPLE_TYPE,
    LIB_PREP,
    SEQ_VENDOR,
    SEQ_PLATFORM,
]

DERIVED_UNITS_FIELDS = {
    "RUNID",
    "SAMPLEID",
    "EXPERIMENTID",
    "LANEID",
    "BARCODEID",
    "LIBPREP",
    "SEQ_VENDOR",
    "SEQ_PLATFORM",
    "ILMN_R1_PATH",
    "ILMN_R2_PATH",
    "PACBIO_R1_PATH",
    "PACBIO_R2_PATH",
    "ONT_R1_PATH",
    "ONT_R2_PATH",
    "UG_R1_PATH",
    "UG_R2_PATH",
    "SUBSAMPLE_PCT",
    "SAMPLEUSE",
    "BWA_KMER",
}

UNITS_HEADER = [
    "RUNID",
    "SAMPLEID",
    "EXPERIMENTID",
    "LANEID",
    "BARCODEID",
    "LIBPREP",
    "SEQ_VENDOR",
    "SEQ_PLATFORM",
    "ILMN_R1_PATH",
    "ILMN_R2_PATH",
    "PACBIO_R1_PATH",
    "PACBIO_R2_PATH",
    "ONT_R1_PATH",
    "ONT_R2_PATH",
    "UG_R1_PATH",
    "UG_R2_PATH",
    "SUBSAMPLE_PCT",
    "SAMPLEUSE",
    "BWA_KMER",
    "DEEP_MODEL",
    "ULTIMA_CRAM",
    "ULTIMA_CRAM_ALIGNER",
    "ULTIMA_CRAM_SNV_CALLER",
    "ONT_CRAM",
    "ONT_CRAM_ALIGNER",
    "ONT_CRAM_SNV_CALLER",
    "PB_BAM",
    "PB_BAM_ALIGNER",
    "PB_BAM_SNV_CALLER",
]

SAMPLES_HEADER = [
    "SAMPLEID",
    "SAMPLESOURCE",
    "SAMPLECLASS",
    "BIOLOGICAL_SEX",
    "CONCORDANCE_CONTROL_PATH",
    "IS_POSITIVE_CONTROL",
    "IS_NEGATIVE_CONTROL",
    "SAMPLE_TYPE",
    "TUM_NRM_SAMPLEID_MATCH",
    "EXTERNAL_SAMPLE_ID",
    "N_X",
    "N_Y",
    "TRUTH_DATA_DIR",
]

def log_info(message):
    print(f"[INFO] {message}")

def log_warn(message):
    print(f"[WARN] {message}")

def log_error(message):
    print(f"[ERROR] {message}")
    exit(1)

def check_file_exists(file_path):
    if file_path.startswith(("http://", "https://")):
        response = requests.head(file_path)
        if response.status_code != 200:
            log_error(f"HTTP file not found: {file_path}")
    elif file_path.startswith("s3://"):
        s3 = boto3.client("s3")
        bucket, key = file_path[5:].split("/", 1)
        try:
            s3.head_object(Bucket=bucket, Key=key)
        except NoCredentialsError:
            log_error("AWS credentials not configured.")
        except Exception as e:
            log_error(f"S3 file not found: {file_path} ({e})")
    else:
        if not os.path.exists(file_path):
            log_error(f"Local file not found: {file_path}")


def get_entry_value(entry, field, default=""):
    return (entry.get(field, default) or default).strip()


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def determine_sex(n_x, n_y):
    if n_x == 2 and n_y == 0:
        return "female"
    elif n_x == 1 and n_y == 1:
        return "male"
    return "na"

def validate_and_stage_concordance_dir(concordance_dir, stage_target, sample_prefix):
    if concordance_dir == "na" or concordance_dir.startswith("/fsx/data"):
        return concordance_dir
    target_concordance_dir = os.path.join(stage_target, sample_prefix, "concordance_data")
    os.makedirs(target_concordance_dir, exist_ok=True)
    if concordance_dir.startswith(("http://", "https://")):
        subprocess.run(["wget", "-q", "-P", "--recursive", target_concordance_dir, concordance_dir], check=True)
    elif concordance_dir.startswith("s3://"):
        subprocess.run(["aws", "s3", "cp", concordance_dir, target_concordance_dir, "--recursive"], check=True)
    return target_concordance_dir

def validate_subsample_pct(subsample_pct):
    try:
        pct = float(subsample_pct)
        return pct if 0.0 < pct < 1.0 else "na"
    except ValueError:
        return "na"

def write_tsv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

def copy_files_to_target(src, dst, link=False):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if src.startswith("s3://"):
        bucket, key = src[5:].split("/", 1)
        boto3.client("s3").download_file(bucket, key, dst)
    elif src.startswith(("http://", "https://")):
        subprocess.run(["wget", "-q", "-O", dst, src], check=True)
    else:
        if link:
            subprocess.run(["ln", "-s", src, dst], check=True)
        else:
            subprocess.run(["cp", src, dst], check=True)

def parse_and_validate_tsv(input_file, stage_target):
    samples = defaultdict(list)
    with open(input_file, newline="") as ff:
        reader = csv.DictReader(ff, delimiter="\t")
        if reader.fieldnames is None:
            log_error("Input TSV is missing a header row")

        header_fields = [field for field in reader.fieldnames if field]
        missing_fields = [field for field in KEY_FIELDS + [LANE, SEQBC_ID, R1_FQ, R2_FQ] if field not in header_fields]
        if missing_fields:
            log_error(f"Missing required columns in TSV: {', '.join(missing_fields)}")

        for row in reader:
            if not row:
                continue

            normalized_row = {k: (v or "").strip() for k, v in row.items() if k}
            if not any(normalized_row.values()):
                continue

            key = tuple(normalized_row[field] for field in KEY_FIELDS)
            samples[key].append(normalized_row)

    samples_rows = {}
    sampleid_to_entry = {}
    units_rows = []
    run_ids = set()
    for sample_key, entries in samples.items():
        is_multi_lane = len(entries) > 1
        print(f"Processing sample: {sample_key} with {len(entries)} entries")
        lanes = [e[LANE] for e in entries]
        if is_multi_lane and "0" in lanes:
            log_error(f"Invalid LANE=0 for multi-lane sample: {sample_key}")


        first_entry = entries[0]
        if any("_" in part for part in sample_key + (first_entry[LANE], first_entry[SEQBC_ID])):
            log_warn(f"UNDERSCORES '_' FOUND AND WILL BE REPLACED WITH '-' IN: {sample_key}")
            log_warn(f"RUN_ID, SAMPLE_ID, EXPERIMENTID, SAMPLE_TYPE, LIB_PREP, SEQ_PLATFORM, LANE, SEQBC_ID must not contain underscores: {sample_key} .. {entries}\n\n")
            log_warn(" UNDERSCORES '_' WILL BE REPLACED WITH HYPHENS '-' \n")
            log_warn("...")
            #log_error(f"RUN_ID  SAMPLE_ID  EXPERIMENTID     SAMPLE_TYPE     LIB_PREP        SEQ_PLATFORM    LANE    SEQBC_ID must not contain underscores: {sample_key} .. {entries}\n")
            #raise Exception(f"RUN_ID  SAMPLE_ID  EXPERIMENTID     SAMPLE_TYPE     LIB_PREP        SEQ_PLATFORM    LANE    SEQBC_ID  must not contain underscores: {sample_key} .. {entries}\n")

        (
            raw_run_id,
            raw_sample_id,
            raw_experiment_id,
            raw_sample_type,
            raw_libprep,
            raw_vendor,
            raw_seqplatform,
        ) = sample_key

        ruid = raw_run_id.replace("_", "-")
        sampleid = raw_sample_id.replace("_", "-")
        experiment_id = raw_experiment_id.replace("_", "-")
        sampletype = raw_sample_type.replace("_", "-")
        libprep = raw_libprep.replace("_", "-")
        vendor_value = raw_vendor.replace("_", "-")
        vendor = vendor_value.strip().upper()
        seqplatform = raw_seqplatform.replace("_", "-")
        lane = first_entry[LANE].replace("_", "-")
        seqbc = first_entry[SEQBC_ID].replace("_", "-")

        composite_sample_id = f"{sampleid}-{seqplatform}-{libprep}-{sampletype}-{experiment_id}"
        sample_name = f"{ruid}_{composite_sample_id}"
        sample_prefix = f"{ruid}_{composite_sample_id}_{seqbc}_0"
        staged_sample_path = os.path.join(stage_target, sample_prefix)
        os.makedirs(staged_sample_path, exist_ok=True)

        run_ids.add(ruid)

        primary_entry = entries[0]
        stage_target_value = get_entry_value(primary_entry, STAGE_TARGET, stage_target) or stage_target
        subsample_raw = validate_subsample_pct(get_entry_value(primary_entry, SUBSAMPLE_PCT, "na"))
        subsample_pct = f"{subsample_raw}" if isinstance(subsample_raw, float) else subsample_raw

        if is_multi_lane:
            merged_r1 = os.path.join(staged_sample_path, f"{sample_prefix}_merged_R1.fastq.gz")
            merged_r2 = os.path.join(staged_sample_path, f"{sample_prefix}_merged_R2.fastq.gz")
            r1_files, r2_files = zip(
                *[
                    (get_entry_value(e, R1_FQ), get_entry_value(e, R2_FQ))
                    for e in entries
                ]
            )

            for f in r1_files + r2_files:
                if f and f.lower() != "na":
                    check_file_exists(f)

            tmp_r1_files = []
            tmp_r2_files = []

            log_info(f"Processing multi-lane sample: {sample_prefix} with R1 files: {r1_files} and R2 files: {r2_files}")
            for idx, (r1, r2) in enumerate(zip(r1_files, r2_files)):
                log_info(f"Downloading R1: {r1}, R2: {r2} for sample {sample_prefix}")
                local_r1 = os.path.join(staged_sample_path, f"tmp_{idx}_R1.fastq.gz")
                local_r2 = os.path.join(staged_sample_path, f"tmp_{idx}_R2.fastq.gz")
                copy_files_to_target(r1, local_r1)
                copy_files_to_target(r2, local_r2)
                tmp_r1_files.append(local_r1)
                tmp_r2_files.append(local_r2)

            log_info(f"Concatenating R1 files: {tmp_r1_files} into {merged_r1}")
            subprocess.run(f"cat {' '.join(tmp_r1_files)} > {merged_r1}", shell=True, check=True)

            log_info(f"Concatenating R2 files: {tmp_r2_files} into {merged_r2}")
            subprocess.run(f"cat {' '.join(tmp_r2_files)} > {merged_r2}", shell=True, check=True)

            for tmp_file in tmp_r1_files + tmp_r2_files:
                os.remove(tmp_file)

            final_r1 = merged_r1
            final_r2 = merged_r2
            lane_id = "0"
        else:
            primary_r1 = get_entry_value(primary_entry, R1_FQ)
            primary_r2 = get_entry_value(primary_entry, R2_FQ)
            staged_r1 = os.path.join(staged_sample_path, os.path.basename(primary_r1))
            staged_r2 = os.path.join(staged_sample_path, os.path.basename(primary_r2))
            log_info(f"Processing single-lane sample: {sample_prefix} with R1: {staged_r1} and R2: {staged_r2}")
            stage_directive = get_entry_value(primary_entry, STAGE_DIRECTIVE)
            copy_files_to_target(primary_r1, staged_r1, stage_directive == "link_data")
            copy_files_to_target(primary_r2, staged_r2, stage_directive == "link_data")
            final_r1 = staged_r1
            final_r2 = staged_r2
            lane_id = lane

        concordance_dir = validate_and_stage_concordance_dir(
            get_entry_value(primary_entry, PATH_TO_CONCORDANCE, "na"), stage_target_value, sample_prefix
        )
        sex = determine_sex(safe_int(primary_entry.get(N_X)), safe_int(primary_entry.get(N_Y)))

        units_row = {column: "" for column in UNITS_HEADER}
        units_row.update(
            {
                "RUNID": ruid,
                "SAMPLEID": sampleid,
                "EXPERIMENTID": experiment_id,
                "LANEID": lane_id,
                "BARCODEID": seqbc,
                "LIBPREP": libprep,
                "SEQ_VENDOR": vendor,
                "SEQ_PLATFORM": seqplatform,
                "SUBSAMPLE_PCT": subsample_pct,
            }
        )

        is_pos_ctrl = get_entry_value(primary_entry, IS_POS_CTRL).lower() == "true"
        units_row["SAMPLEUSE"] = get_entry_value(primary_entry, "SAMPLEUSE") or ("posControl" if is_pos_ctrl else "sample")
        units_row["BWA_KMER"] = get_entry_value(primary_entry, "BWA_KMER") or "19"

        for field in set(primary_entry.keys()).intersection(UNITS_HEADER):
            if field in DERIVED_UNITS_FIELDS:
                continue
            value = get_entry_value(primary_entry, field)
            if value:
                units_row[field] = value

        if vendor == "ILMN":
            units_row["ILMN_R1_PATH"] = final_r1
            units_row["ILMN_R2_PATH"] = final_r2
        elif vendor == "ONT":
            units_row["ONT_R1_PATH"] = final_r1
            units_row["ONT_R2_PATH"] = final_r2
        elif vendor == "PACBIO":
            units_row["PACBIO_R1_PATH"] = final_r1
            units_row["PACBIO_R2_PATH"] = final_r2
        elif vendor == "UG":
            units_row["UG_R1_PATH"] = final_r1
            units_row["UG_R2_PATH"] = final_r2

        units_rows.append(units_row)

        samples_row = {
            "SAMPLEID": sampleid,
            "SAMPLESOURCE": sampletype,
            "SAMPLECLASS": "research",
            "BIOLOGICAL_SEX": sex,
            "CONCORDANCE_CONTROL_PATH": concordance_dir,
            "IS_POSITIVE_CONTROL": get_entry_value(primary_entry, IS_POS_CTRL),
            "IS_NEGATIVE_CONTROL": get_entry_value(primary_entry, IS_NEG_CTRL),
            "SAMPLE_TYPE": sampletype,
            "TUM_NRM_SAMPLEID_MATCH": sampleid,
            "EXTERNAL_SAMPLE_ID": get_entry_value(primary_entry, EXTERNAL_SAMPLE_ID) or "na",
            "N_X": get_entry_value(primary_entry, N_X),
            "N_Y": get_entry_value(primary_entry, N_Y),
            "TRUTH_DATA_DIR": concordance_dir,
        }

        existing_sampleid_entry = sampleid_to_entry.get(sampleid)
        if existing_sampleid_entry:
            existing_name, existing_row = existing_sampleid_entry
            if existing_row != samples_row:
                log_error(
                    "Duplicate SAMPLEID detected with conflicting metadata: "
                    f"{sampleid}\nExisting entry from {existing_name}: {existing_row}\n"
                    f"New entry from {sample_name}: {samples_row}"
                )
        existing_sample = samples_rows.get(sample_name)
        if existing_sample and existing_sample != samples_row:
            log_error(
                f"Conflicting metadata for sample {sample_name}:\nExisting: {existing_sample}\nNew: {samples_row}"
            )

        if existing_sampleid_entry and existing_sampleid_entry[1] == samples_row:
            log_warn(
                "Duplicate SAMPLEID detected with identical metadata; "
                f"skipping additional samples TSV entry for {sampleid}."
            )
        else:
            samples_rows[sample_name] = samples_row
            sampleid_to_entry[sampleid] = (sample_name, samples_row)
    output_dir = "/fsx/staged_sample_data"
    os.makedirs(output_dir, exist_ok=True)

    if len(run_ids) == 1:
        run_id_for_filename = next(iter(run_ids))
    elif len(run_ids) > 1:
        run_id_for_filename = "multi_run"
        log_warn(
            "Multiple run IDs detected in input; using 'multi_run' as the filename prefix."
        )
    else:
        run_id_for_filename = "no_run_id"
        log_warn("No run IDs detected; using 'no_run_id' as the filename prefix.")

    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    samples_filename = f"{run_id_for_filename}_{timestamp}_samples.tsv"
    units_filename = f"{run_id_for_filename}_{timestamp}_units.tsv"

    samples_tsv_path = os.path.join(output_dir, samples_filename)
    units_tsv_path = os.path.join(output_dir, units_filename)

    log_warn(f"Writing config samples file: {samples_tsv_path}")
    samples_data = list(samples_rows.values())

    unique_rows = {tuple(row.items()) for row in samples_data}
    if len(unique_rows) != len(samples_data):
        log_error("Duplicate rows detected in samples TSV data; each row must be unique.")
    write_tsv(samples_tsv_path, SAMPLES_HEADER, samples_data)

    log_warn(f"Writing config units file: {units_tsv_path}")
    write_tsv(units_tsv_path, UNITS_HEADER, units_rows)

    log_info(f"Config files created: {samples_tsv_path}, {units_tsv_path}")
    log_info(
        "Use these config files:\n"
        f"\tcp {samples_tsv_path} config/samples.tsv\n"
        f"\tcp {units_tsv_path} config/units.tsv"
    )


def check_aws_credentials():

    if os.environ.get('AWS_PROFILE','unset') == 'unset':
        log_error("AWS_PROFILE must be set to a value matching entries in the ~/.aws/config and credentials files.\n\n -- Have you run 'aws configure --profile <your-profile>' using the same profile used to create this cluster?\n\n")

    try:
        boto3.client("s3").list_buckets()
    except NoCredentialsError:
        log_error("AWS credentials not configured.\n\n -- Have you run 'aws configure --profile <your-profile>' used to create this cluster?\n\n")


# Add the following main function to handle command-line arguments and invoke parsing
def main():
    if len(sys.argv) != 3:
        log_error("Usage: script.py <input_tsv> <stage_target>")

    check_aws_credentials()
    
    input_file = sys.argv[1]
    stage_target = sys.argv[2]

    parse_and_validate_tsv(input_file, stage_target)

if __name__ == "__main__":
    main()
