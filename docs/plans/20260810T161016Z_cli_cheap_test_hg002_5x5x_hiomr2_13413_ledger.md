# `cli-cheap-test` HG002 5x+5x HIOMR2 DayOA `13.4.13` execution ledger

Created: `2026-08-10T16:10:16Z`

Controlling request: use the released DayOA checkpoint/parallel-finalization
implementation to create a fresh `cli-cheap-test` analysis on cluster and cost
center `prod-cand-260809`, run the verified slim-data HG002 approximately-5x
Illumina plus 4.79x ONT chr19-20 HIOMR2 kitchen-sink mega and analytical
Inflection package, and compare biological outputs, task walltime, allocated
vCPU-hours, and task cost with the accepted earlier HIOMR2 run.

## Gate 0 baseline

- DayOA release: annotated tag `13.4.13`, tag object
  `c24c01475c0afdb7d4493b1f5b7e332c18ec7033`, peeling to merge commit
  `1716a4f6ba81dcbb58c16ed7c6052a18fea40924`; the remote tag and peeled commit
  match.
- CLI release: Sentieon CLI annotated tag `1.7.2i`; the DayOA rule environment
  `workflow/envs/hiomr2_cli172i_iamh2o_v0.1.yaml` pins that exact tag.
- Active DayOA profiles select the immutable `1.7.2i` environment. The HIOMR2
  graph owns one 128-core vendor/core rule, one four-core finalizer per
  configured whole contig, and one eight-core ordered gather.
- Cluster: `prod-cand-260809`, `us-west-2`, `UPDATE_COMPLETE`; headnode user is
  `ubuntu`.
- Cost center: `prod-cand-260809`, active, `ubuntu` allowed, monthly cap `$200`.
  No budget or cost-center mutation is authorized or needed.
- Fresh boundary: exact root
  `/fsx/analysis_results/prod-cand-260809/cli-cheap-test` is absent. Planned
  sessions `dayoa_cli_cheap_test_hg002_5x5x_13413_dry_20260810` and
  `dayoa_cli_cheap_test_hg002_5x5x_13413_live_20260810` are absent.
- Preserved concurrent state: existing job `562`, rule `vep_sqjx8366`, is
  `RUNNING` on partition `i8`; all pre-existing tmux sessions and workflows are
  outside this task. No scheduler, job, old controller, or old analysis-root
  action is authorized.
- Input/command contract: catalog row `inflection-bjuice-product-v0.2`, exact
  six-manifest profile `hg002_bjuice_verified_5x5x_fastq`, all supplied FASTQs,
  no time chunking, nested HIOMR2 scope `19-20`, five requested targets,
  `-j 333 -T 1 -p -k --rerun-triggers mtime`, and dry run by terminal `-n`.
- Exact relay boundary:
  `s3://lsmc-ssf-sequencing-data/derived/validation/prod-cand-260809-cli-cheap-test-20260810/`.
  It is for supported DYEC launch payloads only; no analysis export or deletion
  is requested.
- Accepted comparison baseline: the matched `1.7.1i` chr19-20 monolith and
  `1.7.2i` candidate proof in the DayOA integration ledger. Candidate tasks:
  core `1829.3714 s`, chr19 `379.9492 s`, chr20 `376.5950 s`, gather
  `124.7048 s`, total `66.162043` allocated vCPU-hours and `$2.575254` task
  cost. Semantic parity was exact for 32,377,132 gVCF/checkpoint records, 1,525
  SV records, 97 CNV records, and 24,351,770 RSR alignments.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| RELEASE-001 | Immutable release | Prove the new CLI environment and split HIOMR2 rules are present in remote annotated DayOA `13.4.13` | SUCCESS | contract_test | Gate 0 | orchestrator | Remote annotated tag and peeled commit above; tag contains `hiomr2_cli172i_iamh2o_v0.1.yaml` pinned to `1.7.2i`, profile selection, core/finalizer/gather rules |  | No additional DayOA source edit or release is needed. |
| INV-001 | Inventory | Freeze cluster, cost center, fresh root/session, catalog inputs, comparison baseline, and preserved concurrent work | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 evidence above; supported DYEC cluster, cost-center, root, tmux, and job inspections |  | Existing job 562 and all unrelated sessions remain untouched. |
| CLONE-001 | Clone and staging | Use supported DYEC launch so the fresh persistent Ubuntu tmux performs the explicit DayOA `13.4.13` clone and stages the exact six manifests | SUCCESS | feature_implementation | Gate 1 | orchestrator | DYEC catalog launch created `/fsx/analysis_results/prod-cand-260809/cli-cheap-test`; exact tag `13.4.13`, HEAD `1716a4f6ba81dcbb58c16ed7c6052a18fea40924`; all six staged manifest SHA-256 values match the packaged fixture; session `dayoa_cli_cheap_test_hg002_5x5x_13413_dry_20260810` remains as one persistent login shell |  | No existing root/session/job was changed. |
| PLAN-001 | Dry plan | Run the exact five-target command with `-j 333 -T 1 -p -k --rerun-triggers mtime -n`; require RC 0 and the intended bounded graph | SUCCESS | contract_test | Gate 2 | orchestrator | Attributed DYEC status `SUCCEEDED`, RC 0, exact log `.snakemake/log/2026-08-10T161305.515676.snakemake.log`; 291 jobs, max 192 threads, one 128-core `sentdhiomr2_hybrid_cli172i_core`, two four-core finalizers, one eight-core gather; zero submitted Slurm jobs |  | Plan matches the requested five-target fresh analysis; live launch is authorized by the controlling request. |
| LIVE-001 | Live launch | Remove only terminal `-n` after PLAN-001 succeeds and allow Snakemake/Slurm to own scheduling | IN_PROGRESS | feature_implementation | Gate 3 | orchestrator | Live session `dayoa_cli_cheap_test_hg002_5x5x_13413_live_20260810`, run directory `/home/ubuntu/daylily-runs/dayoa_cli_cheap_test_hg002_5x5x_13413_live_20260810`, attributed controller PID `1671014`; effective command matches the accepted dry command with only `-n` absent; cost center `prod-cand-260809` |  | Controller is launched; completion is not yet claimed. |
| OUTPUT-001 | Result equivalence | Compare final gVCF/checkpoint/SV/CNV/RSR and relevant packaging outputs with the accepted earlier HIOMR2 proof | OPEN | contract_test | Gate 4 | orchestrator |  |  |  |
| BENCH-001 | Cost/performance | Collect authoritative combined benchmarks, verify every successful non-local rule has exactly one combined row, and compare walltime/vCPU-hours/task cost | OPEN | contract_test | Gate 4 | orchestrator |  |  |  |
| HANDOFF-001 | Completion | Record controller state, exact tag/commit, output comparison, benchmarks, and any excluded Jasmine/NICU failure without claiming incomplete work complete | OPEN | legitimate_safety_handling | Gate 5 | orchestrator |  |  |  |

## Execution contract

- Use DYEC CLI surfaces for render, launch, visit/lock, status, logs, jobs, and
  benchmark collection.
- DayOA work runs only through `dy-r` in persistent, one-pane, interactive
  Ubuntu tmux. Never invoke raw Snakemake.
- The dry/live commands may differ only by removal of the terminal `-n`.
- Do not administer Slurm or manipulate jobs.
- If Jasmine or any `nicu*`/`*_nicu_*` rule fails, diagnose and report it but do
  not rerun that failed rule.

## Final report

All rows terminal: no

Objective complete: no
