# DayOA Market Chooser / DYEC IAM Release Ledger

Date: 2026-08-01

## Control Ledger

Controlling request: release the DayOA availability-weighted spot partition chooser from clean private release workspaces; port its two required read-only EC2 permissions into current DYEC; advance the DYEC DayOA catalog and self-pins through the normal two-release chain; deploy the IAM policy to the exact target clusters; and collect live read-only evidence for cold lookup, 30-minute cache reuse, and attempt-aware partition selection.

Ledger path: `docs/plans/20260801T061148Z_dayoa_market_chooser_dyec_iam_release_ledger.md`

Gate 0 baseline:

- Private release root: `/Users/jmajor/projects/lsmc/.private-partition-release.REYvOI` (mode `0700`). Interrupted clone directories are isolated evidence only and will not be released.
- Clean DayOA release base: remote annotated tag `13.0.114`, tag object `968060c07b8f4b8882c72ace8979e02a319ea8cc`, peeled merge commit `83216f9e0fd4cc1d090042de1ff48a8eb2527211`. This tag descends from chooser release `13.0.113` and is the newest visible DayOA release at inventory.
- Clean DYEC release base: remote annotated tag `16.1.24`, peeled merge commit `bccc85d54dfede021acbaed9edbeea1471ac94a2`, checked out in `/Users/jmajor/projects/lsmc/.private-partition-release.REYvOI/dyec-current` on `codex/release-dyec-16.1.25-dayoa-iam`. Before PR creation, the single scoped release commit was rebased onto current remote `main` at `0c15bdc639c0286ddfd518515c6919ea8944c17e` so the release does not omit the four post-`16.1.24` mainline commits.
- Newer DYEC tags invalidated the request's provisional `15.0.27` / `15.0.28` candidates. The next candidates are `16.1.25` for the DayOA/IAM release and `16.1.26` for its self-pin release, with a fresh collision check immediately before each tag.
- DYEC `16.1.24` currently pins DayOA `13.0.108` in its active source catalog. The update target is current DayOA `13.0.114`, including its availability-weighted chooser inherited from `13.0.113`.
- Existing detached/stale DayOA and DYEC workspaces are evidence sources only. No release edit, commit, tag, or push may originate there.
- Deployment and live validation targets are intentionally unresolved at Gate 0. They must be established from authenticated AWS/ParallelCluster inventory; no account, profile, region, cluster, policy, or role will be guessed.
- Scope permits only the requested IAM addition and read-only chooser validation. It does not permit Slurm administration, workflow/job mutation, destructive AWS changes, budget changes, or package-index publishing.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| BASE-001 | Both | Establish clean private exact-tag clones and prove current remote release/tag namespace | SUCCESS | config_or_startup_contract | Gate 0 | orchestrator | DayOA `13.0.114` -> `83216f9e...`; DYEC `16.1.24` -> `bccc85d5...`; private root mode `0700` |  | Stale/detached original workspaces excluded from release actions. |
| DYEC-001 | DYEC | Port `ec2:DescribeAvailabilityZones` and `ec2:GetSpotPlacementScores` across every active source and packaged ParallelCluster IAM surface plus validation contracts | SUCCESS | feature_implementation | Gate 1 | orchestrator | Both actions added to four active source templates and their four packaged copies; `ec2:GetSpotPlacementScores` added to the EC2 validation permission group; runtime policy contract covers both actions |  | Source/payload IAM parity is exact; no Slurm policy or scheduler priority was changed. |
| DYEC-002 | DYEC | Advance every active source and packaged DayOA catalog pin from `13.0.108` to `13.0.114` without rewriting historical validation provenance | SUCCESS | config_or_startup_contract | Gate 1 | orchestrator | Source and packaged catalogs each contain 27 active `13.0.114` command pins plus the repository default; seven active contract-test surfaces updated; DayOA release commit `83216f9e0fd4cc1d090042de1ff48a8eb2527211` recorded |  | Historical `validation_runs` tags and commits are unchanged. |
| DYEC-003 | DYEC | Prove source/package parity and run focused plus proportionate broader tests | SUCCESS | contract_test | Gate 2 | orchestrator | Source/package catalog and four IAM-template pairs match byte-for-byte; rebased focused suite `330 passed`; rebased full suite `2426 passed, 20 failed, 11 skipped`; pristine current-`main` baseline reproduces the identical 20 failures (`20 failed, 33 passed` in the failure files) |  | All full-suite failures are inherited from current `main` and outside this patch. |
| DYEC-004 | DYEC | Commit, push, normally merge, and publish the next free annotated DayOA/IAM DYEC release | OPEN | config_or_startup_contract | Gate 3 | orchestrator | Candidate `16.1.25`, subject to final remote recheck |  |  |
| DYEC-005 | DYEC | Advance every authoritative DYEC self-pin to the release from DYEC-004, then test, commit, push, and normally merge | OPEN | config_or_startup_contract | Gate 3 | orchestrator | Pending |  |  |
| DYEC-006 | DYEC | Publish the next free annotated DYEC self-pin release and verify remote tag object / peeled commit | OPEN | config_or_startup_contract | Gate 3 | orchestrator | Candidate `16.1.26`, subject to final remote recheck |  |  |
| AWS-001 | AWS | Establish exact authenticated account/profile/region, active target clusters, managed policy ownership, attachment scope, and current missing permissions | OPEN | config_or_startup_contract | Gate 3 | orchestrator | Pending read-only inventory |  |  |
| AWS-002 | AWS | Deploy only the two requested read-only EC2 permissions through the owning DYEC/CloudFormation IAM surface and verify effective headnode-role permission | OPEN | feature_implementation | Gate 4 | orchestrator | Pending |  |  |
| LIVE-001 | DayOA/headnode | Create a private exact-`13.0.114` validation checkout on an exact target headnode without touching an analysis root or Slurm | OPEN | config_or_startup_contract | Gate 4 | orchestrator | Pending |  |  |
| LIVE-002 | DayOA/headnode | Prove one cold market lookup makes the required AWS calls and records price plus placement evidence | OPEN | contract_test | Gate 5 | orchestrator | Pending |  |  |
| LIVE-003 | DayOA/headnode | Prove a second lookup inside 30 minutes consumes both caches and makes zero AWS calls | OPEN | contract_test | Gate 5 | orchestrator | Pending |  |  |
| LIVE-004 | DayOA/headnode | Prove attempt 1 returns up to two availability-weighted cheap partitions and attempt greater than 1 returns all requested partitions in median price order | OPEN | contract_test | Gate 5 | orchestrator | Pending |  |  |
| DAYOA-001 | DayOA | Cut a further DayOA patch release only if live evidence identifies and validates a real DayOA source defect | OPEN | feature_implementation | Gate 5 | orchestrator | Next candidate `13.0.115`; tag must remain unused if no source change is needed |  |  |
| VERIFY-001 | All | Verify merged commits, clean release workspaces, tag immutability/type, deployment evidence, and every ledger row terminal | OPEN | contract_test | Gate 5 | orchestrator | Pending |  |  |

## Final Report

All rows terminal: no

Objective complete: no

Status counts:

- SUCCESS: 4
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0
- IN_PROGRESS: 0
- OPEN: 11

No release tag or AWS change has been made at Gate 0.
