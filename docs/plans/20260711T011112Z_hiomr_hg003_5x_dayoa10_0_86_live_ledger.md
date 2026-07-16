# HG003 5x HIOMR Kitchensink Live Ledger

Created: 2026-07-11T01:11:12Z

## Objective

Launch exactly one HG003 5x hybrid ILMN+ONT HIOMR kitchensink on
`ifx-reworkB` using a corrected released DayOA tag and the mounted slim-data
inputs. The initial `10.0.86` attempt is retained below as preflight evidence.

## Gate 0

- Cluster: `ifx-reworkB`, region `us-west-2`, status `CREATE_COMPLETE`, compute
  fleet `RUNNING`.
- DayOA: annotated tag `10.0.86`, commit `f5605db`.
- DYEC: annotated final tag `10.0.153`; its packaged self-pin is `10.0.152`.
- Analysis id: `hiomr_hg003_5x_kitchensink_dayoa10_0_86_20260711T011112Z`.
- Analysis root: `/fsx/analysis_results/ifx-reworkB/hiomr_hg003_5x_kitchensink_dayoa10_0_86_20260711T011112Z`.
- Genome/profile: `slurm hg38`.
- Sample: `HG003`; experiment `SR5x-ONT5x`.
- ILMN FASTQs and ONT CRAM/CRAI were verified present under
  `/fsx/data/genomic_data/organism_reads_slim/`; no DRA creation is required.
- Gate-0 `squeue` was empty.
- `dyec headnode configure` attempted SSM command
  `e94eea3b-c96f-4856-ae48-fab49f3b0bd2` and failed before mutation with
  `rc=128` because the private HTTPS GitHub clone had no credentials. Existing
  headnode DYEC still exposes `analysis visit`, `guard`, and `lock`.

## DayOA 10.0.86 Preflight Result

- The controller reached only wrapper preflight; formal Snakemake execution did
  not start and no Slurm jobs were submitted.
- The catalog command lacked explicit `aligners=["sent"]` and
  `snv_callers=["sentdhiomr"]`, leaving the Manta aggregate without inputs.
- After supplying those selectors diagnostically, DAG construction reported an
  ambiguous match between `sentdhiomr_export_sr_cram` and
  `pre_prep_ont_cram`. The ONT preparation wildcard incorrectly accepted `/`
  in a sample-lane value.
- DayOA `10.0.87` constrains the ONT sample-lane wildcard to one path component.
  The corrected DYEC catalog supplies both selectors explicitly.
- The `10.0.86` wrapper released its owned analysis lock after the failed
  preflight, and the Slurm queue remained empty.

## Control Ledger

| ID | Requirement | Status | Evidence | Terminal note |
|---|---|---|---|---|
| PREP-001 | Verify exact released refs, one-sample manifests, mounted inputs, cluster, and empty queue | SUCCESS | Gate 0 evidence above | No duplicate controller or mount creation |
| PREFLIGHT-001 | Generate and validate the Ursa summary manifest and rulegraph before execution | IN_PROGRESS | `10.0.86` failed safely before submission; corrected `10.0.87` pending | DYEC defaults enable both producers |
| RUN-001 | Launch one persistent version-pinned HIOMR kitchensink controller | IN_PROGRESS | Fresh `10.0.87` analysis root pending | No duplicate launch |
| STATUS-001 | Capture initial controller, lock, Slurm, and DAG evidence | OPEN | Pending |  |
| CLOSE-001 | Record terminal result and release owned lock | OPEN | Pending |  |

## Intended Catalog Command

`bin/day_run produce_snv_concordances produce_sentdhiomr_sv produce_tiddit_sv_vcf produce_manta_sv_vcf produce_sentdhiomr_snv_vcf produce_sentdhiomr_segdup produce_htd_calls produce_smn12_orthogonal_calls produce_relatedness produce_vep produce_metagenomics produce_multiqc_all --config 'aligners=["sent"]' 'dedupers=["na"]' 'snv_callers=["sentdhiomr"]' 'sv_callers=["tiddit","manta"]' 'htd_callers=["smn12"]' 'multiqc_qc={"enable_tools":["vep","metagenomics"]}' -p -j 100 -k -T 1 --produce-ursa-manifest true --produce-rulegraph true --produce-filegraph false --produce-dag false`

## Final State

All rows terminal: no
