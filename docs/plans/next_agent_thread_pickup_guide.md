# Next-agent pickup guide: Take61 and Sentieon follow-up

Last assembled: 2026-07-31

This document is the handoff source of truth for the next Codex task. It does
not claim that Take61, the Sentieon issue, or the Sentieon pull request is
complete. The required order is:

1. Complete Take61 through the final MultiQC report and analytical Inflection
   packages.
2. Export the complete Take61 analysis root from FSx to the established S3
   delivery location and notify Mike Kennemer with verified evidence.
3. Finish the controlled Sentieon comparison.
4. File the Sentieon hard-VCF-versus-gVCF investigation issue if its gates pass.
5. Open the upstream `hybrid_anno.py` performance PR if its independent gates
   pass.

There is no recurring or scheduled monitor for this work. The previous monitor
was deleted at the user's request. Existing Slurm jobs, if still present, run
independently and must be refreshed read-only by the next agent.

## Non-negotiable operating boundaries

- Read `/Users/jmajor/.codex/AGENTS-HOW-TO-RUN-DAYOA.md`, this repository's
  `AGENTS.md`, and the controlling ledgers before acting.
- Never invoke `snakemake` directly. Use `dy-r` from an initialized DayOA shell.
- Run DayOA commands as `ubuntu` in one persistent, meaningfully named `tmux`
  session with an interactive `bash -il` shell. Send `source dyoainit`, `dy-a`,
  and `dy-r` as separate commands.
- Before writing beneath `/fsx/analysis_results/**`, record a write visit and
  acquire that analysis root's write lock. Do not silently take over another
  owner's lock.
- Do not cancel, requeue, reprioritize, or otherwise manipulate Slurm jobs
  without explicit approval for that exact action. Monitoring is read-only.
- Preserve existing results, manifests, receipts, logs, ledgers, untracked
  analysis files, failed attempts, and the old Take61 tmux session. Never run
  `git clean`, destructive reset commands, or recreate the Take61 root.
- Do not add fallback paths or guess an S3 destination. Missing authority,
  destination, or provenance is a blocker to report, not permission to invent
  an alternative.
- Keep the invalid Sentieon Slurm 1768 lane excluded. Do not transform the raw
  gVCF or substitute another input.
- Do not merge, tag, release, or modify DayOA/HIOMR2 as part of the Sentieon
  issue/PR work.

## Part 1: Complete Take61 first

### Frozen Take61 state

| Item | Current evidence |
|---|---|
| Analysis root | `/fsx/analysis_results/preval-hiomr2/take61` |
| DayOA checkout | `/fsx/analysis_results/preval-hiomr2/take61/daylily-omics-analysis` |
| Existing checkout state | Detached clean tracked tree at DayOA `13.0.106`, commit `0863d3604cde5608ac64e02cf27e6140bec543cc` |
| Required recovery version | Annotated DayOA tag `13.0.109`, tag object `a7c795a4c321f423c7239ec7d368bc8c4fc04658`, peeled commit `86c62c651ce40e40debf9922d0cb1f4ea46cc625` |
| Peddy fix ancestry | `13.0.109^{}` contains the DayOA `13.0.108` Peddy fix commit `364cee5f7f42d24b0c804455ec91703e9994bdca` |
| Existing tmux | `take61_hiomr2_4sample_13106_20260731`; one window/pane, controller exited at its prompt; retain as evidence |
| Last controller result | RC 1 after 597 of 610 jobs, approximately 98% complete |
| Last queue/controller check | No active Take61 Slurm jobs and no active Take61 `dy-r`/Snakemake controller |
| Last lock check | Take61 analysis root was unlocked |
| Original log | `.snakemake/log/2026-07-31T064926.247752.snakemake.log` |
| Controlling Take61 ledger | `docs/plans/20260731T054202Z_take61_hiomr2_four_sample_launch_ledger.md` inside the Take61 checkout |

The existing checkout has many intentional untracked analysis inputs and
evidence files. Important examples are:

- `config/analysis_unit_inputs.tsv`
- `config/analysis_units.tsv`
- `config/sequencing_inputs.tsv`
- `config/hiomr2_take61_hg002_hg004_na19235_na20775_fullcov.yaml`
- `docs/plans/20260731T054202Z_take61_hiomr2_four_sample_launch_ledger.md`
- identity/manifest receipts and workflow graph PDF/MMD files

These are analysis state, not debris. They must survive the version update.

### Samples and frozen input contract

The four analysis units are:

- `HG002-6bx3870t8tycca`
- `HG004-c8579mk548sp9e`
- `NA19235-4wwp4b2fc95a45`
- `NA20775-tp5b0yt8c3vqn9`

The run uses full-coverage ILMN data and ONT FASTQs restricted to the `[0,25)`
hour window on `hg38`. Do not change identities, samples, manifests, scope, or
input selection during recovery.

### Why Take61 stopped

The failure is the Peddy output-name contract in DayOA `13.0.106`, not an
alignment or upstream HIOMR2 failure. The old rule supplied a prefix ending in
`peddy.` and expected `...peddy.ped`, while Peddy 0.4.8 emitted the native
`...peddy.peddy.ped` name. At least the HG004 Slurm 2231 and NA19235 Slurm 2319
Peddy jobs failed at the old rule's expected-output loop.

DayOA `13.0.109` contains the merged fix aligning the expected native filename,
fallback writer, and MultiQC staging. Recovery must therefore rerun the failed
Peddy/downstream closure without restarting completed SR or LR alignments.

### Exact recovery sequence

1. From the local Mac, enter the DYEC environment and connect to the existing
   headnode as `ubuntu`:

   ```bash
   cd /Users/jmajor/projects/lsmc/daylily-ephemeral-cluster
   source ./activate
   dyec headnode connect --profile lsmc --region us-west-2 --cluster preval-hiomr2
   ```

2. On the headnode, create a new persistent one-pane tmux session named:

   ```text
   take61_hiomr2_4sample_13109_20260731
   ```

   Use an interactive `bash -il` shell. Do not reuse or remove the old
   `take61_hiomr2_4sample_13106_20260731` session.

3. In the new pane, set the stable execution identity:

   ```bash
   export DAYOA_AGENT_ID=codex-take61-recovery-20260731
   export DAYOA_AGENT_KIND=codex
   export DAYOA_HUMAN_REQUESTOR=jmajor
   export DAYOA_TMUX_SESSION=take61_hiomr2_4sample_13109_20260731
   export DAYOA_LEDGER_PATH=/fsx/analysis_results/preval-hiomr2/take61/daylily-omics-analysis/docs/plans/20260731T054202Z_take61_hiomr2_four_sample_launch_ledger.md
   ```

4. Refresh the read-only state. Prove there is no live Take61 controller or
   Take61 Slurm work and inspect the lock. If the root is now owned by another
   agent, stop and follow the documented takeover/approval flow; do not spoof
   its identity.

5. Record the write visit and acquire the Take61 lock:

   ```bash
   dyec analysis visit \
     --analysis-root /fsx/analysis_results/preval-hiomr2/take61 \
     --mode write \
     --intent "Resume Take61 on exact DayOA 13.0.109 after Peddy output-contract fix"

   dyec analysis lock acquire \
     --analysis-root /fsx/analysis_results/preval-hiomr2/take61 \
     --operation write \
     --intent "Resume Take61 on exact DayOA 13.0.109"
   ```

6. Update only the tracked DayOA source to the exact tag while preserving all
   untracked analysis state:

   ```bash
   cd /fsx/analysis_results/preval-hiomr2/take61/daylily-omics-analysis
   git status --short --branch
   git diff --quiet
   git diff --cached --quiet
   git fetch origin --prune --tags
   git cat-file -t 13.0.109
   git rev-parse 13.0.109^{}
   git switch --detach 13.0.109
   git describe --tags --exact-match HEAD
   git status --short --branch
   ```

   Required results are `tag`, commit
   `86c62c651ce40e40debf9922d0cb1f4ea46cc625`, and exact tag `13.0.109`.
   Tracked modifications must be absent. The intentional untracked config,
   ledger, receipts, and graphs must still be present. This is recovery of an
   existing analysis checkout; do not run `day-clone` over Take61.

7. Initialize DayOA in the same tmux pane with each command sent separately:

   ```bash
   cd /fsx/analysis_results/preval-hiomr2/take61/daylily-omics-analysis
   source dyoainit
   export DAY_PROJECT=RnD
   export DAYLILY_COST_CENTER=RnD
   dy-a slurm hg38
   ```

8. Run the exact dry-run command below. The only difference from the intended
   live command is the final `-n`:

   ```bash
   dy-r produce_sentdhiomr2_kitchensink \
     produce_sentdhiomr2_inflection_analytical_package \
     -p -k -j 300 -T 0 --rerun-triggers mtime --rerun-incomplete \
     --configfile config/hiomr2_take61_hg002_hg004_na19235_na20775_fullcov.yaml \
     --config genome_build=hg38 \
       aligners=["sentmm2ont"] dedupers=["na"] \
       snv_callers=["sentdhiomr2"] sv_callers=["tiddit"] \
       htd_callers=["smn12"] \
       use_fq_data_starting_hrs=0 use_fq_data_up_to_hrs=25 \
       seqone_delivery_batch_id=take61 \
       hiomr2_inflection_package_mode=analytical \
     -n
   ```

9. Inspect the dry-run before spending. It must:

   - plan the failed Peddy jobs and their downstream MultiQC/package closure;
   - retain all four frozen analysis units and the same manifests;
   - not plan completed `sentdhiomr2_sr_prepare` alignment work;
   - not plan completed `sentdhiomr2_lr_prepare_fastq` alignment work; and
   - not introduce unrelated targets or a broader analysis scope.

   If either alignment lane is planned, stop and diagnose the mtime/provenance
   cause. Do not launch live merely because the DAG renders.

10. If the dry-run satisfies the gate, execute the byte-identical command with
    only `-n` removed. Leave the tmux session alive after the command exits.

11. Monitor controller logs, `squeue`/`sacct`, rule logs, and declared outputs
    read-only. Do not manually manage workflow jobs. Record new job IDs, failures,
    controller RC, and evidence in the existing Take61 ledger.

### Take61 completion gate

Do not call Take61 complete until all of these are true:

- `dy-r` returns RC 0.
- All four sample closures are complete.
- Peddy native outputs and their MultiQC staging complete for every required
  sample.
- `results/day/hg38/reports/DAY_final_multiqc.html` exists and is readable.
- The corresponding MultiQC data directory exists and includes the expected
  HIOMR2/QC sections without SR/LR sample-name collisions.
- The requested analytical Inflection package closure exists for all four
  samples, with its manifests, indexes, evidence, and artifact receipts.
- The benchmark collector has run from the initialized headnode shell:

  ```bash
  bash bin/util/benchmarks/collect_day_benchmark_data.sh hg38
  ```

- `results/day/hg38/reports/benchmarks_summary.tsv` is present and coherent.
- The Take61 ledger records terminal evidence and exact output paths.

### Take61 FSx-to-S3 export and Mike handoff

Export the entire analysis root, not only selected result files:

```text
/fsx/analysis_results/preval-hiomr2/take61/
```

The exact established S3 destination was not frozen in the prior thread. The
next agent must resolve it from the current DYEC export documentation and prior
verified `for_mk`/Mike export receipts. Do not guess a `derive/for_mk` spelling
or use a new prefix. A previous raw headnode-role attempt against
`lsmc-dayoa-analysis-results-usw2` received `AccessDenied`, so use the supported
DYEC FSx export path and established export authority.

Required export evidence:

- exact source root and destination S3 URI;
- export command/receipt and RC 0;
- durable object count and total bytes;
- checksum or exporter-integrity evidence;
- proof the final MultiQC report, its data directory, all analytical packages,
  ledgers, and manifests are present at the destination; and
- no local FSx deletion.

Only after verification, notify Mike Kennemer through the connected Slack
workflow. Resolve Mike's actual Slack identity rather than sending to a bare
`@Mike`. Include the exact S3 URI, completion status, four sample IDs, DayOA
`13.0.109`, report/package locations, and export receipt. Record the resulting
Slack message permalink or timestamp in the Take61 ledger. Release the Take61
write lock only after the ledger and export evidence are durable.

## Part 2: Sentieon hard-VCF-versus-gVCF investigation

### Controlling source and frozen evidence

- Repository:
  `/Users/jmajor/projects/cli_refactor/sentieon-cli-hybrid-anno-v1.7.0`
- Branch: `codex/hybrid-anno-opt2-v1.7.0`
- Current local HEAD: `e323d5e`
- Fork: `https://github.com/iamh2o/sentieon-cli.git`
- Upstream: `https://github.com/Sentieon/sentieon-cli.git`
- Controlling ledger:
  `/Users/jmajor/projects/cli_refactor/sentieon-cli-hybrid-anno-v1.7.0/docs/plans/20260731T090232Z_hg003_cli_hard_vs_gvcf_issue_and_hybrid_anno_pr_ledger.md`
- The ledger currently has an intentional uncommitted evidence update. Preserve
  and review it; do not discard or overwrite it.
- Take49 root:
  `/fsx/analysis_results/preval-hiomr2/take49/daylily-omics-analysis`
- Evidence root:
  `/fsx/analysis_results/preval-hiomr2/take49/daylily-omics-analysis/manual/sentieon-cli-issue-evidence/HG003-4xvrg7erk7knfs/20260731T090232Z`
- Frozen exact product paths are recorded in
  `provenance/frozen-paths.txt` under that evidence root. Use those paths rather
  than rediscovering or substituting products.
- Evidence branch commit used by the live optimized control:
  `c7d9fd4ebad013ebc76052578e967f28d2e065e9`.

Before any Take49 write, inspect its current lock. It was last recorded as owned
by `codex-hg003-sentieon-issue-pr-20260731`. A new task must not silently reuse
that identity or bypass the lock. If it remains owned, use the documented lock
takeover request and obtain the required explicit approval, or have the existing
owner release it.

### Valid and excluded full-coverage lanes

Use only:

- raw forked CLI 1.7.0 gVCF: Slurm 1769;
- native forked CLI 1.7.0 hard VCF: Slurm 1767;
- native-hard RTG lane: Slurm 1770; and
- completed DayOA GVCFtyper-derived hard-VCF RTG result.

Slurm 1768 is invalid because it used the wrong truth source. Keep it excluded
from every metric, table, bundle, URL, and public statement.

### Evidence already complete

The following full-coverage work is durable under the evidence root:

- corrected inventory/comparison jobs 2127 and 2128 completed RC 0;
- provenance jobs 2142 and 2143 completed RC 0;
- exact stored headers and raw, semantic, command, and volatile header diffs;
- raw and reference-normalized full hard-VCF symmetric differences;
- augmented difference classification tables;
- directional TP-call, TP-baseline, FP, and FN tables;
- checksums, command/resource provenance, receipts, and a compressed evidence
  bundle named `HG003-fullcov-sentieon-hard-vs-gvcf-evidence.tar.gz`;
- all requested net deltas reconcile to the directional sets.

Frozen RTG results are:

| Output | TP call | TP baseline | FP | FN | F-score |
|---|---:|---:|---:|---:|---:|
| Raw CLI gVCF | 3,825,826 | 3,825,851 | 2,576 | 6,064 | 0.99887211 |
| GVCFtyper hard VCF from that gVCF | 3,825,826 | 3,825,851 | 2,576 | 6,064 | 0.99887211 |
| Native CLI hard VCF | 3,825,866 | 3,825,889 | 2,549 | 6,026 | 0.99888060 |

Native minus gVCF-derived is therefore `+40` TP-call, `+38` TP-baseline,
`-27` FP, and `-38` FN.

Directional evidence is larger than the net delta and must be reported:

- TP-call: 309 derived-only and 367 native-only records, including 341
  genotype differences;
- TP-baseline: 251 derived-only and 278 native-only records;
- FP: 144 derived-only and 117 native-only records, including two genotype
  differences; and
- FN: 278 derived-only and 251 native-only records.

Full normalized hard-VCF evidence includes 1,312,487 native-only and 3,969
derived-only records, 12,381 ModelApply-filter differences, 15,211 genotype
differences, and 5,087,236 annotation/quality differences. The native hard VCF
has 5,029,158 unfiltered and 1,301,661 `MLrejected` records. The derived hard
VCF has 5,026,771 unfiltered records and no `MLrejected` filter.

### Controlled 5x reproduction still required

The public issue is gated on a clean four-lane HG003 5x control. The last
verified Slurm snapshot was:

| Job | Lane | Last state |
|---|---|---|
| 2060 | untouched upstream 1.7.0 native hard | COMPLETED, RC 0, 1:05:51 |
| 2061 | untouched upstream 1.7.0 gVCF plus GVCFtyper | RUNNING, 2:16:19 |
| 2062 | optimized fork native hard | COMPLETED, RC 0, 0:52:26 |
| 2063 | optimized fork gVCF plus GVCFtyper | RUNNING, 2:16:19 |
| 2121 | semantic/RTG comparison | PENDING on 2061/2063 |
| 2129 | finalization/evidence receipt | PENDING on 2121 |

This is a staleable handoff snapshot. Refresh all six jobs with `sacct`/`squeue`
before drawing conclusions. Monitor only. Do not cancel, requeue, transform an
output, or substitute a lane.

When 2129 reaches a terminal state, inspect the produced receipts and prove:

1. untouched upstream 1.7.0 reproduces the native-hard-versus-gVCF-derived
   construction difference;
2. upstream and optimized native-hard outputs are semantically identical;
3. upstream and optimized gVCF outputs and their identically generated hard
   VCFs are semantically identical;
4. matched-mode RTG summaries are identical;
5. samples, ordering, variants, genotypes, filters, INFO including `LHC`, and
   representative tabix queries are identical; and
6. the fresh 128-thread annotation measurement shows at least 90% wall-time
   improvement with CPU, memory, record count, command, and commit provenance.

If a comparison or performance gate fails, preserve the evidence and mark the
corresponding ledger rows `FAIL` or `BLOCKED`. Do not file a misleading issue or
PR.

### S3 work remaining before the issue

Target private prefix:

```text
s3://lsmc-dayoa-analysis-results-usw2/validation/sentieon-cli/hg003-fullcov-hard-vs-gvcf-20260731/
```

The prior headnode role could not list or inspect this bucket. Use a supported,
authorized export surface. Upload and verify:

- the raw full-coverage CLI gVCF and index;
- the DayOA GVCFtyper-derived hard VCF and index;
- the native CLI hard VCF and index;
- RTG summaries and category VCFs;
- exact/semantic header reports;
- complete compressed variant-delta tables;
- sanitized command and resource provenance;
- README, SHA-256 manifest, and compressed evidence bundle.

Do not export reads, alignments, references, models, license material,
credentials, or retained CLI scratch trees. Keep public ACLs disabled. Verify
each object's size and checksum metadata, then generate seven-day presigned URLs
immediately before filing. Record the exact UTC expiration.

### Issue creation gate and required content

No public issue had been filed at the last check. File only after the untouched
upstream control reproduces the mode distinction and the evidence upload is
verified.

Repository: `Sentieon/sentieon-cli`

Title:

```text
Investigation: dnascope-hybrid native hard VCF differs from gVCF → GVCFtyper hard VCF in CLI 1.7.0
```

Frame it as a request for clarification, not a confirmed Sentieon defect. It
must contain:

- the three-way RTG metrics and directional counts above;
- the distinct command/construction paths and semantic header differences;
- exact upstream CLI, Sentieon Genomics, reference, model, dbSNP, population
  VCF, input, scope, thread, and command provenance;
- summarized difference classifications with links to complete tables;
- proof raw gVCF and its GVCFtyper hard VCF are RTG-identical;
- proof the optimized annotator is not responsible for the distinction;
- seven-day presigned URLs with UTC expiration; and
- a direct question asking whether the filtering difference is intentional and
  which documented conversion, if any, reproduces native-hard behavior from a
  hybrid gVCF.

After filing, record the issue URL, time, URL expiration, and evidence manifest
hash in the controlling ledger.

## Part 3: Sentieon CLI 1.7.0 `hybrid_anno.py` PR

### PR work already complete

- Clean worktree:
  `/Users/jmajor/projects/cli_refactor/sentieon-cli-hybrid-anno-pr-v1.7.0`
- Local branch: `codex/hybrid-anno-performance-v1.7.0`
- Commit: `bf150c3` (`perf: speed up hybrid annotation with BGZF sharding`)
- Exact upstream base: `1bf377d3ce79fc4d8c2dc221e1f696441e38349d`
- Intended fork destination: `iamh2o/sentieon-cli`
- The branch was not pushed at the last check and no upstream PR existed.
- The PR diff contains exactly:
  - `.github/workflows/ci.yml`
  - `sentieon_cli/scripts/hybrid_anno.py`
  - `tests/unit/test_hybrid_anno.py`
- Optimized script SHA-256:
  `887d281dcf9aba7513d268790fdd601cf7b4a904103226624fdd5403e2574f7e`
- Existing checks in the pinned `sentieon-cli-1.7.0-opt2` environment:
  - focused tests: 12 passed;
  - full suite: 137 passed;
  - doctests: 137 passed;
  - configured Flake8: RC 0;
  - Black check: RC 0; and
  - mypy: RC 0.
- Existing full-data performance evidence is 98.0-98.3% faster for hard VCF
  annotation and 94.4-94.9% faster for gVCF annotation.

Do not add internal ledgers, DayOA environment YAMLs, LSMC paths, cluster
scripts, benchmark scratch, or hard-versus-gVCF semantic changes to this branch.

### Evidence still needed to open the PR

| Requirement | State | Required terminal evidence |
|---|---|---|
| Clean upstream-based three-file patch | Complete | Reverify commit/diff before push |
| Unit/full/doctest/style/type checks | Complete | Preserve exact commands and RCs |
| Prior full-data speedup | Complete | Include 128/192-thread wall times and percentages |
| Fresh upstream-vs-optimized native-hard equivalence | Pending control | Semantic equality and identical RTG summary from 2060/2062 comparison |
| Fresh upstream-vs-optimized gVCF equivalence | Pending control | Semantic equality, identical GVCFtyper hard result, and identical RTG summary from 2061/2063/2121 |
| Fresh 128-thread performance result | Pending control | At least 90% annotation wall-time reduction with command/CPU/memory/record provenance |
| Investigation issue link | Pending issue | Link the filed issue and state this PR does not change those semantics |
| Fork branch and upstream PR | Not done | Push branch, open ready-for-review PR, record URL and CI state |

If all gates pass:

1. Reverify the clean worktree, exact base, three-file diff, commit, and script
   hash.
2. Push `codex/hybrid-anno-performance-v1.7.0` to
   `iamh2o/sentieon-cli` without force-pushing.
3. Open a ready-for-review PR against `Sentieon/sentieon-cli:main` titled:

   ```text
   Speed up hybrid_anno.py with raw BGZF sharding
   ```

4. Include:
   - unchanged public CLI contract;
   - implementation summary;
   - exact tests and check results;
   - upstream-versus-optimized semantic and RTG equivalence;
   - existing full-data 128/192-thread benchmarks;
   - fresh controlled 128-thread benchmark;
   - exact base/implementation commits and script hash; and
   - the investigation issue link with an explicit statement that this PR does
     not attempt to change native-hard versus gVCF-derived semantics.
5. Observe and record upstream CI. Address only review/CI issues within the
   three-file PR scope.

Do not merge the PR, create a Sentieon tag/release, or modify DayOA/HIOMR2.

## Final closeout checklist

The next task is complete only when the relevant ledgers record concrete
terminal evidence for all of the following:

- Take61 DayOA source is exact annotated `13.0.109` and preserved the original
  analysis manifests/results.
- Take61 recovery dry-run did not rerun completed SR/LR alignments.
- Take61 live controller returned RC 0.
- Final MultiQC report/data and all four analytical Inflection packages are
  complete.
- The complete Take61 root is verified at the established S3 destination and
  Mike Kennemer has received the verified location.
- The four controlled Sentieon lanes and comparison/finalization jobs have
  terminal evidence.
- The full-coverage evidence is privately uploaded, verified, and represented
  by seven-day URLs.
- The Sentieon investigation issue URL is recorded, or its failed gate is
  explicitly marked `BLOCKED`.
- The `hybrid_anno.py` PR URL and CI state are recorded, or its failed gate is
  explicitly marked `BLOCKED`.
- The Take49 and Take61 analysis-root locks are released only after their
  durable ledger/evidence updates are complete.

Report exact paths, job IDs, RCs, TP/FP/FN/F-score values, commit SHAs, issue/PR
URLs, S3 prefix, URL expiration, package locations, export receipt, and any
remaining blocker. Never turn an unfinished gate into a success by omitting it.
