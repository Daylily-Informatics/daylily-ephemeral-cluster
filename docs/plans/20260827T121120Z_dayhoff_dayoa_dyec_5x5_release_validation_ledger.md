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

## Gate 0 inventory

- Dayhoff GitHub default branch is currently `jemdev10` at `ee0cef67`; its
  non-default `main` is a strict 66-commit descendant at `3fbf3a9e` and already
  contains PR #196 plus the cluster-sweeper prerequisites. The supplied
  handoff commit `13259de0` adds the terminal live-policy receipt and
  integration instructions. Maximum numeric tag: `9.0.29`; candidate release:
  `9.0.30`.
- The ordinary Dayhoff checkout is dirty and is not a release source. A clean
  integration worktree will begin at `origin/jemdev10`, advance through the
  complete `origin/main` prerequisite line, and then apply `13259de0`.
- DayOA candidate worktree:
  `/Users/jmajor/projects/lsmc/.codex-worktrees/hiomr2-16-0-12-integration/daylily-omics-analysis`;
  branch `codex/hiomr2-16-0-12-integration`; head `896fe88f`; maximum numeric
  tag `16.0.11`; candidate release `16.0.12`.
- Sentieon CLI review head is `4218c04`; tag `1.7.3i` does not exist. Upstream
  issue #35 remains open without a vendor response. The candidate deliberately
  rejects Hybrid small-variant/gVCF execution when `--haploid_bed` is present.
- DYEC candidate worktree:
  `/Users/jmajor/projects/lsmc/.codex-worktrees/dyec-19-0-33-dayoa-16-0-12`;
  branch `codex/dyec-19-0-33-dayoa-16-0-12`; head `efc03fb0`; maximum numeric
  tag `19.0.32`; candidate release `19.0.33`.
- The requested operator checkout
  `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` contains user-owned
  modified and untracked evidence. It must not be reset, cleaned, or switched
  destructively.
- The active catalog fixture is the explicit
  `hg002_bjuice_verified_5x5x_fastq` six-manifest profile. The exact Bjuice plus
  Inflection command, cluster, state file, profile, cost center, and analysis
  identity remain to be resolved through the public CLI before launch.

## Control ledger

| ID | Area | Requirement | Status | Category | Gate | Evidence / blocker | Terminal note |
|---|---|---|---|---|---|---|---|
| DH-001 | Dayhoff | Integrate the complete `main` sweeper prerequisite line and supplied handoff into a clean branch from the actual default `jemdev10`. | SUCCESS | feature_implementation | Gate 1 | Clean branch advanced `ee0cef67` through `3fbf3a9e` and applied handoff as `b15444f`. | Full prerequisite line and supplied receipt are present without touching the dirty ordinary checkout. |
| DH-002 | Dayhoff | Run focused and broad attributable tests, merge through a green PR without admin override, and push annotated tag `9.0.30`. | IN_PROGRESS | contract_test | Gate 2 | PR [#197](https://github.com/lsmc-bio/dayhoff/pull/197) is at `c3ebad2`. Review hardening fixed deployment-scoped paths, strict cleanup S3 destination shape, retired-contract tests, real refresh identity validation, and the Ursa `11.0.50` pin. Every Ursa sidecar now uses an exact credential-free config overlay at `URSA_CONFIG_PATH` and excludes Sysman identity from its environment. Full and Ursa-only rerenders share retired-key cleanup; the full-rerender regression proves both web and sidecar configs omit retired scheduler and `ursa_run_directory_analysis_*` keys. Focused tests pass `326/326`; Ruff, diff checks, and CodeQL pass. The 12 remaining non-E2E failures reproduce exactly on pristine `9.0.29`; E2E is unconfigured without `KAHLO_BASE_URL`. | Fresh CodeRabbit and Codex reviews were requested on `c3ebad2`; CodeRabbit remains in progress. Normal review clearance, merge, and annotated tag remain. |
| CLI-001 | Sentieon CLI | Resolve supported Hybrid haploid small-variant/gVCF behavior, validate fork `1.7.3i`, and publish its annotated tag. | BLOCKED | active_product_contract | Gate 3 | Sentieon issue #35 remained open with no vendor response at `2026-08-27T13:14:31Z`. Official `main`/`dev` inspection on `2026-08-27` found haploid BED processing only in `dnascope-longread`, which requires `haploid_model` and `haploid_hp_model`; official Hybrid has no such path and the installed Hybrid bundle lacks those members. The current fork therefore rejects haploid Hybrid core. | Vendor answer or executable/model proof is required; parser-only enablement is prohibited. |
| DAY-001 | DayOA | Finish the scientifically supported XY core contract, exact candidate tests, and publish annotated tag `16.0.12`. | BLOCKED | active_product_contract | Gate 3 | DayOA ledger HYB-002/ENV-001/VAL-005/REL-DAY remain blocked on CLI-001. | Do not tag a release that cannot run the requested male HG002 fixture. |
| DYEC-001 | DYEC | Set global and command-catalog DayOA pins exactly to released `16.0.12`, render/test the Ganon and HIOMR2 rows, and publish annotated tag `19.0.33`. | BLOCKED | config_or_startup_contract | Gate 4 | Source candidate and baseline comparison are complete; `16.0.12` does not yet exist. | Depends on DAY-001. |
| LOCAL-001 | Operator checkout | Update the DYEC used from `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster` to released `19.0.33` without losing or absorbing user-owned dirty files. | BLOCKED | config_or_startup_contract | Gate 5 | Exact release is unavailable; ordinary checkout is dirty and divergent. | Use a non-destructive reviewed update after DYEC-001. |
| CLUSTER-001 | Deployment | Resolve the exact active cluster or clusters and state files, prove expected identities, then run `dyec headnode configure --force` from released `19.0.33`. | IN_PROGRESS | active_product_contract | Gate 5 | Public `cluster-info` found `bjuiceval-19024` and service-owned `ursa-m-rgx-k53f`. The Bjuice cluster has exact state file `/Users/jmajor/.config/daylily/state_bjuiceval-19024_20260824000053.json`, zero active DayOA controllers, and one unrelated 192-core Ganon build (`16370`) still running. The Ursa cluster is idle but has no exact local create-state file and will not be configured from guessed credentials. | Wait for the Bjuice job to finish naturally and for released `19.0.33`; do not disrupt the job or infer Ursa deployment identity. |
| RUN-001 | Inputs/catalog | Validate the exact 5x ILMN plus 5x ONT six-manifest fixture and render the complete Bjuice plus Inflection packaging command with DYEC `19.0.33` and DayOA `16.0.12`. | BLOCKED | contract_test | Gate 6 | Exact releases and cluster identity are pending. | No alternate fixture or reduced target substitution. |
| RUN-002 | Dry proof | Launch one fresh exact-candidate dry controller and obtain attributable `rc=0` with zero submitted workflow jobs. | BLOCKED | contract_test | Gate 6 | Depends on RUN-001. | The resulting analysis ID/root/checkout/config becomes the live capsule. |
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
  was authoritative with zero active controllers, but Slurm job `16370`
  (`ganon2_blood_oral_ref_20260827_v1`) remained `RUNNING` on 192 CPUs at
  elapsed `4:41:06`. Force
  reconfiguration is held until that independent job terminates naturally.
- `ursa-m-rgx-k53f` headnode is `i-05f4399b13850c049`; it had zero controllers
  and zero Slurm jobs, but it is tagged `cluster-use=ursa`, was created by the
  service identity, and has no exact local state file. It is outside the
  eligible direct-configure set unless its owning deployment supplies exact
  state or both exact deploy-key options.

The ledger is active. The overall objective is not complete while any row is
`OPEN` or `BLOCKED`.
