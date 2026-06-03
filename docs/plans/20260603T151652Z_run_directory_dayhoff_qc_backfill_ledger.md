# Run Directory Dayhoff QC Backfill Ledger

- Source TSV: `/Users/jmajor/Downloads/20260603T151652Z_run_directory_dayhoff_qc_backfill_report.tsv`
- Pre-start annotated spreadsheet: `docs/plans/20260603T151652Z_run_directory_dayhoff_qc_backfill_annotated_start.xlsx`
- Cluster: `BigB-4-mk`
- Executing entity: `BigB-4-mk`
- Repository: `daylily-omics-analysis`
- Required DayOA git tag: `2.0.43` (user override at 2026-06-03)
- Reference profile assumption: `hg38_broad` unless Ursa/sample metadata requires a different approved profile
- Created: `2026-06-03T15:59:47.443440+00:00`



## Emergency Identity Stop Gate

If any evidence suggests either of the following, stop all live activity immediately and debug before continuing:

- An EUID prefix/system mapping appears violated, meaning two issuing systems appear to have assigned the same EUID or an EUID with the wrong system prefix.
- The same issuing system appears to have issued the same EUID for more than one distinct object.

Current assessment: no such evidence is present. The earlier `run_euid={analysis_id}` concern was a local DYEC export-registration template substitution, not a real EUID issuance collision.

## Safety Gates

| Gate | State | Evidence |
| --- | --- | --- |
| GATE-0 inventory | IN_PROGRESS | Local TSV parsed; repo command surfaces inspected; cluster live preflight pending. |
| Destructive FSx delete | CLOSED | No FSx analysis directory deletion until export receipt is verified and exact paths receive separate explicit approval. |
| Slurm intervention | CLOSED | Monitoring only; no cancel/requeue/drain/resume/service changes without explicit approval. |
| Fallback behavior | CLOSED | Missing Ursa policy/EUID/config/command coverage becomes a blocker row. |

## Five-Agent Assignments

| Agent | Responsibility | Current state |
| --- | --- | --- |
| Agent 1 Orchestrator/Ledger | Queue, concurrency, terminal rows, spreadsheet updates | ACTIVE in main thread |
| Agent 2 Cluster/Mounts | Cluster validation, DRA create/verify commands, mount IDs | SPAWNED read-only explorer |
| Agent 3 Ursa/Manifests | EUID decisions, run/sample/unit manifests | SPAWNED read-only explorer |
| Agent 4 RunQC/DayOA Commands | Command IDs, targets, dy-r contract, catalog gaps | SPAWNED read-only explorer |
| Agent 5 Variant/Export/Hybrid | Variant/export rows and hybrid candidate TSV | SPAWNED read-only explorer |

## Concurrency Contract

- At most two active run dirs across the whole plan.
- ILMN rows that require BCLConvert/demux consume both slots and run alone.
- ONT rows may consume one slot each only after FASTQs are verified present; otherwise they are reclassified as exclusive basecalling/demux rows.
- Held rows do not consume slots.

## Command Surface Baseline

```bash
export AWS_PROFILE=lsmc
export REGION=us-west-2
export CLUSTER_NAME=BigB-4-mk
export EXECUTING_ENTITY=BigB-4-mk
dyec --json cluster describe --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME"
dyec --json mounts create "s3://.../run/" --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME" --platform ILMN --read-only --wait --timeout-seconds 3600
dyec --json mounts verify --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME" --mount-id <mount_id>
dyec workflow launch --profile "$AWS_PROFILE" --region "$REGION" --cluster "$CLUSTER_NAME" --repository daylily-omics-analysis --git-tag 2.0.43 --analysis-id "$ANALYSIS_EUID" --executing-entity "$EXECUTING_ENTITY" --genome hg38_broad ...
day-clone -d "$ANALYSIS_EUID" -t 2.0.43 --executing-entity BigB-4-mk
```

## Run Queue

| ID | Order | Status | Platform | Run dir | OOW done | Slots | Planned runQC | Planned downstream | EUID state | Blocker / next action |
| --- | ---: | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| RUN-001 | 1 | PLANNED_GATE0 | ILMN | `20260526_LH01121_0004_B23WW2NLT4` | 2026-05-29T11:46:02+00:00 | 2 | `illumina_run_qc_bclconvert` | ILMN requested bundle: alignstats, Tiddit, Sentieon SNV/SV/CNV, Manta, kitchensink final, relatedness, contam, VEP; catalog gap pending for exact command coverage | runQC=M-RGX-9WR2; variant=not found; prior=M-RGX-9WR2 FAILED;jobs=FAILED; fresh=HTTP_503 | Requires Ursa EUID decision before live launch; prior failed EUID must not be silently reused. |
| RUN-HOLD-001 | HOLD | HELD | ILMN | `20260526_LH01121_0003_A23WW2YLT4` |  | 0 | `illumina_run_qc_bclconvert` | ILMN requested bundle: alignstats, Tiddit, Sentieon SNV/SV/CNV, Manta, kitchensink final, relatedness, contam, VEP; catalog gap pending for exact command coverage | runQC=missing; variant=missing; prior=none ; fresh=HELD_NO_OOW_DONE | Missing OOW.done and usable sample sheet; do not mount or run. |
| RUN-002 | 2 | PLANNED_GATE0 | ONT | `20260522_ONT_4Coriells_chip2` | 2026-05-27T00:43:25+00:00 | 1 | `ont_run_qc` | ont_snv_alignstats_kitchensink plus contam/multiqc_final coverage check | runQC=missing; variant=missing; prior=none ; fresh=BLOCKED_URSA_POLICY_INCOMPLETE | Requires Ursa policy/EUID unblock before live launch; FASTQ presence must be verified. |
| RUN-003 | 3 | PLANNED_GATE0 | ONT | `20260522_ONT_4Coriells_chip4` | 2026-05-26T21:37:04+00:00 | 1 | `ont_run_qc` | ont_snv_alignstats_kitchensink plus contam/multiqc_final coverage check | runQC=missing; variant=missing; prior=none ; fresh=BLOCKED_URSA_POLICY_INCOMPLETE | Requires Ursa policy/EUID unblock before live launch; FASTQ presence must be verified. |
| RUN-004 | 4 | PLANNED_GATE0 | ONT | `20260522_ONT_4Coriells_chip1` | 2026-05-26T19:34:28+00:00 | 1 | `ont_run_qc` | ont_snv_alignstats_kitchensink plus contam/multiqc_final coverage check | runQC=missing; variant=missing; prior=none ; fresh=BLOCKED_URSA_POLICY_INCOMPLETE | Requires Ursa policy/EUID unblock before live launch; FASTQ presence must be verified. |
| RUN-005 | 5 | PLANNED_GATE0 | ILMN | `20260522_LH01106_0010_A23VM5CLT4` | 2026-05-25T05:13:49+00:00 | 2 | `illumina_run_qc_bclconvert` | ILMN requested bundle: alignstats, Tiddit, Sentieon SNV/SV/CNV, Manta, kitchensink final, relatedness, contam, VEP; catalog gap pending for exact command coverage | runQC=M-RGX-9T77; variant=not found; prior=M-RGX-9T77 FAILED;jobs=FAILED; fresh=BLOCKED_URSA_POLICY_INCOMPLETE | Requires Ursa EUID decision before live launch; prior failed EUID must not be silently reused. |

## Execution Rows

| Row | Agent | State | Evidence | Next action |
| --- | --- | --- | --- | --- |
| INV-001 | Agent 1 | IN_PROGRESS | Parsed source TSV and created pre-start annotated spreadsheet. | Run live cluster and command preflight. |
| PRE-CLUSTER-001 | Agent 2 | PENDING | Cluster `BigB-4-mk`; profile `lsmc`; region `us-west-2`. | `dyec --json cluster describe ...`; record headnode config. |
| PRE-CATALOG-001 | Agent 4 | PENDING | Local catalog default DayOA tag `2.0.42`; target coverage pending. | Record command IDs and gap rows. |
| URSA-001 | Agent 3 | PENDING | Rows contain failed prior jobs, HTTP_503, or `BLOCKED_URSA_POLICY_INCOMPLETE`. | Resolve/request EUIDs; do not fabricate. |
| HYB-001 | Agent 5 | PENDING | Initial TSV has ONT Coriell runs but no ONT sample identities. | Produce candidate-pair TSV with blocker evidence. |

## Live State Events

_Append timestamped events here as cluster/mount/workflow/export actions occur._


- `2026-06-03T16:01:37.321198+00:00` START RUN-001 DRA attach lane: ILMN BCLConvert/demux row consumes both concurrency slots; no other run started in parallel.


## Agent Findings Added 2026-06-03T16:03:24.101961+00:00

| Finding | Impact |
| --- | --- |
| BigB-4-mk live preflight | Cluster is `CREATE_COMPLETE`, compute fleet `RUNNING`, headnode `i-0c03cb6be3c84d53b` running; initial managed run mounts count is `0`. Evidence: `20260603T151652Z_bigb4mk_cluster_describe.json`, `20260603T151652Z_bigb4mk_mounts_initial.json`. |
| Mount command surface | Use `dyec mounts list/describe/verify`; no `mounts status` command exists. `mounts create --wait` default timeout is too short, so use `--timeout-seconds 3600`. |
| Run context contract | Run-analysis commands consume `config/runs.tsv` with `RUNID`, `PLATFORM`, `RUN_DIR`, `SOURCE_S3_URI`, `MOUNT_ID`, `SAMPLE_SHEET`, `BASECALLING_STATE`, `RUN_STATUS`, `OUTPUT_ROOT`, `REGION`, `PROFILE`. |
| Ursa/EUID policy gap | Current DayEC/DYEC has no implemented `RunMountRecord.euid`; runQC/BCL artifact registration templates `run_euid` as `{analysis_id}`, not a separate seq-run EUID. This is no longer treated as a run blocker after user clarification; carry seq-run EUID in `RUNID`/`RUN_ID`, analysis EUID in `EXPERIMENTID`, and verify export-time Dewey external-link options carry the run artifact and Ursa analysis relationship. |
| ILMN variant catalog gap | `illumina_hg002_kitchensink_multiqc` covers alignstats, Sentieon SNV, relatedness, contam, VEP, expansionhunter, HTD, metagenomics, MultiQC, but not ILMN-only Tiddit/Manta/Sentieon SV/CNV. Broader `sentdhiomr` SV/CNV targets exist under hybrid/product profiles, not ILMN solo. |
| ONT variant catalog gap | `ont_snv_alignstats_kitchensink` covers alignstats, ONT SNV, concordance, relatedness, VEP, MultiQC; no explicit contam target in that command. |
| Hybrid candidates | Best current candidate is ILMN `20260526_LH01121_0004_B23WW2NLT4` crossed with ONT chip1/chip2/chip4. Confidence remains medium because ONT barcode IDs are unresolved. |

- `2026-06-03T16:03:46.102723+00:00` USER OVERRIDE: DayOA checkout must use `day-clone -t 2.0.43`; no workflow launch had started before this update.

- `2026-06-03T16:05:54.022538+00:00` USER IDENTITY CLARIFICATION: For DayOA sample/unit manifests, populate `RUNID` / `RUN_ID` with the seq-run EUID and populate `EXPERIMENTID` with the analysis EUID. This resolves manifest semantics; export registration should use explicit Dewey link options and be verified after export.

- `2026-06-03T16:07:07.496571+00:00` IDENTITY DECISION: Downgraded prior registration concern from blocker to export verification note. Execution may proceed once required Ursa analysis EUIDs exist; manifests carry `RUNID`/`RUN_ID`=seq-run EUID and `EXPERIMENTID`=analysis EUID. Export should pass Dewey link options for run artifact and Ursa analysis EUID.

- `2026-06-03T16:10:02.599556+00:00` USER SAFETY RULE: EUID prefix/system mismatch or duplicate same-system issuance is emergency-stop-all-activity condition.

- `2026-06-03T16:11:43.592197+00:00` RUN-001 MOUNT SUCCESS: DRA `dra-0fb938ea0124780f5` is `AVAILABLE`; headnode verify usable=true; path `/fsx/run_dir_mounts/20260526_LH01121_0004_B23WW2NLT4/`; local run context `docs/plans/20260603T151652Z_run_contexts/RUN-001_runs.tsv`. Next blocker: resolve/request usable Ursa analysis EUID before sample/unit generation and launch with `-t 2.0.43`.

- `2026-06-03T16:12:49.393974+00:00` START RUN-003/RUN-004 DRA attach lane: ONT chip2 and chip4 have S3 FASTQ evidence and are running as the allowed two-run lane; RUN-005 waits until one completes.

- `2026-06-03T16:17:52.832410+00:00` RUN-001 RUNQC LAUNCHED: analysis `M-RGX-9WR2`, executing entity `BigB-4-mk`, DayOA tag `2.0.43`, tmux `dayhoff_runqc_RUN001_MRGX9WR2_20260603`, repo `/fsx/analysis_results/BigB-4-mk/M-RGX-9WR2/daylily-omics-analysis`, command `dy-r produce_illumina_run_qc_and_bclconvert -p -j 20 -k --config run_context_file=config/runs.tsv bootstrap_bclconvert=true --rerun-triggers mtime`.

- `2026-06-03T16:21:42.514536+00:00` RUN-001 CHECKOUT VERIFIED: remote repo path is exact tag `2.0.43`, commit `aed7c0078339e79459f4db3e30d7e89438467e19`; untracked launcher inputs `config/runs.tsv` and `config/run_dir_links/` only. Evidence: `20260603T151652Z_RUN-001_checkout_tag_verify.txt`.

- `2026-06-03T16:23:26.424331+00:00` RUN-001 RUNQC SETUP FAILED: status exit_code=1 before workflow execution; log shows Mermaid CLI Chrome WS endpoint timeout during DAYOA environment initialization. Treat as runtime setup blocker, not runQC output failure; do not launch kitchensink until runQC/BCLConvert succeeds.

- `2026-06-03T16:27:02.281475+00:00` RUN-001 RUNQC RETRY1 STARTED: persistent tmux `dayhoff_runqc_RUN001_MRGX9WR2_retry1_20260603`; separate commands sent: `source dyoainit`, `dy-a slurm hg38_broad`, `dy-r produce_illumina_run_qc_and_bclconvert ...`; `PUPPETEER_EXECUTABLE_PATH` set to installed chrome-headless-shell.

- `2026-06-03T16:31:57.071670+00:00` RUN-001 RUNQC ACTIVE: `dy-r` accepted command in initialized DAYOA pane and is building DAG / creating run_qc conda env. Evidence: `20260603T151652Z_RUN-001_runqc_retry1_dyr_logs_latest.txt`. Kitchensink remains queued until runQC/BCLConvert outputs complete.

- `2026-06-03T16:35:35.789348+00:00` RUN-003 MOUNT VERIFIED: ONT chip2 DRA `dra-0a6f427e963c17107` AVAILABLE and headnode usable. RUN-005 MOUNT STARTED: ONT chip1 has S3 FASTQ evidence and DRA wait started while RUN-004 chip4 remains active.
