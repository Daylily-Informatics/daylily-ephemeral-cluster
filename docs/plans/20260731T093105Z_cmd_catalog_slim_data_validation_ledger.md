# DYEC command-catalog slim-data validation ledger

Created: 2026-07-31T09:31:05Z
Controlling repository: `daylily-ephemeral-cluster`
Execution cluster: `cmd-catalog-tests`
AWS profile / region: `lsmc` / `us-west-2`
Cost center: `cmd-cat-test`
Starting DYEC release under test: `16.1.18`
Functional fix release: `16.1.19` at `de8641b4ad294b325780d5045cb9a86fc246a198`
Candidate self-pin/configure release: `16.1.20` (pending)
DayOA release under test: `13.0.107`

## Objective

Build a repeatable command-catalog qualification suite in which:

1. every required core DYEC command-catalog command runs cleanly against the
   smallest authoritative slim-data fixture appropriate to that command;
2. the HIOMR2 kitchen-sink catalog lane is explicitly included and consumes the
   exact HG003 1x Illumina paired FASTQs plus the exact HG003 1x
   primary-only ONT FASTQ;
3. two fresh-root runs of a command, using the same pinned software, inputs, and
   rendered command, produce semantically equivalent results;
4. Ursa exposes the canonical DYEC catalog and its qualification state clearly,
   without maintaining a second catalog;
5. failures are debugged at the narrowest shared source, preferring fewer
   generalized DayOA rules and contracts over copied per-command rules; and
6. the converged suite becomes an evidence-producing PR gate plus bounded
   daily and weekly drift monitors.

The objective is complete only when every required ledger row is terminal and
all required command rows are `SUCCESS`. A hidden, skipped, or silently
substituted command is not success.

## Non-negotiable execution contract

- Run locally from a clean, exact-tag DYEC worktree activated with
  `source ./activate`.
- Do not use the canonical DayOA checkout at
  `/Users/jmajor/projects/lsmc/daylily-omics-analysis`.
- Create or realign a dedicated paired DayOA worktree to exact tag `13.0.107`.
  The currently observed paired worktree is detached at `13.0.61` and is not
  eligible for execution.
- Configure the headnode from exact DYEC tag `16.1.18` before launching. The
  observed headnode DYEC version is `16.1.17`.
- On the headnode, workflow execution is as `ubuntu` in a persistent,
  meaningfully named `tmux` session with an interactive Bash login shell.
- DayOA initialization remains separate: `source dyoainit`, then
  `dy-a slurm <genome_build>`, then execution through `dy-r`.
- Never invoke raw `snakemake`. The public entrypoint for this suite is
  `dyec tests command-catalog`, which must preserve the supported `dy-r`
  execution path.
- Before touching an analysis root, record the required `dyec analysis visit`.
  Acquire and retain the analysis-root write lock for live workflow writes, and
  release it only after terminal evidence is captured.
- Do not patch an installed checkout, a running analysis root, or a headnode
  worktree. Fix source in a dedicated local worktree, test it, release immutable
  tags, configure the exact new release, and retry in a fresh analysis root.
- Do not administer Slurm or jobs. Monitoring is allowed; cancel, requeue,
  drain/resume, daemon, partition, and scheduler changes require a separate
  exact proposal and explicit approval.
- Do not create missing mounts implicitly. A required run mount needs confirmed
  provenance and an explicit `dyec mounts create --wait` operation with a
  timeout comfortably above 40 minutes.
- Do not increase the `$200` monthly cap. Any increase requires the repository's
  double-approval process.
- Do not invent an owner-issued analytical batch identifier or a
  Meridian/TapDB-style EUID. A command that requires one remains blocked until
  the owning service supplies a persisted value.
- No fallback paths, inferred data, legacy aliases, or silent command
  substitutions.

## HIOMR2 kitchen-sink freeze boundary

The required frozen lane is the DYEC catalog command:

`hybrid_ilmn_ont_hiomr2_kitchensink_inflection_analytical`

Its current catalog targets include:

- `produce_sentdhiomr2_kitchensink`
- `produce_sentdhiomr2_inflection_analytical_package`

Execution, read-only inspection, log review, DAG comparison, and semantic
artifact comparison are authorized planning activities. They do not authorize
source changes.

Any proposed change to a HIOMR2 kitchen-sink rule, include, target, selector,
environment reference, resource declaration, dependency edge, expected output,
or shared rule that changes this lane's rule/target dependency topology or
output contract must stop at
`WAITING_DOUBLE_APPROVAL`. The execution agent must:

1. show the exact file and diff, the observed failure, the expected effect, and
   a before/after rule graph, target, and contract comparison;
2. request the first explicit approval for that exact proposal; and
3. after restating the approved scope and impact, receive a second explicit
   approval before editing.

The request to include and run this lane is not approval to modify it. Selecting
the explicitly requested versioned slim fixture may change instance-level DAG
fan-out, but it may not change rules, targets, dependency topology, or output
contracts. A generalized fix outside this lane may proceed only when exact-tag
rule-graph and contract evidence proves that frozen boundary is unchanged.

## Gate 0: observed baseline

Observed read-only on 2026-07-31:

| Item | Observation | Gate consequence |
|---|---|---|
| Cluster | `cmd-catalog-tests`, `UPDATE_COMPLETE`, compute fleet `RUNNING` | Eligible for preflight |
| Headnode | `i-043677c5897670f24`, Ubuntu 22.04 | Use `ubuntu`; never root |
| Headnode DYEC | `16.1.17` | Must configure exact `16.1.18` before launch |
| DYEC / DayOA pins | `16.1.18` / `13.0.107` | Immutable starting release pair |
| Catalog validation metadata | Commands are pinned to `13.0.107`, while relevant entries still report `validated_version: 13.0.61` | Replace the stale validation claim only after accepted `13.0.107` evidence |
| Controllers / Slurm | zero authoritative controllers; zero jobs | Clean baseline, not execution authorization |
| FSx | mounted at `/fsx`, about 1% used | Verify exact fixture paths and free space again |
| Managed run mounts | none listed | Run-QC lanes are blocked until a portable fixture or approved mount exists |
| Cost center | `cmd-cat-test`, active, `$200` monthly cap, `ubuntu` allowed | Use exact cost center; no cap increase |
| Processed July usage | `$0`, latest processed hour `2026-07-31T08:00:00Z` | Refresh before every live wave; account for reporting lag |
| `dyec headnode jobs` | remote `yaml` import failure was printed even though the command returned success | General DYEC contract bug; fix/cover before relying on this surface |
| Paired DayOA worktree | detached at `13.0.61` | Replace/realign to exact `13.0.107` |
| Canonical Ursa checkout | contains unrelated user changes and generated artifacts | Use a new isolated Ursa worktree for any implementation |

Before live execution, repeat this baseline and persist raw JSON/text evidence.
Any new controller, job, mount, version mismatch, cost anomaly, or fixture
digest mismatch stops the wave.

### Execution amendment — 2026-07-31T10:45:57Z

- The controlling DYEC worktree acquired substantial unrelated concurrent
  pricing/configuration edits after the original Gate 0. It is read-only for
  this effort except for this ledger; none of those edits may enter a release.
- Clean isolated worktrees were created at:
  - DYEC `16.1.18`: `/Users/jmajor/.codex/worktrees/7731/daylily-ephemeral-cluster-16.1.18`
    at `d0f0a06ef36117abb243650dc393e0568a8f7255`;
  - DayOA `13.0.107`: `/Users/jmajor/.codex/worktrees/7731/daylily-omics-analysis-13.0.107`
    at `ab16caf9d8359753fb69d53c84c7662ee4855ab0`;
  - DYEC fixes: `/Users/jmajor/.codex/worktrees/7731/daylily-ephemeral-cluster-cmd-catalog-fixes`
    on `codex/cmd-catalog-slim-execution-20260731`; and
  - Ursa: `/Users/jmajor/.codex/worktrees/7731/daylily-ursa-catalog-validation`
    on `codex/cmd-catalog-slim-ursa-20260731` at
    `38a222094fcf6933cb98b50c491ebc270003e820`.
- Exact DYEC `16.1.18` cannot pass the pre-launch gate unchanged:
  - one runner test retained a stale `13.0.61` expected Git tag while the
    catalog correctly selects DayOA `13.0.107`; and
  - the headnode bootstrap can leave Conda `base` ahead of `DAY-EC`, emit
    `ModuleNotFoundError: yaml`, and let `dyec headnode jobs` return zero.
- The shared fix branch now reactivates `DAY-EC` whenever Conda startup resets
  it and makes login-startup failures propagate. It also corrects stale
  Git-tag test expectations without changing `validated_version: 13.0.61`.
- The immutable release train is amended to a functional patch `16.1.19`, then
  a `16.1.20` self-pin/configure release pointing explicitly to `16.1.19`.
  Existing tags will not be moved.
- Focused validation is green (`163 passed`). A full-suite run after the first
  fixes reported `2419 passed, 11 skipped, 26 failed`; five failures were stale
  catalog Git-tag expectations now fixed. The remaining 21 failures reproduce
  unchanged on exact `16.1.18` (`21 failed, 52 passed` in the affected-file
  baseline subset) and are not caused by this branch. Ruff likewise reports
  the same 31 pre-existing findings on exact `16.1.18` and the fix branch.

## Required command matrix

The suite distinguishes required coverage from later extended coverage. This
prevents an ambiguous claim that all 27 catalog entries are "core".

### Bootstrap

| Command ID | Data contract | Required result |
|---|---|---|
| `simple-test` | no genomic input | Runner, evidence, tmux, locking, and exit-code smoke |

### Portable slim-data core

These are the sample-analysis members of the released core selector. They must
run without a per-run DRA or an inferred alternate path.

| Command ID | Slim-data profile | Wave |
|---|---|---|
| `illumina_snv_alignstats` | `default_reads_slim` | solo |
| `illumina_hg002_kitchensink_multiqc` | `default_reads_slim` | kitchen sink |
| `ultima_snv_alignstats` | `default_reads_slim` | solo |
| `ultima_snv_alignstats_kitchensink` | `default_reads_slim` | kitchen sink |
| `ont_snv_alignstats` | `default_reads_slim` | solo |
| `ont_snv_alignstats_kitchensink` | `default_reads_slim` | kitchen sink |
| `hybrid_ilmn_ont_hiomr` | `hg003_hiomrs_1x_raw_fastq` | hybrid |
| `hybrid_ilmn_ont_hiomr_kitchensink` | `hg003_hiomrs_1x_raw_fastq` | hybrid kitchen sink |

### Required frozen add-on

| Command ID | Slim-data profile | Wave |
|---|---|---|
| `hybrid_ilmn_ont_hiomr2_kitchensink_inflection_analytical` | `hg003_hiomrs_1x_raw_fastq`, reduced to exact A1 referential closure | frozen HIOMR2, serial |

This command is required even though it is not currently a member of
`DYEC_RELEASED_CORE_COMMAND_IDS`. The qualification suite must select it
explicitly, and Ursa must show it as `required-frozen`, not hide it.

### Core run-analysis commands

| Command ID | Input requirement | Initial state |
|---|---|---|
| `illumina_run_qc` | authoritative minimal Illumina run directory | `BLOCKED_INPUT` |
| `ont_run_qc` | authoritative minimal ONT run directory | `BLOCKED_INPUT` |
| `ultima_run_qc` | authoritative minimal Ultima run directory | `BLOCKED_INPUT` |

These remain core. They may not be silently excluded from the completion claim.
Gate R must either establish versioned, portable, scientifically valid control
fixtures under the normal all-cluster control-data contract or use separately
approved, provenance-confirmed managed mounts. Until then the overall core
objective is incomplete.

### Extended catalog coverage

Production and development entries outside the required matrix—relatedness/VEP,
PacBio, Roche, CG/MGI, pangenome, BCL Convert, packaging, and product-specific
commands—enter rotating coverage only after the required core is green. Their
absence does not redefine core, and their addition must declare inputs,
runtime parameters, cluster compatibility, expected artifacts, and comparator.

## Exact HG003 1x input contract

The HIOMR and HIOMR2 lanes must consume exactly:

```text
/fsx/references/genomic_data/organism_reads_slim/fastq/H_sapiens/giab/NovaSeqX_WHGS_TruSeqPF_HG002-007/downsampled/HG003_1x_R1.fastq.gz
/fsx/references/genomic_data/organism_reads_slim/fastq/H_sapiens/giab/NovaSeqX_WHGS_TruSeqPF_HG002-007/downsampled/HG003_1x_R2.fastq.gz
/fsx/references/genomic_data/organism_reads_slim/fastq/H_sapiens/giab/agbt_2026/ont/HG003_1x.cleaned.primary.fastq.gz
```

Gate D must record for each file: canonical path, type, size, mtime, readable
status, and a content digest or authoritative object-version identity. It must
also prove that the DYEC packaged fixture and the DayOA `13.0.107` fixture are
semantically identical.

The existing six-manifest fixture contains several analysis units. To keep the
suite truly minimal, create a new versioned fixture profile—not an in-place
edit—that retains the full six-manifest referential contract but selects only:

`HG003-SR1x-ONT1x-A1`

The new fixture must reference both Illumina mates and the one primary-only ONT
FASTQ above, pass manifest schema and lineage validation, and carry a normalized
fixture digest. No CRAM may enter this slim-data lane.

If the current command cannot select that one analysis unit without changing
the frozen HIOMR2 graph, keep the existing fixture for the first read-only
render and report the conflict. Do not alter HIOMR2 until double approval.

The analytical package target also requires a real, owner-issued, persisted
`SEQONE_DELIVERY_BATCH_ID`. Gate I remains `BLOCKED_IDENTITY` until that value
and its owning-service evidence are supplied. A placeholder is forbidden.

## Execution phases

### Phase 0 — immutable release and environment convergence

1. Create clean, separate worktrees for:
   - DYEC `16.1.18`;
   - DayOA `13.0.107`; and
   - Ursa at the selected base commit.
2. Verify each tag is annotated where applicable, clean, and resolves to the
   intended commit.
3. Validate catalog metadata, packaged-resource presence, pinned DayOA tag,
   command rendering, and fixture closure locally.
4. Configure `cmd-catalog-tests` from the exact DYEC `16.1.18` worktree.
5. Re-read headnode system information and fail unless it reports `16.1.18`
   and the configured DayOA checkout reports `13.0.107`.
6. Recheck controllers, jobs, mounts, FSx, cluster status, cost-center usage,
   and cluster/command compatibility.

### Phase 1 — no-write rendering and dry-run qualification

1. Render every required command with resolved catalog metadata.
2. Persist command ID, targets, exact DayOA tag, environment/config references,
   fixture profile/digest, required runtime parameters, and rendered shell.
3. Perform catalog validation and a `dy-r`-backed dry run only through the
   supported DYEC runner.
4. Capture the resulting rule/target graph and compare it with the catalog
   declaration.
5. For the frozen HIOMR2 lane, archive this graph as the no-change baseline.
6. Do not launch any live wave until every required portable command is green
   at this phase, except an explicitly recorded missing owner-issued identity.

### Phase 2 — bootstrap and inexpensive solo commands

- Run `simple-test` first.
- Run solo portable commands serially, initially with `--parallel 1`.
- Refresh spend and controller/job state before each command.
- Every command uses a fresh root and a unique evidence prefix.
- A command failure stops the wave; it does not trigger the next command.

### Phase 3 — kitchen sinks and hybrid commands

- Run each non-HIOMR2 kitchen sink serially.
- Run `hybrid_ilmn_ont_hiomr` and its kitchen sink using the exact HG003 input
  contract.
- Collect benchmark data through the supported DayOA benchmark collector after
  each terminal workflow.
- Use observed task costs to bound the next wave within the remaining cap.

### Phase 4 — frozen HIOMR2 kitchen sink

- Require exact fixture digest, exact rendered graph, correct compatible
  cluster resources, and the owner-issued analytical batch ID.
- Run by explicit command ID, serially, against a fresh analysis root.
- Do not make any automatic or opportunistic source change after failure.
- Classify and preserve evidence. If remediation touches the frozen boundary,
  transition to `WAITING_DOUBLE_APPROVAL`.

### Phase 5 — fresh-root semantic repeats

After a command first becomes clean:

1. launch run A and run B in separate new roots;
2. prove identical release tags, rendered command, fixture digest, reference
   identity, config, and comparator version;
3. compare their artifact inventories and semantic digests;
4. investigate any unexplained difference;
5. promote a golden baseline only after A and B are mutually equivalent and
   the evidence is reviewed.

Debug attempts are not golden candidates.

### Phase R — run-directory fixture qualification

For each run-analysis command:

1. define the irreducible platform metadata and data files needed for a valid
   result;
2. establish a versioned control-data fixture with provenance and a digest;
3. prove it is available at the same explicit contract on all target clusters;
4. run the same render, live, repeat, and semantic-equivalence gates; and
5. if portability cannot be established, retain `BLOCKED_INPUT` and keep the
   overall core suite incomplete.

Do not manufacture a biologically misleading "minimal" run directory merely
to make a command exit zero.

## Debug-and-retry loop

Every failure gets one primary class:

- `FIXTURE_CONTRACT`
- `CATALOG_METADATA`
- `DYEC_RUNNER`
- `DAYOA_SHARED_RULE`
- `DAYOA_COMMAND_SPECIFIC`
- `RUNTIME_ENVIRONMENT`
- `CLUSTER_COMPATIBILITY`
- `IDENTITY_CONTRACT`
- `URSA_SURFACING`
- `SEMANTIC_COMPARATOR`

For each attempt:

1. preserve the first failing command, exit code, controller/rule log, rendered
   command, rule graph, versions, fixture digest, and artifact inventory;
2. identify the earliest shared failing contract;
3. prefer a single tool-family or modality-aware rule/validator over copied
   rules for individual catalog commands;
4. keep command catalog entries declarative: command ID, targets, inputs,
   parameters, outputs, and compatibility;
5. do not merge semantically different platforms or tools merely to reduce
   file count;
6. add focused tests reproducing the failure and cross-command tests proving
   the generalized behavior;
7. for any workflow environment change, create a new incremented YAML and
   update explicit references—never edit a versioned environment YAML in place;
8. release a new immutable DayOA patch if DayOA changed, update DYEC's explicit
   DayOA pin, release a new immutable DYEC patch, and configure that exact tag;
9. retry in a new root and new evidence prefix; and
10. append the attempt and disposition to this ledger.

No failure authorizes changing the HIOMR2 frozen boundary.

The known `dyec headnode jobs` remote `yaml` import problem must be fixed at the
shared DYEC remote-command/environment boundary, with a test that asserts a
remote dependency failure propagates a nonzero result. Do not add a
command-specific bypass.

## Semantic-equivalence contract

Byte equality is not required where formats contain legitimate compression,
runtime, or provenance variance. "Looks similar" is not sufficient. Every
authoritative artifact role gets a versioned comparator.

| Artifact | Semantic comparison |
|---|---|
| VCF/gVCF | Validate and decompress; remove only enumerated volatile provenance headers; normalize ordering; compare samples, contigs, records, alleles, filters, INFO, FORMAT, and genotypes. Validate indexes separately. |
| BAM/CRAM | `samtools quickcheck`; compare canonical headers after only enumerated volatile `PG` fields; compare read/flag/stat summaries and a sorted semantic record digest including alignment fields, sequence, quality, and retained tags. |
| TSV/CSV | Compare schema and typed normalized rows sorted by a declared key. Integers and identifiers are exact; floating tolerances must be metric-specific and documented. |
| JSON/YAML/manifests/receipts | Canonical key ordering; remove only enumerated run IDs, timestamps, and absolute roots; require equality of all other semantic fields. |
| MultiQC/HTML | Compare extracted MultiQC data, module/sample inventory, and normalized metrics, not HTML bundle bytes. |
| Directories | Compare authoritative artifact roles and relative semantic paths; fail on missing or unexpected authoritative outputs. |
| Logs/benchmarks | Compare completion state, rule set, and resource contracts. Track runtime, cost, and utilization as bounded drift metrics, not biological equivalence. |

Each comparator result records:

- comparator name and version;
- input and reference digests;
- ignored fields with explicit reasons;
- exact mismatches and tolerance evaluations;
- pass/fail; and
- a final semantic-result digest.

A golden identity is the tuple:

`(command_id, DYEC tag, DayOA tag, fixture digest, reference identity, rendered-command digest, comparator schema version)`

Changing any tuple member creates a new candidate baseline; it may not silently
overwrite an approved one.

## Ursa exposure contract

Implement in an isolated Ursa worktree after the execution schema is stable.
Ursa must consume the installed DYEC canonical catalog/API rather than copy
command definitions.

For each command, show:

- canonical command ID and display name;
- repository, analysis class/type, platform, and data mode;
- DayOA tag and catalog validation version;
- slim-data profile and normalized digest;
- membership: core, extended, portable, run-input, or required-frozen;
- required source inputs and runtime parameters;
- cluster compatibility and blocked reason;
- last clean slim-data run, evidence URI, comparator version, and semantic
  equivalence result;
- current qualification status without hiding blocked or failed commands.

Provide filters for portable core, run-input core, kitchen sinks, and frozen
HIOMR2. A missing identity, fixture, mount, or compatible cluster must display a
specific disabled reason.

Acceptance evidence must include:

1. API/schema tests proving catalog values originate from DYEC;
2. authenticated browser capture of the literal Ursa URL;
3. captured background request and response showing the canonical command;
4. visible proof that HIOMR2 kitchen sink is present and marked
   `required-frozen`;
5. visible evidence links/status for completed slim runs; and
6. regression tests preventing UI filtering from hiding required failures.

Deployment is a separate ledger row and occurs only through the normal Ursa
release/deployment process.

## CI and monitoring design

### Pull requests

Run static and hermetic checks on every relevant PR:

- catalog schema and uniqueness;
- exact release pins;
- packaged fixture closure and normalized digests;
- source-path and manifest validation;
- rendered-command snapshots;
- target/rule graph assertions;
- semantic comparator unit fixtures; and
- Ursa catalog/API/UI contract tests when Ursa changes.

The live cluster lane is required for PRs that change command catalog,
execution, relevant DayOA rules/environments, slim fixtures, or comparators.
Trigger it by an explicit trusted label/manual gate, use the portable bounded
subset serially, and enforce cost and evidence-prefix checks. Do not expose AWS
credentials to untrusted fork code.

### Daily

- Bootstrap plus portable non-kitchen-sink core.
- One rotating non-HIOMR2 kitchen sink.
- Compare with the most recent approved golden at the same identity tuple.
- Stop on the first contract failure or cost guard.

### Weekly

- Full required portable core.
- All kitchen sinks, including the frozen HIOMR2 command when its persisted
  batch-ID contract supports repeatable test execution.
- All qualified run-input core commands.
- Two fresh-root repeats after a release-pair or fixture change; otherwise
  rotate equivalence repeats so every command is repeated within the defined
  monitoring window.

Monitors collect and report. They do not auto-fix source, mutate Slurm, create
mounts, increase budgets, or alter golden baselines.

## Evidence layout

The final evidence S3 root must be explicitly confirmed before first write.
Proposed established namespace:

```text
s3://lsmc-ssf-sequencing-data/derived/command-catalog/
  dyec-<dyec-tag>/
    dayoa-<dayoa-tag>/
      <UTC-stamp>/
        <command-id>/
          <attempt-or-repeat>/
```

Do not write until the bucket, prefix, encryption/ownership, and retention
contract are read-only verified.

Every command evidence directory contains:

```text
inventory.json
versions.json
cluster_preflight.json
catalog_entry.json
rendered_command.txt
rendered_command.sha256
fixture_manifest.json
fixture_digest.txt
analysis_root_receipts/
controller/
rule_logs/
artifact_inventory.json
comparators/
benchmarks_summary.tsv
cost.json
result.json
```

The local run index and compact receipts live under a timestamped
`docs/plans/` evidence directory. Large data remains in the approved S3
namespace, referenced by immutable object identity where available.

## Command templates

These are templates for execution after all prior gates pass; they are not
authorization to launch now.

Local activation:

```bash
cd /path/to/clean/dyec-16.1.18-worktree
source ./activate
```

Exact-tag headnode alignment:

```bash
dyec headnode configure \
  --profile lsmc \
  --region us-west-2 \
  --cluster cmd-catalog-tests
```

Catalog dry-run wave:

```bash
dyec tests command-catalog \
  --cluster cmd-catalog-tests \
  --profile lsmc \
  --region us-west-2 \
  --command-codes <comma-separated-wave-command-ids> \
  --evidence-s3-uri <confirmed-wave-evidence-s3-uri> \
  --executing-entity ubuntu \
  --parallel 1 \
  --timeout-minutes 720 \
  --poll-interval-seconds 30 \
  --output-dir <timestamped-local-evidence-directory> \
  --dry-run
```

Live wave uses the same exact arguments without `--dry-run`. Do not add
`--create-missing-mounts` unless a separately reviewed run-input row authorizes
the exact mount.

The built-in `dyec-released-core` selector is insufficient by itself because it
does not include the required HIOMR2 kitchen-sink command. Pass explicit,
reviewed command IDs or introduce a tested qualification-suite selector that
includes the frozen lane without altering its DayOA graph.

## Execution ledger

Status vocabulary:
`OPEN`, `IN_PROGRESS`, `SUCCESS`, `FAILED`, `BLOCKED_INPUT`,
`BLOCKED_IDENTITY`, `WAITING_DOUBLE_APPROVAL`, `SKIPPED_WITH_REASON`.

| ID | Gate / action | Acceptance evidence | Status |
|---|---|---|---|
| G0.1 | Record current cluster, versions, controllers, jobs, mounts, FSx, cost center, and processed spend | Raw timestamped outputs; observations above reconciled | `SUCCESS` |
| G0.2 | Preserve dirty-worktree boundaries | No modification to unrelated untracked DYEC files, canonical DayOA checkout, or dirty Ursa checkout | `SUCCESS` |
| R0.1 | Create clean DYEC `16.1.18` execution worktree | Detached clean worktree at `d0f0a06ef36117abb243650dc393e0568a8f7255`; annotated tag object verified | `SUCCESS` |
| R0.2 | Create dedicated DayOA `13.0.107` paired worktree | Detached clean worktree at `ab16caf9d8359753fb69d53c84c7662ee4855ab0`; annotated tag object verified | `SUCCESS` |
| R0.3 | Create isolated Ursa worktree | Clean branch `codex/cmd-catalog-slim-ursa-20260731` at `38a222094fcf6933cb98b50c491ebc270003e820` | `SUCCESS` |
| D0.1 | Validate all-cluster default slim-data paths | Explicit paths, sizes, readability, digests | `OPEN` |
| D0.2 | Validate DYEC/DayOA HG003 fixture parity | Exact recursive diff is empty; six DYEC TSV SHA-256 digests recorded in attempt log evidence | `SUCCESS` |
| D0.3 | Create versioned A1-only six-manifest fixture | Referential closure, schema tests, no CRAM, exact three FASTQs | `OPEN` |
| D0.4 | Prove A1 fixture selection does not change frozen HIOMR2 rule topology | Before/after command, target, and rule-graph comparison; only expected analysis-unit DAG fan-out differs | `OPEN` |
| I0.1 | Obtain persisted analytical batch ID from owning service | Owner-issued ID plus persistence/audit evidence | `BLOCKED_IDENTITY` |
| C0.1 | Validate catalog schema, pins, resources, and command rendering | Exact tag exposed stale test expectation; fix branch now passes the 163-test catalog/runner/transport fixture set | `SUCCESS` |
| C0.2 | Add tested suite selection that includes required frozen HIOMR2 | Selection test; no DayOA graph change | `OPEN` |
| H0.1 | Fix `dyec headnode jobs` dependency/exit-code contract | Live reproduction captured; shared bootstrap/SSM fix and focused tests pass; requires immutable release and live recheck | `IN_PROGRESS` |
| REL0.1 | Commit, push, and annotated-tag functional DYEC patch `16.1.19` | Commit `de8641b4ad294b325780d5045cb9a86fc246a198`; pushed branch; annotated remote tag resolves exactly | `SUCCESS` |
| REL0.2 | Self-pin DYEC `16.1.19`, commit, push, and annotated-tag configure release `16.1.20` | Both global configs and contract test pin `16.1.19`; clean pushed tag | `OPEN` |
| H0.2 | Configure headnode through exact `16.1.20` self-pin release | Headnode reports functional DYEC `16.1.19`, DayOA catalog pin `13.0.107`, and clean startup | `OPEN` |
| H0.3 | Repeat no-active-work and capacity/cost preflight | Zero unexpected controllers/jobs; cost/freespace report | `OPEN` |
| P1.1 | Render/dry-run bootstrap and portable core | Per-command render, graph, fixture, and exit evidence | `OPEN` |
| P1.2 | Render/dry-run frozen HIOMR2 | Frozen graph baseline; exact input contract; no modifications | `OPEN` |
| L2.1 | Run `simple-test` | Terminal success and complete evidence contract | `OPEN` |
| L2.2 | Run portable solo core serially | All solo rows terminal success | `OPEN` |
| L3.1 | Run non-HIOMR2 kitchen sinks serially | All required rows terminal success | `OPEN` |
| L3.2 | Run hybrid HIOMR and hybrid HIOMR kitchen sink | Exact HG003 1x input proof; terminal success | `OPEN` |
| L4.1 | Run required frozen HIOMR2 kitchen sink | Exact HG003 A1 inputs, persisted ID, frozen graph, terminal success | `BLOCKED_IDENTITY` |
| E5.1 | Repeat every successful portable command in fresh roots A/B | Identity tuples match; semantic comparators pass | `OPEN` |
| RR.1 | Establish minimal Illumina run fixture | Versioned portable fixture, provenance, validity tests | `BLOCKED_INPUT` |
| RR.2 | Establish minimal ONT run fixture | Versioned portable fixture, provenance, validity tests | `BLOCKED_INPUT` |
| RR.3 | Establish minimal Ultima run fixture | Versioned portable fixture, provenance, validity tests | `BLOCKED_INPUT` |
| RR.4 | Run/repeat all three run-analysis core commands | Clean A/B runs and semantic equivalence | `BLOCKED_INPUT` |
| U1.1 | Expose canonical DYEC catalog and qualification schema in Ursa | API tests; no copied catalog | `OPEN` |
| U1.2 | Implement clear command-catalog UI and filters | Required/frozen/blocked states visible | `OPEN` |
| U1.3 | Verify authenticated literal URL and background requests | Browser/API/screenshot evidence | `OPEN` |
| A1.1 | Add PR static/hermetic suite | Required CI checks green | `OPEN` |
| A1.2 | Add trusted, cost-bounded PR live lane | Manual/label gate, serial wave, evidence receipt | `OPEN` |
| A1.3 | Add daily monitor | Schedule, cost guard, evidence, alert path tested | `OPEN` |
| A1.4 | Add weekly full-core monitor | Includes frozen HIOMR2 and qualified run-input rows | `OPEN` |
| F1.1 | Final terminal-state and evidence audit | Every required row terminal; no hidden skips; objective truth stated | `OPEN` |

Current terminal-state summary:

- Terminal rows: `8`
- Non-terminal or blocked rows: `29`
- Required command suite complete: **no**
- Ursa exposure complete: **no**
- PR/daily/weekly monitor complete: **no**
- Overall objective complete: **no**

## Attempt log

Append one row for every execution or remediation attempt. Never overwrite a
prior result.

| UTC stamp | Ledger row | Command / action | Release pair | Root / evidence URI | Result | Failure class | Disposition |
|---|---|---|---|---|---|---|---|
| 2026-07-31T10:25Z | C0.1 | Exact-tag catalog/runner focused tests | DYEC `16.1.18` / DayOA `13.0.107` | local exact-tag worktree | `44 passed, 1 failed`; stale expected tag `13.0.61` versus rendered `13.0.107` | `CATALOG_METADATA` | Corrected Git-tag expectations on isolated fix branch; retained validated version separately |
| 2026-07-31T10:29Z | D0.2 | Recursive fixture parity and SHA-256 inventory | DYEC `16.1.18` / DayOA `13.0.107` | both exact-tag worktrees | Empty recursive diff; all six manifests identical; A1 resolves exact ILMN R1/R2 and primary-only ONT FASTQs | `FIXTURE_CONTRACT` | Parity gate passed; A1-only new fixture remains separate work |
| 2026-07-31T10:31Z | H0.1 | `dyec headnode jobs` live reproduction | headnode DYEC `16.1.17` | `cmd-catalog-tests` | Slurm header plus `ModuleNotFoundError: yaml`; CLI RC `0` | `RUNTIME_ENVIRONMENT` | Traced to duplicate Conda startup resetting to base plus masked startup failure |
| 2026-07-31T10:45Z | H0.1 / C0.1 | Shared bootstrap, SSM failure propagation, and pin-test repair | candidate DYEC `16.1.19` / DayOA `13.0.107` | isolated fix worktree | `163 passed`; shell syntax and diff checks pass | `DYEC_RUNNER` | Proceed to immutable release and live headnode recheck; no HIOMR2 rule changed |
| 2026-07-31T10:48Z | H0.1 | Full-suite/baseline comparison | candidate DYEC `16.1.19` | isolated fix and exact `16.1.18` worktrees | Full run `2419 passed, 11 skipped, 26 failed`; five catalog pin expectations fixed; remaining affected-file subset reproduces on exact tag as `21 failed, 52 passed` | `RUNTIME_ENVIRONMENT` | Treat remaining 21 and 31 Ruff findings as pre-existing baseline debt outside this release scope |
| 2026-07-31T10:52Z | REL0.1 | Commit, push, annotated tag `16.1.19` | DYEC `16.1.19` / DayOA `13.0.107` | branch `codex/cmd-catalog-slim-execution-20260731` | Commit `de8641b4ad294b325780d5045cb9a86fc246a198`; annotated tag object `3074ca890b56debcb77be20a9bdfe6e6865d0da7`; branch and tag pushed | `DYEC_RUNNER` | Functional release complete; proceed to explicit self-pin release |

## Approval log

This section records approvals only after they occur. The current plan grants
no approval to edit the frozen HIOMR2 boundary, increase a budget, destroy
resources, administer Slurm/jobs, or create an unreviewed mount.

| UTC stamp | Protected action | Exact scope | Approval 1 | Restatement | Approval 2 | Performed |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — |

## Final completion test

The suite may be reported complete only if:

- all bootstrap, portable core, frozen HIOMR2, and run-analysis core rows are
  terminal `SUCCESS`;
- each required command has two fresh-root semantically equivalent results;
- no required command was hidden, silently skipped, or substituted;
- evidence is durable and tied to immutable release/input/comparator identities;
- Ursa visibly exposes canonical catalog and qualification state;
- PR, daily, and weekly paths are implemented and have successful test receipts;
- all fixes followed the generalization and immutable-release contracts; and
- any HIOMR2 kitchen-sink source change, if ultimately needed, has a complete
  two-approval record.
