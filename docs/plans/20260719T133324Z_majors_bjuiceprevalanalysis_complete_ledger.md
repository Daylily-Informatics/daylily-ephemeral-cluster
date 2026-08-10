# Majors Bjuice Prevalidation Complete HIOMRS Ledger

Created: `2026-07-19T13:33:24Z`

## Objective

Create a fresh `bjuiceprevalanalysis-complete` HIOMRS kitchen-sink analysis on
`majors-cluster` with a durable, validated all-20 lineage package. Preserve the
persisted specimen, sample, and two platform-specific library EUIDs for every
identity, while retaining the convenient `HG*` or `NA*` name in human-facing
IDs/comments. The user subsequently narrowed this execution to HG003 only and
requested the half-open ONT elapsed-hour window `[0,4)` and ILMN downsampling
fraction `0.50`. Validate the exact
`-j 456 -p -T 1 -k -n` HG003 plan with global config
`use_fq_data_starting_hrs=0` and `use_fq_data_up_to_hrs=4`, launch the identical
command without `-n` only if green, and monitor the live controller every seven
minutes through the supported CLI surfaces.

## Gate 0 Baseline

- AWS profile `lsmc`, region `us-west-2`, cluster `majors-cluster`, remote user `ubuntu`.
- Analysis id: `bjuiceprevalanalysis-complete`.
- Explicit DayOA ref: `13.0.10`, the latest tag already authenticated and verified on this headnode in the immediately preceding campaign; it will be revalidated before cloning.
- Source identity contract: committed matrix `docs/evidence/betelgeuse_multiplatform_global_dag/bjuice_preval_library_run_matrix.tsv` from `/Users/jmajor/projects/mega_dayhoff/repos_work/daylily-ursa-10.0.1-owy-seqrunqc`, commit `dbd60409fc4cb27e67afa8a549c9ae2597088bab`.
- The live committed TSV SHA-256 is `3da41aca4f567a560981b2029e873cf5dfc7624ebf8bcf6a1378d5514107d92f`. Its companion Markdown records stale SHA-256 `e7d1ad80...`; the actual committed TSV rows, not the stale prose checksum, control identity generation.
- Matrix scope is 21 receipt-backed inputs including NTC. This request selects exactly the 20 biological `HG*`/`NA*` identities and excludes NTC. Each selected identity retains one ILMN and one ONT library EUID. Because each ONT library has three persisted sequencing-run EUIDs, the exact six-manifest topology is 20 specimens, 20 samples, 40 libraries, 80 sequencing inputs (20 ILMN plus 60 ONT), 20 analysis units, and 80 analysis-unit joins.
- First ten biological input rows come from the committed Dayhoff snapshots: `HG001`-`HG007`, `NA19235`, `NA20775`, `NA23687`. Second ten come from `/Users/jmajor/projects/lsmc/remaining`: `NA05067`, `NA10798`, `NA13189`, `NA14732`, `NA14733`, `NA15603`, `NA15848`, `NA15849`, `NA20027`, `NA20230`.
- Required input roots from the source manifests are `/fsx/run_dir_mounts/20260618_LH01106_0011_A23MFMCLT3/` and `/fsx/run_dir_mounts/pca100-2026/`.
- `dyec mounts list --cluster majors-cluster` returned `No mounts found`; the underlying FSx `fs-0c3980010a92252b1` currently has only reference DRA `dra-06a58d32ab234e73d` at `/references/`.
- Three unrelated DayOA controllers are live and remain out of scope. Slurm job `251` was separately cancelled before this request.
- Standalone keepalive job `752` was submitted with exact comment `RnD`, partition `i8`, and command `sleep 6000`, but later failed after `00:09:32` with signal-15 exit `0:15` and no Slurm reason. Replacement job `886` was submitted under the same exact contract; initial state was `CONFIGURING` on `i8-dy-price8-2`.
- Fresh checkout root is `/fsx/analysis_results/majors-cluster/bjuiceprevalanalysis-complete/daylily-omics-analysis`, detached at tag `13.0.10`, commit `27b9f24f9d7ce10322efa9125c7443e56b4380ac`. The root has a write lock owned by `codex-root-majors-bjuicepreval-complete-20260719`.
- Generated six-manifest evidence is under `docs/plans/20260719T133324Z_majors_bjuiceprevalanalysis_complete_artifacts/manifests/`. Generation proves 20/20/40/80/20/80 rows, literal NTC absence from every runtime TSV, and 9,078 globally unique input paths.
- Required `SAMPLEUSE` values come from the exact legacy unit rows: seven `posControl` and thirteen `sample`. Required `ORDER_TYPE` is `RESEARCH` for all 20, read from the owning reviewed planner bundle `manifest_assembly/review_bundle_v1/reviewed_planner_bundle.json`; the generator asserts exact sample-set equality.
- Headnode `dayoa manifests validate --manifest-dir config/` is green: deterministic ordering and foreign keys are valid; identifiers were neither created nor rewritten; the receipt reports 20/20/40/80/20/80 rows. Final manifest SHA-256 values are preserved in `generation_summary.json`.
- Exact sorted path evidence is `manifests/input_paths.txt`, SHA-256 `f138db70489e1183b4d548a10d397605fb9d422d36e6ccaf419d2604c0a0c72c`, with 9,078 lines. ONT DRA `dra-04ddc72645adc61a4` served all 8,758 expected ONT paths with zero missing or empty. ILMN DRA `dra-0793ae787f061be4d` also reached `AVAILABLE`; the effective HG003 proof checked 16 ILMN plus 24 selected ONT paths with zero missing or empty.
- Scope amendment: no workflow had launched when the user narrowed the live run to HG003, requested `ONT[0,4)`, and then requested ILMN downsampling `0.50`. The exact runtime subset under `artifacts/runtime_hg003_ont_0_4/` is green under the DayOA validator: 1 specimen, 1 sample, 2 libraries, 4 sequencing inputs (1 ILMN plus 3 persisted ONT runs), 1 analysis unit, and 4 joins. The analysis unit has exact `SUBSAMPLE_PCT=0.50` and blank `ONT_SUBSAMPLE_PCT`. DayOA's global half-open filter selects 24 ONT FASTQs, 8 per run EUID, plus 16 ILMN FASTQs: 40 effective files total. No other sample is present in the runtime manifests.
- The first dry attempt failed before submission because the persisted source run names contain `_`, while DayOA requires `SQ/RU/EX/LANE` to exclude `.` and `_`. The runtime builder now applies an explicit four-entry HG003 run-alias map using hyphens. Every original run name remains literally recorded in `SEQUENCING_INPUT_COMMENT`; the persisted run EUID and physical input paths are unchanged. The regenerated 1/1/2/4/1/4 validator receipt is green with identifiers neither created nor rewritten.
- The repeated exact dry run planned 178 jobs and returned `0`; it again reported 24/438 ONT FASTQs retained for elapsed hours `[0,4)`. The identical live command, with only `-n` removed, submitted initial jobs `887` through `891` after the green gate. A seven-minute thread heartbeat named `Monitor majors HG003 HIOMRS` (`monitor-majors-hg003-hiomrs`) now owns recurring supported-CLI monitoring and terminal reporting.
- One-sample rulegraph evidence was generated without taking over the live controller lock. An isolated `/fsx/analysis_results/majors-cluster/bjuice-rulegraph-20260719` root used the same DayOA `13.0.10` commit, byte-identical six manifests, exact targets/config, and `dy-r --produce-rulegraph true -n`. The producer returned `0`, planned 178 jobs without submitting any, and rendered a 91-rule/257-edge PNG. Local artifact `artifacts/newrgd.png` and requested copy `~/Downloads/newrgd.png` both have SHA-256 `87cd58f19420ab9dba24159c95e0d890f4d90f53e8f83a243b89f956d12202df` and size 1,702,530 bytes.
- `source dyoainit` binds `dy-a` to this root's `bin/day_activate`, `dy-r` to this root's `bin/day_run`, and Python imports to this root's package. The shared editable checkout remains at older candidate `1818223c...`, but the live command path is the pinned root `27b9f24...`; the validator module blob is identical between them.
- Local DYEC repo is `main`, 41 commits behind `origin/main`, with six pre-existing untracked ledgers. Existing user changes are preserved.
- No raw Snakemake is permitted. Required execution is one dedicated `ubuntu` `bash -il` tmux pane with separate `source dyoainit`, `dy-a slurm hg38`, and `dy-r` commands.

## Control Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| INV-001 | Identity/input baseline | Freeze exactly 20 biological identities, both library EUIDs, source paths, explicit tag, and concurrent-controller boundary | SUCCESS | active_product_contract | Gate 0 | orchestrator | Matrix SHA `3da41aca...`, source repo commit `dbd60409...`, 20 names frozen, NTC excluded |  | Baseline is exact and terminal |
| MNT-001 | Read-only DRAs | Create and verify the exact ILMN and ONT run-directory mounts with waits longer than 40 minutes | SUCCESS | feature_implementation | Gate 1 | orchestrator | ILMN `dra-0793ae787f061be4d` and ONT `dra-04ddc72645adc61a4` are both CLI-verified `AVAILABLE` at the exact headnode paths |  | Both read-only mounts are terminal and green |
| ROOT-001 | Fresh analysis | Create `day-clone -t 13.0.10 -d bjuiceprevalanalysis-complete`, verify exact tag, visit, and lock | SUCCESS | feature_implementation | Gate 2 | orchestrator | Tag `13.0.10`; commit `27b9f24f9d7ce10322efa9125c7443e56b4380ac`; lock owner recorded above |  | Fresh pinned root is ready |
| MAN-001 | Six manifests | Generate, checksum, transfer, and validate 20/20/40/80/20/80 rows with exact EUID/name lineage | SUCCESS | active_product_contract | Gate 2 | orchestrator | S3 transfer MD5 verified; exact headnode SHA-256 receipt and green invariants recorded above |  | Six-manifest contract is terminal and green |
| RUN-001 | Runtime scope | Materialize and validate HG003-only runtime manifests with ONT `[0,4)` and ILMN `SUBSAMPLE_PCT=0.50` | SUCCESS | active_product_contract | Gate 2 | orchestrator | Green 1/1/2/4/1/4 receipt; 24 ONT plus 16 ILMN effective paths; blank `ONT_SUBSAMPLE_PCT`; no other sample present |  | Runtime scope is exact and terminal |
| PATH-001 | Input validation | Prove every effective HG003 ILMN/ONT path exists and is nonempty through the exact DRA roots | SUCCESS | contract_test | Gate 3 | orchestrator | `EFFECTIVE_PATH_TOTAL=40 EFFECTIVE_MISSING_OR_EMPTY=0`; 16 ILMN plus 24 ONT `[0,4)` paths |  | Runtime input proof is terminal and green |
| DRY-001 | DAG gate | Run the exact HIOMRS kitchen-sink dry run with `-j 456 -p -T 1 -k -n`; require rc 0 and inspect plan | SUCCESS | contract_test | Gate 4 | orchestrator | 178 planned jobs; ONT 24/438 for `[0,4)`; `RETURN CODE: 0`; no jobs submitted by dry run | Source `RUNID` underscores failed the first preflight; explicit legal aliases retained exact source provenance | Repeated exact dry gate is terminal and green |
| LIVE-001 | Execution | Launch the identical command without `-n` only after a green dry run | IN_PROGRESS | feature_implementation | Gate 5 | orchestrator | Workflow jobs `887`-`891` submitted; `sacct` reported `887` and `888` `RUNNING`; keepalive `886` remains running |  | Controller is live; completion pending |
| MON-001 | Monitoring | Record supported CLI controller/lock/queue/accounting/log evidence every seven minutes | IN_PROGRESS | contract_test | Gate 5 | orchestrator | Initial tmux, `squeue`, and `sacct` snapshots captured; seven-minute heartbeat `monitor-majors-hg003-hiomrs` active |  | Recurring monitoring active |

## Final Report

All rows terminal: `no`

Objective complete: `no`
