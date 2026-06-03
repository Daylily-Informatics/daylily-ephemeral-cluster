# HG003 Illumina Run Directory Catalog Ledger

Date: 2026-06-01

## Objective

Catalog Illumina run directories in `s3://lsmc-ssf-sequencing-data/` whose sample sheets indicate `hg003*` or `HG003*` samples, then report run metadata and matching HG003 FASTQ object sizes where present.

## Control Ledger

Controlling plan: `docs/plans/20260601T165015Z_hg003_illumina_run_catalog_ledger.md`
Ledger path: `docs/plans/20260601T165015Z_hg003_illumina_run_catalog_ledger.md`

### Gate 0 Baseline

- Repo: `/Users/jmajor/.codex/worktrees/be82/daylily-ephemeral-cluster`
- Branch: `codex/dyec515-full-catalog-20260531...origin/codex/dyec515-full-catalog-20260531`
- Pre-existing dirty files before this ledger: `AGENTS.md`, `docs/plans/20260601T144201Z_dyec_516_517_release_train_ledger.md`
- Instruction files read: `/Users/jmajor/.agents/AGENTS.md`, `/Users/jmajor/.codex/AGENTS.md`, `/Users/jmajor/.codex/memory.md`, `/Users/jmajor/.codex/memories/aws-destructive-changes.md`, `/Users/jmajor/.codex/memories/fallback_and_legacy_and_migration_support_for_code_changes_DO_NOT_UNLESS_TOLD_TO_PLEASE.md`, `/Users/jmajor/.codex/memories/raw_memories.md`, `./AGENTS.md`, `/Users/jmajor/.codex/docs/plan-ledger-workflow.md`
- Memory lookup: `/Users/jmajor/.codex/memories/MEMORY.md` showed prior DayOA/HG003/DYEC context; current S3 state must be verified live.
- Target AWS profile: `lsmc`
- Target bucket: `s3://lsmc-ssf-sequencing-data/`
- Bucket region: `us-west-2`
- AWS identity evidence: `aws sts get-caller-identity --profile lsmc --output json` -> account `108782052779`, ARN `arn:aws:iam::108782052779:root`
- Bucket location evidence: `aws s3api get-bucket-location --bucket lsmc-ssf-sequencing-data --profile lsmc --output json` -> `LocationConstraint: us-west-2`
- Top-level bucket prefixes: `.test_only/`, `_lsmc_owy_dashboard/`, `_lsmc_owy_experiments/`, `basecalls/`, `data/`, `derived/`, `raw/`, `staged_external_data/`
- Non-destructive boundary: S3 listing and object reads only; no S3 writes or deletes.

### Tracking Rows

| ID | Area | Requirement | Status | Category | Approval Gate | Owner | Evidence | Root Cause | Terminal Note |
|---|---|---|---|---|---|---|---|---|---|
| HG003-CAT-001 | Inventory | Identify Illumina run directories in the sequencing bucket that have sample sheets with `hg003*` or `HG003*` samples. | SUCCESS | feature_implementation | Gate 0: Inventory Freeze | Codex | `python docs/plans/20260601T165015Z_hg003_illumina_s3_catalog.py --profile lsmc --region us-west-2 --bucket lsmc-ssf-sequencing-data --prefix basecalls/lsmc/ssf-hq/LH01106/2026/ --prefix basecalls/lsmc/ssf-hq/lh01121/2026/ --prefix raw/lsmc/ssf-hq/LH01106/2026/ --discover-run-roots --out-prefix docs/plans/20260601T165015Z_hg003_illumina_run_catalog` -> 15 Illumina run roots discovered, 14 sample sheets read, 8 sample sheets with HG003 evidence. |  | Found 8 qualifying run directories. |
| HG003-CAT-002 | Metadata | For each matching run directory, capture run info such as flowcell, instrument, run id/date, sample sheet object, and matching sample names. | SUCCESS | feature_implementation | Gate 0: Inventory Freeze | Codex | `docs/plans/20260601T165015Z_hg003_illumina_run_catalog.runs.tsv`; verification showed `missing_run_info []` and `parse_errors []`. |  | All matching run rows include `RunInfo.xml` metadata. |
| HG003-CAT-003 | FASTQ Sizes | For each matching run directory, report matching `hg003*`/`HG003*` FASTQ objects and total size where present. | SUCCESS | feature_implementation | Gate 0: Inventory Freeze | Codex | `docs/plans/20260601T165015Z_hg003_illumina_run_catalog.fastqs.tsv`; verification showed `fastqs 230`, total `1187870235304` bytes / `1106.29 GiB`. |  | Matching HG003 FASTQ object sizes were aggregated from S3 metadata only. |
| HG003-CAT-004 | Artifacts | Write durable tabular and prose catalog artifacts under `docs/plans/`. | SUCCESS | feature_implementation | Gate 5: Final Acceptance | Codex | Wrote `docs/plans/20260601T165015Z_hg003_illumina_run_catalog.md`, `.runs.tsv`, `.samplesheets.tsv`, `.sample_rows.tsv`, `.fastqs.tsv`, `.json`, plus scanner `docs/plans/20260601T165015Z_hg003_illumina_s3_catalog.py`. |  | Durable report and machine-readable artifacts are present under `docs/plans/`. |
| HG003-CAT-005 | Acceptance | Verify all catalog rows are terminal and report objective completion status. | SUCCESS | contract_test | Gate 5: Final Acceptance | Codex | `python -m py_compile docs/plans/20260601T165015Z_hg003_illumina_s3_catalog.py`; JSON verification: `runs 8`, `fastqs 230`, `sample_sheets 8`, `parse_errors []`, `missing_run_info []`. |  | All rows terminal; objective complete for the scanned Illumina run roots. |

### Working Notes

- Treat sample sheet evidence as the primary inclusion criterion. FASTQs are reported only after a run qualifies by sample sheet content.
- Matching pattern is case-sensitive variants requested by the user: `hg003*` and `HG003*`. For practical parsing, object/sample comparisons will use a case-insensitive `^hg003` sample-token check while preserving original sample names in the output.
- Do not infer missing run metadata from service-side discovery. If `RunInfo.xml` or expected run files are absent, record that explicitly.

### Final Report

- Terminal ledger rows: 5 `SUCCESS`, 0 `BLOCKED`, 0 `FAIL`, 0 working.
- Objective completion: complete for the live S3 scope scanned.
- Live S3 scope: `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/LH01106/2026/`, `s3://lsmc-ssf-sequencing-data/basecalls/lsmc/ssf-hq/lh01121/2026/`, and `s3://lsmc-ssf-sequencing-data/raw/lsmc/ssf-hq/LH01106/2026/`.
- Discovery result: 15 Illumina run roots discovered; 14 root-level sample sheets read; 8 sample sheets contained HG003 evidence.
- Matching run directories: 8, including one raw duplicate of `20260514_LH01106_0008_A23TVNWLT4` with no FASTQs under the raw prefix.
- Matching FASTQ totals: 230 objects; 1,187,870,235,304 bytes; 1,106.29 GiB.
- Validation: scanner compiles; no sample-sheet parse errors; no matching run row missing `RunInfo.xml`.
- Non-destructive boundary held: only S3 list/head/get metadata and small text-object reads were used; no bucket writes or deletes.
