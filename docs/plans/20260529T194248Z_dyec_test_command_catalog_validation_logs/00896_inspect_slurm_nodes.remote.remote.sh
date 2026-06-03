set -euo pipefail
echo "date:"
date -Is
echo
echo "sinfo:"
sinfo -Nel || true
echo
echo "squeue:"
squeue -o "%.18i %.9P %.12j %.8u %.2t %.10M %.6D %R" || true
echo
echo "scontrol_job_2658:"
scontrol show job 2658 || true
echo
echo "node_status:"
scontrol show node i192mem-dy-all-1 || true
