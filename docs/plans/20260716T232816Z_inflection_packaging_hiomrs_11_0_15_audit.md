# Inflection Packaging Scripts Audit Against the DYEC-Pinned HIOMRS Kitchen Sink

**Report date:** 2026-07-16
**Audit type:** Static source and interface review only
**Implementation or execution performed:** None

## Executive conclusion

Mike Kennemer's `inflection-packaging` branch is a substantial prototype for transforming HIOMRS outputs into a per-sample Inflection/SeqOne-style delivery tree. It contains useful packaging logic, VCF annotation ideas, a compliance checker, and exploratory CNV review tools, but it is not integrated with DayOA and cannot consume the DayOA version currently pinned by DYEC without changes.

The authoritative starting point requested for this audit is DYEC's current command catalog. At the audited refs:

| Component | Audited ref | Finding |
|---|---|---|
| `daylily-ephemeral-cluster` | `main` at `fcdd4cb3e3b67475da47c95cc502ab95af3b1ba0`, annotated tag `10.3.27` | The command catalog pins DayOA `11.0.15` for HIOMRS and HIOMRS Kitchen Sink. |
| Pinned `daylily-omics-analysis` | annotated tag `11.0.15`, peeled commit `ef279ccafa70dd6244c6feac39340cc34f4a80f3` | This is the workflow and output contract used for the input trace below. |
| Mike K branch | `origin/inflection-packaging` at `7d1198be564c02f7b105d0f4273fbeebc572f9c3` | One commit authored by Michael Kennemer; the branch adds 19 files under `scripts/packaging/inflection/`. |

The Inflection commit is not an ancestor of DayOA `11.0.15`, and `11.0.15` contains none of these packaging files. The branch adds no Snakemake rule, target, automated test, or command-catalog entry. Its packager instead searches a legacy output layout using `sentmm2ont/dmd`, `sent/dmd`, and `sentdhiomr` names. DayOA `11.0.15` uses the `hiomrs_sr/na` and `hiomrs_lr/na` namespaces and the caller name `hiomrs`. Consequently, every hard-coded primary input path used by the packager misses the pinned workflow's declared output path, even though the HIOMRS Kitchen Sink conceptually produces nearly all of the required data.

The central recommendation is therefore **do not run or merge the branch as-is against the pinned workflow**. First agree on the delivery contract, then port the logic into a first-class DayOA rule with explicit, pinned HIOMRS inputs and fail-hard validation.

## Scope and evidence boundary

This report compares:

1. The HIOMRS Kitchen Sink entry in `daylily-ephemeral-cluster/config/daylily_pipeline_command_catalog.yaml`.
2. The output declarations and routing in DayOA `11.0.15`, primarily `workflow/rules/sent_hybrid_ilmn_ont_cli.smk` and `workflow/rules/common.smk`.
3. All files added by `origin/inflection-packaging` under `scripts/packaging/inflection/`.

No script was run. No VCF, CRAM, JSON, or real Kitchen Sink result was inspected. No claim in the branch documentation— including the stated `38/38` compliance result—was independently reproduced. Statements about Kitchen Sink availability mean that the pinned workflow declares the output; they do not prove that a particular analysis completed it successfully.

## What the branch intends to build

The branch's documents describe a per-sample delivery directory with three main groups:

```text
<sample-short-name>/
  results/
    tagged SNV VCF
    tagged CNV VCF with abnormal SMN copy-number calls folded in
    primary structural-variant VCF
    mitochondrial VCF
    normalized ExpansionHunter VCF
    chromosome ploidy TSV
    copy-number track TSV
    short-read CRAM
  qc/
    sample metrics JSON
    package manifest JSON
    SNV and CNV tag summaries
  experimental/
    synthetic SMN result VCF
    TIDDIT VCF
    per-gene segmental-duplication VCFs
```

The intended transformation is:

1. Take existing HIOMRS and Kitchen Sink outputs.
2. Normalize sample naming and selected VCF structure.
3. Add heuristic review tags to SNV and CNV records.
4. Derive ploidy, a CN track, a compact metrics JSON, and an SMN VCF.
5. Assemble a customer-facing directory and inventory it in a manifest.
6. Check selected delivery expectations with a compliance script.

The branch documentation explicitly accepts two delivery deviations: it keeps Sentieon/HIOMRS and TIDDIT structural variants separate instead of producing a merged SV callset, and it delivers CRAM where the referenced SeqOne convention prefers BAM. Those are product-contract decisions, not merely implementation details, and should be approved before the code is treated as a formal delivery pipeline.

## The pinned HIOMRS Kitchen Sink contract

DYEC's pinned Kitchen Sink command targets:

- `produce_hiomrs`
- `produce_snv_concordances`
- `produce_tiddit_sv_vcf`
- `produce_alignstats`
- `produce_relatedness`
- `produce_peddy`
- `produce_gatk_contam_estimate`
- `produce_site_mix_contam_estimate`
- `produce_vep`
- `produce_htd_calls`
- `produce_smn12_orthogonal_calls`
- `produce_metagenomics`
- `produce_multiqc_all`
- the final MultiQC HTML and evidence manifest

Its key configuration selects `sent` alignment, `na` deduplication, `hiomrs` SNV calling, `tiddit` orthogonal SV calling, and `smn12` HTD calling. The DYEC input contract accepts paired Illumina FASTQs plus an aligned ONT CRAM and its aligner/caller metadata for this command. DayOA's broader HIOMRS code also has raw ONT FASTQ routing, but that broader capability is not a reason to infer missing source columns in the DYEC command contract audited here.

### Required packaging inputs and their pinned sources

In the paths below, `<root>` is `results/day/<genome>/<sample>`.

| Packaging need | Declared source in DayOA `11.0.15` / Kitchen Sink | Present in pinned contract? | Branch behavior and gap |
|---|---|---:|---|
| Primary SNV VCF | `<root>/align/hiomrs_sr/na/snv/hiomrs/<sample>.hiomrs_sr.na.hiomrs.snv.sort.vcf.gz` | Yes, through `produce_hiomrs` | The branch searches a legacy `align/sentmm2ont/dmd/.../sentdhiomr/...` path, so it does not find this file. |
| Primary CNV VCF | `<root>/align/hiomrs_sr/na/cnv/hiomrs/<sample>.hiomrs_sr.na.hiomrs.cnv.vcf.gz` | Yes, through `produce_hiomrs` | Same legacy-path mismatch. |
| Primary HIOMRS SV VCF | `<root>/align/hiomrs_sr/na/sv/hiomrs/<sample>.hiomrs_sr.na.hiomrs.sv.vcf.gz`, plus `.provenance.json` and `.done` | Yes, through `produce_hiomrs` | Same path mismatch. More importantly, the pinned rule prefers ONT LongReadSV but may explicitly fall back to short-read DNAscope/SVSolver. The branch treats this input as long-read support without checking the provenance sidecar. |
| Orthogonal TIDDIT SV VCF | `<root>/align/hiomrs_sr/na/sv/tiddit/<sample>.hiomrs_sr.tiddit.sv.sort.vcf.gz` | Yes, through `produce_tiddit_sv_vcf` | The branch searches the old `sent/dmd` namespace. Its documentation that TIDDIT is a Kitchen Sink gap is stale for this pinned command. |
| Mitochondrial VCF | `<root>/align/hiomrs_sr/na/hiomrs/mito/<sample>.mito.vcf.gz` | Yes, through `produce_hiomrs` | The branch searches the old `sentdhiomr` layout. |
| ExpansionHunter VCF | `<root>/align/hiomrs_sr/na/hiomrs/expansionhunter/<sample>.eh.vcf` | Yes, through `produce_hiomrs` | The branch searches an old generic short-read location, then rewrites/compresses the VCF. |
| Per-gene segmental-duplication VCFs | `<root>/align/hiomrs_sr/na/hiomrs/segdup/<sample>.<gene>.result.vcf.gz` | Yes, through `produce_hiomrs` | The branch searches the old layout. DayOA `11.0.15` declares the public gene set `CFH`, `CYP11B1`, `CYP2B6`, `CYP2D6`, `GBA1`, `HBA`, `IKBKG`, `NCF1`, `PMS2`, `RCCX1`, `RHD`, `SBDS`, `SMN1`, and `STRC`; the branch's one-off renamer uses the stale name `GBA`. |
| SMN12 summary JSON | `<root>/align/hiomrs_sr/na/htd/smn12/<sample>.hiomrs_sr.na.smn12.summary.json` | Yes, through `produce_smn12_orthogonal_calls` | The branch searches `sent/dmd`. Its documentation that SMN12 is missing from Kitchen Sink is stale for the pinned command. |
| Samtools stats, flagstat, and idxstat | `<root>/align/hiomrs_sr/na/alignqc/samtmetrics/<sample>.hiomrs_sr.na.{stats,flagstat,idxstat}.tsv` | Yes, through `produce_alignstats` for the short-read route | The branch searches the old `sent/dmd` namespace. |
| Short-read CRAM and CRAI | `<root>/align/hiomrs_sr/na/<sample>.hiomrs_sr.na.cram` and `.crai` | Yes, through `produce_hiomrs` | The packager recursively selects the first `*.cram` anywhere under the dataset directory, creates an absolute symlink, and does not package the CRAI. This can select the long-read CRAM, a source CRAM, or another unrelated CRAM. |
| Long-read CRAM and CRAI | `<root>/align/hiomrs_lr/na/<sample>.hiomrs_lr.na.cram` and `.crai` | Yes, through `produce_hiomrs` | Not a formal delivery output, but its presence makes the recursive first-CRAM selection unsafe. |
| Optional alignment summary | A caller-specific alignment summary may be available among HIOMRS metrics, while Kitchen Sink explicitly produces alignment QC | Partially explicit | `make_sample_metrics.py` treats this as optional and silently emits an empty section if absent. The package has no schema declaring whether it is required. |
| Population AF and allele-support fields used by heuristic taggers | The scripts assume fields such as `INFO/AF_genomes`, `LAD`, `SAD`, or `AD` | Not established as a delivery invariant by the audited command catalog/rule target | These are hidden schema dependencies. The scripts do not preflight them, and the pinned target does not guarantee their presence or semantics as part of the packaging interface. |
| Sample alias / customer-facing short name | The workset identifies the sample/dataset, but no audited rule defines the branch's alias regex as the formal delivery name | Missing product contract | The branch guesses an alias with regexes and falls back to the input name. That is an inferred default, not an authoritative naming source. |
| Reference build and contig convention | The DayOA analysis has a selected genome/reference | Available to the workflow, not passed to these scripts | Several scripts assume GRCh38, `chr`-prefixed contigs, or hard-coded coordinates without receiving or validating the actual reference. |

The practical distinction is important: the pinned Kitchen Sink is not missing most of the data products. The branch is missing an interface to the pinned paths and metadata, and some of its algorithms rely on fields whose presence and meaning are not established by the formal target.

## What the scripts actually do

### Production-shaped scripts

| Script | Stated or apparent intention | Actual behavior | Inputs | Outputs and notable review findings |
|---|---|---|---|---|
| `package_delivery_tree.py` | Orchestrate the complete sample delivery package. | Creates directories, calls the tag/derivation modules directly, copies selected VCFs, symlinks a recursively discovered CRAM, and writes a manifest. It does not invoke `check_compliance.py`. It has no complete preflight and no staging/atomic publish, so a failure can leave a partial package. | Dataset directory plus hard-coded legacy relative paths; imported helper modules; external `bcftools`. | Delivery tree, summaries, and manifest. CRAM choice is unsorted first-match discovery; CRAI is omitted; output symlink is absolute. Manifest omits `.tbi` indexes, does not validate its own inventory, and does not reliably fail if an external record-count command fails. |
| `tag_vcf.py` | Normalize and review-tag the primary SNV VCF. | Uses `bcftools norm -m -any`, replaces every FILTER other than `MLrejected` with `PASS`, adds an `INFO/TAG`, and assigns tags for rejection, depth, dense clusters, allele balance, strand orientation, and long/short-read support. It buffers the full VCF in memory. | SNV VCF containing the assumed depth, allele-balance, orientation, and `LAD`/`SAD` or `AD` fields; thresholds are hard-coded. | Tagged BGZF VCF and index plus tag counts. Summing all LAD/SAD values may count reference support as variant support. Existing caller filters can be erased. Reruns can duplicate TAG headers/values. Multi-sample input is not safely handled because the header can be collapsed while record sample columns remain. |
| `tag_cnv_vcf.py` | Add long-read and TIDDIT support tags to HIOMRS CNVs and rescue supported rejected calls. | Loads DEL calls from the supposed long-read SV VCF and DEL/DUP calls from TIDDIT, then scans for reciprocal-overlap and breakpoint proximity. Annotates support and may turn `MLrejected` into `PASS`. | CNV VCF, HIOMRS SV VCF treated as long-read evidence, and TIDDIT VCF. | Tagged CNV VCF/index and counts. The direct `process()` API silently treats missing support VCFs as empty; the orchestrator uses that API. Contig spelling must match exactly. Lookup is linear across candidate SVs. The HIOMRS SV provenance is not checked, so short-read fallback calls can be mislabeled as long-read confirmation. |
| `cnv_to_ploidy.py` | Derive chromosome ploidy and confidence from alignment depth. | Parses samtools idxstats, computes read-count-per-base by chromosome, normalizes to a median autosomal baseline, estimates variability with MAD, and reports CN/GQ for chromosomes 1-22, X, and Y. | Short-read idxstats TSV with recognized chromosome names. | Ploidy TSV. This is a coarse chromosome-wide heuristic rather than a windowed, GC-corrected ploidy caller. If no valid autosomal baseline exists, formatting/error paths are fragile and results are not trustworthy. |
| `cn_track.py` | Produce a copy-number track for delivery. | Derives an autosomal median from CNV-record `DPS` values and emits only PASS CNV records with a normalized CN estimate. | HIOMRS CNV VCF with numeric `DPS`, FILTER, and intervals. | CN TSV. It is an altered-interval list, not a continuous neutral-plus-altered genome track. It also treats `DPS` as linearly proportional to CN even though another branch script describes the signal as nonlinear/model-internal. |
| `eh_prep.py` | Prepare ExpansionHunter output for customer delivery. | Removes all existing contig headers, injects contigs learned from another VCF, optionally renames the sample, then BGZF-compresses and tabix-indexes the records. | EH VCF and a CNV VCF used as the contig-header donor. | Normalized EH VCF/index. Reference compatibility is inferred, not checked. It assumes a valid `#CHROM` header and canonical contig behavior. |
| `make_sample_metrics.py` | Consolidate alignment and SMN QC into one customer JSON. | Parses flagstat, samtools stats, idxstats, SMN12 JSON, and optional alignment metrics into a custom document. | Short-read QC TSVs, SMN12 JSON, and optional alignment summary. | Metrics JSON. Autosomes are recognized only as `chr1`-`chr22`; unprefixed references lose the autosomal/sex summary. Optional sections can silently be empty. There is no schema/version, and internal absolute source paths are written into the customer artifact. The first SMN12 object is accepted without verifying sample identity. |
| `make_smn1_result_vcf.py` | Convert SMN12 summary results to VCF and fold abnormal SMN copy-number calls into the CNV VCF. | Uses an SMN1 segmental-duplication VCF as a header donor but constructs synthetic SMN records from hard-coded GRCh38 coordinates, REF alleles, ALT definitions, and ad hoc CN-to-GT mappings. Only abnormal calls are folded into CNV. | SMN12 summary JSON, SMN1 per-gene VCF, and primary CNV VCF. | Experimental SMN VCF/index and modified CNV VCF/index. Coordinates and alleles are not validated against the pinned reference. INFO values are not robustly escaped, `NA` can conflict with numeric fields, and high-CN ALT/GT semantics are incomplete. A normal sample may produce no folded record, which conflicts with the compliance check. |
| `check_compliance.py` | Assert that the package satisfies the documented Inflection/SeqOne layout. | Checks selected file presence and performs shallow command-line/record spot checks, then reports a fixed checklist score. It knowingly treats the separate-SV and CRAM decisions as accepted deviations. | Completed delivery directory plus `bcftools` and `htsfile`. | Text checklist/exit status. Helper commands ignore return codes and stderr, which can convert tool failure into misleading check results. The manifest's hashes and completeness are not verified. Sample names, reference build, VCF sort/validity, schemas, and full index inventory are not checked. EH requires a multiallelic record even when a valid sample may have none; CNV requires a folded SMN record even when normal CN may produce none. The documented `38/38` result is therefore evidence of a shallow prototype check, not validated package correctness. |
| `vcf_utils.py` | Share VCF I/O, indexing, sample aliasing, and tool-location helpers. | Finds tools through PATH and then Mac-specific `/opt/homebrew/bin` paths, reads/writes VCF text, runs BGZF/tabix operations, and guesses aliases by regex with fallback to the original name. | VCF paths, external executables, and dataset names. | Utility side effects. Tool discovery and alias fallback are implicit environment/product assumptions. `is_bgzf` does not establish command success before interpreting output. |

### Exploratory analysis scripts

These scripts label calls as likely true or false positives. They are research/review aids, not package assembly steps, and `package_delivery_tree.py` does not call them.

| Script | Actual behavior | Inputs | Outputs and review findings |
|---|---|---|---|
| `analyze_cn_gains.py` | Queries SNVs inside each tagged CN gain and heuristically classifies the CNV from VAF distributions, population AF, and `DPS`. | Tagged CNV VCF and SNV VCF with assumed `AF_genomes`, `SAD`/`AD`, and depth fields; `bcftools`. | TSV to stdout. A failed `bcftools` query is treated like no evidence. The classification assumes a linear DPS/CN relationship and can call a balanced CN4 gain false-positive even though the accompanying notes recognize balanced duplication as plausible. |
| `analyze_longreadsupported.py` | Reviews CNVs tagged as long-read supported using SNV VAF/LOH patterns, flanking evidence, and regional TIDDIT overlap. | Tagged CNV VCF, SNV VCF, TIDDIT VCF, and assumed population/support annotations; `bcftools`. | TSV to stdout. It also ignores query failures and emits high-consequence `LIKELY_TP`/`LIKELY_FP` labels from unvalidated heuristics. Its regional TIDDIT evidence is not the same test as the strict concordance used by the CNV tagger. |

### One-off Coriell batch wrappers

These scripts are tied to the author's local four-Coriell experiment. They scan directories named `HYB-4Coriells-*` next to the code, assume exactly eight datasets, and derive chip/sample variants from filename patterns. They are not general DayOA workflow components.

| Script | Actual behavior | Outputs and review findings |
|---|---|---|
| `batch_annotate.py` | Batch-runs SNV tagging over the expected Coriell directories. | Prototype tagged VCFs. Directory count and naming are hard-coded. |
| `batch_annotate_cnv.py` | Attempts to batch-run CNV tagging over the Coriell directories. | As committed, its constructed path for `tag_cnv_vcf.py` points outside the Inflection directory and appears broken. It also inherits all hard-coded dataset assumptions. |
| `batch_ploidy.py` | Runs ploidy derivation for the local experiment and infers conditions/chips from names. | Prototype ploidy TSVs. Missing regex matches, missing idxstats, or unexpected conditions are not robustly validated. |
| `rename_aux_vcfs.py` | Renames/copies auxiliary VCFs for the local experiment. | Renamed prototype VCFs. Missing files are silently skipped, and the gene name `GBA` does not match the pinned HIOMRS public output name `GBA1`. |

## Branch documents and their current accuracy

| Document | Useful content | Stale or unproven content against the pinned baseline |
|---|---|---|
| `DELIVERY_PIPELINE_RULE_MAP.md` | Maps desired delivery artifacts to conceptual DayOA producers and identifies product-contract questions. | Uses legacy `sentdhiomr`, `sentmm2ont/dmd`, and `sent/dmd` paths. It treats TIDDIT and SMN12 as Kitchen Sink gaps, but both are explicit pinned targets. |
| `package_sentdhiomr_formal_outputs_sketch.md` | Sketches how a formal workflow target might expose the delivery package. | No corresponding rule exists. The names and paths predate the pinned `hiomrs_sr/na` contract. |
| `tag_cnv_vcf_summary.md` | Explains the prototype CNV concordance logic and thresholds. | The performance and accuracy claims are not backed by committed tests or reproducible result artifacts in this branch. |

## Output contract the branch actually creates

The package is a derived delivery artifact only; it does not feed results back into HIOMRS. Its main outputs are:

- Tagged SNV VCF plus index and summary.
- Tagged/folded CNV VCF plus index and summary.
- Copied primary HIOMRS SV VCF and TIDDIT VCF, kept separate.
- Copied mitochondrial and per-gene segmental-duplication VCFs.
- Rewritten ExpansionHunter VCF.
- Derived ploidy and CN TSVs.
- Synthetic SMN VCF.
- Consolidated sample metrics JSON.
- A CRAM symlink without the associated CRAI.
- A JSON manifest of selected outputs.

The output is not currently a reproducible DayOA target because it has no declared Snakemake inputs/outputs, no command-catalog target, no pinned tool environment, no transactional completion marker, and no tests. Several files required to use or verify the delivered files—especially `.tbi` indexes and the CRAM `.crai`—are missing from or excluded by the manifest logic.

## Proposed changes for review

These are recommendations only; none were implemented.

### P0 — contract and correctness blockers

1. **Approve the delivery contract before porting code.** Decide whether this is an Inflection-specific or SeqOne-compatible product; whether SVs must be merged; whether CRAM is acceptable instead of BAM; which SMN source is authoritative; what sample alias authority is used; which gene set is required; and which reference/contig convention applies.
2. **Port the package as a first-class DayOA rule at the selected DayOA baseline.** Use explicit named Snakemake inputs from the `hiomrs_sr/na` and `hiomrs_lr/na` output constants. Do not retain recursive file discovery, legacy path guessing, or silent alternatives.
3. **Require all inputs before writing outputs.** Validate sample identity, reference build, expected VCF fields, indexes, and tools in a preflight. Write into a staging directory and publish atomically only after the entire package and validator succeed.
4. **Use the explicit short-read CRAM and CRAI.** Remove recursive first-CRAM selection. Decide whether delivery copies, hard-links, or symlinks the pair; an absolute symlink into an analysis tree is not portable delivery media.
5. **Honor HIOMRS SV provenance.** Read and validate the pinned `.provenance.json` before calling the primary SV VCF long-read evidence. Fail or label it accurately when the rule used its short-read fallback.
6. **Correct SNV support semantics.** Confirm the schema and use ALT-specific LAD/SAD/AD values. Preserve original caller FILTER state unless an explicitly approved delivery specification requires replacement; do not silently convert unrelated filters to `PASS`.
7. **Fail hard on every external command error.** Capture and validate return code and stderr from `bcftools`, `htsfile`, compression, indexing, and query commands. Absence of evidence must not be conflated with tool failure.
8. **Define and validate the SMN representation.** Obtain coordinates and REF alleles from the pinned reference/resource, escape VCF fields, define CN/GT/ALT semantics for all supported CN values, verify the sample in the SMN12 JSON, and specify how SMN12 relates to the HIOMRS segmental-duplication SMN1 result.

### P1 — validation, robustness, and auditability

9. **Replace shallow compliance scoring with package validation.** Validate the exact inventory, all `.tbi`/`.crai` files, hashes, VCF parseability/sort/reference/sample headers, expected schemas, and manifest completeness. Valid biological absence must not fail checks that demand a multiallelic EH call or abnormal SMN call.
10. **Add an explicit package schema and version.** Version the metrics JSON, manifest, tag vocabulary, required/optional fields, reference build, producing DayOA ref, source artifact hashes, and threshold configuration. Avoid customer-visible internal absolute paths.
11. **Make CNV evidence matching robust.** Normalize contig names under an approved reference policy, build an interval index instead of repeatedly scanning every SV, reject missing support files, and make reruns idempotent without duplicated headers/tags.
12. **Validate or replace the ploidy and CN-track heuristics.** Decide whether chromosome-wide idxstats and CNV-record DPS are acceptable evidence. If a continuous CN track is required, use an authoritative windowed/GC-corrected signal rather than emitting only PASS CNV intervals.
13. **Move thresholds into reviewed configuration.** Depth, allele-balance, SOR, clustering, overlap, and breakpoint thresholds should be versioned inputs with documented evidence, not module constants.
14. **Add focused and integration tests.** Include VCF fixtures for multiallelic, multi-sample, missing-field, contig, filter, normal-SMN, high-CN, no-autosomal-baseline, and rerun cases; path-contract tests against DayOA `11.0.15`; a one-sample Kitchen Sink integration test; and partial-output cleanup/failure tests.

### P2 — scope cleanup and maintainability

15. **Separate exploratory classifiers from production packaging.** Mark `analyze_cn_gains.py` and `analyze_longreadsupported.py` as research-only until their labels are validated; require explicit output paths and expose command failures.
16. **Quarantine or remove the four-Coriell wrappers from the production package.** If retained for reproducibility, place them under an examples/experiments area with an explicit data manifest and fix the broken CNV tagger path and `GBA1` naming.
17. **Update all documentation to the current HIOMRS contract.** Replace `sentdhiomr` and `dmd` references, remove the stale TIDDIT/SMN12 gap statements, and use the pinned public gene names and current rule/target names.
18. **Stream large VCF transformations where possible.** Avoid reading entire VCFs into memory and use indexed interval access for evidence lookups, while preserving deterministic ordering.

## Suggested review sequence

1. Product/clinical delivery contract review.
2. DayOA input/output and reference-contract review against the chosen pinned ref.
3. Variant-representation review of SNV tags, CNV support, SMN synthesis, ploidy, and CN track.
4. Operational review of atomicity, provenance, manifest completeness, and failure behavior.
5. Test-plan review followed by implementation only after the preceding contracts are accepted.

## Final assessment

The branch is best treated as a design and prototyping contribution, not a deployable packaging feature. It demonstrates the desired artifact shape and contains reusable ideas, but its path contract predates the DYEC-pinned HIOMRS workflow, its validation is too shallow for delivery assurance, and several transformations make unvalidated biological or VCF-semantic assumptions. The pinned Kitchen Sink already declares most of the necessary source artifacts; the missing work is a rigorous, explicit, tested integration and an approved product contract—not broader file discovery or fallback behavior.
