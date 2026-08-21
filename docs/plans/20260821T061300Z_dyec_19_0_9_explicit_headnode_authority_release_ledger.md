# DYEC 19.0.9 explicit headnode-authority release ledger

Created: 2026-08-21T06:13:00Z

## Scope

Remove automatic newest-state discovery from `dyec headnode configure` and
`dyec headnode configure-dragen`. Each invocation must supply either one exact
`--state-file` or the complete exact pair of deploy-key secret ARNs. The GitHub
token remains an optional separate credential because the state-backed
deploy-key contract is sufficient for the released read-only repository sync.
When an SSM-backed configure step fails, DYEC now emits bounded remote stderr
and stdout for that exact step rather than only the SSM command identifier.

## Gate 0

| Item | Evidence |
| --- | --- |
| Base release | Annotated `19.0.8`, commit `e2dbc471c4363d0c5737f17f4d0673d7b9464d3a` |
| Release branch | `codex/release-19.0.9-explicit-headnode-config` |
| Production retry | `pclu-18045` with explicit state file reached cache-namespace step and failed before credential or repository work: SSM `b6399d66-7aea-45cd-97fd-132c9b9ce6ba`, `rc=1` |
| Headnode scope | No manual headnode repair, workflow launch, or source edit |

## Release record

| Step | Status | Evidence |
| --- | --- | --- |
| Authority contract | complete | Removed newest-state discovery; omitted authority now fails before SSM submission. |
| Failure observability | complete | Configure-step failures retain and print bounded SSM stdout/stderr. |
| Interfaces and docs | complete | Updated the standard and DRAGEN CLI help, active operator documentation, and agent contract. |
| Catalog release snapshot | complete | Added immutable numeric `19.0.9` snapshot without a `current` alias. |
| Publish | complete | Release branch and annotated `19.0.9` tag point at the clean release commit on the LSMC Bio fork. |

## Verification boundary

Per operator instruction, no pytest, Git test command, or Git diff check is
run. This release does not claim that `pclu-18045` headnode configuration
succeeded; its failure precedes the credential contract.
