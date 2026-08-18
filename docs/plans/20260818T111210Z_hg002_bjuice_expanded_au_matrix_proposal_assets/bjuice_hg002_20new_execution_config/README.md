# Bjuice HG002 20-new-AU catalog execution capsule

This directory contains the explicit input contract for one proposed twenty-AU
Bjuice HG002 downsampling analysis. It creates new work only for the 20 listed
AUs; the 12 E1/E3/P1 observations remain report evidence.

The selected catalog command is
`bjuice-v2-hg002-custom-multi-analysis-unit-hiomr2-kitchensink-mega`. The
current installed catalog resolves it to DayOA `15.0.24`, with production
HIOMR2 kitchen-sink mega and analytical Inflection targets.

`custom_au_plan.json` is the authoritative matrix. It is interpreted only by
the supported DYEC generator; no raw Snakemake command or hand-authored DayOA
YAML is used. The generated six-manifest set belongs under `manifests/` and is
passed to DYEC as `--manifest-dir`. At an authorized catalog launch, DYEC
stages/materializes those inputs in the controller's cloned
`daylily-omics-analysis` directory; no controller-specific config belongs in
`/home/ubuntu`.

## Manifest materialization command

Run this once from the Day-EC checkout when preparing an authorized catalog
render. It is configuration generation only; it does not render or launch a
workflow.

```bash
source ./activate
dyec --json catalog config-bjuice-v2-hg002-multi-au \
  --output-dir docs/plans/20260818T111210Z_hg002_bjuice_expanded_au_matrix_proposal_assets/bjuice_hg002_20new_execution_config/manifests \
  --source-manifest-json docs/plans/20260814T103851Z_bjuice_v2_hg002_launch_inputs/source_manifest_resolved.json \
  --run-evidence-json docs/plans/20260814T103851Z_bjuice_v2_hg002_launch_inputs/run_evidence_v2.json \
  --library-run-matrix-tsv docs/plans/20260814T103851Z_bjuice_v2_hg002_launch_inputs/library_run_matrix.tsv \
  --sample-metadata-tsv docs/plans/20260814T103851Z_bjuice_v2_hg002_launch_inputs/sample_metadata.tsv \
  --legacy-units-tsv docs/plans/20260814T103851Z_bjuice_v2_hg002_launch_inputs/legacy_units.tsv \
  --direct-ilmn-coverage-x 43.73 \
  --direct-ilmn-coverage-evidence docs/plans/20260814T103851Z_bjuice_v2_hg002_launch_inputs/direct_ilmn_coverage_receipt.json \
  --analysis-unit-plan-json docs/plans/20260818T111210Z_hg002_bjuice_expanded_au_matrix_proposal_assets/bjuice_hg002_20new_execution_config/custom_au_plan.json \
  --profile lsmc \
  --region us-west-2
```

The generator must produce exactly 20 `ANALYSIS_UNIT_UID` rows and a receipt
that records every direct-coverage fraction and every `[0,end)` ONT interval.
The required terminal direct-Illumina evidence is 43.73×. It must not be
replaced by a hybrid or RSR number.

## Later authorized catalog flow

When execution authority names a cluster and active accounting identity, first
render the catalog command using the already-generated `manifests/` directory:

```bash
dyec --json catalog render \
  bjuice-v2-hg002-custom-multi-analysis-unit-hiomr2-kitchensink-mega \
  --analysis-id "$ANALYSIS_ID" \
  --manifest-dir docs/plans/20260818T111210Z_hg002_bjuice_expanded_au_matrix_proposal_assets/bjuice_hg002_20new_execution_config/manifests \
  --profile lsmc \
  --region us-west-2 \
  --cluster "$CLUSTER" \
  --remote-user ubuntu \
  --project "$PROJECT" \
  --cost-center "$COST_CENTER" \
  --strict-project-check \
  --git-tag 15.0.24 \
  --dry-run
```

This is a render template only. It deliberately leaves the analysis ID,
cluster, project, and cost center unbound so that no accounting or execution
scope is silently guessed.

No cluster, project/cost center, concurrency, or export policy has been chosen
in this capsule. Those values remain an explicit launch-authorization gate.
