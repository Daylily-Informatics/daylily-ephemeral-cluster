#!/usr/bin/env python3
import os
import sys
import csv
import subprocess
from datetime import datetime
import requests
import boto3
from botocore.exceptions import NoCredentialsError
from collections import defaultdict

RUN_ID = 0
SAMPLE_ID = 1
SAMPLE_ANNO = 2
SAMPLE_TYPE = 3
LIB_PREP = 4
SEQ_PLATFORM = 5
LANE = 6
SEQBC_ID = 7
PATH_TO_CONCORDANCE = 8
R1_FQ = 9
R2_FQ = 10
STAGE_DIRECTIVE = 11
STAGE_TARGET = 12
SUBSAMPLE_PCT = 13
IS_POS_CTRL = 14
IS_NEG_CTRL = 15
N_X = 16
N_Y = 17

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
    with open(input_file) as ff:
        next(ff)
        for line in ff:
            cols = line.strip().split("\t")
            key = tuple(cols[:SEQ_PLATFORM + 1])
            samples[key].append(cols)

    samples_rows = {}
    units_rows = []
    run_ids = set()
    for sample_key, entries in samples.items():
        is_multi_lane = len(entries) > 1
        print(f"Processing sample: {sample_key} with {len(entries)} entries")
        lanes = [e[LANE] for e in entries]
        if is_multi_lane and "0" in lanes:
            log_error(f"Invalid LANE=0 for multi-lane sample: {sample_key}")


        if any("_" in part for part in sample_key + (entries[0][LANE], entries[0][SEQBC_ID])):
            log_warn(f"UNDERSCORES '_' FOUND AND WILL BE REPLACED WITH '-' IN: {sample_key}")
            log_warn(f"RUN_ID, SAMPLE_ID, SAMPLE_ANNO, SAMPLE_TYPE, LIB_PREP, SEQ_PLATFORM, LANE, SEQBC_ID must not contain underscores: {sample_key} .. {entries}\n\n")
            log_warn(" UNDERSCORES '_' WILL BE REPLACED WITH HYPHENS '-' \n")
            log_warn("...")
            #log_error(f"RUN_ID  SAMPLE_ID  SAMPLE_ANNO     SAMPLE_TYPE     LIB_PREP        SEQ_PLATFORM    LANE    SEQBC_ID must not contain underscores: {sample_key} .. {entries}\n")
            #raise Exception(f"RUN_ID  SAMPLE_ID  SAMPLE_ANNO     SAMPLE_TYPE     LIB_PREP        SEQ_PLATFORM    LANE    SEQBC_ID  must not contain underscores: {sample_key} .. {entries}\n")
            
        ruid = sample_key[RUN_ID].replace("_", "-")
        sampleid = sample_key[SAMPLE_ID].replace("_", "-")
        sampleanno = sample_key[SAMPLE_ANNO].replace("_", "-")
        sampletype = sample_key[SAMPLE_TYPE].replace("_", "-")
        libprep = sample_key[LIB_PREP].replace("_", "-")
        seqplatform = sample_key[SEQ_PLATFORM].replace("_", "-")
        lane = entries[0][LANE].replace("_", "-")
        seqbc = entries[0][SEQBC_ID].replace("_", "-")
        
        # RU_sampleid_seqbc_lane(always 0 in this script output)
        new_sample_id = f"{sampleid}-{seqplatform}-{libprep}-{sampletype}-{sampleanno}"
        sample_name = f"{ruid}_{new_sample_id}"
        sample_prefix = f"{ruid}_{new_sample_id}_{seqbc}_0"
        staged_sample_path = os.path.join(stage_target, sample_prefix)
        os.makedirs(staged_sample_path, exist_ok=True)

        run_ids.add(ruid)

        if is_multi_lane:
            merged_r1 = os.path.join(staged_sample_path, f"{sample_prefix}_merged_R1.fastq.gz")
            merged_r2 = os.path.join(staged_sample_path, f"{sample_prefix}_merged_R2.fastq.gz")
            r1_files, r2_files = zip(*[(e[R1_FQ], e[R2_FQ]) for e in entries])

            for f in r1_files + r2_files:
                check_file_exists(f)

            tmp_r1_files = []
            tmp_r2_files = []

            log_info(f"Processing multi-lane sample: {sample_prefix} with R1 files: {r1_files} and R2 files: {r2_files}")
            # Download S3 files locally first if they're from S3
            for idx, (r1, r2) in enumerate(zip(r1_files, r2_files)):
                log_info(f"Downloading R1: {r1}, R2: {r2} for sample {sample_prefix}")
                local_r1 = os.path.join(staged_sample_path, f"tmp_{idx}_R1.fastq.gz")
                local_r2 = os.path.join(staged_sample_path, f"tmp_{idx}_R2.fastq.gz")
                copy_files_to_target(r1, local_r1)
                copy_files_to_target(r2, local_r2)
                tmp_r1_files.append(local_r1)
                tmp_r2_files.append(local_r2)

            log_info(f"Concatenating R1 files: {tmp_r1_files} into {merged_r1}")
            # Concatenate the downloaded local files
            subprocess.run(f"cat {' '.join(tmp_r1_files)} > {merged_r1}", shell=True, check=True)
            
            log_info(f"Concatenating R2 files: {tmp_r2_files} into {merged_r2}")
            subprocess.run(f"cat {' '.join(tmp_r2_files)} > {merged_r2}", shell=True, check=True)

            # Clean up temporary files
            for tmp_file in tmp_r1_files + tmp_r2_files:
                os.remove(tmp_file)

            units_rows.append({
                "sample": sample_name,
                "unit": sample_prefix,
                "run_id": ruid,
                "experiment_id": new_sample_id,
                "lane": "0",
                "seqbc_id": seqbc,
                "r1_path": merged_r1,
                "r2_path": merged_r2,
                "seq_platform": seqplatform,
                "lib_prep": libprep,
                "sample_type": sampletype,
                "merge_strategy": "merge",
                "stage_directive": entries[0][STAGE_DIRECTIVE],
                "stage_target": entries[0][STAGE_TARGET],
            })
            concordance_dir = validate_and_stage_concordance_dir(entries[0][PATH_TO_CONCORDANCE], stage_target, sample_prefix)
            sex = determine_sex(int(entries[0][N_X]), int(entries[0][N_Y]))
        else:
            entry = entries[0]
            staged_r1 = os.path.join(staged_sample_path, os.path.basename(entry[R1_FQ]))
            staged_r2 = os.path.join(staged_sample_path, os.path.basename(entry[R2_FQ]))
            log_info(f"Processing single-lane sample: {sample_prefix} with R1: {staged_r1} and R2: {staged_r2}")
            copy_files_to_target(entry[R1_FQ], staged_r1, entry[STAGE_DIRECTIVE] == "link_data")
            copy_files_to_target(entry[R2_FQ], staged_r2, entry[STAGE_DIRECTIVE] == "link_data")

            units_rows.append({
                "sample": sample_name,
                "unit": sample_prefix,
                "run_id": ruid,
                "experiment_id": new_sample_id,
                "lane": lane,
                "seqbc_id": seqbc,
                "r1_path": staged_r1,
                "r2_path": staged_r2,
                "seq_platform": seqplatform,
                "lib_prep": libprep,
                "sample_type": sampletype,
                "merge_strategy": "single",
                "stage_directive": entry[STAGE_DIRECTIVE],
                "stage_target": entry[STAGE_TARGET],
            })
            concordance_dir = validate_and_stage_concordance_dir(entry[PATH_TO_CONCORDANCE], stage_target, sample_prefix)
            sex = determine_sex(int(entries[0][N_X]), int(entries[0][N_Y]))

        subsample_pct = validate_subsample_pct(entries[0][SUBSAMPLE_PCT])
        sample_metadata = {
            "sample": sample_name,
            "run_id": ruid,
            "sample_id": sampleid,
            "sample_annotation": sampleanno,
            "experiment_id": new_sample_id,
            "biological_sex": sex,
            "iddna_uid": "na",
            "concordance_control_path": concordance_dir,
            "is_positive_control": entries[0][IS_POS_CTRL],
            "is_negative_control": entries[0][IS_NEG_CTRL],
            "sample_type": sampletype,
            "tum_nrm_sampleid_match": sampleid,
            "external_sample_id": "na",
            "instrument": seqplatform,
            "lib_prep": libprep,
            "bwa_kmer": "19",
            "subsample_pct": subsample_pct,
            "stage_target": entries[0][STAGE_TARGET],
        }

        existing_sample = samples_rows.get(sample_name)
        if existing_sample and existing_sample != sample_metadata:
            log_error(
                f"Conflicting metadata for sample {sample_name}:\nExisting: {existing_sample}\nNew: {sample_metadata}"
            )
        samples_rows[sample_name] = sample_metadata
    output_dir = "/fsx/staged_data"
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
    if samples_rows:
        samples_header = list(next(iter(samples_rows.values())).keys())
        samples_data = list(samples_rows.values())
    else:
        samples_header = ["sample"]
        samples_data = []
    write_tsv(samples_tsv_path, samples_header, samples_data)

    log_warn(f"Writing config units file: {units_tsv_path}")
    units_header = [
        "sample",
        "unit",
        "run_id",
        "experiment_id",
        "lane",
        "seqbc_id",
        "r1_path",
        "r2_path",
        "seq_platform",
        "lib_prep",
        "sample_type",
        "merge_strategy",
        "stage_directive",
        "stage_target",
    ]
    write_tsv(units_tsv_path, units_header, units_rows)

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
