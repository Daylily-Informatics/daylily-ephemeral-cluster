# dyec0602bcl BCL2FQ Cluster And 25B ILMN Run Mount Ledger

Created: 2026-06-02T23:54:33Z

## Control

- Ledger path: `docs/plans/20260602T235433Z_dyec0602bcl_bcl2fq_run_mount_ledger.md`
- Log directory: `docs/plans/20260602T235433Z_dyec0602bcl_bcl2fq_run_mount_logs/`
- DYEC input config: `docs/plans/20260602T235433Z_dyec0602bcl_bcl2fq_run_mount_config.yaml`
- Target cluster: `dyec0602bcl`
- Profile: `lsmc`
- Region/AZ: `us-west-2d`
- Region: `us-west-2`
- Cluster template: `config/day_cluster/prod_cluster.yaml`
- Required BCL partition: `bcl2fq`
- Source cluster evidence: `dyec5117`, `CREATE_COMPLETE`, compute fleet `RUNNING`
- Source run mount: `20260514_LH01106_0009_B23TVLGLT4`
- Source S3 URI: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0009_B23TVLGLT4/`
- Target headnode path: `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/`

## Gate 0 Baseline

- Repo: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster`
- Branch: `codex/dyec515-full-catalog-20260531...origin/codex/dyec515-full-catalog-20260531`
- Initial dirty state: existing modified files include `AGENTS.md`, `README.md`, cluster templates under `config/day_cluster/` and `daylily_ec/resources/payload/config/day_cluster/`, `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`, and prior BCL status JSON. Existing untracked benchmark and prior ledger artifacts under `bench_expts/` and `docs/plans/` are treated as user/prior-agent work and not modified except this new ledger/config/log directory.
- Instruction files read: `/Users/jmajor/.agents/AGENTS.md`, `/Users/jmajor/.agents/AGENTS-HOW-TO-RUN-DAYOA.md`, `/Users/jmajor/.codex/AGENTS.md`, `/Users/jmajor/.codex/memories/fallback_and_legacy_and_migration_support_for_code_changes_DO_NOT_UNLESS_TOLD_TO_PLEASE.md`, `/Users/jmajor/.codex/memories/aws-destructive-changes.md`, `AGENTS.md`, `AGENTS-HOW-TO-RUN-DAYOA.md`, `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`.
- `pcluster describe-cluster --region us-west-2 -n dyec0602bcl` with `AWS_PROFILE=lsmc` returned not found before create.
- `dyec5117` source mount evidence: `dra-0ab55b552007f1d6f`, source S3 URI above, read-only, lifecycle `AVAILABLE`, headnode path `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/`.

## Guardrails

- Do not use default AWS credentials; every AWS/DYEC command must use `AWS_PROFILE=lsmc` or `--profile lsmc`.
- Do not delete clusters, FSx data, DRAs, S3 objects, Slurm jobs, or scheduler state without separate explicit approval in this thread.
- Do not launch DayOA workflow work in this ledger. If later requested, use `dy-r` only inside a persistent interactive `ubuntu` tmux login shell.
- Do not use fallback paths, inferred mounts, alternate clusters, service-side discovery as a substitute for explicit config, or raw `aws ssm send-command`.

## Execution Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Baseline | Record instructions, repo state, source mount, and target availability before live work. | SUCCESS | legitimate_safety_handling | Gate 0 | Agent 1 | Gate 0 section in this ledger; `dyec0602bcl` not found; source `dyec5117` mount listed. |  | Baseline complete before create. |
| CFG-001 | Config | Create explicit DYEC input config for `dyec0602bcl` using `prod_cluster.yaml` and `profile=lsmc` values. | SUCCESS | config_or_startup_contract | Gate 0 | Agent 1 | `docs/plans/20260602T235433Z_dyec0602bcl_bcl2fq_run_mount_config.yaml`. |  | Config pins cluster name, S3 URIs, subnets, IAM policy, headnode, FSx size, and template. |
| CL-001 | Preflight | Run DYEC preflight for `dyec0602bcl` in `us-west-2d` with `--profile lsmc`. | SUCCESS | feature_implementation | Gate 1 | Agent 2 | First attempt `preflight.stdout_stderr.txt` exposed a plan-local config triplet issue; retry `preflight_retry1.stdout_stderr.txt` passed 12 checks. |  | Preflight passed after config made explicit in both default and set triplet positions. |
| CL-002 | Create | Create `dyec0602bcl` with the explicit config. | SUCCESS | feature_implementation | Gate 1 | Agent 2 | `create.stdout_stderr.txt`: cluster created in 22m 7s, headnode configured, budgets and heartbeat configured, state written to `/Users/jmajor/.config/daylily/state_dyec0602bcl_20260602235841.json`. |  | Create wrapper exited 0. Rendered YAML: `/Users/jmajor/.config/daylily/dyec0602bcl_cluster_20260602235841.yaml`. |
| CL-003 | Verify cluster | Poll until cluster is `CREATE_COMPLETE`, compute fleet is `RUNNING`, and rendered config includes `bcl2fq`. | SUCCESS | feature_implementation | Gate 2 | Agent 3 | `describe_after_create.json`: `clusterStatus=CREATE_COMPLETE`, `cloudFormationStackStatus=CREATE_COMPLETE`, `computeFleetStatus=RUNNING`; rendered YAML lines 246, 258, 269, 270, 281, 292, 293 show `bcl2fq` and `i4i`/`i3en` resources. |  | Cluster ready for mount work. |
| MNT-001 | Mount | Create read-only DRA for the 25B ILMN run on `dyec0602bcl`. | SUCCESS | feature_implementation | Gate 3 | Agent 4 | `mount_create.stdout_stderr.json`: first wait timed out while DRA `dra-04d1f5b3dd1cc75a4` was `CREATING`; `aws_fsx_dra_final.json` later shows lifecycle `AVAILABLE`; local projection reconciled at `/Users/jmajor/.config/daylily/run_mounts/us-west-2/dyec0602bcl/20260514_LH01106_0009_B23TVLGLT4.json`. | FSx DRA became available after the DYEC 900-second wait timeout, before final verification. | Final mount list shows `platform=ILMN`, `local_projection_status=present`, `read_only=true`, and lifecycle `AVAILABLE`. |
| MNT-002 | Verify mount | Verify mount is usable from the headnode at `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/`. | SUCCESS | feature_implementation | Gate 3 | Agent 4 | `mount_verify_by_mount_id.stdout_stderr.json`: `verified=true`, SSM command `a2fa357b-f093-42ff-a923-39d9591ad107`, headnode instance `i-0c36c39770c533c8e`, `usable=true`. |  | Headnode can use `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4`. |
| ACC-001 | Acceptance | Record final cluster, FSx, DRA association, source URI, mount path, and no workflow launch. | SUCCESS | feature_implementation | Gate 4 | Agent 5 | `describe_final.json`: cluster `CREATE_COMPLETE`, compute fleet `RUNNING`; `mount_list_after_projection.json`: association `dra-04d1f5b3dd1cc75a4`, FSx `fs-05f90a39933f9b539`, source S3 URI, headnode path, `platform=ILMN`, `read_only=true`. |  | No DayOA workflow launched; no Slurm/job/scheduler intervention performed. |
| REP-001 | Report | Report terminal row counts and residual blockers. | SUCCESS | plan_amendment | Gate 4 | Agent 1 | This ledger and final response. |  | All 9 execution rows are terminal SUCCESS. |

## Command Plan

```bash
source ./activate

dyec preflight \
  --profile lsmc \
  --region-az us-west-2d \
  --config docs/plans/20260602T235433Z_dyec0602bcl_bcl2fq_run_mount_config.yaml \
  --non-interactive

dyec create \
  --profile lsmc \
  --region-az us-west-2d \
  --config docs/plans/20260602T235433Z_dyec0602bcl_bcl2fq_run_mount_config.yaml \
  --non-interactive

dyec --json mounts create \
  s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0009_B23TVLGLT4/ \
  --profile lsmc \
  --region us-west-2 \
  --cluster dyec0602bcl \
  --mount-id 20260514_LH01106_0009_B23TVLGLT4 \
  --run-id 20260514_LH01106_0009_B23TVLGLT4 \
  --platform ILMN \
  --read-only \
  --wait

dyec --json mounts verify \
  --profile lsmc \
  --region us-west-2 \
  --cluster dyec0602bcl \
  --mount-id 20260514_LH01106_0009_B23TVLGLT4 \
  --platform ILMN
```

## Read/Write Amendment

Created: 2026-06-03T01:03:13Z

- User approved adding the minimal `.atlas_rw` marker object and updating the existing DRA in place to add `AutoExportPolicy=NEW,CHANGED`; user explicitly said not to delete from S3.
- Marker created at `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260514_LH01106_0009_B23TVLGLT4/.atlas_rw`; evidence `rw_put_atlas_marker.json` and `rw_head_atlas_marker.json`.
- Existing association `dra-04d1f5b3dd1cc75a4` was updated in place; no remount/delete/recreate was performed.
- Update preserved `AutoImportPolicy=NEW,CHANGED` and added `AutoExportPolicy=NEW,CHANGED`; no `DELETED` auto-export event was enabled.
- `rw_dra_update_poll.log` shows lifecycle `UPDATING` from `2026-06-03T01:01:03Z` through `2026-06-03T01:02:05Z`, then `AVAILABLE` at `2026-06-03T01:02:35Z`.
- `rw_mount_list_final.json` shows `read_only=false`, `auto_export_events=["NEW","CHANGED"]`, `auto_import_events=["NEW","CHANGED"]`, `platform=ILMN`, and lifecycle `AVAILABLE`.
- `rw_mount_verify_final.json` shows `verified=true` and `usable=true` on headnode instance `i-0c36c39770c533c8e` for `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4`.
