# CPU-only Slurm placement and native final MultiQC execution ledger

Started: 2026-07-13T22:08:11Z
Operator: Codex
Cluster scope: `sent-hg003-5x-0712` (`us-west-2`, AWS profile `lsmc`)
Controlling request: implement CPU/partition-only Slurm placement, publish immutable boot assets, update the idle cluster, adopt native final MultiQC, and prove the result with a fresh exact-version HG003 1x HIOMRS kitchensink run.

## Gate 0 inventory freeze

- DYEC checkout: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster-sentieon-single`, branch `sentieon-single`, HEAD `9317906a4ee62d9806327b3e7dc33459eb0f3c61`, equal to `origin/sentieon-single`, describe `10.3.5-11-g9317906a-dirty`.
  - Pre-existing tracked change: `docs/plans/20260713T083000Z_sent_hg003_hiomrs_kitchensink_1x_monitor_ledger.md`.
  - Pre-existing untracked files: runtime-cache publisher and Bjuice campaign ledger/artifact directory. Preserve unless directly required.
- DayOA checkout: `/Users/jmajor/projects/lsmc/daylily-omics-analysis-sentieon-single`, branch `sentieon-single`, HEAD `7ee2872dfd99d67b28b380b0fcd25dfaa82fc7b4`, equal to `origin/sentieon-single`, describe `11.0.0-dirty`.
  - Existing modified rules/config/tests and untracked resource-tuning tests are user-approved runtime fixes. Reconcile intentionally; do not overwrite or discard.
  - Existing scratch directories `jemxxx_tmp/` and `tmp_sent-singleton/` are excluded.
- MultiQC checkout: `/Users/jmajor/projects/lsmc/multiqc-samples-hybrid-qc-20260712`, branch `codex/snakemake-samples-hybrid-qc`, HEAD `2fcad4e380de1d620844837c8913b935ef957a6f`, describe `1.36.dev0-lsmc.6-5-g2fcad4e3-dirty`.
  - The native Samples/Benchmarks implementation and supporting parser changes are the intended proven release candidate.
  - `.playwright-cli/` is excluded. Push explicitly to `origin/codex/snakemake-samples-hybrid-qc`; the configured upstream is stale and unrelated.
- Current infrastructure inventory from the approved planning pass found one running cluster: `sent-hg003-5x-0712`, ParallelCluster 3.15.0, Ubuntu headnode `i-04059f0d8c4f701d2`. Live Slurm already reported `SelectTypeParameters=CR_CPU`, but DayOA still emitted explicit memory requests and the cluster had no server-side memory-request blocker.
- 2026-07-13T22:09Z live refresh: cluster/stack `UPDATE_COMPLETE`, compute fleet `RUNNING`, only the headnode instance exists, `squeue` is empty, no DayOA/Snakemake controller process exists, and no tmux server exists. Slurm reports `CR_CPU`, unlimited default/max memory, `JobSubmitPlugins=(null)`, and the four partitions `i96nvme`, `i128nvme`, `i192nvme`, and `i384nvme`.
- Live hook inspection: ParallelCluster already owns `/opt/slurm/etc/scripts/prolog.d/*` and `epilog.d/*` dispatcher entries. The directories are empty, while the old post-install appended duplicate `/opt/slurm/sbin/prolog.sh` and `epilog.sh` lines to `slurm.conf`. The replacement will install the DayEC hooks into the owned directories and let the ParallelCluster update remove those direct config edits.
- Immutable boot-assets base: `s3://lsmc-dayoa-references-usw2/runtime_assets/cluster_boot_config/releases/`. Implementation audit added a seventh object, `install_slurm_job_submit_policy.sh`, so the live headnode and future boot actions use the same atomic policy installer without rerunning a full post-install script or duplicating install logic.
- Remote release-name check at 2026-07-13T22:12Z: `1.36.dev0-lsmc.7`, `11.0.1`, and `10.3.6` are all absent. The immutable boot-assets base currently contains only release `sha256-2f2578f6469fe4668a3fc86d9520b6a57060989c33c010e018caff5821e5ec8f`.
- No analysis-root deletion, S3 overwrite/delete, budget mutation, tag movement, or force push is authorized.

## Tracking rows

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence / terminal note |
|---|---|---|---|---|---|---|---|
| CPU-001 | DYEC templates | Every source/payload Slurm template explicitly disables memory scheduling, contains no `SchedulableMemory`, declares nonexclusive queues, and enables the Lua guard | SUCCESS | feature_implementation | Gate 2 | slurm agent | All 59 source/payload/archive Slurm YAMLs structurally validated: explicit false, zero `SchedulableMemory`, every queue nonexclusive, exact declarative custom settings. |
| CPU-002 | DYEC bootstrap | Ubuntu/RHEL/Alma assets install policy/hooks without rewriting `slurm.conf` or restarting Slurm | SUCCESS | feature_implementation | Gate 2 | slurm agent | Ubuntu/RHEL use the immutable policy installer and managed `prolog.d`/`epilog.d` hooks; Alma delegates to RHEL. Negative scans found no direct Slurm config mutation or restart. |
| CPU-003 | DYEC submit guard | Wrapper and controller reject memory requests; all non-memory scheduling arguments pass unchanged | SUCCESS | feature_implementation | Gate 4 | slurm agent | Wrapper rejects memory flags and preserves `--exclusive`/other inputs. `job_submit.lua` checks submit and modify requests, with nil/`NO_VAL64` unset handling verified against the Slurm API contract. |
| CPU-004 | DayOA | Remove Slurm memory/default placement and pass exact partition/thread resources without resolver or group substitutions | ATTEMPTING_BUGFIX | feature_implementation | Gate 4 | DayOA agent | Initial implementation passed 747 tests, but orchestrator scan found eight residual utility `#SBATCH --mem` directives, missing `--mem-per-tres` rejection, an exclusive-flag rewrite, and default partition names absent from the live four-queue catalog. A concrete cleanup/test pass is underway. |
| CPU-005 | Regression | Add static/unit/cross-contract blockers preventing memory placement and scheduling rewrites from returning | IN_PROGRESS | contract_test | Gate 5 | orchestrator | DYEC focused suite 74 passed; relevant integration suite 300 passed plus workflow 137 passed. DayOA regression expansion is in progress for the residual findings. |
| AWS-001 | S3 | Publish one immutable six-object boot release with verified content hashes | OPEN | config_or_startup_contract | Gate 2 | orchestrator | Never update mutable prefixes or delete prior releases. |
| AWS-002 | Cluster | Update the idle `sent-hg003-5x-0712` cluster and verify CPU-only policy live | OPEN | config_or_startup_contract | Gate 2 | orchestrator | Current implementation request is the second approval for the exact fleet-stop/controller-reconfigure plan. Reconfirm idle immediately before mutation. |
| MQC-001 | MultiQC | Freeze, test, commit, push, and annotate `1.36.dev0-lsmc.7` from the proven native module source | SUCCESS | feature_implementation | Gate 5 | MultiQC agent | Source fingerprint `6d1b33732b790cd04ce9bdc8e4b06f63b5d0553c81df036b41452ac187a9f517` matched the proven wheel payload. Commit `39c5c49e34be039eb8e676de6b940dda05350b5e` is pushed on `origin/codex/snakemake-samples-hybrid-qc`; annotated tag object `f91cc430b8163d5173d3cf7514d131ba42c89918` peels to it. 55 focused tests, Ruff, MyPy, code checks, npm byte-parity build, package builds, and strict renders from the local commit and fetched tag archive passed. `.playwright-cli/` and later unrelated Dewey-share artifacts remain untracked. |
| MQC-002 | DayOA | Adopt native Samples/Benchmarks, strict final render, benchmark rejection ledger, and canonical outputs | OPEN | feature_implementation | Gate 4 | orchestrator | Starts only after AWS-002 proves live memory placement off. |
| REL-001 | DayOA | Commit/push the green integration and create annotated release `11.0.1` | OPEN | feature_implementation | Gate 5 | orchestrator | If an immutable candidate fails, fix and use the next patch; never move it. |
| REL-002 | DYEC | Update both command catalogs and, only after live 1x success, set validation metadata and tag `10.3.6` | OPEN | feature_implementation | Gate 5 | orchestrator | Source/package catalog parity required. |
| LIVE-001 | HG003 1x | Fresh exact-version kitchensink run reaches controller rc 0 and canonical MultiQC/evidence outputs | NO_LONGER_NEEDED | plan_amendment | Gate 5 | orchestrator | Superseded at 2026-07-13T22:28Z by the user's request to restart full-coverage HG001-HG007 from scratch on the newest release. Static, held-job, command-catalog dry-run, and compute smoke gates remain mandatory before the larger launch. |
| LIVE-002 | HG001-HG007 | Launch seven fresh full-coverage Bjuice prevalidation ILMN+ONT HIOMRS kitchensink analyses from the newest exact DayOA release | OPEN | feature_implementation | Gate 5 | orchestrator | Use separate fresh roots/controllers and one sample/unit row per root; reuse no partial output directory. Launch as mounts allow after exact catalog dry-runs. |
| LIVE-003 | HG001-HG007 | Monitor all seven controllers to terminal canonical MultiQC/evidence outputs and record fixes/costs | OPEN | contract_test | Gate 5 | orchestrator | Queue emptiness or partial rule completion is insufficient. Runtime defects require a source fix, tests, a new immutable patch tag when needed, and supported `dy-r` relaunch. |

## Acceptance contract

- Generated DayOA submissions contain no Slurm memory request and preserve exact partition ordering and thread counts.
- Live Slurm reports `CR_CPU`, `JobSubmitPlugins=lua`, and nonexclusive partitions; positive CPU/partition probes pass and all memory-request forms fail explicitly.
- Final MultiQC uses the native modules in strict mode while preserving `DAY_final_multiqc.html`, its data directory, and `dayoa_evidence_manifest.json` for every fresh HG001-HG007 analysis.
- All rows must reach terminal status. A failed immutable release is retained and superseded by the next version rather than moved.
