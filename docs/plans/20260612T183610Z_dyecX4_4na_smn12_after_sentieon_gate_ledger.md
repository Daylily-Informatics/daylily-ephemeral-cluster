# dyecX4 4NA SMN12 Rerun After Sentieon Acceptance Gate

## Summary

Rerun the four NA control samples as eight hybrid units through the full SMN12 caller set after the current Sentieon upgrade acceptance analyses are passing.

Gate condition:
- Do not stop or restart currently running Sentieon acceptance analyses.
- Do not launch this 4NA rerun until the remaining Sentieon acceptance runs are terminal `exit_code=0` and successful DRA export receipts are present.

Requested rerun:
- Cluster: `dyecX4`
- AWS profile: `lsmc`
- Region: `us-west-2`
- Executing entity: `ubuntu`
- DayOA tag for future launch: `10.0.15`
- DYEC tag/local CLI for future launch: `10.0.24`
- Snakemake/DYEC jobs flag: `-j 350`
- Samples: `NA00232`, `NA09677`, `NA03986`, `NA05164`
- Units: each sample as `chip1+chip2` and second unit as `chip3+chip4` where present, with chip4-only substitutions where chip3 is missing.

## Known Reusable Inputs

Previous completed combined analysis:
`/fsx/analysis_results/ubuntu/hiomr_smn12_4na_chip4sub_20260612T015845Z/daylily-omics-analysis/`

Reusable source config on the headnode:
- `/fsx/analysis_results/ubuntu/hiomr_smn12_4na_chip4sub_20260612T015845Z/daylily-omics-analysis/config/samples.tsv`
- `/fsx/analysis_results/ubuntu/hiomr_smn12_4na_chip4sub_20260612T015845Z/daylily-omics-analysis/config/units.tsv`

Observed shape from read-only inspection:
- `samples.tsv`: 4 sample rows plus header.
- `units.tsv`: 8 unit rows plus header.

Prior local intended-analysis manifest:
`docs/plans/20260611T004801Z_dyecX4_4na_smn12_export_cleanup_logs/4na_inputs/4na_intended_analyses.tsv`

## Intended Future Command Shape

Use `dyec workflow launch` with local copies of the reusable `samples.tsv` and `units.tsv`, not raw `snakemake`.

Targets:
```bash
dy-r produce_smn12_orthogonal_calls produce_htd_calls produce_sentdhiomr_segdup -p -T 0 -k -j 350 --rerun-triggers mtime \
  --config 'aligners=["sent"]' 'dedupers=["dmd"]' 'snv_callers=["sentdhiomr"]' 'sv_callers=["sentdhiomr"]' 'htd_callers=["smn12","smaca","sma_finder","hapsma","gauchian","cyrius"]' 'sentdhiomr={"segdup_genes":"SMN1"}'
```

Export destination:
`s3://lsmc-ssf-sequencing-data/derived/analysis_results/sentieon-upgrade/ubuntu/<analysis-id>/`

## Ledger

| ID | Owner | Scope | Status | Evidence / Notes |
| --- | --- | --- | --- | --- |
| R4NA-001 | orchestrator | Record user request and gate behind Sentieon acceptance. | COMPLETE | Request recorded 2026-06-12T18:33Z in the DayOA Sentieon acceptance ledger; this DYEC ledger created for the eventual 4NA launch. |
| R4NA-002 | acceptance-gate | Verify remaining Sentieon acceptance analyses pass and export. | OPEN | Waiting on `sentup_hg003_ilmn30x_hg38_solo_20260612T181511Z` and `sentup_hg003_hiomr_kitchensink_20260612T175000Z`; both non-terminal at 2026-06-12T18:34Z. |
| R4NA-003 | inputs | Copy/reuse 4NA combined `samples.tsv` and `units.tsv` from the previous completed analysis. | OPEN | Source files exist on dyecX4 headnode with expected 4 sample / 8 unit shape. |
| R4NA-004 | dry-run | Run a 4NA SMN12 dry-run from DayOA `10.0.15` with `-j 350 -n`. | OPEN | Must use persistent `ubuntu` tmux via `dyec workflow launch` / `dy-r`. |
| R4NA-005 | live-run | Launch the 4NA SMN12 live run without `-n`, with `-j 350`. | OPEN | Only after R4NA-002 and R4NA-004 pass. |
| R4NA-006 | evidence | Export successful 4NA rerun via DRA and summarize outputs. | OPEN | DRA receipt is export authority. |

