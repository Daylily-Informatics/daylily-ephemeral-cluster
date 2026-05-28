# Kahlo Reachability Ledger

Controlling request: Check whether every currently running ParallelCluster headnode and compute node can reach `https://kahlo.day.lsmc.bio/login?next=/`.

Ledger path: `docs/plans/20260527T050613Z_kahlo_reachability_ledger.md`

## Gate 0 Baseline

- Repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
- Timestamp: `20260527T050613Z`
- Branch/status: `main...origin/main` with pre-existing modified and untracked `docs/plans/20260526T223700Z_goodole3_*` artifacts; no source-code edits made for this reachability check at Gate 0.
- Scope: read-only AWS/SSM inspection only. No cluster, instance, network, DNS, security group, IAM, or filesystem destructive changes are approved or intended.
- Required URL: `https://kahlo.day.lsmc.bio/login?next=/`
- Required access path: use repo activation and Daylily/ParallelCluster/SSM helper paths; headnode command payloads must run as `ubuntu` in a bash login shell.
- Baseline commands recorded before live inspection:
  - `git status --short --branch`
  - `date -u +%Y%m%dT%H%M%SZ`
  - instruction and memory reads for SSM/headnode constraints

## Control Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| KAHLO-001 | Cluster inventory | Identify all currently running clusters to test. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | `source ./activate && dyec --json cluster list --profile daylily-service-lsmc --region us-west-2 --details`; sanitized results in `docs/plans/20260527T050613Z_kahlo_headnode_results.json`. Running clusters: `goodole3`, `blahab44`, `jem-bucktst3`. Excluded: `jem-bucktst1`, `jem-bucktst2` because `CREATE_FAILED` with no headnode instance. |  | Inventory complete for explicit profile `daylily-service-lsmc`, region `us-west-2`. |
| KAHLO-002 | Headnodes | Test Kahlo URL reachability from each running cluster headnode. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | `source ./activate && python docs/plans/20260527T050613Z_kahlo_reachability_driver.py --profile daylily-service-lsmc --region us-west-2 --headnode-only --output docs/plans/20260527T050613Z_kahlo_headnode_results.json`; all three probes returned `curl rc=28`, `http_code=000`, `bytes=0`, `Connection timeout after 10000-10001 ms`. DNS probe on all three headnodes resolved `kahlo.day.lsmc.bio` to `100.75.231.53`. Local workstation curl returned `rc=0`, `http_code=200`, `remote_ip=100.75.231.53`. |  | Test complete: no running headnode can connect to the Kahlo URL. |
| KAHLO-003 | Compute nodes | Test Kahlo URL reachability from compute nodes for each running cluster with active compute. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | Initial Slurm-based compute probe SSM commands timed out and were cancelled: `4dfbc486-a322-4ef5-bfff-ca59959beb60`, `1ebe15dd-774c-48dd-8c5c-6e9e3fad7ce1`, `8863b326-0067-41a0-8a77-ee133e696990`. Direct Daylily SSM helper probes against pcluster-listed compute instances emitted probe output in `docs/plans/20260527T050613Z_kahlo_compute_results.json`: 8/8 compute instances returned `curl rc=28`, `http_code=000`, `bytes=0`, `Connection timeout after 10000-10001 ms`; the SSM command wrapper reported `Failed rc=1` after emitting the timeout probe output. |  | Test complete: no probed running compute node can connect to the Kahlo URL. |

## Evidence Summary

- Control profile/region: `daylily-service-lsmc` / `us-west-2`.
- AWS account identity check: `arn:aws:iam::108782052779:user/daylily-service`.
- Running clusters tested:
  - `goodole3`: headnode `i-0bd631af238bfac56`; compute `i-0fd4243e2c226771f`, `i-0105a6b5e624930dc`, `i-040922372c964cee0`.
  - `blahab44`: headnode `i-0bc04c4642b1c4b8d`; compute `i-0c83a7e440712086f`, `i-0af374619f422dd16`, `i-0d17b292edb35150e`.
  - `jem-bucktst3`: headnode `i-084e068e2e8413877`; compute `i-0c5d37ee0457c2836`, `i-0d9e17cc52f091d7f`.
- Headnode outcome: all 3 headnodes resolved `kahlo.day.lsmc.bio` to `100.75.231.53` but timed out connecting to `https://kahlo.day.lsmc.bio/login?next=/`.
- Compute outcome: all 8 running compute instances timed out connecting to the same URL.
- Workstation control: local curl succeeded with `http_code=200`, `remote_ip=100.75.231.53`, `bytes=3062`, so the endpoint itself was reachable from the workstation during the test window.
- Interpretation: the cluster nodes can resolve the Kahlo hostname, but they do not have network reachability to the resolved `100.75.231.53` address.

## Closure

- All rows are terminal.
- Objective complete: yes. The answer is no for both headnodes and compute nodes in the tested running clusters.

## Superseded Scope Note

2026-05-27T18:14Z user clarification: Kahlo reachability is not required for this work. Treat this ledger as historical evidence only. The active network objective is ongoing headnode reachability to `https://dewey.day.lsmc.bio/`, tracked in `docs/plans/20260527T053324Z_dewey_headnode_tailscale_bootstrap_ledger.md`.
