# IFX P2 remaining-10 HIOMRS kitchensink dry-run ledger

Date: 2026-07-16

## Control Ledger

Controlling request: on cluster `ifx-p2-1000-120-0715` using AWS profile `lsmc`, verify that the exact ILMN and ONT manifest locations are mounted, prove that the supplied manifests select full-coverage ILMN and ONT elapsed-hour window `[0,25)` for exactly 10 remaining Bjuice prevalidation libraries, prove these 10 have not already been processed on this cluster, create `day-clone -t <maximum released DayOA version> -d second-half-bjuice-preval`, and report the HIOMRS kitchensink dry-run plan using `-j 300 -p -T 2 -k -n`.

Ledger path: `docs/plans/20260716T165939Z_ifx_p2_remaining10_hiomrs_kitchensink_dryrun_ledger.md`

### Runtime contract

- AWS profile: `lsmc` (explicit; never default).
- Region: `us-west-2` (from the supplied cluster console link).
- Cluster: `ifx-p2-1000-120-0715`.
- Workset/analysis id: `second-half-bjuice-preval` (exact user value).
- DayOA ref: highest strict semantic-version release tag after a current remote tag fetch; currently `11.0.15`, commit `ef279ccafa70dd6244c6feac39340cc34f4a80f3`.
- Genome/executor: resolve from the current HIOMRS kitchensink catalog; current catalog contract is `slurm hg38`.
- Input manifests: `/Users/jmajor/projects/lsmc/remaining/samples.tsv` and `/Users/jmajor/projects/lsmc/remaining/units.tsv`.
- Requested dry-run flags: `-j 300 -p -T 2 -k -n`.
- Required raw ONT bounds: `--config use_fq_data_starting_hrs=0 use_fq_data_up_to_hrs=25`, interpreted by DayOA as half-open elapsed-hour interval `[0,25)`.
- This request authorizes a dry-run plan only. Do not remove `-n`, launch live jobs, or administer Slurm.
- No raw `snakemake` invocation is authorized. All DayOA commands must run through separate `source dyoainit`, `dy-a`, and `dy-r` commands in one persistent, one-pane `ubuntu` `bash -il` tmux session.

### Gate 0 baseline

- DYEC repo: `main...origin/main`, commit `7dbb9cb5b1f4e02b04fbbeff6cb9aa0c172710a7`; pre-existing modified and untracked files are preserved and are not owned by this execution except this ledger.
- DayOA repo: branch `codex/multiqc-integrity-repair`, pre-existing untracked `docs/plans/20260716T161837Z_dev_shm_audit.md`; current fetched strict-semver maximum is tag `11.0.15` at commit `ef279ccafa70dd6244c6feac39340cc34f4a80f3`.
- Samples manifest: 10 data records; SHA-256 `0a662e6abbd200a8636f7c2bb4dec73f55bdacaf9e1995977e77108ffc3a5824`.
- Units manifest: 10 data records; SHA-256 `0a070b8f9219e7e4dd443175470134f1379c83e629320234ae7500df6392e0c9`.
- Samples: `NA05067`, `NA10798`, `NA13189`, `NA14732`, `NA14733`, `NA15603`, `NA15848`, `NA15849`, `NA20027`, and `NA20230`.
- Each units row has 8 ILMN R1 paths, 8 ILMN R2 paths, 438 ONT FASTQ paths, and blank `SUBSAMPLE_PCT`; live existence/mount checks remain required.
- Exact manifest mount roots: `/fsx/run_dir_mounts/20260618_LH01106_0011_A23MFMCLT3/` for ILMN and `/fsx/run_dir_mounts/pca100-2026/` for ONT.
- Current catalog `hybrid_ilmn_ont_hiomrs_kitchensink` is pinned to DayOA `11.0.15` and targets HIOMRS, SNV concordance, TIDDIT SV, alignstats, relatedness, Peddy, both contamination paths, VEP, HTD/SMN12, Ganon2 metagenomics, final MultiQC, and the evidence manifest. User flags and explicit ONT bounds override its controller defaults without changing the target/config set.
- A prior same-day attempt on different cluster `dyec-tst-r5` created and verified the same two DRA roots there but stopped before dry-run because `source dyoainit` failed its mandatory Mermaid smoke render. That evidence does not prove the mounts or initialization state on this requested cluster.

### Live execution evidence

- Cluster-local DRA inventory and independent `dyec mounts verify` calls:
  - ILMN `dra-0017c9af390ef592a`, `/fsx/run_dir_mounts/20260618_LH01106_0011_A23MFMCLT3/`, lifecycle `AVAILABLE`.
  - ONT `dra-09989fe0dd83e5955`, `/fsx/run_dir_mounts/pca100-2026/`, lifecycle `AVAILABLE`.
- All manifest inputs were checked on the headnode: `4,540` total, `4,540` unique, `0` missing, and `0` empty. This comprises `160` ILMN FASTQs and `4,380` listed ONT FASTQs.
- All 10 units have 8 ILMN R1 paths, 8 ILMN R2 paths, 438 listed ONT paths, and blank `SUBSAMPLE_PCT`. The dry-run then retained 150/438 ONT paths for every unit under the requested half-open `[0,25)` elapsed-hour filter.
- Existing cluster analyses at Gate 1 were `bjuice-preval-hg001-007-smn3-hiomrs-11010-20260716T014729Z`, `bjuice-preval-hg001-007-smn3-hiomrs-1108-20260715T235558Z`, `hg003-1x-hiomrs-1107-20260715T210036Z`, and `test-1x`. Bounded searches of their staged manifests, `day_cmd.log` files, and result directory names returned no hit for any of the 10 requested sample IDs or the `HYBPREVALREM10` analysis-unit prefix. The exact requested root was absent before preparation.
- The headnode's installed `dyec 10.3.26` requires an analysis root to exist before `analysis lock acquire`, while `day-clone` accepts only an absent destination or an empty lock-initialized workspace. After the first acquire failed closed, the tmux pane created only the empty destination directory, immediately acquired the write lock, and then ran the exact clone. No analysis content existed before lock acquisition.
- Checkout: `/fsx/analysis_results/ifx-p2-1000-120-0715/second-half-bjuice-preval/daylily-omics-analysis`, exact tag `11.0.15`, commit `ef279ccafa70dd6244c6feac39340cc34f4a80f3`.
- Manifest handoff: `s3://lsmc-dayoa-control-data-usw2/dayoa_input_manifests/ifx-p2-1000-120-0715/second-half-bjuice-preval/`; staged SHA-256 values exactly match Gate 0.
- Persistent session: `second_half_bjuice_preval_20260716`, one `bash -il` window and one pane as `ubuntu`; `source dyoainit` rc `0`; `dy-a slurm hg38` rc `0`.
- Dry-run output: `/fsx/analysis_results/ifx-p2-1000-120-0715/second-half-bjuice-preval/daylily-omics-analysis/.ignore/hiomrs_kitchensink_j300_T2_ont0_25_dryrun.out`; rc file beside it with value `0`; output has 63,715 lines and 11,996,742 bytes.
- Dry-run plan: 1,181 jobs across 87 unique rules, with per-job thread requests from 1 to 128. Largest job-count contributors are `vep_chromosome_input` 250, `vep_chromosome` 250, `hiomrs_segdup_gene` 140, and 12 separate 20-job rule families including alignstats/QC, contamination, relatedness/sex checks, and Ganon2.
- Post-dry-run state: `RETURN CODE: 0`; Slurm queue header only; no `dy-r`, `day_run`, or Snakemake controller process; analysis lock released and status `unlocked`. No live workflow was launched.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Gate 0 | Freeze repo, manifest, release-tag, command, and safety contracts | SUCCESS | active_product_contract | Gate 0 | orchestrator | Baseline recorded above from local source and fetched tags |  | Local Gate 0 is complete; live inventory follows. |
| AMD-001 | Lock bootstrap | Handle the fresh-root lock bootstrap contract without creating analysis content outside the lock | SUCCESS | plan_amendment | Gate 1 | orchestrator | First acquire failed because the root did not exist; created only the empty destination directory, immediately acquired the lock, and confirmed `day-clone` accepted the lock-initialized workspace | Installed `dyec 10.3.26` rejects nonexistent analysis roots even though `day-clone` supports lock-initialized empty destinations. | Minimal bootstrap completed; all analysis content was created under the owned lock. |
| MNT-001 | DYEC/headnode | Verify the exact ILMN and ONT DRA locations are mounted and every listed path exists and is nonempty | SUCCESS | contract_test | Gate 1 | orchestrator | Both DRA ids independently verified `AVAILABLE`; headnode path sweep: 4,540 total/unique, 0 missing, 0 empty |  | Both exact DRA roots and every referenced input are usable. |
| INPUT-001 | Manifests/DayOA | Prove exactly 10 libraries, full ILMN (all 8 lane pairs, no subsampling), and explicit ONT `[0,25)` | SUCCESS | active_product_contract | Gate 1 | orchestrator | 10/10 rows have 8 R1 + 8 R2 ILMN paths, 438 ONT paths, blank `SUBSAMPLE_PCT`; DayOA retained 150/438 per unit for `[0,25)` |  | Exact full-coverage ILMN plus requested ONT window is in the plan. |
| HISTORY-001 | Headnode | Prove none of the 10 sample IDs or analysis unit IDs has already been processed on this cluster | SUCCESS | contract_test | Gate 1 | orchestrator | Four pre-existing roots inventoried; no hit in manifests, command logs, or result directory names; requested root initially absent |  | No prior processing evidence exists for these 10 on this cluster. |
| DAY-001 | DayOA/headnode | Create fresh `day-clone -t 11.0.15 -d second-half-bjuice-preval` and stage byte-identical manifests | SUCCESS | active_product_contract | Gate 2 | orchestrator | Exact tag/commit and staged SHA-256 values recorded above; one-pane tmux and initialization rc values are 0 |  | Fresh exact-tag checkout is prepared. |
| DRY-001 | DayOA/headnode | Run exact HIOMRS kitchensink dry-run with user flags, catalog config/targets, and ONT `[0,25)`; require rc 0 | SUCCESS | contract_test | Gate 3 | orchestrator | `-j 300 -p -T 2 -k -n`, catalog targets/config, explicit ONT bounds, `RETURN CODE: 0`; output/rc paths recorded above |  | Requested dry-run completed successfully. |
| PLAN-001 | Reporting | Preserve and report job counts, rule counts, max threads/resources, and exact attach/log handles from the dry-run | SUCCESS | contract_test | Gate 5 | orchestrator | 1,181 jobs, 87 unique rules, 1-128 threads; output and tmux handles recorded above |  | Plan is preserved and ready for handoff. |

## Final Report

All rows terminal: yes

Objective complete: yes

Status counts:

- SUCCESS: 8
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0
- IN_PROGRESS: 0
- OPEN: 0

Changed files:

- `daylily-ephemeral-cluster`: this ledger only.

Validation:

- `dyec mounts verify` for both exact mount ids -> success, lifecycle `AVAILABLE`.
- Headnode manifest input sweep -> 4,540/4,540 unique paths present and nonempty.
- Existing-analysis bounded search -> no requested sample/unit hits.
- `source dyoainit` -> rc 0; `dy-a slurm hg38` -> rc 0.
- HIOMRS kitchensink `dy-r ... -j 300 -p -T 2 -k ... -n` with ONT `[0,25)` -> rc 0, 1,181-job plan.
- Post-dry-run `squeue` -> header only; controller process search -> none; analysis lock -> unlocked.

Non-success terminal rows: none yet.

Residual risks:

- This is a successful dry-run plan, not evidence that any of the 1,181 planned jobs or final artifacts completed.
- A future live launch would require a new explicit request, reacquisition of this analysis root's write lock, and the same exact command without `-n`; none of those actions occurred here.
