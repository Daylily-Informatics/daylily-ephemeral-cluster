set -euo pipefail
aid=ccv20260529r8_inflection-bjuice-product-v0.1_dryrun
run_dir=/fsx/analysis_results/ubuntu/$aid
repo_dir=$run_dir/daylily-omics-analysis
echo "=== whoami ==="
id
echo "=== tmux sessions ==="
tmux ls || true
echo "=== target tmux ==="
if tmux has-session -t "=$aid" 2>/dev/null; then
  echo "tmux_session=present"
else
  echo "tmux_session=absent"
fi
echo "=== process search ==="
ps -eo pid,ppid,user,stat,lstart,cmd | grep "$aid" | grep -v grep || true
echo "=== run dir ==="
if [[ -d "$run_dir" ]]; then
  ls -la "$run_dir"
  find "$run_dir" -maxdepth 2 -type f -printf '%TY-%Tm-%TdT%TH:%TM:%TS %s %p\n' | sort
else
  echo "missing $run_dir"
fi
echo "=== status ==="
if [[ -f "$run_dir/status.json" ]]; then
  cat "$run_dir/status.json"
else
  echo "missing status.json"
fi
echo "=== bootstrap log ==="
if [[ -f "$run_dir/tmux-bootstrap.log" ]]; then
  cat "$run_dir/tmux-bootstrap.log"
else
  echo "missing tmux-bootstrap.log"
fi
echo "=== tmux log ==="
if [[ -f "$run_dir/tmux.log" ]]; then
  tail -n 200 "$run_dir/tmux.log"
else
  echo "missing tmux.log"
fi
echo "=== launch script head ==="
if [[ -f "$run_dir/launch.sh" ]]; then
  sed -n '1,80p' "$run_dir/launch.sh"
else
  echo "missing launch.sh"
fi
echo "=== repo dir ==="
if [[ -d "$repo_dir" ]]; then
  ls -la "$repo_dir" | head -n 40
else
  echo "missing $repo_dir"
fi
