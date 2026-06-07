# dyec800 Mount Startup And Slim Dry-Run Ledger

Controlling request: start all missing run-directory mounts for dyec800, and run dry-runs for catalog commands that can use already-mounted slim data.

Safety boundary:
- Allowed by this request: create missing read-only FSx run-directory DRAs for dyec800.
- Not allowed in this pass: cluster create/update/delete, live workflow runs without `--dry-run`, raw DayOA `snakemake`, Slurm job control, mount deletion, or destructive cleanup.

## Rows

| ID | Area | Requirement | Status | Evidence | Terminal Note |
|---|---|---|---|---|---|
| G0-001 | Inventory | Record source catalog run-context inputs and current mounts. | SUCCESS | Catalog has 5 run-context commands collapsed to 3 unique source S3 URIs; pre-create `dyec mounts list` returned `{"mounts": []}`. | Baseline captured. |
| MOUNT-001 | ILMN run DRA | Start read-only DRA for `20260514_LH01106_0009_B23TVLGLT4`. | SUCCESS | `dyec --json mounts create ... --platform ILMN --read-only --no-wait --timeout-seconds 3600` -> `dra-011a9b3abaa2f5967`, lifecycle `CREATING`. | Started under `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/`. |
| MOUNT-002 | ONT run DRA | Start read-only DRA for `20260513_ONT_HG003`. | SUCCESS | `dyec --json mounts create ... --platform ONT --read-only --no-wait --timeout-seconds 3600` -> `dra-0e5e5087b57582870`, lifecycle `CREATING`. | Started under `/fsx/run_dir_mounts/20260513_ONT_HG003/`. |
| MOUNT-003 | Ultima run DRA | Start read-only DRA for `602221-20260417_2346`. | SUCCESS | `dyec --json mounts create ... --platform ULTIMA --read-only --no-wait --timeout-seconds 3600` -> `dra-0d82446e67057a668`, lifecycle `CREATING`. | Started under `/fsx/run_dir_mounts/602221-20260417_2346/`. |
| DRY-001 | Slim sample dry-runs | Run dry-runs for sample-manifest catalog commands that use mounted `organism_reads_slim`. | SUCCESS_WITH_BLOCKERS | Evidence root selected: `s3://lsmc-ssf-sequencing-data/derived/validation/`. All 12 supported default slim sample-manifest commands were launched on dyec800 with stamp `20260607T171725Z`. `complete_genomics_mgi_snv_concordance` remains excluded because it has no supported sample manifest mode. | 9/12 wrappers have `exit_code=0`; ILMN and Ultima kitchen-sink DayOA dry-runs reached `RETURN CODE: 0` but their wrappers are still waiting on output DRAs; ONT kitchen-sink reached DayOA `RETURN CODE: 0` but wrapper `exit_code=1` because FSx hit maximum allowed DRAs. |
| REPORT-001 | Report | Poll status and report mounts/dry-run blockers. | IN_PROGRESS | Post-create and later `dyec --json mounts list` / `aws fsx describe-data-repository-associations` checks show ILMN and Ultima run mounts `AVAILABLE`, ONT run mount `CREATING`, and four output evidence DRAs `CREATING`. | Interim state recorded; final report pending output DRA terminal states or explicit stop. |

## Current Mount Status

| Mount | Association | Lifecycle | Headnode path |
|---|---|---|---|
| `20260514_LH01106_0009_B23TVLGLT4` | `dra-011a9b3abaa2f5967` | `AVAILABLE` | `/fsx/run_dir_mounts/20260514_LH01106_0009_B23TVLGLT4/` |
| `20260513_ONT_HG003` | `dra-0e5e5087b57582870` | `CREATING` | `/fsx/run_dir_mounts/20260513_ONT_HG003/` |
| `602221-20260417_2346` | `dra-0d82446e67057a668` | `AVAILABLE` | `/fsx/run_dir_mounts/602221-20260417_2346/` |

## Current Output Evidence Status

Evidence root: `s3://lsmc-ssf-sequencing-data/derived/validation/`

| Session | Dry-run status | Output DRA | Export prefix |
|---|---|---|---|
| `ccv_dryrun_illumina_hg002_kitchensink_multiqc` | DayOA dry-run command returned `0`; controller still finalizing export | `dra-068e026c3d5c3fec1` `CREATING` | `s3://lsmc-ssf-sequencing-data/derived/validation/dyec800/command_catalog_results/8.0.0-20260607T164557Z/ubuntu/ccv_dryrun_illumina_hg002_kitchensink_multiqc/` |
| `ccv_dryrun_ultima_snv_alignstats_kitchensink` | DayOA dry-run command returned `0`; controller still finalizing export | `dra-08748fff56d9af4e4` `CREATING` | `s3://lsmc-ssf-sequencing-data/derived/validation/dyec800/command_catalog_results/8.0.0-20260607T164557Z/ubuntu/ccv_dryrun_ultima_snv_alignstats_kitchensink/` |
| `ccv_dryrun_ont_snv_alignstats_kitchensink` | `exit_code=1`; generated manifest used default slim `ONT_CRAM` fixture while catalog command required `produce_sentmm2ont_align` | n/a | n/a |

## All-Slim Launch Status `20260607T171725Z`

The 12 supported slim sample-manifest commands were staged under `docs/plans/20260607T171725Z_dyec800_all_slim_dryruns_logs/`. The first three were launched by `dyec tests command-catalog` with evidence export enabled. The remaining nine were launched through `dyec workflow launch` with export omitted because FSx reached the maximum allowed DRA count.

| Command | Launch mode | Status |
|---|---|---|
| `illumina_hg002_kitchensink_multiqc` | command-catalog export | DayOA dry-run `RETURN CODE: 0`; wrapper status pending on output DRA `dra-076b9d7b0be5d3677` `CREATING` |
| `ultima_snv_alignstats_kitchensink` | command-catalog export | DayOA dry-run `RETURN CODE: 0`; wrapper status pending on output DRA `dra-07ffbd56cca0d7779` `CREATING` |
| `ont_snv_alignstats_kitchensink` | command-catalog export | DayOA dry-run `RETURN CODE: 0`; wrapper `exit_code=1` due `You have reached the maximum allowed DRAs for this filesystem.` |
| `hybrid_ilmn_ont_snv_kitchensink` | no-export workflow launch | `exit_code=0` |
| `illumina_snv_alignstats` | no-export workflow launch | `exit_code=0` |
| `illumina_snv_alignstats_relatedness_vep_multiqc` | no-export workflow launch | `exit_code=0` |
| `ultima_snv_alignstats` | no-export workflow launch | `exit_code=0` |
| `ont_snv_alignstats` | no-export workflow launch | `exit_code=0` |
| `pacbio_snv_alignstats` | no-export workflow launch | `exit_code=0` |
| `roche_snv_alignstats` | no-export workflow launch | `exit_code=0` |
| `hybrid_ilmn_ont_snv` | no-export workflow launch | `exit_code=0` |
| `inflection-bjuice-product-v0.1` | no-export workflow launch | `exit_code=0` |

## Blocked Dry-Run Command

```bash
source ./activate && dyec tests command-catalog \
  --cluster dyec800 \
  --profile lsmc \
  --region us-west-2 \
  --command-codes "illumina_snv_alignstats illumina_snv_alignstats_relatedness_vep_multiqc illumina_hg002_kitchensink_multiqc ultima_snv_alignstats ultima_snv_alignstats_kitchensink ont_snv_alignstats ont_snv_alignstats_kitchensink pacbio_snv_alignstats roche_snv_alignstats hybrid_ilmn_ont_snv hybrid_ilmn_ont_snv_kitchensink inflection-bjuice-product-v0.1 complete_genomics_mgi_snv_concordance" \
  --evidence-s3-uri "s3://<exact-evidence-root>/" \
  --dry-run \
  --parallel 3 \
  --jobs 150
```
