#!/bin/bash
set -e
PEM=~/.ssh/lsmc-omics-us-west-2.pem
IP=34.215.222.242
SSH="ssh -i $PEM ubuntu@$IP -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

echo "=== Step 1: Generate SSH key (force overwrite) ==="
$SSH "yes | ssh-keygen -q -t rsa -f ~/.ssh/id_rsa -N ''" 2>&1 || true

echo "=== Step 2: Show public key ==="
$SSH "cat ~/.ssh/id_rsa.pub" 2>&1

echo "=== Step 3: Clone daylily-ephemeral-cluster and install ==="
$SSH "mkdir -p ~/projects && cd ~/projects && \
  if [ -d daylily-ephemeral-cluster ]; then echo 'repo already cloned'; \
  else git clone -b main https://github.com/lsmc-bio/daylily-ephemeral-cluster.git daylily-ephemeral-cluster; fi && \
  cd daylily-ephemeral-cluster && \
  (./bin/install_miniconda 2>&1 || echo 'miniconda install note') && \
  (./bin/init_dayec 2>&1 || echo 'init_dayec note')" 2>&1

echo "=== Step 4: Install headnode tools ==="
$SSH "source ~/.bashrc && cd ~/projects/daylily-ephemeral-cluster && ./bin/install-daylily-headnode-tools" 2>&1 || true

echo "=== Step 5: Verify squeue ==="
$SSH "squeue" 2>&1

echo "=== DONE ==="

