# Bjuiceval 19024 budget-cap increase ledger

Created: `2026-08-24T05:32:12Z`

## Objective

Increase exactly two monthly USD controls from their verified current values
to `$1,200`: the AWS Budget named `bjuiceval-19024` and the active cost center
named `bjuiceval-19024-ccenter`. No other budget, cost center, cluster,
workflow, Slurm, DRA, export, or cleanup state is in scope.

## Gate 0 and approval evidence

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch: `codex/bjuiceval-19024-dra-mounts`
- Starting commit: `6b6765c53039c3cd731b2c9150ef4eda1e2190a1`
- CLI: activated public `dyec` release `19.0.24`.
- AWS context: profile `lsmc`, region/home region `us-west-2`.
- First approval: the user requested both named controls be increased to
  `$1,200`.
- Second approval: after being told the request was the first approval and
  that exact old-cap readback would precede mutation, the user repeated the
  same exact request for both named controls at `$1,200`.
- Cluster budget readback: public `dyec aws budget set-limit --dry-run` with
  exact-old-cap proof returned `previous_monthly_cap_usd=999.0`,
  `observed_monthly_cap_usd=999.0`, `requested_monthly_cap_usd=1200`,
  `changed=true`, `update_submitted=false`.
- Cost-center readback: public `dyec cost-centers show` returned
  `monthly_cap_usd=999` and `status=active` for
  `bjuiceval-19024-ccenter`.
- Exact approved effects:
  - AWS Budget `bjuiceval-19024`: `$999/month` -> `$1,200/month`.
  - Cost center `bjuiceval-19024-ccenter`: `$999/month` ->
    `$1,200/month`.
- Existing user-owned and concurrently appearing untracked files are outside
  scope and remain untouched.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Inventory | Verify exact identities, current caps, target caps, CLI pin, and live context | SUCCESS | plan_amendment | Gate 0 | Forge | Readbacks and dry-run facts above |  | Gate 0 complete. |
| APPROVAL-001 | Safety | Obtain double approval for both exact cap increases | SUCCESS | legitimate_safety_handling | Double approval | Forge | Initial request plus repeated exact request after approval-boundary notice |  | Both approvals received in the current task. |
| BUDGET-001 | AWS Budget | Change `bjuiceval-19024` from `$999` to `$1,200` | SUCCESS | feature_implementation | Double approval | Forge | Live `dyec aws budget set-limit`: `previous=999.0`, `requested=1200`, `observed=1200.0`, `changed=true`, `update_submitted=true` |  | Exact fixed monthly USD limit updated and verified by the command. |
| CC-001 | Cost center | Change `bjuiceval-19024-ccenter` from `$999` to `$1,200` | SUCCESS | feature_implementation | Double approval | Forge | Live `dyec cost-centers edit`: `monthly_cap_usd=1200`, `status=active`, `updated_at=2026-08-24T05:32:59Z` |  | Named active cost center updated; unrelated fields retained. |
| VERIFY-001 | Acceptance | Read back the cluster budget as `$1,200` | SUCCESS | contract_test | Gate 5 | Forge | Non-mutating exact-cap dry-run: `previous=1200.0`, `observed=1200.0`, `changed=false`, `update_submitted=false` |  | Cluster budget independently read back at the target cap. |
| VERIFY-002 | Acceptance | Read back the active cost center as `$1,200` | SUCCESS | contract_test | Gate 5 | Forge | `dyec cost-centers show`: `monthly_cap_usd=1200`, `status=active` |  | Cost center independently read back at the target cap. |

## Approved public CLI commands

```bash
dyec --json aws budget set-limit bjuiceval-19024 \
  --profile lsmc --region us-west-2 \
  --expected-current-monthly-cap-usd 999 \
  --monthly-cap-usd 1200

dyec --json cost-centers edit bjuiceval-19024-ccenter \
  --profile lsmc --home-region us-west-2 \
  --monthly-cap-usd 1200
```

## Final report

All rows terminal: `yes`

Objective complete: `yes`

Status counts:

- SUCCESS: 6
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0
- OPEN: 0
- IN_PROGRESS: 0
- ATTEMPTING_BUGFIX: 0

Validation:

- Cluster-budget live receipt changed only the named fixed monthly USD limit
  from `999.0` to `1200.0` and verified the observed result.
- Post-change non-mutating cluster-budget readback reports `1200.0`,
  `changed=false`, and `update_submitted=false`.
- Cost-center live receipt and independent show readback both report
  `monthly_cap_usd=1200` and `status=active`.

Residual risks: none for the requested cap updates. This authorization did not
extend to workflow, Slurm, DRA, cluster-lifecycle, export, or cleanup actions.
