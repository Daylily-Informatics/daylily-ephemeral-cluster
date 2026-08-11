# Coverage/site-mix DayOA and DYEC release-train ledger

Created: 2026-08-11T09:51:09Z

Objective: publish only the completed CoverageEvennessTwo and site-mix
contamination efficiency work on top of the highest current DayOA release,
then advance every active DYEC DayOA source/package catalog pin to that release,
publish the DYEC pin release, self-pin DYEC to that intermediate release, and
publish the final DYEC release.

## Gate 0: inventory and baseline

Controlling plan and ledger:
`docs/plans/20260811T095109Z_coverage_site_mix_dayoa_dyec_release_ledger.md`

- DayOA repository: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`.
  Branch `codex/solo-kitchensink-sex-contract` is exactly at annotated tag
  `13.4.27`, commit `11c195e66ec6856cc04e57f08deb0b92c144881a`, matching
  `origin/codex/solo-kitchensink-sex-contract`. The `13.4.27` commit preserves
  native alignment metadata in resolved inputs, so the requested current-max
  DayOA work is already the direct parent of the dirty optimization changes.
- DayOA owned release scope is limited to the eight modified implementation,
  rule, profile, gather, and test files plus the new coverage engine test and
  existing efficiency ledger. Pre-existing untracked `tmp/` is unrelated and
  excluded.
- DYEC repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`.
  Branch `codex/seqqc-16.1.66-retry` is exactly at annotated tag `16.1.78`,
  commit `40e5fcac4869c299f4ba0d1d789cecca62885a05`, matching its origin
  tracking branch. The tracked tree is clean before this ledger.
- DYEC has 63 pre-existing untracked paths, including a nested `TrusSV/`
  repository, backups, recordings, exports, temporary scripts, and local
  evidence. They are user-owned, unrelated, and excluded from staging.
- Current active DayOA pins are split across `13.4.20`, `13.4.22`, and
  `13.4.27` in the source and packaged catalogs and their live test contracts.
  Historical validation-run evidence and `docs/plans/**` references are not
  active pins and will remain unchanged.
- Scope amendment at user clarification: every one of the 27 DayOA analysis
  commands must end with both `validated_version` and `git_tag` set to
  `13.4.28` in both source and packaged catalogs. No command-specific older
  release or branch exception remains.
- Current DYEC self-pins are `16.1.73` in source and packaged
  `daylily_cli_global.yaml`, with a matching fork-contract test.
- Inferred next versions from the fetched remote numeric-tag maxima are DayOA
  `13.4.28`, DYEC pin release `16.1.79`, and DYEC self-pin release `16.1.80`.
  Each tag will be rechecked remotely immediately before creation. All release
  tags must be annotated, must be created only after a clean scoped commit, and
  must never overwrite or move an existing tag.
- No workflow, cluster, scheduler, FSx, budget, or analysis-root action is part
  of this release train. No raw Snakemake command will be used.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| REL-001 | DayOA baseline | Reconcile the dirty optimization work with the highest published DayOA release without importing unrelated changes | SUCCESS | feature_implementation | Gate 0 | orchestrator | HEAD and annotated `13.4.27` both peel to `11c195e6`; dirty paths are disjoint from the `13.4.27` resolver commit |  | Current-max work is already the direct baseline; no merge or rebase is required |
| REL-002 | DayOA release | Validate and publish the combined coverage-evenness/site-mix change as annotated `13.4.28` on the feature branch | SUCCESS | feature_implementation | Gate 5 | orchestrator | `69 passed`; commit `f69a6dab2b313294e5175687ec2743feaa250a35`; branch pushed; remote annotated `13.4.28` peels to the same commit |  | Combined optimization release is published on the requested feature branch |
| REL-003 | DYEC DayOA pins | Update every active source/package DayOA default, validated version, git tag, and matching test contract to `13.4.28` | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Both byte-identical catalogs contain 27 commands; all 27/27 have `validated_version=git_tag=13.4.28`; 290 focused contracts pass plus 27/27 selected runner tests |  | Every DYEC DayOA command now uses the new release; historical evidence is unchanged |
| REL-004 | DYEC pin release | Validate and publish the DayOA-pin change as annotated `16.1.79` on the current DYEC feature branch | IN_PROGRESS | feature_implementation | Gate 5 | orchestrator | Full selected run was 317 passed with four unchanged six-manifest runner-test failures; pending exact staging, commit, branch push, and annotated tag |  |  |
| REL-005 | DYEC self-pin | Update source/package DYEC bootstrap pins and their test contract to `16.1.79` | OPEN | config_or_startup_contract | Gate 2 | orchestrator | Current active self-pin is uniformly `16.1.73` |  |  |
| REL-006 | DYEC final release | Validate and publish the self-pin follow-up as annotated `16.1.80` | OPEN | feature_implementation | Gate 5 | orchestrator | Pending |  |  |
| REL-007 | Remote proof | Verify branch convergence, annotated tag objects, peeled commits, exact pin values, and final scoped repository states | OPEN | contract_test | Gate 5 | orchestrator | Pending |  |  |
| REL-008 | Local DAY-EC runtime | Reinstall this checkout editable after the final tag and verify the active `dyec` reports the final source version | OPEN | config_or_startup_contract | Gate 5 | orchestrator | User explicitly requested `pip install -e .` after the release train |  |  |

## Final report

All rows terminal: no

Objective complete: no

Status counts:

- SUCCESS: 3
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0
- OPEN: 4
- IN_PROGRESS: 1
