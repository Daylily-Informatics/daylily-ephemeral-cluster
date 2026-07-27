# HIOMR2 Kitchen Sink Then Inflection Package — Control Ledger

Controlling request: “hiomr2 kitchensink next and then inflection package” (2026-07-26).

This ledger controls the literal `sentdhiomr2` sequence.  It must not substitute
the existing legacy `sentdhiomr` catalog entries named “kitchensink” or
“package”.  The current five-chromosome HG003 workflow is the first live gate;
the kitchen-sink continuation and package follow only after its terminal
evidence is recorded.

## Gate 0 — Inventory freeze

- DYEC repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch
  `jem-candidate-260725`, HEAD `10371c37`; numerous pre-existing untracked
  ledgers/artifacts are user-owned and excluded from this work.
- DayOA repository: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`, branch
  `codex/hiomr2-five-chrom-shards`, HEAD `c33494ed`, clean at inventory.
- Active first gate: cluster `preval-hiomr2`, session
  `hiomr2_hg003_fivechrom_live3_20260726`, analysis root
  `/fsx/analysis_results/preval-hiomr2/hg003-hiomr2-five-chrom-shards-20260726-live3`.
  At `2026-07-26T11:39Z`, DYEC reports `RUNNING`, `2/10`, one scoped Slurm job
  (`sentdhiomr2_sr_prepare`) running, and no workflow failure marker.
- Existing catalog entries `hybrid_ilmn_ont_hiomr_kitchensink` and
  `package_inflection_hybrid_data` both select legacy `sentdhiomr`; neither is
  a valid substitute.
- DayOA exposes native HIOMR2 targets for global gVCF, reference gVCF,
  semantic comparison, CNVscope, LongReadSV, Inflection gVCF-name links, and
  command provenance, but no aggregate `produce_sentdhiomr2_kitchensink`.
- The current SeqOne/Inflection package has an explicit HIOMR2 SNV selector,
  yet still binds CNV/SV/mitochondrial/specialty inputs to legacy HIOMRS paths.
  No caller/product will be relabeled or silently reused as HIOMR2.
- The HG003 six-manifest `analysis_units.tsv` has blank `ANALYSIS_UNIT_EUID`,
  `DELIVERY_EUID`, and `DELIVERY_PROFILE`.  A strict package also requires an
  explicitly supplied persisted `seqone_delivery_batch_id`; DayOA must not
  invent it.

## Control rows

| ID | Repo/area | Requirement | Status | Category | Gate | Evidence / terminal note |
|---|---|---|---|---|---|---|
| KS-001 | DYEC + DayOA | Establish literal HIOMR2 scope; exclude legacy catalog substitution | SUCCESS | plan_amendment | Gate 0 | Catalog and DayOA source inventory recorded above. |
| KS-002 | DayOA | Add a single explicit HIOMR2 kitchen-sink public target aggregating only actual HIOMR2 products | SUCCESS | feature_implementation | Gate 1 | `produce_sentdhiomr2_kitchensink` aggregates native/reference gVCF comparator, CNVscope, LongReadSV, Inflection compatibility links, and command manifest. |
| KS-003 | DayOA | Add focused contract tests for the target’s exact product set and no legacy target dependency | SUCCESS | contract_test | Gate 1 | Focused test rejects legacy `sentdhiomr`, `HIOMRS`, and legacy Inflection delivery dependencies. |
| KS-004 | DYEC | Provide a supported continuation command for an existing analysis root, preserving its data and using a persistent DayOA controller | SUCCESS | feature_implementation | Gate 1 | `dyec workflow launch --reuse-existing-analysis-dir` retains the root, records lock/visit, verifies a clean checkout, fetches the exact requested source ref, and fails closed. |
| KS-005 | DYEC | Add a catalog entry pinned to the released DayOA version after live validation | SUCCESS | feature_implementation | Gate 1 | Literal command `hybrid_ilmn_ont_hiomr2_kitchensink_inflection_analytical` and its BJuice clone are pinned to DayOA `13.0.52`; every DayOA catalog command uses that released ref. |
| KS-006 | live | Record terminal evidence for the active five-chromosome HG003 gate | SUCCESS | contract_test | Gate 5 | Canonical `live7` completed `rc=0` at `2026-07-26T21:15:34Z` on DayOA commit `e2885d27` / annotated tag `13.0.48`; master log is 10/10 with no failure lines. The generic DYEC canonical-artifact aggregate is `INCOMPLETE_OR_UNKNOWN` because this scoped first gate emits no MultiQC/evidence-manifest set. |
| KS-007 | live | Launch the literal kitchen-sink continuation through DYEC after KS-006 succeeds | SUCCESS | feature_implementation | Gate 5 | The combined literal continuation completed `rc=0` with the owner-issued analytical batch `20260726-hiomr2-ks-ip`; it reused the live7 root and did not schedule the retired global gVCF lane. |
| IFX-001 | DayOA | Define a strict HIOMR2 Inflection source contract that does not bind legacy HIOMRS artifacts | SUCCESS | feature_implementation | Gate 1 | The separate analytical target copies only declared HIOMR2 gVCF, CNVscope, LongReadSV, CRAM, comparator, and provenance products. |
| IFX-002 | DayOA | Add focused tests proving package provenance and hard failure on unsupported/unproduced artifact roles | SUCCESS | contract_test | Gate 1 | Unit tests prove materialization, fixed roles, source checks, and hard failure on a symlink source or non-analytical mode. |
| IFX-003 | delivery inputs | Supply owner-issued persisted `seqone_delivery_batch_id` and customer-release identity fields if a customer-release package is intended | SUCCESS | active_product_contract | Gate 3 | User-issued analytical package batch input: `20260726-hiomr2-ks-ip`. No customer-release identity was supplied or inferred; the target remains analytical-only. |
| IFX-004 | live | Dry-run and launch the strict HIOMR2 package only after KS-007 terminal success and IFX-003 inputs are explicit | SUCCESS | contract_test | Gate 5 | The DYEC dry run preserved completed first-gate products, then the identical literal continuation completed `rc=0` and produced the analytical package manifest with eleven declared artifacts. |
| REL-001 | both repos | Commit/push/tag only the verified source and ledger changes at the correct release gate | IN_PROGRESS | feature_implementation | Gate 5 | DayOA `13.0.52` is the annotated release for the final VCF+gVCF analytical package correction. DYEC catalog/pin release remains in this commit train. |

## Current sequencing rule

1. Finish and verify the active five-chromosome workflow.
2. Launch the new literal HIOMR2 kitchen sink against the same analysis root via DYEC.
3. Only then package the resulting products with an explicit Inflection delivery
   contract and supplied delivery batch identity.

No analysis root will be replaced, no jobs will be cancelled, and no Slurm
service or queue intervention is authorized by this ledger.

## Gate 1 — Local implementation evidence

- DayOA now exposes `produce_sentdhiomr2_kitchensink` in
  `workflow/rules/sent_hybrid_ilmn_ont_modular2.smk`. Its inputs are limited to
  the independently produced HIOMR2 five-chromosome gVCF, native gVCF,
  CLI-reference gVCF, semantic comparator, CNVscope, LongReadSV, gVCF-name
  compatibility link, and command manifest. The tool catalog and the original
  HIOMR2 conformance ledger document the new explicit scope.
- `python -m pytest -q tests/test_hiomr2_core_rules.py
  tests/test_hiomr2_inflection_contract.py tests/test_tool_catalog_docs.py` in
  the DayOA `DAY-EC` environment passed: **22 passed**.
- DYEC now accepts `--reuse-existing-analysis-dir` only with
  `--input-contract none --no-input-staging`. It refuses replacement, manifest
  rewrites, bootstrap configuration, a missing existing root, a dirty tracked
  checkout, absent explicit fetched source ref, or a checkout mismatch. The
  controller preserves runtime inputs and uses the existing analysis lock/visit
  receipts before its normal persistent DayOA controller sequence.
- `python -m compileall -q daylily_ec/cli.py
  daylily_ec/scripts/daylily_run_omics_analysis_headnode.py` and
  `pytest -q tests/test_script_entrypoints.py tests/test_cli_registry_v2.py` in
  the DYEC `DAY-EC` environment passed: **255 passed**. Focused Ruff correctness
  checks (`ruff check --select F`) passed. The repository-wide Ruff run reports
  pre-existing broad style findings and is not a clean baseline for this change.
- The live kitchen-sink continuation remains gated on KS-006. At the latest
  read-only DYEC check, the first gate is still `RUNNING` at `2/10`, with one
  `sentdhiomr2_sr_prepare` job active and no controller failure marker.

## Gate 1 — Analytical Inflection package evidence

- DayOA now has the separately named
  `produce_sentdhiomr2_inflection_analytical_package` target. It consumes only
  the declared native/reference/five-chromosome HIOMR2 gVCFs and indexes,
  CNVscope post-model VCF/index, native LongReadSV VCF/index, HIOMR2 SR
  CRAM/CRAI, semantic comparator, and command manifest. Its materializer writes
  copied regular files plus checksums beneath
  `deliveries/inflection_hiomr2/<batch>/<analysis-unit>` and refuses
  replacement or symlink sources.
- The target is intentionally analytical-only: its manifest states
  `customer_release_eligible: false`. It requires both a real owner-issued
  persisted `seqone_delivery_batch_id` and
  `hiomr2_inflection_package_mode=analytical`. There is no inferred batch,
  customer identity, or legacy HIOMRS artifact fallback.
- Focused DayOA validation passed: **33 passed, 1 deselected** across the
  HIOMR2 package/core/contract/catalog tests and the unaffected parser tests;
  focused Ruff correctness checks passed. The one deselected parser test is a
  pre-existing active-rule check that reports raw Sentieon calls already present
  in `sent_hybrid_ilmn_ont_modular2.smk`; this package change does not add such
  a call.

## Gate 5 — Five-shard recovery update

- The original `live3` first gate terminated at `2026-07-26T12:08:41Z` with
  `rc=1`. Its DYEC log showed that Sentieon DNAscope rejected `--gvcf`; no
  kitchen-sink or Inflection continuation was launched from that failed root.
- DayOA commit `e4f8f642` corrects the raw DNAscope call to `--emit_mode gvcf`.
  The focused core/runtime/Inflection suite passed (`23 passed`), and the
  source is published at annotated tag `13.0.43` on
  `codex/hiomr2-five-chrom-shards`.
- A fresh, non-replacing `live4` first gate began at `2026-07-26T12:49:28Z` in
  `/fsx/analysis_results/preval-hiomr2/hg003-hiomr2-five-chrom-shards-20260726-live4`.
  It uses the hash-validated original six-manifest input contract, literal
  `sentdhiomr2` caller/configuration, cost center `bjuice`, and the same
  five-shard target. At `2026-07-26T12:51Z`, DYEC reported it `RUNNING`, with
  active controller, preflight job `14` configuring, zero current failure
  markers, and 11.2 TiB FSx available.
- The heartbeat now monitors `live4` and prints plus speaks a concise exact
  two-sentence status every cycle. KS-007 remains strictly gated on terminal
  `rc=0` and verified artifacts from this corrected first gate.

## Gate 5 — Live6 and combined-continuation policy update — 2026-07-26T17:47Z

- `live4` and `live5` are preserved terminal evidence only. `live5` failed
  after every gVCF shard completed its Sentieon call because the former
  early-exit `<NON_REF>` `awk` validator interacted with strict `pipefail`.
- The canonical first gate is now `live6`: session
  `hiomr2_hg003_fivechrom_live6_20260726`, analysis root
  `/fsx/analysis_results/preval-hiomr2/hg003-hiomr2-five-chrom-shards-20260726-live6`,
  source tag `13.0.45` at DayOA commit `1742e06d`. At `2026-07-26T17:47Z`,
  DYEC reported `RUNNING`, `5/10`, three 96-vCPU five-chromosome gVCF shards
  running, and zero current master-log failure markers.
- After verified `live6` terminal `rc=0`, the next continuation is one
  dependency-aware DYEC launch that requests both literal targets together:
  `produce_sentdhiomr2_kitchensink` and
  `produce_sentdhiomr2_inflection_analytical_package`. The outer DYEC launch
  and inner `dy-r` invocation both use 200 jobs; the inner command uses
  `-p -T 0 -k --rerun-triggers mtime`.
- First run that exact combined continuation with `-n`. It must prove that
  completed first-gate rules are not scheduled for rerun. Only a successful
  dry run with no such rerun may be followed by the identical DYEC launch
  without `-n`.
- The combined target remains analytical-only and requires the actual
  owner-issued persisted `seqone_delivery_batch_id` plus
  `hiomr2_inflection_package_mode=analytical`. No batch, EUID, delivery
  identity, customer-release identity, or legacy target may be invented or
  substituted. Absence of the persisted batch is a terminal continuation
  blocker pending user instruction.

## Gate 6 — Live7 terminal evidence and continuation blocker — 2026-07-26T21:27Z

- Canonical first gate: session `hiomr2_hg003_fivechrom_live7_20260726`, root
  `/fsx/analysis_results/preval-hiomr2/hg003-hiomr2-five-chrom-shards-20260726-live7`,
  DayOA commit `e2885d27` subsequently published as annotated tag `13.0.48`.
  `dyec --json workflow status` reports completion at `2026-07-26T21:15:34Z`
  with `exit_code=0`.
- DYEC master-log evidence records ten completed steps, five successful shard
  gVCFs, a successful concat, and no failure lines. `dyec analysis status
  full` reports no active controller or scoped jobs, 17 parsed benchmark rows,
  and no current failure marker.
- Artifact verification is explicit: the scoped target produced its gVCF,
  TBI, done-marker, and immutable concat-provenance workflow outputs, but it
  does not produce generic `DAY_final_multiqc.html`,
  `dayoa_evidence_manifest.json`, or `multiqc_data.json`. DYEC therefore
  reports the root `INCOMPLETE_OR_UNKNOWN`; this is recorded as a monitoring
  caveat and is not represented as canonical-analysis artifact success.
- The supplied `analysis_units.tsv` has blank `ANALYSIS_UNIT_EUID`,
  `DELIVERY_EUID`, `DELIVERY_PROFILE`, and `CUSTOMER_DELIVERY_ID` fields, and
  no persisted `seqone_delivery_batch_id` was supplied. The mandated combined
  continuation cannot be dry-run or launched without inventing a value, so
  KS-007 and IFX-004 remain blocked pending an owner-issued persisted batch.

## Gate 7 — Owner-issued analytical batch and continuation authorization — 2026-07-26T22:18Z

- The user explicitly supplied `seqone_delivery_batch_id=20260726-hiomr2-ks-ip`
  for this analytical-only continuation. It is used exactly as supplied; no
  EUID, customer-delivery identity, or customer-release eligibility is
  inferred.
- KS-007 and IFX-004 move to `IN_PROGRESS`. The next action is the exact
  combined DYEC dry run with `-p -T 0 -k -j 200 --rerun-triggers mtime -n`.
  Its DYEC log must show that the completed live7 first-gate rules are not
  scheduled before the same command is launched without `-n`.
- DYEC launched that dry run at `2026-07-26T22:19:32Z` as session
  `hiomr2_hg003_ks_inflection_dryrun_20260726`, using tag `13.0.48`, cost
  center `bjuice`, 200 jobs, and the supplied batch value. At `22:27Z` the
  status receipt remained pending; the analysis lock was owned by that
  controller, while DYEC reported an empty controller log, no controller
  process, and no Slurm jobs. The tmux pane was still at `/home/ubuntu`, before
  the controller's `cd`/`dy-r` phase. The supported controller source performs
  its explicit ref fetch at that point, so this is not yet dry-run graph
  evidence. The session and root are preserved; no cancel, replacement, or
  direct headnode action was taken.

## Gate 8 — Post-success cluster cache and container reuse — OPEN

This gate begins only after the combined literal HIOMR2 kitchen-sink and
analytical-only Inflection packaging continuation reaches terminal `rc=0` and
its required artifacts are verified.

- **CACHE-001 — inventory:** identify the DayOA/Conda/Singularity-Apptainer or
  other container-pull caches created on `preval-hiomr2`; classify each by
  producer, immutable version/digest, size, and whether it is safe to reuse.
  Do not treat transient job scratch, analysis outputs, credentials, mutable
  package indexes, or unverified layers as reusable cache assets.
- **CACHE-002 — persist:** export only the verified reusable cache assets to an
  explicit S3 cache location with a manifest containing paths, checksums,
  source cluster, source image/package digest, creation time, and restore
  instructions. Preserve the cluster-local originals until export verification
  succeeds; this gate does not authorize deletion.
- **CACHE-003 — consume:** add an explicit new-cluster bootstrap/link contract
  that reuses an S3 cache asset only when its manifest and requested
  version/digest match. A missing or mismatched asset must be reported clearly
  and use the ordinary fresh-pull/build path; it must never be silently treated
  as equivalent. New clusters link or hydrate verified assets rather than
  re-creating them when present.
- **CACHE-004 — proof:** validate the mechanism on a new cluster with cache-hit
  and cache-miss evidence, including the resolved S3 object versions and a
  before/after record of container-pull or environment-build avoidance. Record
  resulting cost/time evidence in this ledger before making the cache contract
  a default.

## Gate 9 — Literal continuation terminal evidence — 2026-07-27T02:10Z

- DYEC completed the literal kitchen-sink plus analytical-package continuation
  with `rc=0`. It used the scoped five-chromosome concat as the sole gVCF
  source and did not recreate the retired `sentdhiomr2_global_gvcf` lane.
- The analytical package manifest under
  `deliveries/inflection_hiomr2_analytical_callsets_vcf_gvcf` declares eleven
  copied artifacts, including the scoped gVCF/TBI and a separate hard-call
  VCF/TBI. It is explicitly analytical-only and has
  `customer_release_eligible: false`.
- The first-gate generic DYEC analysis aggregation may remain
  `INCOMPLETE_OR_UNKNOWN` because its scoped workflow intentionally lacks the
  generic MultiQC/evidence-manifest outputs. That caveat does not override the
  terminal workflow receipt or the verified package manifest above.
