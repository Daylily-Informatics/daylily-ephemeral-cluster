# Bjuice Validation Source and Configuration Execution Ledger

Created: 2026-08-18T10:50:11Z
Controlling request: implement the approved Bjuice Validation Source Inventory and Configuration Plan
Ledger path: `docs/plans/20260818T105011Z_bjuice_validation_source_config_ledger.md`

## Scope and boundaries

This ledger controls a read-only source inventory and local configuration build for the
non-prevalence Betelgeuse/Bjuice validation cohort. It does not authorize a workflow run,
dry-run controller, DRA creation, S3 write, OWY repair, release, cluster mutation, or cleanup.

The requested configuration baseline is DayOA `15.0.22` and the exact Bjuice v0.9 targets
`produce_sentdhiomr2_slim_kitchensink_mega` plus
`produce_sentdhiomr2_inflection_analytical_package`. Gate 0 froze a catalog target of DayOA
`15.0.23`. A concurrent, unrelated uncommitted worktree change advanced that target to
`15.0.24` during execution. The direct v0.9 entry retained historical
`validated_version: 15.0.3` and its global-window/HG002-specific contract, so neither
catalog state is silently substituted for the requested `15.0.22` per-AU baseline.

## Gate 0: inventory freeze

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
  - Branch at start: `codex/dayoa-15-0-23-catalog-pin`
  - HEAD at start: `607bbb1a549d5316de1443fea62fc5c97e305968`
  - Pre-existing untracked paths preserved: `.playwright-cli/`, `TrusSV/`,
    `docs/candidte-pre-pre-release-tuning.md`, and `tmp/dayoa-ont-headnode-proof/`.
- DayOA source inspected without changing its dirty worktree:
  - Local branch: `codex/solo-kitchensink-sex-contract`, ahead by one commit.
  - Local HEAD: `a6a7cd493eecd51e9e942215414a1822510cffa9`.
  - Pre-existing modified files: `tests/test_hiomr2_core_rules.py`,
    `tests/test_multiqc_qc_targets.py`, `workflow/rules/sent_hybrid_ilmn_ont_modular2.smk`,
    `workflow/rules/tiddit.smk`; pre-existing untracked `tmp/` preserved.
  - Annotated DayOA `15.0.22` peels to
    `e838b3aedd4a38078f916e4ef3c6fe22d3d8414f`.
  - Annotated DayOA `15.0.23` peels to
    `33624a81c167e1e3dcc671d94be3240c7c315ce3`.
- Workbook: `/Users/jmajor/Downloads/Betelgeuse Validation - LAB.xlsx`
  - SHA-256: `face0fc30a241b87ee02223c3f8117a831a6c16b17233b395ae8a15f4ba8bdd7`.
  - Size: 1,717,129 bytes; observed mtime: `2026-08-18T05:47:04-0400`.
  - Read with `@oai/artifact-tool`; source workbook was not modified.
- AWS read-only identity: profile `lsmc`, region `us-west-2`, account `108782052779`,
  ARN `arn:aws:iam::108782052779:root`.
- Bucket transfer acceleration: `lsmc-ssf-sequencing-data` reports `Enabled`.
- xfer1 evidence:
  - Canonical host `sfo1-xfer1.sfo.lsmc.com` did not resolve from this Mac.
  - The locally authenticated Tailscale peer map identified online peer
    `sfo1-xfer1.faun-salmon.ts.net` for host `sfo1-xfer1`; inspection used that explicit,
    verified peer endpoint as `johnm`.
  - All five Illumina source directories and all 32 ONT Set directories are present under
    `/mnt/seqdata`.
  - Every Illumina directory has `CopyComplete.txt`.
  - Every ONT Set directory has three `final_summary_*.txt`, three
    `output_hash_*.csv`, and three `report_*.json` files.
  - None of the 37 source directories contains a local root `OOW.done` or `OOW.err`.
- S3 inventory: all 37 canonical roots are nonempty and vendor-ready; all 37 lack root
  `OOW.done` and `OOW.err`. The inventory covers 450,599 objects and
  38,603,057,564,236 bytes at snapshot `2026-08-18T11:55:36+00:00`.
- Known limits: no launch or mount was attempted. Canonical OWY publication evidence is a
  hard launch gate even when source/S3 byte parity is otherwise demonstrated.

Gate 0 sweep commands include `git status --short --branch`, `git rev-parse HEAD`,
`shasum -a 256`, artifact-tool range inspection/rendering, `aws sts get-caller-identity`,
`aws s3api get-bucket-accelerate-configuration`, read-only S3 list/head operations,
`tailscale status --json`, and read-only xfer1 `find` checks.

## Execution evidence

- Source specification: `docs/jem/bjuice_validation/source_spec.json` defines exactly five
  ILMN and 32 ONT canonical roots, five bundles, and explicit mount projections.
- Reviewed crosswalk: `docs/jem/bjuice_validation/sample_crosswalk.tsv` has 157 rows:
  logical-run totals `48/33/35/41`, paired totals `32/19/17/31`, 29 ILMN-only rows, and
  29 ONT-only rows.
- Read-only inventory: `docs/jem/bjuice_validation/source_inventory.json`; SHA-256
  `3943667953917ac4d9292d5f18f8377b574a8ec125f641a6e9dcb06ebff07127`.
- Local configuration generator: `daylily_ec/bjuice_validation_config.py`; no prevalence
  generator or existing catalog implementation was altered.
- Generated capsules: `docs/jem/bjuice_validation/configs/{bundle1a,bundle1b,bundle2,bundle3,bundle4}/`.
  AU counts are `32/32/19/17/31`; every AU has exactly one SR and one LR input.
- Guidance: `docs/jem/Bjuice_guidance.md` expands all 37 URIs, SeqNAS paths, object/byte
  counts, timestamps, mount projections, config paths, exclusions, runtime contract, and a
  future dry-run-only command sequence marked not executed.
- Focused tests: `pytest -q tests/test_bjuice_validation_config.py` -> `15 passed`.
- DayOA `15.0.22` validation: the tag's own `manifest_contract.load_manifest_set` and
  Draft 4 runtime config schema accepted all five capsules; source inspection confirmed the
  per-AU ONT contract and both requested targets.
- Determinism: a second generation into a new empty directory was byte-identical under
  `diff -qr`.
- Full pytest: `2623 passed, 32 failed, 11 skipped` in both normal and coverage runs. The
  failures are outside the new Bjuice files and cover existing Conda activation, CLI/core,
  concurrent catalog/package parity, and headnode-mock drift.
- Coverage: `python -m coverage report -m --fail-under=70` -> `TOTAL 90%`, gate passed;
  `tests/test_bjuice_validation_config.py` was 100% covered.
- Ruff: the two changed Python files pass. Repository-wide `ruff check .` reports 4,085
  pre-existing/untracked-tree findings, including `bin/` and the pre-existing
  `tmp/dayoa-ont-headnode-proof/` tree.
- No DayOA dry run or live run was invoked. No cluster, DRA, mount, S3, OWY, release, or
  cleanup mutation occurred.

## Control ledger

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| BJV-001 | Gate 0 | Freeze repo, workbook, AWS, xfer1, and S3 baseline | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | Gate 0 plus complete inventory snapshot above |  | Baseline and later concurrent drift are explicitly separated. |
| BJV-002 | Workbook | Normalize all 157 logical-run rows into a reviewed crosswalk | SUCCESS | feature_implementation | Gate 1 | orchestrator | `sample_crosswalk.tsv`; exact totals `48/33/35/41`, paired `32/19/17/31` |  | All rows reviewed; 58 one-sided rows retain explicit blockers. |
| BJV-003 | Sources | Inventory all 37 canonical prefixes and exclusions | SUCCESS | feature_implementation | Gate 1 | orchestrator | `source_inventory.json`; 450,599 objects, 38,603,057,564,236 bytes; 37/37 ready; 0/37 `OOW.done` |  | Every selected and excluded source class is recorded. |
| BJV-004 | Generator | Add deterministic crosswalk/inventory/config generator with fail-closed validation | SUCCESS | feature_implementation | Gate 1 | orchestrator | `daylily_ec/bjuice_validation_config.py`; deterministic regeneration pass |  | Separate from prevalence; ambiguous/missing/unexpected inputs fail loudly. |
| BJV-005 | Bundle 1a | Generate 32 paired AUs from ILMN run 0012 plus Run 1 ONT | SUCCESS | feature_implementation | Gate 1 | orchestrator | `configs/bundle1a/`; 32 AUs, 64 inputs/links |  | Receipt is `CONFIG_COMPLETE`, `LAUNCH_BLOCKED`. |
| BJV-006 | Bundle 1b | Generate 32 paired AUs from ILMN run 0014 plus the same Run 1 ONT | SUCCESS | feature_implementation | Gate 1 | orchestrator | `configs/bundle1b/`; identical ONT paths to 1a, disjoint ILMN root |  | Receipt is `CONFIG_COMPLETE`, `LAUNCH_BLOCKED`. |
| BJV-007 | Bundle 2 | Generate 19 paired AUs using literal ONT `2025/20250629_*` prefixes | SUCCESS | feature_implementation | Gate 1 | orchestrator | `configs/bundle2/`; literal 2025 parent retained; 19 AUs |  | Receipt is `CONFIG_COMPLETE`, `LAUNCH_BLOCKED`. |
| BJV-008 | Bundle 3 | Generate 17 paired AUs from Run 3 sources | SUCCESS | feature_implementation | Gate 1 | orchestrator | `configs/bundle3/`; explicit reviewed GIAB `-c` to BCL `-b` translations; 17 AUs |  | Receipt is `CONFIG_COMPLETE`, `LAUNCH_BLOCKED`. |
| BJV-009 | Bundle 4 | Generate 31 paired AUs from Run 4 sources | SUCCESS | feature_implementation | Gate 1 | orchestrator | `configs/bundle4/`; 31 AUs; no unverified truthset |  | Receipt is `CONFIG_COMPLETE`, `LAUNCH_BLOCKED`. |
| BJV-010 | DayOA | Validate six-manifest topology and runtime YAML against exact tag `15.0.22` | SUCCESS | contract_test | Gate 4 | orchestrator | Tag-native manifest loader and config schema pass all five; exact targets/per-AU source present |  | Local contract validation complete; no controller invoked. |
| BJV-011 | DYEC catalog | Reconcile current v0.9 catalog target/version with requested baseline | BLOCKED | plan_amendment | Gate 4 | orchestrator | Gate 0 target 15.0.23; concurrent uncommitted target 15.0.24; v0.9 validated 15.0.3/global slice | Active catalog contract does not match reviewed 15.0.22 per-AU capsule. | Requires an explicit future catalog/version decision and validation receipt; no substitution made. |
| BJV-012 | Guidance | Create `docs/jem/Bjuice_guidance.md` with expanded URIs, mounts, commands, hashes, counts, and exclusions | SUCCESS | feature_implementation | Gate 1 | orchestrator | `docs/jem/Bjuice_guidance.md` |  | All 37 URIs and all five capsule file sets are expanded. |
| BJV-013 | Tests | Add focused tests for totals, topology, exact path filtering, and negative exclusions | SUCCESS | contract_test | Gate 5 | orchestrator | `tests/test_bjuice_validation_config.py` -> 15 passed; mocked AWS |  | Covers counts, topology, paths, exclusions, aliases, mates, runtime, and receipts. |
| BJV-014 | Acceptance | Run focused/full pytest, Ruff, coverage 70%, and `git diff --check` | BLOCKED | contract_test | Gate 5 | orchestrator | Focused green; coverage 90%; scoped Ruff/diff green; full pytest 32 unrelated failures; repo-wide Ruff 4,085 existing findings | Unrelated existing/concurrent activation, CLI, catalog/package, legacy bin/tmp, and headnode-mock drift keeps repository-wide gates red. | Bjuice acceptance is green; repository-wide green requires the owners of those independent changes to reconcile them. |
| BJV-015 | Launch gate | Preserve `LAUNCH_BLOCKED` until canonical `OOW.done` publication evidence exists | BLOCKED | legitimate_safety_handling | Gate 5 | orchestrator | All five receipts; inventory reports 37 missing `OOW.done` | Canonical OWY publication evidence is absent and the user prohibited launch. | Unblock only after OWY evidence plus explicit future launch approval; nothing was launched. |

## Final report

All rows terminal: yes

Configuration production complete: yes

Live launch authorized: no

Live launch state: `LAUNCH_BLOCKED`

Status counts: `SUCCESS=12`, `BLOCKED=3`, all other terminal states `=0`

The local source-inventory and configuration-production objective is complete. The broader
live execution objective is not complete because BJV-011 and BJV-015 require external
contract/publication decisions and explicit future authorization. Repository-wide acceptance
also remains blocked by BJV-014's unrelated dirty-worktree/test debt; those files were not
modified or reverted by this work.
