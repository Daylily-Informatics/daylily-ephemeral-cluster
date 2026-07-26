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
| KS-005 | DYEC | Add a catalog entry pinned to the released DayOA version after live validation | OPEN | feature_implementation | Gate 1 | No catalog command may point at a stale DayOA ref. |
| KS-006 | live | Record terminal evidence for the active five-chromosome HG003 gate | IN_PROGRESS | contract_test | Gate 5 | Heartbeat monitor `monitor-hg003-hiomr2-five-shard-workflow` is active. |
| KS-007 | live | Launch the literal kitchen-sink continuation through DYEC after KS-006 succeeds | OPEN | feature_implementation | Gate 5 | Fresh controller/session; existing root only; no raw headnode/Slurm action. |
| IFX-001 | DayOA | Define a strict HIOMR2 Inflection source contract that does not bind legacy HIOMRS artifacts | IN_PROGRESS | feature_implementation | Gate 1 | Package must truthfully declare HIOMR2 gVCF, CNVscope, LongReadSV, and any separately produced ancillary lanes. |
| IFX-002 | DayOA | Add focused tests proving package provenance and hard failure on unsupported/unproduced artifact roles | OPEN | contract_test | Gate 1 | No synthetic caller output or identity inference. |
| IFX-003 | delivery inputs | Supply owner-issued persisted `seqone_delivery_batch_id` and customer-release identity fields if a customer-release package is intended | BLOCKED | active_product_contract | Gate 3 | Current manifest lacks required delivery identity values. Analytical packaging may preserve blanks, but still needs a supplied persisted batch ID. |
| IFX-004 | live | Dry-run and launch the strict HIOMR2 package only after KS-007 terminal success and IFX-003 inputs are explicit | OPEN | contract_test | Gate 5 | Must run through DYEC continuation, in the same analysis root. |
| REL-001 | both repos | Commit/push/tag only the verified source and ledger changes at the correct release gate | OPEN | feature_implementation | Gate 5 | Annotated, non-`v` tag; do not tag unproven package behavior. |

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
