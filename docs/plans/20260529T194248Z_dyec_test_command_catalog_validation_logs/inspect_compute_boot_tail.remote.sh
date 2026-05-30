set -euo pipefail
echo "date:"
date -Is
echo
echo "cloud_init_status:"
cloud-init status --long || true
echo
echo "cloud_init_output_tail:"
sudo tail -n 220 /var/log/cloud-init-output.log || true
echo
echo "cloud_init_log_tail:"
sudo tail -n 160 /var/log/cloud-init.log || true
echo
echo "slurmd_status:"
systemctl status slurmd --no-pager -l || true
echo
echo "parallelcluster_logs:"
find /var/log/parallelcluster -maxdepth 2 -type f -printf '%p\n' -exec sudo tail -n 80 {} \; 2>/dev/null || true
