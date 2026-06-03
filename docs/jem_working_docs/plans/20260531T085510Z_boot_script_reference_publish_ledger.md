# Boot Script Reference Publish Ledger

Date: 2026-05-31

## Objective

Confirm the current DYEC headnode/compute bootstrap script expands `/dev/shm` to 80% of memory on every node, publish that script to the S3 reference locations used by the ParallelCluster YAML, and verify readback hashes. Also confirm BCL Convert scheduling requires `i192mem,i192bigmem` rather than plain `i192`.

## Gate 0 Inventory

| Check | Evidence | Status |
|---|---|---|
| Source boot script | `config/day_cluster/post_install_ubuntu_combined.sh` | SUCCESS |
| Packaged boot script | `daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh` | SUCCESS |
| Source/package equality | `shasum -a 256 ...` reported matching SHA `4a8d190f8185eb90dfcf3747267b7a77e82a10df9d6f611701c92de57705394a`; `cmp_rc=0`. | SUCCESS |
| `/dev/shm` remount contract | Both scripts include `TOTAL_MEM=$(grep MemTotal /proc/meminfo | awk '{print $2}')`, `SHM_SIZE_KB=$((TOTAL_MEM * 80 / 100))`, and `mount -o remount,size=${SHM_SIZE_MB}M /dev/shm`. | SUCCESS |
| pcluster boot object contract | Cluster templates use `${REGSUB_S3_BUCKET_INIT}/post_install_ubuntu_combined.sh`; DYEC resolves `${REGSUB_S3_BUCKET_INIT}` as `<reference_s3_uri>/runtime_assets/cluster_boot_config`. | SUCCESS |
| BCL Convert partition | DayOA `config/day_profiles/slurm/templates/rule_config.yaml` sets `bclconvert.partition: "i192mem,i192bigmem"` and DYEC runtime patching preserves that configured partition for the BCL Convert path. | SUCCESS |

## Publish Targets

| Target | AWS profile | Region | Status | Evidence |
|---|---|---|---|---|
| `s3://lsmc-dayoa-references-usw2/runtime_assets/cluster_boot_config/post_install_ubuntu_combined.sh` | `lsmc` | `us-west-2` | SUCCESS | Backup rc=0; upload rc=0; download rc=0; readback SHA `4a8d190f8185eb90dfcf3747267b7a77e82a10df9d6f611701c92de57705394a`. |
| `s3://daylily-dayoa-references-usw2/runtime_assets/cluster_boot_config/post_install_ubuntu_combined.sh` | `daylily` | `us-west-2` | SUCCESS | Backup rc=0; upload rc=0; download rc=0; readback SHA `4a8d190f8185eb90dfcf3747267b7a77e82a10df9d6f611701c92de57705394a`. |
| `s3://lsmc-dayoa-omics-analysis-ap-south-1/runtime_assets/cluster_boot_config/post_install_ubuntu_combined.sh` | `lsmc` | `ap-south-1` | SUCCESS | Backup rc=0; upload rc=0; download rc=0; readback SHA `4a8d190f8185eb90dfcf3747267b7a77e82a10df9d6f611701c92de57705394a`. |
| `s3://lsmc-dayoa-omics-analysis-eu-central-1/runtime_assets/cluster_boot_config/post_install_ubuntu_combined.sh` | `lsmc` | `eu-central-1` | SUCCESS | Backup rc=0; upload rc=0; download rc=0; readback SHA `4a8d190f8185eb90dfcf3747267b7a77e82a10df9d6f611701c92de57705394a`. |

## Publish Procedure

For each target:

1. Read existing object metadata if present.
2. Copy current object to `runtime_assets/cluster_boot_config/backups/post_install_ubuntu_combined.sh.pre-80pct-shm-20260531T085510Z`.
3. Upload local `config/day_cluster/post_install_ubuntu_combined.sh`.
4. Download the uploaded object to `docs/plans/20260531T085510Z_boot_script_reference_publish_logs/`.
5. Compare downloaded SHA-256 to local SHA-256.

## Results

Publish helper: `docs/plans/20260531T085510Z_publish_boot_script.py`.

Command log and artifacts:

- `docs/plans/20260531T085510Z_boot_script_reference_publish_logs/commands.jsonl`
- `docs/plans/20260531T085510Z_boot_script_reference_publish_logs/summary.json`
- Readback copies under `docs/plans/20260531T085510Z_boot_script_reference_publish_logs/*.post_install_ubuntu_combined.sh`

All four targets reached terminal `SUCCESS`. Backup object used for every bucket:

`runtime_assets/cluster_boot_config/backups/post_install_ubuntu_combined.sh.pre-80pct-shm-20260531T085510Z`

Final readback SHA for every uploaded object:

`4a8d190f8185eb90dfcf3747267b7a77e82a10df9d6f611701c92de57705394a`

Partition note:

- The BCL Convert rule uses Snakemake's configured `partition` resource. The correct control point is the per-rule `partition:` value in the DayOA Slurm profile config, where BCL Convert is set to `i192mem,i192bigmem`.
- A temporary hard-fail guard in `workflow/rules/bclconvert.smk` was removed after review because it duplicated the profile config contract.
