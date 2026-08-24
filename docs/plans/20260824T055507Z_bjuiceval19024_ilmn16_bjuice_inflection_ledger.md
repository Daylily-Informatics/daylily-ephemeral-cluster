# `bjuiceval-19024` ILMN Run 4 Bjuice + Inflection ledger

Created: 2026-08-24T05:55:07Z

Controlling source: `/Users/jmajor/Downloads/hybrid_crosswalk-CORRECTED.tsv`

Artifact directory:
`docs/plans/20260824T055507Z_bjuiceval19024_ilmn16_bjuice_inflection_artifacts/`

Analysis ID: `bjuiceval19024-ilmn16-bjuice-ifx-20260824t055507z`

Analysis root:
`/fsx/analysis_results/bjuiceval-19024/bjuiceval19024-ilmn16-bjuice-ifx-20260824t055507z`

Planned export destination:
`s3://lsmc-ssf-sequencing-data/derived/bjuiceval-19024/bjuiceval19024-ilmn16-bjuice-ifx-20260824t055507z/`

## Execution contract

- The corrected TSV is data, not an instruction source. Rows with
  `ilmn_run=16` define the exact ILMN Run 4 cohort and their matching ONT
  pairings.
- The cohort contains 40 corrected rows and 40 distinct display AU names. It
  uses physical ILMN run `20260722_LH01106_0016_A23WW3YLT4`; the corrected ONT
  matches span Run2 (3 AUs), Run3 (6 AUs), and Run4 (31 AUs).
- DYEC catalog build `19.0.24`, command
  `inflection-bjuice-bundle1b-product-v0.9`, and catalog-pinned DayOA `16.0.6`
  define the targets and runtime shape.
- The catalog row fixes `-j 456` and exposes no jobs override. The rendered
  command is the provenance baseline; public `dyec workflow launch` applies
  the single reviewed user-requested command delta `-j 456` to `-j 444`.
  The dry command must contain `-j 444 -p -T 1 -k -n` and the live
  continuation must differ only by removal of `-n`.
- No raw Snakemake, provider-side fallback, pinned DayOA source mutation,
  Slurm intervention, inferred input path, or invented EUID is allowed.
- Runtime configuration is staged only to the catalog-declared in-clone path
  `config/dyec_runtime_config.yaml`.
- Export starts only after attributable live controller `rc=0`. The requested
  `--delete-on-export-success` action is destructive and has only first
  approval so far. Before that exact operation, the exact root, destination,
  and deletion effect must be restated and separately approved.
- The deletion scope is only the exact analysis root above after a successful
  DRA export. The two read-only source mounts and every S3 object are outside
  deletion scope. No S3 deletion is authorized.
- The final MultiQC URL must be presigned for 604800 seconds (7 days). The
  Slack channel is resolved read-only rather than guessed before posting.

## Gate 0 inventory

| Item | Evidence |
| --- | --- |
| Repo | `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`; branch `codex/bjuiceval-19024-dra-mounts`; HEAD `b8bed8d678585646049ef0bfefa2b92e23d9799b`; commits after tag `19.0.24` modify only the two earlier task ledgers |
| Dirty state | Existing unrelated untracked paths are user-owned and preserved; the concurrent `pclu-18045` corrected-campaign ledger/artifacts are read-only context and are not this task's authority |
| Corrected TSV | SHA-256 `c453367fe15a2efbdc875067b460d717125991dbd1eac4c7a23966ac183642fb`; 128 rows total; 40 rows with `ilmn_run=16`; all 40 have `confidence=ok`, `ilmn_ok=TRUE`, and `ont_ok=TRUE` |
| Cluster | `bjuiceval-19024`, profile `lsmc`, region `us-west-2`; `UPDATE_COMPLETE`; fleet `RUNNING`; headnode `i-0ff7f501b24c95530`; FSx `fs-04927ce3710f164c2` |
| Controller/queue | `controller_count=0`, `slurm_job_count=0`, no tmux panes/controllers at 2026-08-24T05:51Z |
| ILMN DRA | `dra-0699649d249652226`; `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/` -> `/fsx/run_dir_mounts/hybrid-crosswalk-ilmn-2026/`; `AVAILABLE`, read-only |
| ONT DRA | `dra-0fe499a0851d5c3ff`; `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/` -> `/fsx/run_dir_mounts/hybrid-crosswalk-ont-pca100/`; `AVAILABLE`, read-only |
| Cost center | `bjuiceval-19024-ccenter`; active; allowed user `ubuntu`; monthly cap `$1200` |
| Cluster budget | Earlier approved task changed AWS Budget `bjuiceval-19024` to `$1200/month`; evidence ledger `docs/plans/20260824T053212Z_bjuiceval19024_budget_caps_ledger.md` |
| Catalog | Build `19.0.24`; catalog SHA-256 `d84b266b6556868a1520c5828a32db06ad409285c168afe9c491b5560e9801f7`; command SHA-256 `dbc0f6d4c3bf8a02c1d8eaad48d9d9f209d86f6a873a2c797eacaf9ba01bec64`; DayOA `16.0.6`; six-manifest input; runtime target `config/dyec_runtime_config.yaml`; jobs `456` |
| Prior file audit | `docs/jem/bjuice_validation/source_inventory.json`, SHA-256 `fc81dcd80e8e6c6566c8a2ba3ad3cdbfe26fd9720d9ce84263ee945e67ffc816`; supplies 37/40 exact ILMN selections and 40/40 exact ONT flowcell/hour selections |
| Missing ILMN audit closed | Corrected rows map `spec_60`, `spec_68`, `spec_75` to canonical `BUCCAL1`, `BUCCAL2`, `BUCCAL3`. Run 4 SampleSheet lines 57-59 and 112-114 confirm those names, and headnode inspection found all 8 lanes x 2 mates for `BUCCAL1_S37`, `BUCCAL2_S38`, and `BUCCAL3_S39` on the verified mount |
| Destructive approval | First approval is the user's request for delete-on-success. Second approval remains required after exact live `rc=0` and export preflight evidence; no S3 deletion is authorized |

## Corrected Run 4 display AUs

1. `ILMN-CASE5-P`
2. `ILMN-CASE6-P`
3. `ILMN-CASE7-P`
4. `ILMN-CASE8-P`
5. `ILMN-CASE9-P`
6. `ILMN-CASE10-P`
7. `ILMN-CASE1-M-a`
8. `ILMN-CASE1-P-a`
9. `ILMN-CASE1-F-a`
10. `ILMN-CASE2-P-a`
11. `ILMN-CASE2-P-b`
12. `ILMN-CASE2-P-c`
13. `BUCCAL1-b`
14. `BUCCAL2-b`
15. `BUCCAL3-b`
16. `BUCCAL10`
17. `ILMN-CASE5-M`
18. `ILMN-CASE5-F`
19. `ILMN-CASE7-M`
20. `ILMN-CASE7-F`
21. `ILMN-CASE9-M`
22. `ILMN-CASE10-M`
23. `ILMN-CASE10-F`
24. `ILMN-CASE11-P`
25. `ILMN-CASE11-M`
26. `ILMN-CASE12-P`
27. `ILMN-CASE12-M`
28. `ILMN-CASE13-P`
29. `ILMN-CASE13-M`
30. `ILMN-CASE13-F`
31. `ILMN-CASE14-P`
32. `ILMN-CASE14-M`
33. `ILMN-CASE14-F`
34. `ILMN-CASE15-P`
35. `ILMN-CASE16-P`
36. `ILMN-CASE16-M`
37. `ILMN-CASE17`
38. `ILMN-CASE18`
39. `ILMN-CASE19-P`
40. `ILMN-CASE19-M`

## Approval gates

- Gate 0: freeze cluster, catalog, source, mount, budget, and dirty-state inventory.
- Gate 1: generate and validate exact 40-AU six-manifest capsule and runtime YAML.
- Gate 2: render catalog baseline and complete dry controller with attributable
  `rc=0` and zero submitted jobs.
- Gate 3: continue the same root/checkout/commit/config with only `-n` removed
  and require attributable live `rc=0`.
- Gate 4: preflight the empty, non-overlapping export destination; restate exact
  deletion effect; obtain second destructive approval; run and verify
  delete-on-success export without any S3 deletion.
- Gate 5: identify final MultiQC object, presign for 7 days, resolve the exact
  Slack channel, post the completion message, and record its receipt.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval gate | Owner | Evidence | Root cause | Terminal note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| INV-001 | Gate 0 | Freeze repo, cluster, controller, mount, budget, catalog, TSV, and AU inventory | SUCCESS | active_product_contract | Gate 0 | Forge | Gate 0 table above |  | Exact current baseline recorded before workflow mutation |
| CFG-001 | Inputs | Rebase audited source selections to the two exact current read-only DRA roots and add the three SampleSheet-bound ILMN selections | SUCCESS | feature_implementation | Gate 1 | Forge | `prepare_run16_inventory.py`; `missing_ilmn_live_inventory.tsv`; `run16_source_inventory.json` SHA-256 `685f11e4690a1d0f5901e1bc0b60887502bba8937690c19ed105cb0675d1a29f`; 37 prior ILMN + 3 live-audited ILMN + 40 audited ONT selections |  | Every source path is explicitly rebased from its S3 URI to one of the two exact DRA roots |
| CFG-002 | Inputs | Materialize and validate six manifests plus runtime YAML for exactly 40 AUs | SUCCESS | contract_test | Gate 1 | Forge | `configs/ilmn-run16`; `dyec identities validate` rc=0; foreign keys/ordered inputs/provider-neutral invariants true; 40 AUs, 80 inputs, 80 links; 1,640 unique source paths; runtime SHA-256 `774c8e68968d34bdd75dc92b2709d8f57dc2f4cfb9366d95d5689a777c3bf4d7` |  | Blank owner-issued EUID fields are valid for this ordinary research analysis; none were invented |
| DRY-001 | Workflow | Render catalog provenance and launch exact `-j 444 -p -T 1 -k -n` dry controller | SUCCESS | contract_test | Gate 2 | Forge | Catalog render `resolved`; receipt SHA-256 `4c254ed917e5243f1e79cb08a5975c001727c2c4a83ab3c9b251bbaf54f136d5`; render SHA-256 `2ef0dbaf425cf125f6103dcea2abd761f3ccb4811e7a6363c4ee977ec71eed39`; DayOA `16.0.6` at commit `063504036cac9cc9cc10d88453b5f0d437b6a0dc`; session `bjuiceval19024-ilmn16-bjuice-ifx-20260824t055507z-dry`; attempt `7828a132-9445-487b-9a2c-6790cb1877d0`; controller/day-run/Snakemake exit codes `0/0/0`; `submitted_count=0`; `finished_count=0`; status reconfirmed 2026-08-24T06:16Z |  | Attributable dry-run success with zero submitted work; exact effective command is frozen below |
| LIVE-001 | Workflow | Same-root live continuation differing only by removal of `-n`, terminal attributable `rc=0` | IN_PROGRESS | feature_implementation | Gate 3 | Forge | Same analysis ID/root, DayOA commit, manifests, runtime config, and command frozen; live session `bjuiceval19024-ilmn16-bjuice-ifx-20260824t055507z-live`; attempt `be8f37a6-58e4-45ef-a3ca-d0d782a46a7b`; controller attributed and running; exact effective command recorded below; catalog-pinned environments completed and first jobs submitted at 2026-08-24T07:01Z; at 2026-08-24T07:13Z exact status reported 162 submitted, 84 finished, 160 running, `84 of 8209 steps (1%) done`, and no failure markers; at 2026-08-24T08:59:29Z exact `sentdhiomr2_hybrid_cli172i_core` rule status reported all 40 AUs submitted and `RUNNING`, with 0 finished; by 2026-08-24T09:32Z three distinct `sentdhiomr2_segdup_gene` failures had been automatically retried under `-T 1`, and all three retry jobs remained `RUNNING` |  |  |
| DIAG-001 | Workflow | Attribute each observed SegDup failure and verify its automatic-retry outcome without scheduler intervention | SUCCESS | diagnostic_evidence | Gate 3 | Forge | Three failures observed by 2026-08-24T09:32Z: `ILMN-CASE13-P`/`CFH`, internal job `1626`, Slurm `1400`, `FAILED` `1:0` after `00:15:43`; `ILMN-CASE7-F`/`CYP2D6`, internal job `1976`, Slurm `1791`, `FAILED` `0:15` after `00:00:02`; and `ILMN-CASE12-P`/`GBA`, internal job `1578`, Slurm `2118`, `FAILED` `0:15` after `00:24:17`. Exact master-log lines record `Trying to restart job` for all three; attempt-2 submissions are Slurm `2094`, `1991`, and `2212`. At 2026-08-24T09:32Z all three retries were `RUNNING`, with no exact `Finished job 1626.`, `Finished job 1976.`, or `Finished job 1578.` line. | Attempt 2 truncates and reuses the same rule and Slurm log paths, so attempt-1 application text is no longer durable; `CASE13-P` is known only to have exited 1, while `CASE7-F` and `CASE12-P` were terminated by signal 15 with Slurm reason `None` | No cancel, requeue, scheduler, node, or workflow intervention was performed |
| STAT-001 | Workflow | Collect an attributable overall and critical-path status snapshot and estimate remaining workflow time | SUCCESS | diagnostic_evidence | Gate 3 | Forge | At 2026-08-24T09:57:30Z controller state `RUNNING`; 2,467 of 8,209 steps finished (30.1%); 2,730 submissions observed; Slurm snapshot 417 `RUNNING`, 1 `CONFIGURING`, 1 `PENDING`; exact core-rule status 23/40 AUs finished and 17 running; exact SegDup status 214/540 jobs finished and 324 active. Subsequent full-log inspection found 20 distinct first-attempt SegDup failures, all 20 automatically restarted and none failed a second time; internal job `1976` had completed its retry. At 2026-08-24T10:00Z `/fsx` had 6.7 TiB available of 14 TiB total (6.8 TiB used, 51% utilization), with 27,936,649 free inodes (15% used). | Count-based projection from 505 newly finished steps over the preceding approximately 32 minutes is 5-8 hours to workflow terminal state; downstream job mix and outstanding retries make this an estimate, not a deadline | Export and delivery remain after terminal attributable `rc=0` and the separate exact-root deletion approval gate |
| STAT-002 | Workflow | Report exact HIOMR2 core Slurm elapsed time per completed and currently running AU | SUCCESS | diagnostic_evidence | Gate 3 | Forge | `hiomr2_core_runtime_snapshot_20260824T100535Z.tsv`; 23 completed AUs: minimum `01:11:00`, median `01:34:36`, mean `01:35:13`, maximum `02:14:29`; 17 running AUs at the snapshot: minimum elapsed `00:30:13`, median `01:51:03`, mean `01:28:17`, maximum `02:11:33` (`ILMN-CASE7-M`). Runtime IDs were mapped through the authoritative in-analysis `analysis_unit_identity_audit.tsv`. | These are exact Slurm allocation elapsed times, excluding queue wait; running values are point-in-time lower bounds, not final runtimes | No benchmark collector or write was run inside the active analysis root |
| STAT-003 | Workflow | Refresh overall progress, critical-path rules, retry exhaustion, storage, and ETA | SUCCESS | diagnostic_evidence | Gate 3 | Forge | At 2026-08-24T11:19:54Z controller state `RUNNING`; 4,228/8,209 steps finished (51.5%); 4,425 submissions observed; Slurm snapshot 223 `RUNNING`; core 33/40 AUs finished and 7 running, with current elapsed `01:45:37`-`02:49:13`; SegDup 412/540 jobs finished and 113 active. Full-log audit found 68 distinct first-attempt SegDup failures, all 68 automatically restarted, 9 exact retries already finished, and zero retry-exhausted jobs. At 2026-08-24T11:21Z `/fsx` had 5.8 TiB available of 14 TiB (7.7 TiB used, 58%). | Recent step throughput supports an updated 3-5 hour estimate to workflow terminal state, subject to the seven long-running core jobs, remaining SegDup retries, and downstream job mix | No scheduler or workflow intervention was performed; export and delivery remain gated after attributable `rc=0` |
| STAT-004 | Workflow | Refresh live progress and retry health after the core-rule long-run threshold | SUCCESS | diagnostic_evidence | Gate 3 | Forge | At 2026-08-24T11:31:29Z controller state `RUNNING`; 4,471/8,209 steps finished (54.5%); 4,730 submissions observed; Slurm snapshot 108 `RUNNING`; core 33/40 AUs finished and 7 running; SegDup 453/540 jobs finished and 1 active. Full-log audit remained 68 distinct first-attempt SegDup failures, all 68 automatically restarted, 24 exact retries finished, and zero retry-exhausted jobs. `/fsx` remained 5.8 TiB available (58% used). | `ILMN-CASE1-M-a` reached `03:00:27` elapsed and is flagged `needs investigation`; elapsed alone does not establish that it is stalled. Recent throughput still supports approximately 3-5 hours to workflow terminal state, with critical-path uncertainty from the seven core jobs. | No scheduler, node, or workflow intervention was performed |
| TIME-001 | Workflow | Extend only eligible remaining HIOMR2 core Slurm limits from four to five hours | BLOCKED | legitimate_safety_handling | Gate 3 | Forge | Exact live inventory found six remaining jobs, all `RUNNING` with `04:00:00`: `1286`, `1508`, `1468`, `824`, `970`, `1101`. `CASE1-M-93pjsz1jmt4gkt` completed before this inventory and is excluded. Analysis write lock owner is the live controller `dyec-workflow-bjuiceval19024-ilmn16-bjuice-ifx-20260824t055507z-live`; read-only takeover request produced token `ac35293d0329a79e`. The user then deferred any time-limit mutation until a job exceeds `03:30:00`; the token was not approved or used. | No job below or at `03:30:00` is eligible. Any later lock takeover would replace the still-live controller as write-lock owner and therefore requires a fresh exact inventory and the separate explicit token approval mandated by the analysis-root locking contract. | At the threshold, re-inventory remaining core jobs and act only on jobs still running past `03:30:00`; do not modify completed jobs or any other rule |
| EXP-001 | Export | Verify exact destination is empty/non-overlapping and successful DRA export can delete only the exact FSx root | BLOCKED | legitimate_safety_handling | Gate 4 | Forge | Exact root and destination above; live/export preflight pending | Second destructive approval is required after exact preflight | Unblock with the user's separate explicit approval of the exact root/destination/effect |
| CLI-001 | Delivery dependency | Add, validate, and release a public DYEC exact-object presign contract rather than bypassing DYEC with raw AWS CLI/SDK calls | SUCCESS | feature_implementation | Gate 5 | Forge | `dyec aws s3 presign`; exact-object `HeadObject`; read-only GET; maximum `604800` seconds; `19.0.25` preserves the `19.0.24` catalog snapshot; focused validation `52 passed`; broader inherited set `300 passed, 15 failed` only in untouched pre-existing resource/pricing/headnode/benchmark/docs-version paths; release commit `d6c24c2e1ae4da58a0a392193bf5419a87f24e16`; annotated tag object `6240d1cba21bcad7a535fe8c94d9da3b32b25e45`; branch and tag verified on origin; activated public CLI reports exact `19.0.25` | Public DYEC `19.0.24` had no presign command | Immutable numeric release published before delivery use |
| CLI-002 | Export dependency | Add, validate, and release a read-only exact export preflight so destructive approval follows destination evidence rather than a mutating command | SUCCESS | feature_implementation | Gate 4 | Forge | `dyec exports preflight`; resolves FSx, validates DRA compatibility and exact suffix, requires empty S3 destination, rejects active DRA overlap, emits `mutation_attempted=false`; `19.0.26` preserves the `19.0.25` catalog snapshot; focused validation `40 passed`; release commit `46fac886eba5900e79fdc279b73b1244e5515d14`; annotated tag object `7cf1ec49b496e25d89ab27be777430fad6317534`; branch and tag verified on origin; activated public CLI reports exact `19.0.26` | `dyec export` enforced these checks internally but no public read-only preflight existed | Immutable numeric release published before Gate 4 preflight |
| CLI-003 | Monitoring dependency | Bound growing workflow-status record collections while preserving exact totals, state counts, terminal evidence, and explicit truncation metadata | SUCCESS | feature_implementation | Gate 3 | Forge | `MAX_TRANSPORT_COLLECTION_RECORDS=20`; submitted/finished/Slurm lists are transport-bounded only; authoritative totals remain complete; focused workflow/CLI/release validation `31 passed`; `19.0.27` preserves the `19.0.26` catalog snapshot; release commit `578fa96ef140b0395c09e4bf5d08cb45c0a25ab4`; annotated tag object `c30bd27c2c1cf093fac891ce3746cc145d6b7857`; branch and tag verified on origin; activated public CLI reports exact `19.0.27`; live status returned valid bounded JSON at 162 submitted jobs | At 140 submitted jobs the unbounded SSM response exceeded its output envelope and returned truncated malformed JSON | Immutable numeric release restored exact large-workflow monitoring without touching the controller or queue |
| CLI-004 | Monitoring dependency | Report compact exact-rule job and unique-AU state from the full attributed Snakemake log and current Slurm queue | SUCCESS | feature_implementation | Gate 3 | Forge | Public `dyec workflow status --rule`; exact internal/external job correlation; complete AU counts with AU-name lists bounded to 50; focused workflow/CLI/release validation `44 passed`; `19.0.29` preserves the `19.0.28` catalog snapshot; release commit `39b33a054bdb9c129f3ed5d91991d1154bb786ea`; annotated tag object `71f6d3a79087b29504ca425c0fdb7ac0d664a24c`; branch and tag verified on origin; activated public CLI reports exact `19.0.29`; live core query returned 40 submitted/40 `RUNNING`/0 finished AUs | Prior bounded status exposed only 20 of 440 active Slurm records, insufficient for an exact per-rule AU count | Read-only release and live validation did not touch the controller or queue |
| URL-001 | Delivery | Create 604800-second presigned URL to the exported MultiQC report | IN_PROGRESS | feature_implementation | Gate 5 | Forge | Public presign release `19.0.25` complete; pending exact exported MultiQC object |  |  |
| SLACK-001 | Delivery | Resolve exact Ursa analysis-jobs channel and post completion, all 40 display AUs, S3 URI, and MultiQC URL | OPEN | feature_implementation | Gate 5 | Forge | LSMC workspace `T08TXCVESPL`; unique public channel `#ursa-analysis-jobs`, ID `C0BRHJ9520G`, not archived; completion message pending |  |  |
| ACCEPT | Final | All rows terminal and requested objective complete | OPEN | contract_test | Gate 5 | Forge | Pending |  |  |

## Dry-run acceptance evidence

- Started: `2026-08-24T06:07:08Z`
- Completed: `2026-08-24T06:09:23Z`
- Analysis attempt: `7828a132-9445-487b-9a2c-6790cb1877d0`
- DayOA checkout: tag `16.0.6`, commit
  `063504036cac9cc9cc10d88453b5f0d437b6a0dc`
- Runtime config SHA-256:
  `774c8e68968d34bdd75dc92b2709d8f57dc2f4cfb9366d95d5689a777c3bf4d7`
- Manifest SHA-256 values:
  - `specimens.tsv`: `1bb650b3a8703412874a9e7cba63f40be75d7f8e15879d306391950d76e93b7a`
  - `samples.tsv`: `57d03027f42e1d5a6fffa29456d8f56afd9dda9eb4391d3f2739ba38c9317eca`
  - `libraries.tsv`: `02cb2b41caad044e2cd1e2f15fb27067db2d2424d8324432de642d0fb4153ef3`
  - `sequencing_inputs.tsv`: `3091044799d8814d296238745aa00361ddd37ce42cb316248bb2f0536b79f24b`
  - `analysis_units.tsv`: `4394ba850777cda181a4d21c342b39145844f40e81473b4f097334c70fee33d9`
  - `analysis_unit_inputs.tsv`: `12efe423617cad13d7cf50e312aef263c5650d2d01940b048a87ad94ab85dcfe`
- Effective dry command:

  ```text
  PIP_NO_BUILD_ISOLATION=1 DAY_CONTAINERIZED=true dy-r produce_sentdhiomr2_slim_kitchensink_mega produce_sentdhiomr2_inflection_analytical_package --configfile config/dyec_runtime_config.yaml --config genome_build=hg38 'aligners=["sentmm2ont"]' 'dedupers=["na"]' 'snv_callers=["sentdhiomr2"]' 'sentdhiomr2={"hg38_sentdhiomr2_chrms":"1-25"}' 'sv_callers=[]' 'htd_callers=["smn12"]' ont_fastq_hour_window_mode=per_analysis_unit hiomr2_inflection_package_mode=analytical seqone_delivery_batch_id=bjuiceval19024-ilmn16-bjuice-ifx-20260824t055507z -j 444 -T 1 -p -k --produce-analysis-artifact-manifest true --produce-rulegraph true --produce-filegraph false --produce-dag false --rerun-triggers mtime -n
  ```
- Live continuation invariant: the effective command above is reused in the
  same capsule with only the final `-n` removed.

## Live continuation evidence

- Session: `bjuiceval19024-ilmn16-bjuice-ifx-20260824t055507z-live`
- Analysis attempt: `be8f37a6-58e4-45ef-a3ca-d0d782a46a7b`
- DayOA checkout: tag `16.0.6`, commit
  `063504036cac9cc9cc10d88453b5f0d437b6a0dc`
- Export trigger: `none`
- Effective live command:

  ```text
  PIP_NO_BUILD_ISOLATION=1 DAY_CONTAINERIZED=true dy-r produce_sentdhiomr2_slim_kitchensink_mega produce_sentdhiomr2_inflection_analytical_package --configfile config/dyec_runtime_config.yaml --config genome_build=hg38 'aligners=["sentmm2ont"]' 'dedupers=["na"]' 'snv_callers=["sentdhiomr2"]' 'sentdhiomr2={"hg38_sentdhiomr2_chrms":"1-25"}' 'sv_callers=[]' 'htd_callers=["smn12"]' ont_fastq_hour_window_mode=per_analysis_unit hiomr2_inflection_package_mode=analytical seqone_delivery_batch_id=bjuiceval19024-ilmn16-bjuice-ifx-20260824t055507z -j 444 -T 1 -p -k --produce-analysis-artifact-manifest true --produce-rulegraph true --produce-filegraph false --produce-dag false --rerun-triggers mtime
  ```

## Final report

All rows terminal: no

Objective complete: no

Current blocker: `EXP-001` needs the required second destructive approval only
after Gate 3 and the exact export preflight are complete.
