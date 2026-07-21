# DAY-EC Mermaid Headnode Runtime Dependencies Ledger

Created: 2026-07-21T01:46:41Z

## Objective

Release the next DAY-EC patch from the exact `13.0.4` lineage with the Ubuntu
runtime libraries required by Puppeteer Chrome headless. Update Ursa to pin that
immutable release before any further SeqRunQC replay or cluster provisioning.

## Scope And Safety

- Source worktree: `/Users/jmajor/projects/lsmc/repos_work/daylily-ephemeral-cluster-13.0.5-mermaid`
- Branch: `codex/dyec-mermaid-runtime-deps-20260721`
- Base tag: annotated `13.0.4`, peeled commit
  `c9c86fd79cc76e79cc3309e100e6e9064f4255e9`
- Expected release: `13.0.5`
- No workflow replay, cluster provisioning, AWS mutation, production deployment,
  teardown, budget change, Bloom change, Dewey change, or OWY cron enablement is
  authorized by this ledger.
- Do not disable the Chrome sandbox or add a fallback renderer. Missing browser
  runtime requirements must continue to fail explicitly.

## Gate 0 Inventory

- The worktree was clean at creation and exactly matched DAY-EC `13.0.4`.
- `13.0.4` is the current maximum remote DAY-EC tag. Its tag object is
  `17ddd8d0404ba7cb8cce1a366eb18d3da1e18a28`; its peeled commit is recorded
  above.
- The `13.x` release lineage is based on `main`. The GitHub default `jem-dev`
  branch has diverged from this lineage and contains older release work; it will
  not be broadly merged into this patch.
- The canonical and packaged Ubuntu post-install scripts were byte-identical at
  Gate 0:
  `config/day_cluster/post_install_ubuntu_combined.sh` and
  `daylily_ec/resources/payload/config/day_cluster/post_install_ubuntu_combined.sh`.
- The existing package block does not declare the documented Puppeteer Chrome
  headless runtime libraries.
- Production ILMN analysis `M-RGX-CSWQ` on cluster
  `ursa-m-rgx-cszh-r2` failed before Snakemake or Slurm. The preserved controller
  log at
  `s3://lsmc-ssf-sequencing-data/derived/analysis_results/cluster_fsx_auto_cleanup/analysis_results/ursa-m-rgx-cszh-r2/M-RGX-CSWQ/daylily-omics-analysis/.dyec/controller.log`
  shows Chrome headless shell `148.0.7778.97` was installed, followed by
  `TimeoutError: Timed out after 30000 ms while waiting for the WS endpoint URL`
  during the mandatory Mermaid smoke render.
- Prior repo evidence records the same cold-start timeout later succeeding on a
  supported initialization retry. This patch therefore supplies the supported
  browser runtime at cluster bootstrap; it does not weaken the mandatory smoke
  test or silently retry a failed analysis.

## Execution Ledger

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| DYEC-001 | Gate 0 | Freeze exact source, release lineage, production failure, and safety boundaries | SUCCESS | plan_amendment | Gate 0 | orchestrator | This ledger; clean `13.0.4` worktree; preserved S3 controller log |  | Inventory recorded before source edits. |
| DYEC-002 | Bootstrap | Install the explicit Ubuntu runtime packages required to start Puppeteer Chrome headless | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Canonical and packaged post-install scripts contain the explicit Chrome runtime package set; `bash -n` and byte-for-byte mirror checks pass. |  | Runtime libraries are installed during normal Ubuntu cluster bootstrap without disabling the browser sandbox. |
| DYEC-003 | Tests | Assert browser dependency coverage, canonical/package mirror equality, and no sandbox bypass | SUCCESS | contract_test | Gate 4 | orchestrator | `python -m pytest -q tests/test_headnode_init.py tests/test_lsmc_bio_fork_contract.py tests/test_packaged_defaults.py` -> 56 passed; `tests/test_headnode_init.py` asserts the package set and rejects `--no-sandbox`. |  | Focused source and packaged-payload contracts pass. |
| DYEC-004 | Release identity | Advance self-release references to `13.0.5` without changing the DayOA command-catalog pin | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Canonical and packaged `config/daylily_cli_global.yaml` now name `13.0.5`; mirror comparison passes; `DAYOA_DEFAULT_TAG` remains `13.0.16`. |  | Release identity advanced without unrelated catalog changes. |
| DYEC-005 | Validation | Run focused and complete DAY-EC tests, Ruff check, Ruff format check, and diff check | SUCCESS | contract_test | Gate 5 | orchestrator | Isolated `.venv` installed the exact `pyproject.toml` dependencies including `aws-parallelcluster==3.15.0`; full suite -> 2,231 passed, 11 skipped in 93.59s. Changed Python files pass Ruff. Shell syntax, both payload mirrors, and `git diff --check` pass. Repo-wide Ruff reports 34 pre-existing errors in historical `docs/` scripts and repo-wide Ruff format reports pre-existing formatting debt; neither touches this patch. |  | Complete tests pass under the declared dependency contract; changed surfaces are clean. |
| DYEC-006 | Release | Merge reviewed patch to the `13.x` release branch and publish immutable annotated tag `13.0.5` | SUCCESS | feature_implementation | Gate 5 | orchestrator | Commit `3b1fa7965bf427238d2a7b556004456a79caf8fd`; PR `lsmc-bio/daylily-ephemeral-cluster#52`; normal merge `09cdacefd990e4232e721b2f23795f9136ec89be`; annotated tag object `100ed7a11c36fc24d69b28a8f0c5a72cdce33fdb`, peeled to the merge commit. |  | Immutable numeric release is published on the reviewed `main` lineage. |
| URSA-001 | Ursa | Pin Ursa exactly to released DAY-EC `13.0.5`, test, release, and deploy only Ursa services | IN_PROGRESS | config_or_startup_contract | External ledger | orchestrator | Ursa controlling ledger `docs/plans/20260719T122247Z_ursa_10_0_1_owy_seqrunqc_acceptance_ledger.md`; DAY-EC `13.0.5` is available remotely. |  | Ursa pin and release work proceeds in the Ursa repository. |
| LIVE-001 | Acceptance | Replay the persisted ILMN identity and provision another compatible replacement cluster | BLOCKED | active_product_contract | Live approval | orchestrator | Prior approved replacement `ursa-m-rgx-cszh-r2` was consumed and automatically swept after export. | A new replay would replace the failed FSx analysis path again and provision a new cluster. | Requires a fresh exact live-effect approval after patched releases are deployed. |

## Acceptance

This ledger is complete only when all DAY-EC rows are terminal, the release tag
is verified as annotated and peeled to the reviewed merge commit, and Ursa has an
immutable DAY-EC release available to pin. Live SeqRunQC success remains owned by
the Ursa and OWY controlling ledgers.

## DAY-EC Release Evidence

- PR: `https://github.com/lsmc-bio/daylily-ephemeral-cluster/pull/52`
- Merge commit: `09cdacefd990e4232e721b2f23795f9136ec89be`
- Tag: annotated `13.0.5`
- Tag object: `100ed7a11c36fc24d69b28a8f0c5a72cdce33fdb`
- Peeled release commit: `09cdacefd990e4232e721b2f23795f9136ec89be`
