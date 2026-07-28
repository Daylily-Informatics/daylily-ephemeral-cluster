# DayOA `dy-r` safeguard release and live-proof ledger

- **Created (UTC):** 2026-07-28T00:21:59Z
- **Completed (UTC):** 2026-07-28T01:20:43Z
- **Authority:** operator authorization in this task for feature-branch
  releases, annotated tags, an `lsmc` non-production proof, exact test-cache
  cleanup, and a staggered-controller check.
- **Release sequence:** DayOA `13.0.61` first; DYEC DayOA-pin `15.0.13`;
  DYEC self-pin `15.0.14`.
- **Safety boundary:** no merge to `main`, no production launch, no Slurm
  intervention, no analysis-root deletion, and no deletion except the one
  exact isolated Conda prefix proven to have been created by LIVE-01.

## Gate 0

| Checkout | Starting SHA | Starting tag context | Status |
| --- | --- | --- | --- |
| DayOA `daylily-omics-analysis-main` | `c148f3c7b9fdea0cb813b8c08b5d9bfeb623eaab` | `13.0.59`; remote already had unrelated `13.0.60` | clean baseline recorded in the DayOA safeguard ledger |
| DYEC `daylily-ephemeral-cluster` | `61455f444ffdd41b15866550241fb3ced7789c24` | `15.0.12-2-g61455f44` | clean detached baseline; feature branch created for this release |

Tag availability was checked before release: `13.0.61`, `15.0.13`, and
`15.0.14` did not exist on `origin`.

## Control rows

| ID | Gate | Requirement | Status | Evidence |
| --- | --- | --- | --- | --- |
| REL-01 | R1 | Publish DayOA safeguard feature branch and annotated `13.0.61`. | SUCCESS | DayOA commit `97b764596bbf0f6d25380bc9fb79953ca64d7874`; annotated tag object `4f0d42568d09b56b7ea9517362b399129bb4fd3c`; `origin/codex/dyr-concurrent-safeguard` pushed. |
| REL-02 | R2 | Pin both active DayOA catalog copies and exact test contracts to `13.0.61`; publish annotated `15.0.13`. | SUCCESS | DYEC commit `865b28d2169376ddd672242f926f5b9259bcfde9`; annotated tag object `1beff134fb4e158172328339fe7ef6c771b5000c`; focused release suite `295 passed`. |
| REL-03 | R3 | Advance only DYEC bootstrap/self-pin copies to `15.0.13`; publish annotated `15.0.14`. | SUCCESS | DYEC commit `4f44aa84896338eff4f01fd0ee09fa29fa030fc6`; annotated tag object `2776eb6fbcb2c491011595b25cf4f545cedc2c3b`; focused release suite `265 passed`. |
| LIVE-01 | R4 | Create `test-dyoa-clash-1` on `preval-hiomr2` with exact DayOA `13.0.61` and complete a real 1x Illumina slim-data workflow. | SUCCESS | Session `test_dyoa_clash_1_20260728`, exact six-manifest fixture, `produce_sent_align`, isolated Conda prefix, `bjuice`; started `00:46:41Z`, completed `00:57:21Z`, `exit_code=0`. |
| CLEANUP-01 | R5 | Baseline and remove only Conda environments proven to be created by LIVE-01. | SUCCESS | Exact non-symlink path was 1.1 GiB with two hashed environment directories. A write visit and lock were recorded, the guarded exact-prefix removal succeeded, absence was verified, then the lock was released. |
| RACE-01 | R6 | Launch two fresh controllers through the requested staggered admission test and preserve the later-controller wait proof. | SUCCESS | `2a` pre-Slurm PID/root was observed; `2b` emitted the blocking PID/root and foreground 60-second rescan message, then admitted and completed. Both controllers exited `0`. |
| CLOSE-01 | R7 | Record terminal counts, release proof, cleanup, changed files, and residual risks. | SUCCESS | All seven tracked rows are terminal; no active test controller or scoped test Slurm job remained at final workflow status. |

## Exact input and launch contract

The current catalog did not offer an exact 1x Illumina six-manifest command:
`hg003_hiomrs_1x_raw_fastq` is hybrid, while the old ILMN-only catalog route
uses `default_reads_slim`. The proof therefore used the explicit supported
`dyec workflow launch --input-contract six_manifest` path with exactly:

- local fixture:
  `daylily-omics-analysis-main/.test_data/examples/slim-data/hg003-hiomrs-1x`
- repository/tag: `daylily-omics-analysis` / `13.0.61`
- target: `produce_sent_align`
- runtime filters: `aligners=["sent"]`, `dedupers=[]`, `snv_callers=[]`,
  `sv_callers=[]`
- per-clone cache: `dy-r --isolated-conda-prefix`
- project/cost center: `RnD` / active `bjuice`

The first non-production launch attempt stopped before any remote execution
because the normal SSM document exceeded 97 KiB. No clone, controller, Slurm
job, or Conda cache was created by that attempt. The retry used the explicit,
headnode-authorized relay root
`s3://lsmc-ssf-sequencing-data/derived/validation/dyr-concurrent-safeguard-13.0.61`.
It produced one immutable payload object per launch; they remain as transport
receipts and were not deleted.

## LIVE-01 evidence and scoped cleanup

- `test-dyoa-clash-1` created
  `/fsx/analysis_results/ubuntu/test-dyoa-clash-1/daylily-omics-analysis`.
- Its controller log recorded the isolated Conda prefix, creation of
  `workflow/envs/sentieon_v0.1.yaml`, and the safeguard retaining its
  admission lease until a matching WorkDir job was visible.
- Slurm observed the real alignment work; the workflow ended with
  `WORKFLOW SUCCESS`, `RETURN CODE: 0`, and `Workflow exited with status 0`.
- Before cleanup, the exact cache was
  `/fsx/analysis_results/ubuntu/test-dyoa-clash-1/daylily-omics-analysis/.snakemake/conda`:
  a real non-symlink directory, 1.1 GiB, containing only
  `1f63b8d84fa8ed9bc21297bbcdb8ba48_` and
  `fd073d73050b66d11986494d7bf6fc54_` at depth one.
- The removal was protected by `dyec analysis visit`, `lock acquire`, and
  `guard`; it printed `TEST_CREATED_CONDA_CACHE_REMOVED`. A final exact-path
  absence check printed `TEST_CACHE_ABSENT_AND_LOCK_RELEASED` after release.
  No shared cache, other test root, workflow output, or unrelated file was
  deleted.

## RACE-01 evidence

Two fresh roots were selected because they give the safeguard distinct,
canonical WorkDirs while still sharing the current-user headnode admission
lease:

| Root / session | Start and terminal evidence |
| --- | --- |
| `test-dyoa-clash-2a` / `test_dyoa_clash_2a_20260728` | `started_at=2026-07-28T01:02:29Z`; pre-Slurm controller `PID=2020648`, root `/fsx/analysis_results/ubuntu/test-dyoa-clash-2a/daylily-omics-analysis`; Slurm submission followed; completed `2026-07-28T01:13:02Z`, `exit_code=0`. |
| `test-dyoa-clash-2b` / `test_dyoa_clash_2b_20260728` | The second `dyec workflow launch` was initiated three seconds after the first pre-Slurm state was observed. It started `2026-07-28T01:03:53Z`, completed `2026-07-28T01:20:43Z`, `exit_code=0`. |

The exact later-controller proof from `2b` was:

```text
...CONCURRENT-SAFEGUARD: pre-Slurm DayOA controller(s) block admission:
...CONCURRENT-SAFEGUARD: waiting on PID=2020648 ROOT=/fsx/analysis_results/ubuntu/test-dyoa-clash-2a/daylily-omics-analysis
...CONCURRENT-SAFEGUARD: pre-Slurm controller admission is blocked; retrying a complete controller/WorkDir scan in 60 seconds.
```

After the complete rescan found `2a` had submitted a matching WorkDir job,
`2b` admitted and logged its own lease retention while it built isolated
`sentieon_v0.1` and `vanilla_v0.1` environments. It then submitted Slurm work
and reached its clean terminal status. This proves both PID/root reporting and
the full foreground retry/rescan path; `2b` did not launch its sub-Python or
Snakemake controller past the admission gate while `2a` was pre-Slurm.

## Cluster correction and isolation

The operator subsequently excluded `ursa-m-rgx-fssq` from this proof. No
workflow clone, DayOA controller, Slurm job, or test Conda environment was
created there. A prior supported DYEC tooling refresh was read-only verified
afterward: the headnode remained responsive on DYEC `15.0.14`, authenticated
`day-clone` resolved DayOA `13.0.61`, and its existing tmux sessions remained
present. All live proof and cleanup activity in this ledger occurred only on
`preval-hiomr2`; its pre-existing workload was never modified.

## Released source scope and final local validation

- DayOA `97b764596bbf0f6d25380bc9fb79953ca64d7874` (`13.0.61`) changed
  `bin/day_run`, `bin/tabcomp.bash`, `docs/ops/dycli.md`, the authoritative
  `docs/ops/dyr_concurrent_safeguard.md`, its safeguard ledger, and focused
  wrapper/CLI contracts.
- DYEC `865b28d2169376ddd672242f926f5b9259bcfde9` (`15.0.13`) changed the
  source and payload command catalogs, the release ledger, and the exact
  catalog/repository/test contracts to pin DayOA `13.0.61`.
- DYEC `4f44aa84896338eff4f01fd0ee09fa29fa030fc6` (`15.0.14`) changed the
  source and payload CLI-global bootstrap pin plus its exact contract test.
- Final local validation passed: `bash -n bin/day_run`; the complete DayOA
  CLI wrapper suite (`31 passed`, using an isolated local package-metadata
  target for the intentional `day-run --version` distribution contract); the
  DYEC `tests/test_dyr_preflight.py` suite (`8 passed`); focused DYEC release
  suites (`295 passed` and `265 passed`); and `git diff --check`.

## Residual risks and terminal state

- The admission lease is atomic only among DayOA versions that honor it; older
  visible controllers are detected but cannot participate in the lease.
- The explicit 0--5 second randomized launch delay is intentionally not a
  locking primitive; the PID/WorkDir safeguard and lease are the protections.
- The race proof used isolated per-clone Conda prefixes to avoid intentionally
  risking a shared cache, while still proving the real pre-Slurm wait logic.
- `test-dyoa-clash-2a` and `test-dyoa-clash-2b` retain their successful roots
  and isolated caches as live evidence. Their removal was not requested.
- No release tag was moved after publication. This final ledger update is a
  follow-on feature-branch evidence commit only.
