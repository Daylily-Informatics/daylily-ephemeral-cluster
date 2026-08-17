# pcand Headnode DYEC 18.0.25 Configuration Ledger

Created: 2026-08-17T10:43:34Z

## Objective and scope

Configure the explicitly named `us-west-2` ParallelCluster headnodes with the
same exact DYEC release as the activated local executable, `18.0.25`, then
prove that the headnode `day-clone` catalog defaults the
`daylily-omics-analysis` repository to DYEC 18.0.25's pinned DayOA ref
`15.0.14`.

Targets supplied by the user:

- `pcand-usw2d` (`35.80.16.153`)
- `pcand-18022` (`35.90.203.236`)

This work does not create an analysis, invoke `dy-r`, submit or alter Slurm
jobs, alter a pinned DayOA checkout, change an AWS budget, export data, or
delete any resource.

## Gate 0: inventory freeze

- Controlling request: current user request in this task.
- Owning repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`.
- Local runtime: `source ./activate && dyec --version` -> `Daylily Ephemeral
  Cluster 18.0.25`.
- Release provenance: detached `18.0.25` tag at
  `03cf995572b3516433fd8fc6d28b7622a774bc44`.
- Pin source: source and packaged
  `daylily_pipeline_command_catalog.yaml` have matching SHA-1
  `e46a588f5ba1e88211181041f02e90b96da2ef7c`; the DayOA repository row has
  `default_ref: "15.0.14"`.
- Local dirty/untracked paths treated as user-owned and not touched:
  `TrusSV/`, `docs/plans/20260817T092432Z_pcand_usw2d_three_platform_run_mounts_ledger.md`,
  and `tmp/dayoa-ont-headnode-proof/`.
- Profile boundary: the earlier terminal `pcand-usw2d` mount ledger names the
  non-default `lsmc` AWS profile. Read-only `dyec headnode info` then resolved
  both requested clusters under that explicit profile, so it is the verified
  profile for this operation rather than an AWS default.
- Read-only validation must resolve each target through ParallelCluster/SSM;
  the supplied public IPs are recorded identifiers, not a substitute for
  instance-ID resolution.
- Supported mutation path: `dyec headnode configure --profile <profile>
  --region us-west-2 --cluster <cluster>`, which first refuses to proceed if a
  DayOA controller is active and then verifies the installed exact DYEC
  version and headnode readiness.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DOCS-001 | DYEC and DayOA docs | Refresh the supported create/launch, headnode, locking, and explicit-tag contract. | SUCCESS | contract_test | Gate 0 | orchestrator | Read `AGENTS-HOW-TO-RUN-DAYOA.md`, both repo `AGENTS.md` files, `docs/quickest_start.md`, `docs/DAY_EC_ENVIRONMENT.md`, and `docs/pipeline_manager_launches.md`; no workflow command was run. |  | Catalog launch owns its controller; manual work requires an explicit DayOA tag and a persistent `ubuntu` login-shell tmux pane using `dy-r`. |
| CLI-001 | DYEC CLI | Inspect CLI capability surface, including `dyec --help` and the headnode subcommands. | SUCCESS | contract_test | Gate 0 | orchestrator | `source ./activate && dyec --help`; `dyec headnode --help`; `dyec headnode configure --help`; `dyec headnode run --help`; `dyec headnode connect --help`. |  | `headnode configure` explicitly aligns the headnode to the running DYEC release. |
| PRECHECK-001 | pcand-usw2d | Read-only resolve current cluster/headnode state and existing DayOA/DYEC configuration before mutation. | SUCCESS | config_or_startup_contract | Gate 0 | orchestrator | `lsmc` resolved `i-01421a467936317f7`, public IP `35.80.16.153`, `UPDATE_COMPLETE`, compute `RUNNING`; no controllers, tmux panes, or Slurm jobs. Ubuntu login shell had DYEC `18.0.22`, DayOA default `15.0.11`, canonical catalog symlink, and explicit `15.0.14` auth success. A repeat inventory at `2026-08-17T10:51:56Z` again found zero active controllers/jobs. |  | Target is idle and proved stale relative to the requested release/pin. |
| PRECHECK-002 | pcand-18022 | Read-only resolve current cluster/headnode state and existing DayOA/DYEC configuration before mutation. | SUCCESS | config_or_startup_contract | Gate 0 | orchestrator | `lsmc` resolved `i-07c38ac3548d7f4c4`, public IP `35.90.203.236`, `UPDATE_COMPLETE`, compute `RUNNING`; zero active controllers/Slurm jobs, though 24 stale idle tmux panes remain. Ubuntu login shell had DYEC `18.0.22`, DayOA default `15.0.11`, canonical catalog symlink, and explicit `15.0.14` auth success. |  | Target is idle and proved stale relative to the requested release/pin; stale idle tmux sessions are not modified. |
| CONFIG-001 | pcand-usw2d | Configure the Ubuntu headnode from DYEC `18.0.25` using the supported SSM-backed command. | NO_LONGER_NEEDED | plan_amendment | Gate 2 | orchestrator | The first no-credential call stopped safely at SSH host-key verification; the subsequent credential-backed rebuild was explicitly cancelled at user direction. |  | Superseded by `AMEND-001` and requested cluster deletion. |
| VERIFY-001 | pcand-usw2d | Verify headnode `dyec --version`, installed catalog default (`15.0.14`), and `day-clone` explicit-ref authentication. | NO_LONGER_NEEDED | plan_amendment | Gate 5 | orchestrator | Pending configuration was cancelled before completion. |  | Superseded by requested cluster deletion. |
| CONFIG-002 | pcand-18022 | Configure the Ubuntu headnode from DYEC `18.0.25` using the supported SSM-backed command. | NO_LONGER_NEEDED | plan_amendment | Gate 2 | orchestrator | User changed the active scope to stop configuration and delete only `pcand-usw2d`; no configuration was sent to `pcand-18022`. |  | Frozen without modification by `AMEND-001`. |
| VERIFY-002 | pcand-18022 | Verify headnode `dyec --version`, installed catalog default (`15.0.14`), and `day-clone` explicit-ref authentication. | NO_LONGER_NEEDED | plan_amendment | Gate 5 | orchestrator | Configuration is no longer in active scope. |  | Frozen without modification by `AMEND-001`. |
| AMEND-001 | Scope | Stop the interrupted `pcand-usw2d` configuration and prepare deletion of the `us-west-2d` cluster instead. | SUCCESS | plan_amendment | Gate 0 | orchestrator | User explicitly changed direction to stop then delete the `us-west-2d` target, resolved as `pcand-usw2d`; `pcand-18022` is not touched further. |  | Configuration verification is superseded for the deletion target. |
| STOP-001 | pcand-usw2d | Stop the interrupted remote DAY-EC rebuild. | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | Targeted SSM command `2f6d59b0-2501-49ac-9eb5-7d9c1390172c` (`Rebuild DAY-EC and install headnode tools`) was cancelled for `i-01421a467936317f7`; readback `status=Cancelled`, `code=137`. |  | No remote configure process remains active from this task. |
| DELETE-DRY-001 | pcand-usw2d | Inspect the exact destructive deletion target without AWS mutation. | SUCCESS | contract_test | Gate 0 | orchestrator | `dyec delete --dry-run --profile lsmc --region us-west-2 --cluster-name pcand-usw2d` -> `UPDATE_COMPLETE`; cluster-bound FSx `fs-09dbcea48d90844c4`; four active input/reference DRAs; no export task reported. |  | Dry-run recorded the exact resources that live deletion would affect. |
| DELETE-001 | pcand-usw2d | Delete the requested `us-west-2d` cluster and monitor teardown. | IN_PROGRESS | config_or_startup_contract | Gate 5 | orchestrator | User explicitly confirmed: `CONFIRM delete pcand-usw2d and fs-09dbcea48d90844c4`. A final read-only controller/analysis-root check is required immediately before teardown. |  |  |
