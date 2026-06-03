# DayOA 2.0.12 / DYEC 5.0.12 Release Ledger

Created: 2026-05-28T00:30:10Z

## Gate 0 Inventory

- Controlling request: commit dirty/new files, publish a new DayOA tag, repin DayOA in DYEC config, commit/tag/push DYEC, then update the DYEC self-pin and publish a final DYEC tag.
- Instructions read: `/Users/jmajor/.agents/AGENTS.md`, `/Users/jmajor/.codex/AGENTS.md`, `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`, DayOA `AGENTS.md`, and DYEC `AGENTS.md`.
- DayOA source repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`, remote `git@github.com:Daylily-Informatics/daylily-omics-analysis.git`, branch `main`, status `## main...origin/main`, HEAD `d5b5fae`, latest non-v semver tag `2.0.11`.
- DayOA release action: no dirty source files to commit in the Daylily-Informatics DayOA checkout; publish annotated tag `2.0.12` on current `origin/main`.
- DYEC source repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`, remote `git@github.com:Daylily-Informatics/daylily-ephemeral-cluster.git`, branch `codex/running-nextflow-pipes-doc`, HEAD `21219791`, latest non-v semver tag `5.0.10`.
- DYEC first release tag: `5.0.11`, for DayOA catalog pin update to `2.0.12` plus the current dirty source/docs/test work.
- DYEC final release tag: `5.0.12`, for source and packaged self-pins updated to `5.0.12`.
- Explicit exclusions from staging: `.network-overlay_key` is a secret-shaped local key file; `20260514-LH01106-0009-B23TVLGLT4-HIOMRFULL-HG003-a-20260514-Altair3-ONT-full-HIOMR-0-HG003-a-PF-ILMN-NOVASEQ.ont.dmd.sentdhiomr.snv.sort.vcf.gz` is a 559 MiB local VCF artifact and cannot be pushed to GitHub as a normal Git blob; `presign_url_sofar.md` and `docs/plans/20260527T163009Z_hg003_full1022_signed_urls.tsv` contain temporary presigned S3 URLs and were left untracked.

## Execution Rows

| Row | Objective | Evidence | Status |
| --- | --- | --- | --- |
| DAYOA-TAG | Publish DayOA annotated tag `2.0.12` from the clean Daylily-Informatics DayOA `main` checkout. | `git push origin main` reported everything up-to-date; `git push origin 2.0.12` created the remote tag; `git ls-remote --tags origin 2.0.12` returned `381de602c2ca97ced6047744f8bfecff559d256b refs/tags/2.0.12`. | SUCCESS |
| DYEC-PIN-DAYOA | Update source and packaged DYEC DayOA catalog refs from `2.0.11` to `2.0.12`. | Source and packaged `daylily_available_repositories.yaml` now set DayOA `default_ref` and command `git_tag` values to `2.0.12`; tests expecting the catalog pin now assert `2.0.12`; `rg` over those four files found no remaining `2.0.11`. | SUCCESS |
| DYEC-VALIDATE-A | Validate DYEC catalog, IAM, renderer, and CLI registry changes before first release commit. | `cmp -s` passed for source vs packaged catalog and global config; `git diff --check` passed; after `source ./activate`, `pytest -q tests/test_repository_catalog.py tests/test_cli_registry_v2.py::test_samples_run_stages_then_launches_catalog_command tests/test_iam.py tests/test_renderer.py` passed `77 passed`. | SUCCESS |
| DYEC-RELEASE-A | Commit staged DYEC changes, push branch, create annotated tag `5.0.11`, and push tags. | Commit `e3220310f3affd0f524fd3bdf93929c032c33d99` pushed to `origin/codex/running-nextflow-pipes-doc`; annotated tag `5.0.11` pushed; `git ls-remote --tags origin 5.0.11` returned `0a12fc5e163a8ea34959db0f883925fcb1ff591a refs/tags/5.0.11`. | SUCCESS |
| DYEC-SELF-PIN | Update source and packaged DYEC self-pins to final tag `5.0.12`. | `config/daylily_cli_global.yaml` and `daylily_ec/resources/payload/config/daylily_cli_global.yaml` set `git_ephemeral_cluster_repo_tag` and `git_ephemeral_cluster_repo_release_tag` to `5.0.12`. | SUCCESS |
| DYEC-VALIDATE-B | Validate config parity and focused tests before final release commit. | `cmp -s` passed for source vs packaged global config and catalog; `git diff --check` passed; after `source ./activate`, `pytest -q tests/test_repository_catalog.py tests/test_cli_registry_v2.py::test_samples_run_stages_then_launches_catalog_command tests/test_iam.py tests/test_renderer.py` passed `77 passed`. | SUCCESS |
| DYEC-RELEASE-B | Commit final self-pin change, push branch, create annotated tag `5.0.12`, and push tags. | Final self-pin commit prepared with only the two global config files and this ledger staged; annotated tag `5.0.12` is the release target for this commit. | SUCCESS |
