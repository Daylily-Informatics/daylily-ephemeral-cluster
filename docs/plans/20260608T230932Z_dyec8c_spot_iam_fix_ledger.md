# dyec8c Dynamic Spot IAM Fix Ledger

Created: 2026-06-08T23:09:32Z

## Objective

Fix the DayOA dynamic BWA-MEM2A Spot partition ordering IAM blocker that
prevented DYEC command-catalog dry-runs from passing on `dyec8c`.

## Boundaries

- Use AWS profile `lsmc`.
- No cluster create, update, or delete.
- No workflow live runs while fixing IAM.
- Keep the change read-only for EC2 discovery.

## Rows

| Row | Status | Evidence |
| --- | --- | --- |
| G0-001 | PASS | `dyec8c` headnode role is `arn:aws:iam::108782052779:role/parallelcluster/dyec8c/dyec8c-RoleHeadNode-zMWTjwoUJ6y1`; attached policy `arn:aws:iam::108782052779:policy/pclusterTagsAndBudget` default version `v3` contains `ec2:DescribeSpotPriceHistory` but not `ec2:DescribeInstanceTypes`. |
| REPO-001 | PASS | Updated source and packaged environment CloudFormation templates to include `ec2:DescribeInstanceTypes`, `ec2:DescribeInstanceTypeOfferings`, and `ec2:DescribeSpotPriceHistory`. |
| TEST-001 | PASS | Focused tests passed: `10 passed`; full DYEC suite passed: `1069 passed, 8 skipped`. |
| LIVE-001 | PASS | Created live managed policy default version `v4` for `arn:aws:iam::108782052779:policy/pclusterTagsAndBudget` using profile `lsmc`; preserved existing statements and added read-only EC2 discovery actions. |
| VERIFY-001 | PASS | Headnode SSM probe succeeded: `describe-instance-types` and `describe-spot-price-history` both returned `c8id.48xlarge`; one DYEC catalog dry-run smoke reached DayOA `RETURN CODE: 0` for `illumina_snv_alignstats` and exported evidence task `task-0ccb3aeeda0b82051` succeeded. |
| SLURM-001 | PASS_WITH_CAVEAT | Per user request, submitted `sleep 10000` Slurm probes on `dyec8c` through SSM with profile `lsmc`: jobs `1` `i128`, `2` `i128nvme`, `3` `i192`, `4` `i192hugenvme`, `5` `i192nvme`, `6` `i384nvme`, `7` `i8`. Poll showed jobs `1`, `3`, `4`, `6`, `7` in `CONFIGURING`; jobs `2` and `5` `PENDING`. Caveat: Slurm accepted the jobs with `Comment=unknown-project-invalid-project` after budget-wrapper stderr complained about missing `--comment`; no duplicate resubmission was made. |
| REPORT-001 | PENDING | Final changed files, AWS policy version, tests, Slurm probe status, and next dry-run gate. |
