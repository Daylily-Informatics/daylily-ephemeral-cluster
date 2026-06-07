# DayOA To DYEC 8.0.1 Release Train Ledger

Created: 2026-06-07T18:25:31Z

## Scope

Run the DayOA-through-DYEC release train without moving existing release tags.

Current source state forced a patch release decision:

- DayOA already has annotated tag `8.0.0` on `jem-dev` `HEAD` and is clean.
- DYEC already has annotated tag `8.0.0` on `jem-dev` `HEAD`, pushed to origin, but the working tree contains post-`8.0.0` release changes.
- Existing pushed release tags must not be moved or overwritten, so the post-`8.0.0` DYEC changes release as `8.0.1`.

No AWS-mutating command, cluster create/update/delete, raw DayOA `snakemake`, Slurm intervention, or live workflow launch is in scope.

## Gate 0 Inventory

| Item | Evidence |
|---|---|
| DayOA repo | `/Users/jmajor/projects/lsmc/daylily-omics-analysis`, branch `jem-dev`, status clean. |
| DayOA tag | `8.0.0` is annotated and resolves to commit `a6382d804f98e0a379c182c942e7b516b1d6e0fd`; local `HEAD` is the same commit. |
| DayOA remote | Origin is `git@github.com:lsmc-bio/daylily-omics-analysis.git`; remote tag `8.0.0` exists. |
| DYEC repo | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch `jem-dev`, dirty after `8.0.0`. |
| DYEC tag | `8.0.0` is annotated and resolves to commit `04314c53620033d60a4eeb2c8bb61b1b405f87cf`; local `HEAD` is that commit before release-train edits. |
| DYEC remote | Origin is `git@github.com:lsmc-bio/daylily-ephemeral-cluster.git`; remote tag `8.0.0` exists. |
| Version decision | Do not move `8.0.0`; release DYEC post-tag work as `8.0.1`. |

## Ledger Rows

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Inventory | Record DayOA/DYEC branches, tag state, dirty state, and release boundary. | SUCCESS | contract_test | Gate 0 | Agent 1 | See Gate 0 table. |  | DayOA `8.0.0` and DYEC `8.0.0` already exist as annotated tags; DYEC dirty state requires `8.0.1` for current work. |
| DAYOA-001 | DayOA | Verify DayOA release tag and do not alter DayOA when clean and already tagged. | SUCCESS | feature_implementation | Gate 1 | Agent 2 | `git status --short --branch` clean; `git rev-parse HEAD` equals `git rev-parse 8.0.0^{}`. |  | DayOA remains `8.0.0`; no commit or tag change needed. |
| DYEC-001 | DYEC self pins | Advance DYEC self-pin files from `8.0.0` to `8.0.1`. | SUCCESS | feature_implementation | Gate 1 | Agent 3 | `config/daylily_cli_global.yaml`; `daylily_ec/resources/payload/config/daylily_cli_global.yaml`; `tests/test_lsmc_bio_fork_contract.py`. |  | Source and packaged self-pins now target `8.0.1`; DayOA pins remain `8.0.0`. |
| DYEC-002 | DYEC source | Include post-`8.0.0` DYEC source/test/docs changes in the release commit. | IN_PROGRESS | feature_implementation | Gate 1 | Agent 4 | Pending staged diff review. |  |  |
| TEST-001 | Tests | Run focused release-train tests proving catalog pins, CLI registry, export helpers, runtime cap, and packaged resources. | OPEN | contract_test | Gate 4 | Agent 5 | Pending. |  |  |
| TAG-001 | Git | Commit DYEC release train and create annotated tag `8.0.1`. | OPEN | feature_implementation | Gate 5 | Agent 6 | Pending tests. |  |  |
| PUSH-001 | Git remote | Push DYEC `jem-dev` and tag `8.0.1`; verify remote tag exists. | OPEN | feature_implementation | Gate 5 | Agent 7 | Pending local commit/tag. |  |  |
| REPORT-001 | Report | Final report with DayOA and DYEC versions, commits, tags, tests, pushed state, and residual dirty/untracked evidence. | OPEN | contract_test | Gate 5 | Agent 8 | Pending. |  |  |
