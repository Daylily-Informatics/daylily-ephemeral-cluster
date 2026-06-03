# DYEC5128 Runtime Env Cache Promotion Ledger

Opened: 2026-06-03T13:41:49Z

## Objective

Promote completed DayOA runtime cache artifacts from the active `dyec5128` FSx
cache into the reference S3 cached-env prefixes so future clusters can seed
them without rebuilding:

```text
s3://lsmc-dayoa-references-usw2/runtime_assets/cached_envs/conda/
s3://lsmc-dayoa-references-usw2/runtime_assets/cached_envs/containers/
```

## Guardrails

- Copy only completed conda env directories with `conda-meta/history`.
- Copy each conda env's matching `*.yaml` file when present.
- Copy container images from writable runtime/cache paths only after identifying
  image names or hashes where possible.
- Do not delete local cache artifacts.
- Do not modify Slurm jobs or DayOA workflow controllers.
- Do not make the shared cache mount writable as part of this task.

## Source Paths To Inspect

```text
/fsx/resources/environments/conda/
/fsx/resources/environments/containers/
/fsx/tmp/apptainer_cache/
/fsx/tnmp/apptainer_cache/
```

## Destination

```text
s3://lsmc-dayoa-references-usw2/runtime_assets/cached_envs/
```

## Status

| Step | Status | Notes |
|---|---:|---|
| Inventory cache sources | complete | Found 20 complete conda env dirs under `/fsx/resources/environments/conda/ubuntu/ip-10-0-0-24`, no real non-symlink `.simg/.sif` files under `/fsx/resources/environments/containers`, and real Nextflow cache dirs `/fsx/resources/environments/nextflow/{24.10.5,java-21}`. |
| Identify `/fsx/tmp` or `/fsx/tnmp` Apptainer usage | complete | `/fsx/tmp/apptainer_cache/cache/net` contains 5 valid SIF cache objects. `/fsx/tnmp/apptainer_cache` is absent. Active DayOA profile env files still set `/fsx/tmp/apptainer_cache/${dayoa_user}/${dayoa_host}`; DYEC shell init had the same stale default and was patched locally. |
| Promote completed conda envs | in_progress | Initial headnode upload failed: `dyec5128-RoleHeadNode-OPuRnHqhyjxj` lacked `s3:PutObject` on `lsmc-dayoa-references-usw2`. Temporary inline policy `dyec5128-runtime-cache-promotion-20260603` was attached, scoped to `runtime_assets/cached_envs/*`; remote sync is running. |
| Promote container images/cache blobs | in_progress | Existing `.simg` files are already symlinks to reference cache. Apptainer net-cache objects are being promoted under `runtime_assets/cached_envs/apptainer_cache/cache/net/`; headnode config now seeds `/fsx/resources/environments/apptainer/cache/net`. |
| Promote Nextflow cache | in_progress | Headnode config now seeds `runtime_assets/cached_envs/nextflow` into `/fsx/resources/environments/nextflow`; remote sync is running for current `nextflow/{24.10.5,java-21}` contents. |
| Distribute headnode config | partial | Source and packaged `post_install_ubuntu_combined.sh` updated. Published to `s3://lsmc-dayoa-references-usw2/runtime_assets/cluster_boot_config/post_install_ubuntu_combined.sh` with backup and matching readback SHA `b4ceb67d51a2636bdf3e566f9d47b9cb4ebe2a1186a2b90a1e6e967f92c84b8f`. Daylily target blocked: `daylily-dayoa-references-usw2` is not visible/existing to local `lsmc` or `daylily` profiles. |
| Verify S3 destination | pending | |
