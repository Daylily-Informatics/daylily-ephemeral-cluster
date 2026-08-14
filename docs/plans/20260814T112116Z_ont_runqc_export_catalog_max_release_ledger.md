# ONT RunQC export, catalog evidence, and max-release integration ledger

Created: 2026-08-14T11:21:16Z

## Objective

Export the successful repaired ONT RunQC analysis through DYEC's no-delete DRA
path, verify the exact S3 evidence objects, add the receipt-backed S3 evidence
URI to the production `ont_run_qc` command catalog record, merge the repaired
DayOA and DYEC histories into each repository's current maximum semver line,
and publish new immutable annotated release tags.

## Gate 0 inventory and boundary

- Successful source root:
  `/fsx/analysis_results/prod-cand-1703/pc1703-ont-set4fc1-seqqc-17018-20260814`.
  The attributed controller ran from `2026-08-14T10:33:08Z` to
  `2026-08-14T11:12:39Z`, exited `0`, is inactive, and left the root unlocked.
- Exact no-delete export destination:
  `s3://lsmc-ssf-sequencing-data/derived/prod-cand-1703/pc1703-ont-set4fc1-seqqc-17018-20260814/`.
  This follows the current cluster's validated export suffix contract. The
  destination must be empty and non-overlapping before export.
- Export protocol: record `dyec analysis visit --mode export` with the exact S3
  URI, then run `dyec export --wait --timeout-seconds 5400` from the analysis
  root. Do not pass `--delete-data-in-file-system`; preserve the FSx source.
  Do not use raw S3 copy/sync commands or alter existing run DRAs.
- DayOA maximum remote tag at Gate 0 is annotated `14.0.18`, commit
  `e5b1dbf457b993c675b89658a3dac7a9cb819a95`. It branched from `14.0.15` and
  does not contain the ONT v0.5 repair line. The repair line maximum is
  annotated `14.0.17`, commit `86288c44af731ad20dafa4105b51cfd66d7f0dd0`,
  whose direct parent is repaired DayOA `14.0.16`.
- DYEC maximum remote tag at Gate 0 is annotated `17.0.24`, commit
  `4ef055e60af1829e36f7db69bb33265574cda539`. It descends DYEC `17.0.19` but
  not the ONT repair merge `17.0.18`, commit
  `9199d7ddc87d227d0e6019f8325fc62fa2601870`.
- Release integration must preserve both histories as merge parents, retain
  historical catalog snapshots byte-exact, use the next free non-v semver patch
  tags, commit before tagging, publish annotated tags, and never move an
  existing tag.
- Tests are source/static contract tests. They must not solve or build a DayOA
  workflow Conda environment; the completed live catalog execution is the
  runtime environment acceptance evidence.
- No FSx deletion, S3 deletion, run-DRA mutation, budget/cost-center change,
  Slurm intervention, fallback path, or unrelated workspace mutation is in
  scope.

## Resume audit after newer releases appeared

- Live DayOA maximum is annotated `14.0.21`, tag object
  `e38fcab71232552969e946112a2b86100273e369`, peeled commit
  `1108a942df9df4143531745be6dca17396b997b6`. Tags `14.0.12` through
  `14.0.20` are all ancestors, and the immutable ONT v0.5 environment is
  byte-identical to repaired `14.0.16`. No additional DayOA patch is needed.
- Live DYEC maximum advanced to annotated `17.0.26`, peeled commit
  `276e5ab28e6dba881cfdffde46bddad52c6fc662`. The main-branch closeout commit
  is `80d225b79ff7d5e5c1edf2863aa9a891e6bf20bb`.
- DYEC `17.0.18` remained divergent from `17.0.26`; its Bioconda installer,
  ONT release snapshots, and associated contract tests were absent from the
  max line. DYEC `17.0.23` was also non-ancestral, but its only change was a
  ledger update already extended and superseded in `17.0.26`, so no unique
  code or evidence was omitted.
- The `17.0.26` source and packaged catalogs were not equal: the packaged
  catalog alone held the successful Bjuice alias evidence. The union retains
  that record, retains the CG export record in both active/current state,
  makes source and payload byte-identical, and pins all active/current commands
  to union DayOA `14.0.21`.
- The ONT evidence prefix is stored in the successful validation run's
  `stage_or_context`, with the exact report object in `report_path`. It is not
  assigned to `validation_evidence_s3_uri_prefix`, because that field requires
  a command-test receipt prefix containing `command_registry.json` and
  `summary.json`, which this no-delete analysis export does not contain.
- At the user's direction, the static suite was stopped rather than completed.
  It had reached 300 passing tests and exposed two stale merge-line assertions;
  both expectations were reconciled to the retained max-line behavior, but no
  test suite was rerun. No workflow environment was built.
- During final tag reservation, annotated `17.0.27` appeared at peeled commit
  `6b700a291f18b992e017bd237c1d90e539bffbdd`. It branched from `17.0.25`
  and adds a non-regressive explicit cost-center requirement for the Bjuice
  multi-AU command, but does not contain `17.0.26` or `17.0.18`. The branch was
  merged without moving or overwriting that tag; the release candidate advanced
  to `17.0.28`, whose historical `17.0.27` snapshot reflects the published tag.

## Control ledger

| ID | Requirement | Status | Evidence | Terminal note |
|---|---|---|---|---|
| G0-001 | Freeze source root, controller receipt, export prefix, max tags, divergent ancestry, and safety boundary | SUCCESS | Gate 0 inventory above | No export or release mutation preceded Gate 0. |
| EXP-001 | Verify the destination is empty/non-overlapping and DRA capacity is available | SUCCESS | Destination KeyCount was `0`; five existing DRAs had no overlap and capacity remained | Preflight failed closed before the export mutation. |
| EXP-002 | Record export visit and complete a no-delete DYEC DRA export | SUCCESS | `docs/plans/20260814T112116Z_ont_runqc_export_catalog_max_release_export/fsx_export.yaml`; DRA `dra-0ff21138a9f0beac1`; task `task-042fe3204b60a0f1e` | Receipt has `status=success`, `phase=complete`, `task_lifecycle=SUCCEEDED`, `detached=true`, and `delete_data_in_file_system=false`; FSx source remains present. |
| EXP-003 | Verify required ONT native and demultiplexed MultiQC objects at the exact S3 prefix | SUCCESS | Exact S3 HEAD checks verified native MultiQC (2,845,226 bytes), demux MultiQC (3,406,606 bytes), summary HTML (1,017 bytes), and demux done marker (9 bytes) | DRA lifecycle and object evidence are both present. |
| DAYOA-001 | Merge repaired DayOA `14.0.17` into maximum DayOA `14.0.18` and validate | SUCCESS | Union commit `1108a942df9df4143531745be6dca17396b997b6`; all `14.0.16`-`14.0.20` releases are ancestors; 66 focused static tests passed | Immutable v0.5 YAML remains byte-identical to `14.0.16`. |
| DAYOA-002 | Commit, push, and publish the next annotated DayOA tag | SUCCESS | Annotated `14.0.21`, tag object `e38fcab71232552969e946112a2b86100273e369` | Branch and tag were pushed; no tag was moved. |
| CAT-001 | Add the exact exported ONT success record to active catalog state and the new DYEC snapshot | SUCCESS | Active/current `ont_run_qc` record for `pc1703-ont-set4fc1-seqqc-17018-20260814`; exact S3 report and prefix; snapshot `17.0.28` | Source/payload catalogs are canonicalized byte-identically; CG and Bjuice evidence from `17.0.26` and the Bjuice cost-center contract from `17.0.27` are retained. |
| DYEC-001 | Merge repaired DYEC `17.0.18` and cost-center DYEC `17.0.27` into the `17.0.26` maximum release line, then pin the merged DayOA release | SUCCESS | Base includes `17.0.26` plus main closeout; merge ancestry includes `17.0.18` and `17.0.27`; active/current DayOA pin is `14.0.21` | User stopped the static suite at 300 passing tests; two observed stale assertions were reconciled without rerunning tests. No Conda environment was built. |
| DYEC-002 | Commit, push, and publish the next annotated DYEC tag | PENDING | Pending live remote-tag reservation | Do not move or reuse a tag. |
| FINAL-001 | Verify remote annotated tag objects, peeled commits, ancestry, catalog URI, and all rows terminal | PENDING | Pending terminal release audit | Report exact versions, commits, and S3 URI. |

## Final report

All rows terminal: no

Objective complete: no
