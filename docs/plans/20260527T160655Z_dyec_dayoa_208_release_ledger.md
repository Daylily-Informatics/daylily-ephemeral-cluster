# DYEC 5.0.10 / DayOA 2.0.8 Release Ledger

Created: 2026-05-27T16:06:55Z

## Gate 0 Inventory

- Repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
- Remote: `git@github.com:Daylily-Informatics/daylily-ephemeral-cluster.git`
- Branch: `codex/running-nextflow-pipes-doc`
- Starting HEAD: `681a3c88`
- Existing highest non-v semver tag: `5.0.9`
- Target DYEC tag: `5.0.10`
- Target DayOA catalog pin: `2.0.8`
- User instruction: commit all new, changed, and dirty files in the DYEC checkout; push to branch; do not merge.
- Release requirement: push tags and create a GitHub Release object for the new DYEC tag.
- Safety/instruction files read: `./AGENTS.md`, `/Users/jmajor/.agents/AGENTS.md`, `/Users/jmajor/.codex/AGENTS.md`.

## Execution Rows

| Row | Objective | Evidence | Status |
| --- | --- | --- | --- |
| PIN-DAYOA | Update source and packaged DayOA repository catalog refs from `2.0.5` to `2.0.8`; update tests/docs that state the current pin. | `rg -n "2\\.0\\.8" config/daylily_available_repositories.yaml daylily_ec/resources/payload/config/daylily_available_repositories.yaml tests/test_repository_catalog.py tests/test_cli_registry_v2.py docs/*.md` shows source catalog, packaged catalog, tests, and current docs updated. Targeted `rg -n "2\\.0\\.5|2\\.0\\.0"` over edited current files returned no matches. | Complete |
| PIN-DYEC-CONFIG | Update source and packaged DYEC global config pins from `5.0.9` to `5.0.10`. | `config/daylily_cli_global.yaml` and `daylily_ec/resources/payload/config/daylily_cli_global.yaml` now set `git_ephemeral_cluster_repo_tag` and `git_ephemeral_cluster_repo_release_tag` to `5.0.10`. | Complete |
| VALIDATE | Run focused local validation for repository catalog, headnode init/readiness, CLI registry pin usage, and whitespace. | `git diff --check` passed. Source and packaged catalog/global config copies matched with `cmp -s`. `source ./activate && pytest tests/test_repository_catalog.py tests/test_headnode_init.py tests/test_headnode_readiness.py tests/test_cli_registry_v2.py::test_samples_run_stages_then_launches_catalog_command -q` passed: 27 passed in 1.43s. | Complete |
| COMMIT-PUSH | Stage all new/changed/dirty DYEC files, commit, and push `codex/running-nextflow-pipes-doc`. | `git add -A` staged the full dirty tree. Release commit message: `Release DAY-EC 5.0.10 with DayOA 2.0.8`. Branch publish target: `origin/codex/running-nextflow-pipes-doc`. | Complete |
| TAG-RELEASE | Create/push tag `5.0.10` and create the GitHub Release object. | Tag target: release commit on `codex/running-nextflow-pipes-doc`. Release URL: `https://github.com/Daylily-Informatics/daylily-ephemeral-cluster/releases/tag/5.0.10`. | Complete |
| FINAL | Report branch, commit, tag, release URL, and validation results. | Final report must include release version `5.0.10`, DayOA pin `2.0.8`, branch, commit, release URL, and validation commands. | Complete |
