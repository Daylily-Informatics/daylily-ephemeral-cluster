# DYEC 18.0.24 release runbook

> **AWS credential notice.** This release work used the still overly-permissioned `lsmc` AWS profile. Josh Durham (@jdurham38) is actively porting this workflow to a tightly scoped IAM role; that work is underway. Do not treat the existing profile as the desired steady-state permission boundary.

## Purpose and source merge

This is the release-facing consolidation of the three pcand-18022 operational records:

1. `docs/runbooks/18.0.22/runbooka1.md` — read-only RunQC DRA mounts, RunQC controllers, and result-export protocol.
2. `docs/runbooks/18.0.22/runbooka2.md` — HG002 slim 5x+5x BJuice / HIOMR2 controllers and their no-delete exports.
3. `docs/runbooks/18.0.22/runbooka3.md` from `codex/dyec-18.0.22-dayoa-15.0.11` — the four solo slim-data controllers and retry history.

It preserves the execution evidence and safety boundaries from those records, while recording the new DYEC 18.0.24 catalog contract. Historical controller receipts remain historical: a completed 1-24 controller does not validate the newly released 1-25 command definition.

## Operator admission

```bash
cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
source ./activate
dyec version
dyec --help
```

For headnode DayOA work, connect through DYEC to the target cluster and use an interactive `ubuntu` bash login shell in a persistent tmux session. The required controller sequence is separate commands:

```bash
cd /path/to/daylily-omics-analysis
source dyoainit
dy-a slurm hg38
dy-r <catalog-targets-and-flags>
```

Never invoke raw `snakemake`. Do not patch a pinned DayOA checkout.

## Data and mount boundary

| Workstream | Input boundary | Mount action |
| --- | --- | --- |
| Illumina / ONT / Ultima RunQC | Read-only pcand-18022 run-directory DRA mounts | Created and observed in runbooka1. No basecalling was introduced. |
| BJuice / HIOMR2 | Existing projected HG002 slim 5x+5x data and the two verified BJuice mounts | No new run mount was created by the BJuice/HIOMR2 controllers. |
| ILMN / ONT / Ultima / CG solo kitchensinks | Existing readable slim-data mount on `pcand-18022` | No `dyec mounts create` command was used for the four solo controllers. |

For any future run-mount creation, use the supported DYEC mount command and allow at least 40 minutes for a dynamic FSx DRA to reach a terminal state before considering a retry. Do not duplicate or delete a still-creating association.

## Current 18.0.24 catalog contract

All active current catalog commands pin immutable DayOA `15.0.14`. That DayOA tag points to the exact DayOA `15.0.12` source commit; no DayOA workflow source or environment YAML changed for this DYEC release. The unused DayOA `15.0.13` tag is not selected by this catalog.

| Catalog command | Released behavior |
| --- | --- |
| `illumina_hg002_kitchensink_multiqc` | Explicit `sentD={"hg38_sentD_chrms":"1-25"}` in both live and dry command definitions. |
| `ont_snv_alignstats_kitchensink` | Explicit `sentdont={"hg38_sentdont_chrms":"1-25"}`. |
| `ultima_snv_alignstats_kitchensink` | Explicit `sentdug={"hg38_sentdug_chrms":"1-25"}`. |
| `complete_genomics_cg_snv_concordance` | Explicit `cgt7p={"hg38_cgt7p_chrms":"1-25"}`. |
| `inflection-bjuice-product-v0.9` | Replaces the long BJuice v2 direct command. Uses `config/hg002_bjuice_5x5x_hiomr2.yaml`, runs chromosomes 1-25, and defaults to all supplied ONT FASTQs. An operator can pass both `--dy-config use_fq_data_starting_hrs=<n>` and `--dy-config use_fq_data_up_to_hrs=<n+n>` for an explicit global ONT[n,n+n) slice. No per-analysis-unit ONT selector is set. |

The source catalog and packaged catalog mirror carry the same release definitions.

## Historical controller and export evidence

The following completed controller/export record is carried forward. Each export was a no-delete DRA export: the task reached `SUCCEEDED`, the association detached, and FSx data was retained.

| Lane | Historical controller result | No-delete DRA task | Detached association | Exported S3 root |
| --- | --- | --- | --- | --- |
| ILMN solo | Controller rc=0; historical numeric 1-24 scope | `task-04d38f6f3f9f1686e` | `dra-08ac9e061273fb7dc` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/analysis_results/pcand18022-ilmn-solo-slim-1511-20260817t075549z-live-r1/` |
| ONT solo | Controller rc=0 after the DayOA 15.0.12 retry; historical numeric 1-24 scope | `task-0beaff08d9ff23808` | `dra-0e80571b6b26f37db` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/analysis_results/pcand18022-ont-solo-slim-1512-20260817t082933z-live-r2/` |
| Ultima solo | Controller rc=0; historical numeric 1-24 scope | `task-087be8073f7e2dd05` | `dra-0947c3a01e9eceb89` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/analysis_results/pcand18022-ultima-solo-slim-1511-20260817t075549z-live-r1/` |
| CG solo | Controller rc=0; historical numeric 1-24 scope | `task-0c093fafedd2f991f` | `dra-041501f85f32fb7b0` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/analysis_results/pcand18022-cg-solo-slim-1511-20260817t075549z-live-r1/` |
| BJuice v0.2 evidence | Controller rc=0 | `task-0a96f7581ba6ddc90` | `dra-065329a4fceb729fd` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022-hg002-slim5x5x-bjuice-ifx-20260817t0648z/` |
| HIOMR2 evidence | Controller rc=0 | `task-07042d644f5dfb3fb` | `dra-099bf60af970a4503` | `s3://lsmc-ssf-sequencing-data/derived/pcand-18022/pcand18022-hg002-slim5x5x-hiomr2-20260817t0648z/` |

The current four numeric 1-25 command definitions and the new v0.9 BJuice command are intentionally validation-pending. Their prerelease test runs must create fresh receipts; the historical success rows must not be relabeled as current-contract proof.

## Result-export procedure

After a controller reaches attributable rc=0 and no submitted workflow jobs remain, record a read-only export visit and use the supported DYEC DRA export path. Substitute only real values; do not execute a placeholder command.

```bash
# On the headnode as ubuntu
dyec analysis visit \
  --analysis-root /fsx/analysis_results/pcand-18022/<ANALYSIS_ID> \
  --mode export \
  --intent "export completed results without FSx cleanup" \
  --s3-visit-uri s3://lsmc-ssf-sequencing-data/derived/pcand-18022/<ANALYSIS_ID>/

# From the activated DYEC checkout
dyec export --profile lsmc --region us-west-2 --cluster pcand-18022 \
  --source-path /fsx/analysis_results/pcand-18022/<ANALYSIS_ID> \
  --destination-s3-uri s3://lsmc-ssf-sequencing-data/derived/pcand-18022/<ANALYSIS_ID>/ \
  --output-dir docs/runbooks/18.0.24/receipts/<ANALYSIS_ID> \
  --wait --timeout-seconds 5400
```

Do not delete FSx data, issue a delete lock, detach a source DRA, or invoke mount cleanup as part of this procedure. Those are separate destructive actions and require a fresh explicit approval.

## Prerelease gate

DYEC 18.0.24 is a prerelease only. No Git tests were run while creating it at the user's direction. The next gate is user-run full command-catalog testing of the prerelease versions. Only after those tests complete without problems may the branch be considered for a merge to `main`; the complete repository test suite follows that merge.
