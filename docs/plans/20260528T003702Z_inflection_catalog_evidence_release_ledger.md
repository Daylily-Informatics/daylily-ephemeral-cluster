# Inflection Catalog Evidence Release Ledger

Created: 2026-05-28T00:37:02Z

## Gate 0 Inventory

- Controlling request: repeat the release so the new command catalog entry is included.
- Instructions in effect: DYEC `AGENTS.md`, user-provided repo instructions, and `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`.
- DayOA source repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`, remote `git@github.com:Daylily-Informatics/daylily-omics-analysis.git`, branch `main`, status `## main...origin/main`, latest pushed tag `2.0.12`; no dirty DayOA files were present, so no DayOA commit or tag is required for this repeat.
- DYEC source repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`, remote `git@github.com:Daylily-Informatics/daylily-ephemeral-cluster.git`, branch `codex/running-nextflow-pipes-doc`, current tag `5.0.12`, next release tag `5.0.13`.
- Catalog entry check: source and packaged command catalogs include `command_id: inflection-bjuice-product-v0.1` with DayOA `git_tag: 2.0.12`.
- New evidence to include: `docs/plans/20260528T003512Z_inflection_controller_rulegraphs/`, including ignored `logs/` evidence files after secret-pattern scanning.
- Explicit exclusions from staging remain unchanged: `.tailscale_key` is a secret-shaped local key file; `20260514-LH01106-0009-B23TVLGLT4-HIOMRFULL-HG003-a-20260514-Altair3-ONT-full-HIOMR-0-HG003-a-PF-ILMN-NOVASEQ.ont.dmd.sentdhiomr.snv.sort.vcf.gz` is a 559 MiB local VCF artifact; `presign_url_sofar.md` and `docs/plans/20260527T163009Z_hg003_full1022_signed_urls.tsv` contain temporary presigned S3 URLs.

## Execution Rows

| Row | Objective | Evidence | Status |
| --- | --- | --- | --- |
| DAYOA-CHECK | Confirm whether a new DayOA commit/tag is needed. | DayOA `git status --short --branch` returned `## main...origin/main`; no dirty files were available to commit. | SUCCESS |
| DYEC-CATALOG-CHECK | Confirm the new command catalog entry is present in DYEC source and packaged catalogs. | `inflection-bjuice-product-v0.1` is present in `config/daylily_available_repositories.yaml` and packaged payload catalog, with DayOA `git_tag: 2.0.12`. | SUCCESS |
| DYEC-EVIDENCE | Include the Inflection rulegraph and dry-run evidence directory in the next release. | `docs/plans/20260528T003512Z_inflection_controller_rulegraphs/` contains manifest, rulegraph DOT files, dry-run counts, queue summaries, and log evidence; secret-pattern scan returned no hits. | SUCCESS |
| DYEC-SELF-PIN | Update source and packaged DYEC self-pins to `5.0.13`. | `config/daylily_cli_global.yaml` and `daylily_ec/resources/payload/config/daylily_cli_global.yaml` set `git_ephemeral_cluster_repo_tag` and `git_ephemeral_cluster_repo_release_tag` to `5.0.13`. | SUCCESS |
| DYEC-VALIDATE | Validate config parity and focused tests before release. | `cmp -s` passed for source vs packaged global config and catalog; `git diff --check` passed; after `source ./activate`, `pytest -q tests/test_repository_catalog.py tests/test_cli_registry_v2.py::test_samples_run_stages_then_launches_catalog_command tests/test_iam.py tests/test_renderer.py` passed `77 passed`. | SUCCESS |
| DYEC-RELEASE | Commit release contents, push branch, create annotated tag `5.0.13`, and push tag. | Release commit prepared with source and packaged self-pin updates, this ledger, and `docs/plans/20260528T003512Z_inflection_controller_rulegraphs/` evidence files. | SUCCESS |
