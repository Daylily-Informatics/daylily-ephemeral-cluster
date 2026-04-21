# Multi-Agent Plan: Remove Local PEM Requirement by Moving Daylily Operator Flows to SSM

## Summary

Yes, this is possible.

The target end state is: a normal Daylily operator can create a cluster, connect to the head node, validate bootstrap, launch workflows, rerun bootstrap steps, export results, and delete the cluster without ever needing a local PEM file. The supported operator path becomes AWS Systems Manager based:
- interactive access uses Session Manager
- scripted remote execution uses SSM Run Command
- data transfer continues to use S3 plus FSx data-repository behavior, not SCP

SSH remains an optional advanced escape hatch in custom ParallelCluster YAML, but it is removed from the default Daylily workflow, default config template, default docs, and required local prerequisites.

## Public Interfaces and Behavior Changes

- `daylily-ec create` no longer requires or resolves `ssh_key_name`, and its final connection hint becomes the SSM-backed headnode helper command.
- `bin/daylily-ssh-into-headnode` keeps its name for continuity, but stops accepting `--pem` and stops using public IPs; it targets the headnode instance through SSM.
- `bin/daylily-run-omics-analysis-headnode` stops accepting `--pem` and uses SSM for stage discovery and tmux session launch.
- `bin/daylily-cfg-headnode` and `bin/daylily-run-ephemeral-cluster-remote-tests` stop requiring a PEM and use the shared SSM execution layer.
- The default config template stops exposing `ssh_key_name`.
- The default rendered cluster YAML stops emitting `HeadNode.Ssh`.
- Local prerequisites change from `ssh` to `session-manager-plugin` for supported interactive headnode access.

## Agent Breakdown

### Agent 1: SSM Substrate and Shared Execution API

Ownership: the shared control-plane execution layer and its unit tests. This agent owns the low-level abstraction every other agent consumes and no other agent edits those files.

Deliverables:
- Add a shared SSM module that provides:
  - headnode instance resolution from cluster name plus region
  - interactive session launch for a managed instance
  - non-interactive shell execution with stdout, stderr, exit-status, timeout, and polling
  - small remote file write support for YAML/text payloads
- Standardize non-interactive execution as `sudo -iu ubuntu bash -lc ...` so automation preserves current SSH-as-ubuntu behavior without requiring account-wide Session Manager Run As.
- Define one result shape for remote execution that all callers use, including hard failure on SSM registration gaps, timeout, document failure, or non-zero shell exit.
- Add unit tests for command construction, invocation polling, timeout handling, error propagation, and remote file writes.

Write scope:
- shared AWS/SSM helper module
- any minimal shared utility needed for cluster-to-instance resolution
- new low-level tests only

Dependencies:
- none

### Agent 2: Create Workflow, Bootstrap, and Cluster Defaults

Ownership: cluster creation path, bootstrap path, and default config/template behavior. This agent does not edit operator-facing launcher scripts or docs except where a create-time help string must change.

Deliverables:
- Remove `ssh_key_name` resolution and local PEM discovery from the create workflow.
- Change the success connection hint from `ssh -i ~/.ssh/...` to the SSM-backed connect helper.
- Replace post-create headnode bootstrap SSH/SCP calls with the Agent 1 SSM execution API.
- Preserve current bootstrap semantics:
  - optional headnode GitHub SSH key generation
  - repo clone
  - miniconda install
  - `daylily-ec headnode init`
  - headnode tooling install
  - repo-override deployment
- Replace SCP-based override deployment with inline remote file creation through the SSM layer.
- Remove `HeadNode.Ssh` from the default cluster YAML templates used by the supported flow.
- Add a create-time validation gate that the headnode becomes SSM-managed before bootstrap begins; fail hard with a clear remediation if SSM is not online.
- Remove `ssh_key_name` from the default Daylily config template and any strict required-value checks tied to PEM presence.

Write scope:
- create workflow
- default cluster template/config
- create workflow tests

Dependencies:
- Agent 1 complete and interface-stable

### Agent 3: Operator Scripts and Remote Workflow Launch

Ownership: laptop-side operator commands and any remaining PEM-bound helper scripts. This agent does not edit create workflow internals or core docs.

Deliverables:
- Rework `bin/daylily-ssh-into-headnode` to resolve the headnode instance ID and start a Session Manager session instead of SSHing to a public IP.
- Rework `bin/daylily-run-omics-analysis-headnode` to:
  - remove `--pem`
  - discover staged config files via SSM Run Command
  - create the tmux session via SSM Run Command
  - print the new attach path using the SSM-backed connect helper
- Rework `bin/daylily-cfg-headnode` and `bin/daylily-run-ephemeral-cluster-remote-tests` to consume the shared SSM execution API instead of SSH/SCP.
- Retire the experimental SCP-based local staging helper from the supported path rather than porting it; the no-PEM replacement is the existing S3/FSx staging helper.
- Keep Git transport choice behavior unchanged except where current help text still implies PEM dependence.

Write scope:
- operator helper scripts under `bin/`
- script-specific tests
- no create workflow edits

Dependencies:
- Agent 1 complete and interface-stable

### Agent 4: Prereqs, Docs, and End-to-End Verification

Ownership: user-facing docs, local prerequisite checks, and full acceptance coverage. This agent does not redesign runtime behavior; it documents and verifies the behavior delivered by Agents 2 and 3.

Deliverables:
- Update prerequisite scripts and docs so the supported local requirements are:
  - AWS CLI v2
  - `pcluster`
  - `session-manager-plugin`
  - configured AWS profile
- Remove PEM setup guidance from quick start, operations, pip-install, and README operator sections.
- Rewrite all supported connection, bootstrap, and workflow-launch examples to use the SSM-backed helper path.
- Document the interactive shell expectation clearly: Session Manager is the supported connect path; if the session lands outside the desired shell context, the operator switches to `ubuntu` and runs the standard activation sequence.
- Add or update acceptance tests covering the full PEM-free operator path.
- Verify there are no remaining supported docs that tell the operator to place a PEM under `~/.ssh/`.

Write scope:
- docs
- prerequisite-check scripts
- acceptance-style tests
- no changes to shared execution code

Dependencies:
- Agents 2 and 3 complete enough to freeze user-facing behavior

## Parallelization and Execution Order

1. Agent 1 builds and freezes the SSM substrate first. No other agent should invent its own SSM wrappers.
2. Agent 2 and Agent 3 run in parallel once Agent 1’s interface is stable.
3. Agent 4 starts doc rewrites only after Agent 2 and Agent 3 settle the final user-facing commands and error messages.
4. Final integration pass verifies there are no surviving supported PEM assumptions in:
   - create
   - connect
   - launch
   - rerun bootstrap
   - docs
   - tests

## Test Plan

- Unit-test headnode instance resolution, Session Manager session invocation, Run Command polling, timeout behavior, stderr/stdout capture, and remote file creation.
- Update create-workflow tests so cluster creation succeeds with no local PEM and no `ssh_key_name`.
- Update launcher-script tests so `--pem` is gone and instance-targeted SSM execution is used instead of public-IP SSH.
- Add integration scenarios for:
  - create cluster from a machine with no `~/.ssh/*.pem`
  - connect to the headnode interactively via Session Manager
  - validate the headnode bootstrap
  - stage sample data with the existing S3/FSx-backed helper
  - launch a workflow into tmux from the laptop
  - rerun headnode bootstrap from the laptop
  - export results
  - delete the cluster
- Add failure-path tests for:
  - missing `session-manager-plugin`
  - headnode not registered in SSM
  - Run Command timeout
  - Run Command non-zero exit
  - remote command must run as `ubuntu` and fails if executed in the wrong user context
- Add one repo-wide grep-style verification in CI or test tooling that supported docs and supported scripts no longer require `--pem`, `~/.ssh/*.pem`, or `ssh -i` for normal operator workflows.

## Assumptions and Defaults

- The supported operator path remains CLI-first, not browser-first.
- Requiring the local `session-manager-plugin` is acceptable.
- PEM-free means “not required for any supported Daylily operator workflow”; it does not forbid an advanced user from adding SSH back in custom ParallelCluster YAML.
- No fallback SSH path is preserved in the default flow. Unsupported or legacy PEM-dependent helpers are either migrated or explicitly retired from the supported workflow.
- Interactive Session Manager access may still require an explicit switch to the `ubuntu` shell context unless a later follow-up standardizes that through an SSM session document; this is acceptable for v1 because it removes PEM dependence without weakening capability.
