# HIOMR2 Release, Export, and Validation Cycles Ledger

Created: 2026-08-13T23:43:21Z
Owner: root release integrator / sole ledger writer
Cadence: one existing 20-minute heartbeat only
Cluster: `prod-cand-1703` (`lsmc`, `us-west-2`)
Safety boundary: no PyPI; no Slurm intervention; no destructive FSx/S3 action; no headnode configure while any DayOA controller is active.

## Objective

Carry the active full-coverage recovery to attributable rc=0; release its proven source fixes through annotated GitHub-only prereleases; export the exact analysis root without deleting FSx data; update the neutral local DYEC install and safely configure the headnode; integrate `vcf-sv-stats` `1.0.1` plus `lsmc-bio/MultiQC` `1.36.dev0-lsmc.15` into every active MultiQC runtime, the HIOMR2 Inflection subset, and the analytical package; then execute a new, version-pinned HG002 HIOMR2 slim 5x ILMN by 5x ONT kitchensink-mega Inflection-packaging validation from new dry/live analysis roots. If that fresh run requires source changes, release them after rc=0 and execute exactly one additional fresh confirmation run. Never start a third fresh run.

## Frozen operating contract

- Use only the existing heartbeat `monitor-and-recover-hg002-full-coverage`, every 20 minutes, in this task.
- Run DayOA only as `ubuntu` in a persistent one-window/one-pane interactive login-bash tmux using separate `source dyoainit`, `dy-a slurm hg38`, and `dy-r` commands. Never invoke raw Snakemake.
- Dry commands use `-j 333 -T 0 -p --rerun-triggers mtime -n`, no `-k`; live commands are byte-identical except for removal of `-n`.
- Fresh validation uses HG002 slim inputs at exactly 5x ILMN and 5x ONT and the HIOMR2 kitchensink-mega Inflection-packaging target rendered from the exact released DYEC catalog.
- Each fresh attempt uses new, distinct dry and live analysis IDs/directories and a new tmux session. Never reuse or overwrite a prior analysis root.
- While a controller or attributable jobs are active, remain read-only. Do not configure the headnode, edit source, commit, push, cancel, requeue, or administer Slurm.
- Diagnose a natural nonzero terminal result from exact logs/artifacts. Edit only under the analysis-root write lock. Run no Git tests on the headnode. Iterate the supported dry/live path until jobs launch, then return to the 20-minute monitor.
- Commit and push source fixes only after the attributable workflow reaches rc=0. Never commit generated analysis artifacts.
- Release from the highest remote annotated non-`v` semver tag proven to descend from the prior release floor. Compute the next patch immediately before tagging. Tags are annotated and immutable.
- GitHub releases are non-draft prereleases with no assets. No PyPI, `twup`, or `twine upload` action is allowed.
- Exports are exact no-delete FSx-to-S3 transfers under the authoritative derived prefix. Record visits, DRA/task IDs, receipt, counts, bytes, and the full final S3 prefix.
- Headnode configuration is allowed only after its active-controller guard passes naturally. Never bypass that guard.
- Preserve every existing versioned environment YAML byte-for-byte. Create a new immutable MultiQC YAML pinned to `1.36.dev0-lsmc.15`, update all active MultiQC rule references, and create a separate immutable `vcf-sv-stats` YAML pinned to the supported `1.0.1` GitHub release wheel. No PyPI or Conda-channel publication is permitted.
- Run `vcf-sv-stats` before the Inflection MultiQC report for every explicitly packaged variant VCF callset, including singleton callers and combined callsets such as TrusSV. Stage every digest-bound summary into the isolated Inflection report and publish the summaries in the analytical package with explicit manifest roles.
- Slack Mike K (`U0AQXA08V6Z`) and John M (`U08TN63K73M`) in an existing shared conversation when possible. Every rc=0 update must say that it is validation progress, not final stable data ready for gap analysis; stable/gap-analysis designation waits for repeated error-free executions, after which the next gap-analysis target will be explicitly named.

## Current immutable evidence

- Current analysis root: `/fsx/analysis_results/prod-cand-1703/pc1703-hg002-fc-ont0-24-mega-ifx-1409-20260813`
- Current recovery tmux: `pc1703_hg002_fc_ont0_24_fastqc15_recovery`
- Current run evidence: `/home/ubuntu/daylily-runs/pc1703_hg002_fc_ont0_24_fastqc15_recovery/live3.log` and `live3.rc`
- Current checkout started from DayOA `14.0.9` commit `f4c7aa7e15f7dca602059097cb2314f96f05a826`; its intended tracked repair includes `workflow/rules/fastqc.smk`.
- Current neutral local DYEC is `17.0.9`, tag object `630d00507ccfe5f62a5099dbb142cf06ba0282fb`, peeled commit `a0a60384724530a079a372735e773f905c6c4f82`, pinning DayOA `14.0.10`.
- The primary DYEC checkout contains user-owned untracked files and must not be reset, cleaned, or blindly switched. Use a clean release worktree and install the final tag non-editably into DAY-EC.

## State rows

| ID | Gate | Initial status | Requirement | Terminal evidence |
|---|---:|---|---|---|
| `CURR-MON-001` | G0 | PASS | Monitor current `live3` naturally at 20-minute cadence | `live3.rc=0`; controller absent; queue empty at 2026-08-14T00:01:35Z |
| `CURR-FIX-001` | G0 | PASS | On natural failure, minimal locked headnode fix/dry/live; no headnode Git tests | FastQC tiny-lane repair; `dry2.rc=0`; live3 admitted and completed |
| `CURR-RC0-001` | G0 | PASS | Validate current requested outputs at attributable rc=0 | package manifest 27,440 B; final MultiQC SHA256 `2a58380c...`; evidence manifest SHA256 `b4ca26cc...`; lock unlocked |
| `DAYOA-REL-A-001` | G1 | PASS | Apply only proven DayOA fixes to latest eligible release ancestry; commit, push, annotated tag, GitHub prerelease | `14.0.11`; tag object `1ea96308...`; peel `ac28402c...`; [pre-release](https://github.com/lsmc-bio/daylily-omics-analysis/releases/tag/14.0.11); 0 assets; no PyPI |
| `DYEC-REL-A-001` | G1 | PASS | Pin released DayOA on active/current and new immutable snapshot; commit, push, annotated tag, GitHub prerelease | `17.0.10`; tag object `40d3c4ac...`; peel `23087e33...`; [pre-release](https://github.com/lsmc-bio/daylily-ephemeral-cluster/releases/tag/17.0.10); catalog parity; 17.0.9 hash preserved; 0 assets; no PyPI |
| `EXPORT-A-001` | G2 | PASS | No-delete export of exact current analysis root | DRA `dra-047731896d93ad47b`; task `task-0a7163e846904a2ec` SUCCEEDED; detached DELETED; 6,288 objects / 150,084,629,815 B; `s3://lsmc-ssf-sequencing-data/derived/prod-cand-1703/pc1703-hg002-fc-ont0-24-mega-ifx-1409-20260813/` |
| `SLACK-A-001` | G2 | PASS | Send Mike/John current export and release URLs with non-stable gap-analysis caveat | [Slack message](https://lsmchq.slack.com/archives/D0AQK8RB3D5/p1786666576987029) |
| `INSTALL-A-001` | G2 | PASS | Install exact released DYEC locally and configure headnode after controller guard clears | local and headnode DYEC `17.0.10`; current catalog and `day-clone --list` default DayOA `14.0.11`; controller guard clear |
| `MQC-REL-001` | G3 | PASS | Verify native `vcf-sv-stats` parser is released in the LSMC MultiQC fork | annotated `1.36.dev0-lsmc.15`; tag object `0825d82b...`; peel `c6799bec...`; includes native module plus validation hardening; focused module suite `14 passed` |
| `MQC-PIN-001` | G3 | PASS | Create a new immutable MultiQC environment pinned to `1.36.dev0-lsmc.15` and update every active MultiQC rule reference | `multiqc_v0.3.yaml`; all 20 active references moved from immutable `v0.2`; headnode prefix `b9397f6b...` materialized before live submission |
| `VSS-ENV-001` | G3 | PASS | Add immutable `vcf-sv-stats` `1.0.1` GitHub-wheel Conda environment | `vcf_sv_stats_v0.1.yaml`; exact wheel SHA256 `d5e3e89c...`; local version/verify-install smoke; headnode prefix `c16681dc...` materialized successfully |
| `VSS-RULE-001` | G3 | PASS | Run one strict digest-bound stats rule for every explicitly packaged variant VCF callset | Fresh1 rc=0; 26 source summaries plus 26 staged and 26 packaged copies; exact tool `1.0.1`, digest-bound validation, and single analysis-unit identity enforced |
| `VSS-MQC-001` | G3 | PASS | Require and stage all stats summaries before the isolated Inflection MultiQC report | Fresh1 native MultiQC data contains 349 `vcf-sv-stats` key hits, including report data sources and general-statistics metrics |
| `VSS-PKG-001` | G3 | PASS | Publish all stats summaries in the analytical package and manifest | schema `dayoa.hiomr2_inflection_analytical_package/2.2`; 26 summary roles under `qc/vcf-sv-stats`; all scoped paths present |
| `FRESH1-DRY-001` | G3 | PASS | New dry analysis root, exact released pins and slim 5x5 command; restart only after stats integration | root `pc1703-hg002-slim5x5x-mega-ifx-dyec17010-dayoa14011-dry-20260814`; retry6 rc=0; 271 jobs; 26 stats jobs; no Slurm submission |
| `FRESH1-LIVE-001` | G3 | PASS | New live root/tmux; launch exact command without `-n` | `live3.rc=0`; 271/271 steps; `WORKFLOW SUCCESS`; controller absent, matching queue empty, lock unlocked at 2026-08-14T04:30:34Z |
| `SLACK-FRESH1-START-001` | G3 | PASS | Notify Mike/John after attributable Slurm jobs submit | [Mike/John DM](https://lsmchq.slack.com/archives/D0AQK8RB3D5/p1786673040994579); includes scope and non-stable gap-analysis caveat |
| `FRESH1-MON-001` | G3 | PASS | Monitor every 20 minutes; diagnose and recover natural failures | sole heartbeat monitored the exact live3 root to natural terminal rc=0; no Slurm intervention |
| `FRESH1-RC0-001` | G3 | PASS | Validate fresh run outputs at attributable rc=0 | manifest SHA256 `0e61a88d...`; 167 declared artifacts, 168 files including manifest, 0 missing/bad hashes/undeclared; 26 VCFs, 2 CRAMs, cross-format identity true; 26 packaged stats summaries; native MultiQC module present |
| `REL-B-001` | G4 | IN_PROGRESS | If Fresh1 required source changes, release DayOA and DYEC as above; otherwise `NO_LONGER_NEEDED` | DayOA `14.0.14` annotated tag object `b05c5a2a...`, peel `8bbf0fe0...`; 1726 passed, 1 skipped; [pre-release](https://github.com/lsmc-bio/daylily-omics-analysis/releases/tag/14.0.14). DYEC `17.0.13` candidate pins active/current to `14.0.14`, preserves `17.0.12` on `14.0.13`, passed 331 focused tests and the complete suite (2539 passed, 11 skipped), and produced clean wheel/sdist metadata plus byte-identical source, payload, and wheel catalogs; annotated tag and GitHub pre-release pending |
| `EXPORT-B-001` | G4 | OPEN | No-delete export of exact Fresh1 live analysis root | DRA/task/receipt/counts/full S3 prefix |
| `INSTALL-B-001` | G4 | OPEN | Install/configure final Fresh1 release only after terminal controller | version/pin proof |
| `SLACK-B-001` | G4 | OPEN | Send Fresh1 result, export, releases, and stability caveat | conversation/message URLs |
| `FRESH2-001` | G5 | OPEN | Only if Fresh1 required actual source changes: run one additional fresh dry/live/monitor-to-terminal cycle | distinct roots/tmux, terminal evidence |
| `REL-C-001` | G5 | OPEN | If Fresh2 required fixes, release/export/configure those proven fixes; otherwise `NO_LONGER_NEEDED` | release/export/configure evidence or no-code proof |
| `FINAL-SLACK-001` | G5 | OPEN | Send final versions, releases, S3 prefix, run count, code-change disposition, and stability caveat | conversation/message URLs |
| `CLOSE-001` | G5 | OPEN | Stop after Fresh1 if no code changed, otherwise after exactly Fresh2; no third run | all rows terminal |

## Stop conditions

- Success without Fresh1 source changes: export Fresh1, send final Slack, update local/headnode as needed, mark Fresh2 and Rel-C `NO_LONGER_NEEDED`, then stop.
- Success with Fresh1 source changes: release/export/install/configure, run exactly Fresh2, perform any rc0-gated release/export/configure required by Fresh2, send final Slack, then stop. Never launch Fresh3.
- Foreign lock, missing credentials, unsafe ancestry, destructive requirement, or materially broader contract change: stop and report; do not guess.
