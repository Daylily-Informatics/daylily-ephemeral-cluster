# `pclu-18045` DYEC 18.0.53 / DayOA 15.0.30 Fresh RC0 Remediation Ledger

Controlling request: use released DYEC `18.0.53`, pinned only to released DayOA
`15.0.30`, to obtain fresh same-root dry/live `rc=0` evidence for the eight
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
- DayOA `15.0.29` (commit `07aff68545687a4c7b29d570993613dacdc15bad`) was the
  first remediation source release: it provides the released
  HIOMR2/ExpansionHunter runtime contracts, duplicate-AU benchmark fix,
  graph-deduper routing, and canonical UG pangenome input routing.
- DayOA `15.0.30` is an annotated, pushed successor peeling to
  `65c45c74e922c276eeb676ed6ed24bfae7fbe859`. It makes the current
  `produce_sentd_snv_vcf` selector enumerate only valid Sentieon-DNA tuples
  and prevents `pre_prep_ultima_cram` from claiming the derived
  `canonical_reference/` graph input. These are fail-closed corrections found
  by the initial pangenome dry controllers before workflow work submission.
- DYEC `18.0.52` is the immutable release used for the first six dry roots and
  their valid same-root continuations. It remains frozen to `15.0.29`.
- DYEC `18.0.53` is the annotated, pushed successor peeling to
  `3f41a6b4842d55e9eef7942816daa48e85cb2ba0`. Its frozen/current catalog pins
  only `15.0.30`; source and packaged catalog copies have identical SHA-256
  `f7b1b7563e5ca2569c8c008c99b1662915e36488e779c6a0e017df9cea97abd2`.
  HIOMR2 and Bjuice retain `PIP_NO_BUILD_ISOLATION=1` before their
  controller-owned `dy-r` command. Each fresh pangenome render must confirm
  this exact immutable pin before launch.
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
- At `2026-08-19T02:11Z`, the authorized `18.0.53` force-configure correctly
  refused while the HIOMR2, Bjuice, and CG live controllers were active. No
  controller, Slurm, lock, or source state was changed by that refusal. The
  configure will be retried only after all three current controllers are
  terminal; it is not safe to replace the DayOA/DYEC runtime beneath them.

## Control ledger

| ID | Area | Requirement | Status | Category | Gate | Evidence / terminal note |
|---|---|---|---|---|---|---|
| G0 | Release/cluster | Verify exact cluster state, cost/FSx availability, controller inventory, mounts, source pins, explicit input contracts, and empty fresh analysis IDs. | IN_PROGRESS | legitimate_safety_handling | Gate 0 | Initial inventory completed before launches; current live-controller inventory is deliberately nonempty and blocks successor configuration. |
| HN-01 | Headnode | Force-configure `pclu-18045` with local DYEC `18.0.50`; prove remote `dyec version` and analysis command surface. | SUCCESS | config_or_startup_contract | Gate 0 | The original configure path's DayOA-bootstrap SSM receipt `7615edca-7f7a-4611-97a7-2bf05d7a07e1` completed `Success`/`rc=0`; remote `dyec version` reports `18.0.50` and `dyec analysis --help` succeeds. A later duplicate local client was terminated before it could add further config work. |
| REL-01 | Forward catalog release | Publish immutable DYEC `18.0.51` from `18.0.50` after only the user-directed current-catalog removals and final MultiQC/evidence target additions. | SUCCESS | plan_amendment | Gate 0 | Annotated tag `18.0.51` points to `35da0907…`, is pushed, and source/package catalog copies have identical SHA-256 `0e755e…f65`. Semantic diff is exactly one removed command, one removed alias, and the three requested final-report target additions. |
| REL-02 | DayOA runtime release | Publish immutable DayOA `15.0.29` containing only the RC0 runtime and graph-input remediation contracts. | SUCCESS | active_product_contract | Gate 0 | Annotated tag `15.0.29` peels to `07aff685…15bad`; focused syntax/contract validation passed before release. |
| REL-03 | Forward catalog release | Publish immutable DYEC `18.0.52`, frozen/current pinned only to DayOA `15.0.29`, with the two deterministic HIOMR2/Bjuice controller environment prefixes. | SUCCESS | active_product_contract | Gate 0 | Annotated/pushed `18.0.52` points to `96ddaa0c066a64ea703bc5313a4f1c8c93f5290e`; its source/package catalog hash is `0daa0d31…34709`. |
| HN-02 | Headnode | Force-configure `pclu-18045` with the exact released DYEC `18.0.51`; prove remote `dyec version` and analysis command surface before launch. | SUCCESS | config_or_startup_contract | Gate 0 | One successor configure client completed; `dyec headnode run` proved remote `Daylily Ephemeral Cluster 18.0.51` and `ANALYSIS_SURFACE_OK`. |
| HN-03 | Headnode | Force-configure `pclu-18045` with exact released DYEC `18.0.52`; prove remote `dyec version` and controller surface. | SUCCESS | config_or_startup_contract | Gate 0 | Configure completed before the first dry wave; remote reported `18.0.52` / DayOA `15.0.29`. |
| REL-04 | DayOA source release | Publish immutable DayOA `15.0.30` for the two pangenome dry-closure defects found before workflow submission. | SUCCESS | active_product_contract | Gate 0 | Annotated/pushed `15.0.30` peels to `65c45c74…be859`; focused selector/canonical-input tests passed `17/17`. |
| REL-05 | Forward catalog release | Publish immutable DYEC `18.0.53`, frozen/current pinned only to DayOA `15.0.30`. | SUCCESS | active_product_contract | Gate 0 | Annotated/pushed `18.0.53` peels to `3f41a6b4…2ba0`; focused frozen-snapshot/catalog tests passed `5/5`; source/package bytes match. |
| HN-04 | Headnode | Force-configure `pclu-18045` with exact released DYEC `18.0.53`; prove remote version and catalog surface before the replacement pangenome dry roots. | BLOCKED | legitimate_safety_handling | Gate 0 | `--force` was refused by the active-controller safety check at `2026-08-19T02:11Z`. CG is now terminal; retry only after the remaining HIOMR2 and Bjuice controllers are terminal. |
| CAT-01 | Catalog | Render the eight remediation commands from `18.0.52`; prove DayOA `15.0.29`, `-j 333 -T 0 -p`, dry-only `-n`, unique roots, and declared explicit inputs. | SUCCESS | active_product_contract | Gate 0 | All eight rendered with the declared six-manifests and exact flags; the two pangenome dry failures were source selector closures before submitted work. |
| CAT-03 | Catalog | Render the two replacement pangenome remediation commands from `18.0.53`; prove DayOA `15.0.30`, same flags, fresh roots, and declared explicit inputs. | OPEN | active_product_contract | Gate 0 | Cannot render/launch on the headnode until HN-04 succeeds. |
| MQC-01 | Catalog | Confirm SOLO ONT, SOLO Ultima, SOLO CG, and both pangenome kitchen-sink closures include final MultiQC HTML plus evidence manifest. | SUCCESS | active_product_contract | Gate 0 | `18.0.52` and `18.0.53` release tests assert the exact target pairs; all relevant controller argv retain them. |
| RUN-01 | ILMN Run-QC | `illumina_run_qc`, explicit mounted ILMN run context, no BCL Convert. | NO_LONGER_NEEDED | scope_control | Gate 1 | Fresh campaign dry/live controllers already reached RC0 and were exported; user narrowed this remediation wave to only commands that ended nonzero. |
| RUN-02 | ONT Run-QC | `ont_run_qc`, explicit mounted ONT run context, no basecalling. | NO_LONGER_NEEDED | scope_control | Gate 1 | Fresh campaign dry/live controllers already reached RC0 and were exported; user narrowed this remediation wave to only commands that ended nonzero. |
| RUN-03 | Ultima Run-QC | `ultima_run_qc`, explicit mounted Ultima run context, no basecalling. | NO_LONGER_NEEDED | scope_control | Gate 1 | Fresh campaign dry/live controllers already reached RC0 and were exported; user narrowed this remediation wave to only commands that ended nonzero. |
| RUN-04 | HIOMR2 | `hiomr2_slim_kitchensink_mega`, 5x ILMN + 5x ONT slim-data. | IN_PROGRESS | active_product_contract | Gate 1 | Dry attempt `ed173b24…bb4e` reached `rc=0` / zero submitted work; same-root live attempt `bb42a3c8…e08` is running and advanced through the long hybrid core (`99` finished, `95` submitted; no failure marker at `2026-08-19T02:28Z`). |
| RUN-05 | Bjuice v0.9 | `inflection-bjuice-product-v0.9`, 5x ILMN + 5x ONT slim-data. | IN_PROGRESS | active_product_contract | Gate 1 | Dry attempt `3639fac1…06b8` reached `rc=0` / zero submitted work; same-root live attempt `9ff50ccd…f2` is running (`98/295`, one Slurm job RUNNING) with no failure marker. |
| RUN-06 | SOLO ILMN | `illumina_hg002_kitchensink_multiqc`, ILMN slim-data. | SUCCESS | active_product_contract | Gate 1 | Dry attempt `bbb65050…49d` and same-root live attempt `2a31be56…98` both reached controller/day-run/Snakemake `rc=0`. |
| RUN-07 | SOLO ONT | `ont_snv_alignstats_kitchensink`, ONT slim-data. | SUCCESS | active_product_contract | Gate 1 | Dry attempt `98e1ea33…4f2` and same-root live attempt `9fc58392…4f2` both reached controller/day-run/Snakemake `rc=0`, including the declared final MultiQC/evidence targets. |
| RUN-08 | SOLO Ultima | `ultima_snv_alignstats_kitchensink`, Ultima slim-data. | SUCCESS | active_product_contract | Gate 1 | Dry attempt `12265cdf…d15` and same-root live attempt `b5a83d2f…6fbc` both reached controller/day-run/Snakemake `rc=0`, including the declared final MultiQC/evidence targets. |
| RUN-09 | SOLO CG | `complete_genomics_cg_snv_concordance`, CG slim-data. | SUCCESS | active_product_contract | Gate 1 | Dry attempt `5ef4ed24…d55` reached `rc=0` / zero submitted work; same-root live attempt `d5d0cb54…3543` reached controller/day-run/Snakemake `rc=0` at `2026-08-19T02:29Z`, including final MultiQC/evidence targets. |
| RUN-10 | Pangenome ILMN | `illumina_sentieon_pangenome_kitchensink`, ILMN slim-data. | IN_PROGRESS | active_product_contract | Gate 1 | The `15.0.29` dry attempt `4cba625c…0fa` failed before submitted work when the current sentd selector requested a graph/doppelmark path. `15.0.30` fixes that selector; a new dry/live same-root pair is pending HN-04. |
| RUN-11 | Pangenome Ultima | `ultima_sentieon_pangenome_kitchensink`, Ultima slim-data. | IN_PROGRESS | active_product_contract | Gate 1 | The `15.0.29` dry attempt `6a08b710…4c` failed before submitted work because `pre_prep_ultima_cram` ambiguously claimed the canonicalized graph CRAM. `15.0.30` constrains the input-lane wildcard; a new dry/live same-root pair is pending HN-04. |
| CAT-02 | Future catalog | Remove the two named retired Bjuice v2/v0.2 commands from mutable `current` in a forward-only DYEC release. | SUCCESS | active_product_contract | Gate 0 | `18.0.51` removed the named command and alias only from `current`; `18.0.52` retains that removal. |
| EVD-01 | Evidence | Update this ledger with dry/live controller receipts, effective argv, terminal rc, and blockers; export only after explicitly requested post-RC0 authorization. | IN_PROGRESS | legitimate_safety_handling | Gate 5 | This ledger now records all initial controller attempts and release transitions. No export/delete action is implied or has been performed. |
