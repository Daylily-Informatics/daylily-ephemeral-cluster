# DYEC Create Defaults 16.1.18 Release Ledger

Controlling request: make the interactive `dyec create` defaults operator-visible,
then commit, push, create a new DYEC version tag, push the tag, and report the
published version.

Ledger path:
`docs/plans/20260731T085155Z_dyec_create_defaults_16.1.18_release_ledger.md`

## Gate 0 baseline

- Repository: `/Users/jmajor/.codex/worktrees/7731/daylily-ephemeral-cluster`
- Release branch: `codex/dyec-create-defaults-16.1.18`
- Release base: annotated tag `16.1.17`, commit
  `6b14f78dacdaa3733682b9dbc557170ac037c3b1`
- Remote default branch: `origin/main` at
  `4edb0b97df96297c021fdb881c61a27e40644a8d`; current DYEC releases are
  branch-tagged beyond that point.
- Highest existing numeric tag after `git fetch origin --prune --tags`:
  `16.1.17`; inferred next patch release: `16.1.18`.
- Source-derived pre-commit version:
  `16.1.18.dev0+g6b14f78da.d20260731`.
- Pinned DayOA version on the release base: `13.0.107`.
- Initial owned changes: source and packaged create templates, config key
  registry, create workflow defaults, and workflow tests.
- Baseline validation:
  `python -m pytest -q tests/test_workflow.py tests/test_triplets.py
  tests/test_packaged_defaults.py::test_packaged_cluster_templates_match_source_templates
  tests/test_cluster_request_config.py` -> `213 passed`.
- `git diff --check` -> clean.
- Live-system boundary: no cluster creation, budget mutation, cost-center
  mutation, or other AWS action is part of this release proof.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| CFG-001 | `dyec create` | Default the prompted budget email to `contact@lsmc.com` while preserving explicit config and `DAY_CONTACT_EMAIL` overrides. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Source and packaged templates plus `_default_budget_email`; focused tests included in the 213-test gate. |  | Interactive and non-interactive resolution are explicit and tested. |
| CFG-002 | `dyec create` | Prompt with `<cluster-name>-ccenter` and monthly cap `200`; do not silently hide the interactive prompts. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | `_resolve_post_create_inputs` supplies prompt defaults; tests assert both `typer.prompt` calls and accepted values. |  | Operators can accept or override both defaults. |
| CFG-003 | `dyec create` | Prompt cluster name with the runtime `${USER}-clu` default while preserving explicit config values. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | `_default_cluster_name`; tests prove `USER=jmajor` renders `jmajor-clu` and remains an interactive prompt. |  | Dynamic default is validated through the existing cluster-name contract. |
| CFG-004 | Packaging | Keep source and installed-payload create templates synchronized and retain required cost-center keys. | SUCCESS | contract_test | Gate 5 | orchestrator | `cmp -s` returned `0`; template and triplet tests passed. |  | Source and packaged defaults are byte-identical. |
| REL-001 | Git | Commit the reviewed release scope on the release branch. | SUCCESS | config_or_startup_contract | Gate 5 | orchestrator | Commit `d0f0a06ef36117abb243650dc393e0568a8f7255`, `feat(create): add operator-visible defaults`. |  | The tested implementation and initial ledger were committed together. |
| REL-002 | GitHub | Push the release branch without force. | SUCCESS | config_or_startup_contract | Gate 5 | orchestrator | Remote branch `codex/dyec-create-defaults-16.1.18` resolved to `d0f0a06ef36117abb243650dc393e0568a8f7255`. |  | Branch push succeeded without force. |
| REL-003 | Release | Create annotated, unprefixed tag `16.1.18` on the clean release commit and push it without moving any existing tag. | SUCCESS | config_or_startup_contract | Gate 5 | orchestrator | Local and remote tag object `1072479dcd33d48ed559893eab6a867307da694f` peels to release commit `d0f0a06ef36117abb243650dc393e0568a8f7255`; `git cat-file -t 16.1.18` -> `tag`. |  | New immutable annotated tag `16.1.18` was pushed. |
| REL-004 | Verification | Verify remote branch/tag SHAs, annotated tag type, clean release tree, and source-derived final version. | SUCCESS | contract_test | Gate 5 | orchestrator | `git ls-remote` matched the branch and peeled tag commit; `git describe --tags --exact-match HEAD` -> `16.1.18`; `dyec --version` -> `Daylily Ephemeral Cluster 16.1.18`; `dyec info` reported pinned DayOA `13.0.107`. |  | Remote and local release identities agree exactly. |

## Final report

All rows terminal: yes

Objective complete: yes

Status counts:

- SUCCESS: 8
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0

DYEC `16.1.18` is published as an annotated, unprefixed tag on commit
`d0f0a06ef36117abb243650dc393e0568a8f7255`. The release reports pinned
DayOA `13.0.107`. No live AWS mutation was performed.
