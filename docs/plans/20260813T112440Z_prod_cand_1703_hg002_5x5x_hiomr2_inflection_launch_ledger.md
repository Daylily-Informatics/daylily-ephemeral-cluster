# prod-cand-1703 HG002 5x+5x HIOMR2 Mega + Inflection Launch Ledger

Created: 2026-08-13T11:24:40Z

## Scope and execution boundary

Refresh the local and `prod-cand-1703` headnode DYEC installation to the exact
annotated `17.0.4` release, then launch the immutable catalog command
`inflection-bjuice-product-v0.2` against its packaged HG002 verified slim-data
fixture. Run the catalog dry lane first with the literal DayOA command flags
`-j 333 -T 0 -p -n` and no `-k`; launch the live lane only if dry-run,
controller, input, lock, and cluster evidence are clean. Use genome `hg38`,
The initial dry lane used catalog-pinned DayOA tag `14.0.6`. After that lane
exposed an owning DayOA DAG defect, the user's explicit debug/fix/retry
amendment authorized a fresh retry with exact annotated patch tag `14.0.7` via
DYEC 17.0.4's supported `--git-tag` override. Retain the catalog-provided
5.862704556x ILMN plus 4.794169766x ONT six-manifest fixture and the catalog's
`19-20` quick validation scope.

This authorization does not include export, local FSx deletion, DRA detach,
cluster teardown, job cancellation/requeue, Slurm administration, a budget-cap
change, command substitution, full-coverage input substitution, or a fallback
DayOA/DYEC version.

## Gate 0: inventory freeze

- Controlling instructions:
  `/Users/jmajor/.codex/AGENTS-HOW-TO-RUN-DAYOA.md`, repository `AGENTS.md`,
  `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`, and `dyec agent guidance`.
- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`.
- Initial branch: `codex/local-dyec-17.0.3` at annotated tag `17.0.3`
  (`532ba648`); local release refresh created
  `codex/local-dyec-17.0.4` at annotated tag `17.0.4`
  (`2ef2c503`, release message `Release DYEC 17.0.4 with DayOA 14.0.6`).
- Initial repository state: no tracked modifications; numerous pre-existing
  untracked user artifacts under the repository were present and are outside
  this launch ledger's write scope. They will not be edited, staged, or removed.
- Local activation: `source ./activate`; `dyec --version` reports
  `Daylily Ephemeral Cluster 17.0.4` after the refresh.
- Catalog evidence:
  `dyec catalog show inflection-bjuice-product-v0.2 --dyec-version 17.0.4`
  resolves a production `six_manifest` command pinned to DayOA `14.0.6`, genome
  `hg38`, profile `slurm`, jobs `333`, and fixture
  `examples/staging/hg002_bjuice_verified_5x5x_fastq`.
- Exact catalog dry command ends in `-j 333 -T 0 -p --rerun-triggers mtime -n`
  and contains no `-k`; live command is byte-equivalent except for removing the
  terminal `-n`.
- Cluster evidence:
  `dyec cluster describe --profile lsmc --region us-west-2 --cluster prod-cand-1703`
  reports `UPDATE_COMPLETE`, compute fleet `RUNNING`, running Ubuntu headnode
  `i-0a19cb6b471874d56` (`10.0.0.22`), and Slurm scheduler.
- Headnode pre-refresh evidence: interactive `dyec headnode connect` landed as
  `ubuntu`; headnode DYEC was `17.0.3`; `tmux list-sessions` found no tmux server;
  `squeue -u ubuntu` contained only its header.
- Known live-system limits: queue emptiness is not workflow success; controller
  rc, catalog receipt, exact analysis root, visit/lock ownership, and tmux state
  must be checked independently. No destructive or Slurm-control action is
  authorized.

Gate 0 status: `SUCCESS`.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| RUN-001 | Instructions/catalog | Re-read current agent, DayOA, DYEC CLI, catalog, and relevant prior-run contracts | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 controlling instructions; DYEC `17.0.4` agent guidance and catalog show |  | Exact supported command and safety boundary established. |
| RUN-002 | Local DYEC | Update activated local checkout/runtime to annotated DYEC `17.0.4` | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | `git cat-file -t 17.0.4 -> tag`; branch at `2ef2c503`; `dyec --version -> 17.0.4` |  | No user-owned untracked artifact changed. |
| RUN-003 | Cluster baseline | Verify exact cluster, headnode user/version, controller/tmux state, and queue before mutation | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | `prod-cand-1703` `UPDATE_COMPLETE`; fleet `RUNNING`; `ubuntu`; DYEC `17.0.3`; no tmux server; empty user queue |  | Baseline captured before headnode refresh. |
| RUN-004 | Headnode DYEC | Reconfigure `prod-cand-1703` from the activated exact DYEC `17.0.4` release and verify remote version | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | First configure SSM command `64b87d72-b2ce-4724-9a5a-f3e58c0e371c` failed at repo fetch with rc 128 and `Host key verification failed`; supported retry with both existing repository-scoped deploy-key references succeeded; remote `dyec --version` and exact git tag are `17.0.4`, checkout is clean, two key references remain, no tmux server exists, and queue is empty | The no-secret configure path did not activate the existing repository-scoped SSH key/known-hosts contract for the SSH origin. | Headnode refresh completed through the supported configure command without exposing secret values or starting workflow work. |
| RUN-005 | Render/input/lock | Render the exact catalog dry launch, resolve the explicit analysis root/ID and fixture, record visit, acquire write lock, and verify a one-pane persistent tmux | SUCCESS | legitimate_safety_handling | Gate 4 | orchestrator | DYEC created the fresh `14.0.6` root, staged and hash-checked all six manifests, initialized one persistent tmux pane, recorded the visit, acquired the write lock, and released it after attributed workflow exit |  | The controller remained inspectable and no Slurm job was submitted. |
| RUN-006 | Dry run attempt 1 | Run the exact catalog dry lane with `-j 333 -T 0 -p -n`, no `-k`, and require controller rc 0 plus clean dry evidence | FAIL | contract_test | Gate 5 | orchestrator | Controller receipt attributed `workflow_exit_code=2`; `.dyec/controller.log` records `MissingInputException` for four slim Truvari `queries/<query>/truvari/log.txt` inputs of `aggregate_report_components`; queue remained empty | Final MultiQC depended on child files beneath Snakemake `directory()` outputs, so Snakemake could not associate those child paths with `sentdhiomr2_slim_truvari_query`. | Failed before formal Snakemake execution; root preserved as evidence and live launch withheld. |
| RUN-006A | DayOA fix | Fix the owning dependency/staging contract, validate it, and publish an immutable patch tag | SUCCESS | feature_implementation | Gate 3 | orchestrator | DayOA commit `4e002975`; annotated tag `14.0.7`; focused tests `29 passed, 1 skipped`; broader MultiQC/reporting tests `166 passed`; branch and tag pushed | Same as RUN-006. | Final MultiQC now consumes the declared aggregate directory and stages its exact four authenticated byte-identical native logs. |
| RUN-006B | Dry run retry | Retry the exact DYEC 17.0.4 catalog lane from a fresh root using supported `--git-tag 14.0.7`; retain `-j 333 -T 0 -p -n` and no `-k` | SUCCESS | contract_test | Gate 5 | orchestrator | Fresh exact-tag root at commit `4e002975`; one-window/one-pane tmux; controller `workflow_exit_code=0`, `exit_code=0`; 243-job DAG includes four slim Truvari queries, aggregate, final MultiQC, kitchen-sink mega, and analytical package; no Slurm jobs; lock status `unlocked` |  | The failed `14.0.6` root remains preserved separately. |
| RUN-007 | Live launch | If RUN-006 succeeds, launch the byte-equivalent live catalog command with only `-n` removed | SUCCESS | feature_implementation | Gate 5 | orchestrator | DYEC 17.0.4 launch receipt records `dry_run=false`, exact DayOA tag `14.0.7`, and the two catalog targets; remote status started `2026-08-13T12:19:26Z`; the live `dy-r` payload contains `-j 333 -T 0 -p` and contains neither `-n` nor `-k` |  | Fresh live root and persistent tmux session launched after the clean fixed dry gate. |
| RUN-008 | Launch evidence | Record live controller, tmux, process, Slurm queue, analysis-root lock, command, tag, and fixture evidence without claiming completion | SUCCESS | contract_test | Gate 5 | orchestrator | At `2026-08-13T12:44:20Z`, exact tag `14.0.7`/commit `4e002975` was active; one-window/one-pane tmux was alive; Snakemake PID `48788` was active; jobs `1`-`5` were submitted and `CONFIGURING`; the analysis root remained locked by `dyec-workflow-pc1703_hiomr2_5x5x_mega_ifx_20260813`; status remained incomplete with null exit codes |  | Launch is proven; workflow completion, export, and delivery are explicitly not claimed. |
| RUN-009 | DYEC patch release | Publish a new immutable DYEC release whose current and numeric catalog snapshot pin the owning DayOA `14.0.7` fix | SUCCESS | feature_implementation | Gate 5 | dyec_1705_release | Release commit `01d56f9c`; annotated tag object `cc4d3b78` peels to that commit; branch and tag verified on origin; focused `364 passed`; full suite `2515 passed, 11 skipped`; build and Twine checks passed |  | DYEC `17.0.5` and `current` pin DayOA `14.0.7`; immutable `17.0.4` remains unchanged on `14.0.6`. |
| RUN-010 | Local DYEC refresh | Update the activated local checkout/runtime to exact annotated DYEC `17.0.5` and verify the catalog command | SUCCESS | config_or_startup_contract | Gate 5 | orchestrator | Local branch `codex/local-dyec-17.0.5` is at tag `17.0.5`/commit `01d56f9c`; `dyec --version` reports `17.0.5`; catalog resolution reports `dyec_version=17.0.5`, `git_tag=14.0.7`, `validated_version=14.0.7`, and the exact dry/live flag split |  | Existing untracked user artifacts were preserved. |
| RUN-011 | Headnode DYEC refresh | Update the headnode to DYEC `17.0.5` only if doing so cannot disrupt the running controller | NOT_EXECUTED | legitimate_safety_handling | Gate 5 | orchestrator | Source audit shows configure runs shared checkout sync, `conda env update --prune`, editable DYEC/tool reinstall, and `/opt/slurm/bin/sbatch` replacement, with no active-controller/tmux/analysis-lock guard; the live 17.0.4 controller and write lock remain active | The requested safety condition cannot be established and the supported configure path mutates shared runtime components used by the live controller and its cleanup path. | Deferred until the controller is terminal and its status receipt and analysis-root lock release are verified; no headnode mutation was attempted. |

## Current report

All rows terminal: yes

Objective complete: yes for the requested dry-gated live launch, DayOA fix,
DYEC 17.0.5 release, and local refresh. The conditional headnode refresh was
not executed because its no-disruption condition is false/unproven. Analytical
workflow completion remains in progress.

The live workflow is running under its persistent controller and analysis-root
write lock. No export, delete, teardown, Slurm intervention, or workflow
completion claim has been made.

## Headnode refresh attempt 1

- Command: `dyec headnode configure --profile lsmc --region us-west-2 --cluster prod-cand-1703`.
- Result: failed closed before repository update; SSM command
  `64b87d72-b2ce-4724-9a5a-f3e58c0e371c`, rc `128`.
- Exact cause from read-only `get-command-invocation`: `Host key verification
  failed` while fetching the existing SSH origin.
- Remote safety check: `/home/ubuntu/projects/daylily-ephemeral-cluster` is a
  clean detached checkout at exact tag `17.0.3`; the failed fetch occurred
  before the configure routine's reset/clean/install steps.
- Explicit existing authentication contract:
  `/home/ubuntu/.config/daylily/github_deploy_keys.yaml` names separate
  repository-scoped DYEC and DayOA secret ARNs in `us-west-2`; pinned
  `/home/ubuntu/.config/daylily/github_known_hosts` also exists. No secret value
  was retrieved or displayed.

## Headnode refresh attempt 2

- Retried the same supported configure operation with both exact, pre-existing
  repository-scoped deploy-key secret references from the headnode config.
- Result: `Headnode configured via SSM for cluster 'prod-cand-1703'.`
- Interactive postcheck as `ubuntu`: `dyec --version` reports `17.0.4`;
  `/home/ubuntu/projects/daylily-ephemeral-cluster` is a clean detached checkout
  at exact tag `17.0.4`; the deploy-key config still contains exactly two secret
  references; no tmux server exists; the Ubuntu Slurm queue remains empty.

## Exact rendered launch contract

- Catalog command: `inflection-bjuice-product-v0.2` from immutable DYEC
  snapshot `17.0.4`; initial DayOA `14.0.6`, amended retry tag `14.0.7`;
  `hg38`; `slurm`.
- Executing entity/project/cost center: `prod-cand-1703` /
  `prod-cand-1703` / `prod-cand-1703-ccenter`.
- Cost-center proof: active, monthly cap `$200`, allowed user `ubuntu`; August
  2026 usage snapshot is currently absent and strict admission must fail closed
  if that is not acceptable to the launcher. No budget setting will be changed.
- Fixture:
  `/Users/jmajor/.config/daylily/resources/17.0.4/examples/staging/hg002_bjuice_verified_5x5x_fastq`.
  It contains all six manifests plus `input_identity.json`; the identity receipt
  records ILMN `5.862704556x` and ONT `4.794169766x` and forbids full-coverage
  substitution.
- Dry analysis ID/root/session:
  `prodcand1703-hiomr2-slim5x5x-mega-ifx-1406-dry-20260813` /
  `/fsx/analysis_results/prod-cand-1703/prodcand1703-hiomr2-slim5x5x-mega-ifx-1406-dry-20260813` /
  `pc1703_hiomr2_5x5x_mega_ifx_dry_20260813`.
- Fresh fixed dry retry ID/root/session:
  `prodcand1703-hiomr2-slim5x5x-mega-ifx-1407-dry2-20260813` /
  `/fsx/analysis_results/prod-cand-1703/prodcand1703-hiomr2-slim5x5x-mega-ifx-1407-dry2-20260813` /
  `pc1703_hiomr2_5x5x_mega_ifx_dry2_20260813`.
- Live analysis ID/root/session:
  `prodcand1703-hiomr2-slim5x5x-mega-ifx-1407-20260813` /
  `/fsx/analysis_results/prod-cand-1703/prodcand1703-hiomr2-slim5x5x-mega-ifx-1407-20260813` /
  `pc1703_hiomr2_5x5x_mega_ifx_20260813`.
- Exact dry `dy-r` payload contains targets
  `produce_sentdhiomr2_slim_kitchensink_mega` and
  `produce_sentdhiomr2_inflection_analytical_package`, scope `19-20`,
  `-j 333 -T 0 -p --rerun-triggers mtime -n`, and no `-k`.
- Exact live payload is the same catalog payload with `-n` absent; the analysis
  and session identifiers differ to preserve the dry lane as immutable evidence.
- DYEC defaults retained explicitly by the rendered launcher: Ubuntu remote user,
  six-manifest input contract, default activation, analysis write lock, strict
  project check, and no automatic export/delete.

## Dry attempt 1 failure and owning fix

- The `14.0.6` dry controller exited `2` during `dy-r`'s requested
  analysis-artifact summary preflight. The controller log, rather than the
  cleanup unlock log, is the authoritative failure source.
- `aggregate_report_components` requested the four native slim Truvari logs as
  child paths under query roots declared by
  `sentdhiomr2_slim_truvari_query` as Snakemake `directory()` outputs.
  Snakemake cannot resolve an undeclared child path to a directory-output rule,
  so it raised `MissingInputException` before formal execution.
- DayOA `14.0.7` changes final MultiQC to depend on the declared aggregate
  directory. Its stager requires the exact four aggregate-native query logs and
  copies them byte-identically to the same collision-safe MultiQC layout.
- DYEC remains exact `17.0.4`; the retry uses its public `--git-tag 14.0.7`
  override. This is the owning patch release, not a guessed fallback or dirty
  headnode checkout.

## Live launch evidence

- DYEC launch receipt: `dry_run=false`, immutable catalog
  `inflection-bjuice-product-v0.2`, exact DayOA tag `14.0.7`, fresh analysis ID
  `prodcand1703-hiomr2-slim5x5x-mega-ifx-1407-20260813`, and automatic export
  disabled.
- Remote status started at `2026-08-13T12:19:26Z`; at the evidence cutoff it
  remained deliberately incomplete with null controller/workflow exit codes.
- Exact active DayOA source: annotated tag `14.0.7`, commit
  `4e0029753244606e809cc5c431c06431c3d8bc6e`.
- Persistent tmux:
  `pc1703_hiomr2_5x5x_mega_ifx_20260813`, one window, one live bash pane at the
  live repository root.
- Exact active workflow payload contains both requested targets, `hg38`,
  `19-20`, `-j 333 -T 0 -p`, and neither `-n` nor `-k`.
- Slurm submission proof at `2026-08-13T12:44:20Z`: external jobs `1` through
  `5` were submitted for short-read preparation, SeqFu, sex-complement panel
  validation, long-read FASTQ preparation, and subsampled FastQC. All five were
  `CONFIGURING`, which is expected while ParallelCluster provisions their
  `i192nvme` nodes.
- The analysis root remained locked by
  `dyec-workflow-pc1703_hiomr2_5x5x_mega_ifx_20260813`; no lock takeover or
  protected/destructive action occurred.

## DayOA and DYEC release follow-up

- DayOA repair commit
  `4e0029753244606e809cc5c431c06431c3d8bc6e` is published under annotated tag
  `14.0.7`. The subsequent branch-only evidence commit `d1ea9390` records the
  clean dry retry and live submission without moving the release tag.
- DYEC release commit `01d56f9c4f9897f1ba9678e5796f800a2334f572`
  is published under annotated tag `17.0.5`; remote tag object `cc4d3b78` peels
  to the exact release commit. A later branch-only ledger closeout commit does
  not move the release tag.
- DYEC release validation: focused release suite `364 passed`; complete suite
  `2515 passed, 11 skipped`; critical Ruff selectors, `git diff --check`,
  wheel/sdist build, embedded-catalog parity, and Twine checks passed.
- The local activated checkout is exact `17.0.5`. Its immutable catalog command
  `inflection-bjuice-product-v0.2` pins DayOA `14.0.7`, retains the verified
  5.862704556x ILMN plus 4.794169766x ONT fixture, and retains the literal dry
  versus live flag contract.
- Headnode DYEC remains `17.0.4` for the active run. The supported future refresh
  command is `dyec headnode configure --profile lsmc --region us-west-2
  --cluster prod-cand-1703`, but source lines 4152-4201 in
  `daylily_ec/workflow/create_cluster.py` show that it synchronizes the shared
  checkout, prunes/updates `DAY-EC`, reinstalls DYEC/headnode tools, and replaces
  the shared `sbatch` wrapper. There is no active-controller guard, so this
  command is deferred until terminal controller status and lock cleanup are
  both verified.

