# Sent HG003 HIOMRS kitchensink 1x monitor ledger

Started: 2026-07-13T08:26:44Z
Local checkout: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster-sentieon-single`
Cluster: `sent-hg003-5x-0712` (`us-west-2`, profile `lsmc`)
Analysis root: `/fsx/analysis_results/sent-hg003-5x-0712/hg003-1x-ks-10102-20260713T071044Z`
Controller tmux: `hiomrs-10102-1x`
Mode: monitor and operate to green. Runtime source fixes and supported `dy-r` retests are authorized under the existing analysis-root write lock. Slurm/node administration, destructive filesystem/AWS actions, and budget changes remain unauthorized. Commit and push are gated on end-to-end live proof.

## Gate 0 inventory and baseline

- Connected through `dyec headnode connect`/SSM as `ubuntu` to headnode `i-04059f0d8c4f701d2` (`ip-10-0-0-203`).
- Required read visit recorded with `dyec analysis visit --mode read` for the exact analysis root.
- Existing write-lock owner: `codex-hiomrs-10102-1x-rerun`, tmux `hiomrs-10102-1x`, pane `%20`, intent `rerun HG003 1x with patched TIDDIT runtime temp validation`. Do not take over this lock; use the owning pane for any post-failure runtime fix/retest.
- Controller shape: one tmux window, one live pane, cwd at the DayOA checkout under the analysis root.
- Controller command: HG003 `SR1x-ONT1x` HIOMRS kitchensink, `hg38`, `-j 100`, `-T 0`, `--rerun-triggers mtime`, `--rerun-incomplete`; targets include HIOMRS, concordance, TIDDIT, alignstats, relatedness, peddy, both contamination paths, VEP, SMN12, Ganon2 metagenomics, MultiQC, and evidence artifacts.
- Initial workflow evidence: controller advanced from `20/126` at 08:20Z to `26/126` at 08:22:54Z.
- 08:32Z progress sample: master log advanced through `35/126` (28%). The literal `ERROR:` match in the tail was part of an unevaluated rule shell snippet, not a reported failure. Job 126 remained active in HIOMRS core; its log had reached conda activation after staging the validation/copy commands. No terminal failure signal was present.
- Initial Slurm evidence: jobs 125 (`relatedness_batch_somalier_extract`, 1 CPU) and 126 (`GROUP-hiomrs_core`, 192 CPUs) were `RUNNING` with `Reason=None`, `Restarts=0`, and two allocated `i192nvme` nodes.
- Initial node evidence: FSx was 10% used and `/scratch` 1% used on both allocated nodes. Bounded Glances samples and OS counters showed Somalier using one CPU on node 1 and the HIOMRS driver using the large allocation on node 2. These are point-in-time observations only.
- Budget text emitted by the controller: cluster total `$450`, used `$52.926` (11.76%); cost-center report was stale by 18.38 hours and is not treated as current spend truth.
- Local DYEC baseline: branch `sentieon-single`, commit `8d9b27e744942f686d3cb8934ee3a2441d2edfef`; tracked tree clean; pre-existing untracked `docs/plans/20260712T192000Z_sent_hg003_runtime_cache_publish.py` preserved.
- Headnode DYEC baseline: branch `sentieon-single`, clean commit `01452ed3edd35e693b56b1f0d79b6d6b625cbda2`, four commits behind local (`6efcc52b`, `887c99dc`, `4acfe67d`, `8d9b27e7`). Exact DYEC version match: **no**.
- Local DayOA baseline: branch `sentieon-single`, commit `d5a5110610fd95e4cae687a546086fc2e67f1e6d`, with a tracked runtime-temp helper modification plus pre-existing untracked tests/scratch directories.
- Active DayOA baseline: detached at the same commit `d5a5110610fd95e4cae687a546086fc2e67f1e6d`, with the same functional eight-line/two-line runtime-temp replacement but different comment text; source blob IDs are local `9050830...` vs active `242a5c6...`. Exact tracked working-tree match: **no**; base commit and executable logic observed in the delta match.

## Tracking rows

| ID | Requirement | Status | Category | Gate | Evidence / terminal note |
|---|---|---|---|---|---|
| MON-001 | Identify the one HG003 HIOMRS kitchensink 1x controller and exact analysis root | SUCCESS | contract_test | Gate 0 | `hiomrs-10102-1x`; one window/pane; controller cwd and command verified. |
| MON-002 | Record the required read visit before analysis-root monitoring | SUCCESS | legitimate_safety_handling | Gate 0 | `dyec analysis visit` returned `recorded read visit`. |
| MON-003 | Verify local/headnode DYEC and local/active DayOA identities | SUCCESS | contract_test | Gate 0 | Exact SHAs, branches, origins, dirty states, and diff/blob hashes recorded above; both exact-match checks failed. |
| MON-004 | Monitor controller progress, queue, current rule logs, and allocated-node telemetry | IN_PROGRESS | legitimate_safety_handling | Gate 5 | Baseline captured; continue bounded read-only samples until terminal workflow state. |
| MON-005 | Determine terminal outcome from controller plus outputs/evidence, not queue emptiness alone | OPEN | contract_test | Gate 5 | Requires `WORKFLOW SUCCESS`/return code and requested final artifacts, or exact terminal failure evidence. |
| FIX-001 | If the run fails, diagnose the first causal rule failure and patch the active DayOA checkout through the owning tmux/write-lock context | OPEN | feature_implementation | Gate 4 | No speculative edit while the current controller is running. Preserve generated outputs and unrelated dirty files. |
| FIX-002 | Reproduce each runtime correction through the supported `dy-r` controller path until the full 126-step kitchensink run is green | OPEN | contract_test | Gate 5 | Partial target success is insufficient; require full controller and artifact proof. |
| REL-001 | Reconcile verified runtime source/test changes back to the local `sentieon-single` checkout(s), run focused tests, commit, and push | OPEN | feature_implementation | Gate 5 | Authorized by user; remains gated on live end-to-end proof. Do not include unrelated untracked files. |

## Terminal-state rule

The objective is complete only when monitoring and any needed runtime-fix rows are terminal, the full test is proven green, verified code/tests are reconciled locally, and the intended commits are pushed. An empty Slurm queue by itself is not success.

Monitoring continuation: Codex task heartbeat `sent-hg003-hiomrs-1x-operate-to-green`, seven-minute cadence, attached to the current task. It must report meaningful changes only and stop after terminal completion.

## 2026-07-13T08:33:54Z stop amendment

The user requested that all controllers on the cluster be killed. The operate-to-green heartbeat was immediately paused. Fresh inventory found exactly one live DayOA controller process chain: PIDs `457623`, `461777`, `461778`, and `461779`, all in analysis `hg003-1x-ks-10102-20260713T071044Z` and tmux `hiomrs-10102-1x`. Slurm job `126` (`GROUP-hiomrs_core-nosample`, 192 CPUs on `i192nvme-dy-price192nvme-2`) was still running. The other 14 tmux sessions were live shell panes but had no `bin/day_run`/Snakemake controller processes and are not classified as controllers.

| ID | Requirement | Status | Category | Gate | Evidence / terminal note |
|---|---|---|---|---|---|
| AMD-001 | Supersede operate-to-green monitoring with the user's stop request | SUCCESS | plan_amendment | Gate 5 | Heartbeat paused; no relaunch/fix activity will run while stop scope awaits approval. |
| KILL-001 | Interrupt the one live controller chain through its owning tmux/write-lock context; verify resulting Slurm/controller state | BLOCKED | legitimate_safety_handling | Destructive second approval | Initial request is first approval only. Requires a second explicit approval after the exact controller, analysis root, and likely Slurm-job cancellation effect are restated. |

## 2026-07-13T08:37:00Z shutdown and cleanup manifest

- `KILL-001` completed after explicit second approval: controller wrappers were interrupted, surviving Slurm job `126` was canceled through `dyec analysis guard`, orphaned controller children exited, the temporary kill lock was released, and final `pgrep`/`squeue` checks were empty.
- After separate explicit approval for the exceptional tmux cleanup, `tmux kill-server` terminated all 15 inventoried sessions. Final `tmux list-sessions` reported no server.
- Preserve target analysis: `/fsx/analysis_results/sent-hg003-5x-0712/hg003-1x-ks-10102-20260713T071044Z` (2.3G).
- Preserve required ancestors and service/audit directories: `/fsx/analysis_results`, `/fsx/analysis_results/sent-hg003-5x-0712`, `/fsx/analysis_results/.dayoa_agent_visits`, `/fsx/analysis_results/cromwell_executions`, `/fsx/analysis_results/daylily`, and `/fsx/analysis_results/ubuntu`.
- Proposed delete scope: the following 29 sibling analysis roots, totaling 23G. No live DayOA controller, Slurm job, tmux session, or write-lock owner was found in any delete candidate.

```text
/fsx/analysis_results/sent-hg003-5x-0712/hg003_5x_hiomrs_sent_single_20260712T134226Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003_5x_hiomrs_clean_20260712T1554Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003_5x_hiomrs_noqc_a_20260712T1620Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003_5x_hiomrs_noqc_b_20260712T1622Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003_5x_hiomrs_cpuset_b_20260712T1640Z
/fsx/analysis_results/sent-hg003-5x-0712/hiomrs_ks_dry_20260712T1803Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003_5x_hiomrs_ks_recovery_20260712T182722Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003_5x_hiomrs_ks_recovery_20260712T1829Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003_5x_hiomrs_ks_recovery_20260712T1834Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003_5x_hiomrs_ks_recovery_20260712T1849Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003_5x_hiomrs_ks_recovery_20260712T1930Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003_5x_hiomrs_ks_nvme_dryrun_20260712T2004Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003_5x_hiomrs_ks_nvme_test_20260712T2009Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003_5x_hiomrs_ks_nvme_270cb4d_20260712T2019Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003_5x_hiomrs_ks_5e1320a_dry_20260712T225737Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003_5x_hiomrs_ks_54fcc90_dry_20260712T230613Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003_5x_hiomrs_ks_738d256_test_20260712T231147Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003_5x_hiomrs_ks_738d256_clean_20260712T232259Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003_5x_hiomrs_ks_e879975_clean_20260712T233453Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003_5x_hiomrs_ks_e879975_retry_20260712T233754Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003_5x_hiomrs_ks_f3b9a24_20260713T013004Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003_5x_hiomrs_ks_f3b9a24b_20260713T013004Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003-5x-ks-b5438f9-20260713T015830Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003-5x-ks-10098-20260713T020404Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003-5x-ks-10099-20260713T021122Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003-full-ks-10099-20260713T023029Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003-5x-ks-10100-20260713T051708Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003-5x-ks-10101-20260713T052846Z
/fsx/analysis_results/sent-hg003-5x-0712/hg003-1x-ks-10101-20260713T054640Z
```

| ID | Requirement | Status | Category | Gate | Evidence / terminal note |
|---|---|---|---|---|---|
| KILL-001 | Stop all live controllers and their Slurm work | SUCCESS | legitimate_safety_handling | Destructive second approval | Zero matching controller processes and empty queue at 08:35:51Z. |
| TMUX-001 | Terminate all tmux sessions | SUCCESS | legitimate_safety_handling | Destructive second approval | All 15 sessions terminated with `tmux kill-server`; no server remained. |
| DELETE-001 | Delete the 29 listed sibling analysis roots while preserving the exact latest 1x root and service/audit directories | BLOCKED | legitimate_safety_handling | Destructive second approval | Exact irreversible scope is now recorded. Await a new explicit confirmation naming the 29 roots / 23G loss boundary. |

## 2026-07-13T09:09:41Z exact command-catalog relaunch

The user directed a new run in the preserved analysis root using its existing HG003 1x manifests. The proposed 23G sibling deletion remains unperformed and blocked at its separate second-approval gate.

- Catalog ID: `hybrid_ilmn_ont_hiomrs_kitchensink` from local DYEC branch `sentieon-single`.
- Active DayOA identity: detached `d5a5110610fd95e4cae687a546086fc2e67f1e6d`, contained by `origin/sentieon-single`, with the previously recorded runtime-temp tracked patch.
- `config/samples.tsv`: 2 lines, one HG003 row, SHA-256 `15bf42e9348a52f921fd785ff82c86615ea060b9b0aa6b646a0c1f928efd17c0`.
- `config/units.tsv`: 2 lines, one `HIOa / HG003 / SR1x-ONT1x` row, SHA-256 `82aa26f9c837149232e8bf5c1ae49786e331f3ce45300b92c9bd81c0b5dd4051`.
- Both Illumina FASTQs and the ONT CRAM referenced by the unit row were present and nonempty.
- Existing user tmux `xa` was preserved untouched. New one-window/one-pane controller session: `hiomrs-ccat-hg003-1x-20260713`.
- Required shell sequence completed separately: `source dyoainit`, then `dy-a slurm hg38`, then catalog `dy-r`.
- Exact catalog dry-run returned `0` with 91 remaining jobs and maximum 192 threads.
- Parent-root lock acquired by `codex-hiomrs-ccat-hg003-1x-20260713` after the dry-run.
- Exact live command launched with `-j 250 -p -T 0 --rerun-triggers mtime --rerun-incomplete`, no `-k`, and no non-catalog producer options. Slurm group job `136` (`GROUP-hiomrs_core-nosample`, 192 CPUs) entered `CONFIGURING` on `i192nvme-dy-price192nvme-1` at 09:09:41Z.

| ID | Requirement | Status | Category | Gate | Evidence / terminal note |
|---|---|---|---|---|---|
| RUN2-001 | Verify preserved HG003 1x manifests and referenced inputs | SUCCESS | contract_test | Gate 0 | One sample/unit row; hashes and three source-file sizes recorded above. |
| RUN2-002 | Resolve and dry-run the exact `hybrid_ilmn_ont_hiomrs_kitchensink` catalog command | SUCCESS | contract_test | Gate 2 | Exact catalog command, 91-job DAG, `RETURN CODE: 0`. |
| RUN2-003 | Acquire the correct parent analysis-root lock and launch one persistent live controller | SUCCESS | feature_implementation | Gate 3 | Lock owner, tmux, controller process chain, and first Slurm job verified. |
| RUN2-004 | Monitor the full catalog continuation to a terminal result and verify final requested artifacts | IN_PROGRESS | contract_test | Gate 5 | Job 136 is running the first `hiomrs_core` group on the allocated 192-vCPU node; queue emptiness alone will not satisfy this row. |

## 2026-07-13T09:19:12Z heartbeat evidence

- Recorded a fresh parent-root read visit before monitoring; the write lock remains owned by `codex-hiomrs-ccat-hg003-1x-20260713` in the controller pane.
- Controller tmux `hiomrs-ccat-hg003-1x-20260713` remains one live bash pane in the exact DayOA repo. The exact `bin/day_run`/workflow controller process chain is still live. No terminal controller marker or first causal failure is present.
- Slurm job `136` transitioned from `CONFIGURING` to `RUNNING` at `2026-07-13T09:14:12Z` on `i192nvme-dy-price192nvme-1`; snapshot runtime `00:04:37`, 192 CPUs, 350000M requested memory, no restarts, and no Slurm failure reason.
- The active core log advanced through Sentieon `HybridStage2` and `CNVModelApply` to their reported 100% points. This is internal rule progress, not workflow success.
- `sstat` point sample for `136.batch`: average CPU `04:23:29`, average RSS `17530544K`, maximum RSS `47450968K`, disk read `206195804389` bytes, and disk write `31660728705` bytes.
- Bounded Glances sample at `09:19:08Z`-`09:19:12Z`: CPU user/system `0.5%`/`0.1%`, load 1/5 `42.65`/`37.22` falling to `39.31`/`36.61`, memory `1.7%` (about 27.2 GB), `/fsx` 8% used, `/scratch` 1% used. This is point-in-time telemetry only; the process sample still showed `bcftools` plus multiple Python workers.
- Final `DAY_final_multiqc.html` and `dayoa_evidence_manifest.json` are not yet accepted because the controller is nonterminal.

## 2026-07-13T09:22:52Z release-and-fresh-run amendment

The user directed an explicit breaking `10.3.0` release on the `sentieon-single` branches of both DayOA and DYEC, followed by a new exact-tag HG003 1x kitchensink run from a fresh analysis checkout on the same cluster. The currently running checkout and Slurm job remain untouched while release preparation proceeds; their outputs cannot satisfy the new fresh-run row.

Gate 0 release inventory:

- DayOA release worktree: `/Users/jmajor/projects/lsmc/daylily-omics-analysis-sentieon-single`, branch `sentieon-single`, base/remote `d5a5110610fd95e4cae687a546086fc2e67f1e6d` (`10.0.102`). Intended tracked release scope is `workflow/scripts/dayoa_runtime_tmp.bash` plus `tests/test_dayoa_runtime_tmp.py`. Generated `jemxxx_tmp/` and `tmp_sent-singleton/` are unrelated and excluded.
- The active headnode checkout has the exact same runtime-helper source bytes as the prepared local fix worktree (`SHA-256 3fe5c771fcdeb436cd6652bf5c3c105bca7d75d8a38c129bcdab923160330c21`); its `.dayoa_agent/`, checkpoint diagrams, Ursa logs, and scratch files are runtime artifacts and excluded.
- DYEC release worktree: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster-sentieon-single`, branch/remote `sentieon-single`, base `8d9b27e744942f686d3cb8934ee3a2441d2edfef`. The already-pushed branch contains single-node cluster support, the HIOMRS kitchensink catalog command, and the 12-node queue limit. Intended new release scope pins the two single-node HIOMRS catalog entries to DayOA `10.3.0`, mirrors the packaged catalog, updates its focused test, and includes this controlling ledger.
- Existing dirty `daylily_ec/aws/slurm_accounting.py`, `tests/test_slurm_accounting.py`, and untracked `docs/plans/20260712T192000Z_sent_hg003_runtime_cache_publish.py` are unrelated to this release and remain excluded.
- Remote `10.3.0` tags were absent in both repositories at inventory time. Release tags must be annotated, created only after their commits, verified as tag objects, and pushed without overwrite.

| ID | Requirement | Status | Category | Gate | Evidence / terminal note |
|---|---|---|---|---|---|
| REL2-001 | Reconcile the exact headnode DayOA runtime-temp fix and focused regression test onto local `sentieon-single` | SUCCESS | feature_implementation | Gate 4 | Exact headnode source plus regression test committed as `f1badba`; focused runtime-helper and dependent contract suite: 40 passed. |
| REL2-002 | Commit and push DayOA `sentieon-single`, then create and push annotated tag `10.3.0` | IN_PROGRESS | feature_implementation | Gate 5 | Narrow two-file release commit `f1badba` created; push and annotated tag remain. |
| REL2-003 | Pin the two DYEC single-node HIOMRS catalog entries to DayOA `10.3.0` and validate source/package parity | SUCCESS | feature_implementation | Gate 4 | Source/package catalogs are byte-identical; focused catalog and repository suite: 15 passed. |
| REL2-004 | Commit and push DYEC `sentieon-single`, then create and push annotated tag `10.3.0` | OPEN | feature_implementation | Gate 5 | Unrelated accounting/runtime-cache files explicitly excluded. |
| RUN3-001 | Create a new analysis checkout on `sent-hg003-5x-0712` pinned exactly to DayOA tag `10.3.0` | OPEN | contract_test | Gate 3 | Must use `day-clone -t 10.3.0 -d <fresh-id>` in a new persistent one-pane tmux. |
| RUN3-002 | Stage exact HG003 1x `samples.tsv` and `units.tsv`, verify hashes/inputs, and pass the exact catalog dry-run | OPEN | contract_test | Gate 2 | Expected prior hashes are recorded under RUN2-001; new checkout must be independently verified. |
| RUN3-003 | Acquire the new parent analysis-root lock and launch the exact no-`-k` catalog live command through `dy-r` | OPEN | feature_implementation | Gate 3 | Requires distinct stable agent/tmux identity and a non-overlapping new analysis root. |
| RUN3-004 | Monitor the fresh run to controller rc 0 plus final MultiQC and evidence manifest | OPEN | contract_test | Gate 5 | Queue emptiness or success of the earlier checkout is insufficient. |
