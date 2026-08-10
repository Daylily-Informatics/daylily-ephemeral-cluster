# prod-cand-260809 DayOA 13.4.9 HG002 5x+5x HIOMR2 execution ledger

Created: `2026-08-10T01:41:44Z`

Ledger path: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster/docs/plans/20260810T014144Z_prod_cand_1349_hg002_5x5x_hiomr2_ledger.md`

Objective: On existing cluster `prod-cand-260809`, create a fresh `init-test`
analysis from exact annotated DayOA tag `13.4.9`; use the authoritative HG002
approximately-5x Illumina plus 5x ONT slim-data inputs; initialize DayOA in one
persistent `ubuntu` Bash-login tmux pane; dry-run the literal HIOMR2 kitchen-sink
mega closure plus Inflection analytical packaging with `-j 333 -p -T 1 -k -n`;
and, only if that exact plan is valid, repeat it with only `-n` removed.

## Gate 0 inventory freeze

- Execution repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch
  `260809-prod-candidate`, commit `aa15d5b45d9e2b0d68a76c21a729ed8f8cf8d995`.
  The worktree contains extensive pre-existing untracked plans and artifacts;
  this ledger is the only local file owned by this execution.
- Local DayOA evidence repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`,
  branch `260809-prod-candidate`, clean at commit
  `4b1fab794de95796235f16deb081c161cf021167`; private origin
  `git@github.com:lsmc-bio/daylily-omics-analysis.git`.
- Release identity: annotated tag object
  `185fba7e7844eadf0cf692d538c24af80e39874f` named `13.4.9`, peeled commit
  `4b1fab794de95796235f16deb081c161cf021167`.
- DYEC runtime: local and headnode `16.1.44`.
- Explicit AWS scope: profile `lsmc`, region `us-west-2`, cluster
  `prod-cand-260809`.
- Live cluster at `2026-08-10T01:42Z`: ParallelCluster `3.15.0`, cluster/stack
  `UPDATE_COMPLETE`, compute fleet `RUNNING`, headnode
  `i-0ee0f65150b39b976` / `ip-10-0-0-13`, Ubuntu `22.04.5`, `ubuntu` remote user.
- FSx at `2026-08-10T01:43Z`: `9,613,144,064 KiB` total,
  `9,613,033,984 KiB` available, `1%` used.
- Controller baseline: zero DayOA controllers, zero Slurm jobs, zero tmux panes,
  and no stale controller receipts.
- Canonical proposed analysis root:
  `/fsx/analysis_results/prod-cand-260809/init-test`. It must be proved absent
  before creation; no alternate root may be inferred.
- Stable identity: `DAYOA_AGENT_ID=codex-prod-cand-init-test-1349-20260810`,
  `DAYOA_AGENT_KIND=codex`, `DAYOA_HUMAN_REQUESTOR=jmajor`,
  `DAYOA_TMUX_SESSION=dayoa_init_test_hg002_5x5x_1349_20260810`, and
  `DAYOA_LEDGER_PATH` equal to this ledger path.
- The current DYEC catalog is validated at DayOA `13.4.9`. Its BJuice mega
  entry proves the core target family, but it is a full-coverage/SeqOne-v2
  contract and therefore cannot silently replace the user's slim-data plus
  analytical-package request. The exact tagged HG002 5x5x overlay and literal
  target closure will be validated in the clone.
- No Slurm administration, job/controller cancellation, lock takeover,
  destructive AWS action, export, teardown, or budget-cap change is authorized.

## Control ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| RUN-001 | Contracts | Read DayOA, tmux, DYEC, analysis-lock, and ledger instructions | SUCCESS | active_product_contract | Gate 0 | orchestrator | Required instruction files and current DYEC help read before headnode writes |  | Supported execution boundary fixed |
| RUN-002 | Cluster/release | Verify live cluster, empty controller baseline, and exact annotated `13.4.9` identity | SUCCESS | config_or_startup_contract | Gate 0 | orchestrator | Cluster/headnode/FSx/controller JSON and local tag object/peeled commit recorded above |  | Live scope and immutable release proven |
| RUN-003 | Analysis root | Prove proposed root unused; record visit; acquire lock; create one-pane persistent tmux | SUCCESS | legitimate_safety_handling | Gate 0 | orchestrator | Root and parent were absent; write visit recorded; lock acquired by `codex-prod-cand-init-test-1349-20260810`; one window/pane `%0` in `dayoa_init_test_hg002_5x5x_1349_20260810`; Bash flags include `i` and `login_shell=yes` |  | Fresh persistent execution boundary established as `ubuntu` |
| RUN-004 | Clone | Run `day-clone -t 13.4.9 -d init-test` and prove private origin, exact detached HEAD, annotated tag, and clean checkout | BLOCKED | config_or_startup_contract | Gate 1 | orchestrator | Main repository reached clean detached `HEAD=4b1fab794de95796235f16deb081c161cf021167`, private SSH origin, and exact annotated tag object `185fba7e...`; `day-clone` then failed twice cloning gitlink `b7d0964...` from `https://github.com/lsmc-bio/TrusSV.git` with `fatal: could not read Username for 'https://github.com': terminal prompts disabled` and returned `Error: Git clone failed with exit code 1.` | Tag `13.4.9` declares the new private TrusSV submodule over unauthenticated HTTPS, while the strict temporary DayOA deploy-key environment supports the catalog's SSH parent transport and no HTTPS credential or permitted URL rewrite is configured | Clone is partial and deliberately not accepted as a successful exact-tag workspace; requires an owner-approved transport/release correction |
| RUN-005 | Inputs | Prove exact regular HG002 approximately-5x ILMN and 5x ONT slim-data paths plus six-manifest identity/lineage closure | BLOCKED | active_product_contract | Gate 2 | orchestrator | Not attempted after RUN-004 hard failure | Exact-tag clone contract is incomplete | No manifests or inputs were staged or changed |
| RUN-006 | Initialization | Run separate `source dyoainit` and `dy-a slurm hg38` commands in the persistent pane | BLOCKED | config_or_startup_contract | Gate 2 | orchestrator | Not attempted after RUN-004 hard failure | Exact-tag clone contract is incomplete | No DayOA environment was initialized |
| RUN-007 | Dry run | Run exact literal kitchen-sink mega plus Inflection analytical package closure with `-j 333 -p -T 1 -k -n`; require RC 0 and inspect DAG/config/input/target closure | BLOCKED | contract_test | Gate 3 | orchestrator | No `dy-r` command was issued | Exact-tag clone contract is incomplete | No dry-run plan exists |
| RUN-008 | Live run | If RUN-007 is valid, repeat the identical command once with only `-n` removed and capture controller/queue evidence | BLOCKED | feature_implementation | Gate 4 | orchestrator | DYEC inventory at `2026-08-10T01:52:48Z`: zero controllers and zero Slurm jobs | Dry-run gate did not run because the clone failed | No live workflow was submitted |
| RUN-009 | Handoff | Record exact tmux, root, tag/commit, command, controller state, jobs, lock state, and objective boundary | SUCCESS | legitimate_safety_handling | Gate 5 | orchestrator | Partial checkout preserved at the exact root; one idle Bash tmux pane remains; owned write lock was released and verified `unlocked`; final DYEC inventory has zero controllers/jobs and one tmux pane |  | Blocker and untouched execution boundary recorded without destructive cleanup |

## Acceptance boundary

The requested launch is complete only when the clone, exact inputs/manifests,
dry-run plan, and live controller start are proven. A successful launch is not a
claim that the long-running workflow or Inflection package has completed.

## Evidence log

- `2026-08-10T01:42Z` to `01:43Z`: DYEC proved cluster, headnode, FSx, and
  empty controller/Slurm/tmux baseline.
- The proposed root and its cluster parent were absent. The root was created,
  visited, locked, and assigned one persistent interactive Bash-login tmux pane
  as `ubuntu` before `day-clone` was issued.
- `day-clone -t 13.4.9 -d init-test` cloned the main private repository and
  checked out the exact peeled commit, then failed its mandatory recursive
  submodule clone twice. `.gitmodules` at the tag explicitly records
  `url = https://github.com/lsmc-bio/TrusSV.git`; the gitlink remains
  uninitialized (`-b7d0964...`). No Git URL rewrite, credential fallback,
  skipped-submodule behavior, or partial-clone workflow launch was used.
- The write lock was released after the hard failure. At
  `2026-08-10T01:52:48Z`, DYEC reported zero controllers, zero Slurm jobs, no
  stale receipts, and the single idle tmux pane at the partial checkout.

## Final report

All rows terminal: `yes`

Objective complete: `no`

Status counts:

- SUCCESS: `4`
- BLOCKED: `5`

Changed local files:

- This execution ledger only.

Live effects:

- Created and preserved the partial analysis root and its one idle tmux pane.
- Submitted no workflow controller or Slurm job.
- Released the analysis write lock.

Unblock condition: provide an owner-approved exact authentication/transport
contract for the private TrusSV gitlink. Because `13.4.9` is immutable, the
clean source fix is normally a new DayOA patch tag whose `.gitmodules` uses the
supported authenticated transport and whose recursive `day-clone` is proven.
An exact-tag one-off URL/credential override would be fallback behavior and was
not attempted without explicit approval.

## 2026-08-10 durable repair amendment

The user explicitly resumed this ledger with the instruction to make the fix
durable across newly built clusters. The earlier terminal snapshot remains the
historical result for `13.4.9`; the rows below now control the replacement
release and resumed launch.

Fresh diagnosis changed the preferred repair. Merely rewriting the submodule
URL from HTTPS to SSH would still ask the repository-scoped DayOA deploy key to
authenticate to a second private repository. New headnodes intentionally
receive only the DayOA and DYEC deploy-key contracts, so that would preserve a
cross-repository bootstrap dependency instead of fixing it. The durable design
is to vendor the exact 28-file, GPL-3.0 TrusSV `v0.3.1` source tree into DayOA,
record its origin commit and Git tree object, and make the rule verify the
vendored tree from the enclosing exact-tag checkout. This keeps the bootstrap
fully satisfied by the existing DayOA deploy key and adds no credential or
transport fallback.

Frozen upstream identity:

- repository: `https://github.com/lsmc-bio/TrusSV.git`
- tag: `v0.3.1`
- commit: `b7d0964a0c55fa1ed720d3106c4db06826f8e73d`
- root tree: `a61c4dd11ad7cda765c407e3b3b5cfb558c273d9`
- tracked files: `28`
- license: `GPL-3.0-or-later`

| ID | Area | Requirement | Status | Category | Approval Gate | Evidence / terminal note |
|---|---|---|---|---|---|---|
| FIX-001 | Diagnosis | Freeze the actual new-headnode credential boundary and select a no-fallback source contract | SUCCESS | config_or_startup_contract | Repair Gate 0 | Parent deploy key cannot satisfy a second private repository; exact TrusSV commit/tree recorded above |
| FIX-002 | DayOA source | Replace the gitlink with the byte-identical vendored upstream tree plus a provenance receipt | SUCCESS | feature_implementation | Repair Gate 1 | Staged vendored path has 28 files and Git tree `a61c4dd...`, exactly matching upstream; `.gitmodules` removed |
| FIX-003 | DayOA contract | Verify the enclosing checkout's vendored tree object in the HIOMR2 rule and add focused regressions | SUCCESS | contract_test | Repair Gate 1 | Rule checks committed tree plus working-path cleanliness; focused NICU, Inflection, and SeqOne v2 suite passed 81/81 |
| FIX-004 | DayOA release | Test, commit, push, and publish a new immutable annotated patch tag | SUCCESS | release | Repair Gate 2 | Annotated `13.4.10` tag object `d7b1a14b...` peels to pushed commit `118f70f4...`; `13.4.9` was not moved |
| FIX-005 | DYEC release | Pin source and packaged catalogs to the replacement DayOA tag, test parity, self-pin, and publish a new immutable DYEC tag | SUCCESS | release | Repair Gate 3 | Pushed commit `f61d83de...` and annotated tag `16.1.45` pin DayOA `13.4.10`; pushed self-pin commit `9c41e266...` and annotated tag `16.1.46` make that corrected bootstrap contract the new-cluster DYEC payload |
| FIX-006 | Candidate proof | Refresh `prod-cand-260809` through DYEC and prove the corrected exact-tag clone as `ubuntu` | SUCCESS | config_or_startup_contract | Repair Gate 4 | Refreshed headnode reports DYEC `16.1.46` and catalog DayOA `13.4.10`; fresh proof clone `/fsx/analysis_results/prod-cand-260809/init-test-13410-bootstrap-proof` completed with no URL rewrite or credential injection; actual `init-test` checkout was then moved cleanly to exact tag `13.4.10` |
| FIX-007 | Resumed launch | Re-enter the locked `init-test` root, initialize separately, prove exact inputs/targets, dry-run with the requested flags, then remove only `-n` if valid | IN_PROGRESS | feature_implementation | Repair Gate 5 | The root is locked and the workflow remains stopped while the canonical slim-data input defect is repaired and validated |

The earlier `All rows terminal: yes` and `Objective complete: no` statements
apply only to the stopped `13.4.9` attempt and are superseded for current work
by this amendment.

## 2026-08-10 HG002 5x-by-5x slim-data correction amendment

Input validation proved that three canonical BJuice objects whose names claim
`5x` actually contain full-coverage data. This is a source-fixture defect, not
a workflow-selection defect, so the run remains stopped until the canonical S3
objects are durably corrected for this and future clusters.

Authoritative correct Illumina objects already present on S3:

- `NovaSeqX_WHGS_TruSeqPF_HG002-007/downsampled/HG002_5x_R1.fastq.gz`:
  `3,899,321,181` bytes, SHA256
  `0a3282844bc53ac600566899b9a02d1dd556befe63269b9b09f2c8be17780eb3`,
  `60,277,137` reads and `9,052,461,224` bases.
- `NovaSeqX_WHGS_TruSeqPF_HG002-007/downsampled/HG002_5x_R2.fastq.gz`:
  `4,000,405,121` bytes, SHA256
  `6b365ebb3ef333783cc4f85bedd881ebcd8356d66f5a040dfdbe666ec624e4d7`,
  `60,277,137` reads and `9,053,152,391` bases.
- Combined observed depth is `5.862704556x` against the frozen primary-contig
  denominator of `3,088,269,832` bases.

Mislabeled canonical replacement targets under
`s3://lsmc-dayoa-references-usw2/genomic_data/organism_reads_slim/fastq/H_sapiens/giab/bjuice_preval_2026/HG002/`:

- `illumina/HG002_BJUICEPREVAL_ILMN_5x_R1.fastq.gz`: `37,003,624,993`
  bytes, metadata SHA256 `897f3d126efed5da49641534c7c903167105db407eeef0569011f2ca5e22cbe7`.
- `illumina/HG002_BJUICEPREVAL_ILMN_5x_R2.fastq.gz`: `37,335,094,934`
  bytes, metadata SHA256 `617f6e52ea4251b1b544c5153863482f8a3ce780c3cc93b738ecae556886c476`.
- `ont/HG002_BJUICEPREVAL_ONT_5x.fastq.gz`: `62,270,705,691` bytes,
  metadata SHA256
  `9bd2303e9a7c63e78b8e76cd8110ebad3b34828794336fd10b29393f320b6e21`;
  its `61,029,539,852` sequenced bases measure `19.7617x`.

The earlier deterministic ONT 5x recipe is preserved in
`docs/plans/20260810T024728Z_rebuild_hg002_5x5x_slim_fixture.sbatch`: SeqKit
`2.13.0` exact package SHA256 `538ff4ab...e6d4`, seed `1340`, proportion
`0.253014346781`, compression level `1`, and strict expected output identity of
`16,810,459,174` bytes, `1,963,980` reads, `15,447,946,531` bases,
`5.002136268x`, SHA256
`8758ef77c51ac473c145cbd777108373960f0d82c3f62d159e5d87d440f6cad1`.

At `2026-08-10T03:27Z`, the human requestor explicitly accepted an approximate
ONT input in the range `2.5x` through `7.5x`.  The fast repair lane therefore
uses the known source coverage and read count: the full source has `7,759,331`
reads at `19.7617x`, so the first `1,963,980` complete FASTQ records estimate
approximately `5x`.  The protected `i96nvme` job must stop decompression after
that prefix, validate the exact read count and complete gzip/FASTQ structure,
measure sequenced bases and depth, and emit compressed plus uncompressed-stream
SHA256 receipts.  No estimated artifact is accepted merely from the arithmetic.

Protected job `4` completed successfully in `18:00`, with `1,074` measured
seconds from download start through FSx publication.  Its selected prefix has
`1,963,980` reads, `14,805,689,859` bases, measured depth `4.794169766x`,
`15,086,588,357` compressed bytes, SHA256
`f35e79a5601271f6503455a952cc04892f452b078ad45941cbf27ae77f4ed45b`,
and uncompressed FASTQ stream SHA256
`7441b3018d02fe6c0c318bf2904ae7d7bb5c08093ddaa3bbd7e876b3e4ec8be0`.
The receipt reports passing gzip-to-EOF, FASTQ-to-EOF, exact-read-count, and
accepted-depth-range checks.  Re-reading the published FSx file independently
reproduced the compressed SHA256.  The exact/random lane also completed, but
took `50:38`; it is preserved as comparison evidence and is not the selected
under-20-minute repair.

The selected ONT file and the already-existing verified Illumina pair now form
the complete tree at `/fsx/analysis_results/tmp_slinm_fq/hg002_5x5x`.  A second
three-file SHA256 pass from that final tree matched all expected values.  The
three old full-coverage objects were copied, without changing canonical keys,
to the honest quarantine prefix
`s3://lsmc-dayoa-references-usw2/genomic_data/organism_reads_slim/fastq/H_sapiens/giab/_quarantine/full_coverage_mislabeled/20260810T034514Z/`;
HEAD validation matched all three original sizes and metadata SHA256 values.

The independently implemented rapidgzip lane, protected job `5`, completed in
`14:57` (`891` measured seconds) and reproduced the same `1,963,980` records,
`14,805,689,859` bases, `4.794169766x` depth, `15,086,588,357` byte count, and
uncompressed FASTQ SHA256
`7441b3018d02fe6c0c318bf2904ae7d7bb5c08093ddaa3bbd7e876b3e4ec8be0`.
Its compressed SHA256 is
`c096d055e15d323357349008683cb579178c2f459f1495a0b9adcba81ad69b20`,
while job `4` produced
`f35e79a5601271f6503455a952cc04892f452b078ad45941cbf27ae77f4ed45b`;
the first ten
gzip bytes prove that only the four-byte gzip mtime header differs before the
identical deflate stream prefix.  The durable follow-on script
`docs/plans/20260810T040500Z_extract_hg002_ont5x_repro96.sbatch` therefore uses
`pigz -n` for a no-name, zero-mtime gzip header; the selected replacement
object remains bound to its exact compressed and uncompressed identities.

During that header inspection, a two-positional-argument `xxd` invocation
mistakenly treated the redundant rapid-lane FSx staging path as its output and
replaced only that copy with a 124-byte hex dump.  The selected final tree, DRA
export, canonical S3 keys, quarantine copies, and all receipts were unaffected.
The intact rapid-lane NVMe file was copied to an FSx partial path, verified at
`15,086,588,357` bytes and SHA256
`c096d055e15d323357349008683cb579178c2f459f1495a0b9adcba81ad69b20`,
then atomically restored
over the 124-byte staging file under the owned analysis-root guard.

After the human requestor supplied the required second explicit destructive
approval, exactly the three canonical BJuice keys were replaced.  Destination
HEAD proof now reports R1 `3,899,321,181` bytes with metadata SHA256
`0a3282844bc53ac600566899b9a02d1dd556befe63269b9b09f2c8be17780eb3`,
R2 `4,000,405,121` bytes with metadata SHA256
`6b365ebb3ef333783cc4f85bedd881ebcd8356d66f5a040dfdbe666ec624e4d7`,
and ONT `15,086,588,357` bytes with metadata SHA256
`f35e79a5601271f6503455a952cc04892f452b078ad45941cbf27ae77f4ed45b`,
uncompressed FASTQ SHA256
`7441b3018d02fe6c0c318bf2904ae7d7bb5c08093ddaa3bbd7e876b3e4ec8be0`,
and measured
depth `4.794169766x`.  All three objects carry fixture profile
`hg002_bjuice_verified_5x5x_fastq`, `application/x-gzip`, and AES256 server-side
encryption.  No other canonical key was changed; the prior full-coverage bytes
remain only under the honest timestamped quarantine prefix.

| ID | Area | Requirement | Status | Approval Gate | Evidence / terminal note |
|---|---|---|---|---|---|
| DATA-001 | S3 inventory | Prove which correct 5x objects exist and which canonical names contain full coverage | SUCCESS | Data Gate 0 | Exact keys, byte sizes, hashes, read/base counts, and depth evidence recorded above; bucket versioning is not enabled |
| DATA-002 | ONT rebuild | Produce a validated ONT input within the explicitly accepted `2.5x`-`7.5x` band and emit a machine-readable receipt | SUCCESS | Data Gate 1 | Prefix job `4` completed in `18:00`; measured `4.794169766x` and all receipt gates passed; exact/random job `1` completed independently in `50:38` and was not selected |
| DATA-003 | Replacement staging | Stage and independently validate the correct Illumina pair plus rebuilt ONT file | SUCCESS | Data Gate 2 | Final FSx tree and three-file SHA receipt pass; no-delete DYEC DRA `dra-02bf97a24798ac8b0` task `task-0ca854916eeec75cc` succeeded to `s3://lsmc-dayoa-staging-usw2/codex/hg002-5x5x-repair/20260810T035206Z/tmp_slinm_fq/hg002_5x5x/`; all three S3 object sizes match |
| DATA-004 | Recoverability | Back up the three existing full-coverage objects to one exact timestamped archive prefix | SUCCESS | Data Gate 3 | Three server-side copies completed under the timestamped `full_coverage_mislabeled` quarantine prefix and were HEAD-verified against original sizes and metadata hashes; quarantine remained intact after the separately approved canonical replacement |
| DATA-005 | Canonical repair | Replace exactly the three mislabeled canonical keys and prove their final identities | SUCCESS | Data Gate 4, explicit second approval | Second approval received; exactly three canonical objects were server-side replaced; HEAD size, content type, encryption, profile, read/base/depth, compressed SHA256, and ONT raw-stream SHA256 metadata match the verified fixture; quarantine remains intact |
| DATA-006 | Workflow proof | Make `init-test-x2` consume the corrected canonical 5x-by-5x surface, dry-run, then remove only `-n` if the plan is valid | IN_PROGRESS | Repair Gate 5 | User superseded the destination with exact fresh analysis ID `init-test-x2` and required the latest created DayOA release `13.4.10` |
| DATA-007 | DYEC catalog | Bind the BJuice command and packaged six-manifest fixture to the corrected three-file identities and requested `-j 333 -p -T 1 -k` contract | SUCCESS | Data Gate 2 | Source and payload catalogs are byte-identical; packaged fixture carries the measured 5.862704556x ILMN / 4.794169766x ONT identities; focused catalog/resource/manifest suite passes 28/28; pushed catalog commit `ea0ef45f...` / annotated tag `16.1.47` and self-pin commit `268b06f7...` / annotated tag `16.1.48` |

## 2026-08-10 `init-test-x2` clean-cluster acceptance amendment

The human requestor superseded the earlier destination and release selections:
the controlling clone is now exactly `day-clone -t 13.4.10 -d init-test-x2` in
tmux `dayoa_init_test_x2_hg002_5x5x_13410_20260810`. The acceptance criterion
also requires any encountered prerequisite failure to be repaired in checked-in
DYEC or DayOA code so a headnode created de novo by `dyec create` can execute the
catalog command without a cluster-local workaround.

At `2026-08-10T04:20Z`, the proposed root and tmux name were both absent and the
obsolete `init-test` lock had been released. The required pre-clone command
`dyec analysis visit --mode write` then failed closed because the fresh analysis
root did not yet exist. This exposed a long-recorded bootstrap contradiction:
the safety contract requires visit/lock ownership before `day-clone` writes,
but the public analysis-lock CLI required a prior manual `mkdir`. No directory,
clone, manifest, controller, or Slurm job was created after that failure.

The durable DYEC correction makes only an explicit `write` visit or `write`
lock acquisition initialize the exact requested
`/.../analysis_results/<owner>/<analysis_id>` directory. It first requires the
enclosing `analysis_results` mount to exist. Read-only visits and
`unlock`/`delete`/`kill` operations continue to fail on a missing analysis root,
so the change does not add path discovery, destructive fallback, or mount-tree
creation.

| ID | Area | Requirement | Status | Approval Gate | Evidence / terminal note |
|---|---|---|---|---|---|
| BOOT-001 | Fresh-root contract | Reproduce the pre-clone failure without manually creating `init-test-x2` | SUCCESS | Clean-cluster Gate 0 | Headnode DYEC `16.1.48` returned `Analysis root does not exist`; exact root remained absent |
| BOOT-002 | Durable DYEC fix | Initialize only a missing exact analysis directory for explicit write visit/lock operations | SUCCESS | Clean-cluster Gate 1 | `daylily_ec/analysis_lock.py` now requires the enclosing `analysis_results` directory and preserves fail-closed behavior for read/destructive modes |
| BOOT-003 | Regression proof | Prove analysis CLI, workflow controller, DayOA clone, resource packaging, and corrected catalog contracts | SUCCESS | Clean-cluster Gate 2 | Analysis/CLI/controller suite passed 270/270; clone/workflow/create-resource/catalog suite passed 262/262; focused Ruff fatal-error and diff checks passed |
| BOOT-004 | Immutable release | Commit, push, annotate, self-pin, and refresh the candidate headnode | SUCCESS | Clean-cluster Gate 3 | Repair commit `970a9e3c...` / annotated tag `16.1.49` and self-pin commit `4a4fac9b...` / annotated tag `16.1.50` are pushed; source and packaged create defaults pin exactly `16.1.49`; supported `dyec headnode configure` completed and `dyec headnode run 'dyec --version'` returned `16.1.50` |
| BOOT-005 | Exact clone and catalog run | Retry from absent `init-test-x2`, prove exact tag/input identities, dry-run, and remove only `-n` if valid | IN_PROGRESS | Clean-cluster Gate 4 | CLI-only proof confirmed the root remains absent and exposed the catalog target mismatch recorded below; no manual root initialization is permitted |

## 2026-08-10 analytical Inflection catalog amendment

The documented six-manifest gate is intentional: `catalog render` and
`catalog launch` require an explicit `--manifest-dir` rather than silently
selecting test inputs. DYEC `resources-dir` returned the immutable packaged
`16.1.50` payload, and naming its exact
`hg002_bjuice_verified_5x5x_fastq` directory produced a valid render. No source
change is required for that explicit-input safety contract.

That render exposed a separate product defect in the newly added command row.
The requested and DayOA-documented operation is analytical Inflection packaging,
but `inflection-bjuice-product-v0.2` was wired to the customer SeqOne-v2 release
target and unresolved `HIOMR2_SEQONE_V2_CONFIG_FILE` plus
`SEQONE_DELIVERY_BATCH_ID` environment prerequisites. The public catalog CLI
does not inject those shell-only values, and this request supplied no
owner-reviewed SeqOne-v2 release snapshot or delivery identity. Launching that
row would therefore fail on every de novo cluster or invent a release contract.

The corrected row follows the checked-in DayOA operator contract: it targets
`produce_sentdhiomr2_inflection_analytical_package`, sets
`hiomr2_inflection_package_mode=analytical`, and binds
`seqone_delivery_batch_id` to the explicit controller `ANALYSIS_ID`. It contains
no `--configfile`, SeqOne-v2 target, or unresolved release environment variable.

| ID | Area | Requirement | Status | Approval Gate | Evidence / terminal note |
|---|---|---|---|---|---|
| CATBOOT-001 | CLI routing | Use public DYEC catalog/headnode commands rather than an interactive SSM workaround | SUCCESS | Catalog Gate 0 | `headnode configure`, `headnode run`, `resources-dir`, `catalog show`, and `catalog render` were used; no new interactive SSM command was issued |
| CATBOOT-002 | Explicit inputs | Name the exact versioned packaged HG002 six-manifest fixture | SUCCESS | Catalog Gate 0 | `/Users/jmajor/.config/daylily/resources/16.1.50/examples/staging/hg002_bjuice_verified_5x5x_fastq`; render preserved DayOA `13.4.10`, `-j 333 -T 1 -p -k -n`, Ubuntu, RnD, and `init-test-x2` |
| CATBOOT-003 | Analytical package | Remove customer-release-only prerequisites from the requested analytical catalog command | SUCCESS | Catalog Gate 1 | Source/payload catalogs are byte-identical; exact target and `$ANALYSIS_ID` binding render with no SeqOne-v2 config or delivery environment dependency |
| CATBOOT-004 | Regression proof | Prove parser, fixture identity, DayOA 12 manifest, resource, CLI renderer, and controller contracts | SUCCESS | Catalog Gate 2 | Focused catalog suite passed 35/35 after assertion correction; expanded catalog/CLI/controller suite passed 295/295; diff parity and whitespace checks passed |
| CATBOOT-005 | Immutable release and candidate refresh | Publish and deploy the corrected catalog before any clone/controller launch | IN_PROGRESS | Catalog Gate 3 | Release pending; `init-test-x2` remains absent |
