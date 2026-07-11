# Private DayOA Deploy-Key Authentication Ledger

Objective: make private `lsmc-bio/daylily-omics-analysis` checkouts work through
`day-clone` on new DYEC headnodes using one read-only repository deploy key,
without granting GitHub credentials to compute nodes.

## Gate 0 Baseline

- DYEC checkout: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch/HEAD: `jem-dev` at `0fb6d4b1` (`10.0.155`), matching `origin/jem-dev`
- Worktree: clean (`git status --short --branch` reported only the branch line)
- DayOA visibility: `lsmc-bio/daylily-omics-analysis` is temporarily `PUBLIC`
- AWS account/profile: profile `lsmc`, account `108782052779`; caller is account root
- Existing direct dependency: DYEC `pyproject.toml` pins DayOA through `git+https`
- Existing clone surface: `day-clone` defaults to catalog HTTPS and supports explicit SSH
- Safety boundary: only the headnode may receive deploy-key secret access; no compute
  queue may receive the policy.

## Control Ledger

| ID | Work item | State | Evidence / terminal note |
|---|---|---|---|
| DK-001 | Add explicit deploy-key configuration and validation. | SUCCESS | Required exact secret and policy ARNs are parsed and preflighted in the target account and region. |
| DK-002 | Attach the exact secret-read policy only to the rendered headnode IAM block. | SUCCESS | Rendered-YAML helper rejects the policy in every queue and inserts it once under `HeadNode.Iam.AdditionalIamPolicies`. |
| DK-003 | Configure the non-secret deploy-key ARN/region on the headnode through SSM. | SUCCESS | Headnode configuration writes only `secret_arn` and `region` to the Daylily config. |
| DK-004 | Make DayOA catalog cloning explicitly SSH plus AWS deploy-key authenticated. | SUCCESS | Source and packaged catalogs declare `clone_transport: ssh` and `auth_mode: aws_deploy_key`; other rows remain explicit HTTPS/none. |
| DK-005 | Fetch, validate, use, and always remove the temporary deploy key in `day-clone`; add `--check-auth`. | SUCCESS | Implementation uses strict packaged host keys, mode `0700`/`0600` temporary storage, `IdentitiesOnly=yes`, and context-managed cleanup. |
| DK-006 | Remove DYEC's direct `git+https` DayOA dependency. | SUCCESS | DayOA is absent from `pyproject.toml` dependencies and is acquired through explicit version-pinned `day-clone`. |
| DK-007 | Add focused contract tests and run full local validation. | SUCCESS | `pytest -q`: 1376 passed, 11 skipped; targeted Ruff, Python/Bash syntax, YAML, payload parity, and `git diff --check` passed. Repository-wide Ruff remains nonzero only for 33 pre-existing errors in unrelated archived `docs/` scripts. |
| DK-008 | Create the repository deploy key, AWS secret, and exact IAM policy. | IN_PROGRESS | AWS secret and policy exist and pass DYEC preflight. GitHub rejected key creation because deploy keys are disabled at the `lsmc-bio` organization level. |
| DK-009 | Return DayOA to private and verify authenticated access. | OPEN | Do not create a separate paid cluster solely for this validation. |

## Bugfix Attempts

- `2026-07-11T02:15Z` — Focused baseline after the first implementation pass:
  `pytest -q tests/test_day_clone.py tests/test_repository_catalog.py
  tests/test_lsmc_bio_fork_contract.py tests/test_headnode_readiness.py
  tests/test_workflow.py` -> `112 passed, 31 failed`. Root cause: existing test and
  version-1 catalog fixtures did not yet declare the new explicit
  `clone_transport`/`auth_mode` fields, and workflow fixtures did not include the
  exact deploy-key secret/policy ARNs. Next attempt: update those fixtures and keep
  production parsing strict rather than adding inferred defaults.
- `2026-07-11T02:34Z` — First complete suite after the focused suite passed:
  `pytest -q` -> `1371 passed, 11 skipped, 5 failed`. All five failures were stale
  contract expectations: two CLI mocks lacked the new explicit empty deploy-key
  kwargs, two remote-test assertions still expected raw HTTPS cloning, and the
  legacy login-SSH sweep needed a path-specific exception for strict Git SSH host
  verification in `day-clone`. Next attempt: update only those exact expectations
  and preserve all other SSH/PEM prohibitions.

## Live Provisioning Evidence

- Secret ARN: `arn:aws:secretsmanager:us-west-2:108782052779:secret:dayec/github-deploy-keys/lsmc-bio-daylily-omics-analysis-igtfHD`
- Policy ARN: `arn:aws:iam::108782052779:policy/DayECHeadnodeDayOAClone`
- DYEC preflight: `iam.dayoa_deploy_key_secret_policy PASS`; the validator did not
  call `GetSecretValue`.
- GitHub deploy-key attempt: HTTP 422, `Deploy keys are disabled for this repository`.
  The authenticated GitHub identity is an active `lsmc-bio` organization owner. GitHub
  documents the required switch under organization Settings, Member privileges,
  Deploy keys.
- DayOA remains `PUBLIC`; no visibility change has occurred.
- The protected local setup key remains mode `0600` only until GitHub key registration
  and both public/private authentication checks complete.

## Live-Action Boundaries

- No cluster creation or teardown is authorized by this ledger.
- No secret material may be written into this ledger, repository files, command logs,
  cluster YAML, S3 bootstrap payloads, or DYEC state records.
- The private key may exist only in the local protected setup file, AWS Secrets Manager,
  and a mode-`0600` temporary headnode file for the lifetime of one Git operation.
- DayOA visibility changes happen only after the deploy key and AWS controls validate.
