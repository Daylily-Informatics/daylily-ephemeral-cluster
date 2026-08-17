# Bjuice Prevalence Six-AU Execution Ledger

Created: `2026-08-17T11:03:01Z`

## Objective and execution boundary

Prepare the requested Bjuice pre-validation cohort for one DYEC-owned dry
controller, with six analysis units for HG002, HG003, HG004, and the three
SMN12 samples; use full-coverage ILMN inputs and the catalog's global ONT
half-open interval `[0,24)`; cover numeric hg38 chromosomes `1-25`; and use
the maximum strict numeric DayOA tag verified from the live remote.

The request contains `-n` and also directs monitoring once Slurm jobs launch.
For DayOA, `-n` is a dry-run: it produces no Slurm work and no results that can
be exported. After the dry-run controller reaches attributable `rc=0`, the
live controller must use the exact same analysis root, DayOA checkout, and
in-clone configuration, with only `-n` removed from the verified command.

The controller must be DYEC-owned (one persistent Ubuntu tmux controller), and
no overlapping controller will be started. The user explicitly authorized one
25-minute monitoring process after Slurm work is visible. The monitor stops at
terminal controller state or after six hours, at which point continuation must
be reconfirmed.

FSx-to-S3 export is a separate no-delete, receipt-backed operation after an
explicitly authorized successful live controller. FSx cleanup is destructive
and remains blocked until the exact analysis root, destination prefix, export
receipt, and intended deletion effect are shown and separately confirmed in
this thread.

## Gate 0: inventory freeze

- Owning repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`.
- Baseline time: `2026-08-17T11:03:01Z`.
- Repo state: detached `HEAD`; pre-existing user-owned untracked paths:
  `TrusSV/`,
  `docs/plans/20260817T092432Z_pcand_usw2d_three_platform_run_mounts_ledger.md`,
  `docs/plans/20260817T104334Z_pcand_headnode_dyec_18025_config_ledger.md`, and
  `tmp/dayoa-ont-headnode-proof/`. They are not touched by this work.
- Local runtime check: `source ./activate && dyec --version` ->
  `Daylily Ephemeral Cluster 18.0.25`.
- DYEC command-contract reads completed: `dyec --help`, `dyec catalog --help`,
  `dyec catalog launch --help`, `dyec catalog render --help`, `dyec export --help`,
  `dyec exports --help`, `dyec analysis --help`, and `dyec workflow --help`.
- DayOA/agent-contract reads completed: repo/global `AGENTS.md`,
  `AGENTS-HOW-TO-RUN-DAYOA.md`, and
  `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`.
- Memory review completed before live inspection. The previous Bjuice mount
  topology is historical only; live cluster, DRA, controller, tag, and receipt
  state must be revalidated.
- Maximum strict numeric DayOA tag from live `origin` refs:
  `15.0.14` at `aee35abe71fe18b5de396ce419d23d9110319873`.
- Current-catalog evidence: the literal v0.9 id is
  `inflection-bjuice-product-v0.9`, pinned to `15.0.14`. Its render accepts the
  six-manifest input contract and the paired global ONT selector
  `use_fq_data_starting_hrs=0` / `use_fq_data_up_to_hrs=24` (a 24-hour
  half-open interval), but its immutable command is `-j 333 -T 0 -p` and has
  no `-k`. Catalog render has no supported `--jobs` or `--snakemake-extra`
  override. It therefore cannot silently become the requested
  `-j 444 -T 1 -k -n` command. The approved current execution path is an exact
  `dyec workflow launch --dy-command` dry controller pinned to `15.0.14`, with
  the six-sample `sentdhiomr2` mapping passed as an explicit config assignment.
- Live read-only inventory: `pcand-18022` is the only verified usable Bjuice
  topology: its ILMN and canonical 2026 ONT parent run mounts are both
  `AVAILABLE`, its compute fleet is `RUNNING`, its cost center
  `pcand-18022-ccenter` is active, and there was no catalog controller or
  Slurm job at `2026-08-17T11:06Z`. Its headnode reports DYEC `18.0.22` while
  the local controlled CLI is `18.0.25`; that correction is isolated below
  rather than inferred or performed with an invented credential reference.
- Six source-backed full-coverage manifests were generated locally at
  `docs/plans/20260817T110301Z_bjuice_preval_six_au_execution_artifacts/manifests/`.
  Receipt confirms HG002, HG003, HG004, NA19235, NA20775, and NA23687, with
  blank SR/ONT downsample values. `analysis_units.tsv` contains exactly six
  AUs. The generator returned `ok: true` and recorded the manifest hashes.
- Render-only proof: `dyec catalog render inflection-bjuice-product-v0.9`
  with the six manifests, `--dry-run`, and the paired `0`/`24` selectors
  returned `rc=0`. It did not create an analysis root, stage inputs, start a
  controller, or submit Slurm work.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DOC-001 | DYEC / DayOA contracts | Read the applicable operation, catalog, locking, export, and controller rules. | SUCCESS | contract_test | Gate 0 | orchestrator | Gate 0 command/document inventory above. |  | Catalog launches own one Ubuntu tmux controller; raw Snakemake is prohibited. |
| MEM-001 | Prior Bjuice state | Review prior Bjuice mount and release evidence without treating it as live truth. | SUCCESS | contract_test | Gate 0 | orchestrator | `MEMORY.md` Bjuice-preval and Take15 entries; prior Bjuice DRA rollout summary. |  | Prior `prod-cand2` state is stale; current resources require fresh inspection. |
| TAG-001 | DayOA provenance | Resolve and pin the maximum strict numeric DayOA tag. | SUCCESS | contract_test | Gate 0 | orchestrator | `git ls-remote --tags origin` numeric-semver comparison -> `15.0.14`, `aee35abe71fe18b5de396ce419d23d9110319873`. |  | All render/dry/live commands must pass `--git-tag 15.0.14`. |
| CMD-001 | Command contract | Launch the exact six-AU dry controller at `15.0.14` with 1-25 scope, `-T 1`, `-j 444`, `-p`, `-k`, and `-n`. | IN_PROGRESS | active_product_contract | Gate 2 | orchestrator | User authorized the no-release direct execution path. The existing catalog remains literal v0.9 (`-j 333 -T 0 -p`), while `dyec workflow launch --dy-command` can carry the exact requested command. | Existing catalog flags are immutable. | Launch a fresh dry root; do not reuse the old 15.0.11 Bjuice checkout. |
| CONFIG-001 | Runtime configuration | Provide a complete `sentdhiomr2` config assignment keyed by the six external `SAMPLEID` values. | IN_PROGRESS | config_or_startup_contract | Gate 2 | orchestrator | DayOA requires `lr_input_mode_by_sample` to contain every active biological sample. Existing v0.9 config declares HG002 only. The local six-manifest input set has distinct local `ANALYSIS_UNIT_UID` values and blank `ANALYSIS_UNIT_EUID` fields. | No EUID may be invented. | Pass all six `fastq` mappings, a safe provenance label, and `1-25` in the command; later record the same contract for catalog operators. |
| LIVE-001 | Cluster and input topology | Read-only inventory of a live Bjuice cluster, exact input mounts, cost center, controller, and Slurm state. | SUCCESS | config_or_startup_contract | Gate 0 | orchestrator | `pcand-18022`; ILMN DRA `dra-0cc3051c7e460429e`; ONT DRA `dra-0a739dd6aa2d433a0`; both `AVAILABLE`; compute `RUNNING`; cost center active; controller count 0 and Slurm job count 0 at `2026-08-17T11:06Z`. |  | Historical `prod-cand2` was not reused. |
| HEADNODE-001 | Headnode toolchain | Verify the selected headnode can resolve the exact DayOA tag and host the DYEC controller. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Connected through `dyec headnode connect` to `pcand-18022` as `ubuntu`; repaired the shell to interactive login Bash; `day-clone --check-auth -t 15.0.14 --repository daylily-omics-analysis` succeeded. |  | No headnode configure was needed for this source-pinned dry controller. |
| MAN-001 | Six manifests | Generate and validate one exact six-manifest set from reviewed source evidence and an explicit six-AU plan. | SUCCESS | feature_implementation | Gate 0 | orchestrator | `docs/plans/20260817T110301Z_bjuice_preval_six_au_execution_artifacts/manifests/bjuice_preval_config_receipt.json`; `ok: true`; six AUs; full SR and ONT input values; hashes emitted by generator. |  | Uses source-owned records only; no EUIDs were invented. |
| DRY-001 | Dry controller | Launch the dry controller in the intended analysis root with the exact command and wait for attributable `rc=0`, zero Slurm submissions. | IN_PROGRESS | contract_test | Gate 2 | orchestrator | The user authorized this direct DYEC execution. The six-manifest payload is 516,679 bytes, so it must use the verified `s3://lsmc-ssf-sequencing-data/staged_external_data` payload relay rather than SSM inline content. |  | Preserve this exact root, checkout, and in-clone config for the live continuation. |
| LIVE-002 | Live controller | From the same analysis root, checkout, and in-clone config, launch one live DYEC controller with the verified command changed only by removing `-n`. | BLOCKED | feature_implementation | Gate 2 | orchestrator | User explicitly authorized this follow-on live phase. | DRY-001 must first prove the complete rendered configuration with rc=0. | One controller only; do not clone or restage the analysis for the live continuation. |
| MON-001 | Monitoring | Start exactly one user-authorized 25-minute monitor once Slurm jobs are launched; stop on terminal controller state or request confirmation at six hours. | BLOCKED | legitimate_safety_handling | Gate 2 | orchestrator | Automation interface resolved; no monitor was created because no controller or Slurm job exists. | The user-specified start condition has not occurred. | When unblocked, create exactly one heartbeat monitor at 25-minute cadence, ending at terminal controller state or the six-hour reconfirmation boundary. |
| EXP-001 | FSx to S3 | After LIVE-002 `rc=0`, record export visit, execute a no-delete DRA export, and verify receipt plus expected S3 objects. | BLOCKED | feature_implementation | Gate 3 | orchestrator | Destination and analysis root do not yet exist. | The requested `-n` cannot produce exportable results; no live controller has been explicitly authorized. | Export begins only after a separately authorized live controller terminal success. |
| DEL-001 | FSx cleanup | Delete only the exported exact FSx analysis root after S3 success. | BLOCKED | active_product_contract | Gate 5 | orchestrator | User made the initial cleanup request; no exact root/destination/receipt exists yet. | Separate destructive approval required after `EXP-001` proof. | Will not run until the user explicitly reconfirms the exact root and deletion effect. |

## Current status counts

- SUCCESS: 6
- IN_PROGRESS: 3
- OPEN: 0
- BLOCKED: 3
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0

All rows terminal: yes.
Objective complete: no.
