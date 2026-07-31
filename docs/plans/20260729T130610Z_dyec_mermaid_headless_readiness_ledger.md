# DYEC Mermaid Headless-Shell Readiness Ledger

Date: 2026-07-29

## Objective

Remove the double-browser Mermaid bootstrap behavior observed on the Ursa lane:

- pin the DAYOA Node.js dependency;
- install Mermaid from a repository-owned npm lockfile with `npm ci`;
- install Mermaid CLI with `PUPPETEER_SKIP_DOWNLOAD=true`;
- explicitly install and select the pinned Chrome headless-shell payload;
- write a versioned DAYOA-environment readiness marker only after a real Mermaid PDF smoke succeeds;
- make Linux `dyoainit` repair an existing environment when that marker or its required executables are absent, and fail if readiness cannot be established;
- remove DYEC's separate regular-Chrome override so the cloned DayOA runtime owns browser selection.

No live cluster, workflow, release, commit, push, or tag action is in scope for this implementation.

## Control Ledger

Controlling plan: user request in the active Codex task

Ledger path: `docs/plans/20260729T130610Z_dyec_mermaid_headless_readiness_ledger.md`

Gate 0 baseline:

- DYEC repo: `/Users/jmajor/projects/lsmc/daylily-ephemeral-cluster`, branch `codex/hiomr2-catalog-repair`, HEAD/tag `f4cc860b` / `15.0.24`, dirty before this work.
- Pre-existing DYEC tracked changes not owned by this work: `config/daylily_pipeline_command_catalog.yaml`, `daylily_ec/resources/payload/config/daylily_pipeline_command_catalog.yaml`, and `tests/test_repository_catalog.py`.
- Pre-existing DYEC untracked work includes `bkup/`, existing `docs/plans/**` ledgers/artifacts, reports, recordings, and temporary run-QC/export artifacts; none are to be modified.
- DayOA repo: `/Users/jmajor/projects/lsmc/daylily-omics-analysis`, branch `codex/feat-hiomr2-sentieon-cli-fidelity-13.0.72`, HEAD/tag `896b0708` / `13.0.76`, dirty before this work.
- Pre-existing DayOA tracked changes not owned by this work: `config/external_tools/multiqc_config.yaml`, `docs/plans/20260729T075020Z_hiomr2_cli_fidelity_execution_ledger.md`, four focused HIOMR2/HTD tests, four HIOMR2/QC rule or script files, and related new QC ledger/script files. None are to be modified.
- Source sweep: `rg -l 'MERMAID_CHROME|PUPPETEER_EXECUTABLE_PATH|chrome-headless-shell|PUPPETEER_SKIP_DOWNLOAD|readiness marker|runtime-ready' daylily_ec config tests --glob '!daylily_ec/resources/payload/quarantine/**'` found two active DYEC files: the generated headnode runner and its test.
- Source sweep: `rg -l 'DAYOA_MERMAID|PUPPETEER_EXECUTABLE_PATH|chrome-headless-shell|PUPPETEER_SKIP_DOWNLOAD|runtime-ready|readiness marker' config dyoainit tests` found two active DayOA files: the installer and its contract test.
- Ownership finding: DYEC currently hardcodes Puppeteer's regular Chrome path; the active Mermaid installer and `dyoainit` are owned by DayOA. The smallest durable repair therefore spans these two clean source surfaces.
- Baseline DYEC test: `source ./activate && pytest -q tests/test_script_entrypoints.py::TestRunOmicsAnalysisHeadnodeScript::test_main_launches_workflow_session` -> `1 passed`.
- Baseline DayOA test: activate DYEC, then `pytest -q tests/test_shell_wrapper_contracts.py::test_dayoa_environment_declares_mermaid_cli_for_pipeline_reports` -> `1 passed`.
- Live-system limit: no headnode mutation or live PDF smoke was requested. Local contract tests will prove command composition and marker gating; a real Linux install remains a release/live acceptance step.

| ID | Area/Repo | Requirement/Surface | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| MER-001 | DayOA installer | Install Mermaid CLI without Puppeteer's implicit browser download. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | `config/day/day_env_installer.sh` scopes `PUPPETEER_SKIP_DOWNLOAD=true` to npm installation. |  | Puppeteer's implicit browser acquisition is disabled. |
| MER-002 | DayOA installer | Explicitly install, validate, and select one pinned Chrome headless-shell payload. | SUCCESS | feature_implementation | Gate 2 | orchestrator | `config/day/day_env_contract.sh` pins `148.0.7778.97`; installer installs that exact payload, checks its executable, and exports its path. |  | One explicit headless-shell payload owns Mermaid rendering. |
| MER-003 | DayOA installer | Atomically write a versioned environment readiness marker only after a non-empty PDF smoke. | SUCCESS | feature_implementation | Gate 2 | orchestrator | Installer runs `mmdc` to PDF, checks `-s`, then atomically moves the temporary marker into the conda prefix. |  | The marker cannot precede a successful real PDF render. |
| MER-004 | DayOA `dyoainit` | Require valid marker, `mmdc`, and headless-shell; repair an existing incomplete environment and fail hard if repair fails. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Linux `dyoainit` calls `dayoa_mermaid_runtime_ready`, reruns the installer on failure, rechecks, and returns nonzero if still incomplete. |  | Existing but incomplete DAYOA environments no longer bypass repair. |
| MER-005 | DYEC headnode runner | Remove the regular-Chrome override and rely on successful cloned-DayOA initialization. | SUCCESS | removable_compatibility_debt | Gate 1 | orchestrator | Removed `MERMAID_CHROME` and the regular-Chrome `PUPPETEER_EXECUTABLE_PATH` export from `daylily_run_omics_analysis_headnode.py`; `dyoainit` failure already propagates. |  | DYEC no longer selects or provisions a second browser. |
| MER-006 | Tests | Add focused positive and negative contracts for skip-download, explicit payload, PDF-gated marker, existing-env repair, and absence of regular-Chrome override. | SUCCESS | contract_test | Gate 5 | orchestrator | Three DayOA Mermaid tests passed; DYEC's generated-runner test passed; the broader DYEC headnode selection passed 52 tests. A broader DayOA-file probe found three unrelated failures from the pre-existing dirty coverage rewrite and macOS manifest preflight, so those user-owned surfaces were not changed. |  | Focused positive and negative contracts cover all requested behavior. |
| MER-007 | Acceptance | Run focused tests and source checks without altering unrelated dirty work. | SUCCESS | contract_test | Gate 5 | orchestrator | `bash -n` and both repos' `git diff --check` passed; focused pytest selections passed; `npm ci --dry-run --ignore-scripts` resolved the lock to 258 packages; no repository `node_modules` was created. |  | Local source and dependency-contract acceptance is complete. |
| MER-008 | DayOA environment | Pin the Node.js version in `config/day/day.yaml`. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | `config/day/day.yaml` and the shared runtime contract pin `nodejs=22.23.1`; Conda-forge inspection confirmed that exact version for `linux-64` and `osx-arm64`; the installer reconciles existing environments to the same version. |  | New and repaired DAYOA environments use the same exact Node.js version. |
| MER-009 | DayOA npm runtime | Install Mermaid from a repository-owned npm lockfile using `npm ci`. | SUCCESS | config_or_startup_contract | Gate 2 | orchestrator | Added `config/day/npm/mermaid-cli/package.json` and lockfile v3; exact direct pins are Mermaid CLI 11.15.0, Puppeteer 24.43.1, and Puppeteer browsers 2.13.2; installer stages those files and runs `npm ci`. |  | Global semver-resolving npm installation has been replaced by the checked-in lock contract. |

## Final Report

All rows terminal: yes

Objective complete: yes

Status counts:

- SUCCESS: 9
- DUPLICATE: 0
- NO_LONGER_NEEDED: 0
- FAIL: 0
- BLOCKED: 0
- ATTEMPTING_BUGFIX: 0
- IN_PROGRESS: 0
- OPEN: 0

Changed files:

- DYEC: `daylily_ec/scripts/daylily_run_omics_analysis_headnode.py`, `tests/test_script_entrypoints.py`, and this ledger.
- DayOA: `config/day/day.yaml`, `config/day/day_env_contract.sh`, `config/day/day_env_installer.sh`, `config/day/npm/mermaid-cli/package.json`, `config/day/npm/mermaid-cli/package-lock.json`, `dyoainit`, and `tests/test_shell_wrapper_contracts.py`.

Validation:

- DayOA Mermaid-focused pytest selection: 3 passed.
- DYEC generated-runner test: 1 passed.
- DYEC run-omics/headnode-focused selection: 52 passed.
- `npm ci --dry-run --ignore-scripts --no-audit --no-fund`: resolved 258 locked packages successfully; the expected local engine warning reports Node 25.6.1 versus the pinned deployment Node 22.23.1.
- `bash -n` for the three changed shell files: passed.
- `git diff --check` in both repos: passed.
- Broader DayOA shell-wrapper probe: 3 unrelated failures, specifically two assertions against the pre-existing dirty `calc_coverage_evenness_two.smk` rewrite and one existing macOS/date plus manifest-fixture preflight failure. These are outside this change and were not modified.

Non-success terminal rows:

- None.

Residual risks:

- A real Linux Mermaid PDF smoke is not performed by local static contract tests.
- No commit, push, tag, headnode configuration, or live workflow action was performed.
