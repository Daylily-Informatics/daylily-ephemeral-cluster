# jul8itelx4 Export And Delete Ledger

Created: 2026-07-09T01:12:30Z

Controlling request: stop the active controller work for cluster `jul8itelx4`,
export all `/fsx/analysis_results/**` data to S3, and delete the cluster after
the export is complete.

## Control Paths

- Work root: `/Users/jmajor/projects/lsmc`
- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`
- Ledger path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260709T011230Z_jul8itelx4_export_delete_ledger.md`
- Cluster: `jul8itelx4`
- Region/profile: `us-west-2` / `lsmc`
- Headnode: `i-02946c880916d6dbc`, `r7i.4xlarge`, private IP `10.0.0.248`
- Managed FSx: `fs-021b9667d227d3f65`
- Proposed export root: `s3://lsmc-ssf-sequencing-data/derived/jul8itelx4/full_analysis_results_export/20260709T011230Z/`

## Gate 0 Inventory

- Required SOPs read:
  - `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`
  - `/Users/jmajor/.codex/AGENTS-HOW-TO-RUN-DAYOA.md`
  - `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/AGENTS.md`
- Memory check: `MEMORY.md` indicates export/delete must be gated as
  inventory first, export only after quiescence, and destructive delete only
  after fresh explicit approval.
- DYEC status at Gate 0: branch `jem-dev`, tracking `origin/jem-dev`, dirty
  work existed before this ledger, including spot-pricing changes, headnode
  utility changes, and several existing July 8 ledgers.
- DayOA status at Gate 0: branch `jem-dev`, tracking `origin/jem-dev`, clean.
- `pcluster describe-cluster --cluster-name jul8itelx4 --region us-west-2`
  reported `clusterStatus=CREATE_COMPLETE`, `computeFleetStatus=RUNNING`,
  CloudFormation stack `CREATE_COMPLETE`.
- `pcluster describe-cluster-instances` reported one running headnode plus five
  running compute nodes:
  - `i-0382bd5badc290055`, `i128`, `c6i.metal`
  - `i-050589c656c3a2be4`, `i128`, `c6i.metal`
  - `i-0bc0f390f7ee0723c`, `i128`, `c6i.metal`
  - `i-037d562f061580a81`, `i128nvme`, `i4i.metal`
  - `i-0b8059bc9d789ac80`, `i128`, `c6i.metal`
  - `i-0626422c678ca37b6`, `i128`, `c6i.metal`
- `dyec delete --dry-run --cluster-name jul8itelx4 --region us-west-2 --profile lsmc`
  changed no AWS resources and warned:
  - FSx still associated: `fs-021b9667d227d3f65`
  - Active DRAs still attached:
    - `dra-0e31c89df77176d37` at `/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/`
    - `dra-0a60db320f05c1eb1` at `/run_dir_mounts/20260513_ONT_HG003/`
    - `dra-03ebcc27fecb99c6f` at `/run_dir_mounts/602221-20260417_2346/`
    - `dra-0b397d39dd1536375` at `/references/`
- CloudFormation stack resources include managed FSx logical resource
  `FSX36b98071af8e309d` -> `fs-021b9667d227d3f65`.
- Headnode `/fsx` at 2026-07-09T01:09:38Z: `589G/6.6T`, 9% used.
- `/fsx/analysis_results` total size at Gate 0: `61G`.
- Active controller sessions at Gate 0:
  - `ccv_live_illumina_snv_alignstats_20260708T150500Z`
  - `ccv_live_illumina_snv_alignstats_relatedness_vep_multiqc_20260708T152112Z`
  - `ccv_live_illumina_hg002_kitchensink_multiqc_20260708T152112Z`
  - `ccv_live_hybrid_ilmn_ont_snv_20260708T152112Z`
  - `ccv_live_hybrid_ilmn_ont_snv_kitchensink_20260708T152112Z`
  - `ccv_live_inflection_bjuice_product_v0_1_20260708T152112Z`
- Slurm at Gate 0 had live work: one `CONFIGURING` `alignstats` job and many
  pending `doppelmark_dups`, `sent_DNAscope`, and `sentdhiomr_*` jobs.
- Active roots have `.dayoa_agent/write.lock` ownership from the original DYEC
  catalog agents, e.g. `dyec-jul8itelx4-agent01-20260708T150500Z` through
  `dyec-jul8itelx4-agent12-20260708T152112Z`; kill/cancel therefore needs
  explicit takeover/kill approval.

## Export Scope

DYEC export validates source paths at
`/fsx/analysis_results/<executing_entity>/<analysis_id>/`, so export will be
performed per analysis root rather than as one unsupported export of
`/fsx/analysis_results`.

Each root will export to:

`s3://lsmc-ssf-sequencing-data/derived/jul8itelx4/full_analysis_results_export/20260709T011230Z/ubuntu/<analysis_id>/`

Current analysis-root inventory:

| Analysis ID | Size | Newest observed file timestamp/path |
|---|---:|---|
| `ccv_live_hybrid_ilmn_ont_snv_20260708T142032Z` | 597M | `2026-07-08T14:35:16Z unlock_fails.log` |
| `ccv_live_hybrid_ilmn_ont_snv_20260708T152112Z` | 7.9G | `2026-07-09T01:01:38Z pipeline_workflow_checkpoint_20260709T010137Z.pdf` |
| `ccv_live_hybrid_ilmn_ont_snv_kitchensink_20260708T142032Z` | 597M | `2026-07-08T14:35:41Z unlock_fails.log` |
| `ccv_live_hybrid_ilmn_ont_snv_kitchensink_20260708T152112Z` | 7.1G | `2026-07-09T01:03:15Z pipeline_workflow_checkpoint_20260709T010315Z.pdf` |
| `ccv_live_illumina_hg002_kitchensink_multiqc_20260708T142032Z` | 597M | `2026-07-08T14:34:07Z unlock_fails.log` |
| `ccv_live_illumina_hg002_kitchensink_multiqc_20260708T152112Z` | 3.5G | `2026-07-09T01:01:20Z pipeline_workflow_checkpoint_20260709T010119Z.pdf` |
| `ccv_live_illumina_run_qc_20260708T152112Z` | 601M | `2026-07-08T18:55:36Z unlock_fails.log` |
| `ccv_live_illumina_snv_alignstats_20260708T142032Z` | 598M | `2026-07-08T14:31:44Z write_interop_summary_csv.py` |
| `ccv_live_illumina_snv_alignstats_20260708T145000Z` | 599M | `2026-07-08T14:57:50Z .dayoa_agent/visits/20260708.jsonl` |
| `ccv_live_illumina_snv_alignstats_20260708T150000Z` | 598M | `2026-07-08T15:02:36Z unlock_fails.log` |
| `ccv_live_illumina_snv_alignstats_20260708T150500Z` | 965M | `2026-07-09T01:10:54Z logs/slurm/alignstats/...err` |
| `ccv_live_illumina_snv_alignstats_relatedness_vep_multiqc_20260708T142032Z` | 596M | `2026-07-08T14:32:04Z write_interop_summary_csv.py` |
| `ccv_live_illumina_snv_alignstats_relatedness_vep_multiqc_20260708T150500Z` | 598M | `2026-07-08T15:14:08Z unlock_fails.log` |
| `ccv_live_illumina_snv_alignstats_relatedness_vep_multiqc_20260708T152112Z` | 3.5G | `2026-07-09T01:08:51Z pipeline_workflow_checkpoint_20260709T010850Z.pdf` |
| `ccv_live_inflection_bjuice_product_v0_1_20260708T142032Z` | 597M | `2026-07-08T14:36:04Z .dayoa_agent/visits/20260708.jsonl` |
| `ccv_live_inflection_bjuice_product_v0_1_20260708T152112Z` | 11G | `2026-07-09T01:08:06Z .snakemake/log/2026-07-08T154834.926275.snakemake.log` |
| `ccv_live_ont_run_qc_20260708T152112Z` | 675M | `2026-07-08T17:18:52Z .dayoa_agent/visits/20260708.jsonl` |
| `ccv_live_ont_snv_alignstats_20260708T142032Z` | 597M | `2026-07-08T14:33:47Z unlock_fails.log` |
| `ccv_live_ont_snv_alignstats_20260708T152112Z` | 2.6G | `2026-07-08T18:12:58Z unlock_fails.log` |
| `ccv_live_ont_snv_alignstats_kitchensink_20260708T142032Z` | 597M | `2026-07-08T14:34:10Z unlock_fails.log` |
| `ccv_live_ont_snv_alignstats_kitchensink_20260708T152112Z` | 4.8G | `2026-07-08T20:31:07Z unlock_fails.log` |
| `ccv_live_pacbio_snv_alignstats_20260708T142032Z` | 597M | `2026-07-08T14:34:31Z unlock_fails.log` |
| `ccv_live_pacbio_snv_alignstats_20260708T152112Z` | 2.2G | `2026-07-08T18:33:41Z unlock_fails.log` |
| `ccv_live_roche_snv_alignstats_20260708T142032Z` | 597M | `2026-07-08T14:34:55Z .dayoa_agent/visits/20260708.jsonl` |
| `ccv_live_roche_snv_alignstats_20260708T152112Z` | 2.1G | `2026-07-08T15:50:48Z unlock_fails.log` |
| `ccv_live_ultima_run_qc_20260708T152112Z` | 598M | `2026-07-08T16:20:10Z unlock_fails.log` |
| `ccv_live_ultima_run_qc_20260708T162300Z` | 598M | `2026-07-08T16:26:19Z unlock_fails.log` |
| `ccv_live_ultima_run_qc_20260708T162800Z` | 598M | `2026-07-08T16:29:41Z unlock_fails.log` |
| `ccv_live_ultima_run_qc_20260708T163200Z` | 598M | `2026-07-08T16:32:09Z unlock_fails.log` |
| `ccv_live_ultima_snv_alignstats_20260708T142032Z` | 596M | `2026-07-08T14:32:50Z write_interop_summary_csv.py` |
| `ccv_live_ultima_snv_alignstats_20260708T152112Z` | 1.6G | `2026-07-08T17:24:35Z unlock_fails.log` |
| `ccv_live_ultima_snv_alignstats_kitchensink_20260708T142032Z` | 596M | `2026-07-08T14:33:24Z unlock_fails.log` |
| `ccv_live_ultima_snv_alignstats_kitchensink_20260708T152112Z` | 2.5G | `2026-07-08T20:07:32Z unlock_fails.log` |

## Planned Commands After Explicit Approval

The following are intentionally not executed before explicit approval:

1. Stop and quiesce workflows:
   - request/take over the six active analysis locks as needed;
   - cancel active `ubuntu` Slurm jobs for `jul8itelx4`;
   - kill the six active `ccv_live_*` tmux controller sessions;
   - verify `squeue` has no live jobs and no `dy-r`/Snakemake controller
     processes remain.
2. Export each analysis root above with `dyec export --wait`, e.g.
   - `dyec export --cluster jul8itelx4 --region us-west-2 --profile lsmc --source-path /fsx/analysis_results/ubuntu/<analysis_id> --destination-s3-uri s3://lsmc-ssf-sequencing-data/derived/jul8itelx4/full_analysis_results_export/20260709T011230Z/ubuntu/<analysis_id>/ --output-dir docs/plans/20260709T011230Z_jul8itelx4_export_delete/exports/<analysis_id> --wait --timeout-seconds 7200`
3. Verify S3 object count and byte count for each exported root.
4. After all exports verify, delete cluster with:
   - `dyec delete --cluster-name jul8itelx4 --region us-west-2 --profile lsmc --yes`
5. Poll until the cluster is not describable and FSx `fs-021b9667d227d3f65`
   is gone or reaches a terminal delete state.

## Control Ledger

| ID | Area | Requirement | Status | Category | Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| INV-001 | Inventory | Capture cluster, FSx, controller, Slurm, DRA, and export-source baseline before destructive action. | SUCCESS | plan_amendment | Gate 0 | orchestrator | Gate 0 sections above; `dyec delete --dry-run` changed no resources; `/fsx/analysis_results` inventory captured 33 `ubuntu` roots. |  | Baseline complete. |
| STOP-001 | Controllers | Stop active catalog controllers and cancel remaining Slurm work so exports are quiescent. | BLOCKED | legitimate_safety_handling | Gate 1 | orchestrator | Six active `ccv_live_*` tmux sessions and live Slurm jobs present at Gate 0. | Requires fresh explicit approval for kill/cancel plus lock takeover of active analysis roots. | Not performed. |
| EXP-001 | Export | Export all 33 `/fsx/analysis_results/ubuntu/<analysis_id>` roots to the proposed S3 export root and verify object/byte counts. | BLOCKED | feature_implementation | Gate 2 | orchestrator | Export scope table above; DYEC export source validation requires per-root exports. | Waiting for workflow quiescence after STOP-001 approval/completion. | Not performed. |
| DEL-001 | Cluster delete | Delete `jul8itelx4` after successful export verification and poll teardown. | BLOCKED | legitimate_safety_handling | Gate 3 | orchestrator | Dry-run reports cluster `CREATE_COMPLETE`, FSx `fs-021b9667d227d3f65`, active DRAs. | Requires fresh explicit approval after export verification; live delete will destroy the cluster stack, headnode, compute nodes, and managed FSx data. | Not performed. |

## Approval Boundary

No live controller kill, Slurm cancellation, FSx export, or cluster deletion has
been performed in this ledger yet.

The next required user action is explicit approval for the destructive step:

`approve stop/cancel active jul8itelx4 workflows, export all 33 analysis roots to the S3 prefix above, and delete jul8itelx4 including managed FSx fs-021b9667d227d3f65 after export verification`
