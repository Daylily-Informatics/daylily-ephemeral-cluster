#!/usr/bin/env bash
set -euo pipefail

old_tmux="hybonly_stage_ilmn_20260606T010256Z"
new_tmux="hybonly_stage_ilmn_parallel_20260606T010256Z"
remote_script="/home/ubuntu/hyb_only_stage_ilmn_parallel_20260606T010256Z.sh"
log_dir="/fsx/scratch/ILMN/logs"
mkdir -p "$log_dir"

cat > "$remote_script" <<'REMOTE_SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C

root="/fsx/run_dir_mounts/ilmn-lh01121-b23ww2nlt4-fastq"
dest_dir="/fsx/scratch/ILMN"
tmp_dir="$dest_dir/tmp"
log_dir="$dest_dir/logs"
manifest_dir="$log_dir/parallel_manifests"
done_dir="$log_dir/parallel_done"
err_dir="$log_dir/parallel_errors"
main_log="$log_dir/stage_commands_parallel.log"
jobs="${ILMN_STAGE_JOBS:-4}"

mkdir -p "$tmp_dir" "$log_dir" "$manifest_dir" "$done_dir" "$err_dir"
test -d "$root"

expected="$log_dir/expected_ilmn_stage_files.tsv"
{
  sample_num=1
  for hg_num in 001 002 003 004 005 006 007; do
    for rep in a b c; do
      for read in R1 R2; do
        printf 'HG%s\tAltair-HG%s-%s_S%s_%s_001.fastq.gz\n' \
          "$hg_num" "$hg_num" "$rep" "$sample_num" "$read"
      done
      sample_num=$((sample_num + 1))
    done
  done
  for read in R1 R2; do
    printf 'NA00232\tNA00232-SMN_S46_%s_001.fastq.gz\n' "$read"
  done
  for read in R1 R2; do
    printf 'NA09677\tNA09677-SMN_S47_%s_001.fastq.gz\n' "$read"
  done
  for read in R1 R2; do
    printf 'NA03986\tNA03986-DMPK_S48_%s_001.fastq.gz\n' "$read"
  done
  for read in R1 R2; do
    printf 'NA05164\tNA05164-DMPK_S49_%s_001.fastq.gz\n' "$read"
  done
} > "$expected"

count="$(wc -l < "$expected" | tr -d ' ')"
if [[ "$count" != "50" ]]; then
  printf 'ERROR expected 50 ILMN FASTQs, found %s in %s\n' "$count" "$expected" >&2
  exit 2
fi

printf 'start_ilmn_parallel\t%s\tjobs=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$jobs" | tee -a "$main_log"
df -h /fsx | tee -a "$main_log"

stage_one() {
  local sample="$1"
  local base="$2"
  local src="$root/$base"
  local dest="$dest_dir/$base"
  local tmp="$tmp_dir/$base.tmp.$(hostname).$$.$RANDOM"
  local per_log="$log_dir/parallel_${base}.log"
  local manifest="$manifest_dir/${base}.tsv"
  local done="$done_dir/${base}.ok"
  local err="$err_dir/${base}.err"

  rm -f "$err"
  test -s "$src"
  {
    printf 'CMD\t%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$src" "$dest"
    if [[ ! -s "$dest" ]]; then
      cp -- "$src" "$tmp"
      mv -f "$tmp" "$dest"
    fi
    gzip -t "$dest"
    printf 'sample\tsource\tdest\tbytes\n' > "$manifest"
    printf '%s\t%s\t%s\t%s\n' "$sample" "$src" "$dest" "$(stat -c '%s' "$dest")" >> "$manifest"
    printf 'DONE\t%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$base" "$(stat -c '%s' "$dest")"
    touch "$done"
  } > "$per_log" 2>&1 || {
    rc=$?
    printf 'FAIL\t%s\t%s\trc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$base" "$rc" | tee "$err" >&2
    rm -f "$tmp"
    return "$rc"
  }
}
export root dest_dir tmp_dir log_dir manifest_dir done_dir err_dir main_log
export -f stage_one

awk -F '\t' '{print $1 "\t" $2}' "$expected" \
  | xargs -n 2 -P "$jobs" bash -c 'stage_one "$1" "$2"' _

done_count="$(find "$done_dir" -maxdepth 1 -type f -name '*.ok' | wc -l | tr -d ' ')"
if [[ "$done_count" != "50" ]]; then
  printf 'ERROR expected 50 validated ILMN FASTQs, got %s\n' "$done_count" >&2
  exit 3
fi

printf 'sample\tsource\tdest\tbytes\n' > "$log_dir/source_manifest_parallel.tsv"
find "$manifest_dir" -maxdepth 1 -type f -name '*.tsv' -print0 \
  | sort -z \
  | xargs -0 awk 'FNR > 1 { print }' >> "$log_dir/source_manifest_parallel.tsv"
cp "$log_dir/source_manifest_parallel.tsv" "$log_dir/source_manifest.tsv"

df -h /fsx | tee -a "$main_log"
printf 'finish_ilmn_parallel\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$main_log"
REMOTE_SCRIPT

chmod +x "$remote_script"

{
  printf 'replace_serial_ilmn\t%s\told_tmux=%s\tnew_tmux=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$old_tmux" "$new_tmux"
  if tmux has-session -t "$old_tmux" 2>/dev/null; then
    tmux kill-session -t "$old_tmux"
    printf 'old_tmux_killed\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  else
    printf 'old_tmux_absent\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  fi
} | tee -a "$log_dir/serial_stage_replaced.log"

if tmux has-session -t "$new_tmux" 2>/dev/null; then
  tmux kill-session -t "$new_tmux"
fi
tmux new-session -d -s "$new_tmux" \
  "bash -l -c '$remote_script > $log_dir/tmux_stage_ilmn_parallel.stdout.txt 2> $log_dir/tmux_stage_ilmn_parallel.stderr.txt; rc=\$?; echo \$rc > $log_dir/tmux_stage_ilmn_parallel.rc; exit \$rc'"
printf 'launched_ilmn_parallel\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$new_tmux"
