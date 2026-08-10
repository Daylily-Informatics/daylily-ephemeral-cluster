# Take15 HG003 + NA23687 HIOMR2 execution ledger

**Created:** 2026-07-29T14:14:00Z  
**Controlling request:** Launch a fresh `13.0.80` Bjuice HIOMR2 full-coverage
workflow for HG003 plus NA23687 on `preval-hiomr2`, with five configured
primary-assembly shards, the analytical package batch `take15`, and SNV
concordance.

## Gate 0 — inventory freeze

- DYEC repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`,
  branch `codex/hiomr2-catalog-repair`, already dirty before this work; all
  unrelated changes are preserved.
- DayOA repository: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`,
  branch `codex/feat-hiomr2-sentieon-cli-fidelity-13.0.72`, already dirty
  before this work; it is not the source for the fresh tagged clone.
- Requested DayOA release: annotated tag `13.0.80`, commit
  `b2181febc3fac8ef1b91d20a13637f065a1f890d`.
- Cluster/profile/region: `preval-hiomr2` / `lsmc` / `us-west-2`,
  `UPDATE_COMPLETE`; headnode is Ubuntu and exposes `day-clone`, `tmux`,
  `squeue`, and DYEC analysis locking.
- Input mounts: the full Illumina and pca100-2026 ONT mounts are both
  `AVAILABLE`, projected locally, and read-only.
- Controller/queue baseline: zero live controllers and zero Slurm jobs; stale
  receipts and unrelated idle tmux sessions are not reused.
- Target root `/fsx/analysis_results/preval-hiomr2/take15-hg003` was absent.
- Cost center: `bjuice` is active for `ubuntu`, cap USD 700, current recorded
  July usage USD 0. No budget cap or bypass is authorized.

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| T15-001 | Baseline | Freeze source, cluster, mount, lock, controller, and cost-center state before writes. | SUCCESS | contract_test | Gate 0 | Codex | `cluster-info`, `mounts list`, `headnode system-info`, `headnode dayoa-controllers`, `cost-centers show/usage`, and target-root inspection at 2026-07-29T14:13Z. |  | Fresh idle target is safe to initialize. |
| T15-002 | Inputs | Generate full-coverage six manifests for exactly HG003 and NA23687. | SUCCESS | config_or_startup_contract | Gate 1 | Codex | `docs/plans/20260729T141400Z_take15_hg003_na23687_hiomr2_manifests/`; generator receipt has exactly two samples. |  | Full SR and raw ONT source paths were generated without subsample flags. |
| T15-003 | Inputs | Validate manifest topology, hashes, source receipt, full SR, and three ONT inputs per sample. | SUCCESS | contract_test | Gate 1 | Codex | `dyec identities validate` reported valid foreign keys, ordered inputs, no identifier creation/rewrite; 2 specimens, 2 samples, 4 libraries, 8 inputs, 2 units, and 8 links. |  | Each sample has one SR plus three LR inputs; both subsample fields are blank. HG003 has GIAB truth; NA23687 has none. |
| T15-004 | Analysis root | Create fresh `13.0.80` clone under an owned write lock. | SUCCESS | config_or_startup_contract | Gate 1 | Codex | `day-clone -t 13.0.80 -d take15-hg003 --executing-entity preval-hiomr2` completed in tmux `take15_hiomr2_hg003_na23687_20260729`; `git rev-parse HEAD` = `b2181febc3fac8ef1b91d20a13637f065a1f890d`; `git describe --tags --exact-match` = `13.0.80`. |  | The empty root remained owned by `codex-take15-hiomr2-20260729T141700Z` throughout clone creation. |
| T15-005 | Runtime config | Stage exact manifests and the two-sample five-shard overlay without altering source manifests. | SUCCESS | config_or_startup_contract | Gate 1 | Codex | SSM-text-only staging rebuilt `/home/ubuntu/t15s_1420` and verified the six target hashes before a guarded copy to `config/`: `specimens=d3ffea1551f338aaf635f73f01127db0616eadc3b78a626b636f231a56bd6a60`, `samples=ae662279f16e04cc093b2fbc515c9b0e79003a765903d1d31a62f773937e8f95`, `libraries=381ba5aec7a758bd15c480cc6ddf143e2e01efaefc722f02e51b6384688c6fbd`, `sequencing_inputs=c1d5d2d533735b3d92f5f5a69ad7c64930df6b67cbd4a83a65d4eb7d0cfc8667`, `analysis_units=ac945e104b62f4e381c9460b9dbd4942416c88f1d135d20d297db7a764016b09`, `analysis_unit_inputs=28406e29d9efd1093ce34ac61f6816b4cc63b9f63c50bb36d520f22addb0f213`; overlay hash `c06ab2df7fa7f26c33620ea13d0d45a92717e85c5c4e911e7c9332021577f238`; receipt hash `cc227ea921f95615e8f911f837ad92ca0861e5b7f64b6edab66ddfb5357b412e`. | The first unused home staging root (`/home/ubuntu/t15s_1414`) stopped on an SSM 100-character comment limit before reconstruction or clone writes; it is retained. | The accepted clone contains only the generated six-manifest set, receipt, and exact two-sample overlay; source manifest metadata was not rewritten. |
| T15-006 | Dry run | Render the exact catalog-derived target set, including SNV concordance. | BLOCKED | contract_test | Gate 2 | Codex | The exact `13.0.80` command, plus only `produce_snv_concordances` and `-n`, reached the DAG with both staged samples and retained `150/438` ONT FASTQs per sample for `[0,25)`, then exited `1` before any Slurm job: `HIOMR2 native QC requires one of [('sentdhiomr2_lr', 'na'), ('sentdhiomr2_sr', 'smd')]; found ('sentmm2ont', 'na')`. | In `13.0.80`, ExpansionHunter keeps its `sentmm2ont/na` wildcard for `SEX_COMPLEMENT_JSON_PATTERN`, while its HIOMR2 short-read input resolver maps the same task to the native SR CRAM. The sex-complement rule rejects that unremapped wildcard. This is a source-level producer/consumer mismatch, not a config-owned selection; the tag exposes no override. | Dry-run acceptance did not pass; no alternate aligner contract or source patch was inferred. |
| T15-007 | Live run | Submit only the accepted dry-run-equivalent `dy-r` command under `bjuice`. | BLOCKED | feature_implementation | Gate 3 | Codex | Not submitted. The dry run created no Slurm jobs and no DayOA controller. | T15-006 is not accepted. | A live command would violate the plan’s explicit dry-run gate. |
| T15-008 | Validation | Record launch and terminal workflow evidence; retain the root lock until controller completion. | OPEN | contract_test | Gate 4 | Codex | Pending. |  |  |

## Selected runtime contract

- Samples: `HG003`, `NA23687`.
- Genome: `hg38`; full Illumina; ONT runtime window `[0,25)` via
  `use_fq_data_starting_hrs=0` and `use_fq_data_up_to_hrs=25`.
- HIOMR2 scopes: `1-3`, `4-8`, `9-15`, `16-20`, and `21-25`.
- Batch: user-supplied `SEQONE_DELIVERY_BATCH_ID=take15`.
- NA23687 observed-sex overlay: `female`, retained as an explicit run setting;
  source sample metadata remains unchanged. This is the user-selected mapping;
  the linked [Coriell NA23687 record](https://catalog.coriell.org/0/Sections/Search/Sample_Detail.aspx?Product=DNA&Ref=NA23687)
  identifies the donor as the mother, supporting the female inference without
  rewriting source metadata.

## Dry-run blocker and retained state

- `dyoainit` accepts only its DayOA initialization project.  The cluster-valid
  initializer is `preval-hiomr2`; `bjuice` is an active DYEC cost center, not a
  valid `dyoainit --project` value.  Per the DYEC launcher contract, the pane
  exported `DAY_PROJECT=bjuice` and `DAYLILY_COST_CENTER=bjuice` immediately
  before `dy-r`, which is the submission-time cost-center boundary.  No budget
  bypass was used.
- `dy-a slurm hg38` completed under the owned root lock.  The exact dry run then
  detected all six generated manifests, selected only HG003 and NA23687, and
  applied the requested ONT interval.  It failed while building the graph, not
  while scheduling or running a job.
- The write lock remains owned by `codex-take15-hiomr2-20260729T141700Z`; the
  persistent tmux session remains available.  No controller exists and no
  scheduler, export, deletion, budget, or infrastructure action occurred.
- Source review identifies the fault boundary precisely: `workflow/rules/expansionhunter.smk`
  requests `SEX_COMPLEMENT_JSON_PATTERN` with the catalog `sentmm2ont/na`
  wildcard, whereas `workflow/rules/common.smk` routes the HIOMR2 short-read
  CRAM to `sentdhiomr2_sr/smd`.  A fixed release must route that companion sex
  evidence to the same native SR QC lane; changing the catalog’s requested
  aligner alone would not be an equivalent command contract.
