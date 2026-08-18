# `pclu-18045` DYEC 18.0.51 Fresh RC0 Remediation Ledger

Controlling request: force-configure `pclu-18045` from exact local DYEC
`18.0.50`, then obtain fresh same-root dry/live `rc=0` evidence for the eleven
listed production catalog lanes.  The three Run-QC lanes use their explicit
mounted run contexts; every other lane uses explicit slim-data six-manifests.

Supersedes for new execution only:
`docs/plans/20260818T165711Z_pclu_18045_fresh_rc0_catalog_execution_ledger.md`.
That earlier ledger remains an immutable record of its terminal outcomes.

## Gate 0 baseline

- Local operator checkout: exact annotated tag `18.0.50`, peeled commit
  `012f194c1880ad9f78c0d57da231c495005ef4c3`; `source ./activate` reports
  `Daylily Ephemeral Cluster 18.0.50`.
- The mutable current catalog changes requested here require the forward-only
  successor `18.0.51`; it retains the DayOA `15.0.28` pin, removes the two
  retired entries, and makes missing final MultiQC/evidence targets explicit.
  Each render must confirm that immutable pin before any controller launch.
- No raw Snakemake, queue intervention, implicit inputs, or replacement live
  root after a passing dry run is allowed.  A dry/run pair remains in one
  analysis ID/root and differs only by removal of `-n`.
- The two retired production entries are not launch scope:
  `bjuice-v2-hg002-custom-multi-analysis-unit-hiomr2-kitchensink-mega` and
  `inflection-bjuice-product-v0.2`.  They require a forward-only current-catalog
  removal in a new DYEC release; immutable `18.0.50` is not modified.
- User explicitly authorizes `dyec headnode configure --force`; this removes
  only the DAYOA/DAY-EC Conda environments before rebuild.  It does not
  authorize Slurm administration, data deletion, export cleanup, or retries
  outside the controlled fresh-root lane executions below.
- Read-only inventory at `2026-08-18T23:32Z`: cluster `pclu-18045` is
  `UPDATE_COMPLETE` with its compute fleet `RUNNING`; FSx has
  `11,635,338,752 KiB` free (4% used); the four explicit ILMN/ONT/Ultima run
  mounts are `AVAILABLE`; `pclu-18045-ccenter` is active with a $999 monthly
  cap; controller and Slurm-job counts are both zero. Thirty-one tmux panes
  are stale/idle evidence only and are not touched.

## Control ledger

| ID | Area | Requirement | Status | Category | Gate | Evidence / terminal note |
|---|---|---|---|---|---|---|
| G0 | Release/cluster | Verify exact cluster state, cost/FSx availability, controller inventory, mounts, source pins, explicit input contracts, and empty fresh analysis IDs. | IN_PROGRESS | legitimate_safety_handling | Gate 0 | No cloud mutation before this row supplies the exact evidence. |
| HN-01 | Headnode | Force-configure `pclu-18045` with local DYEC `18.0.50`; prove remote `dyec version` and analysis command surface. | SUCCESS | config_or_startup_contract | Gate 0 | The original configure path's DayOA-bootstrap SSM receipt `7615edca-7f7a-4611-97a7-2bf05d7a07e1` completed `Success`/`rc=0`; remote `dyec version` reports `18.0.50` and `dyec analysis --help` succeeds. A later duplicate local client was terminated before it could add further config work. |
| REL-01 | Forward catalog release | Publish immutable DYEC `18.0.51` from `18.0.50` after only the user-directed current-catalog removals and final MultiQC/evidence target additions. | IN_PROGRESS | plan_amendment | Gate 0 | `18.0.50` remains immutable. Remote tag availability and source/payload parity are required before tag/push. |
| HN-02 | Headnode | Force-configure `pclu-18045` with the exact released DYEC `18.0.51`; prove remote `dyec version` and analysis command surface before launch. | OPEN | config_or_startup_contract | Gate 0 | The prior 18.0.50 configuration is preserved as baseline; no second configure begins until the successor tag is immutable. |
| CAT-01 | Catalog | Render all eleven exact commands from `18.0.51`; prove DayOA `15.0.28`, `-j 333 -T 0 -p`, dry-only `-n`, unique roots, and declared explicit inputs. | OPEN | active_product_contract | Gate 0 | Render first; never substitute targets/config/manifests. |
| MQC-01 | Catalog | Confirm SOLO ONT, SOLO Ultima, SOLO CG, and both pangenome kitchen-sink closures include final MultiQC HTML plus evidence manifest. | IN_PROGRESS | active_product_contract | Gate 0 | Inspection found explicit targets missing in the Ultima SOLO, CG SOLO, and Ultima pangenome entries; REL-01 adds them forward-only. |
| RUN-01 | ILMN Run-QC | `illumina_run_qc`, explicit mounted ILMN run context, no BCL Convert. | OPEN | active_product_contract | Gate 1 | Fresh dry `rc=0`/zero jobs, then same-root live `rc=0`. |
| RUN-02 | ONT Run-QC | `ont_run_qc`, explicit mounted ONT run context, no basecalling. | OPEN | active_product_contract | Gate 1 | Fresh dry `rc=0`/zero jobs, then same-root live `rc=0`. |
| RUN-03 | Ultima Run-QC | `ultima_run_qc`, explicit mounted Ultima run context, no basecalling. | OPEN | active_product_contract | Gate 1 | Fresh dry `rc=0`/zero jobs, then same-root live `rc=0`. |
| RUN-04 | HIOMR2 | `hiomr2_slim_kitchensink_mega`, 5x ILMN + 5x ONT slim-data. | OPEN | active_product_contract | Gate 1 | Previous PyPI 502 is diagnostic history only; new root requires a clean dry/live proof. |
| RUN-05 | Bjuice v0.9 | `inflection-bjuice-product-v0.9`, 5x ILMN + 5x ONT slim-data. | OPEN | active_product_contract | Gate 1 | Previous ExpansionHunter dynamic-linker failure must be resolved by released pinned source/runtime, never fallback. |
| RUN-06 | SOLO ILMN | `illumina_hg002_kitchensink_multiqc`, ILMN slim-data. | OPEN | active_product_contract | Gate 1 | Require final MultiQC and evidence completion through controller `rc=0`. |
| RUN-07 | SOLO ONT | `ont_snv_alignstats_kitchensink`, ONT slim-data. | OPEN | active_product_contract | Gate 1 | Require final MultiQC/evidence targets and no duplicate-AU benchmark failure. |
| RUN-08 | SOLO Ultima | `ultima_snv_alignstats_kitchensink`, Ultima slim-data. | OPEN | active_product_contract | Gate 1 | Require final MultiQC/evidence targets and no ExpansionHunter linker failure. |
| RUN-09 | SOLO CG | `complete_genomics_cg_snv_concordance`, CG slim-data. | OPEN | active_product_contract | Gate 1 | Require exact staged mate receipt plus final MultiQC/evidence targets. |
| RUN-10 | Pangenome ILMN | `illumina_sentieon_pangenome_kitchensink`, ILMN slim-data. | OPEN | active_product_contract | Gate 1 | Require graph deduper closure with no semantic config substitution. |
| RUN-11 | Pangenome Ultima | `ultima_sentieon_pangenome_kitchensink`, Ultima slim-data. | OPEN | active_product_contract | Gate 1 | Require explicit UG CRAM/.crai/alignment contract and graph/reference closure. |
| CAT-02 | Future catalog | Remove the two named retired Bjuice v2/v0.2 commands from mutable `current` in a forward-only DYEC release. | OPEN | active_product_contract | Gate 5 | Do not rewrite historical snapshots or `18.0.50`; record the successor tag and payload parity. |
| EVD-01 | Evidence | Update this ledger with dry/live controller receipts, effective argv, terminal rc, and blockers; export only after explicitly requested post-RC0 authorization. | OPEN | legitimate_safety_handling | Gate 5 | No delete/export action is implied by this remediation request. |
