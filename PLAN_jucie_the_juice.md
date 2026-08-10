# DayOA 13.0.110 NICU Caller and Inflection Packaging Plan

## Summary

> For all testing, use the hg002 5x ILMN 5xONT fastq data now avail

> use dayoa==13.0.112 as the starting point for a workbracnh new localhost clone PWD so you don't conflicy with in agents in the current dirs

Implement the NICU research portfolio in isolated DayOA and DYEC clones. Add complementary SR/LR callers, tandem-repeat calling, three SV-merging lanes, benchmarking, and a market-comparison report.

Extend the existing HIOMR2 Inflection analytical package so these results are delivered under explicitly experimental folders. Raw Manta and Dysgu VCFs will not be packaged; their evidence will be represented through the Jasmine ensemble and its source-provenance/support artifacts.

Methylation remains deferred because no POD5 or modBAM data are archived.

## Caller and Merger Integration

- SR callers on the canonical SR alignment:
  - Manta 1.6.0.
  - Dysgu 1.8.0 in paired-end mode.
  - Existing TIDDIT.
- LR callers on the canonical ONT alignment:
  - Sentieon LongReadSV.
  - Sniffles2.
  - Severus germline calling, including its final VCF and complex-SV cluster tables. [Severus outputs](https://github.com/KolmogorovLab/Severus#output-files)
- Repeat callers:
  - Existing LongTR genome-wide and disease-focused catalogs.
  - Existing ExpansionHunter retained independently.
- GBA1 remains covered by Sentieon SegDup; do not add Gauchian.
- Feed the same normalized caller set into:
  - Jasmine as the primary ensemble.
  - SURVIVOR as a comparison baseline.
  - OctopuSV as an experimental challenger.
- Preserve raw calls in the analysis root even where they are intentionally excluded from the Inflection package.

## Inflection Package Contract

Update `produce_sentdhiomr2_inflection_analytical_package` and bump its schema from `dayoa.hiomr2_inflection_analytical_package/1.2` to `/1.3`.

Keep all existing `results/`, `provenance/`, and realigned-CRAM paths unchanged. Add:

```text
experimental/
├── sv/
│   ├── callers/
│   │   ├── <sample>.tiddit.vcf.gz[.tbi]
│   │   ├── <sample>.sniffles2.vcf.gz[.tbi]
│   │   ├── <sample>.severus.germline.vcf.gz[.tbi]
│   │   ├── <sample>.severus.breakpoint_clusters.tsv
│   │   ├── <sample>.severus.breakpoint_clusters_list.tsv
│   │   └── <sample>.severus.breakpoint_double.csv
│   ├── merged/
│   │   ├── jasmine/<sample>.jasmine.vcf.gz[.tbi]
│   │   ├── survivor/<sample>.survivor.vcf.gz[.tbi]
│   │   └── octopusv/<sample>.octopusv.{svcf,vcf.gz,vcf.gz.tbi,bedpe}
│   └── comparison/
│       ├── <sample>.source-support.tsv
│       ├── <sample>.merger-concordance.tsv
│       └── <sample>.bnd-topology-validation.json
├── repeats/
│   └── longtr/
│       ├── <sample>.longtr.all.vcf.gz[.tbi]
│       └── <sample>.longtr.disease.vcf.gz[.tbi]
├── cnv_sv/
│   └── <sample>.cnv-sv-concordance.tsv
├── benchmarks/
│   ├── <sample>.truvari-summary.tsv
│   └── <sample>.truvari-metrics.json
└── provenance/
    ├── <sample>.caller-inputs.tsv
    ├── <sample>.jasmine-inputs.tsv
    └── <sample>.experimental-artifacts.json
```

Manta and Dysgu packaging rules:

- Do not copy their raw VCFs into the Inflection package.
- Include both as mandatory Jasmine inputs after normalization.
- Require `jasmine-inputs.tsv` to record each caller’s original path, version, SHA-256, record count, normalization actions, modality, and support-vector position.
- Require the Jasmine support table to expose which merged records contain Manta or Dysgu support.
- Keep Manta and Dysgu in the identical input set used for the SURVIVOR and OctopuSV comparison lanes, while exposing their package provenance principally through Jasmine.
- Absence or invalidity of either required input fails the research/package target; do not silently create a reduced ensemble.

## Packaging Interface and Validation

- Generate a strict `dayoa.hiomr2_nicu_research_artifacts/1.0` manifest from the research aggregate.
- Add `--experimental-manifest` to the packaging CLI and declare the manifest plus every referenced artifact as Snakemake inputs.
- Use a fixed role-to-destination allowlist; never accept destination paths supplied by the manifest.
- Validate sample identity, GRCh38 reference identity, source location beneath the analysis root, expected byte size and SHA-256, VCF/index pairing, caller versions, unique roles, and the complete required-role set.
- Copy experimental caller outputs byte-for-byte. Any package-ready VCF normalization, compression, indexing, or sample-name handling occurs upstream and is documented in provenance.
- Mark every new manifest row with `package_tier: experimental` and `clinical_interpretation_allowed: false`.
- Retain `customer_release_eligible: false`; these additions do not promote an experimental callset into the accepted Inflection result surface.
- Reject symlinks, path escapes, undeclared roles, raw Manta/Dysgu package roles, missing files, hash mismatches, malformed nonempty VCFs, and incomplete indexes.

## CNV and Reporting

- Keep CNVscope as the independent copy-state result under `results/`.
- Do not merge CNVscope segments into any SV VCF.
- Package a 50% reciprocal-overlap CNV/SV concordance table retaining CN state, coordinates, overlap fractions, and caller/merged-record identifiers.
- Create the timestamped Markdown report covering algorithms, NICU capability gaps, merger performance, comparison with rapid and ultrarapid WGS products, and the methylation eligibility conclusion:
  - Native PCR-free SQK-LSK114 and SQK-NBD114.24 data would be compatible if POD5 existed.
  - PCR/WGA-derived libraries are not suitable for recovering the native methylome.
  - Current FASTQ-only archives remain ineligible for retrospective methylation calling.
  - No modkit, Dorado-modbase, or POD5 workflow is implemented now.

## DYEC and Testing

- Add research command `hybrid_ilmn_ont_hiomr2_nicu_research`.
- Have it request the research aggregate and schema-1.3 Inflection analytical package.
- Leave established customer-delivery commands unchanged.
- Add tests for:
  - Exact package tree and deterministic manifest hashes.
  - Presence of all requested experimental outputs.
  - Absence of raw Manta and Dysgu VCFs.
  - Mandatory Manta/Dysgu rows and support-vector positions in Jasmine provenance.
  - VCF/index, sample, build, BND topology, malformed-input, symlink, path-escape, and hash failures.
  - CNV/SV concordance without CNV-to-SV substitution.
  - `customer_release_eligible: false` and experimental classification.
- Run local tests and supported `dy-r` dry-runs.
- Require one fresh exact-release hybrid HG002 validation with GIAB SV v5.0q assets.
- Preserve all live logs, manifests, package inventories, benchmarks, and checksums in the controlling ledgers before releasing DayOA and updating the DYEC pin.

# Multiqc fork updates
- Be sure to include all of these new tools outputs in the multiqc final report, which might mean hacking the final multiqc lsmc-bio fork to include them. 

# Finally, cp all created cache and container pulls to the s3 location so they are pulled in and available for all future built clusters, saving rebuild of the same cache situatioon. Also, please review env yamls and tighten up pinned version of python where they are free floating (and query the created cached conda env for the actual python ver to pin the correct one please. Do this before ther final test runs so they rebuild correctly.

# regression testsing

- I wantt o be able to delete the raw fastq for both ONT and ilmn, but this depends on the crams created being able to reverse generate the input fastqs completely. Which, if i understand correctluy, depends on certain minimap2 and bwa args being in place. I want a test to run that confirms we can in fact reverse getnerate the complete input fastq set for ilmn and ont (including failed or unmapped reads!  all fastqs should be reproducible end to end.  Is this possible for both ilmn and ont?  can you add a test for this?

# Bonuis Plan Addition
# Dynamic `/scratch`–`/dev/shm` Execution and FSx Publication Ledger

## Summary

Create the controlling ledger at:

`/Users/jmajor/projects/lsmc/hiomr2-nicu-callers/daylily-omics-analysis/docs/plans/20260801T051014Z_dynamic_local_storage_fsx_publish_ledger.md`

Implement from DayOA `13.0.110` in the isolated `codex/hiomr2-nicu-callers-13.0.110` clone. Preserve the separate DYEC clone for compatibility review; do not touch the existing dirty checkouts.

This replaces the earlier strict NVMe-only plan for all active DayOA rules. Backend selection occurs once, inside each allocated compute job:

1. Select `/scratch` when it is a real, writable, local NVMe mount with existing 10% free-space headroom.
2. Otherwise log the rejection reason and select mounted, writable `tmpfs` `/dev/shm`.
3. Fail before running the tool if neither passes.
4. Never switch storage during execution.
5. Publish every locally produced final artifact back to its canonical FSx path before success.

No backend, scratch root, or fallback preference is configurable. Slurm partition lists remain unchanged.

## Runtime and Publication Contract

- Make `dayoa_spool_publish.bash` the canonical active-rule interface. It exports a unique job/rule directory plus `TMPDIR`, `TMP`, and `TEMP`.
- Use actual mount and filesystem evidence—not partition names or directory existence. Reject symlinks, the root filesystem masquerading as `/scratch`, FSx/network backing, unsafe ownership, or unsupported filesystem types.
- Use check-only capacity admission as requested: retain the existing 10% headroom check without adding per-rule capacity reservations. Document that concurrent jobs can still exhaust the selected backend.
- Open declared logs directly on FSx before probing local storage so selector failures remain durable.
- Require publisher sources to be regular non-symlink files beneath the exact claimed job directory and destinations beneath `/fsx`.
- Stage outputs as hidden FSx siblings, flush them, and atomically rename them. For output sets, stage everything first, commit data/index/metadata files, and commit any completion marker last.
- Preserve rule-specific validators; do not impose a universal nonempty-file gate because some legitimate outputs may be empty.
- Clean selected local storage after success or failure. A local-only artifact never satisfies a rule.
- Keep controller and environment setup temporary files under `/tmp`; this selector is compute-job-only.

## Control Ledger

| ID | Requirement | Status | Category | Gate | Owner | Acceptance evidence | Root cause / terminal note |
|---|---|---|---|---|---|---|---|
| AMD-001 | Supersede the NVMe-only and “no `/dev/shm` fallback” clauses in `update_all_nvme_plan.md` with the runtime-selection contract above. | `SUCCESS` | `plan_amendment` | Gate 0 | orchestrator | Current-thread decisions: all active rules, runtime-only scheduling, check-only admission. | New ledger becomes controlling. |
| G0-001 | Create isolated DayOA and DYEC clones, record exact SHAs, branches, remotes, and clean status; confirm DayOA baseline is tag `13.0.110` at `9479e65e…`. | `OPEN` | `feature_implementation` | Gate 0 | orchestrator | Clone paths and `git status --short --branch`. | — |
| G0-002 | Build the recursive active `workflow/Snakefile` include graph and inventory every reachable rule using `/scratch`, `/dev/shm`, manual fallback code, runtime-temp helpers, or local-output publication. | `OPEN` | `feature_implementation` | Gate 0 | orchestrator | Initial sweep found 71 candidate rule files; append one `RULE-###` ledger row per reachable rule. | Exclude commented, deprecated, quarantined, and unreachable copies. |
| G0-003 | Classify each active hit as temp-only, local-output producer, strict-NVMe claimant, explicit staging workflow, container bind, or non-storage literal. | `OPEN` | `feature_implementation` | Gate 0 | orchestrator | Per-rule table names outputs, FSx destinations, current helper, and affected config keys. | No literal is changed without classification. |
| CON-001 | Refactor selection so any `/scratch` validation or headroom failure falls through to validated `/dev/shm`, with both diagnostics retained if selection fails. | `OPEN` | `feature_implementation` | Gate 1 | orchestrator | Focused selector tests. | — |
| CON-002 | Provide collision-safe job/rule directories, environment variables, traps, and cleanup for either backend. | `OPEN` | `feature_implementation` | Gate 1 | orchestrator | Concurrency, unsafe-path, signal, and cleanup tests. | — |
| PUB-001 | Generalize atomic publication so sources under the selected `/scratch` or `/dev/shm` job directory publish to FSx. | `OPEN` | `feature_implementation` | Gate 1 | orchestrator | Scratch and shm publication fixtures produce identical FSx results. | — |
| LOG-001 | Ensure every migrated rule opens its declared FSx log before local-storage selection and keeps benchmarks on FSx. | `OPEN` | `contract_test` | Gate 1 | orchestrator | Static ordering test plus selector-failure fixture. | — |
| CFG-001 | Remove backend-controlling `scratch_root`, `tmp_base`, `tmpdir`, or equivalent settings from active rule/profile contracts; reject attempted overrides instead of ignoring them. | `OPEN` | `config_or_startup_contract` | Gate 2 | orchestrator | Profile/schema tests and negative override tests. | Tool-private subdirectory names may remain; backend paths may not. |
| MIG-001 | Migrate active temp-only and duplicated manual-fallback rules to the shared selector. | `OPEN` | `feature_implementation` | Gate 2 | orchestrator | All generated `RULE-###` rows terminal with focused tests. | — |
| MIG-002 | Migrate active local-output producers to shared atomic FSx publication, including Manta, Dysgu, TIDDIT, sorting/indexing, and report producers. | `OPEN` | `feature_implementation` | Gate 2 | orchestrator | No successful rule can leave its declared terminal output only in local storage. | — |
| MIG-003 | Replace strict `/scratch`-only behavior in active HIOMR2, Jasmine, alignment, shard, gather, and publisher paths while preserving unique analysis/sample/rule namespaces. | `OPEN` | `feature_implementation` | Gate 2 | orchestrator | Updated HIOMR2 contract tests accept both selected backends and retain FSx publication. | — |
| MIG-004 | Reconcile explicit staging workflows such as BCL Convert, align/sort, Sentieon, and large fan-in rules without staging FSx inputs unnecessarily. | `OPEN` | `active_product_contract` | Gate 2 | orchestrator | Existing output and staging semantics preserved; only local backend selection changes. | — |
| MIG-005 | Require every new NICU caller and merger rule—LongTR, Severus, Manta, Dysgu, TIDDIT, Jasmine, SURVIVOR, OctopuSV, and Truvari—to use the same shared contract. | `OPEN` | `feature_implementation` | Gate 2 | orchestrator | Caller-specific static and output-publication tests. | Methylation remains excluded. |
| DYEC-001 | Inspect the isolated DYEC clone for container visibility of `/dev/shm` and optional `/scratch`; make no queue, partition, pricing, or cluster-template change. | `OPEN` | `not_applicable_after_inspection` | Gate 2 | orchestrator | Compatibility inspection recorded. | Expected terminal state is `NO_LONGER_NEEDED`; amend before any DYEC source change. |
| TEST-001 | Cover mounted NVMe, absent scratch, scratch symlink, root-directory masquerade, unwritable/unsupported/full scratch, valid tmpfs, and neither-backend cases. | `OPEN` | `contract_test` | Gate 3 | orchestrator | Focused pytest passes. | — |
| TEST-002 | Cover atomic stage/commit, multi-output ordering, interrupted copy, failed validation, publish failure, signals, cleanup, and durable FSx logs. | `OPEN` | `contract_test` | Gate 3 | orchestrator | No partial file becomes a declared final output. | — |
| TEST-003 | Add an active-include-graph guard proving no reachable rule retains manual backend selection or a backend-config override. | `OPEN` | `contract_test` | Gate 3 | orchestrator | Deprecated and unreachable sources reported separately. | — |
| VAL-001 | Run focused tests, workflow/profile/catalog tests, `bash tests/test_cli_commands.sh`, full pytest, and `git diff --check`. | `OPEN` | `contract_test` | Gate 4 | orchestrator | Exact commands and results entered into the ledger. | Never invoke raw `snakemake`. |
| LIVE-001 | Before release, run supported `dy-r` proof jobs on one NVMe node and one node without `/scratch`; verify selected roots, FSx outputs, cleanup, logs, and benchmarks. | `OPEN` | `active_product_contract` | Gate 4 | orchestrator | Exact cluster, jobs, nodes, output paths, and checksums recorded. | Mark `BLOCKED` if no appropriate cluster or live-run authority is available. |
| FINAL-001 | Terminalize every workstream and generated `RULE-###` row and report whether the ledger is terminal and whether the objective is complete. | `OPEN` | `contract_test` | Gate 5 | orchestrator | Zero `OPEN`, `IN_PROGRESS`, or `ATTEMPTING_BUGFIX` rows. | Any `FAIL` or `BLOCKED` means the objective is not fully complete. |

## Validation and Defaults

Focused validation begins with:

```bash
python -m pytest \
  tests/test_dayoa_spool_publish.py \
  tests/test_hiomrs_scratch.py \
  tests/test_rule_log_benchmark_contracts.py \
  tests/test_slurm_profile.py -q
bash tests/test_cli_commands.sh
python -m pytest -q
git diff --check
```

Defaults and boundaries:

- Scope is every rule reachable from the active Snakefile include graph, not every historical source file.
- Backend selection is automatic and cannot be configured.
- Scheduling remains unchanged; no non-NVMe partitions are added.
- Capacity is checked but not reserved. Later exhaustion fails the rule and prevents successful publication.
- Input data stays on FSx unless an existing rule explicitly requires staging.
- No current controller, running analysis, dirty checkout, AWS resource, Slurm policy, commit, push, tag, PR, or release is changed by creating or locally implementing this ledger.
