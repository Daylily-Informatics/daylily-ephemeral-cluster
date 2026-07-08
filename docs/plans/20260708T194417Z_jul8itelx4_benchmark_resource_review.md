# jul8itelx4 Benchmark Resource Review

Snapshot time: `2026-07-08T19:47:42Z`.

Scope: current `jul8itelx4` 15-command catalog run only.

Evidence artifacts:

- `docs/plans/20260708T194417Z_jul8itelx4_benchmark_resource_review/benchmark_resource_top.tsv`
- `docs/plans/20260708T194417Z_jul8itelx4_benchmark_resource_review/bounded_remote_output.txt`

Rows reviewed:

- Benchmark rows found: 451
- Rows matched to Snakemake resource blocks: 445
- Benchmark paths included `results/day/*/benchmarks/*.bench.tsv`, `results/day/*/*/benchmarks/*.bench.tsv`, and `logs/benchmarks/*.bench.tsv`.

## Conclusion

Yes, the benchmark evidence supports the concern: CPU packing is being suppressed by inflated memory requests for multiple rules. With Slurm configured as `CR_CPU_MEMORY`, those memory requests are hard placement constraints.

On the current `i7i.48xlarge` Slurm node shape, the schedulable envelope is approximately:

- CPUs: 192
- Memory: 356000 MB

Several rules request enough memory that Slurm can place only 0-7 jobs by memory even though CPU capacity would allow many more jobs. The most obvious example is `vep_chromosome`: it requests 128000 MB and 8 CPUs, but completed benchmarks show only about 1.7 GB p95 RSS and 2.5 GB max RSS. On the i7i node, that request permits only 2 VEP jobs by memory, using 16/192 CPUs.

## Highest Impact Over-Requests

| Rule | n | Req Mem MB | CPUs | p95 RSS MB | Max RSS MB | Max Mem Util | i7i Jobs By Mem | i7i Jobs By CPU | CPU Fill By Mem | Bench-Derived Mem |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `rtg_vcfeval_roi` | 30 | 650000 | 16 | 45196 | 113382 | 17.4% | 0 | 12 | 0.0% | 136058 |
| `sentieon_bwa_sort` | 4 | 350000 | 96 | 110342 | 110344 | 31.5% | 1 | 2 | 50.0% | 165513 |
| `sentdhiomr_call_svs` | 3 | 300000 | 96 | 8065 | 8085 | 2.7% | 1 | 2 | 50.0% | 12097 |
| `sentdhiomr_sr_align` | 3 | 300000 | 96 | 111795 | 112482 | 37.5% | 1 | 2 | 50.0% | 167692 |
| `parse_vcfeval_summary_roi` | 30 | 128000 | 16 | 60 | 61 | 0.05% | 2 | 12 | 16.7% | 4000 |
| `sentdhiomr_pass1` | 37 | 128000 | 48 | 3872 | 4088 | 3.2% | 2 | 4 | 50.0% | 5809 |
| `sentdhiomr_stage1` | 3 | 128000 | 48 | 19964 | 20003 | 15.6% | 2 | 4 | 50.0% | 29946 |
| `vep_chromosome` | 32 | 128000 | 8 | 1743 | 2503 | 2.0% | 2 | 24 | 8.3% | 4000 |
| `sentdhiomr_mapq0_bed` | 46 | 64000 | 32 | 2050 | 2065 | 3.2% | 5 | 6 | 83.3% | 4000 |
| `sentdhiomr_mapq0_slop` | 23 | 50000 | 2 | 21 | 21 | 0.04% | 7 | 96 | 7.3% | 4000 |
| `sentdhiomr_hybrid_select` | 18 | 50000 | 4 | 194 | 197 | 0.4% | 7 | 48 | 14.6% | 4000 |
| `vep_chromosome_input` | 50 | 50000 | 1 | 76 | 76 | 0.15% | 7 | 192 | 3.6% | 4000 |

`Bench-Derived Mem` is a rough sizing value from the observed completed benchmark rows: `max(p95 RSS * 1.5, max RSS * 1.2, 4000 MB)`. It is not a final recommendation by itself; it is a triage value showing how far the current request is from observed usage.

## What This Means For i7i Packing

The `i7i.48xlarge` looked lightly loaded by CPU because memory requests consumed the schedulable memory budget.

Examples:

- `vep_chromosome`: 8 CPUs, 128 GB requested. Slurm can fit only 2 per i7i by memory, so only 16 CPUs are used even though CPU capacity would allow 24 jobs.
- `sentdhiomr_mapq0_slop`: 2 CPUs, 50 GB requested. Slurm can fit only 7 jobs by memory, so only 14 CPUs are used even though CPU capacity would allow 96 jobs.
- `sentdhiomr_pass1`: 48 CPUs, 128 GB requested. Slurm can fit only 2 jobs by memory, so 96 CPUs are used even though CPU capacity would allow 4 jobs.
- `sentieon_bwa_sort`: 96 CPUs, 350 GB requested. Slurm can fit only 1 job by memory; benchmarked RSS suggests two jobs may be possible with a request closer to 160-170 GB.

## Important Caveats

- This review uses completed benchmark files only. Running or pending jobs without benchmark output are not included yet.
- Snakemake benchmark `max_rss` is the available evidence, but for wrapper-heavy rules it should be treated as an operational measurement, not a formal peak-memory proof across all inputs.
- The current data are slim-control runs. Full-depth production inputs may need larger safety margins.
- Some whole-node-style rules request 191-192 CPUs. For those, memory over-request may still exist, but it does not explain low CPU packing because CPU already limits to one job per 192-core node.

## Operational Recommendation

Do not treat this as evidence that the hardware is wrong. The scheduler is behaving according to requested resources. The resource requests are the problem.

The highest-yield fix is to lower per-rule memory requests for the over-requested rules, especially:

- `vep_chromosome`
- `vep_chromosome_input`
- `sentdhiomr_mapq0_slop`
- `sentdhiomr_hybrid_select`
- `sentdhiomr_pass1`
- `sentdhiomr_stage1`
- `sentdhiomr_call_svs`
- `rtg_vcfeval_roi`
- 100 GB one-thread/reporting/glue rules such as `compile_seqfu`, `stage_supporting_data`, `workflow_staging`, `relatedness_batch_*`, and `produce_*`

Global memory scheduling disablement would increase CPU packing immediately, but it would also remove Slurm's protection against genuine high-memory collisions. The benchmark evidence points to resource-profile correction as the cleaner fix.
