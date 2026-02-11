# Daylily Ephemeral Cluster — Control Plane Refactor Implementation Plan

**Branch**: `refactor/control-plane-implementation-plan`
**Spec**: `REFACTOR_SPEC.md`
**Status**: DRAFT — Awaiting approval before any implementation begins.

---

## 1. Executive Summary

This plan converts the 2585-line Bash monolith (`bin/daylily-create-ephemeral-cluster`) into a deterministic, testable Python control plane (`daylily_ec/` package) while preserving **100% behavioral parity** with the existing system.

**Scope**:
- 19 implementation tasks (CP-001 → CP-019)
- 5 phases (Phase 0 → Phase 4)
- New `daylily_ec/` package (~20 modules) alongside existing `daylib/`
- Thin Bash wrapper replaces monolith as entrypoint
- Local JSON-based state store (no new AWS persistence)

**Non-negotiables**:
- Same CLI flags, same interactive prompts, same exit behavior
- Same artifact filenames and paths under `~/.config/daylily/`
- Same AWS resource shapes (budgets, heartbeat, CFN stacks, IAM policies)
- Same environment variable semantics (`DAY_DISABLE_AUTO_SELECT`, `DAY_BREAK`, `AWS_PROFILE`)
- Parity verification gate before legacy removal

**Risks**:
- Triplet config parsing edge cases (string/list/map normalization)
- Spot price script integration (subprocess vs library import)
- Interactive prompt parity in non-TTY environments
- yq flavor elimination may surface hidden YAML parsing differences

---

## 2. Ambiguities & Conflicts Found in REFACTOR_SPEC.md

| # | Issue | Resolution | Status |
|---|-------|-----------|--------|
| A1 | **Exit codes diverge from current Bash.** Spec assigns exit 2 = AWS failure, 3 = drift. Current Bash uses `exit 3` for general failures and `exit 1` for validation. | **Adopt spec's exit codes** for the Python path. Document the change. Old Bash wrapper retains `exit 3` until removed. | ✅ Resolved |
| A2 | **`dayctl infra ...` commands** referenced in spec (§4, §5) but no CP task explicitly implements them. | **Defer** `dayctl` CLI to a post-CP-019 task. The create workflow calls modules directly. Revisit scope later. | ✅ Resolved (deferred) |
| A3 | **Phase 0 mentions `--use-python` hidden flag** but no CP task covers it. | Add to CP-017 scope. | ✅ Resolved |
| A4 | **Spot price script path ambiguity.** CP-012 offers Option A (library import) vs Option B (subprocess). | **Library import** (Option A). Refactor `bin/calcuate_spotprice_for_cluster_yaml.py` into an importable module that also remains runnable as a standalone script (`if __name__ == "__main__"`). | ✅ Resolved |
| A5 | **`cli-core-yo` package** per global rules. Spec doesn't mention it. | **Use `cli-core-yo`** (`typer`/`click`/`rich` based, Daylily-internal). Provides consistent CLI behavior, output styling, plugin system, and XDG paths across Daylily tools. Already used by `zebra_day`. | ✅ Resolved |
| A6 | **Config format preference.** Global rules prefer JSON over YAML. Spec preserves YAML configs (triplets, pcluster templates). | Keep YAML for config/pcluster templates (backward compat). Use JSON for new artifacts (preflight report, state). | ✅ Resolved |

All ambiguities resolved.

---

## 3. Dependency Graph

```
CP-001 (skeleton)
├── CP-002 (triplets) ──────────────────── CP-011 (renderer) ── CP-012 (spot) ── CP-013 (pcluster runner)
├── CP-003 (AWS context) ───┬── CP-004 (preflight framework)                         │
│                           │   ├── CP-005 (quotas)                                   │
│                           │   ├── CP-006 (S3 bucket)                        CP-014 (monitor)
│                           │   └── CP-007 (IAM) ── CP-015 (heartbeat)                │
│                           └── CP-008 (CFN stack)                                    │
│                               └── CP-009 (subnet/policy selection)                  │
│                                                                                     │
├── CP-010 (budgets) ←── CP-003, CP-006, CP-004                                      │
│                                                                                     │
└── CP-016 (state/drift) ←── CP-004, CP-008, CP-010, CP-015                          │
                                                                                      │
    CP-017 (wire workflow) ←── ALL above ─────────────────────────────────────────────┘
    CP-018 (tests) ←── CP-002..CP-016
    CP-019 (docs) ←── CP-017
```

---

## 4. Phase Breakdown

### Phase 0 — Build Control Plane Alongside Existing Bash (CP-001 → CP-016)

**Goal**: Implement all Python modules without changing the existing entrypoint. The Bash monolith remains the production path.

**Deliverables**:
- `daylily_ec/` package with all submodules
- Unit tests for triplets, renderer, preflight report schema
- Hidden `--use-python` flag on existing Bash wrapper (end of phase)

**Acceptance**: Python path can create clusters end-to-end using same YAML templates; produces same AWS-visible outcomes as Bash.

**Duration estimate**: 3–4 weeks (bulk of work).

### Phase 1 — Swap Entrypoint (CP-017)

**Goal**: `bin/daylily-create-ephemeral-cluster` becomes a thin Bash wrapper (conda/bash guard → `exec python -m daylily_ec.cli`). Old monolith renamed to `bin/legacy/daylily-create-ephemeral-cluster.bash`.

**Deliverables**:
- Wrapper script (< 30 lines)
- Legacy script preserved for rollback
- Parity verification checklist executed and documented

**Acceptance**: All flags, prompts, artifacts, and AWS resources match legacy output.

**Duration estimate**: 1 week.

### Phase 2 — Internalize Remaining Shell Glue

**Goal**: Replace subprocess calls to shell scripts with native Python/boto3.

**Targets**:
- `bin/init_cloudstackformation.sh` → `daylily_ec.aws.cloudformation` (already done in CP-008)
- `bin/create_budget.sh` → `daylily_ec.aws.budgets` (already done in CP-010)
- `bin/get_git_deets.sh` → Python `git` + YAML read
- `bin/other/regsub_yaml.sh` → already replaced by Python renderer (CP-011)

**Acceptance**: No `yq`/`jq`/`bc` required for the create path.

**Duration estimate**: 1 week.

### Phase 3 — Formal Drift Detection (CP-016 completion)

**Goal**: `dayctl drift check` command.

**Deliverables**:
- CFN stack drift detection (Layer 1)
- Budget presence and notification verification (Layer 3)
- Heartbeat schedule/topic/subscription state (Layer 3)
- Machine-readable JSON drift report

**Acceptance**: Drift report is stable and deterministic.

**Duration estimate**: 1 week.

### Phase 4 — Immutable Image Baking (Optional, Feature-Flagged)

**Goal**: `dayctl image build` using `pcluster build-image`.

**Deliverables**:
- Split `post_install_ubuntu_combined.sh` into image-time vs runtime steps
- Feature flag (default: off)
- Node readiness check script

**Acceptance**: Cluster nodes converge to identical state vs current runtime bootstrap.

**Duration estimate**: 2–3 weeks (can be deferred).

---

## 5. Task Sequencing (CP-001 → CP-019)

### CP-001: Python Control Plane Package Skeleton

| Property | Value |
|----------|-------|
| **Phase** | 0 |
| **Deps** | None |
| **Risk** | Low |
| **Complexity** | Low |

**Files created**:
- `daylily_ec/__init__.py`
- `daylily_ec/cli.py` — built on `cli-core-yo` (`typer`/`click`/`rich`)
- `daylily_ec/workflow/__init__.py`
- `daylily_ec/config/__init__.py`
- `daylily_ec/aws/__init__.py`
- `daylily_ec/pcluster/__init__.py`
- `daylily_ec/render/__init__.py`
- `daylily_ec/state/__init__.py`
- `daylily_ec/artifacts/__init__.py`
- `daylily_ec/util/__init__.py`

**Files modified**:
- `pyproject.toml` — add `daylily_ec*` to `[tool.setuptools.packages.find] include`; add `cli-core-yo` to deps

**Acceptance criteria**:
1. `python -c "import daylily_ec"` succeeds in DAY-EC
2. `daylily_ec/cli.py` uses `cli-core-yo` app scaffolding and accepts `--region-az`, `--profile`, `--config`, `--pass-on-warn`, `--debug`, `--repo-override`, `--non-interactive` (even if unimplemented)
3. `--help` output shows all preserved flags with `rich`-formatted help

---

### CP-002: Config Triplet Parsing + Write-Back

| Property | Value |
|----------|-------|
| **Phase** | 0 |
| **Deps** | CP-001 |
| **Risk** | Medium — triplet normalization has edge cases |
| **Complexity** | Medium |

**Files created**:
- `daylily_ec/config/triplets.py` — `TripletConfig`, `Triplet`, `TripletResolver`
- `daylily_ec/config/models.py` — Pydantic models for config structure

**Acceptance criteria**:
1. Can load `config/daylily_ephemeral_cluster_template.yaml`
2. Missing required keys are added to config file on disk with `[PROMPTUSER, "", ""]` triplets
3. Auto-select logic matches Bash `should_auto_apply_config_value` exactly:
   - If `DAY_DISABLE_AUTO_SELECT` is set → auto-select disabled
   - If `action == "USESETVALUE"` and `set_value` present and auto-select enabled → use `set_value`
   - If `set_value` present and not `PROMPTUSER` → use it (regardless of action, when auto-select enabled)
4. Normalization: `"null"`/`"None"` → `""`, `True`/`False` → `"true"`/`"false"`
5. String, list `[action, default, set_value]`, and map `{action, default_value, set_value}` formats all parsed correctly

---

### CP-003: AWS Context and Clients

| Property | Value |
|----------|-------|
| **Phase** | 0 |
| **Deps** | CP-001 |
| **Risk** | Low |
| **Complexity** | Low |

**Files created**:
- `daylily_ec/aws/context.py` — `AWSContext` class wrapping boto3 session, profile, region, account_id, caller_arn

**Acceptance criteria**:
1. Given `--profile` + `--region-az`, returns `account_id` and `caller_arn`
2. Stable for both IAM user and assumed-role ARNs
3. Region resolution precedence: CLI flag → explicit config → env var → hardcoded default
4. `AWS_PROFILE` env respected when no `--profile` flag given

---

### CP-004: Preflight Framework and Report Writer

| Property | Value |
|----------|-------|
| **Phase** | 0 |
| **Deps** | CP-001, CP-003 |
| **Risk** | Medium — sets the contract for all validators |
| **Complexity** | Medium |

**Files created**:
- `daylily_ec/workflow/create_cluster.py` — skeleton orchestrator
- `daylily_ec/state/models.py` — `PreflightReport`, `CheckResult(PASS|WARN|FAIL)` Pydantic models
- `daylily_ec/state/store.py` — writes JSON to `~/.config/daylily/preflight_<cluster>_<ts>.json`

**Acceptance criteria**:
1. Preflight emits JSON report to `~/.config/daylily/`
2. Report ordering stable, keys sorted, includes PASS/WARN/FAIL
3. FAIL stops immediately — no AWS mutation
4. Gating order matches spec §10.5: Toolchain → AWS Identity → IAM → Config → Quota → S3 Bucket → KeyPair → Network
5. `--pass-on-warn` allows WARN to continue, absence causes WARN to exit

---

### CP-005: QuotaValidator

| Property | Value |
|----------|-------|
| **Phase** | 0 |
| **Deps** | CP-003, CP-004 |
| **Risk** | Low |
| **Complexity** | Low |

**Files created**:
- `daylily_ec/aws/quotas.py` — `QuotaValidator`

**Acceptance criteria**:
1. Emits check results for all quota codes (vCPU on-demand, spot, EBS, VPC, etc.)
2. Spot vCPU computed from `max_count_*` exactly as Bash
3. WARN/FAIL gating respects `--pass-on-warn`

---

### CP-006: S3 Bucket Selector + Validator

| Property | Value |
|----------|-------|
| **Phase** | 0 |
| **Deps** | CP-003, CP-004 |
| **Risk** | High — non-negotiable gate |
| **Complexity** | Medium |

**Files created**:
- `daylily_ec/aws/s3.py` — `S3BucketSelector`, `S3BucketValidator`

**Acceptance criteria**:
1. Filters buckets by name containing `omics-analysis` and region match
2. Runs `daylily-omics-references.sh verify --exclude-b37` and hard-fails on non-zero exit
3. Workflow **cannot** reach any pcluster call if this validator fails
4. Auto-select if single bucket and `DAY_DISABLE_AUTO_SELECT` not set

---

### CP-007: IAM Policy Checks and Ensurers

| Property | Value |
|----------|-------|
| **Phase** | 0 |
| **Deps** | CP-003, CP-004 |
| **Risk** | Medium — touches IAM |
| **Complexity** | Medium |

**Files created**:
- `daylily_ec/aws/iam.py` — `IAMPolicyChecker`, `IAMPolicyEnsurer`

**Acceptance criteria**:
1. Checks `DaylilyGlobalEClusterPolicy` + `DaylilyRegionalEClusterPolicy-${region}` attached via user or group
2. Ensures managed policy `pcluster-omics-analysis` exists (idempotent create)
3. Resolves scheduler role ARN using env vars (`DAY_HEARTBEAT_SCHEDULER_ROLE_ARN`) and existing role names (`eventbridge-scheduler-to-sns`, `daylily-eventbridge-scheduler`)

---

### CP-008: Baseline CloudFormation Stack Ensure

| Property | Value |
|----------|-------|
| **Phase** | 0 |
| **Deps** | CP-003, CP-004 |
| **Risk** | Medium — CFN stack creation |
| **Complexity** | Medium |

**Files created**:
- `daylily_ec/aws/cloudformation.py` — `CloudFormationEnsurer`

**Acceptance criteria**:
1. Uses existing template `config/day_cluster/pcluster_env.yml`
2. Stack name derivation matches Bash: `daylily-cs-<az>` with digit-to-word substitution (1→one, 2→two, etc.)
3. Parameters match `bin/init_cloudstackformation.sh`
4. If policy already exists, passes `CreatePolicy=false`
5. Idempotent: if stack in `CREATE_COMPLETE`, skips

---

### CP-009: Subnet and Policy Selection

| Property | Value |
|----------|-------|
| **Phase** | 0 |
| **Deps** | CP-003, CP-008 |
| **Risk** | Low |
| **Complexity** | Medium |

**Files created**:
- `daylily_ec/aws/ec2.py` — `SubnetSelector`, `PolicySelector`

**Acceptance criteria**:
1. Finds public/private subnets using tag containing `Public Subnet` / `Private Subnet` and AZ match
2. Preserves logic: both missing → triggers CFN stack creation; partial missing → hard fail
3. Selects `pclusterTagsAndBudget` IAM policy ARN (auto-select if single and auto-select enabled)
4. Triplet config override for subnets/policy respected



---

### CP-010: BudgetManager (replace create_budget.sh)

| Property | Value |
|----------|-------|
| **Phase** | 0 |
| **Deps** | CP-003, CP-006, CP-004 |
| **Risk** | Medium — budget shapes must match exactly |
| **Complexity** | Medium |

**Files created**:
- `daylily_ec/aws/budgets.py` — `BudgetManager`

**Acceptance criteria**:
1. Creates budgets identical in shape to `bin/create_budget.sh`:
   - Cost filters: `user:aws-parallelcluster-project$<project>` and `user:aws-parallelcluster-clustername$<cluster>`
   - Threshold notifications identical (25, 50, 75, 99 for global; 75 for cluster)
2. Updates S3 tags file path: `data/budget_tags/pcluster-project-budget-tags.tsv`
3. Idempotent when budgets already exist
4. Global budget (`daylily-global`) and cluster budget (`da-<region_az>-<cluster>`) both handled
5. Budget enforcement flag (`enforce`/`skip`) preserved

---

### CP-011: YAML Substitutions Renderer

| Property | Value |
|----------|-------|
| **Phase** | 0 |
| **Deps** | CP-002 |
| **Risk** | Medium — must replace regsub_yaml.sh + envsubst exactly |
| **Complexity** | Medium |

**Files created**:
- `daylily_ec/render/renderer.py` — `YAMLRenderer`

**Acceptance criteria**:
1. Replaces all `${REGSUB_*}` tokens in template text exactly
2. Writes both `.yaml.init` (template copy) and `init_template` artifact in `~/.config/daylily/` matching naming scheme
3. Required substitution keys enforced: `REGSUB_REGION`, `REGSUB_PUB_SUBNET`, `REGSUB_PRIVATE_SUBNET`, `REGSUB_CLUSTER_NAME`
4. All 25+ `REGSUB_*` keys from current `REG_SUBSTITUTIONS` associative array supported
5. YAML key ordering preserved (stable output)

---

### CP-012: Spot Heuristics Integration

| Property | Value |
|----------|-------|
| **Phase** | 0 |
| **Deps** | CP-003, CP-011 |
| **Risk** | Medium — pricing API access may vary by account |
| **Complexity** | Medium |

**Approach**: Library import (Option A). Refactor `bin/calcuate_spotprice_for_cluster_yaml.py` into an importable module under `daylily_ec/` while preserving its `if __name__ == "__main__"` block so it remains runnable as a standalone script.

**Files created/modified**:
- `daylily_ec/aws/spot_pricing.py` — importable spot price logic extracted from `bin/calcuate_spotprice_for_cluster_yaml.py`
- `bin/calcuate_spotprice_for_cluster_yaml.py` — becomes thin wrapper calling `daylily_ec.aws.spot_pricing` (preserves standalone CLI)
- `daylily_ec/workflow/create_cluster.py` — calls spot pricing as library

**Acceptance criteria**:
1. Final YAML has `SpotPrice` values set for each `ComputeResources` group
2. Uses bump price `4.14` and AZ/profile inputs
3. Fails with actionable message if spot API access denied (parity with current behavior)
4. Input: init template YAML → Output: final cluster YAML
5. `python bin/calcuate_spotprice_for_cluster_yaml.py -i ... -o ... --az ... --profile ... -b 4.14` still works as before

---

### CP-013: PclusterRunner + Dry-Run Semantics

| Property | Value |
|----------|-------|
| **Phase** | 0 |
| **Deps** | CP-011, CP-012 |
| **Risk** | Medium — must match exact dry-run success string |
| **Complexity** | Medium |

**Files created**:
- `daylily_ec/pcluster/runner.py` — `PclusterRunner`

**Acceptance criteria**:
1. Dry-run success criterion: `message == "Request would have succeeded, but DryRun flag is set."`
2. Honors `DAY_BREAK=1` → exit 0 after dry-run success, no real creation
3. Real create with same flags: `-n <name> -c <config> --region <region>`
4. AWS_PROFILE passed via environment (same as current `AWS_PROFILE=${AWS_PROFILE} pcluster create-cluster ...`)
5. Returns parsed JSON response

---

### CP-014: Cluster Creation Monitor

| Property | Value |
|----------|-------|
| **Phase** | 0 |
| **Deps** | CP-013 |
| **Risk** | Low |
| **Complexity** | Low |

**Files created**:
- `daylily_ec/pcluster/monitor.py` — `ClusterMonitor`

**Acceptance criteria**:
1. Wait loop stops only on `CREATE_COMPLETE`
2. 5 consecutive non-zero monitor exits before failing (matches Bash threshold)
3. Uses `bin/helpers/watch_cluster_status.py` via subprocess initially (or reimplements its polling logic)
4. Reports status transitions to stdout

---

### CP-015: HeartbeatManager and Role Resolution

| Property | Value |
|----------|-------|
| **Phase** | 0 |
| **Deps** | CP-003, CP-007 |
| **Risk** | Medium — multi-fallback role resolution |
| **Complexity** | Medium |

**Files created**:
- `daylily_ec/aws/heartbeat.py` — `HeartbeatManager` (port of `bin/helpers/setup_cluster_heartbeat.py`)

**Acceptance criteria**:
1. Creates/updates SNS topic, subscription, and EventBridge Scheduler schedule with same names and schedule expression
2. Persists created ARNs in StateStore
3. Non-fatal failure behavior matches current script (warn and continue, do not abort cluster creation)
4. Role ARN resolution: `DAY_HEARTBEAT_SCHEDULER_ROLE_ARN` env → `daylily-eventbridge-scheduler` role → `eventbridge-scheduler-to-sns` role → fail with clear message
5. `AuthorizationError` on SNS handled gracefully (same as current Python helper)

---

### CP-016: StateStore + Drift Detection

| Property | Value |
|----------|-------|
| **Phase** | 0 (state) / Phase 3 (drift detection) |
| **Deps** | CP-004, CP-008, CP-010, CP-015 |
| **Risk** | Low (state) / Medium (drift) |
| **Complexity** | Medium |

**Files created/modified**:
- `daylily_ec/state/store.py` — `StateStore` (extend from CP-004)
- `daylily_ec/state/drift.py` — `DriftDetector`

**Acceptance criteria**:
1. Writes state JSON per run (`~/.config/daylily/state_<cluster>_<ts>.json`) including:
   - Selected bucket, keypair, subnet IDs, policy ARN
   - Budget names
   - Heartbeat resources (topic ARN, schedule name)
   - Paths to generated YAML artifacts
2. JSON serialized with sorted keys (deterministic)
3. Drift check (Phase 3) reports mismatches for Layer 1 and Layer 3 resources without mutating anything
4. Exit code 3 for drift detected (drift command only)

---

### CP-017: Wire Full Create Workflow + Swap Entrypoint

| Property | Value |
|----------|-------|
| **Phase** | 1 |
| **Deps** | CP-001 through CP-016 |
| **Risk** | High — the critical swap |
| **Complexity** | High |

**Files modified**:
- `daylily_ec/workflow/create_cluster.py` — full orchestration
- `bin/daylily-create-ephemeral-cluster` — becomes thin wrapper (< 30 lines)

**Files created**:
- `bin/legacy/daylily-create-ephemeral-cluster.bash` — preserved monolith for rollback

**Acceptance criteria**:
1. End-to-end run produces:
   - Same gating behaviors (bucket validation, quota checks)
   - Same pcluster create semantics
   - Same artifact outputs in `~/.config/daylily/`
2. Old Bash monolith is no longer the orchestrator
3. `--use-python` hidden flag works (for transition testing before full swap)
4. Parity verification checklist (§10.7) passes before this is merged to main

---

### CP-018: Tests

| Property | Value |
|----------|-------|
| **Phase** | 0 (continuous) |
| **Deps** | CP-002 through CP-016 |
| **Risk** | Low |
| **Complexity** | Medium |

**Files created**:
- `tests/test_triplets.py` — triplet parsing, auto-select, normalization
- `tests/test_renderer.py` — REGSUB substitution correctness, byte-stable output
- `tests/test_preflight_report.py` — schema stability, gating order
- `tests/test_aws_context.py` — profile/region resolution precedence
- `tests/test_budgets.py` — budget shape parity (mocked)
- `tests/test_state_store.py` — JSON output determinism

**Acceptance criteria**:
1. Unit tests cover: triplet parsing, auto-select behavior, renderer substitution, preflight report schema
2. Mocked AWS tests for: budget creation shape, IAM policy check, CFN stack name derivation
3. Byte-stable output assertions for renderer and state store
4. `pytest --cov` shows coverage on all `daylily_ec/` modules
5. All tests pass in CI (GitHub Actions)

---

### CP-019: Documentation Updates

| Property | Value |
|----------|-------|
| **Phase** | 1 |
| **Deps** | CP-017 |
| **Risk** | Low |
| **Complexity** | Low |

**Files modified**:
- `README.md` — describes new Python control plane, updated quick start, preserved prerequisites

**Acceptance criteria**:
1. README describes Python control plane behavior
2. CLI flags and environment variables documented
3. Prerequisites unchanged (conda, pcluster, AWS credentials)
4. Migration notes for users of `--use-python` flag

---

## 6. Testing Strategy

### Layers

| Layer | What | How | When |
|-------|------|-----|------|
| **Unit** | Triplet parsing, renderer substitutions, model schemas, config normalization | `pytest` with fixtures, no AWS calls | Every CP task (CP-018 tracks) |
| **Mocked AWS** | Budget creation shapes, IAM policy checks, CFN stack name derivation, heartbeat wiring | `pytest` + `moto` or `unittest.mock` patching boto3 | CP-005 through CP-016 |
| **Integration (local)** | End-to-end workflow with real AWS (sandbox account) | Manual + scripted: run Python path, compare artifacts to Bash path | Phase 1 gate |
| **Parity verification** | Side-by-side Bash vs Python cluster creation | Compare: generated YAML, budgets, heartbeat resources, IAM, subnets, artifacts | **Mandatory** before legacy removal |

### Key Test Cases

1. **Triplet edge cases** (CP-002):
   - String format: `"PROMPTUSER"`
   - List format: `["USESETVALUE", "", "subnet-abc123"]`
   - Map format: `{action: USESETVALUE, default_value: "", set_value: "subnet-abc123"}`
   - Null normalization: `"null"` → `""`, `"None"` → `""`
   - Boolean normalization: `True` → `"true"`, `False` → `"false"`
   - `DAY_DISABLE_AUTO_SELECT` set vs unset

2. **Renderer byte stability** (CP-011):
   - Given identical inputs, output YAML is byte-identical across runs
   - All 25+ `REGSUB_*` keys substituted
   - Missing required key → immediate error

3. **Preflight gating order** (CP-004):
   - Validators execute in spec-mandated order
   - FAIL at step N → steps N+1..end skipped
   - WARN + `--pass-on-warn` → continue
   - WARN without flag → exit 1

4. **Budget shape** (CP-010):
   - Cost filter key format matches `bin/create_budget.sh`
   - Notification thresholds match
   - Idempotent re-run does not error

5. **State store determinism** (CP-016):
   - JSON output has sorted keys
   - Same inputs → byte-identical JSON

### Coverage Target

- `pytest --cov=daylily_ec` with minimum 80% line coverage on core modules
- 100% coverage on `triplets.py` and `renderer.py` (these are parity-critical)

### CI Integration

- GitHub Actions workflow runs `pytest` on every push to feature branches
- `ruff check` + `ruff format --check` + `mypy --ignore-missing-imports` as pre-merge gates

---

## 7. Rollback Plan

### During Phase 0 (No Risk)

The Bash monolith is untouched. Python code exists alongside but is not wired as entrypoint. Rollback = delete `daylily_ec/` directory.

### During Phase 1 (Swap)

| Step | Action |
|------|--------|
| 1 | `bin/legacy/daylily-create-ephemeral-cluster.bash` preserved at swap time |
| 2 | If Python path fails in production: `cp bin/legacy/daylily-create-ephemeral-cluster.bash bin/daylily-create-ephemeral-cluster` |
| 3 | Commit revert and push |
| 4 | Investigate failure in Python path before re-attempting swap |

### During Phase 2+ (Internalization)

Each shell script replacement is a separate commit. Revert specific commits to restore subprocess calls to the shell originals.

### Nuclear Rollback

```sh
git revert --no-commit HEAD~N..HEAD  # revert all refactor commits
git commit -m "rollback: restore pre-refactor state"
```

The legacy branch and original Bash script remain available indefinitely.

---

## 8. Migration Checkpoints (Go/No-Go Gates)

### Gate 1: Contract Lock (after CP-002 + CP-004)

**Criteria**:
- [ ] `TripletConfig` model finalized and unit-tested
- [ ] `PreflightReport` JSON schema finalized and unit-tested
- [ ] Byte-stability tests pass for both

**Decision**: If models change after this point, all downstream tasks must re-verify.

### Gate 2: AWS Module Completeness (after CP-010)

**Criteria**:
- [ ] All AWS modules (context, quotas, S3, IAM, CFN, ec2, budgets) implemented
- [ ] Mocked tests pass for each module
- [ ] Budget shape matches `bin/create_budget.sh` output exactly

**Decision**: Proceed to renderer + pcluster integration only if AWS modules are solid.

### Gate 3: End-to-End Dry Run (after CP-013)

**Criteria**:
- [ ] Python workflow can produce a valid cluster YAML
- [ ] `pcluster create-cluster --dryrun true` succeeds with Python-generated YAML
- [ ] Artifacts match expected naming and content

**Decision**: If dry-run fails, stop and debug before CP-014+.

### Gate 4: Parity Verification (before CP-017 merge to main)

**Criteria** (spec §10.7):
- [ ] Create cluster with Bash script (sandbox account)
- [ ] Create cluster with Python refactor (same inputs)
- [ ] Compare:
  - Generated YAML (structural equivalence)
  - Budgets created (name, filters, thresholds)
  - Heartbeat resources (topic, subscription, schedule)
  - IAM policies created
  - Subnet selection
  - S3 bucket chosen
  - Spot prices applied
  - Artifact files created (names, content)
- [ ] AWS-visible diff shows **no behavioral difference**

**Decision**: Only after this gate passes may Bash monolith be demoted to legacy.

### Gate 5: Legacy Removal (Phase 2+)

**Criteria**:
- [ ] Python path has been production default for ≥ 2 successful cluster creations
- [ ] No rollbacks needed
- [ ] All subprocess shell calls internalized

**Decision**: Remove `bin/legacy/` directory and shell script dependencies.

---

## 9. Implementation Order Summary

| Order | Task | Phase | Complexity | Risk |
|-------|------|-------|-----------|------|
| 1 | CP-001 Skeleton | 0 | Low | Low |
| 2 | CP-002 Triplets | 0 | Medium | Medium |
| 3 | CP-003 AWS Context | 0 | Low | Low |
| 4 | CP-004 Preflight | 0 | Medium | Medium |
| 5 | CP-018 Tests (start) | 0 | Medium | Low |
| 6 | CP-005 Quotas | 0 | Low | Low |
| 7 | CP-006 S3 Bucket | 0 | Medium | High |
| 8 | CP-007 IAM | 0 | Medium | Medium |
| 9 | CP-008 CFN Stack | 0 | Medium | Medium |
| 10 | CP-009 Subnets | 0 | Medium | Low |
| 11 | CP-010 Budgets | 0 | Medium | Medium |
| 12 | CP-011 Renderer | 0 | Medium | Medium |
| 13 | CP-012 Spot | 0 | Medium | Medium |
| 14 | CP-013 Pcluster Runner | 0 | Medium | Medium |
| 15 | CP-014 Monitor | 0 | Low | Low |
| 16 | CP-015 Heartbeat | 0 | Medium | Medium |
| 17 | CP-016 State/Drift | 0/3 | Medium | Medium |
| 18 | CP-017 Wire + Swap | 1 | High | High |
| 19 | CP-018 Tests (final) | 0 | Medium | Low |
| 20 | CP-019 Docs | 1 | Low | Low |

---

**End of Implementation Plan**