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
`produce_sentdhiomr2_inflection_analytical_package`. Current repository state advertises
DayOA `15.0.23`; that drift is tracked explicitly rather than silently substituted.

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
- S3 sentinel check: representative canonical ILMN and ONT prefixes return `404` for
  `OOW.done`; the complete 37-prefix inventory remains an in-progress ledger row.
- Known limits: no launch or mount was attempted. Canonical OWY publication evidence is a
  hard launch gate even when source/S3 byte parity is otherwise demonstrated.

Gate 0 sweep commands include `git status --short --branch`, `git rev-parse HEAD`,
`shasum -a 256`, artifact-tool range inspection/rendering, `aws sts get-caller-identity`,
`aws s3api get-bucket-accelerate-configuration`, read-only S3 list/head operations,
`tailscale status --json`, and read-only xfer1 `find` checks.

## Control ledger

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| BJV-001 | Gate 0 | Freeze repo, workbook, AWS, xfer1, and S3 baseline | IN_PROGRESS | legitimate_safety_handling | Gate 0 | orchestrator | Baseline above; complete S3 aggregates pending |  |  |
| BJV-002 | Workbook | Normalize all 157 logical-run rows into a reviewed crosswalk | OPEN | feature_implementation | Gate 1 | orchestrator | Workbook ranges `SN Validation Run Mapping!A3:J102`, `ONT Barcode decoder!B3:O49`, `ONT Plate map!A1:P59` inspected |  |  |
| BJV-003 | Sources | Inventory all 37 canonical prefixes and exclusions | OPEN | feature_implementation | Gate 1 | orchestrator | Five ILMN plus 32 ONT source directories present on xfer1 |  |  |
| BJV-004 | Generator | Add deterministic crosswalk/inventory/config generator with fail-closed validation | OPEN | feature_implementation | Gate 1 | orchestrator | Existing prevalence and HG002-only generators inspected and frozen |  |  |
| BJV-005 | Bundle 1a | Generate 32 paired AUs from ILMN run 0012 plus Run 1 ONT | OPEN | feature_implementation | Gate 1 | orchestrator | Expected cardinality supplied by workbook plan |  |  |
| BJV-006 | Bundle 1b | Generate 32 paired AUs from ILMN run 0014 plus the same Run 1 ONT | OPEN | feature_implementation | Gate 1 | orchestrator | Expected cardinality supplied by workbook plan |  |  |
| BJV-007 | Bundle 2 | Generate 19 paired AUs using literal ONT `2025/20250629_*` prefixes | OPEN | feature_implementation | Gate 1 | orchestrator | Literal xfer1 directories present |  |  |
| BJV-008 | Bundle 3 | Generate 17 paired AUs from Run 3 sources | OPEN | feature_implementation | Gate 1 | orchestrator | Source directories present |  |  |
| BJV-009 | Bundle 4 | Generate 31 paired AUs from Run 4 sources | OPEN | feature_implementation | Gate 1 | orchestrator | Source directories present |  |  |
| BJV-010 | DayOA | Validate six-manifest topology and runtime YAML against exact tag `15.0.22` | OPEN | contract_test | Gate 4 | orchestrator | Tag resolves to `e838b3...`; per-AU `[start,end)` mode exists at this tag |  |  |
| BJV-011 | DYEC catalog | Reconcile current v0.9 catalog target/version with requested baseline | OPEN | plan_amendment | Gate 4 | orchestrator | Current catalog targets `15.0.23`; request specifies `15.0.22` |  |  |
| BJV-012 | Guidance | Create `docs/jem/Bjuice_guidance.md` with expanded URIs, mounts, commands, hashes, counts, and exclusions | OPEN | feature_implementation | Gate 1 | orchestrator | Pending generated receipts |  |  |
| BJV-013 | Tests | Add focused tests for totals, topology, exact path filtering, and negative exclusions | OPEN | contract_test | Gate 5 | orchestrator | Pending implementation |  |  |
| BJV-014 | Acceptance | Run focused/full pytest, Ruff, coverage 70%, and `git diff --check` | OPEN | contract_test | Gate 5 | orchestrator | Pending implementation |  |  |
| BJV-015 | Launch gate | Preserve `LAUNCH_BLOCKED` until canonical `OOW.done` publication evidence exists | OPEN | legitimate_safety_handling | Gate 5 | orchestrator | Canonical sentinel checks presently negative |  |  |

## Final report

All rows terminal: no
Configuration production complete: no
Live launch authorized: no
Live launch state: `LAUNCH_BLOCKED`
