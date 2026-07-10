# DRAGEN Export, Recreate, And Betelgeuse Five-Sample Ledger

Created: `2026-07-10T19:26:46Z`

Controlling request: after the active HG003 native-DRAGEN concordance
controller completes, preserve and push DRAGEN-related source changes, verify
the private operational AMI remains account-private, export all required
`dragain11` FSx results to S3, delete `dragain11`, create a replacement private
mixed DRAGEN/CPU cluster, mount the Betelgeuse ILMN and ONT run prefixes, and
run `HG002`, `HG003`, `NA19235`, `NA20775`, and `NA23687` through native DRAGEN,
hybrid variant calling, SNV concordance, SMN callers, ExpansionHunter, routine
QC, reporting, and final S3 export.

## Gate 0

| Surface | Evidence |
|---|---|
| Current cluster | `dragain11`, `us-west-2`, `CREATE_COMPLETE`, compute fleet `RUNNING`, headnode `i-0684060a8c71c339a`, FSx `fs-09ff0f6f0412bc7d9`. |
| Active controller | Terminal success. `dragen_hg003_conc_dragain11_20260710` completed, native DRAGEN job `7` and RTG concordance completed, and the Slurm queue drained. |
| HG003 native outputs | Non-empty 72,469,974,208-byte BAM, 451,596,448-byte SNV VCF, 2,004,111,962-byte gVCF, indexes, native validation JSON, and `giab_concordance_mqc.tsv`; no partial files. Primary GIAB HC `All` F-score: `0.999079967406051`; SNP transition/transversion F-scores: `0.9992405988623179` / `0.9989431693637525`. |
| Prior native proof | HG002 native SNV completed under DayOA `10.0.83`; license/FPGA/memlock validation is terminal success. |
| Current mounts | Reference DRA and ILMN BCLConvert FASTQ DRA are available; no ONT DRA is attached to `dragain11`. |
| Private image | Child `ami-046ab49ce477823fe` is owned by account `108782052779`, `Public=false`, and has no launch permissions. Snapshot `snap-0c4395d45b0d99d73` has no create-volume permissions. |
| Cost center | `dragen-followup-20260710`, active, cap `$250`; current CUR snapshot reports `$0` through `2026-07-10T15:00:00Z` and is not real-time. |
| Sample set | `HG002`, `HG003`, `NA19235`, `NA20775`, `NA23687`. Truth expectations for SMN1/SMN2 are `2/2`, `2/2`, `4/0`, `3/1`, `1/2`. |
| ILMN source | `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/Analysis/1/Data/BCLConvert/fastq/`; all five samples have eight R1 and eight R2 lane FASTQs. |
| ONT sources | Full Set3 FC1/FC2/FC3 for `NA19235` and `NA20775`; full Set4 FC1/FC2/FC3 for `HG002`, `HG003`, and `NA23687`. Prior partial/24-hour manifests are not accepted. |
| Git boundary | Public AlmaLinux branches are clean. DayOA native DRAGEN work is pushed to `origin/jem-dev` through annotated tag `10.0.84`. DYEC operational work is pushed to `origin/jem-dev` through annotated tag `10.0.147`; `jem-dev` subsequently advanced to `10.0.148`. Mixed-queue work remains isolated on `codex/dragen-hybrid`. |
| Destructive gate | User explicitly approved deletion of `dragain11` in `us-west-2` after successful exports. Both required exports are now independently verified, so live deletion is authorized after the mixed-queue PR is published and the final empty-queue/dry-run checks pass. |

## Control Ledger

| ID | Requirement | Status | Evidence / Next Gate |
|---|---|---|---|
| CUR-HG003-001 | Finish HG003 native SNV concordance and verify aggregate metrics. | SUCCESS | Controller completed, queue drained, `giab_concordance_mqc.tsv` exists, primary GIAB HC `All` F-score is `0.999079967406051`, and SNP transition/transversion F-scores are `0.9992405988623179` / `0.9989431693637525`. |
| GIT-DAYOA-001 | Commit and push all DRAGEN-related DayOA changes without unrelated dirty work. | SUCCESS | Native DRAGEN/memlock release `d831c5b` is included in `origin/jem-dev` commit `90adbd5`, annotated tag `10.0.84`. |
| GIT-DYEC-001 | Commit and push all DRAGEN-related DYEC code, config, tests, manifests, and ledgers without unrelated dirty work. | IN_PROGRESS | Operational releases are pushed through `10.0.149`; mixed `dragen`/CPU partition support was committed as `939b4520`, pushed on `codex/dragen-hybrid`, and merged by PR `#7` into `jem-dev` at `fc1978ae`. Replacement-cluster config, current ledger evidence, and the lock-initialized `day-clone` fix remain to be committed and merged. |
| AMI-PRIVATE-001 | Keep private child AMI and snapshot LSMC-account-only. | SUCCESS | Image and snapshot have no public or cross-account permissions. |
| EXPORT-OLD-001 | Export every required completed `dragain11` analysis root to a new empty S3 destination and verify receipts. | SUCCESS | HG002 task `task-044d48709a8970750` and HG003 task `task-0036549a5bab2a9f5` both `SUCCEEDED`; both temporary DRAs detached with lifecycle `DELETED`; both receipts record `delete_data_in_file_system: false`. S3 inventories: HG002 `1924` objects / `14239363777` bytes; HG003 `2481` objects / `78461853721` bytes. |
| DELETE-OLD-001 | Delete `dragain11` only after export verification and second approval. | SUCCESS | Final queue was empty; delete dry-run passed; exact approval was applied. DYEC removed heartbeat resources, ParallelCluster reached terminal deletion, and FSx `fs-09ff0f6f0412bc7d9` no longer exists. Exported/source S3 prefixes were not deleted. |
| MIXED-TEMPLATE-001 | Add a private EFA-disabled mixed template with `dragen`, `i192`, and `i192nvme` partitions. | SUCCESS | Source and packaged templates contain exact queues `dragen`, `i192`, and `i192nvme`; CPU bootstrap skips DRAGEN device validation while DRAGEN nodes remain fail-hard. Focused tests: `5 passed`; broader workflow/default/headnode/pricing tests: `162 passed`; Ruff, Bash syntax, YAML parse, and `git diff --check` passed. PR `#7` merged normally after all CodeQL checks passed. |
| CREATE-NEW-001 | Create replacement cluster in `us-west-2b` under the active `$250` cost center. | SUCCESS | `dragain12` reached `CREATE_COMPLETE` in 24m44s. Headnode `i-0222f73126d42ef9` (`10.0.1.84`) uses `r7i.2xlarge`; the mixed template has one-node maxima for `dragen`, `i192`, and `i192nvme`. Preflight passed 14 checks, ParallelCluster dry-run passed, and private AMI/secret/reference/budget gates passed. |
| SOURCE-BUNDLE-001 | Seed exact private DYEC and DayOA releases without placing personal GitHub credentials on the cluster. | SUCCESS | AES256-encrypted immutable S3 bundles were verified by exact byte size and SHA-256, then cloned on the headnode at DYEC `10.0.149` (`08f21590`) and DayOA `10.0.84` (`90adbd5`). The local-only Git URL rewrite points DayOA clone requests to the exact seeded repository. No personal SSH key or PAT was copied. |
| DRAGEN-SMOKE-001 | Prove native DRAGEN device and license operation on one replacement-cluster f2 node. | SUCCESS | Slurm job `1` ran alone on partition `dragen`; native DRAGEN `13.031.818.4.5.4` initialized and the supported `dragen_lic` query exited `0`. Genome entitlement is active, with `4.6 Tbases` remaining of `5.0 Tbases`, expiry `2026-11-01`. Credential contents were not printed. |
| MOUNT-ILMN-001 | Mount and verify the exact ILMN BCLConvert FASTQ prefix read-only. | IN_PROGRESS | DRA `dra-0308b51ae189f35a1` is `CREATING`; waiter uses `--timeout-seconds 5400`. Source inventory proves eight R1 and eight R2 lane FASTQs for each of the five samples. |
| MOUNT-ONT-001 | Mount and verify all six exact ONT Set3/Set4 flow-cell prefixes read-only. | IN_PROGRESS | DRAs `dra-0160c72eb42da82b6`, `dra-04c2a667f482cab64`, `dra-015b7101ecb16bc9f`, `dra-06ccb2b86e3c92e9e`, `dra-0350b4f45c18fcdce`, and `dra-0b32994c9e77325b8` are `CREATING`; each waiter uses 5400 seconds. Source inventory proves 73 `fastq_pass` files per relevant barcode per flow cell, or 219 per sample. `fastq_fail` is excluded. |
| CLONE-LOCK-001 | Allow `day-clone` to populate a newly lock-initialized analysis root without weakening existing-destination protection. | SUCCESS | `day-clone` now accepts only an existing root whose sole entry is non-symlink `.dayoa_agent` with a non-symlink `write.lock` directory; any analysis data still fails hard. Source/package copies match; 42 focused tests, Ruff, Python compile, and `git diff --check` passed. |
| MANIFEST-001 | Rebuild exact five-sample hybrid manifests from mounted full inputs. | PENDING | Eight ILMN pairs per sample; complete ONT FASTQ lists; truth and biological metadata preserved. |
| DRYRUN-001 | Dry-run the complete target set and inventory jobs, partitions, unsupported rules, and projected cost. | PENDING | No live launch until all rules map to available partitions and bounded cost is compatible with `$250`. |
| RUN-DRAGEN-001 | Run native DRAGEN all-callers including SNV/gVCF/CNV/SV/targeted/SMN/HLA/repeat/MRJD. | PENDING | Serial native DRAGEN workload; stop on license, FPGA, reference, memlock, or infrastructure failure. |
| RUN-HYBRID-001 | Run hybrid Sentieon SNV/SV/CNV/mito/SMN1 segdup outputs. | PENDING | Full ILMN+ONT manifests only. |
| RUN-SMN-001 | Run short-read SMNCopyNumberCaller plus supported orthogonal SMN callers and aggregate evidence. | PENDING | Include `smn12`, `smaca`, and `sma_finder`; include hybrid Sentieon SMN1 segdup and native DRAGEN SMN. Unsupported Parascopy remains excluded unless validated resources exist. |
| RUN-QC-001 | Run ExpansionHunter, concordance, routine QC/reporting, and evidence manifest. | PENDING | Include `produce_expansionhunter`, `produce_snv_concordances`, MultiQC, and evidence manifest; broaden only after dry-run proves supported inputs/resources. |
| EXPORT-NEW-001 | Export completed replacement-cluster analysis to S3 and verify receipt/inventory. | PENDING | No cleanup until export task `SUCCEEDED`, DRA detached, and S3 inventory is non-empty. |
| FINAL-001 | Terminalize every row and report exact completed outputs, tags, costs, exports, and remaining blockers. | PENDING | Objective is not complete while any required run/export row is non-terminal. |

## Safety And Scope Contracts

- Never print credential contents or credential-bearing URLs.
- Never invoke raw Snakemake; use `dy-r` in persistent interactive `ubuntu`
  tmux sessions with explicit DayOA tags and analysis-root locks.
- Do not stage or commit unrelated dirty files from shared worktrees.
- Do not infer or silently substitute missing sample, mount, truth, reference,
  caller-resource, partition, or export paths.
- Do not delete FSx, S3 objects, mounts, AMIs, snapshots, or clusters without
  the required destructive-action approval.
- The `$250` cost-center cap is a hard launch boundary. CUR usage lag is recorded
  explicitly and is not treated as real-time zero cost.
