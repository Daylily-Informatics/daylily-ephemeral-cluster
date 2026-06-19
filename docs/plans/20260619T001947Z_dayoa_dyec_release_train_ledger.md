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
| REL-002 | DYEC | Pin DayOA `10.0.27` in DYEC package/config/test surfaces, commit, push, tag and push DYEC `10.0.46`. | IN_PROGRESS | config_or_startup_contract | Gate 5 | Pin surfaces identified in Gate 0. |  |  |
| REL-003 | DYEC | Update DYEC self-pin to `10.0.46`, commit, push, tag and push DYEC `10.0.47`. | OPEN | config_or_startup_contract | Gate 5 | Prior release cadence verified: `10.0.45` self-pins `10.0.44`. |  |  |
| REL-004 | DYEC | Verify final tag chain and clean repo states. | OPEN | contract_test | Gate 5 | Pending release checks. |  |  |
