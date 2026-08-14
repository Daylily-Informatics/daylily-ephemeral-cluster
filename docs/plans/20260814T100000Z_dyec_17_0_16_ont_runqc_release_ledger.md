# DYEC 17.0.16 ONT RunQC repair release ledger

Created: 2026-08-14T10:00:00Z

## Objective

Release DYEC `17.0.16` with a strict Conda-Forge/Bioconda headnode channel
contract and a current catalog pinned to DayOA `14.0.16`, configure
`prod-cand-1703`, and start a fresh ONT RunQC catalog execution against the
existing mounted run directory.

## Gate 0

- Baseline is annotated DYEC tag `17.0.15`, commit
  `0644308e2a80edfb133654a0add6463cfb2d36cf`, in an isolated worktree.
- DayOA `14.0.16` is an annotated remote tag at commit
  `ab8a66afa65a62b4d447ce583c9e44855b6be6dc`.
- DYEC `17.0.15` was published concurrently during remediation. Its tag and
  catalog snapshot remain immutable; the ONT repair therefore uses the next
  patch release, `17.0.16`.
- The live headnode baseline had `defaults` configured with flexible channel
  priority. The failed environment solved NanoPlot `1.30.1` alongside
  Matplotlib `3.11.1` and then crashed on removed `matplotlib.cm.cmap_d`.
- Unit tests inspect installer and catalog contracts without creating or
  solving Conda environments. The fresh catalog workflow is runtime
  acceptance.
- The failed ONT analysis root is preserved. No Slurm, DRA, export, budget, or
  destructive action is authorized or required.

## Control ledger

| ID | Requirement | Status | Evidence | Terminal note |
|---|---|---|---|---|
| CONDA-001 | Configure Conda-Forge and Bioconda only, with strict priority | SUCCESS | Installer and payload mirror are byte-identical; installer tests passed | Configuration failures remain hard failures. |
| CAT-001 | Pin active catalog to DayOA `14.0.16` and append `17.0.16` snapshot | SUCCESS | Source/payload mirror, YAML parse, active-pin assertions, and byte-level mutation-boundary check passed | Every snapshot through `17.0.15` remains byte-for-byte unchanged. |
| TEST-001 | Validate through static/unit tests without building a Conda env | SUCCESS | Focused release suite: `357 passed in 133.75s`; `git diff --check` passed | No test-time solve/build occurred. |
| REL-001 | Commit, push, and publish annotated DYEC tag `17.0.16` | PENDING | Pending | Existing `17.0.15` tag remains untouched. |
| CFG-001 | Configure `prod-cand-1703` from exact DYEC `17.0.16` and verify channels | PENDING | Pending live evidence | Profile `lsmc`, region `us-west-2`. |
| DRY-001 | Run fresh ONT catalog dry run against existing mounted run context | PENDING | Pending | Must create zero Slurm jobs. |
| LIVE-001 | Launch fresh ONT RunQC catalog execution | PENDING | Pending | Preserve prior failed analysis root. |

## Final report

All rows terminal: no

Objective complete: no
