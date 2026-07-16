# Archive Untracked Plan Artifacts and DYEC 10.3.24 Release Ledger

Opened: 2026-07-16T11:08:15Z

## Objective

Preserve every file that was untracked beneath `docs/plans/` in the canonical
DYEC checkout by committing it beneath `docs/plans/old_files/`, then publish a
new annotated DYEC release from the current feature-branch lineage without
committing or modifying the unrelated dirty source and template files in that
canonical checkout.

## Gate 0

| Item | Evidence |
|---|---|
| Canonical checkout | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch `codex/dyec-self-pin-10317`, commit `eaa36f07`, dirty with 51 tracked and 73 untracked paths. |
| Requested archive scope | `git ls-files --others --exclude-standard docs/plans` returned exactly 13 files. |
| Safe release base | Annotated tag `10.3.23` peels to `cc760660`; the canonical branch commit is an ancestor of that release commit. |
| Release worktree | `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-archive-ledgers-10324-20260716`, detached from `cc760660`. |
| Next tag | `10.3.24`; absent locally and from `origin` at Gate 0. |
| Scope exclusion | No dirty source, tests, template files, or untracked Intel templates from the canonical checkout are copied into this release. |

## Control Ledger

| ID | Requirement | Status | Category | Evidence | Terminal note |
|---|---|---|---|---|---|
| ARC-001 | Archive all 13 untracked `docs/plans` files under `docs/plans/old_files/`. | SUCCESS | historical_docs_only | Exactly 13 source artifacts plus one `.gitattributes` metadata file; source/destination SHA-256 values matched for every artifact; archive size 1.4 MiB. | The complete requested untracked plan-artifact set is preserved. |
| ARC-002 | Preserve the existing tracked Intel template-split ledger by moving it rather than duplicating it. | SUCCESS | historical_docs_only | Git records `20260716T025545Z_intel_spot_ondemand_template_split_ledger.md` as a rename into `old_files`. | No duplicate remains at the root of `docs/plans`. |
| REL-001 | Advance source, packaged, and tested DYEC self-pins to `10.3.24`. | SUCCESS | config_or_startup_contract | Both global YAML copies and `DYEC_BLESSED_TAG` now name `10.3.24`; YAML parity assertion passed. | Release self-pins consistently. |
| REL-002 | Validate archive payloads, pin parity, and focused release tests. | SUCCESS | contract_test | `45 passed`; Python/JSON/CSV/XML/shell/Node syntax checks; secret-pattern scan clean; archived CRLF CSV preserved byte-for-byte and marked `-diff -text` for a clean `git diff --check`. | Archive payload and release-pin gates passed. |
| REL-003 | Commit, push the current feature branch, create an annotated `10.3.24` tag, and verify remote refs. | SUCCESS | feature_implementation | Release commit `cac55384`; remote branch matched it; annotated tag object `56dd4386` peeled to `cac55384` locally and on `origin`. | Branch and immutable release tag are published. |

## Guardrails

- Preserve the canonical dirty checkout exactly; do not stash, reset, clean, or
  stage its unrelated paths.
- Do not open or merge a PR to `main`; the user explicitly requested the
  current feature branch.
- Do not move an existing tag or force-push a branch.
- Tag only a clean, tested commit and verify the remote tag object and peeled
  commit after publication.

## Completion

All rows terminal: yes

Objective complete: yes
