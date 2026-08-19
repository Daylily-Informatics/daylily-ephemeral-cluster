# `pclu-18045` DYEC 18.0.52 / DayOA 15.0.29 Fresh RC0 Remediation Ledger

Controlling request: use released DYEC `18.0.52`, pinned only to released DayOA
`15.0.29`, to obtain fresh same-root dry/live `rc=0` evidence for the eight
production catalog lanes whose preceding `pclu-18045` controllers ended
nonzero. The three Run-QC lanes already reached fresh dry/live `rc=0` in this
campaign and are context only, not rerun scope. Every remediation lane uses an
explicit slim-data six-manifest.

Supersedes for new execution only:
`docs/plans/20260818T165711Z_pclu_18045_fresh_rc0_catalog_execution_ledger.md`.
That earlier ledger remains an immutable record of its terminal outcomes.

## Gate 0 baseline

- The immutable baseline is DYEC `18.0.50`; its earlier controller outcomes
  diagnose scope only and cannot satisfy this fresh RC0 campaign.
- DayOA `15.0.29` is an annotated, pushed tag peeling to
  `07aff68545687a4c7b29d570993613dacdc15bad`. It provides the released
  HIOMR2/ExpansionHunter runtime contracts, the duplicate-AU benchmark fix,
  graph-deduper routing, and explicit canonical UG pangenome input routing.
- DYEC `18.0.52` is the forward-only release being prepared from `18.0.51`.
  Its frozen/current catalog must pin only `15.0.29`; HIOMR2 and Bjuice also
  set `PIP_NO_BUILD_ISOLATION=1` before their controller-owned `dy-r` command.
  Each render must confirm this exact immutable pin before any controller
  launch.
- No raw Snakemake, queue intervention, implicit inputs, or replacement live
  root after a passing dry run is allowed.  A dry/run pair remains in one
  analysis ID/root and differs only by removal of `-n`.
- The two retired production entries are not launch scope and were removed
  from mutable `current` by the already-published `18.0.51`:
  `bjuice-v2-hg002-custom-multi-analysis-unit-hiomr2-kitchensink-mega` and
  `inflection-bjuice-product-v0.2`. Immutable historical snapshots are not
  rewritten.
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
- Forward release `18.0.51` is an annotated, pushed tag at
  `35da09077a63177eb768a4a74d4ad9b1f134d645`.  Its source and packaged
  catalog hashes are both
  `0e755ea6b3a44f79a905f8fa909f8ec3c8a62650fbf6231b6de4eb79767a7f65`.
  It preserves the `15.0.28` DayOA pin, removes only the named Bjuice-v2
  command and v0.2 alias from `current`, and adds explicit final MultiQC HTML
  plus evidence-manifest targets to SOLO Ultima, SOLO CG, and Ultima
  pangenome. `18.0.52` preserves those target additions.
- At `2026-08-18T23:54Z`, a single authorized successor force-configure
  completed.  Remote `dyec version` reports `18.0.51` and `dyec analysis
  --help` succeeds.  No workflow controller or Slurm job was present before
  configuration began.

## Control ledger

| ID | Area | Requirement | Status | Category | Gate | Evidence / terminal note |
|---|---|---|---|---|---|---|
| G0 | Release/cluster | Verify exact cluster state, cost/FSx availability, controller inventory, mounts, source pins, explicit input contracts, and empty fresh analysis IDs. | IN_PROGRESS | legitimate_safety_handling | Gate 0 | No cloud mutation before this row supplies the exact evidence. |
| HN-01 | Headnode | Force-configure `pclu-18045` with local DYEC `18.0.50`; prove remote `dyec version` and analysis command surface. | SUCCESS | config_or_startup_contract | Gate 0 | The original configure path's DayOA-bootstrap SSM receipt `7615edca-7f7a-4611-97a7-2bf05d7a07e1` completed `Success`/`rc=0`; remote `dyec version` reports `18.0.50` and `dyec analysis --help` succeeds. A later duplicate local client was terminated before it could add further config work. |
| REL-01 | Forward catalog release | Publish immutable DYEC `18.0.51` from `18.0.50` after only the user-directed current-catalog removals and final MultiQC/evidence target additions. | SUCCESS | plan_amendment | Gate 0 | Annotated tag `18.0.51` points to `35da0907…`, is pushed, and source/package catalog copies have identical SHA-256 `0e755e…f65`. Semantic diff is exactly one removed command, one removed alias, and the three requested final-report target additions. |
| REL-02 | DayOA runtime release | Publish immutable DayOA `15.0.29` containing only the RC0 runtime and graph-input remediation contracts. | SUCCESS | active_product_contract | Gate 0 | Annotated tag `15.0.29` peels to `07aff685…15bad`; focused syntax/contract validation passed before release. |
| REL-03 | Forward catalog release | Publish immutable DYEC `18.0.52`, frozen/current pinned only to DayOA `15.0.29`, with the two deterministic HIOMR2/Bjuice controller environment prefixes. | IN_PROGRESS | active_product_contract | Gate 0 | Source/package parity, parse/render checks, annotated tag, and deployment proof are required before any new controller. |
| HN-02 | Headnode | Force-configure `pclu-18045` with the exact released DYEC `18.0.51`; prove remote `dyec version` and analysis command surface before launch. | SUCCESS | config_or_startup_contract | Gate 0 | One successor configure client completed; `dyec headnode run` proved remote `Daylily Ephemeral Cluster 18.0.51` and `ANALYSIS_SURFACE_OK`. |
| HN-03 | Headnode | Force-configure `pclu-18045` with exact released DYEC `18.0.52`; prove remote `dyec version` and controller surface. | OPEN | config_or_startup_contract | Gate 0 | One authorized successor configure only; no controller begins until remote version and catalog surface match. |
| CAT-01 | Catalog | Render the eight remediation commands from `18.0.52`; prove DayOA `15.0.29`, `-j 333 -T 0 -p`, dry-only `-n`, unique roots, and declared explicit inputs. | OPEN | active_product_contract | Gate 0 | Render first; never substitute targets/config/manifests. |
| MQC-01 | Catalog | Confirm SOLO ONT, SOLO Ultima, SOLO CG, and both pangenome kitchen-sink closures include final MultiQC HTML plus evidence manifest. | IN_PROGRESS | active_product_contract | Gate 0 | The `18.0.52` release test asserts the five exact target pairs; each launch render must preserve them. |
| RUN-01 | ILMN Run-QC | `illumina_run_qc`, explicit mounted ILMN run context, no BCL Convert. | NO_LONGER_NEEDED | scope_control | Gate 1 | Fresh campaign dry/live controllers already reached RC0 and were exported; user narrowed this remediation wave to only commands that ended nonzero. |
| RUN-02 | ONT Run-QC | `ont_run_qc`, explicit mounted ONT run context, no basecalling. | NO_LONGER_NEEDED | scope_control | Gate 1 | Fresh campaign dry/live controllers already reached RC0 and were exported; user narrowed this remediation wave to only commands that ended nonzero. |
| RUN-03 | Ultima Run-QC | `ultima_run_qc`, explicit mounted Ultima run context, no basecalling. | NO_LONGER_NEEDED | scope_control | Gate 1 | Fresh campaign dry/live controllers already reached RC0 and were exported; user narrowed this remediation wave to only commands that ended nonzero. |
| RUN-04 | HIOMR2 | `hiomr2_slim_kitchensink_mega`, 5x ILMN + 5x ONT slim-data. | OPEN | active_product_contract | Gate 1 | Previous PyPI 502 is diagnostic history only; new root requires a clean dry/live proof. |
| RUN-05 | Bjuice v0.9 | `inflection-bjuice-product-v0.9`, 5x ILMN + 5x ONT slim-data. | OPEN | active_product_contract | Gate 1 | Previous ExpansionHunter dynamic-linker failure must be resolved by released pinned source/runtime, never fallback. |
| RUN-06 | SOLO ILMN | `illumina_hg002_kitchensink_multiqc`, ILMN slim-data. | OPEN | active_product_contract | Gate 1 | Require final MultiQC and evidence completion through controller `rc=0`. |
| RUN-07 | SOLO ONT | `ont_snv_alignstats_kitchensink`, ONT slim-data. | OPEN | active_product_contract | Gate 1 | Require final MultiQC/evidence targets and no duplicate-AU benchmark failure. |
| RUN-08 | SOLO Ultima | `ultima_snv_alignstats_kitchensink`, Ultima slim-data. | OPEN | active_product_contract | Gate 1 | Require final MultiQC/evidence targets and no ExpansionHunter linker failure. |
| RUN-09 | SOLO CG | `complete_genomics_cg_snv_concordance`, CG slim-data. | OPEN | active_product_contract | Gate 1 | Require exact staged mate receipt plus final MultiQC/evidence targets. |
| RUN-10 | Pangenome ILMN | `illumina_sentieon_pangenome_kitchensink`, ILMN slim-data. | OPEN | active_product_contract | Gate 1 | Require graph deduper closure with no semantic config substitution. |
| RUN-11 | Pangenome Ultima | `ultima_sentieon_pangenome_kitchensink`, Ultima slim-data. | OPEN | active_product_contract | Gate 1 | Require explicit UG CRAM/.crai/alignment contract and graph/reference closure. |
| CAT-02 | Future catalog | Remove the two named retired Bjuice v2/v0.2 commands from mutable `current` in a forward-only DYEC release. | SUCCESS | active_product_contract | Gate 0 | `18.0.51` removed the named command and alias only from `current`; `18.0.52` retains that removal. |
| EVD-01 | Evidence | Update this ledger with dry/live controller receipts, effective argv, terminal rc, and blockers; export only after explicitly requested post-RC0 authorization. | OPEN | legitimate_safety_handling | Gate 5 | No delete/export action is implied by this remediation request. |
