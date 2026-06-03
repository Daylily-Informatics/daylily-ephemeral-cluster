set -euo pipefail
export PROJECT=dyec-test
job_id=2654
echo '=== before ==='
squeue -j "$job_id" -o '%i|%P|%C|%t|%M|%D|%R|%j' || true
scancel "$job_id" || true
sleep 2
echo '=== after ==='
squeue -j "$job_id" -o '%i|%P|%C|%t|%M|%D|%R|%j' || true