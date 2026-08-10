# `init-test-chr5` HG002 5x+5x HIOMR2 DayOA `13.4.11` execution ledger

Created: `2026-08-10T09:23:06Z`

Controlling request: on cluster and cost center `prod-cand-260809`, use the
DYEC CLI to create `day-clone -t 13.4.11 -d init-test-chr5` in persistent tmux,
plan the verified slim-data HG002 5x ILMN plus 5x ONT HIOMR2 kitchen-sink mega
and analytical Inflection package with `-j 333 -p -T 1 -k -n`, restrict the
active HIOMR2 Hybrid CLI to chromosome 5 when supported, and remove only `-n`
after an accepted plan. Existing controllers, tmux sessions, and Slurm jobs
must remain untouched.

## Gate 0 baseline

- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch
  `codex/pin-dayoa-13.4.10-16.1.45`, `HEAD=e60c0433ddcde783bdf96cd0c73e44526121cf37`
  (`16.1.58`). The worktree contains extensive pre-existing untracked user
  artifacts; none are in this task's write scope except this ledger and its
  paired overlay.
- DayOA release: annotated tag `13.4.11`, peeled commit
  `287923d167ca0ef6b05cb4469e290ade45f4852b`. The local tag has no signature;
  the annotated tag object and release message are present.
- Cluster: `prod-cand-260809`, `us-west-2`, `UPDATE_COMPLETE`; headnode login is
  `ubuntu`; headnode DYEC reports `16.1.54`; private DayOA authentication for
  ref `13.4.11` succeeds.
- Cost center: `prod-cand-260809`, active, `ubuntu` allowed, monthly cap
  `$200`. No cost-center or budget mutation is authorized or needed.
- Fresh boundary: exact root
  `/fsx/analysis_results/prod-cand-260809/init-test-chr5` and tmux
  `dayoa_init_test_chr5_hg002_5x5x_13411_20260810` were absent at
  `2026-08-10T09:25Z`.
- Preserved concurrent state: existing tmux sessions remain intact. Slurm job
  `82` is running in `i192nvme` as
  `sentdhiomr2_hybrid_cli170-HG002-Z-HG002-ANALYSIS-UNIT-5X5X`; no scheduler,
  controller, lock-takeover, or existing-root action is authorized.
- Input contract: catalog row `inflection-bjuice-product-v0.2`, validated for
  DayOA `13.4.11`, exact packaged six-manifest profile
  `hg002_bjuice_verified_5x5x_fastq`, catalog source/payload parity RC `0`.
- Scope contract: the active `sentdhiomr2_hybrid_cli170` rule consumes only
  `HIOMR2_SCOPE_BED`; the preflight renders that BED from nested setting
  `sentdhiomr2.hg38_sentdhiomr2_chrms`. The task overlay sets it explicitly to
  string `"5"`. The broader kitchen sink still includes specialty/QC/package
  products whose own biological scopes are not controlled by this setting.
- Relay root: the task may use only
  `s3://lsmc-ssf-sequencing-data/derived/validation/prod-cand-260809-init-test-chr5-20260810/`
  for supported DYEC payload transfer. No export or deletion is requested.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| CHR5-001 | Inventory | Prove exact cluster, cost center, tag, fresh root/session, catalog/input profile, and preserve all concurrent work | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 facts above; DYEC controller inventory found seven pre-existing tmux panes and running Slurm job `82` |  | No existing controller, tmux, job, or root was modified |
| CHR5-002 | Scope | Prove the active HIOMR2 CLI supports an explicit chr5 scope without inventing a caller switch | SUCCESS | config_or_startup_contract | Gate 0 | orchestrator | DayOA `13.4.11` `sentdhiomr2_hybrid_cli170` reads `HIOMR2_SCOPE_BED`; `_hiomr2_scope` reads nested `hg38_sentdhiomr2_chrms`; overlay sets `"5"` |  | Scope is explicit for the vendor HIOMR2 CLI; non-HIOMR2 specialty/QC targets are not relabeled chr5-only |
| CHR5-003 | Overlay/input | Stage the exact reviewed chr5 overlay and six immutable packaged manifests through supported DYEC relay paths | SUCCESS | config_or_startup_contract | Gate 1 | orchestrator | Remote overlay SHA-256 `66668df54c2de2ab23de799d74ed3d321a353e2148501d731c44c9c2fd06834d`; all six remote manifest hashes matched the packaged `hg002_bjuice_verified_5x5x_fastq` profile |  | Staged only through task-scoped DYEC upload and workflow payload relays |
| CHR5-004 | Clone/tmux | Use supported DYEC workflow launch so `day-clone -t 13.4.11 -d init-test-chr5` runs under one persistent Ubuntu interactive-login tmux boundary and owns the exact-root write lock | SUCCESS | feature_implementation | Gate 1 | orchestrator | Fresh root cloned exact annotated tag `13.4.11`, commit `287923d167ca0ef6b05cb4469e290ade45f4852b`; persistent tmux `dayoa_init_test_chr5_hg002_5x5x_13411_20260810` retained after its initial command exited |  | The exact existing checkout was reused only after tag/commit and clean tracked state were proved |
| CHR5-005 | Dry plan | Run the exact catalog-equivalent command with `-j 333 -p -T 1 -k -n`; require terminal RC 0 and chr5 scope evidence before live launch | SUCCESS | contract_test | Gate 2 | orchestrator | Retry tmux `dayoa_init_test_chr5_hg002_5x5x_13411_dry2_20260810`; matching `status.json` reports `SUCCEEDED`, RC `0`, zero submitted jobs, Snakemake log `2026-08-10T093352.758959.snakemake.log`; plan renders `sentdhiomr2_preflight --scope 5`, and `sentdhiomr2_hybrid_cli170` consumes the resulting BED with `-b` |  | Plan accepted for live launch; no DayOA code change was required |
| CHR5-006 | Live launch | If and only if CHR5-005 is accepted, launch the mechanically identical command with only `-n` removed | SUCCESS | feature_implementation | Gate 3 | orchestrator | Initial live tmux `dayoa_init_test_chr5_hg002_5x5x_13411_live_20260810` and three minimally repaired successors remained confined to this root. Final successor `dayoa_init_test_chr5_hg002_5x5x_comparisonfix_live_20260810`, PID `987385`, reached attributed RC `0`. |  | Live proof completed after immutable TrusSV compile/version and four-lane comparison repairs; no unrelated controller or job was modified. |
| CHR5-007 | Handoff | Record exact root, tmux, tag/commit, config, controller, Slurm, lock, and completion boundary | SUCCESS | legitimate_safety_handling | Gate 4 | orchestrator | Handoff below; live scope BED SHA-256 `0bcd547a07ddcb60d93a7bb755051f3b8898c5bdaffdac24e0a7ac04f17adb64`, one row `chr5 0 181538259`; existing job `82` and all pre-existing tmux sessions still present |  | Launch objective is complete; the 288-step workflow remains active and is not claimed complete |

## Fixed dry command

The dry command is catalog-equivalent except that its reviewed config file
adds the explicit nested chr5 scope:

```bash
DAY_CONTAINERIZED=true dy-r produce_sentdhiomr2_kitchensink produce_sentdhiomr2_nicu_research produce_sentdhiomr2_jasmine_sharded_per_sample produce_sentdhiomr2_inflection_analytical_package results/day/hg38/reports/DAY_final_multiqc.html --configfile /home/ubuntu/init-test-chr5-hg002-5x5x.yaml --config genome_build=hg38 'aligners=["sentmm2ont"]' 'dedupers=["na"]' 'snv_callers=["sentdhiomr2"]' 'sv_callers=[]' 'htd_callers=["smn12"]' hiomr2_inflection_package_mode=analytical seqone_delivery_batch_id=init-test-chr5 -j 333 -T 1 -p -k --rerun-triggers mtime -n --produce-analysis-artifact-manifest true --produce-rulegraph true --produce-filegraph false --produce-dag false
```

Live authorization is conditional on the accepted dry plan. The live command
must differ only by removal of the `-n` token.

## Attempt history

- The first dry controller cloned the fresh exact tag successfully, then exited
  RC `2` before Snakemake planning because the catalog-rendered
  `seqone_delivery_batch_id=$ANALYSIS_ID` was delivered literally and failed
  DayOA's unsafe-byte validation. It submitted no Slurm jobs.
- The first retry attempt stopped locally before controller creation because
  its inline SSM document exceeded the AWS document-size limit. The retry used
  DYEC's supported task-scoped S3 payload relay instead.
- The successful retry supplied the already explicit analysis identifier
  `init-test-chr5` as `seqone_delivery_batch_id`, retained the same targets,
  resources, config, and `-n`, and produced the Gate 2 evidence above.

## Live handoff

- Analysis root:
  `/fsx/analysis_results/prod-cand-260809/init-test-chr5`
- Checkout: exact DayOA tag `13.4.11`, commit
  `287923d167ca0ef6b05cb4469e290ade45f4852b`
- Controller tmux:
  `dayoa_init_test_chr5_hg002_5x5x_13411_live_20260810`
- Run state:
  `/home/ubuntu/daylily-runs/dayoa_init_test_chr5_hg002_5x5x_13411_live_20260810`
- Attributed controller PID: `713263`
- Attributed Snakemake log:
  `/fsx/analysis_results/prod-cand-260809/init-test-chr5/daylily-omics-analysis/.snakemake/log/2026-08-10T094326.455845.snakemake.log`
- Live scope BED:
  `/fsx/analysis_results/prod-cand-260809/init-test-chr5/daylily-omics-analysis/results/day/hg38/HG002-Z-HG002-ANALYSIS-UNIT-5X5X/align/sentmm2ont/na/snv/sentdhiomr2/preflight/HG002-Z-HG002-ANALYSIS-UNIT-5X5X.sentdhiomr2.scope.bed`
- Terminal boundary: final successor
  `dayoa_init_test_chr5_hg002_5x5x_comparisonfix_live_20260810` reached
  attributed RC `0`. Verified TrusSV VCF/TBI, all four comparison outputs,
  NICU manifest/marker, analytical Inflection package manifest, final MultiQC,
  and the one-row scope BED exactly `chr5 0 181538259`.
- Preserved concurrent work: pre-existing Slurm job `82` remains `RUNNING` as
  `sentdhiomr2_hybrid_cli170-HG002-Z-HG002-ANALYSIS-UNIT-5X5X`; every
  pre-existing tmux session remains present. No Slurm or old-controller action
  was taken.
