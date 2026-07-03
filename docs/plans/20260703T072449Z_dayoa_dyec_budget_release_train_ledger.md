# DayOA / DYEC Budget Release Train Ledger

Created: 2026-07-03T07:24:49Z

## Gate 0 Inventory Freeze

- Controlling request: commit dirty DayOA work to `jem-dev`, push and tag a new DayOA version; update DYEC DayOA pins, commit/push/tag a DYEC version; update DYEC self-pin to that DYEC version, commit/push/tag a follow-up DYEC version; report final tags.
- Primary repos:
  - DayOA: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`, branch `jem-dev`, starting head `79c5689`, remote branch `origin/jem-dev`, local branch ahead by 1 before this release train.
  - DYEC: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch `jem-dev`, starting head `633eca30`, remote branch `origin/jem-dev`.
- Baseline dirty state:
  - DayOA modified: `AGENTS.md`, `README.md`, `config/day_profiles/local/templates/rule_config.yaml`, `config/day_profiles/slurm/templates/config.yaml`, `config/day_profiles/slurm/templates/rule_config.yaml`, `config/external_tools/multiqc_config.yaml`, `config/global.yaml`, `docs/examples/multiqc/README.md`, `docs/ops/dycli.md`, `docs/workflows/bclconvert.md`, `tests/test_htd_callers_contract.py`, `tests/test_multiqc_qc_targets.py`, `tests/test_slurm_profile.py`, `workflow/Snakefile`, `workflow/rules/common.smk`, `workflow/rules/hapsma.smk`, `workflow/rules/htd_calls.smk`, `workflow/rules/multiqc_final_wgs.smk`, `workflow/rules/sma_finder.smk`, `workflow/rules/smaca.smk`, `workflow/rules/smn12_orthogonal_calls.smk`, `workflow/rules/smn_copynumbercaller.smk`; untracked: `workflow/rules/smn12_input_qc.smk`, `workflow/scripts/smn12_input_qc.py`.
  - DYEC modified before this release request included budget-enforcement implementation plus pre-existing dirty docs: `AGENTS.md`, `README.md`, `config/day_cluster/post_install_ubuntu_combined.sh`, `config/day_cluster/sbatch`, `config/daylily_ephemeral_cluster_template.yaml`, `daylily_ec/**`, docs, and tests; untracked: `docs/plans/20260703T064534Z_dyec_budget_enforcement_ledger.md`, `tests/test_sbatch_wrapper.py`.
- Tag baseline:
  - DayOA local/remote max semver tag: `10.0.51`.
  - DYEC local/remote max semver tag: `10.0.78`.
- Planned tags:
  - DayOA dirty release: `10.0.52`.
  - DYEC DayOA-pin/budget release: `10.0.79`.
  - DYEC self-pin follow-up release: `10.0.80`.
- Version/tag rules: non-`v` semver tags; annotated tags; commit before tag; do not move pushed tags.
- Live-system boundary: no live cluster creation, AWS resource mutation, Slurm job submission, PR merge, or package publication requested in this release train.

## Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| ORCH-001 | Ledger | Record Gate 0, selected versions, and terminal row counts. | IN_PROGRESS | feature_implementation | Gate 0 | orchestrator | This ledger. |  |  |
| DAYOA-001 | DayOA | Stage dirty DayOA work, commit to `jem-dev`, push branch, create annotated tag `10.0.52`, push tag. | SUCCESS | feature_implementation | Gate 1 | orchestrator | Commit `0b5e912`; `git push origin jem-dev` succeeded; annotated tag `10.0.52` pushed; `git cat-file -t 10.0.52 -> tag`; focused DayOA tests `99 passed`. |  | DayOA dirty release is pushed and tagged as `10.0.52`. |
| DYEC-001 | DYEC DayOA pin | Update DYEC DayOA pins to `10.0.52`, include current DYEC dirty budget-enforcement work, commit to `jem-dev`, push branch, tag `10.0.79`, push tag. | IN_PROGRESS | feature_implementation | Gate 2 | orchestrator | DYEC DayOA pins updated from `10.0.51` to `10.0.52`; focused DYEC suite `335 passed`. |  |  |
| DYEC-002 | DYEC self pin | Update DYEC self pin to `10.0.79`, commit to `jem-dev`, push branch, tag `10.0.80`, push tag. | OPEN | feature_implementation | Gate 2 | orchestrator | DYEC self-pin config and tests. |  |  |
| VAL-001 | Validation | Run focused local checks sufficient for the release train and verify annotated tags. | OPEN | contract_test | Gate 5 | orchestrator | Test commands and `git cat-file -t`. |  |  |

## Final Terminal Report

Pending execution.
