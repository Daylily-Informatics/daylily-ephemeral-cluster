# PEM-Free Operator Access Via SSM

## Summary

Yes, this is possible.

The repo can be made PEM-free for normal operators by shifting all laptop-to-headnode access from direct SSH/SCP to AWS Systems Manager:
- interactive access uses Session Manager
- non-interactive remote work uses SSM Run Command
- data movement continues to use S3 plus FSx data-repository behavior, not SCP

Default Daylily operation becomes PEM-free and does not require a local `~/.ssh/*.pem` at any point. SSH can remain an explicit advanced opt-in in custom ParallelCluster YAML, but it is no longer part of the supported Daylily workflow or required by any shipped command.

## Implementation Changes

### Access model

- Replace the supported operator connection path with SSM everywhere.
- Rework `bin/daylily-ssh-into-headnode` to become the standard connect helper backed by `aws ssm start-session`; keep the command name for continuity, but remove `--pem` and all public-IP lookup logic.
- Resolve the headnode by instance ID, not by public IP. Use `pcluster describe-cluster-instances` to locate the `HeadNode` instance and fail hard if it cannot be found or is not SSM-managed.
- Add one shared SSM execution layer used by all remote orchestration:
  - `start_session(instance_id, region, profile)` for interactive access
  - `run_shell(instance_id, region, profile, script, as_user="ubuntu")` using SSM Run Command plus polling
  - `push_text(instance_id, region, profile, remote_path, content)` for small config payloads via base64 write on the node
- Default interactive SSM sessions do not depend on account-level Session Manager Run As. For automation, always execute remote commands with `sudo -iu ubuntu bash -lc ...` so behavior matches the current SSH-as-ubuntu model.

### Public interfaces and config

- Remove `ssh_key_name` from the default Daylily config template and from the create workflow prompt/validation path.
- Change `daylily-ec create` so it no longer discovers local PEMs or prints `ssh -i ...` as the success hint. The connection hint becomes the SSM-backed helper command.
- Remove `--pem` from all supported operator scripts that currently require it, especially:
  - `bin/daylily-run-omics-analysis-headnode`
  - `bin/daylily-cfg-headnode`
  - `bin/daylily-run-ephemeral-cluster-remote-tests`
- Update host prereqs so the supported local toolchain is:
  - AWS CLI v2
  - `pcluster`
  - `session-manager-plugin`
- Keep SSH only as an explicit custom-cluster escape hatch, not as a normal Daylily requirement. Default rendered cluster YAML omits `HeadNode.Ssh` entirely.

### Remote bootstrap and orchestration

- Reimplement post-create headnode bootstrap in the Python workflow on top of SSM Run Command instead of SSH/SCP.
- Preserve current bootstrap behavior:
  - optional headnode GitHub SSH key generation
  - repo clone
  - miniconda install
  - `daylily-ec headnode init`
  - headnode tool install
  - repo override deployment
- Replace local `scp` usage for override config deployment with inline file creation on the headnode from SSM-delivered content.
- Rework `bin/daylily-run-omics-analysis-headnode` so it:
  - discovers stage files with SSM Run Command
  - creates the tmux session with SSM Run Command
  - reports the session name and then tells the operator to attach via the SSM connect helper
- Keep the supported laptop-side staging path as S3/FSx-backed and retire the experimental SCP-based staging helper from the supported workflow.

### Docs, policy, and guardrails

- Rewrite the operator docs so PEM setup is removed from quick start, operations, and pip-install guidance.
- Add an explicit prereq check for `session-manager-plugin` anywhere the repo currently checks for `ssh` as a required laptop-side tool.
- Add a create-time validation that the headnode becomes SSM-managed before Daylily attempts bootstrap; fail clearly if SSM is not online.
- Keep the shipped operator IAM policy broad enough for this model. The current policy already includes `ssm:*`; document that the local operator must also have the plugin installed.

## Test Plan

- Unit-test the new SSM wrapper layer for:
  - headnode instance resolution
  - interactive session command construction
  - Run Command submission and polling
  - stdout/stderr capture
  - timeout and failed-invocation handling
  - remote file write for small YAML payloads
- Update create-workflow tests so cluster creation succeeds with no `ssh_key_name` and no local `~/.ssh/*.pem`.
- Update launcher tests so `bin/daylily-run-omics-analysis-headnode` no longer accepts or requires `--pem`, and uses SSM instance targeting instead of public-IP SSH.
- Add acceptance scenarios covering:
  - create cluster from a clean laptop with no PEM files present
  - connect to headnode interactively via Session Manager
  - validate headnode bootstrap
  - stage data from laptop with the existing S3/FSx helper
  - launch a workflow into tmux from the laptop
  - rerun headnode bootstrap manually from the laptop
  - export FSx results
  - delete the cluster
- Add failure-path tests for:
  - missing `session-manager-plugin`
  - headnode not registered in SSM
  - Run Command returns non-zero
  - Run Command times out
  - command succeeds as root but fails unless wrapped with `sudo -iu ubuntu`

## Assumptions and defaults

- The supported operator experience remains CLI-driven; browser/PCUI is optional, not primary.
- The standard local dependency set may include `session-manager-plugin`.
- No account-wide Session Manager Run As preference is required; the repo handles the `ubuntu` user context itself for non-interactive work.
- Default Daylily templates stop configuring `HeadNode.Ssh`; if an advanced user explicitly wants SSH later, they can add `HeadNode.Ssh` in custom ParallelCluster YAML outside the default supported path.
- The experimental SCP-based staging flow is not preserved; the supported no-PEM replacement is the existing S3/FSx-backed staging path.
