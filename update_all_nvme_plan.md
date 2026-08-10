# Catalog-wide NVMe scratch artifact overhaul

## Summary

Migrate every BAM, CRAM, VCF, gVCF, and `.g.vcf` producer reachable from the 27 active DayOA command-catalog commands to a strict NVMe/scratch contract. Freeze the running Take8 lane; validate the overhaul only from a new explicit-tag clone.

The current Snakemake 7.25 implementation cannot safely use one rule with both a node-local scratch output and its FSx final output. The safe contract is: compute to declared `temp()` scratch artifacts, consume them within one connected group, then use a terminal publisher rule in that group to atomically create FSx artifacts.

## Two-agent ledger

Create the controlling ledger in DayOA `docs/plans/` and a linked DYEC pin/release row. Each row records command, target, concrete producer rule, artifact class, scratch path, group boundary, NVMe partition, dry-run result, live proof, and release commit.

| Agent | Model / effort | Ownership |
|---|---|---|
| 1 | `gpt-5.6-sol` / high | Build the exhaustive 27-command reachability inventory from exact catalog dry-runs, target aliases, artifact manifests, declared outputs, and shell/script-created sequence artifacts. Own catalog parity and producer classification. |
| 2 | `gpt-5.6-sol` / xhigh | Build the reusable scratch/group contract; migrate Jasmine first, then all inventoried producer families; own grouping correctness, publication boundaries, and failure/retry tests. |

## Implementation changes

- Treat the source and packaged command catalogs as one contract. Dry-run every active catalog row and classify every reachable sequence artifact as:
  - durable FSx terminal;
  - grouped scratch intermediate;
  - same-rule tool temporary;
  - package-materialized artifact;
  - external/pass-through input, which is recorded but not rewritten.

- Add one strict scratch-artifact helper that produces deterministic, collision-proof paths:
  - `/scratch/dayoa/<pipeline>/<analysis-root-sha256>/<rule>/<identity>/<filetag>`;
  - identity includes every concurrent discriminator: analysis unit, aligner/deduper, caller, shard, role, and basename as applicable;
  - reject non-`/scratch` roots, symlinks, non-NVMe mounts, insufficient space/inodes, unsafe tokens, and `/dev/shm` fallback.

- Change Jasmine paths to:
  - per-sample: `/scratch/dayoa/sentdhiomr2/<analysis-hash>/jasmine_<AU>/<stage>/`;
  - shared reference: `jasmine_reference`;
  - cohort: `jasmine_cohort`.
  This preserves the current analysis-root namespace while making two AUs on one 384-vCPU node visibly and physically separate.

- For every in-scope producer, declare scratch artifacts as `temp()` outputs and set all relevant internal temp variables beneath that same rule-specific scratch root: `TMPDIR`, `TMP`, `TEMP`, `TEMPDIR`, `APPTAINER_TMPDIR`/`APPTAINER_HOME`, and `SENTIEON_TMPDIR` where applicable. Inputs remain on FSx; no input staging or copying into scratch.

- Replace current manual “delete claimed scratch root on shell exit” behavior where it would remove declared scratch outputs. Snakemake owns declared artifact cleanup; terminal publishers may only remove non-declared tool-private directories after successful publication.

- Use an explicit terminal publisher rule for each linear compute chain. It consumes only group-internal scratch artifacts and atomically publishes validated, nonempty FSx products with the existing hidden-sibling/fsync/replace pattern. Logs and benchmarks continue to write directly to FSx.

- Group only connected, serial, per-analysis-unit/per-caller/per-shard chains. Do not group cross-sample or cohort fan-ins, and retain no `group-components` override.
  - For parallel sharded callers, each shard group publishes a temporary FSx shard endpoint.
  - A separate NVMe gather reads those FSx shards and publishes the single durable merged VCF/gVCF.
  - This preserves parallelism; a zero-FSx-until-merged design would require all shards in one oversized allocation on Snakemake 7.25.

- Require NVMe-only partitions for every migrated rule and verify the rendered group allocation rather than assuming member-rule resources. Grouped serial layers must request the maximum required CPU/memory/time layer, not an accidental sum of independent shard jobs.

## Test and release plan

- Add static contract tests for path uniqueness across analysis roots, AUs, callers, shards, and same-node concurrency; Jasmine must specifically render `jasmine_<AU>` roots.
- Add negative tests for unsafe paths, missing identity discriminators, `/dev/shm` fallback, non-NVMe partitions, undeclared scratch outputs, direct FSx compute outputs, partial publication, stale owner metadata, retry, and spot-loss rerun behavior.
- Add group-DAG tests proving scratch artifacts never cross a group boundary; shard components remain independent; terminal publishers are the only FSx artifact producers; and no group joins parallel shards.
- Generate and retain an inventory plus output-parity dry-run for all 27 command-catalog commands. Fail the release if any reachable sequence producer is unclassified or violates the contract.
- Run focused caller tests, profile tests, catalog tests, and representative full dry-runs for ILMN, ONT, PacBio, Ultima, Complete Genomics/MGI, HIOMR, and HIOMR2.
- Validate from a new explicit-tag headnode clone: first dry-run, then a representative live multi-AU NVMe run that proves two 128-thread jobs can share an eligible 384-vCPU node without scratch collision, atomically publishes FSx finals, and removes scratch `temp()` artifacts.
- Commit DayOA only after the full inventory is terminal and validation passes; tag the clean commit; then update both DYEC catalog copies and pins, test them, and release DYEC separately.

## Assumptions

- All 27 active catalog rows are in scope; deprecated HIOMRS sources are not migrated unless an active catalog DAG reaches them.
- The recommended distributed-shard design is accepted: temporary FSx shard checkpoints followed by one durable merged result.
- Validation omits `--keep-temp` so Snakemake’s cleanup contract is actually proven.
- No current Take8 source, controller, or running Jasmine job is modified by this overhaul.
