# `DayECHeadnodeGitHubClone` — split plan

**Status: not done. This is the fix for an account-wide outage that is still
live.** Daylily worked around it locally; nobody else has.

## What is broken

Every `dyec create` in account `108782052779` aborts at preflight:

```
✗ iam.dyec_deploy_key_secret_policy
✗ iam.dayoa_deploy_key_secret_policy
Preflight FAIL detected — aborting.
```

The remediation text says to create the secret and policy. Both exist and grant
the right actions. That message is misleading — the real cause is the *shape* of
the policy document.

## Cause

`daylily_ec/aws/github_deploy_key.py:120-152` asserts four things about the
policy named by `*_deploy_key_policy_arn`:

| # | Assertion | Line |
|---|---|---|
| 1 | exactly **one** statement | `:131` |
| 2 | `Effect` is `Allow` | `:135` |
| 3 | action set equals `{DescribeSecret, GetSecretValue}` **exactly** | `:140` |
| 4 | resource list equals **exactly one** computed pattern | `:149` |

Pattern 4 is built by `lsmc_bio_policy_resource()` from the configured secret
ARN, so it carries that ARN's **region** — `us-west-2`. A `*` region is a string
mismatch and fails.

`DayECHeadnodeGitHubClone` now violates 1 and 4:

| Version | Created | Statements | Region | Verdict |
|---|---|---|---|---|
| v1 | 2026-07-13 | 1 | `us-west-2` | **passes** — a 2026-08-16 create ran on this |
| v2 | 2026-08-17 | 2 | `us-west-2` | fails 1 |
| **v3** | **2026-08-19** | 2 | `*` | fails 1 **and** 4 — current default |

The added statement grants the `dayec/github-token/lsmc-bio-dayoa-dyec-*` secret.
It is a legitimate need placed in a policy that cannot hold it.

**Both changes were made using the account root access key** (`AKIA…`, no MFA,
`aws-cli/2.34.29` on macOS from `98.109.218.150`) — not through Terraform and not
through review. That is a separate conversation from the outage, and worth having.

## Blast radius

`DayECHeadnodeGitHubClone` is attached to four principals:

```
dclu-1904-RoleHeadNode-zyrlUcV1z8e8                     live cluster headnode
pclu-18045-RoleHeadNode-QWFIIUSw21tL                    live cluster headnode
ursa-m-rgx-hx01-RoleHeadNode-VpIYdevyy6HD               Ursa cluster headnode
Dayhoff-day-Compute-InstanceRole3CCE2F1D-Nt0s1SL3rfbr   the Dayhoff host
```

Three belong to other teams. The last is not a cluster headnode at all, despite
the policy's "headnode-only" description.

## The fix — attach before you subtract

Ordered so token access is never lost, even momentarily.

1. **Create `DayECHeadnodeGitHubToken`** with the token statement alone:
   ```json
   {"Version":"2012-10-17","Statement":[{
     "Sid":"ReadDayoaDyecGitHubToken","Effect":"Allow",
     "Action":["secretsmanager:DescribeSecret","secretsmanager:GetSecretValue"],
     "Resource":"arn:aws:secretsmanager:us-west-2:108782052779:secret:dayec/github-token/lsmc-bio-dayoa-dyec-*"}]}
   ```
2. **Attach it to all four principals above.**
3. **Verify** `secretsmanager:GetSecretValue` on the token ARN still resolves for
   each — simulate against the real ARN, not a guessed one.
4. **Then** create v4 of `DayECHeadnodeGitHubClone` containing only the
   deploy-key statement **with region `us-west-2`, not `*`** — v1's document
   exactly — and set it default.
5. **Confirm** a `dyec create` preflight passes both deploy-key checks.

**Rollback:** v3 is retained; `set-default-policy-version --version-id v3`
restores today's state. Version count is 3 of a maximum 5, so v4 fits.

> Step 4 must restore the region as well as drop the statement. Removing only the
> second statement leaves v3's `*` region, which still fails assertion 4.

## Longer-term: the assertion is brittle

Requiring a *shared* policy to contain exactly one statement means any team adding
a legitimate grant silently breaks cluster creation account-wide, with a
misleading error. Relaxing `_validate_policy_document` to require the expected
statement be **present** rather than **sole** would remove that trap. It is a DYEC
change and does not help until released, so it is not on the critical path here.

## What Daylily did instead, and why it is not the fix

`config/baseline-cluster-request.yaml` now points at
`arn:aws:iam::108782052779:policy/daylily/DayecHeadnodeDeployKeyRead` — a
Daylily-owned, single-statement, `us-west-2` policy validated against DYEC's own
checker for both secrets.

That unblocks one config without touching four live principals belonging to other
teams. **It leaves the account-wide outage in place.** It is a workaround pending
the split above, not a substitute for it.
