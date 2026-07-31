# SHM Partitions And Partition-Aware Local Publication Ledger

Controlling plan: this ledger  
Ledger path: `docs/plans/20260731T101016Z_shm_partitions_and_local_publish_ledger.md`

## Objective

Add `i128shm`, `i192shm`, and `i384shm` to every actively packaged CPU-analysis
cluster AZ/config, and make DayOA compute-local claiming/publication select
`/scratch` for NVMe partitions and `/dev/shm` for SHM partitions. Selection must
use the actual Slurm allocation so grouped jobs obey the node/partition that
actually ran them. Missing or mixed partition identity must fail explicitly.
Compute-local trees must be removed by traps, and selection/publication/cleanup
messages must reach rule logs and therefore Snakemake's captured job output.

## Gate 0: inventory freeze

- DYEC repo: `/Users/jmajor/.codex/worktrees/7731/daylily-ephemeral-cluster`,
  branch `codex/dyec-create-defaults-16.1.18`; pre-existing untracked files are
  the `20260731T090555Z` through `20260731T095832Z` analysis artifacts and are
  preserved.
- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`, branch
  `codex/feat-hiomr2-sentieon-cli-fidelity-13.0.72`; clean at baseline.
- The user clarified that the queue target is the 30 Intel templates across 15
  AZs plus the active DRAGEN template in `us-west-2b` (31 files total). The
  `sentieon-single` `us-west-2c` template is explicitly outside scope.
- Current Intel templates already carry memory-qualified `i128mem` and
  `i192mem` type sets; new SHM queues require the explicit thresholds 468 GiB,
  468 GiB, and 968 GiB and may include instance-store types.
- Current HIOMR2 source accepts only NVMe partition names, requires configured
  roots below `/scratch`, claims through the NVMe-only
  `daylily_omics_analysis.hiomr2_scratch` wrapper, and publishes through
  `workflow/scripts/hiomr2_publish.py`, which hard-codes `/scratch`.
- `workflow/scripts/publish_scratch_directory.py` also defaults to `/scratch`.
- Prior production evidence showed that a controller-wide `/dev/shm` TMPDIR
  leaks into headnode Conda/pip setup and fails before compute work. This change
  must remain inside allocated compute jobs.
- Baseline execution is local-only. No cluster creation, Slurm intervention,
  AWS resource mutation, DayOA controller, or live workflow run is authorized
  or required.

## Control ledger

| ID | Repo/area | Requirement | Status | Category | Gate | Owner | Evidence | Root cause | Terminal note |
|---|---|---|---|---|---|---|---|---|---|
| INV-001 | Cross-repo | Freeze repo state, active config inventory, publisher/claim surfaces, and controller TMPDIR boundary. | SUCCESS | config_or_startup_contract | Gate 0 | orchestrator | Gate 0 above; `INTEL_TEMPLATE_REGION_AZS`; source sweeps for queue names, `/scratch`, publishers, and traps. |  | Inventory recorded before runtime edits. |
| DYEC-001 | DYEC configs | Add all three SHM queues to all 30 packaged Intel AZ templates with threshold-qualified, AZ-valid x86 CPU types and explicit max-count substitutions. | SUCCESS | feature_implementation | Gate 2 | orchestrator | `20260731T101016Z_refresh_shm_partitions.py --check`: 30 Intel templates, zero drift. |  | Source and packaged mirrors updated. |
| DYEC-002 | DRAGEN config | Add all three SHM queues to the active `us-west-2b` DRAGEN template, preserving its custom AMI and RHEL/DRAGEN node bootstrap contract; remove the mistakenly generated queues from Sentieon-single. | SUCCESS | feature_implementation | Gate 2 | orchestrator | DRAGEN validator and packaged-default contract pass; Sentieon-single exclusion test passes. |  | Corrected target is Intel plus DRAGEN. |
| DYEC-003 | DYEC validation | Prove every targeted Intel/DRAGEN template has exactly one `i128shm`, `i192shm`, and `i384shm`, no `/scratch` mount on SHM queues, correct vCPU/memory/AZ offerings, and mirrored packaged resources. | SUCCESS | contract_test | Gate 5 | orchestrator | Live read-only EC2 offering refresh check; 37 focused tests passed; `git diff --check` passed. |  | Full DYEC suite: 2419 passed, 11 skipped, 28 unrelated branch-baseline failures. |
| DOA-001 | DayOA root resolution | Add one strict partition-to-local-root contract: actual `SLURM_JOB_PARTITION` selects `/scratch` for NVMe and `/dev/shm` for SHM; mixed/unknown/missing identity fails. | SUCCESS | active_product_contract | Gate 4 | orchestrator | `tests/test_local_work.py`; NVMe/SHM and hard-failure cases pass. |  | Runtime allocation identity is authoritative. |
| DOA-002 | DayOA claiming | Allow HIOMR2 claims on verified tmpfs `/dev/shm` while retaining strict NVMe verification on `/scratch`, owner metadata, capacity checks, and no fallback. | SUCCESS | feature_implementation | Gate 4 | orchestrator | Tmpfs, capacity, owner metadata, and wrong-filesystem tests pass. |  | NVMe claimant remains unchanged and delegated. |
| DOA-003 | DayOA publishers | Make file and directory publishers validate sources beneath the root selected from the actual partition, including grouped jobs. Emit start/success details to stdout/stderr. | SUCCESS | feature_implementation | Gate 4 | orchestrator | Both publisher tests pass for selected media; start/complete messages asserted. |  | No alternate-root discovery. |
| DOA-004 | DayOA rules | Admit SHM partitions, select the compute-local root inside job shells, retain cleanup traps on EXIT/INT/TERM, and log selection/publication/cleanup to durable rule logs/core-captured output. | SUCCESS | feature_implementation | Gate 4 | orchestrator | Main HIOMR2 has 10 claims/10 cleanup traps; faithful lane has 7/7; grouped Jasmine uses failure cleanup plus final EXIT cleanup and tee logging. |  | Mixed storage classes are rejected for DAG-visible grouped outputs. |
| ACC-001 | Cross-repo acceptance | Run syntax, focused contracts, config inventory/validation, full relevant test suites, diff checks, PR checks, and merge both repos to `main`. | IN_PROGRESS | contract_test | Gate 5 | orchestrator | DayOA relevant suite 148 passed; DYEC focused 37 passed; both diff checks passed. |  | Awaiting commits, PR checks, and merges. |

## Assumptions

- “All currently supported cluster AZs” means the 30 active Intel templates and
  the active DRAGEN `us-west-2b` template. It excludes archived, legacy root
  DRAGEN/RHEL, and Sentieon-single templates.
- SHM roots are compute-job-local `/dev/shm/dayoa/...`; the headnode/controller
  runtime remains under `/tmp/dayoa-runtime/...`.
- An ordered list containing both NVMe and SHM partitions is allowed for Slurm
  placement only when the runtime resolver uses the single actual
  `SLURM_JOB_PARTITION`. Static resolution of a mixed candidate list is
  forbidden.
