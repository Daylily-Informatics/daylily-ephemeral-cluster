# Named Rule Resource Tuning Follow-up

Captured from `docs/plans/20260707T144453Z_benchmark_resource_review/` after the 2026-07-08T01:08Z refresh, plus a direct read-only `dyec headnode jobs` / `squeue` / `sinfo` probe on `cmdcat-103-all-20260707`.

## CPU Over-requested Rules

| rule | command evidence | requested CPUs | observed avg cores | over-request | instance evidence | suggestion |
| --- | --- | ---: | ---: | ---: | --- | --- |
| `sent_aln_sort_snv` | `illumina_pangenome_snv` | 128 | 9.9 | 12.9x | `i128nvme-dy-price128nvme-2:i4i.32xlarge` | Trial 32 or 48 CPUs; keep local NVMe TMPDIR. |
| `sentieon_pangenome_ug` | `ultima_pangenome_snv` | 128 | 11.4 | 11.2x | `i384nvme-dy-mem384nvme-1:r8idb.96xlarge` | Trial 32 CPUs; memory also looks high but should be changed separately. |
| `sent_snv_ont` | `ont_snv_alignstats`, kitchensink | 191 | 21.8-22.3 | 8.6-8.8x | `i384nvme-dy-bigmem384nvme-1:r8idb.96xlarge` | Trial 48 CPUs. |
| `sent_snv_pacbio` | `pacbio_snv_alignstats` | 192 | 75.3 | 2.6x | `i384nvme-dy-mem384nvme-1:r8idb.96xlarge` | Trial 96 or 128 CPUs, not below 96 on current evidence. |
| `sentmm2_align_sort` | `pacbio_snv_alignstats` | 192 | 27.0 | 7.1x | `i384nvme-dy-mem384nvme-1:r8idb.96xlarge` | Trial 64 CPUs and recheck sort/minimap split. |

## Memory Over-requested Rules

| rule family | request | observed peak RSS | over-request | suggestion |
| --- | ---: | ---: | ---: | --- |
| `doppelmark_dups` | 512000 MB | 43291-148280 MB | 3.5x-11.8x | Set 192000-256000 MB; 192 GB covers current max with ~30% headroom, 256 GB is safer. |
| `rtg_vcfeval_roi` | 650000 MB | 23923-116983 MB | 5.6x-27.2x | Set 192000-256000 MB; 192 GB is enough on current evidence. |
| `sentdhiomr_stage1` | 128000 MB | 20414-20572 MB | 6.2x-6.3x | Set 48000-64000 MB. |
| `sentdhiomr_stage2` | 64000 MB | 667-679 MB | 94.2x-96.0x | Set 8000-16000 MB if Slurm profile floor allows; otherwise keep floor. |
| `sentdhiomr_stage3` | 128000 MB | 7028-7135 MB | 17.9x-18.2x | Set 32000-50000 MB. |
| `sentdhiomr_pass1` | 128000 MB | 4064-4110 MB | 31.1x-31.5x | Set 32000-50000 MB. |
| `sentdhiomr_pass2` | 128000 MB | 6468-6692 MB | 19.1x-19.8x | Set 32000-50000 MB. |
| `sentdhiomr_model_apply` | 64000 MB | 312-335 MB | 191.0x-204.8x | Set 8000-16000 MB if Slurm profile floor allows; otherwise keep floor. |
| `sentdhiomr_final_norm` | 50000 MB | 45-50 MB | 991x-1116x | Keep only the platform minimum; this is a tiny bcftools/tabix step. |

## BCLConvert Status

- No `run_bclconvert_lane` benchmark files exist yet for either `illumina_bclconvert` or `illumina_run_qc_bclconvert`.
- Live queue has 16 lane jobs pending on `i192hugenvme`, each with 48 CPUs and `500000M`; no lane job has a node assignment.
- Direct `sinfo` probe showed `i192hugenvme-dy-price192hugenvme-1` as `down!`, `0/0/192/192` CPUs, `1494220` MB. `scontrol show job` reason for job 9 was `Nodes_required_for_job_are_DOWN,_DRAINED_or_reserved_for_jobs_in_higher_priority_partitions`; most other lanes showed `Priority`.
- Because there are no completed BCL lane benchmarks, memory cannot be lowered from evidence. For future launches only, DayOA Slurm profile was changed to request/use 96 CPUs per lane while leaving memory at 500000 MB: two lanes per 192-vCPU node then reserve 192 CPUs instead of 96.

## DayOA Changes Made

Changed in `/Users/jmajor/projects/lsmc/daylily-omics-analysis`:

- `config/day_profiles/slurm/templates/rule_config.yaml`: `sentdhiomr.transfer_tmp_parent` now `/scratch`; BCL lane and tile-shard threads now 96 with doubled internal BCL thread split.
- `workflow/rules/sent_hybrid_ilmn_ont_modular.refactored.smk`: `sentdhiomr_sr_markdup`, `sentdhiomr_transfer`, and `sentdhiomr_transfer_merge` now fail if configured scratch is under `/fsx`, require a writable local scratch parent, write heavy temp outputs locally, then copy completed outputs back.
- `workflow/rules/bcftools_vcfstat.smk`, `workflow/rules/expansionhunter.smk`, `workflow/rules/legacy_cram_compat_bam.smk`: write temp work under `/scratch`, then copy finished artifacts to workflow outputs.
- Contract tests updated for the scratch and BCL profile changes.

Validation:

```text
pytest tests/test_sentdhiomr_resource_tuning.py tests/test_ont_fastq_contracts.py tests/test_bclconvert_multiqc.py tests/test_expansionhunter_contracts.py tests/test_multiqc_sample_identifiers.py tests/test_multiqc_qc_targets.py
111 passed in 1.44s
```

No live queued job was cancelled or modified, no Slurm administration was performed, and no AWS resource mutation was performed for this follow-up.
