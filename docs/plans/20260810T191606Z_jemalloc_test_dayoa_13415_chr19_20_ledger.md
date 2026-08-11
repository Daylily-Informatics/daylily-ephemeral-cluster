# DayOA 13.4.15 jemalloc chr19-20 live proof ledger

Date: 2026-08-10

## Objective

Launch a fresh HG002 verified 5x Illumina plus 5x ONT analytical HIOMR2 kitchen-sink/mega/Inflection packaging run on `prod-cand-260809`, using DayOA tag `13.4.15`, analysis ID `jemalloc-test`, chr19-20 scope, `-j 300 -T 0 -p`, no `-k`, and no FASTQ time bounds. Run the exact graph first with `-n`; remove only `-n` after the plan is accepted.

## Gate 0 inventory

- Cluster: `prod-cand-260809`, profile `lsmc`, region `us-west-2`, headnode user `ubuntu`.
- Analysis root: `/fsx/analysis_results/prod-cand-260809/jemalloc-test`.
- DayOA tag: annotated remote tag `13.4.15` object `5ed552ca34aef612ef3e1405e42e92b845d189a8`, peeled commit `8d48f62012e62fef7c2534c7ec5875b3f1b6e6f6`.
- DYEC: `16.1.68` from the activated local checkout.
- Cost center: `prod-cand-260809`, active, `$200` monthly cap, allowed user `ubuntu`.
- Cluster state: `UPDATE_COMPLETE`; compute fleet `RUNNING`; headnode `running`.
- Initial live state: zero DYEC DayOA controllers and zero Slurm jobs. Existing idle tmux sessions are foreign and remain untouched.
- Catalog base: `inflection-bjuice-product-v0.2`, test-data profile `hg002_bjuice_verified_5x5x_fastq`.
- Inputs: exact packaged six-manifest fixture under `daylily_ec/resources/payload/examples/staging/hg002_bjuice_verified_5x5x_fastq`; its identity document binds the three slim-data FASTQs.
- Scope/config: `config/hg002_bjuice_5x5x_hiomr2.yaml` plus `sentdhiomr2={"hg38_sentdhiomr2_chrms":"19-20"}`. No `use_fq_data_starting_hrs` or `use_fq_data_up_to_hrs` assignment is supplied.
- Targets: `produce_sentdhiomr2_kitchensink`, `produce_sentdhiomr2_nicu_research`, `produce_sentdhiomr2_jasmine_sharded_per_sample`, `produce_sentdhiomr2_inflection_analytical_package`, and `results/day/hg38/reports/DAY_final_multiqc.html`.
- Requested execution flags: `-j 300 -T 0 -p --rerun-triggers mtime`; no `-k`; dry run adds only `-n`.
- Local repo began dirty with unrelated user-owned files; this ledger is the only local file created for this launch.

## Control ledger

| ID | Requirement | Status | Evidence / terminal note |
|---|---|---|---|
| RUN-001 | Create fresh exact-tag DayOA analysis through the supported DYEC workflow launcher and persistent Ubuntu tmux controller | SUCCESS | Fresh clone created at the exact analysis root; tmux `dayoa_jemalloc_test_13415_dry_20260810`; detached commit `8d48f62012e62fef7c2534c7ec5875b3f1b6e6f6`. |
| RUN-002 | Stage the exact HG002 verified 5x/5x six-manifest fixture without rewriting identities | SUCCESS | DYEC accepted and staged the packaged six-manifest contract; dry-run sample resolved as `HG002-Z-HG002-ANALYSIS-UNIT-5X5X`. |
| RUN-003 | Execute and inspect chr19-20 dry run with `-j 300 -T 0 -p -n`, no `-k`, and no time bounds | SUCCESS | Attributed RC 0; 291 jobs; 0 workflow failure markers; one core, two contig-finalize, one gather; 16 `LD_PRELOAD` and 14 `MALLOC_CONF` plan lines; dry-run lock released. |
| RUN-004 | If the plan is sound, restart the exact invocation without only `-n` | SUCCESS | Exact immutable `13.4.15` continuation launched in tmux `dayoa_jemalloc_test_13415_live_20260810`; controller PID `2139936`. |
| RUN-005 | Confirm a live controller and submitted/running Slurm work, without administering Slurm | SUCCESS | At 2026-08-10T19:48:41Z the attributed controller was `RUNNING`, 73/291 steps (25%) were complete, 72 external jobs had been submitted, 15 were `RUNNING`, and no failure marker or terminal RC existed. No Slurm state was changed. |
| RUN-006 | Audit every non-local job in the selected 291-job DAG for an `/fsx`-resolved log and canonical benchmark declaration | SUCCESS | Corrected audit: 241 non-local instances, 81 unique rules, zero missing logs, zero non-FSx logs, zero missing benchmarks, and one unique collector-path exception duplicated across dry/live plans: `sentdhiomr2_lr_prepare_fastq`. DayOA `13.4.17` moves that benchmark to the canonical direct analysis-unit root; separate headnode dry-run RC 0 rendered the fixed path with zero Slurm submissions. The active 13.4.15 job retains its historical nested benchmark path. |
| RUN-007 | Compare the two exact prior pre-/post-Sentieon-CLI-update runs using canonical combined benchmark TSVs | OPEN | Identify comparable roots from immutable run/tag/controller evidence before aggregation. |
| RUN-008 | After `jemalloc-test` completes, collect its authoritative benchmark TSV, verify successful non-local benchmark coverage, and add it as the third comparison run | OPEN | Gated on terminal workflow success. |

## Launch note

The first live reuse launch created controller PID `2139936` in tmux `dayoa_jemalloc_test_13415_live_20260810`. A later diagnostic retry was correctly rejected with `__DAYLILY_ERROR__=session_exists`; it did not create a second controller. The retained first controller is the sole authoritative live invocation.

## Safety boundary

- No raw `snakemake`; all workflow execution goes through `dy-r` inside the DYEC-created persistent tmux controller.
- The launcher owns analysis-root visit/lock acquisition and release.
- Existing analyses, controllers, tmux sessions, and Slurm jobs are not modified.
- No auto-export or delete-on-export is requested.
