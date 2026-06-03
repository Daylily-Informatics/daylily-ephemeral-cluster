from daylily_ec.aws.ssm import run_shell


INSTANCE_ID = "i-0c36c39770c533c8e"
REGION = "us-west-2"
PROFILE = "lsmc"

SCRIPT = r'''
set -euo pipefail
REPO=/fsx/analysis_results/dyec0602bcl/bcl2fq_scratch_dra_dayoa_20260603/daylily-omics-analysis
PATCH=/home/ubuntu/daylily-runs/bcl2fq_scratch_to_dra_20260603T011121Z/dayoa_bcl_scratch_20260603.patch
RUN_DIR=/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4
cd "$REPO"
git apply --check "$PATCH"
git apply "$PATCH"
python3 -c 'import csv, pathlib; sample_sheet=pathlib.Path("/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/SampleSheet.csv"); out=pathlib.Path("config/samples.tsv"); rows=[]; in_data=False; header=None; seen=set();
for raw in sample_sheet.read_text(encoding="utf-8-sig").splitlines():
    line=raw.strip();
    if line == "[BCLConvert_Data]": in_data=True; header=None; continue
    if line.startswith("[") and line != "[BCLConvert_Data]": in_data=False
    if not in_data or not line: continue
    cells=next(csv.reader([raw]));
    if header is None:
        header=[c.strip() for c in cells]; continue
    row={h:(cells[i].strip() if i < len(cells) else "") for i,h in enumerate(header)}; sid=row.get("Sample_ID", "").strip();
    if sid and sid not in seen: seen.add(sid); rows.append(sid)
if not rows: raise SystemExit("no Sample_ID rows found in mounted SampleSheet")
out.write_text("SAMPLEID\tSAMPLESOURCE\tSAMPLECLASS\tBIOLOGICAL_SEX\tCONCORDANCE_CONTROL_PATH\tIS_POSITIVE_CONTROL\tIS_NEGATIVE_CONTROL\tSAMPLE_TYPE\tTUM_NRM_SAMPLEID_MATCH\tEXTERNAL_SAMPLE_ID\tN_X\tN_Y\tTRUTH_DATA_DIR\n" + "".join(f"{sid}\tblood\tresearch\tunknown\tna\tfalse\tfalse\tblood\tna\t{sid}\tna\tna\tna\n" for sid in rows), encoding="utf-8")
print(f"wrote {out} with {len(rows)} samples")'
python3 -c 'from pathlib import Path; p=Path("config/bclconvert_scratch_dra.yaml"); p.write_text("""bootstrap_bclconvert: true
bclconvert:
  run_id: fasts_from_bclconvert
  run_dir: /fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4
  sample_sheet: /fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/SampleSheet.csv
  output_root: /fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4
  partition: bcl2fq
  constraint: "--constraint=nvme48"
  threads: 48
  mem_mb: 300000
  tmpdir: /scratch/dayoa_bclconvert_tmp
  scratch_output_root: /scratch/dayoa_bclconvert
  parallel_tiles: 8
  conversion_threads: 2
  compression_threads: 24
  decompression_threads: 8
  tile_shard_level: lane
  tile_shard_lanes: ""
  tile_shard_threads: 48
  tile_shard_mem_mb: 300000
  tile_parallel_tiles: 8
  tile_conversion_threads: 2
  tile_compression_threads: 24
  tile_decompression_threads: 8
  merge_lane_fastqs: false
  merge_tile_fastqs: false
  shared_thread_odirect_output: false
  fastq_gzip_compression_level: 1
  output_legacy_stats: true
  num_unknown_barcodes_reported: 1000
  strict_mode: false
  first_tile_only: false
  sampleproject_subdirectories: false
  keep_undetermined_fastqs: true
""", encoding="utf-8"); print(f"wrote {p}")'
git diff --check
git status --short
wc -l config/samples.tsv
sed -n '1,80p' config/bclconvert_scratch_dra.yaml
'''


result = run_shell(
    INSTANCE_ID,
    REGION,
    SCRIPT,
    profile=PROFILE,
    timeout=180,
    comment="Patch DayOA checkout",
)
print("command_id=" + result.command_id)
print(result.stdout, end="")
if result.stderr:
    print(result.stderr, end="")
