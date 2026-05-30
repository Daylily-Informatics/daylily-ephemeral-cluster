set -euo pipefail
echo "identity:"
id
hostname
date -Is
echo
echo "cloud_init:"
cloud-init status --long || true
echo
echo "systemd_failed:"
systemctl --failed --no-pager || true
echo
echo "slurmd:"
systemctl status slurmd --no-pager -l || true
echo
echo "slurmd_log_tail:"
sudo tail -n 220 /var/log/slurm/slurmd.log 2>/dev/null || true
echo
echo "bootstrap_markers:"
ls -lah /var/log/parallelcluster /var/log/cloud-init* /opt/slurm/sbin/check_tags.sh 2>/dev/null || true
echo
echo "postinstall_mentions:"
sudo grep -RInE 'check_tags|post_install|completion|error|failed' /var/log/cloud-init-output.log /var/log/parallelcluster 2>/dev/null | tail -n 200 || true
