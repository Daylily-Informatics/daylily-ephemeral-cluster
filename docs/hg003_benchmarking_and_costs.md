# HG003 Benchmarking And 30x SNV Cost Comparison

This document tracks the public-safe HG003 benchmark plan and the 30x short-read SNV-calling comparison table. Values are labeled as:

- **live observed**: measured in the current DYEC/DayOA benchmark ledger
- **vendor reported**: stated by a vendor or official project source
- **AWS-price-estimated**: derived from current AWS Price List API on-demand rates plus an assumed wall time
- **pending live benchmark**: expected output, not measured yet

## Live HG003 5x Benchmark Scope

Target cluster: `dyec5128`

Dataset: HG003 5x Illumina paired FASTQs mounted under the configured reference bucket:

- `HG003_5x_R1.fastq.gz`
- `HG003_5x_R2.fastq.gz`
- GIAB HG003 v4.2.1 truth resources
- `hg38_broad` reference assets

Benchmark arms:

| Arm | Repository | Engine | Command profile | Status |
|---|---|---|---|---|
| DayOA | `daylily-omics-analysis` | Snakemake 7 through `dy-r` | Current DYEC catalog command `illumina_snv_alignstats`, DayOA `2.0.41`, genome `hg38_broad`, `-j 20` | Launched as `dyec5128_hg003_5x_ilmn_snv_20260603T110935Z`; terminal metrics pending |
| nf-core/Sarek | `daylily-sarek` | Nextflow / nf-core Sarek | Current catalog repo ref `0.7.379`; no runnable Sarek analysis command is currently present in the catalog | Pending launch; blocked by active dyec5128 controller/job and missing pinned Nextflow/Java runtime |

Read-only preflight on 2026-06-03 found:

- SSM headnode access works as `ubuntu`.
- `/fsx` had about 6.3 TiB available.
- HG003 5x FASTQs, GIAB truth, `hg38_broad` BED, `/fsx/references`, `/fsx/resources`, `/fsx/analysis_results`, and cached runtime assets were present.
- `tmux`, `squeue`, `sbatch`, `sinfo`, `day-clone`, `aws`, `python3`, `java`, `singularity`, `apptainer`, and `dyec` were present.
- `sacct` binary was present, but Slurm accounting storage was disabled, so accounting queries were unavailable.
- Current catalog validation came from `config/daylily_pipeline_command_catalog.yaml`, not an old plan. `illumina_snv_alignstats` is DayOA `2.0.41` with targets `produce_sent_align`, `produce_dmd_dedup_cram`, `produce_sentd_snv_vcf`, `produce_snv_concordances`, and `produce_alignstats`.
- `dyec samples stage ... --precheck-only` passed for the HG003 5x manifest: `rows checked=1, samples checked=1, source objects checked=20, concordance directories checked=1`.
- `nextflow` was missing from the pinned runtime path checked for the Sarek arm, and the Java 21 path expected beside it was also missing.
- Active DayOA/Snakemake controller processes and Slurm job `21` were present on dyec5128, so benchmark launch remains gated.

Evidence paths:

- `docs/plans/20260603T084759Z_dyec_dayoa_public_docs_benchmark/logs/preflight_dyec5128_hg003_5x_enforced_20260603.stdout_stderr.txt`
- `docs/plans/20260603T084759Z_dyec_dayoa_public_docs_benchmark/logs/preflight_dyec5128_hg003_5x_enforced_20260603.rc`
- `docs/plans/20260603T084759Z_dyec_dayoa_public_docs_benchmark/logs/current_catalog_dyec5128_hg003_20260603.txt`
- `docs/plans/20260603T084759Z_dyec_dayoa_public_docs_benchmark/logs/precheck_dyec5128_illumina_snv_alignstats_20260603.stdout.txt`
- `docs/plans/20260603T084759Z_dyec_dayoa_public_docs_benchmark/logs/launch_dyec5128_hg003_5x_ilmn_snv_20260603T110935Z.stdout.txt`
- `docs/plans/20260603T084759Z_dyec_dayoa_public_docs_benchmark/generated_sample_configs/dyec5128_hg003_5x_ilmn_snv_20260603T110935Z/20260603T110937Z_dfc39a0a_samples_run_receipt.json`
- `docs/plans/20260603T084759Z_dyec_dayoa_public_docs_benchmark/logs/aws_price_list_api_usw2_ondemand_20260603.tsv`

## Expected Measurements

Each arm should record:

- exact repository commit/tag and command line
- workflow engine version
- container/tool versions
- queue, partition, instance type, CPU/GPU resources, and job count
- wall time from launch to terminal success/failure
- FSx usage before and after
- output paths under `/fsx/analysis_results/<executing_entity>/<analysis_id>`
- exported S3 prefix and `fsx_export.yaml`
- SNV/indel concordance metrics from GIAB/RTG or pipeline-native equivalent
- alignstats and MultiQC evidence paths
- ease, complexity, reproducibility, and operator notes

## Public MultiQC Link

No public no-auth HG003 kitchen-sink MultiQC URL is documented here yet. Public docs may include one only after:

```bash
curl -sS -I "https://<public-report-url>" | sed -n '1,20p'
```

returns HTTP 200 without credentials, signed URLs, Basic auth, or internal-only distribution patterns. If no existing URL passes that check, the public link remains blocked.

## 30x SNV-Calling Comparison

Current AWS on-demand rates were captured with the AWS Price List API for Linux/shared tenancy in US West Oregon on 2026-06-03:

| Instance | USD/hour |
|---|---:|
| `c7i.48xlarge` | 8.568 |
| `c7i.24xlarge` | 4.284 |
| `r7i.4xlarge` | 1.0584 |
| `g5.48xlarge` | 16.288 |
| `p4d.24xlarge` | 21.95764 |
| `p5.48xlarge` | 55.04 |

AWS EC2 on-demand pricing is pay-as-you-go without up-front commitment, and AWS bills Linux instances per second with a 60-second minimum. FSx for Lustre pricing is separate; AWS states FSx usage is prorated by the second and billed from average monthly usage. FSx storage, S3 requests/storage, data transfer, software licenses, and operator time are not included unless a row explicitly says so.

| Pipeline / platform | SNV-calling path | Accuracy evidence | Wall time | Compute cost | Complexity | Reproducibility | Notes |
|---|---|---|---|---:|---|---|---|
| DayOA + Sentieon DNAscope | DayOA catalog `illumina_snv_alignstats`: Sentieon alignment/markdup/DNAscope, RTG/GIAB concordance, alignstats | Pending live HG003 metrics; Sentieon reports DNAscope 30x WGS runtime and AWS compute claims | Pending live 5x; 30x vendor reported about 30 min | Vendor reported $1.50 AWS compute; DYEC c7i.48xlarge 30 min estimate is $4.28 before FSx/license | Medium: explicit DYEC + DayOA setup, but one catalog profile | High when catalog pin, references, manifests, and export receipt are preserved | Vendor report: [Sentieon DNAscope Illumina](https://www.sentieon.com/dnascope-illumina/). |
| nf-core/Sarek GATK-style | Nextflow/nf-core Sarek with germline variant calling configuration | Pending live HG003 metrics; nf-core describes Sarek as WGS/targeted germline/somatic variant workflow | Pending live; DRAGEN docs cite BWA-MEM+GATK-HC around 10 hours as a historical CPU baseline | AWS-price-estimated 10h on c7i.48xlarge: $85.68 before FSx | High: samplesheet, Nextflow profile, containers/cache, references, executor tuning | High when Nextflow config, revision, containers, reports, and work directory are preserved | Sources: [nf-core/sarek](https://github.com/nf-core/sarek), [GATK HaplotypeCaller](https://gatk.broadinstitute.org/hc/en-us/articles/360036800611-HaplotypeCaller). |
| NVIDIA Parabricks DeepVariant | `pbrun deepvariant_germline`: BWA MEM, sort, mark duplicates, DeepVariant | NVIDIA documents pipeline composition; Google DeepVariant reports high PrecisionFDA/GIAB accuracy for earlier versions | Vendor-reported accelerated pipelines are sub-hour; Parabricks GATK germline page reports 30x WGS under 25 min on DGX A100 | AWS-price-estimated 25 min on p4d.24xlarge: $9.15; on g5.48xlarge 30 min: $8.14 before FSx/license | Medium: GPU instance, NVIDIA container, license/NGC, references | High with pinned container and command; lower portability without GPU | Sources: [Parabricks pipelines](https://docs.nvidia.com/clara/parabricks/4.2.0/documentation/toolsbycategory/pipelines.html), [Parabricks GATK germline](https://docs.nvidia.com/clara/parabricks/4.2.0/Documentation/ToolDocs/man_germline.html), [DeepVariant blog](https://google.github.io/deepvariant/posts/2020-02-20-looking-through-deepvariants-eyes/). |
| Illumina DRAGEN | DRAGEN Germline / DRAGEN secondary analysis | Illumina reports PrecisionFDA Truth Challenge accuracy around 99.89-99.90% | Vendor reported 34x genome in about 30 min or 40x genome in about 34 min; BaseSpace datasheet says whole human genome about 35 min | Vendor reported BaseSpace DRAGEN apps about $5/genome; hardware/on-instrument/cloud pricing varies | Low for managed/BaseSpace or on-instrument; medium for cloud appliance integration | High within DRAGEN ecosystem; proprietary platform | Sources: [DRAGEN docs](https://help.dragen.illumina.com/), [DRAGEN product page](https://www.illumina.com/products/by-type/informatics-products/dragen-secondary-analysis.html), [BaseSpace DRAGEN datasheet](https://www.illumina.com/content/dam/illumina-marketing/documents/products/datasheets/dragen-on-basespace-970-2019-015.pdf). |
| Open-source GATK/DeepVariant baseline | BWA-MEM/BQSR/MarkDuplicates/HaplotypeCaller or BWA/DeepVariant on CPU | GATK and DeepVariant are standard benchmarkable callers; accuracy depends on versions, model, filtering, and reference | Vendor/literature baseline commonly hours to tens of hours for 30x WGS on CPU | AWS-price-estimated 10-30h on c7i.48xlarge: $85.68-$257.04 before FSx | High: toolchain composition, intervalization, JVM/GPU/CPU tuning, filtering | High if workflow, containers, references, and truth resources are pinned | Good open baseline, but operator burden and wall time are usually higher than accelerated commercial stacks. |

## Source Notes

- AWS EC2 pricing overview: <https://aws.amazon.com/ec2/pricing/>
- AWS FSx for Lustre pricing: <https://aws.amazon.com/fsx/lustre/pricing/>
- AWS FSx for Lustre deployment/storage classes: <https://docs.aws.amazon.com/fsx/latest/LustreGuide/using-fsx-lustre.html>
- nf-core/Sarek repository and citations: <https://github.com/nf-core/sarek>
- GATK HaplotypeCaller docs: <https://gatk.broadinstitute.org/hc/en-us/articles/360036800611-HaplotypeCaller>
- NVIDIA Parabricks pipeline docs: <https://docs.nvidia.com/clara/parabricks/4.2.0/documentation/toolsbycategory/pipelines.html>
- NVIDIA Parabricks GATK germline docs: <https://docs.nvidia.com/clara/parabricks/4.2.0/Documentation/ToolDocs/man_germline.html>
- DeepVariant blog: <https://google.github.io/deepvariant/posts/2020-02-20-looking-through-deepvariants-eyes/>
- Illumina DRAGEN docs: <https://help.dragen.illumina.com/>
- Illumina DRAGEN product page: <https://www.illumina.com/products/by-type/informatics-products/dragen-secondary-analysis.html>
- Illumina DRAGEN BaseSpace datasheet: <https://www.illumina.com/content/dam/illumina-marketing/documents/products/datasheets/dragen-on-basespace-970-2019-015.pdf>
- Sentieon DNAscope Illumina page: <https://www.sentieon.com/dnascope-illumina/>
