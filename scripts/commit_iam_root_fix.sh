#!/bin/sh
set -e
cd /Users/jmajor/projects/daylily/daylily-ephemeral-cluster-mega/daylily-ephemeral-cluster
git add daylily_ec/aws/iam.py tests/test_iam.py
git commit -m "fix: IAM preflight auto-PASS for root accounts

Root accounts have implicit full access and cannot have IAM policies
attached via the normal user/group mechanism. The preflight now detects
username=='root' and returns PASS with a note instead of FAIL/WARN.

Adds 2 new tests for root account handling (468 total, all pass)."
git push origin feature/cp-001-package-skeleton

