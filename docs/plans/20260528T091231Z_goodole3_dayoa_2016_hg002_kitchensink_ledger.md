# Goodole3 DayOA 2.0.16 HG002 Kitchen-Sink Validation Ledger

Created: 2026-05-28T09:12:31Z

## Objective

Clone DayOA `2.0.16` on the running `goodole3` cluster, configure the bundled HG002 `0.01x` Illumina fixture, dry-run the requested Illumina-only kitchen-sink target set, and launch the live run only if the dry-run succeeds.

## Result

Terminal blocked. Clone, HG002 fixture config, setup, and preflight succeeded, but the requested DayOA `2.0.16` kitchen-sink dry-run exited `1` during Snakemake workflow parsing. Per the plan gate, the live command was not launched.

## Gate 0 Inventory

- Control ledger: `docs/plans/20260528T091231Z_goodole3_dayoa_2016_hg002_kitchensink_ledger.md`
- DYEC repo: `/Users/jmajor/.codex/worktrees/dyec-fsx-dra-mounts/daylily-ephemeral-cluster`
- DYEC branch: `codex/dyec-dewey-registration-refactor-20260528`
- DYEC status before ledger creation: clean
- Target cluster: `goodole3`, `us-west-2`, AWS profile `lsmc`
- Headnode: `i-0bd631af238bfac56`, private host `ip-10-0-0-144`, user `ubuntu`
- Cluster state: `CREATE_COMPLETE`; compute fleet `RUNNING`
- Queue baseline: `dyec headnode jobs --profile lsmc --region us-west-2 --cluster goodole3` returned only the header row, with no Slurm jobs.
- FSx baseline: `/fsx` mounted, `4.4T` total, `851G` used, `3.6T` available, `20%` used.
- Clone destination: `/fsx/analysis_results/ubuntu/2.0.16` absent before execution.
- Existing tmux sessions: `inflection_20x10x_kitchensink_j250_20260528T043733Z`, `inflection_20x10x_knownpass_j400_real_20260528T011810Z`.
- Required reference assets present:
  - Ganon2 prefix suffixes: `.hibf`, `.tax`, `.manifest.txt`
  - Kraken2 DB: `/fsx/references/runtime_assets/tool_specific_resources/metagenomics/kraken2/k2_pluspfp_16_GB_20260226`
  - sourmash DB: `/fsx/references/runtime_assets/tool_specific_resources/sourmash/gtdb-rs226/gtdb-reps-rs226-k31.dna.zip`
  - HG002 truth VCF/TBI/BED under `/fsx/references/genomic_data/organism_annotations/H_sapiens/hg38/controls/giab/snv/v4.2.1/HG002/hg38/`
- Inspection command evidence: SSM command `298d6716-4886-46a8-aada-c5097a80af4e`, status `Success`, response code `0`.

## Execution Notes

- `source dyoainit` was not available in `/home/ubuntu` before clone (`bash: dyoainit: No such file or directory`); the clone-local `dyoainit` from `/fsx/analysis_results/ubuntu/2.0.16/daylily-omics-analysis` was used after `day-clone`, matching the fresh-checkout execution context.
- A first non-interactive tmux driver attempt was stopped before dry-run because `source dyoainit` printed `CondaError: Run 'conda init' before 'conda activate'` and the `dy-a` alias was unavailable (`dy-a: command not found`). No Snakemake command ran in that attempt. Evidence was rotated to `.ignore/dayoa_2016_hg002_kitchensink.noninteractive_attempt.log`.
- The authoritative dry-run was executed in a persistent interactive `bash -il` tmux pane with setup sent as separate commands: `source dyoainit`, `dy-a slurm hg38`, then `dy-r ... -n`.

## Execution Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| KS-001 | Ledger | Record Gate 0 before headnode mutation. | SUCCESS | feature_implementation | Gate 0 | orchestrator | Gate 0 inventory recorded above. |  | Baseline captured before clone/config/run work. |
| KS-002 | Headnode clone | Run `day-clone -t 2.0.16 -d 2.0.16` as `ubuntu` and verify tag/commit. | SUCCESS | feature_implementation | Gate 1 | orchestrator | `day-clone -t 2.0.16 -d 2.0.16` completed with `Great success`; checkout path `/fsx/analysis_results/ubuntu/2.0.16/daylily-omics-analysis`; `git describe --tags --exact-match` returned `2.0.16`; `git rev-parse HEAD` returned `35eaa37034eb3a048b7cf531ae8b3c488685f18e`. |  | Fresh DayOA clone created and pinned to requested tag/commit. |
| KS-003 | Fixture config | Configure bundled HG002 `0.01x` samples/units in the fresh checkout and verify input FASTQs/truth/Ganon2 prefix suffix files. | SUCCESS | feature_implementation | Gate 1 | orchestrator | Copied `.test_data/data/0.01xwgs_HG002_hg38.samples.tsv` to `config/samples.tsv`; copied `.test_data/data/0.01xwgs_HG002_hg38.units.tsv` to `config/units.tsv`; preflight confirmed both HG002 FASTQs, `/HG002/` truth path in `config/samples.tsv`, and Ganon2 `.hibf`, `.tax`, `.manifest.txt` assets. |  | HG002 fixture config and required files verified before dry-run. |
| KS-004 | Dry-run gate | Run the requested target set with `-n`; if nonzero, do not launch live. | FAILED | contract_test | Gate 2 | orchestrator | Dry-run command started at `2026-05-28T09:18:46+00:00` in tmux `dayoa_2016_hg002_kitchensink`; rc marker `.ignore/dayoa_2016_hg002_kitchensink_dryrun.rc` contains `DAYOA_2016_DRYRUN_RC=1`; `day_cmd.log` recorded the exact Snakemake command; latest Snakemake log `.snakemake/log/2026-05-28T091849.030971.snakemake.log`. | DayOA 2.0.16 fails during workflow parsing in `workflow/rules/contam_identity.smk`, line 393: `AttributeError: 'Rules' object has no attribute 'legacy_cram_compat_bam'`. | Live launch gate blocked; no altered-scope rerun performed. |
| KS-005 | Live launch | If dry-run succeeds, launch the same target set without `-n` inside tmux `dayoa_2016_hg002_kitchensink`. | NO_LONGER_NEEDED | feature_implementation | Gate 3 | orchestrator | Dry-run exited nonzero; `squeue -u ubuntu` showed only the header row after dry-run. | Dry-run gate failed before any live Snakemake execution. | Live command was not launched. |
| KS-006 | Initial monitoring | Capture initial status, tmux log, `squeue`, and output handles after live launch. | NO_LONGER_NEEDED | contract_test | Gate 4 | orchestrator | `.ignore/dayoa_2016_hg002_kitchensink.log` contains the interactive dry-run transcript; final report check returned `MISSING:results/day/hg38/reports/DAY_final_multiqc.html`; failing rule context: `bam=rules.legacy_cram_compat_bam.output.bam` and `bai=rules.legacy_cram_compat_bam.output.bai` at `workflow/rules/contam_identity.smk:393-394`. | Live launch did not occur because the dry-run gate failed. | No live outputs expected from this attempt. |
| KS-007 | LongTR scope | Exclude LongTR from this Illumina-only validation. | NO_LONGER_NEEDED | plan_amendment | Gate 0 | orchestrator | User-selected plan states LongTR is skipped because DayOA restricts LongTR to ONT CRAM alignments. |  | LongTR is out of scope for this run; no ONT manifest will be synthesized. |

## Command Under Test

```bash
dy-r produce_sent_align produce_dmd_dedup_cram produce_sentd_snv_vcf produce_alignstats produce_snv_concordances produce_relatedness produce_gatk_contam_estimate produce_site_mix_contam_estimate produce_global_contam_check produce_vep produce_expansionhunter produce_htd_calls produce_metagenomics produce_multiqc_all \
  --config 'aligners=["sent"]' 'dedupers=["dmd"]' 'snv_callers=["sentd"]' 'htd_callers=["gauchian","cyrius","smn12","parascopy","smaca","genetocn"]' 'multiqc_qc={"enable_tools":["vep","metagenomics","contam_identity"]}' \
  -p -j 100 -k
```
