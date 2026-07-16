## Control Ledger

Controlling request: refresh the published DayOA and DYEC pins when newer Sentieon releases are ready, use DYEC release `10.3.5`, then rerun supported headnode configuration for `sentlic-e`.

Gate 0 baseline:

- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster-sentieon-single`, branch `sentieon-single`, HEAD and origin at `202a04dcb35bb07d1411efbb159d279f6f177d01`, annotated tag `10.3.2`.
- DayOA Sentieon repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis-sentieon-single`, branch and origin `sentieon-single` at `f1badba142059173376938fe05eea49c8bf811de`, annotated tag `10.3.0`.
- Existing DYEC self-pin was mainline `10.0.160`; the DayOA catalog default was `10.0.97` even though published Sentieon tag `10.3.0` is the exact `origin/sentieon-single` commit.
- Requested target: DayOA default `10.3.0`, DYEC self-pin/release `10.3.5`.
- Pre-existing dirty files outside this release scope remain unstaged and preserved: the HG003 monitor ledger and runtime-cache helper in DYEC, plus existing DayOA worktree changes. No DayOA worktree mutation is required because `10.3.0` is already published.
- Live target before configuration: cluster `sentlic-e`, region `us-west-2`, account `108782052779`, headnode `i-048ff099d73057e09`.

| ID | Requirement | Status | Evidence | Terminal note |
|---|---|---|---|---|
| PIN-001 | Pin the DayOA default to the published Sentieon release | SUCCESS | Published annotated DayOA tag `10.3.0` points at `origin/sentieon-single` commit `f1badba142059173376938fe05eea49c8bf811de`; source and packaged catalog defaults now match `10.3.0` | DayOA Sentieon pin is exact and published |
| PIN-002 | Pin and publish DYEC as `10.3.5` | SUCCESS | Source and packaged self-config match `10.3.5`; focused release gate passed `326` tests with one known unrelated Sentieon template test deselected, Ruff clean, and packaged-config byte parity. Commit `75e5b3f18fe5a827a090e08a410813802cb6fe60` and annotated tag `10.3.5` were pushed to origin | Exact requested release is published |
| CFG-001 | Run supported `dyec headnode configure` on `sentlic-e` | SUCCESS | Activated local DYEC checkout and ran `dyec headnode configure --profile lsmc --region us-west-2 --cluster sentlic-e` with both explicit deploy-key secret ARNs; command completed with `Headnode configured via SSM` | Supported Ubuntu SSM bootstrap completed |
| QA-001 | Verify exact headnode refs, auth, version surfaces, IAM isolation, and cluster health | SUCCESS | SSM `857d1f0b-05c1-4916-9795-98db1591a7b5` ran as `ubuntu` and proved repo HEAD `75e5b3f18fe5a827a090e08a410813802cb6fe60`, tag `10.3.5`, installed DYEC `10.3.5`, both DYEC self-pins `10.3.5`, DayOA default `10.3.0`, and explicit DayOA `10.3.0` auth. Final ParallelCluster, CloudFormation, compute fleet, and headnode states were healthy | Live target matches the published release contract |

## Current Report

All rows terminal: yes.

Objective complete: yes. `sentlic-e` is configured from published DYEC `10.3.5`, defaults DayOA to published Sentieon tag `10.3.0`, and remains `CREATE_COMPLETE` with compute fleet `RUNNING`.
