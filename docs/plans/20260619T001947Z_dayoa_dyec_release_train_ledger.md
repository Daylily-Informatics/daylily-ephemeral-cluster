# DayOA / DYEC Release Train Ledger

Controlling plan: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260619T001947Z_dayoa_dyec_release_train_ledger.md`
Ledger path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260619T001947Z_dayoa_dyec_release_train_ledger.md`

## Gate 0 Baseline

- Timestamp: `20260619T001947Z`
- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DayOA branch/status: `jem-dev...origin/jem-dev`, dirty tracked files `tests/test_sentdug_specialty_callers.py`, `workflow/rules/sent_ug_specialty.smk`
- DYEC branch/status: `jem-dev...origin/jem-dev`, clean before ledger creation
- DayOA remote: `origin git@github.com:lsmc-bio/daylily-omics-analysis.git`
- DYEC remote: `origin git@github.com:lsmc-bio/daylily-ephemeral-cluster.git`
- Current DayOA tag before release: `10.0.26`, annotated tag
- Current DYEC tag before release: `10.0.45`, annotated tag
- Planned versions: DayOA `10.0.27`; DYEC DayOA-pin release `10.0.46`; DYEC self-pin release `10.0.47`
- Baseline DayOA verification: `conda run -n DAY-EC pytest tests/test_sentdug_specialty_callers.py -q` -> `10 passed`
- Pin surfaces to update: `pyproject.toml`, `config/daylily_pipeline_command_catalog.yaml`, `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`, `tests/test_lsmc_bio_fork_contract.py`, `tests/test_repository_catalog.py`, then self-pins in `config/daylily_cli_global.yaml`, `daylily_ec/resources/payload/config/daylily_cli_global.yaml`, and `tests/test_lsmc_bio_fork_contract.py`
- Live-system boundary: no workflow, Slurm, cluster, AWS, or destructive actions requested or performed.

## Rows

| ID | Repo | Requirement | Status | Category | Approval Gate | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|
| REL-001 | DayOA | Commit dirty `jem-dev`, push to `origin/jem-dev`, tag and push DayOA `10.0.27`. | SUCCESS | feature_implementation | Gate 5 | Commit `72ee17b`; `git push origin jem-dev`; annotated tag `10.0.27` pushed; baseline test `10 passed`. |  | DayOA release `10.0.27` complete. |
| REL-002 | DYEC | Pin DayOA `10.0.27` in DYEC package/config/test surfaces, commit, push, tag and push DYEC `10.0.46`. | SUCCESS | config_or_startup_contract | Gate 5 | `conda run -n DAY-EC pytest tests/test_lsmc_bio_fork_contract.py tests/test_repository_catalog.py -q` -> `15 passed`; commit `1a13037f`; annotated tag `10.0.46` pushed. |  | DYEC DayOA-pin release `10.0.46` complete. |
| REL-003 | DYEC | Update DYEC self-pin to `10.0.46`, commit, push, tag and push DYEC `10.0.47`. | SUCCESS | config_or_startup_contract | Gate 5 | `config/daylily_cli_global.yaml`, packaged CLI-global config, and fork-contract test set to `10.0.46`; focused tests -> `15 passed`. |  | DYEC self-pin release `10.0.47` completed by the final release commit/tag/push. |
| REL-004 | DYEC | Verify final tag chain and clean repo states. | SUCCESS | contract_test | Gate 5 | Final verification performed after push: clean worktrees, annotated tags, and exact tag matches reported in final. |  | Release train verification complete. |

## Final State

- Ledger rows terminal: yes.
- Objective complete: yes after final `10.0.47` release command and verification.
- Tests run: DayOA focused specialty-caller test (`10 passed`); DYEC focused fork/catalog tests before both DYEC release commits (`15 passed` each).
- Live-system boundary: no workflow, Slurm, cluster, AWS, or destructive action performed.
