# prod-cand-260809 CLI 1.7.2i Runtime Cache Promotion Ledger

Opened: 2026-08-10T13:19:07Z

## Objective

Promote only the complete non-symlink Conda environment created by the live
HIOMR2 CLI-1.7.2i checkpoint proof into the canonical cache that seeds future
clusters. The prior 30-environment promotion completed successfully and is not
repeated.

## Frozen contract

- Cluster/headnode: `prod-cand-260809`, `us-west-2`, `ip-10-0-0-13`.
- Candidate: `0233798f12c3ebe5938ba5446a32e9ef_`.
- Source bytes: `3069662769`.
- Adjacent YAML: 873 bytes, SHA-256
  `2880a986a8fa8b63314c00c8df955cec24c180a29e11f663e4e9818d1ca8ed06`.
- Candidate is a real directory, has `conda-meta/history`, and its adjacent
  YAML is a real file. It is not a seeded symlink.
- No Conda/mamba creation or Apptainer/Singularity pull/build process remained
  after environment creation.
- Baseline Slurm job `544` and candidate Slurm job `548` were both `RUNNING`.
- Zero real container image misses exist.
- Canonical destination:
  `s3://lsmc-dayoa-references-usw2/runtime_assets/cached_envs/conda/`.
- Relay destination:
  `s3://lsmc-ssf-sequencing-data/derived/validation/prod-cand-260809-init-test-x2-20260810/cache-promotion/20260810T131907Z/cached_envs/conda/`.
- Initial collision gate: candidate prefix KeyCount `0` and adjacent YAML
  `HeadObject` 404 in both relay and canonical destinations.

## Control ledger

| ID | Requirement | Status | Evidence |
|---|---|---:|---|
| C172-CACHE-001 | Freeze one complete real environment after build/pull processes end and Slurm is running | SUCCESS | Contract above |
| C172-CACHE-002 | Prove exact relay and canonical destinations are absent | SUCCESS | Both exact prefixes empty; both YAML HEADs returned 404 |
| C172-CACHE-003 | Stage source to authorized relay without deleting or overwriting | SUCCESS | Headnode tmux `runtime_cache_promote_cli172i_prod_cand_20260810` completed at `2026-08-10T13:41:14Z` with RC 0; helper `20260810T131907Z_prod_cand_cli172i_cache_promote.sh` preserved manifest/status/RC evidence |
| C172-CACHE-004 | Publish relay to canonical S3 and verify zero differences | SUCCESS | Local tmux `runtime_cache_publish_cli172i_prod_cand_20260810` completed at `2026-08-10T14:03:48Z` with RC 0; canonical prefix contains 88,468 objects and 6,302,730,273 bytes; post-publish `aws s3 sync --dryrun` evidence is zero bytes; adjacent YAML is 873 bytes and retains SHA-256 `2880a986a8fa8b63314c00c8df955cec24c180a29e11f663e4e9818d1ca8ed06` |
| C172-CACHE-005 | Verify future-cluster DRA visibility and preserve manifests/status/RC | SUCCESS | Read-only headnode check found the directory, adjacent YAML, and `conda-meta/history` under `/fsx/references/runtime_assets/cached_envs/conda/0233798f12c3ebe5938ba5446a32e9ef_`; local cache and relay were preserved |

The S3 object-byte total is larger than the source `du` total because the AWS
copy followed environment-internal symlinks into object keys; the frozen root
itself was a real cache miss, not a seeded root symlink.

All rows terminal: yes

Objective complete: yes
