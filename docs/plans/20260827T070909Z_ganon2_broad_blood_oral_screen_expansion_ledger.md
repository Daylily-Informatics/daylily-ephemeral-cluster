# Ganon2 Broad Blood/Oral Screen Expansion Ledger

Created: `2026-08-27T07:09:09Z`

Objective: build and persist one immutable Ganon 2.4.2 blood/oral reference
bundle, implement one hierarchical classification per primary SR/LR alignment,
surface reconciled read outcomes and top hits in MultiQC, release DayOA, and
obtain an attributable dry/live pilot with measured recurring runtime and cost.

## Fixed Scope And Safety Contract

- Cluster: `bjuiceval-19024`; profile `lsmc`; region `us-west-2`.
- DYEC: public CLI `19.0.30` from
  `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-19-0-30-maxcount`.
- DayOA release base: annotated tag `16.0.10`, commit
  `13daa804b7e32625844d849b39541b6437171e09`. The implementation release is
  annotated tag `16.0.11`, commit
  `878749f1ea9d9f0d6585c02a3415f07724bd97ff`.
- Bundle ID: `ganon2_blood_oral_ref_20260827_v1`.
- FSx staging root:
  `/fsx/analysis_results/bjuiceval-19024/ganon2_blood_oral_ref_20260827_v1`.
- Immutable S3 destination:
  `s3://lsmc-dayoa-references-usw2/runtime_assets/tool_specific_resources/ganon2/ganon2_blood_oral_ref_20260827_v1/`.
- Stable reference path:
  `/fsx/references/runtime_assets/tool_specific_resources/ganon2/ganon2_blood_oral_ref_20260827_v1/`.
- Database export is no-delete. No FSx or S3 deletion is authorized.
- Database build is an accepted, potentially large one-time expense. Recurring
  classifier runtime and cost are measured and tuned after end-to-end results;
  neither is an analytical failure gate.
- All five components use Ganon `k=27`, `w=51`, and HIBF `max_fp=0.001`.
  Relative to the Ganon default `19/31`, the larger window samples fewer
  minimizers to reduce recurring database memory, I/O, and query time, while
  the moderately larger k-mer retains discriminative power for this
  informational high-quality SR/LR screen. The pilot, not assumption, will
  quantify the resulting runtime and sensitivity tradeoff.
- No Slack notification is in scope.

## Gate 0 Inventory Freeze

- Controlling ledger: this file.
- Artifact directory:
  `docs/plans/20260827T070909Z_ganon2_broad_blood_oral_screen_expansion_artifacts/`.
- DYEC repo baseline: branch `codex/bjuiceval-19024-dra-mounts`, commit
  `79190f52fb4f4e96be7757a7b35af88854766945`; existing modified and untracked
  files belong to other work and will be preserved.
- DayOA ordinary checkout baseline: branch `codex/solo-kitchensink-sex-contract`,
  commit `1b5191fe9260a230e0b49dbe46b5ed6e8080a4e8`, ahead by two with unrelated
  modified files in HIOMR2/TIDDIT tests and rules plus `tmp/`; implementation
  will use a separate clean worktree from `16.0.10`.
- Live cluster at `2026-08-27T07:08:07Z`: `UPDATE_COMPLETE`, compute fleet
  `RUNNING`, zero authoritative controllers, zero Slurm jobs.
- Build lane: partition `i192nvme` exposes `mem192nvme`; requested build shape
  is one node, 192 CPUs, 700 GB, exclusive, 24 hours, comment `RnD`.
- Existing reference baseline contains only
  `dayoa_qc_refseq_abfv_complete_top1_20260528` (`.hibf` 23,645,453,479 bytes,
  `.tax` 964,706 bytes, manifest 692 bytes). It does not satisfy the expanded
  scope.
- FSx baseline: 14 TB total, 8.3 TB used, 5.2 TB available. `/scratch` is
  compute-node-local and is intentionally absent on the headnode.
- Required instructions read: repository `AGENTS.md`, DayOA `AGENTS.md`,
  `docs/agent_cli_guide.md`, `AGENTS-HOW-TO-RUN-DAYOA.md`, and
  `plan-ledger-workflow.md`.
- Clean DayOA implementation worktree:
  `/Users/jmajor/projects/lsmc/.codex-worktrees/dayoa-16-0-11-ganon2`, branch
  `codex/ganon2-broad-blood-oral`, clean base commit
  `13daa804b7e32625844d849b39541b6437171e09`.

## Database Build Submission

- A remote write visit and exact-root write lock were recorded for the fresh
  staging root before build submission. The root may contain only its
  `.dayoa_agent` control directory until the completed scratch build stages
  the release payload.
- The initial literal plan command was rejected before creating a job because
  this cluster disables Slurm memory placement and requires removing
  `--mem=700G`. Read-only `sinfo` showed the selected `mem192nvme` shape has
  192 CPUs and 747,110 MB configured memory. No compute allocation or partial
  build resulted from the rejected command.
- This is a cluster-wide CPU-only scheduling contract, not a Ganon-specific
  exception: explicit `--mem`, `--mem-per-cpu`, `--mem-per-gpu`, and
  `--mem-per-tres` requests are rejected. `mem192nvme` is the selected
  ParallelCluster compute-resource constraint, not a Slurm memory request.
- The corrected command removed only the unsupported `--mem=700G` option and
  retained the explicit `i192nvme`, `mem192nvme`, one-node, 192-CPU,
  exclusive, 24-hour, and `RnD` contract. Slurm accepted job `16368` at
  `2026-08-27T07:26:11Z`; first state was `CONFIGURING` on
  `i192nvme-dy-mem192nvme-1`.
- Admission reported cluster budget `$3,518.689 / $3,900` (`90.22%`) and an
  active `RnD` cost center. This is admission evidence, not final task cost.
- Corrected public upload relay (retained, no deletion authorized):
  `s3://lsmc-ssf-sequencing-data/codex-relay/ganon2_blood_oral_ref_20260827_v1-r2/dyec-headnode-transfer/bjuiceval-19024/20260827T072327Z-10fb858464b2/`.
- Slurm job `16368` terminated `FAILED`, exit `1:0`, after two seconds. The
  preserved stderr is exactly `ERROR: food watchlist is missing beside build
  script`. The uploaded watchlists were present, but Slurm executed its copied
  batch script from the spool directory, so deriving assets from
  `BASH_SOURCE[0]` was incorrect. No database command ran and the locked FSx
  root remained empty outside `.dayoa_agent`.
- The corrected build uses authoritative `SLURM_SUBMIT_DIR` for its uploaded
  assets and emits generated TSVs with real tab characters. `bash -n` and
  `git diff --check` returned zero at `2026-08-27T07:47:49Z`. A same-shape
  replacement is a staging correction, not a resource escalation.
- Public DYEC upload staged the corrected build, both watchlists, and both
  candidate `lsmc-bio` documents through retained relay prefix
  `s3://lsmc-ssf-sequencing-data/codex-relay/ganon2_blood_oral_ref_20260827_v1-r3/dyec-headnode-transfer/bjuiceval-19024/20260827T074822Z-f7cb220f5041/`.
  The existing interactive `ubuntu` tmux pane admitted same-shape replacement
  job `16369`; first state was `CONFIGURING` on
  `i192nvme-dy-mem192nvme-1`.
- Job `16369` terminated `FAILED`, exit `1:0`, after nine seconds at the first
  host/QC `ganon build-custom`. The pinned `ganon` executable was invoked by
  absolute path, but its adjacent `genome_updater.sh`,
  `ganon-get-seq-info.sh`, `ganon-build`, and `raptor` executables were not on
  `PATH`. Public headnode inspection confirmed all five executables exist and
  are executable in the pinned Ganon 2.4.2 environment; the narrow correction
  exports that environment's `bin` directory on `PATH`. No index build ran and
  the locked FSx root again remained empty outside `.dayoa_agent`.
- Public upload relay revision `r4` staged the path-corrected script and exact
  candidate-resource documents at
  `s3://lsmc-ssf-sequencing-data/codex-relay/ganon2_blood_oral_ref_20260827_v1-r4/dyec-headnode-transfer/bjuiceval-19024/20260827T075753Z-82fdd14bb72a/`.
  The same persistent `ubuntu` tmux pane submitted job `16370` with the same
  non-escalated shape. At `2026-08-27T08:01:53Z` it was `RUNNING` on
  `i192nvme-dy-mem192nvme-1`, exit evidence remained `0:0`, host/QC had built
  successfully in 109.69 seconds, and the RefSeq ABFV species-selection
  download was progressing. This is an active build, not completion evidence.
- The first RefSeq ABFV download pass reached all `94,480` selected assemblies
  but reported only `4,046` successful downloads and `90,434` failures. The
  bundled `genome_updater` then began its built-in retry `#2`; job `16370`
  remains active and has not entered index construction for this component.
  This is a measured upstream-download/concurrency warning, not a valid partial
  bundle. No Slurm or job intervention was performed.
- Source inspection established that `genome_updater` defaults to conditional
  exit `-n 0`, which accepts unresolved files, and to five retry batches. The
  corrected build contract now uses `12` download threads, `10` bounded retry
  batches, `-n 1`, and an explicit non-empty `*_url_failed.txt` rejection after
  RefSeq ABFV, broad-euk, and GenBank-gap acquisition. It retains all `192`
  threads for index construction. `bash -n` and scoped `git diff --check`
  returned zero. This correction is prepared only for a future fresh build;
  it does not alter or cancel active job `16370`.
- At the `2026-08-27T08:28Z` read-only snapshot, job `16370` remained
  `RUNNING` with exit evidence `0:0`. Retry `#2` increased successful RefSeq
  ABFV downloads from `4,046` to only `4,055`, leaving `90,425`; retry `#3`
  was then 20% through that residual set. The active script remains bounded by
  its original five retries, but this attempt is not acceptable for export or
  distribution unless it ultimately resolves every selected assembly. No
  Slurm intervention was performed.
- At `2026-08-27T08:36Z`, retry `#3` had recovered only ten more assemblies:
  `4,065 / 94,480` were present and `90,415` remained as retry `#4` began.
  This repeatable near-zero recovery establishes that continuing this attempt
  into index construction would create a partial ABFV component, not the
  approved complete bundle. Stopping Slurm job `16370` remains a separately
  gated scheduler action; no cancellation was inferred from this evidence.
- At `2026-08-27T08:48:46Z`, public `dyec headnode jobs` still reported job
  `16370` `RUNNING` with 192 CPUs on `i192nvme-dy-mem192nvme-1`; this remains
  active-build evidence, not a completed database or export receipt. A
  read-only preflight using the pinned public DYEC `19.0.30` rejected the
  intended immutable tool-resource destination before querying or mutating S3
  because the generic export contract requires a suffix of
  `bjuiceval-19024/ganon2_blood_oral_ref_20260827_v1/`. No export task or DRA
  was created. The missing public route for this approved
  `runtime_assets/tool_specific_resources/ganon2/...` destination is cataloged
  below and must be resolved without a raw AWS fallback before DB-005.

## DayOA Focused Validation

- The implementation uses one structured ordered database list, includes only
  primary SR and LR lanes, excludes derived RSR, and separates candidate-read
  preparation from Ganon classification as distinct Snakemake rules.
- Per-AU/modality outputs include one Ganon tree/report, reconciled read
  outcomes, top-ten non-host hits with hierarchy/taxonomy/modality, and Sankey
  edges. Final MultiQC stages the native Ganon inputs plus cohort outcome and
  top-hit tables.
- The bundle compatibility gate checks the small component manifest for exact
  members, taxonomy/hierarchy metadata, Ganon `2.4.2`, and `k=27`, `w=51`; it
  does not hash database payloads or introduce dependency authority parallel
  to Snakemake.
- The broader focused test command passed `138` tests in `2.07` seconds, and
  `git diff --check` returned zero. Receipt:
  `ganon2_broad_blood_oral_screen_expansion_artifacts/dayoa_focused_tests_20260827T0802Z.txt`.
- Commit `878749f1ea9d9f0d6585c02a3415f07724bd97ff` was pushed on branch
  `codex/ganon2-broad-blood-oral`, then annotated non-v tag `16.0.11`
  (`Release 16.0.11`) was pushed without moving an existing tag. Local tag
  type verification returned `tag` and dereferenced to that exact commit.
  Compact receipt:
  `ganon2_broad_blood_oral_screen_expansion_artifacts/dayoa_16.0.11_release_receipt.txt`.

## Candidate `lsmc-bio` Distribution Resource

- The bundle is documented as candidate resource format
  `lsmc-bio.ganon2-resource/1.0`; no external publication is authorized.
- `LSMC_BIO_RESOURCE.md` records intended research-screening use, exact
  components and taxonomy boundaries, Ganon `2.4.2` and `27/51`
  compatibility, immutable update policy, consumer paths, payload contract,
  known analytical limitations, and a release-time source rights/attribution
  review.
- `lsmc_bio_resource_manifest.tsv` provides a small machine-readable candidate
  resource identity. The distribution payload will include these documents
  after the build completes; the publication gate remains separate.

## Control Ledger

| ID | Area/Repo | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | cross-repo | Freeze repositories, release base, cluster, queue, FSx, partition, existing reference, and safety boundaries | SUCCESS | plan_amendment | Gate 0 | orchestrator | Gate 0 section above; public DYEC `19.0.30` cluster/controller/job inventory |  | Baseline is attributable and unrelated work is preserved. |
| DB-001 | build specification | Materialize exact versioned bundle/source/watchlist manifests and one sequential NVMe build script | SUCCESS | feature_implementation | Gate 1 | orchestrator | `ganon2_broad_blood_oral_screen_expansion_artifacts/ganon2_blood_oral_ref_20260827_v1.build.sh`; food and parasite watchlists; `bash -n` and `git diff --check` rc=0 |  | Five Ganon 2.4.2 components are pinned to compatible `k=27`, `w=51`, HIBF `max_fp=0.001`; raw FASTAs remain scratch-only. |
| DB-002 | cluster build | Submit one sequential `RnD` `i192nvme/mem192nvme` build at a time and preserve Slurm/runtime/cost evidence | IN_PROGRESS | feature_implementation | Gate 2 | orchestrator | Active job `16370`; host/QC completed successfully and RefSeq ABFV download was progressing at the latest read-only snapshot; r4 relay and single-pane tmux recorded above | Jobs `16368` and `16369` exposed narrow Slurm-spool asset and Ganon helper-PATH defects before meaningful build work. | One same-shape build is active; no resource escalation. |
| DB-003 | reference bundle | Produce compatible Ganon 2.4.2 host/QC, RefSeq ABFV, broad-euk, GenBank species-gap, and MGnify oral indexes | OPEN | feature_implementation | Gate 2 | orchestrator | Pending build outputs |  |  |
| DB-004 | validation | Validate component identity, Ganon compatibility, Homo sapiens exclusion outside host/QC, and targeted coverage watchlists | OPEN | contract_test | Gate 4 | orchestrator | Pending build validation receipt |  |  |
| DB-005 | FSx/S3 | Stage completed bundle to exact FSx root and complete public no-delete DYEC export to immutable S3 prefix | OPEN | feature_implementation | Gate 2 | orchestrator | Pending visit/lock/preflight/export receipts |  |  |
| DB-006 | shared references | Verify exact S3 objects and current-cluster visibility at stable `/fsx/references` path | OPEN | contract_test | Gate 5 | orchestrator | Pending object and headnode evidence |  |  |
| DYEC-001 | DYEC public CLI | Provide a supported no-delete export route for the approved immutable `runtime_assets/tool_specific_resources/ganon2/<bundle-id>/` destination | OPEN | bug_fix | Gate 2 | orchestrator | Pinned DYEC `19.0.30` read-only preflight at `2026-08-27T08:48:46Z` rejected the intended destination because generic analysis export requires an executing-entity/analysis-ID suffix; no mutation occurred | The generic analysis export destination validator does not admit the explicit shared tool-resource prefix required by this plan. | Do not use raw AWS or alter the destination silently; resolve through a reviewed public DYEC interface. |
| DAYOA-001 | DayOA | Create clean isolated worktree from annotated `16.0.10` and preserve unrelated ordinary-checkout changes | SUCCESS | feature_implementation | Gate 1 | orchestrator | Clean worktree and exact base commit recorded in Gate 0 |  | Ordinary dirty checkout remains untouched. |
| DAYOA-002 | DayOA rules/config | Implement structured ordered database configuration and explicit primary SR/LR modality selection excluding RSR | SUCCESS | feature_implementation | Gate 2 | orchestrator | Modified profile templates and `workflow/rules/unmapped_metagenomics.smk`; focused receipt above |  | Configuration is explicit and fail-closed. |
| DAYOA-003 | DayOA DAG | Split candidate preparation/counting from Ganon classification while leaving Snakemake as sole dependency authority | SUCCESS | feature_implementation | Gate 2 | orchestrator | `unmapped_metagenomics_ganon2_prepare` and `unmapped_metagenomics_ganon2_classify`; focused receipt above |  | No parallel rerun/provenance system or large-input hashing was added. |
| DAYOA-004 | reporting | Emit one consolidated report/tree, read outcomes, top-ten non-host hits, and Sankey-edge TSV per AU/modality | SUCCESS | feature_implementation | Gate 2 | orchestrator | `workflow/scripts/summarize_unmapped_ganon2.py`; focused receipt above |  | Zero-screenable and zero-hit cases are explicit. |
| DAYOA-005 | MultiQC | Stage and render cohort read-outcome and top-hit tables with explicit modality labels | SUCCESS | feature_implementation | Gate 2 | orchestrator | `workflow/rules/multiqc_final_wgs.smk`, MultiQC config, focused receipt above |  | Native Ganon inputs and custom cohort tables retain modality. |
| TEST-001 | DayOA | Pass focused config, hierarchy, modality, reconciliation, zero-hit, top-hit, staging, and MultiQC tests | SUCCESS | contract_test | Gate 4 | orchestrator | `dayoa_focused_tests_20260827T0802Z.txt`: 138 passed; `git diff --check` rc=0 |  | Actual `dy-r` dry/live validation remains under PILOT rows. |
| REL-001 | DayOA release | Commit, push, and publish the next clean annotated non-v release tag after rechecking remote tags | SUCCESS | active_product_contract | Gate 5 | orchestrator | Branch `codex/ganon2-broad-blood-oral`; commit `878749f1ea9d9f0d6585c02a3415f07724bd97ff`; annotated tag `16.0.11` pushed to origin |  | Release is immutable and ready for the later `dy-r` pilot. |
| PILOT-001 | live DayOA | Create one exact pilot capsule and pass attributable `dy-r` dry run with zero submissions | OPEN | contract_test | Gate 5 | orchestrator | Pending controller receipt |  |  |
| PILOT-002 | live DayOA | Remove only `-n`, reach attributable controller/DayOA/Snakemake `0/0/0`, and verify SR/LR outputs plus MultiQC inclusion | OPEN | feature_implementation | Gate 5 | orchestrator | Pending controller/artifact evidence |  |  |
| PERF-001 | benchmarking | Record SR/LR walltime, peak RSS, CPU, I/O, and task cost; recommend the next measured tuning step | OPEN | contract_test | Gate 5 | orchestrator | Pending benchmark rows |  |  |
| DIST-001 | distribution documentation | Document the bundle as a candidate `lsmc-bio` distributable research-screening resource with versions, taxonomy, source licenses/attribution, build/update contract, compatibility, limitations, and non-diagnostic scope | SUCCESS | active_product_contract | Gate 4 | orchestrator | `ganon2_broad_blood_oral_screen_expansion_artifacts/LSMC_BIO_RESOURCE.md`; `ganon2_broad_blood_oral_screen_expansion_artifacts/lsmc_bio_resource_manifest.tsv` |  | Candidate format `lsmc-bio.ganon2-resource/1.0` is documented; external publication remains separately gated and unauthorized. |

## Final Report

All rows terminal: `no`

Objective complete: `no`

Current status counts:

- SUCCESS: 10
- IN_PROGRESS: 1
- OPEN: 8
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0
