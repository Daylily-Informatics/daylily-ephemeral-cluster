set -euo pipefail
echo '=== headnode reference compatibility path ==='
if [[ -e /fsx/data && ! -L /fsx/data ]]; then
  if [[ "$(readlink -f /fsx/data)" != /fsx/references ]]; then
    echo 'ERROR: /fsx/data exists but does not resolve to /fsx/references' >&2
    exit 1
  fi
else
  sudo ln -sfn /fsx/references /fsx/data
fi
test -L /fsx/data
test "$(readlink -f /fsx/data)" = /fsx/references
ls -ld /fsx/data
echo '=== compute-node reference compatibility path ==='
export PROJECT=dyec-test
mapfile -t node_rows < <(sinfo -h -N -o '%N|%P' | sed 's/*//g' | sort -u)
if [[ ${#node_rows[@]} -eq 0 ]]; then
  echo 'ERROR: no Slurm compute nodes are visible' >&2
  exit 1
fi
for row in "${node_rows[@]}"; do
  node=${row%%|*}
  partition=${row#*|}
  partition=${partition%%,*}
  echo "--- $node partition=$partition"
  srun --overlap --partition="$partition" --nodes=1 --ntasks=1 --nodelist="$node" bash -lc 'set -euo pipefail; if [[ -e /fsx/data && ! -L /fsx/data ]]; then if [[ "$(readlink -f /fsx/data)" != /fsx/references ]]; then echo "ERROR: /fsx/data exists but does not resolve to /fsx/references" >&2; exit 1; fi; else sudo ln -sfn /fsx/references /fsx/data; fi; test -L /fsx/data; test "$(readlink -f /fsx/data)" = /fsx/references; ls -ld /fsx/data'
done