# Slurm Bootstrap Memory Scheduling Override Ledger

Created: 2026-07-08T19:57:00Z

## Request

Turn off the DYEC bootstrap rewrite that forces Slurm `SelectTypeParameters=CR_CPU_Memory`, then report what else in the bootstrap scripts rewrites Slurm configuration outside the ParallelCluster YAML/config path.

## Gate 0 Inventory

- Repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch: `jem-dev`
- Baseline HEAD: `f34d25a36a9728a5848856d6726bd3569408e843`
- Baseline dirty state included pre-existing catalog/runtime report work:
  - `M docs/plans/20260708T142032Z_intel_catalog_bjuice_jul8itelx4_dyec_10_0_118_ledger.md`
  - `M docs/plans/20260708T142032Z_intel_catalog_bjuice_selected_commands.json`
  - `M docs/plans/20260708T142032Z_intel_catalog_bjuice_selected_commands.tsv`
  - untracked `docs/plans/20260708T142032Z_intel_catalog_bjuice_runtime/illumina_run_qc/`
  - untracked `docs/plans/20260708T191757Z_jul8itelx4_catalog_progress_packing_report.md`
  - untracked `docs/plans/20260708T192900Z_jul8itelx4_cost_progress/`
  - untracked `docs/plans/20260708T192900Z_jul8itelx4_percent_complete_spot_cost_report.md`
  - untracked `docs/plans/20260708T194417Z_jul8itelx4_benchmark_resource_review.md`
  - untracked `docs/plans/20260708T194417Z_jul8itelx4_benchmark_resource_review/`
- Source scripts inspected:
  - `config/day_cluster/post_install_ubuntu_combined.sh`
  - `config/day_cluster/post_install_rhel8_dragen.sh`
- Packaged payload scripts inspected:
  - `daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh`
  - `daylily_ec/resources/payload/config/day_cluster/post_install_rhel8_dragen.sh`
- Tests inspected:
  - `tests/test_headnode_init.py`
  - `tests/test_packaged_defaults.py`
- Live system boundary: no live headnode patching, no Slurm restart, and no S3 boot-config publish were approved or performed as part of this ledger.

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Evidence | Terminal Note |
|---|---|---|---|---|---|---|---|
| SLURM-001 | Ubuntu boot script | Stop forcing `SelectTypeParameters=CR_CPU_Memory` while preserving explicit partition oversubscription behavior. | SUCCESS | config_or_startup_contract | Gate 2 | `config/day_cluster/post_install_ubuntu_combined.sh`; `bash -n config/day_cluster/post_install_ubuntu_combined.sh` passed. | Removed the code path that rewrote or appended `SelectTypeParameters`; the helper now only rewrites `PartitionName` `OverSubscribe` values. |
| SLURM-002 | RHEL/DRAGEN boot script | Stop forcing `SelectTypeParameters=CR_CPU_Memory` while preserving explicit partition oversubscription behavior. | SUCCESS | config_or_startup_contract | Gate 2 | `config/day_cluster/post_install_rhel8_dragen.sh`; `bash -n config/day_cluster/post_install_rhel8_dragen.sh` passed. | Removed the code path that rewrote or appended `SelectTypeParameters`; the helper now only rewrites `PartitionName` `OverSubscribe` values. |
| SLURM-003 | Packaged payload | Keep packaged boot payload copies byte-identical to source scripts. | SUCCESS | contract_test | Gate 2 | `diff -u` source vs packaged payload for Ubuntu and RHEL scripts produced no output; packaged scripts passed `bash -n`. | Packaged payload copies match the source scripts. |
| SLURM-004 | Tests | Update tests to reject the memory-scheduling override and retain checks for intended Slurm mutations. | SUCCESS | contract_test | Gate 2 | `pytest tests/test_headnode_init.py tests/test_packaged_defaults.py -q` -> 33 passed. | Tests now assert the old `SelectTypeParameters=CR_CPU_Memory` injection and heredoc branch are absent. |
| SLURM-005 | Audit report | Report remaining Slurm config changes performed by bootstrap scripts outside the PCluster YAML/config path. | SUCCESS | config_or_startup_contract | Gate 5 | `rg -n "slurm\\.conf|systemctl restart slurmctld|append_once ...|OverSubscribe=|SelectTypeParameters"` over source and payload scripts. | Remaining Slurm touch points are documented below. |

## Verification

- `source ./activate && pytest tests/test_headnode_init.py tests/test_packaged_defaults.py -q` -> 33 passed.
- `bash -n config/day_cluster/post_install_ubuntu_combined.sh` -> passed.
- `bash -n config/day_cluster/post_install_rhel8_dragen.sh` -> passed.
- `bash -n daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh` -> passed.
- `bash -n daylily_ec/resources/payload/config/day_cluster/post_install_rhel8_dragen.sh` -> passed.
- Source vs packaged payload `diff -u` for both boot scripts -> no output.
- `rg -n "SelectTypeParameters=CR_CPU_Memory|line\\.startswith\\(\\\"SelectTypeParameters=\\\"\\)|has_select_type_parameters|SelectTypeParameters=" config/day_cluster daylily_ec/resources/payload/config/day_cluster tests/test_headnode_init.py tests/test_packaged_defaults.py` -> only negative test assertions remain.

## Remaining Slurm Bootstrap Mutations Outside PCluster YAML

The following remain in source and packaged payload scripts after this change:

- Ubuntu and RHEL/DRAGEN still rewrite every `PartitionName=` row in `/opt/slurm/etc/slurm.conf` so `OverSubscribe=YES`, and fail hard if any `OverSubscribe=EXCLUSIVE` remains.
- Ubuntu and RHEL/DRAGEN still append these Slurm config lines to `/opt/slurm/etc/slurm.conf` with `append_once` on the headnode:
  - `AccountingStoreFlags=job_comment`
  - `PrologFlags=Alloc`
  - `Prolog=/opt/slurm/sbin/prolog.sh`
  - `Epilog=/opt/slurm/sbin/epilog.sh`
- Ubuntu and RHEL/DRAGEN still create `/opt/slurm/sbin/check_tags.sh`, `/opt/slurm/sbin/prolog.sh`, and `/opt/slurm/sbin/epilog.sh` to tag compute instances with active Slurm user/job metadata.
- Compute nodes still install a per-minute cron entry for `/opt/slurm/sbin/check_tags.sh`.
- Headnodes still replace wrapper paths for `sbatch`/`srun` and install `sleep_test.sh` from the boot-config S3 prefix.
- Ubuntu restarts `slurmctld` after wrapper installation and again after Slurm config/prolog/epilog changes.
- RHEL/DRAGEN restarts `slurmctld` once after wrapper installation plus Slurm config/prolog/epilog changes.

## Live Deployment Boundary

This ledger changed local source and packaged payload files only. It did not publish boot config to S3, patch `jul8itelx4`, or restart Slurm on any live cluster.

`dyec create` publishes `post_install_rhel8_dragen.sh`, `post_install_ubuntu_combined.sh`, `sbatch`, and `sleep_test.sh` through `publish_cluster_boot_config()` before cluster creation, so a future create run from this updated checkout/package payload will upload the corrected scripts through the approved create path.
