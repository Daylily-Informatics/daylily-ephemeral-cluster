# Portable GitHub credential-policy preflight ledger

Created: 2026-08-19T08:08:25Z

## Objective

Repair the DYEC deploy-key preflight so a narrowly scoped shared policy that
also grants the existing managed GitHub-token read can be used immediately,
and make that policy portable across explicitly configured AWS Region-AZ
creates without accepting unrelated permissions.

## Scope and approval

- User authorization: "relax this so it is fixed right now and durably for
  future cluster creates in arbitrary REGION-AZs... ideally with no code
  changes if possible".
- Branch: `codex/portable-github-policy-18057`, based on annotated tag
  `18.0.56` (`b3129397d1ba74906e30044ef4293b7113e27205`).
- The fixed policy remains account-scoped and permits only
  `secretsmanager:DescribeSecret` and `secretsmanager:GetSecretValue` for the
  explicit LSMC Bio deploy-key namespace and the one managed two-repository
  GitHub-token name. The region position may be wildcarded so the same IAM
  policy works with explicitly supplied regional secret ARNs.
- A create still requires an exact regional secret ARN matching the requested
  cluster region. This work neither creates/replicates secrets nor adds
  discovery, inferred defaults, or a fallback path.
- Out of scope: retrying `dyec create`, creating a cluster, changing budgets,
  creating/replicating secrets, and detaching the current policy from an
  active compute role. The latter is a separately authorized active-role
  change.

## Gate 0 baseline

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`.
- Initial checkout: detached annotated tag `18.0.54` (`8ea1f1bf`); working
  branch created from the current annotated tag `18.0.56`.
- Pre-existing, unowned paths preserved: `TrusSV/` and
  `tmp/dayoa-ont-headnode-proof/`.
- Source condition: `daylily_ec/aws/github_deploy_key.py` requires exactly one
  managed-policy statement. Its focused suite passed (`6 passed`), but a
  read-only invocation against the live policy returned
  `Managed policy must contain exactly one statement.`
- Live IAM inventory (read-only, secret values never read):
  `DayECHeadnodeGitHubClone` default version `v2` contains one deploy-key
  namespace statement and one managed-token statement; both use only the two
  allowed Secrets Manager actions. Version `v1` contains only the deploy-key
  statement. `v2` is attached to one headnode and one compute role.
- Region inventory: cluster templates exist for multiple Region-AZs, while
  the default config currently names `us-west-2` secrets. The existing
  explicit region-match contract remains in force.

## Control Ledger

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Repository and AWS baseline | Record current source, policy, secret metadata, supported Region-AZ inventory, and unowned worktree state before a change. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | Gate 0 above; focused baseline `tests/test_github_deploy_key.py` -> `6 passed`. |  | Inventory is complete; no secret value, policy attachment, or cluster state was changed. |
| DES-001 | Policy-only route | Establish whether a no-code IAM document can preserve managed-token access and satisfy the existing validator. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Existing validator requires exactly one statement and exactly one deploy-key resource; a token statement necessarily fails it. | The current CLI cannot attach an independent token policy through a validated create input. | A bounded validator change is required; policy-only rollback would remove token access. |
| CODE-001 | DYEC preflight | Accept exactly the deploy-key statement plus the designated managed-token statement, with no broader actions/resources or silent fallback. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | `github_deploy_key.py` now accepts legacy deploy-only or bounded deploy-plus-designated-token policy documents; it permits only the region field to be wildcarded and rejects malformed configured ARNs. | The legacy exact-one-statement check rejected an otherwise least-privilege managed token read. | No token discovery, name expansion, account wildcard, or unsupported fallback was added. |
| TEST-001 | DYEC tests | Cover legacy one-statement policy, bounded two-statement policy, portable regional resource form, and reject extra statements/actions/resources. | SUCCESS | contract_test | Gate 5 | orchestrator | `python -m pytest -q tests/test_github_deploy_key.py tests/test_cli_docs_contract.py` -> `18 passed`; create-path selection `tests/test_workflow.py -k 'deploy_key or create_output_never_prints_deploy_key_secret_arns'` -> `5 passed, 156 deselected`; Ruff, `py_compile`, and `git diff --check` passed. |  | The suite covers exact and portable region forms, alternate explicit region input, unknown token, extra statement/action, account wildcard, and malformed configured ARN rejection. |
| DOC-001 | Operator contract | Align policy documentation with the bounded two-statement portable policy and explicit regional-secret requirement. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | `docs/aws_setup.md` documents the bounded policy; current operator docs and their contract test now align to DYEC `18.0.57` / current DayOA `15.0.37`. |  | Historical ledgers were intentionally not rewritten. |
| IAM-001 | Live IAM policy | Publish a new default version of `DayECHeadnodeGitHubClone` with the bounded portable resource patterns, preserving allowed actions only. | SUCCESS | active_product_contract | Gate 3 | orchestrator | New default policy version `v3` created `2026-08-19T08:14:09Z`: exactly two statements, each with only `DescribeSecret`/`GetSecretValue`, fixed account `108782052779`, fixed LSMC secret names, and `*` only in the region field. | Existing `v2` had the needed token statement but was rejected by the one-statement source contract. | Policy attachments were not changed: its active compute-role attachment remains out of scope and needs separate approval. |
| LIVE-001 | Live preflight | Re-run only the deploy-key validator against the new policy and confirm the secret value remains unread. | SUCCESS | contract_test | Gate 5 | orchestrator | Read-only live validation of both DYEC and DayOA deploy-key secret metadata against default `v3` returned `PASS`; both reports had `secret_value_read=False`, and no `GetSecretValue` request was made. |  | No cluster create was retried. |
| REL-001 | DYEC release | Commit, annotate, and push a non-v patch release so future creates use the fixed validator. | IN_PROGRESS | feature_implementation | Gate 5 | orchestrator | Source, docs, tests, and live-policy verification complete; preparing clean `18.0.57` patch release from the immutable `18.0.56` base. | Existing `18.0.56` is already an immutable annotated release and cannot safely receive this fix. | Pending commit, annotated tag, push, and release-source build verification. |

## Initial decision

The user requested arbitrary Region-AZ support, not a broad credential policy.
The implementation will therefore keep the AWS account and secret-name scopes
fixed, allow only the two read actions, and make only the region component
portable. No account wildcard, `ListSecrets`, arbitrary token name, secret
copy, or automatic per-region selection is permitted.

## Final Report

All rows terminal: no

Objective complete: no
