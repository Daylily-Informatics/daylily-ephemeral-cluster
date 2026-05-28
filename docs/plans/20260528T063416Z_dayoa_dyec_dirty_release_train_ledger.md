# DayOA And DYEC Dirty Release Train Ledger

Created: 2026-05-28T06:34:16Z

## Objective

Commit current repo-owned dirty work in DayOA and DYEC, publish feature branches, create new bare semver tags, push those tags, and carry the release train through the DYEC command catalog so DYEC uses the new DayOA tag.

## Gate 0 Inventory

Controlling ledger: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster/docs/plans/20260528T063416Z_dayoa_dyec_dirty_release_train_ledger.md`

Repositories:

- DayOA: `/Users/jmajor/projects/daylily/daylily-omics-analysis`
  - Branch: `codex/dayoa-local-evidence-dewey-refactor-20260528`
  - Baseline dirty state: modified `AGENTS.md`
  - Current tag at baseline: `2.0.13`
  - Planned next tag: `2.0.14`
- DYEC: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
  - Branch: `codex/dyec-dewey-registration-refactor-20260528`
  - Baseline dirty state: modified `AGENTS.md`, modified `docs/plans/20260528T003512Z_inflection_controller_rulegraphs/*`, untracked plan artifacts under `docs/plans/`, untracked `presign_url_sofar.md`, untracked `.tailscale_key`, and untracked 559 MB VCF.
  - Current tag at baseline: `5.0.14`
  - Planned next tag: `5.0.15`

Safety exclusions:

- `.tailscale_key` is a secret-shaped auth key file and is not a repo artifact.
- `20260514-LH01106-0009-B23TVLGLT4-HIOMRFULL-HG003-a-20260514-Altair3-ONT-full-HIOMR-0-HG003-a-PF-ILMN-NOVASEQ.ont.dmd.sentdhiomr.snv.sort.vcf.gz` is 559 MB and is not suitable for normal Git/GitHub push.

Remote tag preflight:

- `origin` had no `2.0.14`, `5.0.15`, or `5.0.16` tag at Gate 0.

## Tracking Rows

| ID | Area/Repo | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| REL-001 | Ledger | Record Gate 0 inventory and release assumptions before committing. | SUCCESS | plan_amendment | Gate 0 | orchestrator | This ledger. |  | Gate 0 complete before release commits. |
| REL-002 | DayOA | Commit `AGENTS.md`, tag `2.0.14`, push branch and tag. | SUCCESS | feature_implementation | Gate 5 | orchestrator | `git diff --check` passed; commit `49dbbce` (`Document DayOA shell session defaults`); `git push origin codex/dayoa-local-evidence-dewey-refactor-20260528` succeeded; `git push origin 2.0.14` succeeded. |  | DayOA dirty work is committed, pushed, tagged, and the tag is pushed. |
| REL-003 | DYEC catalog | Pin DYEC source and packaged command catalogs to DayOA `2.0.14`. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | `config/daylily_available_repositories.yaml` and `daylily_ec/resources/payload/config/daylily_available_repositories.yaml` now use `default_ref: 2.0.14` and `git_tag: 2.0.14`; `cmp -s` passed; `git ls-remote` confirmed origin tag `2.0.14^{}` -> `49dbbce995d23219ad4bea35814b308a5cee1cd8`. |  | Catalog train points at the new DayOA release tag. |
| REL-004 | DYEC dirty artifacts | Commit repo-owned dirty docs, plans, and catalog changes while excluding secret/oversized non-artifacts. | SUCCESS | feature_implementation | Gate 5 | orchestrator | Added targeted `.gitignore` rules for `.tailscale_key`, `presign_url_sofar.md`, `*_signed_urls.tsv`, and root `/*.vcf.gz`; repo-owned plan artifacts are included; `source ./activate && python -m pytest -q tests/test_repository_catalog.py tests/test_cli_registry_v2.py` -> `102 passed`. |  | Durable repo artifacts are ready for the DYEC release commit; sensitive/oversized local files remain untracked and ignored. |
| REL-005 | DYEC release | Tag DYEC `5.0.15`, push branch and tag, and verify remotes. | SUCCESS | feature_implementation | Gate 5 | orchestrator | Commit `b625830` (`Release DYEC 5.0.15 with DayOA 2.0.14`); `git push origin codex/dyec-dewey-registration-refactor-20260528` succeeded; `git push origin 5.0.15` succeeded; remote branch `refs/heads/codex/dyec-dewey-registration-refactor-20260528` -> `b625830decc95a0efd25f5df08b361f61ea3b2cb`; remote `5.0.15^{}` -> `b625830decc95a0efd25f5df08b361f61ea3b2cb`. |  | DYEC branch and tag `5.0.15` are published. |

## Final Terminal-State Report

Updated: 2026-05-28T06:45Z

Terminal rows: 5 of 5.

- `SUCCESS`: REL-001, REL-002, REL-003, REL-004, REL-005
- `OPEN`, `IN_PROGRESS`, `ATTEMPTING_BUGFIX`: none

Final branch/tag state:

- DayOA commit `49dbbce995d23219ad4bea35814b308a5cee1cd8`; remote branch matches; remote tag `2.0.14^{}` matches.
- DYEC commit `b625830decc95a0efd25f5df08b361f61ea3b2cb`; remote branch matches; remote tag `5.0.15^{}` matches.

The second DYEC tag after this ledger-only terminal update is expected to be `5.0.16`.
