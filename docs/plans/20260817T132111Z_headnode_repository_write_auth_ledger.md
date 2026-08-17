# Headnode Repository Write-Authentication Ledger

Created: `2026-08-17T13:21:11Z`

## Objective

Ensure the AWS Secrets Manager-backed deploy keys shared by configured DayEC
headnodes can clone/fetch and push the two LSMC-owned repositories, without
persisting private keys on headnode disks or changing the public third-party
catalog repositories.

## Evidence and change

| Repository | Previous GitHub deploy key | Replacement GitHub deploy key | Verification |
|---|---|---|---|
| `lsmc-bio/daylily-omics-analysis` | ID `156961830`, `read_only=true`, title `DayEC headnode read-only` | ID `160495063`, `read_only=false`, title `DayEC headnode read/write (AWS Secrets Manager)` | A headnode push dry-run succeeded, followed by the real feature-branch push. |
| `lsmc-bio/daylily-ephemeral-cluster` | ID `156964384`, `read_only=true`, title `DayEC headnode private clone (AWS Secrets Manager)` | ID `160495066`, `read_only=false`, title `DayEC headnode read/write (AWS Secrets Manager)` | A headnode push dry-run succeeded. No probe branch was created. |

GitHub deploy keys are immutable, so each existing key was deleted and
immediately recreated with the identical public key and `read_only=false`.
The operation included automatic rollback to the original read-only key if
recreation failed. Both replacements succeeded. AWS Secrets Manager private
key material and repository references were not changed.

The catalog's public third-party repositories, `rna-seq-star-deseq2` and
`daylily-sarek`, retain HTTPS `auth_mode: none`; no write permission was added
to repositories not owned by LSMC.

## DayOA publication proof

- Branch: `codex/truvari-per-sample-truth-gate`.
- Source/test commit: `2303bf8e` (`9` files, `453` insertions, `79` deletions).
- Documentation commit: `0d7a8a3d` (`AGENTS.md`, `README.md`).
- Remote branch tip verified:
  `0d7a8a3dc19e4c1913ffca735ef9994f5c32142e`.
- Focused headnode tests: `59 passed in 0.56s`.
- `git diff --check` passed.
- The analysis-root write lock was released after the commit and push.
