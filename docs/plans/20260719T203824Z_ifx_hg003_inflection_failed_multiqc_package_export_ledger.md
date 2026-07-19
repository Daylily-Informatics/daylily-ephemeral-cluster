# IFX HG003 Inflection failed-MultiQC package export ledger

Created: 2026-07-19T20:38:24Z

## Objective

Export, without deleting or changing the source package, the exact HG003 Inflection
batch whose four library packages completed but whose dependent
`create_inflection_multiqc_final` rule returned nonzero. Preserve an immutable local
receipt and verify the new S3 prefix after the FSx export task completes.

## Execution contract

- AWS profile / region / cluster: `lsmc` / `us-west-2` / `ifx-p2-1000-120-0715`
- Source analysis root: `/fsx/analysis_results/ifx-p2-1000-120-0715/hg003-1x-hiomrs-1307-4attempt-inflection-20260719T072500Z/daylily-omics-analysis`
- Exact package batch: `results/day/hg38/deliveries/inflection/Z-HG003-1X-1307-20260719`
- Source state: four `package_manifest.json` files, 255 regular files, 1.9 GiB; no final Inflection HTML; controller `RETURN CODE: 1` in `create_inflection_multiqc_final`.
- Export staging root: `/fsx/analysis_results/ifx-p2-1000-120-0715/inflection-package-Z-HG003-1X-1307-20260719-export-20260719T203824Z`
- Destination: `s3://lsmc-ssf-sequencing-data/derived/analysis_results/cluster_fsx_bulk_export/20260719T203824Z/ifx-p2-1000-120-0715/inflection-package-Z-HG003-1X-1307-20260719-export-20260719T203824Z/`
- Receipt directory: `docs/plans/20260719T203824Z_ifx_hg003_inflection_failed_multiqc_package_export_artifacts`
- Safety boundary: no source delete, S3 delete, package mutation, workflow rerun, DRA cleanup outside the supported export helper, or export of unrelated analysis outputs.

## Ledger

| ID | Area | Requirement | Status | Evidence | Terminal note |
|---|---|---|---|---|---|
| INV-001 | Source | Identify the exact package batch that failed only at dependent Inflection MultiQC. | SUCCESS | Four package manifests exist under batch `Z-HG003-1X-1307-20260719`; `inflection_multiqc_final.log` exists without final HTML; tmux records Slurm job 5594 and controller `RETURN CODE: 1`. | This is distinct from the older ten-library package-only proof. |
| STAGE-001 | FSx | Materialize a dedicated export analysis root containing only the exact package batch and verify source/staging path parity. | SUCCESS | Hardlinked exact batch under the dedicated root; source/staging relative path, inode, and size comparison returned `rc=0`; both sides contain 255 files and 2,020,625,008 bytes. | Source package was not modified or deleted. |
| EXP-001 | S3 | Run the supported temporary-DRA FSx export to the new empty immutable prefix. | SUCCESS | Export task `task-0e80915dbd466b819` reached `SUCCEEDED`; receipt `fsx_export.yaml` records `status: success`, `phase: complete`, `delete_data_in_file_system: false`. | Temporary DRA `dra-0231e35b82295fc79`. |
| VERIFY-001 | Reconciliation | Verify terminal task success, zero failed files, detached temporary DRA, and S3 object/byte evidence. | SUCCESS | Receipt records `failure_details: {}`, `detached: true`, `detach_lifecycle: DELETED`; live FSx API query returns no association. Exact package S3 subtree contains 245 nonzero objects matching the source's 245 nonzero files and 2,020,625,008 bytes; 88 zero-byte objects comprise 10 source zero-byte files plus 78 FSx directory markers. | Export receipts are under the recorded artifact directory. |

## Final report

All rows terminal: yes

Objective complete: yes
