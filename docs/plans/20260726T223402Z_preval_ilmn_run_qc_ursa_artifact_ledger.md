# Preval mounted Illumina RunQC and Ursa artifact-recording ledger

Created: 2026-07-26T22:34:02Z
Scope: Run the no-BCL-to-FASTQ Illumina sequencing QC on the pre-validation
mounted Illumina run at the non-Ursa `preval-hiomr2` cluster, then verify that
the resulting MultiQC report contains the section set represented by the
provided reference report. Ensure the applicable important-output rule records
the required RunQC outputs in the Ursa artifacts file, if that contract is not
already implemented. This ledger does not alter the read-only source mount,
delete resources, intervene in Slurm, or run BCL Convert.

Controlling mount ledger:
`docs/plans/20260726T035509Z_bjuice_preval20_hiomr2_mounts_ledger.md`
Ledger path:
`docs/plans/20260726T223402Z_preval_ilmn_run_qc_ursa_artifact_ledger.md`

## Gate 0: inventory and baseline

- DYEC repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
  on branch `jem-candidate-260725`.
- Baseline worktree contains pre-existing modified and untracked plans,
  reports, temporary directories, `mount_preval_bjuice.md`, and other
  artifacts. This ledger is the only new local record owned by this work.
- Target cluster: `preval-hiomr2` in `us-west-2`, resolved by the controlling
  mount ledger as the non-Ursa cluster.
- Target source: the read-only mounted Illumina run
  `/fsx/run_dir_mounts/20260618_LH01106_0011_A23MFMCLT3/`, backed by
  `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/`.
- Requested workflow boundary: `illumina_run_qc` only; do not select either
  `illumina_bclconvert` or `illumina_run_qc_bclconvert`.
- Acceptance reference:
  `/Users/jmajor/Downloads/run_qc_illumina_all/20260512_LH01106_0007_B23K5JKLT4/20260512_LH01106_0007_B23K5JKLT4.multiqc.html`.
  Compare report/data sections, not its data values or run identity.
- Live limits: launch only after the mounted source, current catalog command,
  explicit output root, analysis-root lock contract, and Ursa artifact-file
  contract have all been verified. No scheduler or AWS service intervention is
  authorized.

## Execution evidence

- Live mount inspection found exactly one BCLConvert-style metrics directory:
  `Analysis/1/Data/Demux/`, containing `Demultiplex_Stats.csv`,
  `Demultiplex_Tile_Stats.csv`, `Top_Unknown_Barcodes.csv`, and
  `Index_Hopping_Counts.csv`. The source rule now scans below the mounted
  run's `Analysis/` directory, requires exactly one `Demultiplex_Stats.csv`,
  and stages only the supplied metrics into the canonical MultiQC input shape.
- The supported DayOA source branch is
  `codex/preval-illumina-run-qc-sections` at `59df1ab3`. It adds the mounted
  metrics scan, a strict run-context-only mode with no synthetic sample
  lineage, artifact-manifest support for `config/runs.tsv`, and parse safety
  for unselected empty-sample rules. Focused validation: 65 passed.
- The successful dry-run controller
  `preval_ilmn_run_qc_dryrun_20260726T230921Z` exited 0 and planned exactly
  six rules: `illumina_run_qc_fetch_metric_subset`,
  `illumina_run_qc_interop_summary`, `illumina_run_qc_json`,
  `illumina_run_qc_report`, `illumina_run_qc_multiqc`, and
  `produce_illumina_run_qc`. It did not plan a BCL-to-FASTQ or BCLConvert
  workflow rule.
- The dry-run's standard `analysis_artifacts.tsv` records
  `config/runs.tsv` as `run_context` and records both
  `summary.html` and `multiqc_report.html` as terminal artifacts. Its empty
  `artifact_lineage.tsv` has only a header, which correctly reflects a
  run-level QC with no fabricated sample/analysis-unit lineage.
- The reference report requires the BCLConvert and InterOp MultiQC module
  sections (plus standard software versions), with saved-data keys
  `multiqc_bclconvert_bylane`, `multiqc_bclconvert_bysample`, and
  `interop_runsummary`. The dry-run rendered an explicit `multiqc -m interop
  -m bclconvert -m custom_content` command over the staged metric subset.
- The live controller `preval_ilmn_run_qc_20260726T231133Z` reached the
  `illumina_run_qc_fetch_metric_subset` submission but DYEC rejected `sbatch`
  before a job was created: `RnD` cost-center usage was 181.28 hours stale,
  exceeding the configured 36-hour maximum. Its terminal status is exit 1;
  no matching QC job was present in Slurm. The controller released its
  analysis-root lock. No budget, cost-center, Slurm, AWS, BCLConvert, or mount
  state was changed.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| INV-001 | DYEC / target inventory | Verify the exact `preval-hiomr2` cluster, read-only mount, `illumina_run_qc` catalog contract, and current output/artifact-registration surfaces. | COMPLETE | legitimate_safety_handling | Gate 0 | Codex | CLI confirmed the exact AVAILABLE, read-only ILMN mount and its one metrics directory; reference report parsed structurally. |  | Target, mount, source URI, and report acceptance set are fixed. |
| CFG-002 | DayOA/DYEC output contract | Locate the rule owning important RunQC outputs; add Ursa-artifacts-file recording only if missing, with focused tests. | COMPLETE | feature_implementation | Gate 1 | Codex | `analysis_artifacts.tsv` / `artifact_lineage.tsv` are the standard Ursa artifact records; source branch `59df1ab3`; focused suite 65 passed. |  | Run context and terminal RunQC HTML artifacts are recorded without invented lineage. |
| RUN-003 | DayOA run preparation | Create/validate an explicit no-BCLConvert run context and analysis root; log visit and acquire the required write lock before workflow writes. | COMPLETE | legitimate_safety_handling | Gate 1 | Codex | Fresh dry-run root `preval_ilmn_run_qc_dryrun_20260726T230921Z`, exit 0; launch performed controller visit/lock and released it. |  | Exact six-rule plan has no BCL-to-FASTQ rule. |
| RUN-004 | DayOA execution | Run the supported no-BCL-to-FASTQ `illumina_run_qc` path from an `ubuntu` interactive bash-login `tmux` session on `preval-hiomr2`. | BLOCKED | external_control_plane | Gate 1 | DYEC cost-center refresh owner | Live root `preval_ilmn_run_qc_20260726T231133Z`; `sbatch` rejection: latest RnD cost-center hour `2026-07-19T10:00:00Z`, age 181.28h, maximum 36h; controller exit 1; no QC job submitted. | Current cost-center usage data is stale. | Do not bypass the enforcement gate. Refresh the cost-center data under its owning process, then launch a fresh root using the verified command. |
| QA-005 | MultiQC acceptance | Compare generated report and `multiqc_data` section identities against the reference report; diagnose and make the smallest explicit scan-path correction if required. | BLOCKED | external_dependency | Gate 5 | DYEC cost-center refresh owner | Reference expectation and rendered MultiQC command verified in the successful dry-run. | Live `multiqc_report.html` could not be generated because no job was allowed to start. | On a successful fresh run, compare HTML anchors and `multiqc_data.json` section/data keys to the recorded reference set. |
| EVD-006 | Durable evidence | Record the executed command, output paths, Ursa-artifact entry, report-section comparison, and final terminal status in this ledger. | COMPLETE | feature_implementation | Gate 5 | Codex | This ledger records dry-run, live-controller, artifact-manifest, lock, and block evidence. |  | All ledger rows are terminal; the execution objective remains blocked, not complete. |
