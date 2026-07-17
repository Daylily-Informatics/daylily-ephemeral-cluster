# DYEC tst-r5 remaining-10 HIOMRS kitchensink execution ledger

Date: 2026-07-16

## Control Ledger

Controlling request: create the ILMN and ONT DRA mounts required by the supplied manifests on `dyec-tst-r5`, clone the maximum released DayOA tag, dry-run the HIOMRS kitchensink with the user-specified controller flags, and launch it live only if the dry-run is clean.

Ledger path: `docs/plans/20260716T153510Z_dyec_tst_r5_remaining10_hiomrs_kitchensink_ledger.md`

### Runtime contract

- AWS profile: `lsmc` (explicit; never default)
- Region: `us-west-2`
- Cluster: `dyec-tst-r5`
- DayOA tag: `11.0.15` (highest strict semver published on `origin` at Gate 0)
- DayOA tag object: `23b3660b4179b2fdea58d87837570b4264ed1825`
- DayOA commit: `ef279ccafa70dd6244c6feac39340cc34f4a80f3`
- Workset/analysis id: `remaining10-hiomrs-11015-20260716T153510Z`
- Tmux session: `remaining10_hiomrs_11015_20260716`
- Genome/executor: `slurm hg38`
- User flags: `-j 300 -p -k -T 2`; dry-run first with `-n`, then the identical command without `-n` only after dry-run return code 0.
- Catalog defaults retained explicitly: raw ONT half-open interval `[0,24)`, `--rerun-triggers mtime`, and `--rerun-incomplete`.
- Manifest handoff prefix: `s3://lsmc-dayoa-control-data-usw2/dayoa_input_manifests/dyec-tst-r5/remaining10-hiomrs-11015-20260716T153510Z/`.

### Gate 0 baseline

- DYEC repo: clean `main...origin/main`, commit `7dbb9cb5b1f4e02b04fbbeff6cb9aa0c172710a7`, version `10.3.26`.
- DayOA repo: clean `main...origin/main`, commit `ef279ccafa70dd6244c6feac39340cc34f4a80f3`.
- Cluster: `dyec cluster-info --profile lsmc --region us-west-2` reports `dyec-tst-r5 CREATE_COMPLETE`.
- Filesystem: `fs-048f04318d6585174`, `PERSISTENT_2`, lifecycle `AVAILABLE`.
- Existing DRA inventory: one association, `dra-05affa9dc4fdd31be`, `/references/`, lifecycle `AVAILABLE`.
- Local managed run mounts: `dyec mounts list --cluster dyec-tst-r5 --region us-west-2 --profile lsmc` reports none.
- Samples manifest: `/Users/jmajor/projects/lsmc/remaining/samples.tsv`, 10 records, SHA-256 `0a662e6abbd200a8636f7c2bb4dec73f55bdacaf9e1995977e77108ffc3a5824`.
- Units manifest: `/Users/jmajor/projects/lsmc/remaining/units.tsv`, 10 records, SHA-256 `0a070b8f9219e7e4dd443175470134f1379c83e629320234ae7500df6392e0c9`.
- Required mount roots extracted from `units.tsv`: `/fsx/run_dir_mounts/20260618_LH01106_0011_A23MFMCLT3` and `/fsx/run_dir_mounts/pca100-2026`.
- ILMN source: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/20260618_LH01106_0011_A23MFMCLT3/`; read-only S3 listing returned `Analysis/1/CopyComplete.txt`.
- ONT source: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/2026/`; read-only S3 listing returned an object under the prefix.
- Highest released DayOA tag: strict-semver remote tag inventory ends at annotated `11.0.15`; peeled commit equals current clean `main` commit `ef279ccafa70dd6244c6feac39340cc34f4a80f3`.
- No raw `snakemake` invocation is authorized. Workflow setup and execution must occur as `ubuntu` in one persistent `bash -il` tmux pane through `day-clone`, separate `source dyoainit`, `dy-a`, and `dy-r` commands.
- DRA waits use `--timeout-seconds 5400`, comfortably above the 40-minute minimum, and are never retried or duplicated merely because lifecycle remains `CREATING`.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Gate 0 | Freeze repo, manifest, cluster, FSx/DRA, S3, release-tag, and command contracts | SUCCESS | active_product_contract | Gate 0 | orchestrator | Baseline recorded above from live read-only checks |  | Gate 0 is complete. |
| MNT-001 | DYEC/AWS | Create and wait for the read-only ILMN DRA at the exact manifest mount root | SUCCESS | active_product_contract | Gate 1 | orchestrator | Corrected `--batch-import-metadata-on-create` invocation created `dra-0aaa29750b458e11e`; original waiter returned lifecycle `AVAILABLE`. |  | Read-only ILMN DRA is available at `/fsx/run_dir_mounts/20260618_LH01106_0011_A23MFMCLT3/`. |
| MNT-002 | DYEC/AWS | Create and wait for the read-only ONT DRA at the exact manifest mount root | SUCCESS | active_product_contract | Gate 1 | orchestrator | Corrected `--batch-import-metadata-on-create` invocation created `dra-0282dd397c5f6ec56`; original waiter returned lifecycle `AVAILABLE`. |  | Read-only ONT DRA is available at `/fsx/run_dir_mounts/pca100-2026/`. |
| MNT-003 | DYEC/headnode | Verify both exact mounted paths are usable on the headnode | SUCCESS | contract_test | Gate 1 | orchestrator | `dyec mounts verify` returned success and lifecycle `AVAILABLE` independently for both mount ids. |  | Both exact manifest mount roots are usable on `dyec-tst-r5`. |
| DAY-001 | DayOA/headnode | Create a fresh explicit `day-clone -t 11.0.15` analysis root and stage the exact manifests | SUCCESS | active_product_contract | Gate 2 | orchestrator | One-pane `bash -il` tmux `remaining10_hiomrs_11015_20260716`; checkout `/fsx/analysis_results/dyec-tst-r5/remaining10-hiomrs-11015-20260716T153510Z/daylily-omics-analysis`; exact tag `11.0.15`, commit `ef279ccafa70dd6244c6feac39340cc34f4a80f3`; staged hashes equal Gate 0. |  | Fresh exact-tag checkout and exact manifest staging are complete. |
| DRY-001 | DayOA/headnode | Run the full catalog HIOMRS kitchensink with `-j 300 -p -k -T 2 -n` and require rc 0 | BLOCKED | contract_test | Gate 3 | orchestrator | `source dyoainit` returned rc `1` before `dy-a`: mandatory `mmdc` smoke render failed with `TimeoutError: Timed out after 30000 ms while waiting for the WS endpoint URL to appear in stdout!`, followed by `Error: Failed to install the DAYOA environment.` | The new headnode's DAYOA bootstrap cannot validate Mermaid/Chrome headless, while this kitchensink explicitly requests DAG/rulegraph/filegraph artifacts. The workflow contract requires stopping when `dyoainit` fails. | Diagnose and repair the supported DayOA Mermaid/Chrome bootstrap, then rerun `source dyoainit`; do not bypass the smoke check or reuse the partially initialized environment as healthy. |
| LIVE-001 | DayOA/headnode | Acquire the analysis-root write lock and launch the same HIOMRS kitchensink without `-n` | BLOCKED | active_product_contract | Gate 4 | orchestrator | No `dy-a`, dry-run, or live `dy-r` command was sent. The analysis lock was released after the bootstrap failure. | Upstream DRY-001 cannot run until supported initialization succeeds. | Resume only after initialization and dry-run both return rc 0; reacquire the exact analysis-root write lock before live execution. |
| LIVE-002 | DayOA/headnode | Prove persistent controller, initial Slurm queue state, and exact log/attach handles | BLOCKED | contract_test | Gate 5 | orchestrator | `squeue` contains only its header; no `dy-r`, `day_run`, or Snakemake process exists. Tmux remains alive with exactly one window and one pane for inspection. | No live controller was launched because DRY-001 is blocked. | Attach handle remains `tmux attach -t remaining10_hiomrs_11015_20260716`; no workflow jobs exist. |

## Final Report

All rows terminal: yes

Objective complete: no

Status counts:

- SUCCESS: 5
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 3
- IN_PROGRESS: 0
- OPEN: 0

Changed files:

- `daylily-ephemeral-cluster`: this ledger only.

Validation:

- Gate 0 live and local evidence recorded above.
- Both exact DRA waiters returned `AVAILABLE`; both `dyec mounts verify` checks passed.
- DayOA checkout and staged manifest hashes match the frozen tag and local inputs.
- `source dyoainit` -> rc `1`, mandatory Mermaid Chrome-headless smoke-render timeout.
- Post-stop status: no Slurm jobs and no workflow controller process; analysis lock released.

Non-success terminal rows:

- `DRY-001` `BLOCKED`: supported DayOA initialization failed its mandatory Mermaid smoke render; repair is required before `dy-a` or dry-run.
- `LIVE-001` `BLOCKED`: dry-run gate did not pass, so no live command was authorized or launched.
- `LIVE-002` `BLOCKED`: no live controller exists; the one-pane tmux is retained only for evidence/resumption.

Residual risks:

- The partially created `DAYOA` environment must not be treated as healthy merely because it now exists; its installer returned rc 1.
- The live workflow remains gated on successful supported initialization, a clean dry-run, and reacquisition of the analysis-root write lock.
