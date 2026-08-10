# prod-cand-260809 Runtime Cache Promotion Ledger

Opened: 2026-08-10T05:57:25Z

## Objective

While the DayOA `13.4.10` HG002 5x ILMN by 5x ONT HIOMR2 workflow continues,
promote only the complete non-symlink runtime cache misses created on headnode
`ip-10-0-0-13` into the canonical S3 cache that seeds future clusters:

```text
s3://lsmc-dayoa-references-usw2/runtime_assets/cached_envs/conda/
s3://lsmc-dayoa-references-usw2/runtime_assets/cached_envs/containers/
```

## Guardrails

- Do not stop, requeue, alter, or administer the DayOA controller or Slurm.
- Require genuinely running Slurm jobs and no active conda/container build or
  pull process before freezing candidates.
- Copy only real conda directories with `conda-meta/history` and a matching
  real adjacent YAML. Never copy seeded cache symlinks.
- Copy only nonempty real `.simg` or `.sif` files. Never dereference seeded
  container symlinks.
- Do not upload incomplete or temporary artifacts, overwrite S3 keys, delete
  local/S3 data, or make `/fsx/references` writable.
- A nonempty destination prefix or existing YAML/container key is a hard stop.
- Any temporary write authority must be limited to the frozen exact keys,
  expire automatically, and be removed after verification.

## Gate 0 Baseline

| Item | Evidence |
|---|---|
| Cluster/headnode | `prod-cand-260809`, `us-west-2`, `ip-10-0-0-13`, headnode role `prod-cand-260809-RoleHeadNode-eadPOAt3UaZr` |
| Live workflow | Session `dayoa_init_test_x2_hg002_5x5x_13410_live_20260810`; jobs `7`, `8`, and `9` were `RUNNING` at 2026-08-10T05:53:09Z, including ONT and ILMN preparation. |
| Build/pull gate | No `conda env create`, mamba/micromamba create, Apptainer/Singularity pull, or container build process at 2026-08-10T05:53:09Z. |
| Conda cache | 30 real hash directories; all have `conda-meta/history` plus a real adjacent YAML. There are 127 seeded conda symlinks excluded from promotion. |
| Container cache | Zero real `.simg`/`.sif` misses; three seeded container symlinks excluded from promotion. |
| Collision preflight | At 2026-08-10T05:56:38Z all 30 exact S3 environment prefixes had `KeyCount=0` and all 30 YAML HEAD checks returned absent. |
| Existing permissions | Headnode `S3Access` grants read/list on the reference bucket and read/write on the DYEC relay bucket. The exact inline reference-cache policy attempt was rejected by the role's aggregate inline-policy quota, with no policy installed. |

## Execution Ledger

| ID | Action | Status | Evidence / notes |
|---|---|---:|---|
| CACHE-001 | Verify live-workflow and cache-build gates. | SUCCESS | Three Slurm jobs running; no cache build/pull process. |
| CACHE-002 | Freeze complete non-symlink candidate set. | SUCCESS | 30 conda environments; zero real container images. |
| CACHE-003 | Verify exact S3 collision state. | SUCCESS | 30 empty prefixes and 30 absent YAML keys. |
| CACHE-004 | Install expiring least-privilege write policy for exact frozen destinations. | SUPERSEDED | `PutRolePolicy` failed with `LimitExceeded: Maximum policy size ... exceeded`; no policy was installed and the role policy set was unchanged. Use the existing write-authorized DYEC relay without widening IAM. |
| CACHE-005 | Stage frozen cache entries to the isolated authorized relay in persistent Ubuntu tmux. | SUCCESS | Headnode tmux `runtime_cache_promote_prod_cand_20260810`; terminal status `SUCCESS 2026-08-10T09:51:54Z rc=0`; manifest contains one header plus all 30 candidates. |
| CACHE-006 | Server-side copy the frozen relay objects to the canonical cache. | SUCCESS | Local tmux `runtime_cache_publish_prod_cand_20260810`; terminal status `SUCCESS 2026-08-10T10:29:30Z rc=0`; canonical manifest contains one header plus all 30 candidates. No environment payload was downloaded locally. |
| CACHE-007 | Verify canonical S3 readback and future-cluster linkage contract. | SUCCESS | Every environment passed zero post-upload/publish sync differences and matching YAML size before its manifest row was written; both terminal RC files contain `0`. |

## Frozen Conda Candidates

```text
082c686fea1dcb2e746ed6db73354d1a_
36d377f2690370c395cad3d44fcb97ff_
3a4066336aa1dec4d6bc615e5e6cbb16_
41bdd5851090dbb2336356a3f0be2473_
4ff65c6aaa4e6658e7c422971c95ee85_
766fb474be68885012083f6c622f6179_
88aa4998af771810a00fe2cb10e21246_
92f8bbc953659a4d8cf233a75d457e3f_
957e87d5fe4ac8a44e5724ce50a149a1_
9a8eaaa988c7096ecb77708fde347089_
a443e7e684bb6c610530885db6664055_
af0132e7fe10ee4cd05c1b877bcd09e8_
b26a7b457aa6640a1af9af0f76be96a2_
b3a9d533cd18cabddbe62f2713320a54_
bf30457594bff473900e8811233cd47a_
bf9ae2783a216ee7f6faf43a364179db_
c2e451114a625144ab03840e398ea712_
c9170b1232ccf7ec20f43ced852fb8c2_
caa10c232eb19f6543aa45820fda8f74_
cba901145cdb176cc8ee56f2aac12b87_
ccc71549f5b9bbb8371ee8cfe43bf60c_
cda71b1de49e4d37d9611dd7d2715e4b_
ce665216e6cf27f7dd1729335b653c5b_
d4b04c8d5d3069cacc630f531de5d173_
d64dacd09ba579b5d7cacdfc400033c5_
d8d3b1575e41db2f7ea52b3fb3531258_
dccc9356e3c60edb825fa3a21a2296ae_
df47ac2d26fef6f0eace26f819bda392_
e64cde7284147387e31d87ada68f2d1c_
ec5a7de2ea751bbceef716fb67d26c3a_
```

## Execution Notes

- 2026-08-10T06:05:29Z: the headnode promoter passed its repeated frozen
  candidate and relay collision checks and started under `ubuntu` with
  `nice 10`, low I/O priority, four S3 transfer workers, and one environment
  at a time.
- 2026-08-10T06:08:50Z: the local publisher started after independently
  confirming all 30 canonical destinations were empty. It treats the relay
  YAML, which is written only after the headnode's zero-difference tree check,
  as the per-environment completion marker.
- 2026-08-10T06:14:13Z: canonical environment
  `082c686fea1dcb2e746ed6db73354d1a_` completed with a zero-difference
  S3-to-S3 sync check and matching YAML size.
- 2026-08-10T09:51:54Z: headnode relay promoter completed all 30 candidates
  with `rc=0`.
- 2026-08-10T10:29:30Z: local canonical publisher completed all 30 candidates
  with `rc=0`; the canonical manifest contains 30 data rows.
- The later CLI-1.7.2i environment miss
  `0233798f12c3ebe5938ba5446a32e9ef_` was created after this candidate set was
  frozen and is tracked separately in
  `20260810T131907Z_prod_cand_cli172i_runtime_cache_promotion_ledger.md`.
