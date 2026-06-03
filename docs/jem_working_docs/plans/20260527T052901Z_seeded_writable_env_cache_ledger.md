# Seeded Writable DayOA Environment Cache Ledger

Date opened: 2026-05-27T05:29:01Z

Controlling request: restore the previous cache model where the read-only reference runtime cache seeds a writable FSx environment cache, and new Snakemake conda/container cache entries are created beside the seeded entries.

Ledger path: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/plans/20260527T052901Z_seeded_writable_env_cache_ledger.md`

## Gate 0 Inventory

- Instructions read: DAY-EC repo `AGENTS.md`, DayOA repo `AGENTS.md`, and `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`.
- DAY-EC repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`, branch `main`, dirty state includes unrelated GoodOle3/blahab44/Kahlo/Sarek plan artifacts and `docs/plans/20260526T224018Z_blahab44_catalog_runs.jsonl`; preserve them.
- DayOA repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`, branch `main`, clean at baseline.
- Current DAY-EC boot contract: `config/day_cluster/post_install_ubuntu_combined.sh` reads runtime assets from `/fsx/references/runtime_assets/cached_envs` directly and does not create `/fsx/resources/environments`.
- Current DayOA profile contract: `conda-prefix` is writable `/fsx/resources/environments/conda/USER_REGSUB/HOSTNAME`, but `singularity-prefix` is read-only `/fsx/references/runtime_assets/cached_envs/containers`.
- Historical implementation evidence: DAY-EC commit `e754bfad` used `link_cached_entries` to seed `/fsx/resources/environments/{conda,containers}/{ubuntu,daylily}/$(hostname)` from the mounted cache.
- Live blahab44 evidence: writable conda cache under `/fsx/resources/environments/conda/ubuntu/ip-10-0-0-224` is about `15G`; reference runtime cache S3 prefix `s3://lsmc-dayoa-references-usw2/runtime_assets/cached_envs/` is `10.974 GiB`; Roche dry-run failed because missing container was looked up under the read-only reference container prefix.

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CACHE-001 | DAY-EC boot | Seed writable `/fsx/resources/environments` conda and container caches from `/fsx/references/runtime_assets/cached_envs` during headnode config. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | `config/day_cluster/post_install_ubuntu_combined.sh` and packaged payload mirror now define `environment_cache_root=/fsx/resources/environments`, create writable conda/container cache dirs for `ubuntu` and `daylily`, and `link_cached_entries` from `${runtime_assets_root}/cached_envs/{conda,containers}` into each host-specific writable cache root. |  | New clusters will seed writable DayOA cache roots from the read-only mounted reference cache; new cache entries can be created in the writable roots. |
| CACHE-002 | DAY-EC readiness | Validate seeded writable cache dirs as part of headnode readiness. | SUCCESS | contract_test | Gate 2 | orchestrator | `daylily_ec/headnode_readiness.py` now checks `/fsx/resources/environments/conda/ubuntu/$(hostname)` and `/fsx/resources/environments/containers/ubuntu/$(hostname)`; `tests/test_headnode_readiness.py` covers the contract. |  | Headnode readiness fails hard if the writable seeded cache dirs are not present. |
| CACHE-003 | DayOA profiles | Point Snakemake `singularity-prefix` at the same writable seeded environment cache namespace as conda. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | DayOA `config/day_profiles/local/templates/config.yaml` and `config/day_profiles/slurm/templates/config.yaml` now use `singularity-prefix: "/fsx/resources/environments/containers/USER_REGSUB/HOSTNAME"`; `tests/test_multiqc_sample_identifiers.py` rejects the read-only reference container prefix. |  | DayOA will write newly pulled container images beside seeded cached images in the writable FSx cache. |
| CACHE-004 | Validation | Run focused DAY-EC and DayOA tests proving the new cache contract. | SUCCESS | contract_test | Gate 5 | orchestrator | DAY-EC: `source ./activate >/dev/null && python -m pytest tests/test_headnode_init.py tests/test_headnode_readiness.py tests/test_resources_extraction.py -q -> 19 passed`; `source ./activate >/dev/null && python -m pytest tests/test_packaged_defaults.py tests/test_repository_catalog.py -q -> 14 passed`. DayOA: `eval "$(conda shell.zsh hook)" && conda activate DAY-EC && python -m pytest tests/test_multiqc_sample_identifiers.py -q -> 26 passed`; `eval "$(conda shell.zsh hook)" && conda activate DAY-EC && python -m pytest tests/test_slurm_profile.py tests/test_shell_wrapper_contracts.py -q -> 12 passed`. |  | Focused cache-contract tests passed. |

## Final State

- All rows are terminal.
- Objective implemented locally in DAY-EC and DayOA source.
- No live cluster mutation, S3 copy, or destructive AWS action was performed.
