# Majors Cluster Candidate Bootstrap Ledger

Created: `2026-07-19T10:18:08Z`

## Control Ledger

Controlling request: user request in the current Codex task.

Ledger path: `docs/plans/20260719T101808Z_majors_headnode_candidate_bootstrap_ledger.md`

Gate 0 baseline:

- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch `main`, behind `origin/main` by 41 commits, with two pre-existing untracked ledgers under `docs/plans/`.
- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`, branch `codex/feat-multiqc-integrity-release-11.0.24`, with pre-existing untracked plan artifacts.
- Exact DayOA candidate commit `1818223c3dfc9fc9e8227db40a8fc29224406b4d` exists locally with subject `Complete HIOMRS six-manifest runtime integration`; no local tag points at it.
- DYEC tag `12.0.2` is annotated and resolves to commit `a1d8b1207cd99d67300b8fcc55021636ba4df58e`.
- Live target is only `majors-cluster` in profile `lsmc`, region `us-west-2`, accessed as `ubuntu` using `dyec headnode connect`.
- The requested Slurm job submission and removal of Conda environments `DAY-EC` and `DAYOA` are explicitly authorized. No analysis-root mutation or destructive AWS action is authorized.
- The DayOA `13.0.8` tag is not assumed to exist until verified. Missing ref or missing checkout identity must fail hard rather than select another version.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| AMEND-001 | Plan | Treat repeated request after exact cap restatement as second explicit approval; use exact DayOA commit as the candidate identity | SUCCESS | plan_amendment | Gate 2 | orchestrator | User repeated the full requested workflow after the exact `RnD` `$500` mutation and DayOA tag/commit conflict were reported. |  | Second approval accepted; exact commit wins over later published tag tree. |
| COST-001 | DYEC registry | Create active `RnD` with monthly cap `$500`, initial usage `$0`, allowed user `ubuntu`, no groups or owner email | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Created `2026-07-19T10:41:07Z`; live `show` returned status `active`, cap `500`, allowed user `ubuntu`, no groups/owners. |  | Exact double-approved registry record created. |
| RUN-001 | majors-cluster / Slurm | Submit `sleep 100000` with comment `RnD` to partition `i8` | SUCCESS | feature_implementation | Gate 1 | orchestrator | `sbatch --comment RnD --partition i8 --wrap='sleep 100000'` -> job `251`; `scontrol` showed `Comment=RnD`, partition `i8`; later `squeue` showed `RUNNING` on `i8-dy-price8-1`. |  | Exact requested workload submitted and running. |
| ENV-001 | majors-cluster / Conda | Remove exactly Conda envs `DAY-EC` and `DAYOA` | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Both removal transactions completed; a follow-up `conda env list` returned neither name. Subsequent requested DYEC activation recreated `DAY-EC`; subsequent `dyoainit` recreated `DAYOA` before failing at Mermaid CLI. |  | Removal boundary was proven; later recreation came from requested initialization steps. |
| DAYOA-001 | DayOA | Establish a `~/dayoa` checkout at candidate `13.0.8`, exact commit `1818223c3dfc9fc9e8227db40a8fc29224406b4d` | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Authenticated-local complete Git bundle SHA-256 `50db5ef5bb329e1c4e16b456d7e56d843a269fd13fb876100fa378dd70ca00b8`; headnode checkout clean and detached at exact requested commit. |  | Exact candidate commit installed without substituting published tag tree `6f93cada...`. |
| DYEC-001 | DYEC | Use DYEC `12.0.2` through its supported `source ./activate` entrypoint | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Corrected bundle source after detecting an initial wrong-repo tag artifact; transferred bundle SHA-256 `3bf64d90a5502d73b126a9891600a31641dc13b3b726513aecaf4cf791b5b759`; `~/dyec` clean at `a1d8b120...`, annotated tag type `tag`; `source ./activate` and `dyec version` -> `12.0.2`. |  | Exact DYEC checkout and activation succeeded. |
| SESSION-001 | majors-cluster | Exit, reconnect through CLI, and finish at `~/dayoa` | SUCCESS | feature_implementation | Gate 5 | orchestrator | Exited first Session Manager shell, reconnected through `dyec headnode connect`, and changed directory to `/home/ubuntu/dayoa`. |  | Requested reconnect boundary completed. |
| BUILD-001 | DayOA | From `~/dayoa`, run `source dyoainit`, then `dy-b BUILD` | BLOCKED | config_or_startup_contract | Gate 2 | orchestrator | `source dyoainit` ran from exact commit but returned `1`. Conda/pip created `DAYOA` and installed Snakemake fork `7.25.0b113` at `f866b1f...`; Mermaid CLI install failed because Chrome cache `linux-148.0.7778.97` exists while `chrome-linux64/chrome` is missing. `dy-b BUILD` was not run. | DayOA initialization failed before the supported build command. | Stopped under the required DayOA failure contract; no overlapping or fallback build attempted. |
| DYACT-001 | DayOA | Start a fresh Ubuntu login shell, source `dyoainit`, then `dy-a slurm hg38` | BLOCKED | config_or_startup_contract | Gate 5 | orchestrator | `dy-b` resolved to `/home/ubuntu/projects/daylily-ephemeral-cluster/bin/init_dayec`; that canonical checkout is clean DYEC `11.0.4` at `93e0042...`, not `~/dyec` `12.0.2`. | BUILD-001 failed and DayOA's canonical DYEC alias does not point at the requested `12.0.2` checkout. | No `dy-a` command was run through the wrong DYEC identity. |
| VERSION-001 | DayOA | Report workflow engine version after successful `dy-a slurm hg38` | BLOCKED | contract_test | Gate 5 | orchestrator | Raw `snakemake --version` is prohibited; intended supported check is `dy-r --version`. | BUILD-001 and DYACT-001 did not complete. | No raw Snakemake command or premature wrapper check was run. |
| CONFIG-001 | majors-cluster / repository catalog | Copy the DYEC `12.0.2` command catalog into the user catalog and pin DayOA to the exact candidate commit | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | `~/.config/daylily/daylily_available_repositories.yaml` remains a symlink to `daylily_pipeline_command_catalog.yaml`; source copied from `~/dyec/config/daylily_pipeline_command_catalog.yaml`; parsed `repositories.daylily-omics-analysis.default_ref` is `1818223c3dfc9fc9e8227db40a8fc29224406b4d`; final SHA-256 `a435341a77d24cbc3d180e53f4b19a16caea01b82c17e6b4c7e84e66f9d419fc`. |  | DYEC `12.0.2` catalog shape installed with only the DayOA candidate ref changed from shipped `13.0.3` to the explicitly requested commit. |

## Final Report

All rows terminal: `yes`

Objective complete: `no`

Status counts:

- `SUCCESS`: 8
- `BLOCKED`: 3

Job `251` remained running at the last check. No raw `snakemake` command was invoked.
