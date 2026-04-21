#!/bin/bash
set -e
PEM=~/.ssh/lsmc-omics-us-west-2.pem
IP=34.215.222.242
SSH="ssh -i $PEM ubuntu@$IP -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

echo "=== Step 1: Force regenerate SSH key ==="
$SSH "rm -f ~/.ssh/id_rsa ~/.ssh/id_rsa.pub && ssh-keygen -q -t rsa -f ~/.ssh/id_rsa -N ''" 2>&1

echo "=== Step 2: Init DAY-EC via login shell ==="
$SSH "bash -l -c 'cd ~/projects/daylily-ephemeral-cluster && ./bin/init_dayec'" 2>&1

echo "=== Step 3: Verify squeue ==="
$SSH "bash -l -c 'export PATH=/opt/slurm/bin:\$PATH && squeue'" 2>&1

echo "=== Step 4: Verify conda + DAY-EC ==="
$SSH "bash -l -c 'conda activate DAY-EC 2>/dev/null && echo DAY-EC_OK || echo DAY-EC_MISSING'" 2>&1

echo "=== DONE ==="

