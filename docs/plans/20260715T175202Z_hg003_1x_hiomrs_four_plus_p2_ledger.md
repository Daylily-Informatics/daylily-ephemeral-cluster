# HG003 1x HIOMRS four-cluster comparison and P2-default rollout ledger

Created: `2026-07-15T17:52:02Z`

## Objective

Run the exact HG003 SR1x+LR1x HIOMRS kitchensink workflow from immutable DayOA
tag `11.0.6` on the four live Oregon clusters in parallel. Integrate and release
the already proven DYEC-owned `PERSISTENT_2` lifecycle as the explicit default,
pin the current HIOMRS command to DayOA `11.0.6`, support a 14.4-TiB P2
filesystem at the highest supported SSD throughput tier, then create a fifth
cluster and run the same workflow there when all execution gates are satisfied.

## Gate 0 baseline

- AWS account/profile/region: `108782052779` / `lsmc` / `us-west-2`.
- DayOA release: annotated tag `11.0.6`, peeled commit
  `5e245f59fefb80c9a6fb85dec748a2bd4d828f2b`. The preceding accepted HG003 1x
  root reached controller rc 0 and produced final MultiQC plus the DayOA
  evidence manifest on the 1,200-GiB `SCRATCH_2` filesystem, but provenance
  inspection shows its checkout remained at tag `11.0.5` / commit
  `ee86670c3c5347cb4d821f570283c8c034c23671`. Its two runtime-modified files
  have SHA-256 values exactly matching the eventual `11.0.6` release; therefore
  it is a valid live-tested-code baseline, not an exact-tag `11.0.6` checkout.
- DYEC source: clean worktree
  `/Users/jmajor/projects/lsmc/.worktrees/dyec-p2-default-hiomrs-1106`, branch
  `codex/p2-default-hiomrs-1106`, based on `origin/sentieon-single` commit
  `80a32383370d79e9a3913495835b9436eb765955`.
- Latest published DYEC release: annotated tag `10.3.7`, peeled commit
  `a943d8e71b0d4bc9366f3bdc801318c968174c77`. Its command catalog still pins
  DayOA/HIOMRS to `10.3.0`, so a new pin release is required.
- Proven P2 canary source: commits `904c1c9b`, `e3aafb9d`, and `7347d1b0` on
  `origin/codex/p2-fsx-canary`; live canary filesystem
  `fs-0e8434a86af264b29` is `PERSISTENT_2`, 4,800 GiB, 250 MB/s/TiB, Lustre
  2.15, metadata `AUTOMATIC`, and `AVAILABLE`.
- Four target clusters are live and idle at Gate 0:
  `ifx-p2-250-0714`, `ifx-sacctoff-1037`, `ifx-20260719h`, and
  `sent-hg003-5x-0712`. Each headnode is reachable as `ubuntu` through the
  supported DYEC/SSM login shell, `/fsx` is mounted read/write, the exact Daylily
  `squeue` format is empty, and `dyec analysis` is available.
- FSx comparison shapes: 4,800-GiB P2-250; 4,800-GiB Scratch_2; 14,400-GiB
  Scratch_2; and 1,200-GiB Scratch_2.
- The requested 14,000 GiB is not an FSx Lustre SSD capacity quantum. Persistent
  SSD capacity at this size must be a multiple of 2,400 GiB, so the exact fifth
  configuration is 14,400 GiB. AWS supports P2 SSD throughput tiers 125, 250,
  500, and 1000 MB/s/TiB; the requested highest tier is therefore 1000.
- The three `ifx-*` clusters do not have same-named DYEC cost centers. All five
  comparison runs use the already active `sent-hg003-5x-0712` project/cost
  center (cap `$750`, allowed user `ubuntu`) explicitly in `dyoainit`; no budget
  or cost-center cap is changed.
- HG003 manifests come only from tag `11.0.6`:
  `.test_data/data/hybrid/empty_cells/hiomr/samples.tsv` and the header plus
  first data row of `.test_data/data/hybrid/empty_cells/hiomr/units.tsv`.
  Expected SHA-256 values are `15bf42e9348a52f921fd785ff82c86615ea060b9b0aa6b646a0c1f928efd17c0`
  and `a5b3d5ba0cd585b26aee2fa57bc200d9060fbfe1947b11409074b897d7ecb4ec`.
- No raw Snakemake, SSH, silent fallback, filesystem deletion, DRA deletion,
  Slurm administration, budget increase, or foreign lock takeover is allowed.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval gate | Owner | Evidence | Root cause | Terminal note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Inventory | Freeze repos, releases, inputs, clusters, queues, filesystems, cost centers, and no-fallback contract | SUCCESS | feature_implementation | Gate 0 | orchestrator | Gate 0 baseline above |  | Baseline complete before workflow or AWS mutation. |
| RUN-001 | `ifx-p2-250-0714` | Fresh exact-tag HG003 1x HIOMRS dry-run then live controller | RUNNING | feature_implementation | Gate 1 | orchestrator | Root `/fsx/analysis_results/ifx-p2-250-0714/hg003-1x-hiomrs-1106-20260715T1754Z`; tmux `hg003-1x-hiomrs-1106-p2-250-20260715`; exact tag/commit and input hashes verified; 174-job dry-run rc 0; live controller is creating pinned conda environments |  | Controller live; no terminal claim. |
| RUN-002 | `ifx-sacctoff-1037` | Fresh exact-tag HG003 1x HIOMRS dry-run then live controller | RUNNING | feature_implementation | Gate 1 | orchestrator | Root `/fsx/analysis_results/ifx-sacctoff-1037/hg003-1x-hiomrs-1106-20260715T1754Z`; tmux `hg003-1x-hiomrs-1106-s2-48-20260715`; exact tag/commit and input hashes verified; 174-job dry-run rc 0; live controller is creating pinned conda environments |  | Controller live; no terminal claim. |
| RUN-003 | `ifx-20260719h` | Fresh exact-tag HG003 1x HIOMRS dry-run then live controller | RUNNING | feature_implementation | Gate 1 | orchestrator | Root `/fsx/analysis_results/ifx-20260719h/hg003-1x-hiomrs-1106-20260715T1754Z`; tmux `hg003-1x-hiomrs-1106-s2-144-20260715`; exact tag/commit and input hashes verified; 174-job dry-run rc 0; live jobs 1-5 submitted with zero Slurm memory placement |  | Controller live; initial LR/SR preparation and QC jobs are configuring. |
| RUN-004 | `sent-hg003-5x-0712` | Fresh exact-tag HG003 1x HIOMRS dry-run then live controller | RUNNING | feature_implementation | Gate 1 | orchestrator | Root `/fsx/analysis_results/sent-hg003-5x-0712/hg003-1x-hiomrs-1106-20260715T1754Z`; tmux `hg003-1x-hiomrs-1106-s2-12-20260715`; 174-job dry-run rc 0. First live submission failed closed on stale cost-center evidence, released its lock, then authoritative refresh and explicit visit/lock reacquisition admitted jobs 1149-1153. At `2026-07-15T18:15Z`, 4 of 172 live steps were complete and jobs 1150-1160 were active. Existing unrelated tmux sessions remain untouched. | Missing `refresh-usage` integration left a 43.05-hour snapshot behind the 36-hour enforcement maximum. | Controller live; current jobs use zero Slurm memory placement. |
| SRC-001 | DYEC P2 | Integrate the proven cluster-bound P2 implementation without unrelated canary evidence | SUCCESS | feature_implementation | Gate 2 | orchestrator | Cherry-picked canary commits `904c1c9b`, `e3aafb9d`, `7347d1b0` as `a412508a`, `6ee6fe83`, `1ca3236c` |  | Proven implementation and evidence integrated. |
| SRC-002 | DYEC P2 | Make P2 the explicit default and accept valid capacity/throughput pairs including 14,400/1000 | SUCCESS | feature_implementation | Gate 2 | orchestrator | Source/payload defaults now use cluster-bound P2 4,800/250; validator accepts AWS P2 tiers and 14,400/1000; exact fifth config `config/daylily_ephemeral_cluster_ifx_p2_1000_144_20260715.yaml` resolves to 14,400 GiB and 1000 MB/s/TiB |  | Source complete; release pending. |
| SRC-003 | DYEC catalog | Pin default DayOA and HIOMRS command-catalog refs to `11.0.6` in source and packaged payload | SUCCESS | feature_implementation | Gate 2 | orchestrator | Source and packaged catalogs pin default plus both HIOMRS commands to DayOA `11.0.6`; focused catalog/fork tests passed before refresh integration |  | Source complete; release pending. |
| SRC-004 | DYEC cost controls | Integrate authoritative dedicated-cluster CUR refresh so stale usage is repaired without fabricated timestamps | SUCCESS | feature_implementation | Gate 2 | orchestrator | Added fail-closed `dyec cost-centers refresh-usage`; 162 focused tests passed. Dry-run and live refresh each read 838 EC2 CUR rows; DDB readback is `$401.88672953969999999994924` through `2026-07-15T06:00:00Z`. | The tested command existed only on an older internal line and was absent from `sentieon-single`. | Live admission restored without changing either `$750` cap. |
| REL-001 | DYEC release | Focused/full validation, commit, push branch, and cut next unused annotated pin release | SUCCESS | contract_test | Gate 3 | orchestrator | Full suite: `1540 passed, 11 skipped`; focused Ruff clean; source/payload comparisons, exact fifth-config YAML assertions, and `git diff --check` passed; release commit `878f595e3844a60a00580d7c85ee7f6c19eb60d6`; annotated tag `10.3.8` |  | First release commit and annotated tag complete. |
| REL-002 | DYEC self-pin | Advance source and packaged DYEC self-pin to REL-001, validate, commit, push, and cut next patch tag | RUNNING | contract_test | Gate 3 | orchestrator | Source and packaged global config plus fork-contract test now pin `10.3.8` |  | Focused validation, commit, push, and next annotated tag pending. |
| SACCT-001 | `ifx-p2-250-0714` | Attach supported Slurm accounting without interrupting the comparison run | OPEN | contract_test | Gate 4 | orchestrator | `AccountingStorageType=(null)`; supported `dyec slurm-accounting attach` requires `CREATE_COMPLETE` plus a stopped compute fleet | Active exact-tag controller owns running scope; fleet will be stopped only after the workflow is terminal and the queue is empty. | Deferred, not skipped. |
| SACCT-002 | `ifx-sacctoff-1037` | Attach supported Slurm accounting without interrupting the comparison run | OPEN | contract_test | Gate 4 | orchestrator | `AccountingStorageType=(null)`; supported `dyec slurm-accounting attach` requires `CREATE_COMPLETE` plus a stopped compute fleet | Active exact-tag controller owns running scope; fleet will be stopped only after the workflow is terminal and the queue is empty. | Deferred, not skipped. |
| SACCT-003 | `ifx-20260719h` | Verify existing Slurm accounting | SUCCESS | contract_test | Gate 4 | orchestrator | `AccountingStorageType=accounting_storage/slurmdbd`, accounting host `ip-10-0-0-56`, port `6819`; `sacct` responds |  | Accounting already attached. |
| SACCT-004 | `sent-hg003-5x-0712` | Verify existing Slurm accounting | SUCCESS | contract_test | Gate 4 | orchestrator | `AccountingStorageType=accounting_storage/slurmdbd`, accounting host `ip-10-0-0-203`, port `6819`; `sacct` shows current jobs 1149-1153 |  | Accounting already attached and active. |
| SACCT-005 | Fifth cluster | Enable Slurm accounting in the creation contract | SUCCESS | feature_implementation | Gate 4 | orchestrator | Exact fifth config sets `slurm_accounting_enabled=true` |  | Creation will attach accounting through the supported declarative path. |
| AWS-001 | Fifth cluster | Validate quota/cap/config and create 14,400-GiB P2-1000 cluster without fallback | OPEN | feature_implementation | Gate 4 | orchestrator | Existing P2 use 4,800 GiB; five ParallelCluster records currently exist including one failed record |  |  |
| RUN-005 | Fifth cluster | Verify head/compute FSx contract and launch the identical HG003 1x HIOMRS controller | OPEN | feature_implementation | Gate 5 | orchestrator | Pending AWS-001 and submission-cost-center proof |  |  |
| ACC-001 | Acceptance | Track controller, queue, final MultiQC/evidence, wall time, benchmark cost, and FSx shape for all runs | OPEN | contract_test | Gate 6 | orchestrator | Pending terminal runs |  |  |

## Speed comparison baseline

- The accepted predecessor root is
  `/fsx/analysis_results/sent-hg003-5x-0712/hg003-1x-hiomrs-1105-20260714T230848Z`
  on 1,200-GiB `SCRATCH_2`.
- End-to-end analysis-root timestamp to final evidence manifest was
  `2026-07-14T23:08:48Z` to `2026-07-15T03:35:23Z`, or `4:26:35`.
- The first recorded Snakemake attempt began at `2026-07-14T23:15:42Z`; the
  final log closed at `2026-07-15T03:35:33Z`, a multi-attempt controller span
  of `4:19:51`.
- Its final benchmark summary contains 131 priced rows totaling `$4.609317` in
  task-attributed benchmark cost.
- Final comparative conclusions remain open until the four exact-tag runs reach
  the same final evidence gate. Cold conda-environment creation is tracked
  separately from compute-phase time because the first three clusters did not
  have the tag's environments cached while the existing `sent-*` headnode did.

## Exact workflow contract

- Genome: `hg38`.
- Targets: `produce_hiomrs produce_snv_concordances produce_tiddit_sv_vcf
  produce_alignstats produce_relatedness produce_peddy
  produce_gatk_contam_estimate produce_site_mix_contam_estimate produce_vep
  produce_htd_calls produce_smn12_orthogonal_calls produce_metagenomics
  produce_multiqc_all results/day/hg38/reports/DAY_final_multiqc.html
  results/day/hg38/reports/dayoa_evidence_manifest.json`.
- Config: `aligners=["sent"]`, `dedupers=["na"]`,
  `snv_callers=["hiomrs"]`, `sv_callers=["tiddit"]`,
  `htd_callers=["smn12"]`, and final MultiQC tools `vep`,
  `unmapped_metagenomics_ganon2`, `gatk_contam`, `site_mix`, `peddy`.
- Flags: `-j 250 -p -T 0 --rerun-triggers mtime --rerun-incomplete`; dry-run
  adds only `-n`. No `-k`.
- Every controller is an interactive `ubuntu` bash login shell in one persistent,
  meaningfully named tmux pane. Commands remain separate: `source dyoainit`,
  `dy-a slurm hg38`, and `dy-r ...`.

## Completion condition

Starting a tmux session or seeing an empty queue is not success. A run succeeds
only with controller rc 0, final `DAY_final_multiqc.html`, final MultiQC data,
and `dayoa_evidence_manifest.json`. The overall objective also requires a
terminal fifth-cluster create result and every ledger row in a terminal state.
