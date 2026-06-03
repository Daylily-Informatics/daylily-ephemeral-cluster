set -euo pipefail

printf 'UTC %s\n' "$(date -u +%FT%TZ)"
printf 'HOST %s USER %s\n' "$(hostname)" "$(whoami)"

echo '--- squeue ---'
squeue || true

echo '--- sacct recent ---'
sacct -S now-6hours -o JobID,JobName%40,State,ExitCode,Elapsed,NodeList%30 | tail -n 120 || true

echo '--- snakemake/controllers ---'
pgrep -af 'snakemake|daylily_run_omics|dy-r|bcl-convert' || true

echo '--- tmux ---'
tmux ls 2>/dev/null || true

echo '--- fsx df ---'
df -h /fsx || true

echo '--- analysis dirs ---'
find /fsx/analysis_results/ubuntu -mindepth 1 -maxdepth 1 -type d -printf '%TY-%Tm-%Td %TH:%TM %p\n' 2>/dev/null \
  | sort \
  | tee /tmp/analysis_dirs_inventory.txt \
  | tail -n 80
printf 'analysis_dir_count=%s\n' "$(wc -l < /tmp/analysis_dirs_inventory.txt)"

echo '--- dra-ish mount roots ---'
find /fsx -maxdepth 3 -type d \( \
  -path '/fsx/references' \
  -o -path '/fsx/control_data' \
  -o -path '/fsx/run_dir_mounts' \
  -o -path '/fsx/run_dir_mounts/*' \
  -o -path '/fsx/staged_external_data' \
  -o -path '/fsx/staging' \
  -o -path '/fsx/staging/*' \
\) -printf '%p\n' 2>/dev/null | sort || true
