# Take101 full-root export and Take222 four-sample full-coverage execution ledger

- Created: `2026-08-03T08:27:14Z`
- Human requestor: John Major
- Cluster/profile/region: `preval-hiomr2` / `lsmc` / `us-west-2`
- Completed source analysis root: `/fsx/analysis_results/preval-hiomr2/take101`
- Planned export prefix: `s3://lsmc-ssf-sequencing-data/derived/preval-hiomr2/take101/`
- Planned next analysis root: `/fsx/analysis_results/preval-hiomr2/take222`
- Controlling predecessor ledger: `docs/plans/20260802T221250Z_hg002_5x5x_closeout_take101_fullcov_ledger.md`

## Objective

Preserve every live-proven DayOA repair from Take101 in an immutable release; build a technical two-sample report inside the Take101 root; export the entire root to a new empty S3 prefix with verified delete-on-success semantics; create a seven-day presigned final-MultiQC share link; update the DYEC command catalog to match the accepted Bjuice HIOMR2 kitchen-sink, mega, and Inflection analytical-package command; then create Take222 at the proven DayOA release for HG003, HG004, NA19235, and NA20775 using all accepted full-coverage Illumina lanes and Bjuice ONT elapsed hours `[0,25)`, pass the exact `-j 444 -p -T 1 -k --rerun-triggers mtime -n` preflight, run the identical live command without `-n`, and monitor one controller every 20 minutes.

## Gate 0 inventory baseline

- DYEC checkout: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch `codex/hg002-13.4.0-run-ledger`, HEAD `2c6e5e1d5d8be120e6ece3d4440de025822819c5`. Existing unrelated modified configuration/validation/test files and a large pre-existing untracked documentation set are excluded; only this ledger and later explicitly named command-catalog/report/export artifacts are in scope.
- Local DayOA checkout: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`, branch `codex/feat-hiomr2-sentieon-cli-fidelity-13.0.72`, HEAD `c0cd125d9bf42cbb64f8c00908dd0bc3c9866716`, two commits ahead of its upstream plus one untracked market-comparison document. It will not be switched or cleaned. Reconciliation will use fetched immutable refs and an isolated worktree.
- Headnode Take101 DayOA checkout: branch `codex/13.4.2-take101-multisample-nicu-warning`, HEAD `53b43186f0b840a756c9151df1ff1b830033c139`; pushed annotated tag `13.4.2` peels to the same commit. Local DayOA had not fetched that tag at Gate 0.
- Runtime boundary: no DayOA controller process, empty `squeue -u ubuntu`, Take101 write lock absent, and the existing Take101 tmux remains one window. No Slurm or workflow intervention is authorized by this inventory.
- Take101 size/capacity: `577,873,233,408` allocated bytes, `8,214` regular files, `1,303` directories. FSx has approximately `5.7T` free (`50%` used) and `23,544,871` free inodes.
- Terminal artifacts present: final MultiQC HTML `12,196,815` bytes; MultiQC JSON `18,523,045` bytes; benchmark summary `132,798` bytes; DayOA evidence manifest `584,931` bytes; HG002 and NA23687 Inflection manifests `26,292` and `26,517` bytes.
- Export preflight: destination prefix `s3://lsmc-ssf-sequencing-data/derived/preval-hiomr2/take101/` has `KeyCount=0`. FSx `fs-0ce0851156199113a` has no DRA overlapping `/analysis_results/preval-hiomr2/take101/`.
- Destructive boundary: `dyec export --delete-data-in-file-system` will, only after a successful FSx export task, detach its temporary DRA with `DeleteDataInFileSystem=true` and remove the entire source tree `/fsx/analysis_results/preval-hiomr2/take101` from FSx. The user request is first approval only; exact live invocation remains blocked until John gives a separate explicit confirmation after seeing this scope.
- Report mode: technical-audience portable HTML, modeled on `docs/plans/20260802T221250Z_hg002_5x5x_closeout_take101_artifacts/HG002_5x5x_HIOMR2_13.4.1_VALIDATION_REPORT.artifact.json`, with one canonical artifact JSON, packaged HTML, source receipts, quantitative visuals, and final-context verification.

## Control ledger

| ID | Area / repo | Requirement | Status | Category | Approval gate | Evidence | Root cause / terminal note |
|---|---|---|---|---|---|---|---|
| REL-001 | DayOA local + headnode | Reconcile every Take101 source repair, prove the pushed branch and annotated tag contain the exact live-proven tree, and make the release available in an isolated local worktree without touching unrelated local work | SUCCESS | feature_implementation | Release gate | Annotated `13.4.2` and branch both peel to `53b43186...`; local/headnode tree `307b1047...`; seven per-file SHA-256 values match; 49 focused tests and Ruff pass | No missing source delta; `13.4.2` is the correct new version, so no fabricated `13.4.3` was cut |
| REP-001 | Take101 report | Inventory variant treatment, GIAB/Truvari, SMN1/2, coverage, fragment, benchmark, package, provenance, and limitation evidence for both samples | SUCCESS | feature_implementation | Report evidence gate | Reviewed TSVs enumerate 4 coverage rows, 16 treatment rows, 9 GIAB rows, 4 SMN caller rows, 15 Truvari/applicability rows, 3 live repairs, 2 packages, and exact primary artifact hashes | Published metrics are separated from raw diagnostic summaries and not-applicable lanes |
| REP-002 | Take101 report | Build one verified technical HTML report and supporting receipts inside the Take101 export root, including important final S3 object URIs | SUCCESS | feature_implementation | Report evidence gate | Portable delivery passed validation/package/browser verification: 26 blocks, 3 charts, 9 tables, source dialog, and 1440/390 px; all 15 installed files hash-match local | Root-level report HTML SHA-256 `7786f95b...`; artifact JSON `bb36f5ad...`; write lock released |
| EXP-001 | DYEC / AWS | Prove exact source size/count, destination emptiness, no overlapping DRA, and supported full-root export command | SUCCESS | legitimate_safety_handling | Export preflight | `577,873,233,408` bytes; `8,214` files; empty prefix; no overlapping DRA | Preflight complete without mutation |
| EXP-002 | DYEC / AWS | Obtain separate explicit approval for delete-on-success of the entire Take101 FSx root | BLOCKED | legitimate_safety_handling | Destructive second approval | Exact scope recorded above | Requires a second explicit John confirmation after report installation and final pre-delete inventory |
| EXP-003 | DYEC / AWS | Run supported full-root DRA export with `DeleteDataInFileSystem=true`, reconcile S3 objects/bytes/important hashes, and prove source deletion only after export success | OPEN | feature_implementation | Destructive second approval | Destination reserved as `s3://lsmc-ssf-sequencing-data/derived/preval-hiomr2/take101/` | Blocked behind REP-002 and EXP-002 |
| SHARE-001 | AWS / report | Generate and verify a seven-day presigned final-MultiQC HTTPS URL after the object exists in S3; record important S3 URIs in report and ledger | OPEN | feature_implementation | Post-export | Final MultiQC export-relative path known | Pending successful export |
| CAT-001 | DYEC | Update the Bjuice/HIOMR2 command-catalog entry to the exact eight-target Take101 command shape and add focused contract tests | OPEN | feature_implementation | Catalog contract gate | Current catalog references identified in `config/command_catalog.yaml` and `tests/test_dayoa12_manifest_contract.py` | Pending exact current-vs-requested diff |
| T222-001 | DYEC manifests | Generate and validate a provider-neutral four-sample manifest set for HG003, HG004, NA19235, and NA20775 using accepted full Illumina coverage plus ONT `[0,25)` | OPEN | feature_implementation | Input evidence gate | Bjuice generator and prior Take21/Take101 manifests identified | Pending exact source/hash selection |
| T222-002 | Headnode DayOA | Create one fresh `take222` root and one one-pane interactive Ubuntu tmux with `day-clone -t <proven-release> -d take222`; initialize with separate `source dyoainit` and `dy-a slurm hg38` commands | OPEN | feature_implementation | Post-export gate | Planned tmux `dayoa_take222_hg003_hg004_smn12_20260803` | Must not start until EXP-003 proves source deletion and SHARE-001 closes |
| T222-003 | Headnode DayOA | Run exact eight-target dry run with `-j 444 -p -T 1 -k --rerun-triggers mtime -n`; only if clean run identical live command without `-n` | OPEN | feature_implementation | Live workflow gate | Required command flags fixed by user | Pending T222-001/002 and catalog parity |
| T222-004 | Monitoring | Create exactly one 20-minute same-thread monitor after the real controller exists; inspect controller/jobs/logs read-only; alert locally on terminal defects; use mtime dry run before any code-fix live retry | OPEN | legitimate_safety_handling | Live controller gate | Alert prefix and two-sentence explanation contract recorded | Pending accepted live controller; no automation exists yet |

## Exact planned export command after second approval

```bash
source ./activate
dyec export \
  --cluster preval-hiomr2 \
  --source-path /fsx/analysis_results/preval-hiomr2/take101 \
  --destination-s3-uri s3://lsmc-ssf-sequencing-data/derived/preval-hiomr2/take101/ \
  --profile lsmc \
  --region us-west-2 \
  --output-dir docs/plans/20260803T082714Z_take101_export_take222_fullcov_export \
  --wait \
  --timeout-seconds 14400 \
  --delete-data-in-file-system
```

This command is intentionally not authorized for live execution until EXP-002 is unblocked by a second explicit user confirmation.

## DayOA 13.4.2 reconciliation recorded 2026-08-03

- Pushed branch: `codex/13.4.2-take101-multisample-nicu-warning`.
- Release commit: `53b43186f0b840a756c9151df1ff1b830033c139`.
- Annotated non-v tag: `13.4.2`; tag object `796098d9ba27311e614e749154bc5e448c872c61`; tag and branch both peel to the release commit.
- Local isolated worktree: `/Users/jmajor/.codex/worktrees/dayoa-13.4.2-take222`, detached at exact tag without switching or cleaning the unrelated dirty DayOA checkout.
- Local and headnode Git tree: `307b10472eb25b65e040a75371cf2429e5ae9429`.
- Release delta from `13.4.1`: exactly seven tracked files, 369 insertions, and 34 deletions. Every changed file has the same SHA-256 locally and on the headnode; `git diff --check` is clean.
- Focused local validation: `49 passed in 0.44s`; functional Ruff checks passed.
- The existing pushed `13.4.2` already contains every live-proven Take101 repair. Creating a new patch version without a further source change would have invented a release and was not done.

## Take101 technical report recorded 2026-08-03T09:06:39Z

- Durable local bundle: `docs/plans/20260803T082714Z_take101_export_take222_report/`.
- Installed export-root files: 15 root-level files under `/fsx/analysis_results/preval-hiomr2/take101`, including the canonical artifact, self-contained HTML, reviewed audit TSVs, report generator, README, and delivery receipt.
- Canonical artifact: `TAKE101_HG002_NA23687_FULLCOV_HIOMR2_13.4.2_VALIDATION_REPORT.artifact.json`, 72,814 bytes, SHA-256 `bb36f5ad8dea5f95b765e71800223f621b7c011cd2c003da4b84eab79e796354`.
- Portable HTML: `TAKE101_HG002_NA23687_FULLCOV_HIOMR2_13.4.2_VALIDATION_REPORT.html`, 800,405 bytes, SHA-256 `7786f95b81dfd51d35cef7cd2a0426b575bfcdafeb83e5fdd6a458a93cd16eb3`.
- Verification receipt: validation, packaging, and browser verification passed with 26 blocks, three native charts, nine tables, keyboard source-dialog interaction, and 1440/390 px viewports.
- Evidence coverage: final MultiQC coverage/fragment statistics; both package treatment-tag maps; HG002 hard-VCF `ROI=giabHC` F-scores; both samples' Sentieon regional and SMNCopyNumberCaller outputs; every standard, alias, alignment-comparison, copy-state, NICU warning, and not-applicable benchmark lane; exact release/repair provenance; package closure; primary hashes; and important stable S3 URIs.
- Installation used a normal analysis-root write visit, lock, and guarded copy. All 15 post-install hashes match local source; the write lock is absent afterward.
- The seven-day MultiQC URL is intentionally not embedded in the durable artifact because it is credential-bearing and ephemeral. It will be generated and verified only after the S3 object exists, then retained in the post-export share receipt.

## Alert and recovery contract

- Lost-node recovery remains Snakemake's `-T 1` responsibility. Do not cancel, requeue, hold, release, drain, resume, or otherwise administer Slurm.
- Diagnose code defects only at a terminal controller boundary with normal lock release.
- For a proven terminal code defect, run local `say` beginning `MAJOR, ALERT! Please know there were terminal issues` followed by exactly two explanatory sentences.
- Apply only the smallest proven source repair under the analysis-root lock, run focused tests and the exact `--rerun-triggers mtime -n` command, and remove only `-n` for the live retry.

## Final acceptance

- All rows terminal: no `OPEN`, `IN_PROGRESS`, or `ATTEMPTING_BUGFIX` rows.
- Objective complete: Take101 report/export/delete/share reconciled; DayOA release immutable; DYEC catalog updated and validated; Take222 dry run clean, live controller accepted, and one monitor active until terminal completion.
