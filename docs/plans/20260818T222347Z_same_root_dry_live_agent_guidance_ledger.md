# Dry-to-live same-analysis-root agent-guidance ledger

Created: 2026-08-18T22:23:47Z

## Scope

Make the DayOA/DYEC dry-to-live contract unmistakable in the active DYEC,
DayOA, Ursa, and shared agent guidance. A successful dry controller validates
the real command in one analysis capsule. The later live invocation must reuse
the same analysis ID, FSx root, DayOA checkout/commit, staged inputs, and
runtime configuration, with only `-n` removed. A distinct `-dry` or `-live`
controller/tmux session name is allowed; it is not a new analysis directory.

## Gate 0

| ID | Area | Status | Evidence |
|---|---|---|---|
| G0 | Inventory and authority | SUCCESS | User explicitly requested guidance plus memory updates. Reviewed the active DYEC checkout, DayOA checkout, Ursa checkout at `/Users/jmajor/projects/mega_dayhoff/repos_work/daylily-ursa`, shared DayOA runbooks, `dyec agent guidance`, and the existing same-root memory note. Existing unrelated dirty/untracked work in all three repositories is preserved. |

## Control ledger

| ID | Area | Requirement | Status | Category | Gate | Evidence / terminal note |
|---|---|---|---|---|---|---|
| DYEC-001 | DYEC guidance | State that dry-to-live is same-root continuation in `AGENTS.md`, the operator guide, CLI guidance output, and CLI reference. | SUCCESS | active_product_contract | Gate 1 | Updated `AGENTS.md`, `docs/agent_cli_guide.md`, `docs/cli_reference.md`, and `daylily_ec/cli.py`. The rendered `dyec agent guidance` output explicitly limits `-dry`/`-live` to controller labels and requires one analysis capsule. |
| DAYOA-001 | DayOA guidance | Remove ambiguity between a fresh initial clone and a fresh post-dry live root; state the same-root rule. | SUCCESS | active_product_contract | Gate 1 | Updated `/Users/jmajor/projects/lsmc/daylily-omics-analysis/AGENTS.md` with a standalone Dry-to-Live Continuity section and corrected the initial-clone wording. |
| URSA-001 | Ursa guidance | Require Ursa-orchestrated DayOA validation to continue its dry analysis capsule rather than allocate a live replacement. | SUCCESS | active_product_contract | Gate 1 | Updated `/Users/jmajor/projects/mega_dayhoff/repos_work/daylily-ursa/AGENTS.md` with the same contract for Ursa-requested workflows. |
| GLOBAL-001 | Shared agent guidance | Strengthen both shared runbooks and shell guidance with the same analysis-capsule contract. | SUCCESS | active_product_contract | Gate 1 | Updated `/Users/jmajor/.codex/AGENTS.md`, `/Users/jmajor/.agents/AGENTS.md`, and both `AGENTS-HOW-TO-RUN-DAYOA.md` runbooks. |
| MEM-001 | Durable memory | Add the user-requested memory extension note; do not mutate memory registry/source files. | SUCCESS | historical_docs_only | Gate 1 | Added append-only `/Users/jmajor/.codex/memories/extensions/ad_hoc/notes/20260818T222347Z_dry_live_same_analysis_capsule.md`; no memory registry/source file was changed. |
| VERIFY-001 | Static verification | Check guidance wording, `dyec agent guidance` output, and whitespace; no workflow, cloud, or test execution is in scope. | SUCCESS | contract_test | Gate 5 | Scoped `git diff --check` passed for DYEC, DayOA, and Ursa guidance files. `rg` found the required same-capsule wording in every updated surface. `source ./activate && dyec agent guidance` rendered the new contract. No test suite or workflow was run because this is guidance-only work. |
