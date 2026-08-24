# Bjuiceval 19024 hybrid input DRA mount ledger

Created: `2026-08-24T01:17:15Z`

## Objective

Attach two explicit, read-only FSx data repository associations to cluster
`bjuiceval-19024` so the Illumina and ONT sequence-data paths named by
`hybrid_crosswalk-CORRECTED.tsv` can be used by later Bjuice and Inflection
packaging work. This ledger does not authorize or claim a Bjuice/Inflection
workflow launch, export, DRA detach, FSx deletion, or cluster teardown.

## Control ledger

Controlling request: user request in the current Codex task.

Ledger path:
`docs/plans/20260824T011715Z_bjuiceval19024_hybrid_dra_mounts_ledger.md`

### Gate 0: inventory freeze

- Repository: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`
- Branch: `codex/bjuiceval-19024-dra-mounts`
- Release commit/tag: `7d32d4258613be08cdeb6fa97240e0e3060f6794` / `19.0.24`
- Existing worktree state: user-owned untracked files were present before this
  task and are preserved; this ledger is the only task-owned repo file.
- CLI: activated public `dyec`; `dyec --json version` returned `19.0.24`.
- AWS context: profile `lsmc`, region `us-west-2`, cluster
  `bjuiceval-19024`.
- Cluster baseline: `clusterStatus=UPDATE_COMPLETE`,
  `computeFleetStatus=RUNNING`, headnode instance is running.
- DRA baseline: `dyec --json mounts list ...` returned zero managed mounts.
- Input: `/Users/jmajor/Downloads/hybrid_crosswalk-CORRECTED.tsv`
- Input SHA-256:
  `c453367fe15a2efbdc875067b460d717125991dbd1eac4c7a23966ac183642fb`
- TSV audit: 128 rows, 122 distinct `unit_id` values, 128/128
  `confidence=ok`, 128/128 `ilmn_ok=TRUE`, and 128/128 `ont_ok=TRUE`.
- Repeated `unit_id` values retained as source data rather than silently
  deduplicated: `M-BCN-605`, `M-BCN-A613`, `M-BCN-A5AE`, `HG002-b`,
  `HG003-b`, and `HG004-b` each occur twice.
- Illumina topology: four named FASTQ directories, all under the supplied
  common ancestor
  `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/`.
- ONT topology: 128 named barcode directories across four runs and 32 sets,
  all under the supplied common ancestor
  `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/`.
- Scope decision: create exactly two associations, matching the requested
  ILMN and ONT mounts. The selected prefixes are deterministic common
  ancestors of every corresponding URI in the TSV; no source path is
  discovered or substituted from another analysis.
- Planned policy: read-only, batch metadata import enabled, auto-import
  `NEW,CHANGED`, no auto-export/writeback, wait up to 5,400 seconds, and verify
  the two exact returned association and mount IDs.
- Baseline tests: not applicable; no runtime source code is being changed.
- Live limit: DRA creation can legitimately remain `CREATING` for more than
  40 minutes. A short transport return is not failure and must not trigger a
  duplicate association.

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| G0-001 | Inventory | Freeze source, cluster, CLI, repo, and DRA baseline before mutation | SUCCESS | plan_amendment | Gate 0 | Forge | Facts and commands recorded above |  | Gate 0 complete; zero pre-existing managed mounts. |
| MOUNT-ILMN | AWS/FSx | Create read-only ILMN association for `.../LH01106/2026/` at mount ID `hybrid-crosswalk-ilmn-2026` | SUCCESS | feature_implementation | User-authorized live attach | Forge | `dyec.mounts.create.v1`: DRA `dra-0699649d249652226`, FSx `fs-04927ce3710f164c2`, lifecycle `AVAILABLE`, platform `ILMN`, read-only, auto-export empty, completed `2026-08-24T02:00:12Z` |  | Original create/wait returned `rc=0` after about 41 minutes; no replacement association. |
| MOUNT-ONT | AWS/FSx | Create read-only ONT association for `.../pca100/` at mount ID `hybrid-crosswalk-ont-pca100` | SUCCESS | feature_implementation | User-authorized live attach | Forge | `dyec.mounts.create.v1`: DRA `dra-0fe499a0851d5c3ff`, FSx `fs-04927ce3710f164c2`, lifecycle `AVAILABLE`, platform `ONT`, read-only, auto-export empty, completed `2026-08-24T01:39:44Z` |  | Original create/wait returned `rc=0`; no replacement association. |
| VERIFY-ILMN | Headnode | Verify exact ILMN DRA and `/fsx/run_dir_mounts/hybrid-crosswalk-ilmn-2026/` are usable | SUCCESS | contract_test | Gate 5 | Forge | `dyec.mounts.verify.v1`: `verified=true`, `usable=true`, command `45ad1c48-6457-4f05-a2cb-df5c3c81a709`, headnode `i-0ff7f501b24c95530`, `2026-08-24T02:00:30Z` |  | Exact ILMN mount path is usable. |
| VERIFY-ONT | Headnode | Verify exact ONT DRA and `/fsx/run_dir_mounts/hybrid-crosswalk-ont-pca100/` are usable | SUCCESS | contract_test | Gate 5 | Forge | `dyec.mounts.verify.v1`: `verified=true`, `usable=true`, command `ec91c3e3-0ce9-466a-962e-e69d353f11af`, headnode `i-0ff7f501b24c95530`, `2026-08-24T01:43:10Z` |  | Exact ONT mount path is usable. |
| COVERAGE-001 | Input mapping | Prove all 128 TSV rows map beneath both selected mount roots | SUCCESS | contract_test | Gate 5 | Forge | Bundled-Python TSV audit: 0 ILMN and 0 ONT rows outside the selected prefixes; 4 unique projected ILMN directories and 128 unique projected ONT directories; 0 empty paths |  | Every supplied row maps deterministically without fallback or deduplication. |

## Executed public CLI commands

```bash
dyec --json mounts create \
  s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/ \
  --profile lsmc --region us-west-2 --cluster bjuiceval-19024 \
  --purpose run --platform ILMN \
  --mount-id hybrid-crosswalk-ilmn-2026 \
  --file-system-path /run_dir_mounts/hybrid-crosswalk-ilmn-2026/ \
  --read-only --batch-import-metadata-on-create \
  --auto-import NEW,CHANGED --wait --timeout-seconds 5400

dyec --json mounts create \
  s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/pca100/ \
  --profile lsmc --region us-west-2 --cluster bjuiceval-19024 \
  --purpose run --platform ONT \
  --mount-id hybrid-crosswalk-ont-pca100 \
  --file-system-path /run_dir_mounts/hybrid-crosswalk-ont-pca100/ \
  --read-only --batch-import-metadata-on-create \
  --auto-import NEW,CHANGED --wait --timeout-seconds 5400
```

## Final report

All rows terminal: `yes`

Objective complete: `yes`

Status counts:

- SUCCESS: 6
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0
- OPEN: 0
- IN_PROGRESS: 0
- ATTEMPTING_BUGFIX: 0

Changed files:

- `docs/plans/20260824T011715Z_bjuiceval19024_hybrid_dra_mounts_ledger.md`

Validation:

- Final `dyec --json mounts list` reports exactly the two task DRAs as
  `AVAILABLE`, locally projected, read-only, and platform-labeled `ILMN` and
  `ONT`.
- Both exact `dyec mounts verify` calls returned `verified=true` and
  `usable=true` on the running headnode.
- The deterministic TSV audit proves all 128 rows map beneath both selected
  mount roots.
- `git diff --check` returned no errors.

### Live evidence log

- `2026-08-24T01:19:33Z`: DYEC created ILMN DRA
  `dra-0699649d249652226` and ONT DRA `dra-0fe499a0851d5c3ff` on
  `fs-04927ce3710f164c2`.
- Both exact descriptions report `read_only=true`,
  `batch_import_metadata_on_create=true`, auto-import `NEW,CHANGED`, empty
  auto-export events, and lifecycle `CREATING`.
- At this initial `CREATING` snapshot, the original two
  `dyec mounts create --wait --timeout-seconds 5400` processes remained
  active. Both later returned `rc=0`; no retry or replacement association was
  issued.
- Deterministic TSV projection audit: all 128 rows are covered; zero source
  paths fall outside the selected prefixes; the mapping yields four unique
  Illumina FASTQ directories and 128 unique ONT barcode directories under the
  planned headnode roots.
- `2026-08-24T01:39:44Z`: ONT DRA `dra-0fe499a0851d5c3ff` reached
  `AVAILABLE`; the create receipt recorded platform `ONT`, read-only policy,
  and local projection creation.
- `2026-08-24T01:43:10Z`: `dyec mounts verify` returned `verified=true` and
  `usable=true` for `/fsx/run_dir_mounts/hybrid-crosswalk-ont-pca100` on
  headnode `i-0ff7f501b24c95530`.
- `2026-08-24T02:00:12Z`: ILMN DRA `dra-0699649d249652226` reached
  `AVAILABLE`; the create receipt recorded platform `ILMN`, read-only policy,
  and local projection creation after the original patient wait.
- `2026-08-24T02:00:30Z`: `dyec mounts verify` returned `verified=true` and
  `usable=true` for `/fsx/run_dir_mounts/hybrid-crosswalk-ilmn-2026` on
  headnode `i-0ff7f501b24c95530`.
- `2026-08-24T02:01:23Z`: final `dyec mounts list` reported exactly both task
  associations `AVAILABLE`, locally projected, read-only, and with no
  auto-export events.

Residual risks: none for the requested mount attachment. Bjuice/Inflection
configuration, dry/live execution, packaging, export, and cleanup remain
separate operations outside this ledger.
