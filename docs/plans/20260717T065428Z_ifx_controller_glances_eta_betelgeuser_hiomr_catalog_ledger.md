# IFX Controller, Glances, ETA, and Betelgeuser HIOMR Catalog Ledger

Created: 2026-07-17T06:54:28Z

Objective: audit the live `ifx-p2-1000-120-0715` controller and every child Slurm job, capture bounded Glances profiles for the headnode and all allocated compute nodes, calculate an evidence-backed completion estimate, and add a production command-catalog copy named `betelgeuser_hiomr_prod_v1`.

## Control Ledger

Controlling plan: this ledger.

Ledger path: `docs/plans/20260717T065428Z_ifx_controller_glances_eta_betelgeuser_hiomr_catalog_ledger.md`

Gate 0 baseline:

- Owning repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch/commit: `main` at `fcdd4cb3e3b67475da47c95cc502ab95af3b1ba0`, one commit behind `origin/main` at inventory time.
- Existing user work preserved: modified Slurm-accounting CLI/resource/config/test files; untracked PrivateLink implementation/tests and July 16-17 ledgers. Catalog source, packaged catalog, and HIOMRS catalog test were clean at inventory time.
- Catalog source: `config/daylily_pipeline_command_catalog.yaml`; packaged mirror: `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`.
- Source command selected from current source: `hybrid_ilmn_ont_hiomrs_kitchensink`, because it matches the active controller's explicit HIOMRS kitchen-sink targets and the user's request followed directly from that live controller audit.
- Catalog-copy assumption: preserve the source command's runtime/input/compatibility/version contract exactly; create the exact requested command ID `betelgeuser_hiomr_prod_v1`; change `type` to `prod` and use a distinct display name/description so the duplicate is intentionally user-visible rather than an indistinguishable alias.
- Live boundary: monitoring only. No workflow, Slurm, controller, node, cluster, or AWS mutations are authorized by this task.
- Sweep evidence: `rg` found existing source entries `hybrid_ilmn_ont_hiomrs` and `hybrid_ilmn_ont_hiomrs_kitchensink` in both catalogs, with focused coverage in `tests/test_hiomrs_command_catalog.py` and `tests/test_repository_catalog.py`.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| MON-001 | live IFX | Audit controller and every child job; calculate ETA from queue, accounting, logs, outputs, and benchmarks. | SUCCESS | legitimate_safety_handling | Gate 0 | controller_jobs_eta | Read visit `06:54:51Z`; exact `07:00:30Z` snapshot found a live controller, 9 running cores, 43 configuring downstream jobs, 10 completed long-read SV jobs, and one newly completed core. Prior and current benchmark evidence supports a conditional `09:30–10:30Z` finish window. |  | No state changed; downside extends to `10:30–12:00Z` if another requeue/configuration/final aggregation failure occurs. |
| MON-002 | live IFX | Capture bounded headnode Glances profile and verify monitoring cleanup. | SUCCESS | legitimate_safety_handling | Gate 0 | headnode_glances | `06:58:57Z`: CPU 15.3%, load 0.84/0.55/0.40 on 8 cores, memory 12.3%, no swap, root 10.1%, FSx 34%; controller actively submitted VEP work. Audit listener/process and SSM cleanup verified. |  | Point-in-time sample; dedicated bounded XML-RPC workaround used because Glances 3.2.4.2 stdout crashes on list plugins. |
| MON-003 | live IFX | Capture bounded Glances profile for every allocated compute node and verify monitoring cleanup. | SUCCESS | legitimate_safety_handling | Gate 0 | compute_glances | Read visit `06:55:01Z`; complete Glances profiles captured for all 10 initially allocated nodes from `06:57:28–06:59:34Z`; job 2502 completed during the sample. Audit stdout processes were absent afterward. |  | Point-in-time samples; pre-existing Glances servers and 20 unrelated approximately one-day-old timeout/SSH wrappers on the headnode were not changed. |
| CAT-001 | DYEC catalog | Freeze the exact source command and clone contract for `betelgeuser_hiomr_prod_v1`. | SUCCESS | active_product_contract | Gate 3 | orchestrator | Current source inspected; clone boundary recorded in Gate 0. |  | Source is `hybrid_ilmn_ont_hiomrs_kitchensink`; no runtime behavior changes permitted. |
| CAT-002 | DYEC catalog | Add `betelgeuser_hiomr_prod_v1` to source and packaged catalogs with focused contract coverage. | SUCCESS | feature_implementation | Gate 3 | orchestrator | Added one entry to each catalog and an exact-copy regression test; only `command_id`, `type`, `display_name`, and `description` differ from `hybrid_ilmn_ont_hiomrs_kitchensink`. |  | Local source and packaged payload updated; not deployed or released. |
| CAT-003 | DYEC catalog | Validate catalog parsing, mirror equality, unique ID, copied fields, and focused repository contract. | SUCCESS | contract_test | Gate 5 | orchestrator | `cmp -s` passed; `pytest -q tests/test_hiomrs_command_catalog.py tests/test_repository_catalog.py` => 16 passed; `git diff --check` passed; one requested-ID occurrence per catalog. |  | Focused catalog contract is green. |
| FINAL-001 | cross-lane | Reconcile parallel evidence, ETA uncertainty, catalog validation, and terminal states. | SUCCESS | plan_amendment | Gate 5 | orchestrator | Parallel findings reconciled below; catalog validation green; live monitoring cleanup proven; every row terminal. |  | Objective complete without workflow, Slurm, node, cluster, or AWS mutation. |

## Reconciled Live Audit

Snapshot boundary: controller/job state at `2026-07-17T07:00:30Z`; Glances samples from `06:57:28Z` through `06:59:34Z`.

Controller:

- tmux `na20027_xyfix_18296a2_20260717`, one window and one pane.
- Alive chain: tmux bash PID `2143583` -> `bin/day_run` PID `2180267` -> `bin/day_run` PID `2180510` -> Snakemake PID `2180511`.
- Snakemake runtime `02:33:23`; progress `13 of 778 steps (2%)`. This ratio is not linear ETA evidence because the first core completion immediately released 43 downstream jobs.
- Owner `codex-na20027-live-fix-20260717`; human requester `jmajor`; write lock still owned by that expected agent.
- Checkout `dbf07664c0c4ae43e6d6da2c996bd19506e26f62`, described as `11.0.20-1-gdbf0766`.
- The controller was actively submitting `vep_chromosome_input` work during profiling, so it was not stalled.

Core job state:

| Job | Sample | State/current attempt | Elapsed | Active stage | Benchmark-derived remaining |
|---:|---|---|---:|---|---:|
| 2488 | NA20230 | RUNNING | 2:28:37 | hybrid_anno | ~1:11 |
| 2490 | NA20027 | RUNNING | 2:28:37 | hybrid_anno | ~0:49 |
| 2491 | NA15849 | RUNNING | 2:28:37 | hybrid_anno | ~0:23 |
| 2492 | NA10798 | RUNNING | 2:28:37 | hybrid_anno | ~0:49 |
| 2495 | NA15848 | RUNNING after one NODE_FAIL/requeue | 1:37:36 current attempt | DNAscope hybrid pass 2 | ~1:58 |
| 2497 | NA05067 | RUNNING | 2:28:36 | hybrid_anno | ~0:31 |
| 2500 | NA15603 | RUNNING | 2:28:07 | bcftools concat | ~1:09 |
| 2501 | NA14733 | RUNNING | 2:28:36 | hybrid_anno | ~0:34 |
| 2504 | NA13189 | RUNNING after six rapid NODE_FAIL attempts | 2:20:43 current stable attempt | bcftools concat | ~1:14 |
| 2502 | NA14732 | COMPLETED | 2:26:25 | downstream released | done `06:58:19Z` |

All 10 earlier `hiomrs_longreadsv` jobs completed successfully: 2489 NA15849 `0:06:43`; 2493 NA14733 `0:06:27`; 2494 NA13189 `0:09:25`; 2496 NA20027 `0:07:54`; 2498 NA15603 `0:11:25`; 2499 NA14732 `0:07:01`; 2503 NA20230 `0:06:03`; 2505 NA15848 `0:06:44`; 2506 NA10798 `0:09:22`; 2507 NA05067 `0:09:12`. Every sample had a new nonempty HIOMRS SV VCF and `.sv.done` marker. Job 2508 was not part of this controller's external-job-ID sequence and was excluded.

All 43 downstream queue members were for NA14732 and were `CONFIGURING`, not pending or running: 2509 `hiomrs_segdup_gene`; 2510 `peddy`; 2511-2512 `hiomrs_segdup_gene`; 2513 `hiomrs_expansionhunter_collect`; 2514-2517 `hiomrs_segdup_gene`; 2518 `rtg_vcfstats`; 2519-2523 `hiomrs_segdup_gene`; 2524 `bcftools_vcfstat`; 2525-2526 `hiomrs_segdup_gene`; 2527-2551 `vep_chromosome_input`.

Headnode Glances at `06:58:57Z`:

- CPU 15.3% total; load 0.84/0.55/0.40 on 8 cores.
- Memory 8.19 GB of 66.33 GB used (12.3%); no swap.
- Root filesystem 10.1% used; `/fsx` 3.8 TiB of 12 TiB used (34%).
- 421 processes, 2 running, 746 threads.

Compute-node Glances summary:

| Job | Sample | Compute node | CPU used | Load 1/5/15 | Memory used | Root/scratch used | Observation |
|---:|---|---|---:|---:|---:|---:|---|
| 2495 | NA15848 | `i128nvme-dy-price128nvme-9` | 96.5% | 85.3/32.6/38.1 | 28.3 GiB | 62.2%/0.1% | Actively CPU-bound at sample. |
| 2504 | NA13189 | `i128nvme-dy-price128nvme-2` | 0.9% | 2.7/22.7/54.2 | 15.7 GiB | 62.0%/0.1% | Low instantaneous CPU after prior heavy load. |
| 2500 | NA15603 | `i128nvme-dy-price128nvme-13` | 0.9% | 1.1/9.5/41.5 | 14.2 GiB | 62.1%/0.4% | Low instantaneous CPU after prior heavy load. |
| 2497 | NA05067 | `i128nvme-dy-price128nvme-10` | 1.3% | 1.2/1.2/6.8 | 23.3 GiB | 62.0%/0.1% | Phase transition or I/O wait plausible. |
| 2501 | NA14733 | `i128nvme-dy-price128nvme-14` | 4.7% | 5.0/5.2/19.0 | 36.7 GiB | 63.4%/0.6% | Low instantaneous CPU. |
| 2488 | NA20230 | `i128nvme-dy-price128nvme-1` | 4.5% | 5.9/5.7/18.9 | 37.9 GiB | 62.4%/0.1% | Low instantaneous CPU. |
| 2490 | NA20027 | `i128nvme-dy-price128nvme-3` | 4.6% | 5.2/5.5/18.7 | 36.7 GiB | 62.3%/0.1% | High scratch write sample, 57.7 MB/s. |
| 2491 | NA15849 | `i128nvme-dy-price128nvme-4` | 0.9% | 1.1/1.1/6.1 | 24.0 GiB | 62.1%/0.1% | Low instantaneous CPU. |
| 2492 | NA10798 | `i128nvme-dy-price128nvme-5` | 3.4% | 4.5/6.4/29.5 | 41.0 GiB | 62.0%/0.1% | Low instantaneous CPU after prior heavy load. |
| 2502 | NA14732 | `i192nvme-dy-price192nvme-1` | 0.6% | 1.3/3.9/14.0 | 15.6 GiB | 62.0%/0.0% | Completed during profiling. |

ETA method and result:

- Historical exact per-sample core benchmarks in this analysis root span 2:51:26-3:39:16; only current-attempt runtime was subtracted, excluding lost requeue attempts.
- The newly completed NA14732 core took 2:26:14 benchmark wall time, faster than its prior 3:10:49, so historical subtraction is conservative for most samples.
- Historical post-core windows were 21-35 minutes under parallel fanout.
- Most cores therefore had 23-74 minutes remaining; restarted NA15848 was the likely ~1h58m straggler.
- Conditional controller finish: `09:30-10:30Z` (`02:30-03:30 PDT`), approximately 2.5-3.5 hours after the job snapshot. If another core requeues, node configuration is unusually slow, or final aggregation fails, downside extends to `10:30-12:00Z`.

## Final Report

All rows terminal: yes

Objective complete: yes

Status counts:

- SUCCESS: 7
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0
- Working: 0

Changed files:

- `docs/plans/20260717T065428Z_ifx_controller_glances_eta_betelgeuser_hiomr_catalog_ledger.md`
- `config/daylily_pipeline_command_catalog.yaml`
- `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`
- `tests/test_hiomrs_command_catalog.py`
- `tests/test_repository_catalog.py`

Validation: catalog mirrors are byte-identical; 16 focused tests passed; owned-file diff check passed. Live evidence used the required `squeue` format, `sacct -D`, `sstat`, `scontrol show job`, tmux/process inspection, controller/domain logs, current outputs, benchmark TSVs, and bounded Glances sampling. Audit processes and sessions were cleaned up.

Residual risks: live Glances samples are point-in-time observations; ETA remains conditional on no further node failures or unexpected downstream/final aggregation work. Twenty unrelated approximately one-day-old timeout/SSH monitoring wrappers found on the headnode predate this audit and remain untouched.
