# Dayhoff, DayOA, DYEC, and HIOMR2 5x5 release-validation ledger

Controlling request: incorporate Dayhoff handoff commit
`13259de0c15e47b2237ca29e9ed1dab5ebdc5333` into a new versioned release,
release the prepared DayOA and DYEC candidates with exact pins, update the
operator DYEC installation, force-configure the exact active headnode or
headnodes, and run the verified 5x ILMN plus 5x ONT slim-data Bjuice and
Inflection packaging workflow through attributable `rc=0`.

Ledger path:
`docs/plans/20260827T121120Z_dayhoff_dayoa_dyec_5x5_release_validation_ledger.md`

## Authorization and boundaries

- Source integration, tests, commits, pull requests, ordinary green merges,
  annotated release tags, headnode `configure --force`, and the requested
  DayOA dry/live validation are authorized.
- The validation must use the supported public DYEC catalog/workflow boundary,
  an explicit released DayOA tag, an exact supplied six-manifest fixture, and
  the same analysis capsule from dry proof to live continuation.
- No raw `snakemake`, pinned-source mutation, inferred input replacement,
  Slurm administration, analysis export, S3 result publication, Slack
  mutation, result cleanup, FSx deletion, or cluster teardown is authorized.
- Existing dirty user checkouts are evidence sources only. Releases use clean
  isolated worktrees and must not absorb unrelated user files.
- This is a fresh-forward release. Completed analyses are not recalled or
  restarted, and no previous-result reuse contract or alternate recall target
  will be added. The validation capsule runs the complete ordinary production
  Bjuice plus Inflection DAG.
- The pre-`dy-r` global artifact inventory is removed. DAG PNG rendering is
  retained, and explicit DayOA Snakemake targets write the existing artifact
  and lineage TSV schemas for SeqQC, solo kitchensink, and Bjuice products.
  The corresponding catalog target lists will include those manifest rules;
  this user-facing target-shape change is explicitly approved.

## Gate 0 inventory

- Dayhoff GitHub default branch `jemdev10` now contains the complete
  prerequisite line and supplied handoff through PR #197, with release
  evidence through PR #198. Annotated tag `9.0.30` points to merged default-
  branch commit `b254238ff8a9831f6e21dec7bccd017125b565e2`.
- The ordinary Dayhoff checkout is dirty and is not a release source. A clean
  integration worktree will begin at `origin/jemdev10`, advance through the
  complete `origin/main` prerequisite line, and then apply `13259de0`.
- DayOA candidate worktree:
  `/Users/jmajor/projects/lsmc/.codex-worktrees/hiomr2-16-0-12-integration/daylily-omics-analysis`;
  branch `codex/hiomr2-16-0-12-integration`; head `e2516ff5`; maximum numeric
  tag `16.0.11`; candidate release `16.0.12`.
- Sentieon CLI PR #4 merged at
  `50aeace1466682e8941ad24127256bbba36151b9`; annotated tag `1.7.3i` is
  published and verified. Upstream issue #35 remains open without a vendor
  response. It is retained as future clarification, not a release blocker:
  Hybrid small variants keep the existing `-b` scope contract, while
  `--haploid_bed` is restricted to isolated CNV/SV.
- DYEC candidate worktree:
  `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-19-0-33-dayoa-16-0-12`;
  branch `codex/dyec-19-0-33-dayoa-16-0-12`; head `f6aca8d2`; maximum numeric
  tag `19.0.32`; candidate release `19.0.33`.
- The requested operator checkout
  `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` contains user-owned
  modified and untracked evidence. It must not be reset, cleaned, or switched
  destructively.
- The applicable Ganon2 broad blood/oral change from operator branch
  `codex/ganon2-broad-blood-oral-dyec` is already represented in the isolated
  candidate by commit `ebf11678`. Its stable patch ID
  `88367c27968db6ac31c1688f44569b7df9b024f7` exactly matches operator commit
  `6e10f4f3`; it must not be cherry-picked a second time. Unrelated
  BloodBridge/campaign commits from the operator branch are out of scope.
- The active catalog fixture is the explicit
  `hg002_bjuice_verified_5x5x_fastq` six-manifest profile. The exact Bjuice plus
  Inflection command, cluster, state file, profile, cost center, and analysis
  identity remain to be resolved through the public CLI before launch.

## Control ledger

| ID | Area | Requirement | Status | Category | Gate | Evidence / blocker | Terminal note |
|---|---|---|---|---|---|---|---|
| DH-001 | Dayhoff | Integrate the complete `main` sweeper prerequisite line and supplied handoff into a clean branch from the actual default `jemdev10`. | SUCCESS | feature_implementation | Gate 1 | Clean branch advanced `ee0cef67` through `3fbf3a9e` and applied handoff as `b15444f`. | Full prerequisite line and supplied receipt are present without touching the dirty ordinary checkout. |
| DH-002 | Dayhoff | Run focused and broad attributable tests, merge through a green PR without admin override, and push annotated tag `9.0.30`. | SUCCESS | contract_test | Gate 2 | PR [#197](https://github.com/lsmc-bio/dayhoff/pull/197) merged normally as `78436daa555fc13aed52439e7968470c7bff0bb2` after exact-head `3c09e88` passed 332 focused tests, Ruff, diff checks, JavaScript/Python/aggregate CodeQL, CodeRabbit approval, and Codex review. Review hardening added deployment-scoped paths, strict S3 bucket/prefix contracts, credential-free sidecar config, exact least-authority binds, dedicated writable SQLite directories, retired-key cleanup, fail-closed placement config validation, and the Ursa `11.0.50` pin. Evidence PR [#198](https://github.com/lsmc-bio/dayhoff/pull/198) merged as `b254238ff8a9831f6e21dec7bccd017125b565e2`. Annotated tag object `44eb58ccc897fa3c666d33ab4d9c1aaff0cd9d9c` was pushed as `9.0.30`, peels to that exact commit, and `git cat-file -t 9.0.30` returned `tag`. Post-release receipt PR [#199](https://github.com/lsmc-bio/dayhoff/pull/199) merged as `8fb385640e7755995ebac86b5a219ffc803d2baa`, terminalizing the Dayhoff-local ledger without moving the release tag. | Dayhoff release and durable receipt are complete without admin override. |
| AMD-FRESH-001 | Scope | Run fresh from these releases forward; leave completed analyses untouched and add no recall/reuse DAG. | SUCCESS | plan_amendment | Gate 0 | Explicit user decision and amended DayOA ledger; the ordinary production targets remain the validation boundary. | Vendor issue #35 and completed-analysis recall are no longer release gates. |
| AMD-GANON-001 | Scope | Disable Ganon2 in the 16.0.12 Bjuice/Inflection overlays while its separate work continues. | SUCCESS | plan_amendment | Gate 0 | Explicit user direction; DayOA candidate `e2516ff5` uses `multiqc_qc.disable_tools=[unmapped_metagenomics_ganon2]` and `enable_tools=[]` in both in-scope overlays; 101 focused tests pass. | No Ganon2 rule/database or substitute metagenomics caller belongs in this release DAG. The unrelated active build remains untouched. |
| AMD-MANIFEST-001 | Provenance/catalog | Remove the global pre-run artifact inventory, retain stable DAG PNG rendering, and add explicit scoped manifest targets for ILMN/ONT/ULTIMA SeqQC, Bjuice, and ILMN/ULTIMA/ONT/CG solo kitchensink. | ATTEMPTING_BUGFIX | plan_amendment | Gate 0 | Explicit user approval; DayOA now has eight rule-owned same-schema manifests whose rows are all `important` and whose written paths are declared inputs, including stable `dags/dag.png`. DYEC source and packaged catalogs are byte-identical, add the approved target to active and immutable `19.0.33` commands, remove the obsolete global producer switch, and default only DAG generation on. Capsule `...t1900z` proved DayOA/Snakemake `rc=0` but controller `rc=24` because it watched obsolete timestamped DAGs. Capsule `codex-hiomr2-16012-hg002-5x5-20260827t1907z` proved the stable PNG was captured and again returned DayOA/Snakemake `rc=0` with zero submissions, but controller `rc=25` because its exact pinned-checkout runtime allowlist omitted its own `.dyec/controller-dag.png` evidence path. That single generated evidence file is now explicitly allowlisted alongside `.dyec/controller.log`; no directory-wide exemption is added. | Obtain the exact fresh production-shaped controller/DayOA/Snakemake `rc=0` proof and exact stable DAG evidence. |
| CLI-001 | Sentieon CLI | Restrict `--haploid_bed` to `--only_cnv`/`--only_svs`, validate fork `1.7.3i`, and publish its annotated tag. | SUCCESS | active_product_contract | Gate 3 | PR #4 merged normally; `173 passed, 1 skipped`; annotated tag object `690848bd` peels to `50aeace1`. | Issue #35 remains tracked but is nonblocking because core does not use `--haploid_bed`. |
| DAY-001 | DayOA | Restore supported generic-scope core argv, prove isolated routed CNV/SV behavior, implement product-scoped manifests, obtain exact dry `rc=0`, and publish annotated tag `16.0.12`. | IN_PROGRESS | active_product_contract | Gate 3 | Capsule `...t1900z` used behavior checkpoint `4f9f6621`; DayOA and Snakemake returned `rc=0` with zero submissions and rendered the expected 118-job closure with no Ganon2 or Jasmine job. Only the stale DYEC controller DAG filename contract failed. The DayOA candidate is clean and pushed at ledger checkpoint `41fbc943`; broad HIOMR2 contracts pass (`482 passed, 1 skipped`). | Repeat the exact proof with the corrected DYEC stable-DAG monitor, then release DayOA only after all three attributed return codes are zero. |
| DYEC-001 | DYEC | Set global and command-catalog DayOA pins exactly to released `16.0.12`, add explicit manifest targets to SeqQC, solo-kitchensink, and Bjuice+Inflection commands, validate, and publish annotated tag `19.0.33`. | IN_PROGRESS | config_or_startup_contract | Gate 4 | The isolated candidate sets `CURRENT_DYEC_BUILD=19.0.33`, retargets active/global commands to DayOA `16.0.12`, adds the eight approved scoped-manifest targets to the corresponding command families, removes the global manifest producer option, defaults DAG rendering on, and keeps the two catalog copies byte-identical. Focused pin/catalog/preflight tests are `13 passed, 23 skipped`. | Exact candidate dry proof and released DayOA `16.0.12` remain required before DYEC commit/tag promotion. |
| LOCAL-001 | Operator checkout | Update the DYEC used from `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` to released `19.0.33` without losing or absorbing user-owned dirty files. | BLOCKED | config_or_startup_contract | Gate 5 | Exact release is unavailable; ordinary checkout is dirty and divergent. | Use a non-destructive reviewed update after DYEC-001. |
| CLUSTER-001 | Deployment | Resolve the exact active cluster or clusters and state files, prove expected identities, then run `dyec headnode configure --force` from released `19.0.33`. | IN_PROGRESS | active_product_contract | Gate 5 | Public `cluster-info` found `bjuiceval-19024` and service-owned `ursa-m-rgx-k53f`. The Bjuice cluster has exact state file `/Users/jmajor/.config/daylily/state_bjuiceval-19024_20260824000053.json`, zero active DayOA controllers, and one unrelated 192-core Ganon build (`16371`) still running. The Ursa cluster is idle but has no exact local create-state file and will not be configured from guessed credentials. | Wait for the Bjuice job to finish naturally and for released `19.0.33`; do not disrupt the job or infer Ursa deployment identity. |
| RUN-001 | Inputs/catalog | Validate the exact 5x ILMN plus 5x ONT six-manifest fixture and render the complete ordinary Bjuice plus Inflection packaging command with DYEC `19.0.33`, DayOA `16.0.12`, and `bjuice_manifest`. | IN_PROGRESS | contract_test | Gate 6 | The packaged `hg002_bjuice_verified_5x5x_fastq` six-manifest fixture and Bjuice identity are resolved. Exact scoped-manifest target names, release identities, and final launch render remain pending. | No recall target, alternate fixture, previous-artifact inputs, or reduced target substitution. |
| RUN-002 | Dry proof | Launch one fresh exact-candidate dry controller and obtain attributable `rc=0` with zero submitted workflow jobs. | ATTEMPTING_BUGFIX | contract_test | Gate 6 | Capsules `...t1900z` and `...t1907z` both returned DayOA/Snakemake `rc=0`, zero submissions, and the expected 118-job closure with no Ganon2 or Jasmine job. The first exposed the stale timestamped-DAG monitor (`controller rc=24`); the second captured stable DAG evidence but exposed its missing exact runtime-path allowlist entry (`controller rc=25`). `.dyec/controller-dag.png` is now an explicit controller-owned generated evidence path in the immutable-checkout verifier. | Commit/push the exact allowlist correction, then create a new analysis identity/root using DayOA `41fbc943`. Require controller/DayOA/Snakemake `rc=0`, zero submissions, and an attributed nonempty stable DAG PNG. |
| RUN-003 | Live proof | Continue the same capsule with only `-n` removed and run the complete requested workflow to attributable `rc=0`. | BLOCKED | active_product_contract | Gate 6 | Depends on RUN-002. | Failures are diagnosed in scope; no Slurm intervention or unapproved fallback. |

## Acceptance

- Every released tag is numeric, annotated, immutable, and points to a clean
  tested commit reachable from the repository's owning release branch.
- The configured headnode reports exact released DYEC and DayOA identities and
  a clean DayOA source checkout.
- The final workflow receipt proves the explicit Bjuice and Inflection targets,
  the exact slim-data fixture, the exact release commits, and terminal
  controller `rc=0`.

## Live inventory receipts

- At `2026-08-27T12:40Z`, `dyec cluster-info --profile lsmc
  --region us-west-2` returned exactly `bjuiceval-19024` and
  `ursa-m-rgx-k53f`, both `UPDATE_COMPLETE`.
- `bjuiceval-19024` headnode is `i-0ff7f501b24c95530`; controller inventory
  was authoritative with zero active controllers. At `2026-08-27T16:28Z`,
  Slurm job `16371` (`ganon2_blood_oral_ref_20260827_v1`) remained `RUNNING`
  on 192 CPUs at elapsed `31:19`. Amendment `AMD-GANON-001` removes its output
  from the 16.0.12 workflow dependency closure, so it no longer blocks the next
  zero-submission dry proof. Force reconfiguration remains held until that
  independent job terminates naturally; the job will not be interrupted.
- `ursa-m-rgx-k53f` headnode is `i-05f4399b13850c049`; it had zero controllers
  and zero Slurm jobs, but it is tagged `cluster-use=ursa`, was created by the
  service identity, and has no exact local state file. It is outside the
  eligible direct-configure set unless its owning deployment supplies exact
  state or both exact deploy-key options.

The ledger is active. The overall objective is not complete while any row is
`OPEN` or `BLOCKED`.
