# DayOA 2.0.16 To DYEC Release Train Ledger

Created: 2026-05-28T08:51:20Z

## Objective

Publish the existing DayOA 2.0.16 release commit to `main`, update DYEC's pinned DayOA repository catalog version to `2.0.16`, and publish a new DYEC release tag.

## Gate 0 Inventory

### DayOA

- Repo: `/Users/jmajor/projects/daylily/daylily-omics-analysis`
- Branch: `codex/dayoa-local-evidence-dewey-refactor-20260528`
- Worktree: clean at inventory
- Local HEAD: `35eaa37034eb3a048b7cf531ae8b3c488685f18e`
- Tags on HEAD: `2.0.15`, `2.0.16`
- Remote `origin/main` before publication: `d5b5faefc33efbb0edb6ec58ce56cbcd5ae4a19e`
- Remote `2.0.16` tag: annotated tag `0c6942745bb91a94f1441342320050a53dcd0aaa`, dereferences to `35eaa37034eb3a048b7cf531ae8b3c488685f18e`
- Publication action: fast-forward `origin/main` to `35eaa37034eb3a048b7cf531ae8b3c488685f18e`; no new DayOA tag needed.

### DYEC

- Repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
- Branch: `codex/dyec-dewey-registration-refactor-20260528`
- Worktree: clean at inventory before ledger creation
- Local HEAD: `0dedbfe72aec3760033f2f04baa7aad9ba6011b3`
- Tag on HEAD: `5.0.17`
- Current DayOA catalog/test pin: `2.0.14`
- Target DayOA pin: `2.0.16`
- Proposed next DYEC tag: `5.0.18`
- Remote `5.0.18` tag before publication: absent

## Execution Ledger

| Row | Step | Status | Evidence |
| --- | --- | --- | --- |
| REL-001 | Record Gate 0 inventory and target versions. | COMPLETE | Ledger created with repo paths, branches, current tags, and target pins. |
| REL-002 | Publish DayOA `2.0.16` commit to `origin/main`. | COMPLETE | `git push origin HEAD:main` updated `origin/main` from `d5b5fae` to `35eaa37`; `git ls-remote --heads origin main` returned `35eaa37034eb3a048b7cf531ae8b3c488685f18e`; remote tag `2.0.16^{}` also resolves to `35eaa37034eb3a048b7cf531ae8b3c488685f18e`. |
| REL-003 | Update DYEC DayOA catalog/test pin from `2.0.14` to `2.0.16`. | COMPLETE | Updated both catalog copies and focused tests; `rg -n "2\.0\.14\|2\.0\.16" ...` found only `2.0.16` matches in the targeted files; `cmp -s config/daylily_available_repositories.yaml daylily_ec/resources/payload/config/daylily_available_repositories.yaml` passed. |
| REL-004 | Run focused DYEC tests for repository catalog and registry behavior. | COMPLETE | `source ./activate && python -m pytest -q tests/test_repository_catalog.py tests/test_cli_registry_v2.py` passed: 102 tests passed in 2.77s. |
| REL-005 | Commit DYEC dirty/new/edited work, push to `main`, tag `5.0.18`, and push the tag. | READY | Pending final `git diff --check`, staging, commit, push, tag, and remote verification. |
